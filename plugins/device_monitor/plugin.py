"""
设备监控插件
提供设备状态监控功能，包括设备连接状态检查、自动重连和电池电量监控
"""

import asyncio
import logging
import os
import yaml
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
    global ws_server, device
    ws_server = server
    # 获取设备引用
    if hasattr(server, 'device'):
        device = server.device

async def load_config() -> None:
    """加载插件配置"""
    global config
    
    # 配置文件路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_config_path = os.path.join(base_dir, "config.yaml")
    
    # 尝试加载YAML配置
    if os.path.exists(yaml_config_path):
        try:
            with open(yaml_config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info("已从YAML文件加载配置")
            return
        except Exception as e:
            logger.error(f"加载YAML配置失败: {str(e)}")
    
    # 如果配置加载失败，使用默认配置并创建配置文件
    config = DEFAULT_CONFIG.copy()
    
    # 创建YAML配置文件
    try:
        with open(yaml_config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("已创建默认YAML配置文件")
    except Exception as e:
        logger.error(f"创建YAML配置文件失败: {str(e)}")

def setup() -> None:
    """插件初始化"""
    global config, monitor_task
    
    # 加载配置
    asyncio.ensure_future(load_config())
    
    # 启动监控任务
    monitor_task = asyncio.create_task(check_device_status())
    
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
    global config
    
    try:
        if data.get("type") != "plugin_device_monitor":
            return {"status": "ignored"}
            
        # 确保配置已加载
        if config is None:
            return {"status": "error", "message": "配置尚未加载完成"}
            
        action = data.get("action")
        if action == "get_status":
            # 获取当前状态
            if device and device.is_connected:
                # 确保状态已更新
                await device.update_battery()
                battery_level = device.state.battery
                return {
                    "status": "success",
                    "data": {
                        "connected": True,
                        "battery": battery_level,
                        "address": device.device_address
                    }
                }
            else:
                return {
                    "status": "success",
                    "data": {
                        "connected": False,
                        "battery": 0,
                        "address": device.device_address if device else None
                    }
                }
        else:
            return {"status": "error", "message": f"未知的操作: {action}"}
            
    except Exception as e:
        logger.error(f"处理消息时出错: {e}")
        return {"status": "error", "message": str(e)}

async def check_device_status() -> None:
    """定期检查设备状态"""
    global device, config
    
    # 等待配置加载完成
    while config is None:
        await asyncio.sleep(0.1)
    
    while True:
        try:
            if device and device.is_connected:
                # 检查电池电量
                await device.update_battery()
                battery_level = device.state.battery
                
                # 如果电池电量低于警告阈值，发送警告
                if battery_level <= config["monitor"]["battery_warning"]:
                    await broadcast_status(
                        f"电池电量低: {battery_level}%",
                        "warning"
                    )
                
            elif device:
                await handle_disconnection()
                
            await asyncio.sleep(config["monitor"]["check_interval"])
            
        except Exception as e:
            logger.error(f"检查设备状态时出错: {e}")
            await asyncio.sleep(config["monitor"]["check_interval"])

async def handle_disconnection() -> None:
    """处理设备断开连接"""
    global device, config
    
    # 确保配置已加载
    if config is None:
        logger.warning("配置尚未加载，使用默认值")
        config = DEFAULT_CONFIG.copy()
    
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