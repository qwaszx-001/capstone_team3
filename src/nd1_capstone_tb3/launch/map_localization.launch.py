#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  좌표 기반 자율주행 — SLAM으로 만든 고정 지도(map_localization) 위에서
#  AMCL로 위치추정만 하고, Nav2로 좌표(NavigateToPose) 목표를 실행한다.
#  Cartographer(SLAM)는 더 이상 쓰지 않는다 — 지도는 이미 완성되어 고정.
#
#  선행: hospital_world.launch.py 로 병원 월드 + TurtleBot3가 이미 떠 있어야 함.
#  실행:
#    ros2 launch nd1_capstone_tb3 map_localization.launch.py
#
#  RViz에서 "2D Pose Estimate"로 초기 위치를 지도 위 실제 로봇 위치와 맞춰준
#  뒤에 "2D Goal Pose"나 좌표 기반 액션으로 주행 테스트를 한다.
# ════════════════════════════════════════════════════════════════
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    nav2_bringup_share = get_package_share_directory('nav2_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    map_yaml_file = LaunchConfiguration(
        'map', default=os.path.expanduser('~/capstone_tb3_hospital/maps/hospital_map.yaml'))
    params_file = os.path.expanduser('~/capstone_tb3_hospital/config/burger_hospital.yaml')

    localization_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'localization_launch.py')
        ),
        launch_arguments={
            'map': map_yaml_file,
            'use_sim_time': use_sim_time,
            'params_file': params_file,
            'autostart': 'true',
        }.items()
    )

    navigation_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': params_file,
            'autostart': 'true',
        }.items()
    )

    rviz_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'rviz_launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items()
    )

    ld = LaunchDescription()
    ld.add_action(localization_cmd)
    ld.add_action(navigation_cmd)
    ld.add_action(rviz_cmd)
    return ld
