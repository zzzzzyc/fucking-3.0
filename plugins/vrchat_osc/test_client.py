#!/usr/bin/env python3
"""
测试客户端，用于模拟VRChat发送OSC消息
"""

import argparse
import time
import random
from pythonosc import udp_client

def main():
    parser = argparse.ArgumentParser(description="测试客户端，模拟VRChat发送OSC消息")
    parser.add_argument("--ip", default="127.0.0.1", help="OSC服务器IP地址")
    parser.add_argument("--port", type=int, default=9001, help="OSC服务器端口")
    parser.add_argument("--param", default="/avatar/parameters/pcs/contact/enterPass", help="OSC参数名称")
    parser.add_argument("--mode", default="ramp", choices=["ramp", "pulse", "random"], help="测试模式：ramp(渐变)、pulse(脉冲)、random(随机)")
    parser.add_argument("--duration", type=float, default=10.0, help="测试持续时间（秒）")
    
    args = parser.parse_args()
    
    # 创建OSC客户端
    client = udp_client.SimpleUDPClient(args.ip, args.port)
    
    print(f"正在向 {args.ip}:{args.port} 发送OSC消息，参数：{args.param}")
    print(f"测试模式：{args.mode}，持续时间：{args.duration}秒")
    print("按Ctrl+C停止测试")
    
    start_time = time.time()
    
    try:
        if args.mode == "ramp":
            # 渐变模式：从0到1，然后从1到0
            while time.time() - start_time < args.duration:
                elapsed = time.time() - start_time
                cycle_position = (elapsed % 5.0) / 5.0  # 5秒一个周期
                
                if cycle_position < 0.5:
                    # 从0到1
                    value = cycle_position * 2.0
                else:
                    # 从1到0
                    value = 2.0 - cycle_position * 2.0
                
                client.send_message(args.param, value)
                print(f"发送：{args.param} = {value:.2f}")
                time.sleep(0.1)
        
        elif args.mode == "pulse":
            # 脉冲模式：定期发送1，其余时间为0
            while time.time() - start_time < args.duration:
                elapsed = time.time() - start_time
                cycle_position = elapsed % 2.0  # 2秒一个周期
                
                if cycle_position < 0.2:  # 每个周期的前0.2秒发送1
                    value = 1.0
                else:
                    value = 0.0
                
                client.send_message(args.param, value)
                print(f"发送：{args.param} = {value:.2f}")
                time.sleep(0.1)
        
        elif args.mode == "random":
            # 随机模式：发送随机值
            while time.time() - start_time < args.duration:
                value = random.random()  # 0到1之间的随机值
                
                client.send_message(args.param, value)
                print(f"发送：{args.param} = {value:.2f}")
                time.sleep(0.2)
    
    except KeyboardInterrupt:
        print("\n测试已停止")
    
    # 测试结束后发送0值
    client.send_message(args.param, 0.0)
    print("测试结束，已发送值0")

if __name__ == "__main__":
    main() 