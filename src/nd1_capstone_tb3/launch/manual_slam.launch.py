#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  수동 주행 SLAM 매핑 — 자율 탐사(autonomous_slam.launch.py)는 건드리지 않고
#  별도로 유지. 이 launch는 teleop_keyboard만 안내하는 용도이며, 실제 조작은
#  키보드 입력이 필요하므로 별도 터미널에서 직접 실행해야 한다.
#
#  선행: hospital_world.launch.py + turtlebot3_cartographer cartographer.launch.py
#        (+ 필요시 nav2_bringup navigation_launch.py) 가 이미 떠 있어야 함.
#  실행:
#    ros2 run turtlebot3_teleop teleop_keyboard
#  (w/x: 전진/후진, a/d: 좌/우 회전, s: 정지 — 터미널 창에 포커스가 있어야 동작)
#
#  지도가 다 그려지면 저장:
#    ros2 run nav2_map_server map_saver_cli -f ~/capstone_tb3_hospital/maps/hospital_map
# ════════════════════════════════════════════════════════════════
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    teleop_node = Node(
        package='turtlebot3_teleop',
        executable='teleop_keyboard',
        name='teleop_keyboard',
        output='screen',
        prefix='xfce4-terminal --disable-server -x',
    )
    return LaunchDescription([teleop_node])
