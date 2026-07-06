#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  병원 월드(AWS RoboMaker hospital_world) + TurtleBot3 스폰
#
#  turtlebot3_gazebo의 empty_world.launch.py와 동일한 패턴이지만,
#  world 파일만 aws_robomaker_hospital_world 패키지의 hospital.world로 교체.
#
#  사전 준비: export TURTLEBOT3_MODEL=burger  (또는 waffle/waffle_pi)
#  실행:
#    ros2 launch nd1_capstone_tb3 hospital_world.launch.py
#    ros2 launch nd1_capstone_tb3 hospital_world.launch.py x_pose:=0.0 y_pose:=0.0
#
#  ⚠️ aws_robomaker_hospital_world 패키지는 사람·침상·의료장비 등 44종 모델을
#     `fuel_models/`에 별도 보관하는데, 패키지 export(gazebo_model_path)가
#     `models/`만 잡아줘서 fuel_models는 GAZEBO_MODEL_PATH에 안 잡힌다.
#     그대로 두면 그 44종이 전부 "Unable to find uri" 로 조용히 빠진다 →
#     아래에서 fuel_models를 GAZEBO_MODEL_PATH에 직접 추가해준다.
#  ⚠️ 기본 스폰 좌표(3.75, 2.75)는 world 파일의 가구 좌표를 분석해 안내데스크·
#     의자 클러스터에서 가장 멀리 떨어진 지점으로 고른 추정치다. 그래도 로봇이
#     끼거나 계속 돌면 x_pose/y_pose를 다른 값으로 바꿔 재시도할 것.
# ════════════════════════════════════════════════════════════════
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    tb3_gazebo_launch_dir = os.path.join(
        get_package_share_directory('turtlebot3_gazebo'), 'launch')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')
    hospital_share = get_package_share_directory('aws_robomaker_hospital_world')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    x_pose = LaunchConfiguration('x_pose', default='3.75')
    y_pose = LaunchConfiguration('y_pose', default='2.75')

    world = os.path.join(hospital_share, 'worlds', 'hospital.world')

    # fuel_models(사람·침상·의료장비 등)를 Gazebo가 찾도록 모델 경로에 추가
    set_model_path_cmd = SetEnvironmentVariable(
        'GAZEBO_MODEL_PATH',
        os.path.join(hospital_share, 'fuel_models') + ':' +
        os.path.join(hospital_share, 'models') + ':' +
        os.environ.get('GAZEBO_MODEL_PATH', '')
    )

    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': world}.items()
    )

    # gazebo_ros의 gzclient.launch.py는 --gui-client-plugin=libgazebo_ros_eol_gui.so
    # (EOL 배너 오버레이)를 붙이는데, 이 플러그인이 카메라 초기화 타이밍과 충돌해
    # "Camera px != 0" assertion으로 gzclient가 즉시 죽는 경우가 있다. 플러그인 없이
    # 순정 gzclient만 실행해 회피.
    gzclient_cmd = ExecuteProcess(cmd=['gzclient'], output='screen')

    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_gazebo_launch_dir, 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items()
    )

    spawn_turtlebot_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_gazebo_launch_dir, 'spawn_turtlebot3.launch.py')
        ),
        launch_arguments={
            'x_pose': x_pose,
            'y_pose': y_pose
        }.items()
    )

    ld = LaunchDescription()
    ld.add_action(set_model_path_cmd)
    ld.add_action(gzserver_cmd)
    ld.add_action(gzclient_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(spawn_turtlebot_cmd)

    return ld
