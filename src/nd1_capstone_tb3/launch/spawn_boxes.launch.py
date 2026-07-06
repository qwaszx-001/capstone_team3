#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  백신 4종 스폰 launch — 약국(pharmacy) 좌표 주변에 4개를 나란히 배치.
#  이후 배달 시 node_c_grasp가 해당 이름을 delete(픽업)했다가 병실 좌표에
#  다시 spawn(배달)하는 방식으로 텔레포트한다.
#  사용:
#    ros2 launch nd1_capstone_tb3 spawn_boxes.launch.py
# ════════════════════════════════════════════════════════════════
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

# 약국(pharmacy) 좌표 — config/rooms.yaml 과 동일한 값
PHARMACY_X = -10.37
PHARMACY_Y = -26.25

# 로봇이 약국 좌표(PHARMACY_X, PHARMACY_Y)로 정확히 이동해 정차하므로, 그 지점에
# 바로 박스를 두면 로봇 몸체와 충돌/끼임이 발생한다. y방향으로 0.6m 떨어뜨려
# 로봇 발자국(반경 ~0.1m)+목표 허용오차(0.25m)에 안 걸리게 한다.
VACCINES = [
    ("vaccine_a", PHARMACY_X - 0.225, PHARMACY_Y + 0.6),
    ("vaccine_b", PHARMACY_X - 0.075, PHARMACY_Y + 0.6),
    ("vaccine_ab", PHARMACY_X + 0.075, PHARMACY_Y + 0.6),
    ("vaccine_o", PHARMACY_X + 0.225, PHARMACY_Y + 0.6),
]


def generate_launch_description():
    pkg = get_package_share_directory("nd1_capstone_tb3")

    spawn_nodes = [
        Node(
            package="gazebo_ros", executable="spawn_entity.py", output="screen",
            arguments=["-entity", name, "-file", os.path.join(pkg, "models", f"{name}.sdf"),
                       "-x", str(x), "-y", str(y), "-z", "0.1"])
        for name, x, y in VACCINES
    ]

    return LaunchDescription(spawn_nodes)
