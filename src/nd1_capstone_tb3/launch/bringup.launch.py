#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  ND1 캡스톤(TurtleBot3 이식) — 4노드 일괄 기동 launch (+ 선택적 SLAM/Nav2)
#
#  사전 준비: export TURTLEBOT3_MODEL=burger  (또는 waffle/waffle_pi)
#
#  사용 (시뮬 단독, B/C/Gazebo 불필요):
#     ros2 launch nd1_capstone_tb3 bringup.launch.py sim_mode:=true
#
#  사용 (실연동 통합 — Gazebo는 터미널1에서 먼저 기동):
#     # 터미널1: ros2 launch turtlebot3_gazebo empty_world.launch.py
#     # 터미널2(이 런처가 SLAM+Nav2+4노드를 한 번에):
#     ros2 launch nd1_capstone_tb3 bringup.launch.py \
#         sim_mode:=false slam:=true nav2:=true
#
#  사전 맵(turtlebot3_world + 기존 map.yaml)으로 AMCL 로컬라이제이션을 쓰려면
#  nav2_bringup/localization_launch.py를 별도로 추가해야 한다(이 launch는 미포함).
#  기본 권장 경로는 slam:=true 로 사전 맵 없이 즉석 SLAM을 쓰는 것.
#
#  ⚠️ 원본(TurtleBot4) 킷과 달리 도킹(undock/dock) 관련 인자·노드가 없다 —
#     TB3에는 Create3 도킹 스테이션이 없기 때문에 FSM에서 해당 state를 제거했다.
# ════════════════════════════════════════════════════════════════
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory

TURTLEBOT3_MODEL = os.environ.get("TURTLEBOT3_MODEL", "burger")


def generate_launch_description():
    sim = LaunchConfiguration("sim_mode")
    use_slam = LaunchConfiguration("slam")
    use_nav2 = LaunchConfiguration("nav2")

    params = [{"sim_mode": sim}]
    cartographer_share = FindPackageShare("turtlebot3_cartographer")
    nav2_bringup_share = FindPackageShare("nav2_bringup")
    default_nav2_params = os.path.join(
        get_package_share_directory("turtlebot3_navigation2"),
        "param", "humble", f"{TURTLEBOT3_MODEL}.yaml")

    # ── 인자 선언 ────────────────────────────────────────────────
    args = [
        DeclareLaunchArgument("sim_mode", default_value="true",
                              description="true=B/C 시뮬, false=실연동"),
        DeclareLaunchArgument("slam", default_value="false",
                              description="true=cartographer SLAM 기동(map→odom 공급, 사전맵 불필요)"),
        DeclareLaunchArgument("nav2", default_value="false",
                              description="true=Nav2 플래너/컨트롤러 기동(navigate_to_pose 액션 서버)"),
        DeclareLaunchArgument("nav2_params_file", default_value=default_nav2_params,
                              description="Nav2 파라미터 yaml (TURTLEBOT3_MODEL 기준 기본값)"),
        DeclareLaunchArgument("box_model", default_value="box1",
                              description="Node C 텔레포트 대상 박스 모델 이름"),
        DeclareLaunchArgument("box_sdf_path", default_value="",
                              description="배치(place) 재생성용 SDF 절대경로(비우면 패키지 share의 box1.sdf)"),
    ]

    # ── map→odom 공급원: SLAM(cartographer) ───────────────────────
    includes = [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution(
                [cartographer_share, "launch", "cartographer.launch.py"])),
            condition=IfCondition(use_slam),
            launch_arguments={"use_sim_time": sim, "use_rviz": "false"}.items(),
        ),
        # Nav2: 경로계획/제어/코스트맵만 (localization 미포함 — SLAM/AMCL이 map→odom 공급)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution(
                [nav2_bringup_share, "launch", "navigation_launch.py"])),
            condition=IfCondition(use_nav2),
            launch_arguments={
                "use_sim_time": sim,
                "params_file": LaunchConfiguration("nav2_params_file"),
                "autostart": "true",
            }.items(),
        ),
    ]

    # ── 캡스톤 4노드 (항상 기동) ─────────────────────────────────
    nodes = [
        Node(package="nd1_capstone_tb3", executable="node_a_llm", name="node_a_llm",
             output="screen"),
        Node(package="nd1_capstone_tb3", executable="node_b_nav", name="node_b_nav",
             output="screen", parameters=params),
        Node(package="nd1_capstone_tb3", executable="node_c_grasp", name="node_c_grasp",
             output="screen", parameters=[{
                 "sim_mode": sim,
                 "box_model": LaunchConfiguration("box_model"),
                 "box_sdf_path": LaunchConfiguration("box_sdf_path"),
                 # classic Gazebo factory 플러그인이 부하 상황에서 응답을 늦게
                 # 보내는 경우가 있어 기본 5.0s보다 넉넉하게 잡는다.
                 "server_timeout": 20.0,
             }]),
        Node(package="nd1_capstone_tb3", executable="coordinator_fsm", name="coordinator_fsm",
             output="screen", parameters=[{"sim_mode": sim}]),
    ]

    return LaunchDescription(args + includes + nodes)
