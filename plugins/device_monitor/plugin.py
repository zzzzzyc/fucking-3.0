"""
设备监控插件
提供设备状态监控功能，包括设备连接状态检查、自动重连和电池电量监控
"""

import asyncio
import logging
from typing import Dict, Any
from bleak import BleakClient

# 设置日志
logger = logging.getLogger(__name__)

# 全局变量
ws_server = None
device = None
config = None
monitor_task = None

# 默认配置
DEFAULT_CONFIG = {
    "monitor": {
        "check_interval": 30,  # 状态检查间隔（秒）
        "battery_warning": 20,  # 电池电量警告阈值（百分比）
        "auto_reconnect": True,  # 是否启用自动重连
        "reconnect_interval": 5,  # 重连尝试间隔（秒）
        "max_reconnect_attempts": 3  # 最大重连尝试次数
    }
}

def set_ws_server(server):
    """设置WebSocket服务器引用"""
    global ws_server
    ws_server = server

def setup() -> None:
    """插件初始化"""
    global config
    config = DEFAULT_CONFIG
    logger.info("设备监控插件已初始化")

async def handle_message(device, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理WebSocket消息
    
    Args:
        device: DGLabDevice实例
        data: 消息数据
        
    Returns:
        Dict[str, Any]: 处理结果
    """
    try:
        if data.get("type") != "plugin_device_monitor":
            return {"status": "ignored"}
            
        action = data.get("action")
        if action == "get_status":
            # 获取当前状态
            if device and device.client:
                battery = await device.client.read_gatt_char(device.CHAR_BATTERY)
                battery_level = battery[0]
                return {
                    "status": "success",
                    "data": {
                        "connected": True,
                        "battery": battery_level,
                        "address": device.address
                    }
                }
            else:
                return {
                    "status": "success",
                    "data": {
                        "connected": False,
                        "battery": 0,
                        "address": None
                    }
                }
        else:
            return {"status": "error", "message": f"未知的操作: {action}"}
            
    except Exception as e:
        logger.error(f"处理消息时出错: {e}")
        return {"status": "error", "message": str(e)}

async def check_device_status() -> None:
    """定期检查设备状态"""
    global device
    
    while True:
        try:
            if device and device.client:
                # 检查电池电量
                battery = await device.client.read_gatt_char(device.CHAR_BATTERY)
                battery_level = battery[0]
                
                # 如果电池电量低于警告阈值，发送警告
                if battery_level <= config["monitor"]["battery_warning"]:
                    await broadcast_status(
                        f"电池电量低: {battery_level}%",
                        "warning"
                    )
                
                # 检查连接状态
                if not device.client.is_connected:
                    await handle_disconnection()
                    
            await asyncio.sleep(config["monitor"]["check_interval"])
            
        except Exception as e:
            logger.error(f"检查设备状态时出错: {e}")
            await asyncio.sleep(config["monitor"]["check_interval"])

async def handle_disconnection() -> None:
    """处理设备断开连接"""
    global device
    
    if not config["monitor"]["auto_reconnect"]:
        await broadcast_status("设备已断开连接", "error")
        return
        
    attempts = 0
    while attempts < config["monitor"]["max_reconnect_attempts"]:
        try:
            await broadcast_status(f"尝试重新连接设备 (第{attempts + 1}次)", "info")
            await device.connect()
            await broadcast_status("设备已重新连接", "success")
            return
        except Exception as e:
            logger.error(f"重连失败: {e}")
            attempts += 1
            if attempts < config["monitor"]["max_reconnect_attempts"]:
                await asyncio.sleep(config["monitor"]["reconnect_interval"])
                
    await broadcast_status("重连失败，已达到最大尝试次数", "error")

async def broadcast_status(message: str, level: str = "info") -> None:
    """广播状态消息"""
    if ws_server:
        await ws_server.broadcast({
            "type": "plugin_device_monitor",
            "message": message,
            "level": level
        })

def cleanup() -> None:
    """插件清理"""
    global monitor_task
    if monitor_task:
        monitor_task.cancel()
    logger.info("设备监控插件已清理") 