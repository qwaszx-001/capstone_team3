#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  Node C — 파지/배치 노드 (IK) (TurtleBot3 / classic Gazebo 이식)
#  역할: /grasp_request → nd1_m7_ik IK 계산 → 텔레포트 파지/배치 → /grasp_result
#
#  원본(TurtleBot4/Ignition)은 `ign service -s /world/<world>/create|remove`를
#  subprocess로 셸아웃했다. classic Gazebo11은 gzserver가 자동 로드하는
#  factory 플러그인이 /spawn_entity, /delete_entity ROS2 서비스를 전역으로
#  제공하므로 네이티브 서비스 클라이언트로 교체했다 (world 이름 불필요).
#
#  토픽 계약(고정):
#    In  /grasp_request {op:"grasp"|"place", x, y}
#    Out /grasp_result(Bool) / /robot_status
#  ★ 표준안 제약: 팔 로컬 파지 타깃 y-offset ≥ 0.20 (y=0 특이점 → IK 발산)
# ════════════════════════════════════════════════════════════════
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from ament_index_python.packages import get_package_share_directory
from gazebo_msgs.srv import SpawnEntity, DeleteEntity

Y_OFFSET_MIN = 0.20  # 특이점 회피 최소 y (표준안) — 변경 금지


class NodeCGrasp(Node):
    def __init__(self):
        super().__init__("node_c_grasp")
        self.declare_parameter("sim_mode", True)
        self.declare_parameter("arm_links", [0.20, 0.18, 0.12])
        self.declare_parameter("grasp_x", 0.35)
        self.declare_parameter("grasp_y", 0.25)
        self.declare_parameter("box_model", "box1")
        self.declare_parameter("box_sdf_path", "")
        self.declare_parameter("server_timeout", 5.0)
        self.sim_mode = self.get_parameter("sim_mode").value
        self.links = list(self.get_parameter("arm_links").value)
        self.timeout = float(self.get_parameter("server_timeout").value)

        self.pub_result = self.create_publisher(Bool, "/grasp_result", 10)
        self.pub_status = self.create_publisher(String, "/robot_status", 10)
        self.create_subscription(String, "/grasp_request", self._on_request, 10)
        self._robot = self._init_arm()

        self._spawn_cli = self.create_client(SpawnEntity, "/spawn_entity")
        self._delete_cli = self.create_client(DeleteEntity, "/delete_entity")
        self._status(f"Node C 시작 (sim_mode={self.sim_mode}, IK={'ON' if self._robot else 'OFF'})")

    def _on_request(self, msg: String):
        try:
            d = json.loads(msg.data)
            op = d.get("op", "grasp")
            wx, wy = float(d["x"]), float(d["y"])
            box = d.get("box") or self.get_parameter("box_model").value
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self._status(f"⚠️ grasp_request 파싱 실패: {e}"); self._result(False); return

        tx = float(self.get_parameter("grasp_x").value)
        ty = float(self.get_parameter("grasp_y").value)
        # ★ 특이점 회피: y-offset 강제
        if abs(ty) < Y_OFFSET_MIN:
            self._status(f"⚠️ y={ty:.2f} < {Y_OFFSET_MIN} → 클램프")
            ty = Y_OFFSET_MIN

        q = self._solve_ik(tx, ty)
        if q is None:
            self._status("⚠️ IK 수렴 실패"); self._result(False); return
        self._status(f"{op} IK 해 q={[round(float(v), 3) for v in q]} (target=({tx:.2f},{ty:.2f}))")

        # ★ 이 콜백은 이미 rclpy.spin(node)의 실행자 안에서 돌고 있으므로,
        # 여기서 spin_until_future_complete로 재진입(nested spin)하면 응답
        # 콜백이 실행자에게 전달되지 않고 유실/타임아웃되는 경우가 있었다.
        # (실제로는 delete_entity/spawn_entity 요청이 처리됐는데도 응답을 못
        # 받아 실패로 오판하는 버그의 원인이었음) → add_done_callback으로
        # 논블로킹 처리하도록 수정.
        self._teleport_async(op, wx, wy, box)

    def _solve_ik(self, x, y):
        """팔 로컬 타깃 (x,y)의 관절각을 구한다. 실패 시 None."""
        if self._robot is None:
            return [0.0, 0.0, 0.0] if self.sim_mode else None
        try:
            from nd1_m7_ik import numerical_ik
            return list(numerical_ik(self._robot, (x, y)))
        except Exception:
            return [0.0, 0.0, 0.0] if self.sim_mode else None

    def _init_arm(self):
        try:
            from nd1_m7_ik import RobotArm3DOF
            return RobotArm3DOF(links=self.links)
        except Exception as e:
            self.get_logger().warn(f"nd1_m7_ik 로드 실패(sim 전용 가능): {e}")
            return None

    def _teleport_async(self, op: str, x: float, y: float, box: str):
        """op=grasp → 박스 삭제 / op=place → (x,y)에 박스 재생성. 결과는 콜백에서 _result()."""
        if self.sim_mode:
            self._status(f"[sim] {op} {box} 텔레포트 가정 — 성공")
            self._result(True)
            return

        if op == "grasp":
            self._delete_box_async(box)
        else:
            self._spawn_box_async(box, x, y)

    def _delete_box_async(self, name: str):
        if not self._delete_cli.service_is_ready():
            self._status("⚠️ /delete_entity 서비스 없음"); self._result(False); return
        req = DeleteEntity.Request()
        req.name = name
        future = self._delete_cli.call_async(req)
        future.add_done_callback(self._on_delete_done)

    def _on_delete_done(self, future):
        try:
            res = future.result()
        except Exception as e:
            self._status(f"⚠️ delete_entity 예외: {e}"); self._result(False); return
        self._result(bool(res.success))

    def _spawn_box_async(self, name: str, x: float, y: float):
        if not self._spawn_cli.service_is_ready():
            self._status("⚠️ /spawn_entity 서비스 없음"); self._result(False); return
        sdf_path = self.get_parameter("box_sdf_path").value or self._default_sdf_path(name)
        try:
            with open(sdf_path, "r") as f:
                xml = f.read()
        except OSError as e:
            self._status(f"⚠️ box sdf 읽기 실패: {e}"); self._result(False); return

        req = SpawnEntity.Request()
        req.name = name
        req.xml = xml
        req.initial_pose.position.x = x
        req.initial_pose.position.y = y
        req.initial_pose.position.z = 0.1
        future = self._spawn_cli.call_async(req)
        future.add_done_callback(self._on_spawn_done)

    def _on_spawn_done(self, future):
        try:
            res = future.result()
        except Exception as e:
            self._status(f"⚠️ spawn_entity 예외: {e}"); self._result(False); return
        self._result(bool(res.success))

    def _default_sdf_path(self, box_name: str) -> str:
        return get_package_share_directory("nd1_capstone_tb3") + f"/models/{box_name}.sdf"

    def _result(self, ok: bool):
        self.pub_result.publish(Bool(data=ok))
        self._status(f"결과: {'성공' if ok else '실패'}")

    def _status(self, text):
        self.get_logger().info(text)
        self.pub_status.publish(String(data=f"[C] {text}"))


def main(args=None):
    rclpy.init(args=args)
    node = NodeCGrasp()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node(); rclpy.shutdown()


if __name__ == "__main__":
    main()
