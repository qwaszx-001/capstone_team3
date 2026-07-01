# Foxglove 시각화 가이드 — 헤드리스 Gazebo + Foxglove

> Gazebo GUI 없이(헤드리스, RTF 0.99) **로봇 위치·경로·맵·카메라·미션상태**를 Foxglove로 본다.
> 레이아웃 파일: `foxglove/nd1_capstone_layout.json`

## 0. 사전 (bridge 실행)
```bash
# 컨테이너 안:
source /opt/ros/humble/setup.bash
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765
```
Foxglove(데스크톱 앱 권장) → Open connection → **Foxglove WebSocket** → `ws://localhost:8765`
> 브라우저판은 mixed-content로 `ws://` 차단될 수 있음 → **데스크톱 앱** 사용.

## 1. 레이아웃 불러오기 (임포트)
Foxglove 앱 → 좌상단 **Layouts** 패널 → **Import from file** → `nd1_capstone_layout.json` 선택.
- 패널 4개가 한 번에 구성됨: 3D(좌), 카메라/상태/속도(우).
- 토픽이 자동 매칭 안 되면 각 패널 설정에서 토픽만 다시 고르면 됨(2·3절).

## 2. 패널 구성 (이 레이아웃이 보여주는 것)

| 패널 | 보는 것 | 핵심 토픽 |
|------|---------|-----------|
| **3D** | 맵 + 로봇 위치 + 라이다 + 경로 | `/map`, `/tf`, `/scan`, `/plan` |
| **Image** | 카메라 영상 | `/oakd/rgb/preview/image_raw` (※ standard 모델만) |
| **Raw Messages** | 미션 상태(FSM 로그) | `/robot_status` |
| **Plot** | 로봇 실제 이동량 | `/cmd_vel` linear.x / angular.z |

- **로봇 위치/경로/맵** = 3D 패널 하나로 다 봄. `followTf: base_link`라 로봇을 따라다님.
- **미션 진행** = Raw Messages의 `/robot_status` 에 `[FSM:NAVIGATING]…[DONE]` 가 그대로 흐름.
- **실제 움직이는지** = Plot의 `cmd_vel` 값이 0이 아니면 주행 중(정지 진단에 유용).

## 3. 수동 구성 (임포트가 안 되거나 버전이 다를 때 — 버전 무관 확실)

Foxglove 버전마다 JSON 키가 달라 임포트가 어긋나면, 빈 레이아웃에서 직접:

1. **3D 패널 추가** → 설정에서:
   - Follow → `base_link`
   - 토픽 켜기: `/map`(OccupancyGrid), `/scan`(LaserScan), `/plan`(Path), `/tf`
   - (선택) `/global_costmap/costmap`, `/local_costmap/costmap`
2. **Image 패널 추가** → Image topic = `/oakd/rgb/preview/image_raw`
   (※ **lite 모델엔 카메라 없음** → 이 패널은 standard 모델일 때만. 자세한 건 5절)
3. **Raw Messages 패널 추가** → Message path = `/robot_status.data`
4. **Plot 패널 추가** → 시리즈 추가:
   - `/cmd_vel.linear.x`
   - `/cmd_vel.angular.z`

## 4. 토픽 실제 이름 확인 (필수)
TurtleBot4 배포판/네임스페이스에 따라 이름이 다를 수 있음. **실측으로 확인 후 패널에 반영**:
```bash
ros2 topic list                       # 전체 토픽
ros2 topic list | grep -E "map|scan|plan|cmd_vel|odom|image|robot_status"
ros2 topic echo /robot_status --once   # 미션 상태 흐르는지
ros2 topic echo /scan --once           # 라이다 (lite 기본 제공)
```
- `/plan`이 없으면 Nav2가 경로를 아직 안 냄(목표 미수신) — 미션 시작 후 생김.
- `/cmd_vel`이 다른 이름이면(예: `/diffdrive_controller/cmd_vel`) Plot 경로 교정.

## 5. 카메라 주의 (사실)
- 지금 권장 기동은 **`model:=lite`** → **OAK-D 카메라 없음** → Image 패널은 빈 화면.
- 카메라 영상이 꼭 필요하면:
  - `model:=standard` 로 시뮬 기동(단, 카메라 렌더가 무거워 RTF↓ 가능 — GPU 필요)
  - 토픽 확인: `ros2 topic list | grep -i image` → 실제 이름으로 Image 패널 설정
  - 헤드리스에서도 카메라 센서는 동작하나, 렌더 부하가 커 RTF에 영향.
- **권장(의견)**: 캡스톤은 2D Nav2 기반이라 카메라 불필요 → **lite + 3D/상태/속도 패널**로 충분.

## 6. 3D 패널이 비어 보일 때 (트러블슈팅)
| 증상 | 원인 | 조치 |
|------|------|------|
| 맵 안 보임 | `/map` 미발행(SLAM 미기동) | SLAM 기동, `ros2 topic echo /map --once` |
| 로봇/축 안 보임 | TF 없음 | `ros2 run tf2_ros tf2_echo map base_link` 확인, Follow=base_link |
| 경로 안 보임 | 미션 전이라 `/plan` 없음 | 미션 시작 후 표시됨 |
| 전부 안 보임 | bridge 미연결 | `ws://localhost:8765` 재연결, `/foxglove_bridge` 노드 확인 |
| 좌표 이상 | Display frame 불일치 | 3D 패널 Frame을 `map`으로 |

## 7. 권장 워크플로 (의견)
1. 헤드리스 시뮬(RTF 0.99) + SLAM + Nav2 기동
2. `foxglove_bridge` 실행 → Foxglove 데스크톱 앱 연결
3. 이 레이아웃 임포트 → 3D에 맵/로봇/라이다 확인
4. 캡스톤 노드 + 미션 실행 → Raw Messages로 FSM 진행, 3D로 경로, Plot로 이동 확인
→ Gazebo GUI 없이도 위치·경로·맵·상태를 모두 시각화. (카메라만 standard 모델 한정)

## 주의 (기준)
- Foxglove 레이아웃 JSON은 **앱 버전에 따라 키가 달라** 임포트가 어긋날 수 있음 → 그땐 3절 수동 구성(확실).
- 토픽 이름은 **반드시 `ros2 topic list`로 실측 확인** 후 반영(배포판 편차).
- 실제 표시는 컨테이너의 bridge·시뮬에서만 확인 가능(본 레이아웃은 구조·토픽 매핑까지 제공).
