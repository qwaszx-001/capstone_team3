#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  자율주행 SLAM 매핑 — Cartographer(SLAM+RViz) + Nav2 + explore_lite(프론티어 탐사)
#
#  선행: 터미널1에서 hospital_world.launch.py 로 병원 월드 + TurtleBot3가 이미 떠 있어야 함.
#  사전 준비: export TURTLEBOT3_MODEL=burger
#  실행:
#    ros2 launch nd1_capstone_tb3 autonomous_slam.launch.py
#
#  키보드 주행 없이 explore_lite가 미탐사 영역(프론티어)을 자동으로 찾아
#  Nav2 navigate_to_pose 액션으로 로봇을 보내고, Cartographer가 그 경로를
#  돌아다니는 동안 지도를 채운다. RViz는 cartographer.launch.py가 자동으로 띄운다.
#
#  ⚠️ explore_lite는 시작하자마자 첫 /map 스냅샷에 프론티어가 없으면 즉시
#     "stopping"으로 완전히 멈추고 재시도하지 않는다(/explore/resume 토픽으로만
#     재개 가능). 게다가 cartographer 점유격자는 처음 몇 십 초간 확률값이
#     0/100으로 완전히 수렴하지 않아 "정확히 FREE_SPACE(0)"인 셀이 로봇 근처에
#     하나도 없을 수 있다 → 10초 지연으로도 실패 가능. 그래서 explore_lite
#     최초 시작(10초 지연)에 더해, /explore/resume 을 6회(10초 간격) 추가로
#     재전송해 지도가 무르익을 때까지 재시도하도록 한다.
# ════════════════════════════════════════════════════════════════
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

TURTLEBOT3_MODEL = os.environ.get('TURTLEBOT3_MODEL', 'burger')


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    cartographer_share = get_package_share_directory('turtlebot3_cartographer')
    nav2_bringup_share = get_package_share_directory('nav2_bringup')
    explore_share = get_package_share_directory('explore_lite')

    # 실제 사용 파라미터: 원본 burger.yaml이 아니라 병원 월드용으로
    # inflation_radius/속도를 조정한 workspace config/burger_hospital.yaml.
    default_nav2_params = os.path.expanduser(
        '~/capstone_tb3_hospital/config/burger_hospital.yaml')

    # SLAM: map -> odom 발행 + RViz(카토그래퍼 뷰) 자동 기동
    cartographer_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(cartographer_share, 'launch', 'cartographer.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items()
    )

    # Nav2: 경로계획/제어/코스트맵 (localization 미포함 — SLAM이 map→odom 공급)
    nav2_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': default_nav2_params,
            'autostart': 'true',
        }.items()
    )

    # 프론티어 자동 탐사: /map(occupancy grid)에서 미탐사 경계를 찾아 Nav2로 목표 전송
    # Cartographer/Nav2 코스트맵이 초기 지도를 쌓을 시간을 벌기 위해 10초 지연 시작
    explore_cmd = TimerAction(
        period=10.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(explore_share, 'launch', 'explore.launch.py')
            ),
            launch_arguments={'use_sim_time': use_sim_time}.items()
        )]
    )

    # explore_lite가 첫 시도에 "No frontiers found"로 완전히 멈춰버리는 경우를 대비한
    # 재시도 킥: 20초부터 10초 간격으로 6회 /explore/resume 발행
    explore_retry_kick = TimerAction(
        period=20.0,
        actions=[ExecuteProcess(
            cmd=['bash', '-c',
                 'for i in $(seq 1 6); do '
                 'ros2 topic pub --once /explore/resume std_msgs/msg/Bool "{data: true}"; '
                 'sleep 10; done'],
            output='screen'
        )]
    )

    ld = LaunchDescription()
    ld.add_action(cartographer_cmd)
    ld.add_action(nav2_cmd)
    ld.add_action(explore_cmd)
    ld.add_action(explore_retry_kick)
    return ld
