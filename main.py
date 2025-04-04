#!/usr/bin/env python3
"""
DG-LAB 设备控制服务

提供核心蓝牙功能和WebSocket接口，允许插件扩展功能
"""

import asyncio
import logging
import argparse
import os
import sys
import signal
import platform
from typing import Optional

from core.dglab_device import DGLabDevice
from server.ws_server import DGLabWebSocketServer
from plugins.plugin_loader import PluginLoader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("dglab")


async def main(args):
    """
    主函数
    
    Args:
        args: 命令行参数
    """
    # 创建插件目录（如果不存在）
    if not os.path.exists(args.plugins_dir):
        os.makedirs(args.plugins_dir)
        logger.info(f"创建插件目录: {args.plugins_dir}")
    
    device = None
    server = None
    
    try:
        # 如果提供了设备地址，直接连接；否则扫描连接
        if args.device_address:
            logger.info(f"使用提供的设备地址: {args.device_address}")
            device = DGLabDevice(args.device_address)
            await device.connect()
        elif not args.no_scan:
            logger.info("扫描并连接DG-LAB设备...")
            device = await DGLabDevice.scan_and_connect()
        
        # 创建WebSocket服务器
        server = DGLabWebSocketServer(
            host=args.host,
            port=args.port,
            device=device
        )
        
        # 启动服务器
        await server.start()
        
        # 加载插件
        if not args.no_plugins:
            plugin_loader = PluginLoader(server, args.plugins_dir)
            
            # 创建示例插件（如果指定）
            if args.create_example_plugin:
                logger.info("创建示例插件...")
                plugin_loader.create_plugin_template("example")
            
            # 加载所有插件
            results = plugin_loader.load_all_plugins()
            
            # 输出加载结果
            for name, success in results.items():
                if success:
                    logger.info(f"插件 {name} 加载成功")
                else:
                    logger.warning(f"插件 {name} 加载失败")
            
            # 添加以下日志输出
            logger.debug(f"插件加载顺序: {', '.join(results.keys())}")
        
        # 等待服务器运行直到被中断
        logger.info(f"DG-LAB 设备控制服务已启动 - 监听 {args.host}:{args.port}")
        
        # 设置信号处理（仅在非Windows平台）
        if platform.system() != "Windows":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(server)))
            logger.info("已设置信号处理")
        else:
            logger.info("在Windows平台上运行，跳过信号处理设置")
        
        # 保持运行直到手动停止
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("程序被取消")
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行错误: {str(e)}")
    finally:
        # 关闭服务器（如果已创建）
        if server:
            await server.stop()


async def shutdown(server: Optional[DGLabWebSocketServer]) -> None:
    """
    优雅关闭服务器
    
    Args:
        server: WebSocket服务器实例
    """
    if server:
        logger.info("正在关闭服务器...")
        await server.stop()
    
    # 停止事件循环
    loop = asyncio.get_running_loop()
    loop.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DG-LAB 设备控制服务")
    
    # 添加命令行参数
    parser.add_argument("--host", default="127.0.0.1", help="服务器监听地址")
    parser.add_argument("--port", type=int, default=8080, help="服务器监听端口")
    parser.add_argument("--device-address", help="设备蓝牙地址（不提供则自动扫描）")
    parser.add_argument("--no-scan", action="store_true", help="不扫描设备（仅在与--device-address一起使用时有意义）")
    parser.add_argument("--plugins-dir", default="plugins", help="插件目录")
    parser.add_argument("--no-plugins", action="store_true", help="不加载插件")
    parser.add_argument("--create-example-plugin", action="store_true", help="创建示例插件")
    parser.add_argument("--debug", action="store_true", help="启用调试日志")
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        logger.info("程序被用户中断") 