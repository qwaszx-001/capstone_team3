#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  Node A — 병원 백신 배달 자연어 명령 해석
#  역할: /llm_command(String) → groq LLM 파싱(+폴백) → /mission(String, JSON)
#
#  약국(pharmacy)에서 지정된 백신을 픽업해 지정된 병실로 배달하는
#  pick_and_place 미션 하나로 표현한다 (텔레포트: node_c_grasp 담당).
#
#  좌표/백신 목록은 config/rooms.yaml, config/vaccines.yaml 에서 로드한다.
#  GROQ_API_KEY는 프로젝트 루트 .env 에서 로드(없으면 상위 프로세스 환경변수 사용).
#
#  토픽 계약(고정):
#    In  /llm_command (std_msgs/String) — 사용자 자연어
#    Out /mission     (std_msgs/String) — RobotCommand JSON 1건
# ════════════════════════════════════════════════════════════════
import json
import os
from enum import Enum
from pathlib import Path

import rclpy
import yaml
from rclpy.node import Node
from std_msgs.msg import String
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(os.path.expanduser("~/capstone_tb3_hospital"))
ROOMS_YAML = PROJECT_ROOT / "config" / "rooms.yaml"
VACCINES_YAML = PROJECT_ROOT / "config" / "vaccines.yaml"
ENV_FILE = PROJECT_ROOT / ".env"


def _load_env_file(path: Path):
    """.env 를 os.environ 에 반영(이미 설정된 값은 덮어쓰지 않음). python-dotenv 없이 최소 구현."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _load_rooms():
    with open(ROOMS_YAML) as f:
        return yaml.safe_load(f)


def _load_vaccines():
    with open(VACCINES_YAML) as f:
        return yaml.safe_load(f)


_load_env_file(ENV_FILE)
ROOMS = _load_rooms()
VACCINES = _load_vaccines()
PHARMACY = ROOMS["pharmacy"]


class ActionType(str, Enum):
    PICK_AND_PLACE = "pick_and_place"
    STOP = "stop"


class RobotCommand(BaseModel):
    """LLM/폴백이 생성하는 구조화 명령 (이 스키마를 그대로 /mission 으로 발행)."""
    action: ActionType
    object: str = ""          # box 엔티티명 (예: vaccine_a) — node_c_grasp 텔레포트 대상
    pick_x: float = 0.0
    pick_y: float = 0.0
    place_x: float = 0.0
    place_y: float = 0.0
    yaw: float = Field(default=0.0)


def _build_system_prompt() -> str:
    room_lines = "\n".join(
        f'- {r["name"]}({r.get("blood_type", "")}): x={r["x"]}, y={r["y"]}, yaw={r["yaw"]}'
        for key, r in ROOMS.items() if key != "pharmacy"
    )
    vaccine_lines = "\n".join(f'- "{name}" → box="{v["box"]}"' for name, v in VACCINES.items())
    return f"""너는 병원 배달 로봇 명령 파서다. 한국어 명령을 RobotCommand JSON으로만 변환한다.

약국(픽업 위치): x={PHARMACY["x"]}, y={PHARMACY["y"]}

병실 목록:
{room_lines}

백신 목록(자연어 이름 → object 필드에 넣을 box 값):
{vaccine_lines}

명령에서 백신 종류와 배달할 병실을 찾아 pick_and_place 액션으로 변환하라.
pick_x/pick_y는 항상 약국 좌표, place_x/place_y/yaw는 지정된 병실 좌표, object는 위 표의 box 값을 사용한다.
병실이나 백신을 알 수 없으면 action을 "stop"으로 하라.
스키마: {{"action":"pick_and_place|stop","object":"","pick_x":0,"pick_y":0,"place_x":0,"place_y":0,"yaw":0}}
설명 없이 JSON 객체 하나만 출력."""


SYSTEM_PROMPT = _build_system_prompt()


class NodeALLM(Node):
    def __init__(self):
        super().__init__("node_a_llm")
        self.pub = self.create_publisher(String, "/mission", 10)
        self.pub_status = self.create_publisher(String, "/robot_status", 10)
        self.create_subscription(String, "/llm_command", self._on_command, 10)
        self._llm = self._init_groq()
        self._model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        self._status(f"Node A 시작 — LLM={'ON' if self._llm else 'OFF(폴백)'}")

    def _on_command(self, msg: String):
        text = msg.data
        self._status(f"명령 수신: '{text}'")
        cmd = self._parse_with_llm(text) or self._parse_fallback(text)
        self.pub.publish(String(data=cmd.model_dump_json()))
        self._status(f"미션 발행: {cmd.action.value} object={cmd.object} "
                     f"pick=({cmd.pick_x},{cmd.pick_y}) place=({cmd.place_x},{cmd.place_y})")

    def _parse_with_llm(self, text: str):
        if self._llm is None:
            return None
        try:
            resp = self._llm.chat.completions.create(
                model=self._model, temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": text}])
            data = json.loads(resp.choices[0].message.content)
            return RobotCommand(**data)
        except Exception as e:
            self._status(f"⚠️ LLM 파싱 실패({e}) → 폴백")
            return None

    def _parse_fallback(self, text: str) -> RobotCommand:
        """규칙 기반 파서. groq 차단 상황에서도 데모가 돌아가게 하는 안전망.
        - '정지/멈춰/스톱' 포함 → STOP
        - 텍스트에서 병실 이름/혈액형으로 목적지 방을 찾는다
        - 텍스트에서 백신 이름(혈액형)으로 object(box)를 찾는다
        - 방과 백신을 둘 다 못 찾으면 STOP
        """
        if any(k in text for k in ("정지", "멈춰", "스톱")):
            return RobotCommand(action=ActionType.STOP)

        # 혈액형 문자열은 "B형"이 "AB형"의 부분 문자열이라 길이가 긴 표현부터
        # 먼저 검사해야 "AB형"을 "B형"으로 오매칭하지 않는다.
        room_candidates = sorted(
            ((r["name"], r) for k, r in ROOMS.items() if k != "pharmacy"),
            key=lambda p: -len(p[0]),
        ) + sorted(
            ((r["blood_type"], r) for k, r in ROOMS.items()
             if k != "pharmacy" and r.get("blood_type")),
            key=lambda p: -len(p[0]),
        )
        target_room = None
        for key_str, r in room_candidates:
            if key_str in text:
                target_room = r
                break

        vaccine_candidates = sorted(VACCINES.items(), key=lambda p: -len(p[0]))
        target_box = None
        for name, v in vaccine_candidates:
            short = name.replace(" 독감 백신", "")
            if name in text or short in text:
                target_box = v["box"]
                break

        if target_room is None or target_box is None:
            return RobotCommand(action=ActionType.STOP)

        return RobotCommand(
            action=ActionType.PICK_AND_PLACE,
            object=target_box,
            pick_x=PHARMACY["x"], pick_y=PHARMACY["y"],
            place_x=target_room["x"], place_y=target_room["y"], yaw=target_room["yaw"],
        )

    def _init_groq(self):
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key or key.startswith("your_"):
            return None
        try:
            from groq import Groq
            return Groq(api_key=key)
        except Exception:
            return None

    def _status(self, text: str):
        self.get_logger().info(text)
        self.pub_status.publish(String(data=f"[A] {text}"))


def main(args=None):
    rclpy.init(args=args)
    node = NodeALLM()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
