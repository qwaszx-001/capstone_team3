#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════
#  Node B — 내비게이션 노드 (TurtleBot3 이식)
#  역할: /nav_request → Nav2 NavigateToPose
#
#  원본(TurtleBot4) 대비 변경점: TB3에는 Create3 도킹 스테이션이 없으므로
#  undock/dock 관련 코드 전체를 제거했다 (irobot_create_msgs 의존 삭제).
#
#  토픽/액션 계약(고정):
#    In  /nav_request {x,y,yaw}
#    Out /nav_result(Bool) / /robot_status
#    Action: navigate_to_pose (TB3 Nav2도 동일 액션명)
# ════════════════════════════════════════════════════════════════
import json
import math

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String, Bool
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


class NodeBNav(Node):
    def __init__(self):
        super().__init__("node_b_nav")
        self.declare_parameter("sim_mode", True)
        self.declare_parameter("server_timeout", 5.0)
        self.sim_mode = self.get_parameter("sim_mode").value
        self.timeout = self.get_parameter("server_timeout").value

        self.pub_nav_res = self.create_publisher(Bool, "/nav_result", 10)
        self.pub_status = self.create_publisher(String, "/robot_status", 10)
        self.create_subscription(String, "/nav_request", self._on_nav, 10)

        self._nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self._active = False
        self._status(f"Node B 시작 (sim_mode={self.sim_mode})")

    def _on_nav(self, msg: String):
        """/nav_request {x,y,yaw} → Nav2 목표 전송 → 결과를 _nav_result(bool) 로."""
        if self._active:
            return
        try:
            d = json.loads(msg.data)
            x, y, yaw = float(d["x"]), float(d["y"]), float(d.get("yaw", 0.0))
        except (json.JSONDecodeError, KeyError, ValueError):
            self._nav_result(False); return

        self._active = True
        if self.sim_mode:
            t = self.create_timer(2.0, lambda: (t.cancel(), self._nav_result(True)))
            return

        if not self._nav_client.wait_for_server(timeout_sec=self.timeout):
            self._status("⚠️ Nav2 액션 서버 없음"); self._nav_result(False); return
        goal = NavigateToPose.Goal()
        goal.pose = self._pose(x, y, yaw)
        self._nav_client.send_goal_async(goal).add_done_callback(self._nav_goal_cb)

    def _nav_goal_cb(self, future):
        h = future.result()
        if not h.accepted:
            self._status("⚠️ Nav2 goal 거부"); self._nav_result(False); return
        h.get_result_async().add_done_callback(lambda f: self._nav_result(f.result().status == 4))

    def _nav_result(self, ok):
        self._active = False
        self.pub_nav_res.publish(Bool(data=ok))
        self._status(f"이동 결과: {'성공' if ok else '실패'}")

    def _pose(self, x, y, yaw):
        p = PoseStamped()
        p.header.frame_id = "map"
        p.header.stamp = self.get_clock().now().to_msg()
        p.pose.position.x = x; p.pose.position.y = y
        p.pose.orientation.z = math.sin(yaw / 2.0)
        p.pose.orientation.w = math.cos(yaw / 2.0)
        return p

    def _status(self, text):
        self.get_logger().info(text)
        self.pub_status.publish(String(data=f"[B] {text}"))


def main(args=None):
    rclpy.init(args=args)
    node = NodeBNav()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node(); rclpy.shutdown()


if __name__ == "__main__":
    main()
