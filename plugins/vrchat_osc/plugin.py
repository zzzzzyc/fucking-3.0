"""
VRChat OSC 插件
监听VRChat发送的OSC消息并控制DG-LAB设备
"""

import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import socket
import time
import fnmatch
import re

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

# 添加yaml支持
import yaml

# 设置日志
logger = logging.getLogger(__name__)

# 全局变量
osc_server = None
ws_server = None
device = None
server_task = None
running = False
config = None

# 默认配置
DEFAULT_CONFIG = {
    "osc": {
        "listen_host": "127.0.0.1",
        "listen_port": 9001
    },
    "channel_a": {
        "avatar_params": [
            "/avatar/parameters/pcs/contact/enterPass"
        ],
        "mode": "distance",
        "strength_limit": 100,
        "trigger_range": {
            "bottom": 0.0,
            "top": 1.0
        }
    },
    "channel_b": {
        "avatar_params": [
            "/avatar/parameters/pcs/contact/enterPass"
        ],
        "mode": "distance",
        "strength_limit": 100,
        "trigger_range": {
            "bottom": 0.0,
            "top": 1.0
        }
    },
    "wave_presets": {
        "default_channel_a": "Pulse",
        "default_channel_b": "Pulse",
        "distance_mode": "Wave",
        "shock_mode": "Pulse"
    }
}

# 记录上次的强度值，用于平滑过渡
last_strength = {"A": 0, "B": 0}

# 添加波形缓存变量，避免频繁切换相同波形
wave_cache = {
    "A": None,  # 通道A当前波形
    "B": None,  # 通道B当前波形
    "A_last_change": 0,  # 通道A上次波形变更时间
    "B_last_change": 0,  # 通道B上次波形变更时间
}

# 波形更新最小间隔（秒），避免频繁切换
WAVE_UPDATE_INTERVAL = 1.0

def is_port_in_use(host, port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind((host, port))
            return False
        except socket.error:
            return True

async def start_osc_server() -> None:
    """启动OSC服务器以监听VRChat消息"""
    global running, dispatcher
    
    # 等待配置加载完成
    while not config:
        await asyncio.sleep(0.1)
    
    try:
        # 检查端口是否被占用
        host = config["osc"]["listen_host"]
        port = config["osc"]["listen_port"]
        
        if is_port_in_use(host, port):
            logger.error(f"端口 {port} 已被占用，无法启动OSC服务器")
            return
        
        # 创建OSC分发器
        dispatcher = Dispatcher()
        
        # 注册通道A的参数处理
        register_osc_handlers(config["channel_a"]["avatar_params"], handle_channel_a)
        
        # 注册通道B的参数处理
        register_osc_handlers(config["channel_b"]["avatar_params"], handle_channel_b)
        
        # 创建OSC服务器
        loop = asyncio.get_running_loop()
        server = AsyncIOOSCUDPServer((host, port), dispatcher, loop)
        transport, protocol = await server.create_serve_endpoint()
        
        # 标记为运行中
        running = True
        
        logger.info(f"OSC服务器已启动，监听 {host}:{port}")
        
        # 等待直到服务被停止
        while running:
            await asyncio.sleep(1)
        
        # 关闭服务器
        transport.close()
        logger.info("OSC服务器已关闭")
        
    except Exception as e:
        logger.error(f"OSC服务器启动失败: {str(e)}")
        running = False

def register_osc_handlers(patterns: List[str], handler: Callable) -> None:
    """
    注册OSC消息处理器，支持通配符
    
    Args:
        patterns: OSC地址模式列表，支持通配符
        handler: 处理函数
    """
    for pattern in patterns:
        # 检查是否包含通配符
        if '*' in pattern:
            # 将OSC通配符模式转换为正则表达式
            regex_pattern = '^' + re.escape(pattern).replace('\\*', '.*') + '$'
            # 添加正则匹配处理器
            dispatcher.map_all(lambda address, *args: re.match(regex_pattern, address), handler)
            logger.info(f"注册通配符OSC参数: {pattern}")
        else:
            # 普通精确匹配
            dispatcher.map(pattern, handler)
            logger.info(f"注册OSC参数: {pattern}")

def handle_channel_a(address: str, *args: Any) -> None:
    """处理通道A的OSC消息"""
    value = sanitize_osc_param(args)
    logger.debug(f"通道A收到OSC消息: {address} = {value}")
    
    # 根据配置的模式处理参数
    if DEFAULT_CONFIG["channel_a"]["mode"] == "distance":
        asyncio.create_task(handle_distance_mode("A", value))
    elif DEFAULT_CONFIG["channel_a"]["mode"] == "shock":
        asyncio.create_task(handle_shock_mode("A", value))

def handle_channel_b(address: str, *args: Any) -> None:
    """处理通道B的OSC消息"""
    value = sanitize_osc_param(args)
    logger.debug(f"通道B收到OSC消息: {address} = {value}")
    
    # 根据配置的模式处理参数
    if DEFAULT_CONFIG["channel_b"]["mode"] == "distance":
        asyncio.create_task(handle_distance_mode("B", value))
    elif DEFAULT_CONFIG["channel_b"]["mode"] == "shock":
        asyncio.create_task(handle_shock_mode("B", value))

def sanitize_osc_param(args: Tuple) -> float:
    """处理并规范化OSC参数值"""
    if not args:
        return 0.0
    
    value = args[0]
    
    # 处理布尔值
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    
    # 处理数值
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    
    # 无法处理的类型，返回0
    logger.warning(f"无法处理的OSC参数类型: {type(value)}")
    return 0.0

async def handle_distance_mode(channel: str, value: float) -> None:
    """处理距离模式"""
    # 检查是否满足触发条件
    channel_key = "channel_a" if channel == "A" else "channel_b"
    bottom = config[channel_key]["trigger_range"]["bottom"]
    top = config[channel_key]["trigger_range"]["top"]
    
    if value <= bottom:
        normalized_value = 0.0
    elif value >= top:
        normalized_value = 1.0
    else:
        normalized_value = (value - bottom) / (top - bottom)
    
    # 获取强度限制
    strength_limit = config[channel_key]["strength_limit"]
    
    # 计算目标强度
    target_strength = int(normalized_value * strength_limit)
    
    # 确保设备有波形设置
    if target_strength > 0 and device and device.is_connected:
        # 使用配置中指定的距离模式波形
        preset_name = config.get("wave_presets", {}).get("distance_mode", "Wave")
        await ensure_device_wave(channel, preset_name)
    
    # 更新设备强度
    await update_device_strength(channel, target_strength)
    
    # 播报状态
    await broadcast_status(f"通道{channel} 距离: {value:.2f}, 归一化: {normalized_value:.2f}, 强度: {target_strength}")

async def handle_shock_mode(channel: str, value: float) -> None:
    """处理电击模式"""
    # 检查是否满足触发条件
    channel_key = "channel_a" if channel == "A" else "channel_b"
    bottom = config[channel_key]["trigger_range"]["bottom"]
    
    if value > bottom:
        # 获取强度限制
        strength_limit = config[channel_key]["strength_limit"]
        
        # 使用配置中指定的电击模式波形
        if device and device.is_connected:
            preset_name = config.get("wave_presets", {}).get("shock_mode", "Pulse")
            await ensure_device_wave(channel, preset_name)
        
        # 设置最大强度
        await update_device_strength(channel, strength_limit)
        
        # 2秒后恢复为0
        await broadcast_status(f"通道{channel} 触发电击，强度: {strength_limit}")
        
        # 创建任务在2秒后将强度设置回0
        asyncio.create_task(reset_strength_after_delay(channel, 2.0))

async def reset_strength_after_delay(channel: str, delay: float) -> None:
    """延迟后重置强度为0"""
    await asyncio.sleep(delay)
    await update_device_strength(channel, 0)
    await broadcast_status(f"通道{channel} 电击结束")

async def update_device_strength(channel: str, strength: int) -> None:
    """更新设备强度"""
    # 确保设备已连接
    if not device or not device.is_connected:
        logger.warning(f"设备未连接，无法设置强度")
        return
    
    # 记录新的强度值
    global last_strength
    last_strength[channel] = strength
    
    # 根据通道设置强度
    try:
        if channel == "A":
            # 使用正确的属性路径设置A通道强度
            device.state.channel_a.strength = strength
            await device.set_strength(strength, device.state.channel_b.strength)
        else:
            # 使用正确的属性路径设置B通道强度
            device.state.channel_b.strength = strength
            await device.set_strength(device.state.channel_a.strength, strength)
        
        logger.info(f"已设置通道{channel}强度为{strength}")
    except Exception as e:
        logger.error(f"设置强度失败: {str(e)}")

async def broadcast_status(message: str) -> None:
    """广播状态消息到所有连接的WebSocket客户端"""
    if not ws_server:
        logger.debug(f"状态消息无法广播(ws_server未初始化): {message}")
        return
        
    if not hasattr(ws_server, 'clients') or not ws_server.clients:
        logger.debug(f"状态消息无法广播(无客户端连接): {message}")
        return
    
    try:
        status_message = json.dumps({
            "type": "plugin_vrchat_osc",
            "message": message
        })
        
        # 广播到所有客户端
        client_count = 0
        for client_id, websocket in ws_server.clients.items():
            try:
                await websocket.send(status_message)
                client_count += 1
            except Exception as e:
                logger.error(f"向客户端 {client_id} 发送状态消息失败: {e}")
        
        if client_count > 0:
            logger.debug(f"状态消息已广播到 {client_count} 个客户端: {message}")
    
    except Exception as e:
        logger.error(f"广播状态消息失败: {e}")

async def load_config() -> None:
    """加载插件配置"""
    global config
    
    # 配置文件路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_config_path = os.path.join(base_dir, "config.json")
    yaml_config_path = os.path.join(base_dir, "config.yaml")
    
    # 首先尝试加载YAML配置
    if os.path.exists(yaml_config_path):
        try:
            with open(yaml_config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info("已从YAML文件加载配置")
            return
        except Exception as e:
            logger.error(f"加载YAML配置失败: {str(e)}")
    
    # 如果YAML配置不存在或加载失败，尝试加载JSON配置
    if os.path.exists(json_config_path):
        try:
            with open(json_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info("已从JSON文件加载配置")
            return
        except Exception as e:
            logger.error(f"加载JSON配置失败: {str(e)}")
    
    # 如果两种配置都加载失败，使用默认配置并创建配置文件
    config = DEFAULT_CONFIG.copy()
    
    # 创建YAML配置文件
    try:
        with open(yaml_config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("已创建默认YAML配置文件")
    except Exception as e:
        logger.error(f"创建YAML配置文件失败: {str(e)}")
        
        # 如果YAML创建失败，尝试创建JSON配置
        try:
            with open(json_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            logger.info("已创建默认JSON配置文件")
        except Exception as e:
            logger.error(f"创建JSON配置文件失败: {str(e)}")

async def save_config() -> None:
    """保存插件配置"""
    global config
    
    # 配置文件路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_config_path = os.path.join(base_dir, "config.json")
    yaml_config_path = os.path.join(base_dir, "config.yaml")
    
    # 首先尝试保存为YAML
    try:
        with open(yaml_config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("已保存配置到YAML文件")
        return
    except Exception as e:
        logger.error(f"保存YAML配置失败: {str(e)}")
    
    # 如果YAML保存失败，尝试保存为JSON
    try:
        with open(json_config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        logger.info("已保存配置到JSON文件")
    except Exception as e:
        logger.error(f"保存JSON配置失败: {str(e)}")

def setup():
    """插件设置函数，加载插件时调用"""
    global server_task
    
    try:
        # 创建配置加载任务
        asyncio.ensure_future(load_config())
        # 创建服务器启动任务
        server_task = asyncio.ensure_future(start_osc_server())
        
        # 初始化设备波形 - 设置为脉冲模式
        if device and device.is_connected:
            asyncio.ensure_future(init_device_wave())
        
        logger.info("VRChat OSC插件已加载")
    except Exception as e:
        logger.error(f"VRChat OSC插件加载失败: {e}")
        raise

async def init_device_wave():
    """初始化设备波形设置"""
    global config
    
    if not device or not device.is_connected:
        logger.warning("设备未连接，无法初始化波形")
        return
    
    # 确保配置已加载
    if config is None:
        logger.warning("配置尚未加载，等待配置加载完成...")
        while config is None:
            await asyncio.sleep(0.1)
        logger.info("配置已加载，继续初始化波形")
    
    try:
        # 获取配置中的默认波形预设
        channel_a_preset = config.get("wave_presets", {}).get("default_channel_a", "Pulse")
        channel_b_preset = config.get("wave_presets", {}).get("default_channel_b", "Pulse")
        
        # 为两个通道设置默认波形预设
        await device.set_wave_preset(channel_a_preset, channel="A")
        await device.set_wave_preset(channel_b_preset, channel="B")
        
        # 更新缓存
        wave_cache["A"] = channel_a_preset
        wave_cache["B"] = channel_b_preset
        wave_cache["A_last_change"] = time.time()
        wave_cache["B_last_change"] = time.time()
        
        logger.info(f"已初始化设备波形预设 (A: {channel_a_preset}, B: {channel_b_preset})")
    except Exception as e:
        logger.error(f"设置波形预设失败: {str(e)}")

def cleanup():
    """插件清理函数，卸载插件时调用"""
    global running, server_task, osc_server
    
    try:
        # 停止OSC服务器
        running = False
        
        # 关闭OSC服务器
        if osc_server and hasattr(osc_server, 'transport') and osc_server.transport:
            osc_server.transport.close()
            logger.info("OSC服务器已关闭")
        
        # 取消服务器任务
        if server_task and not server_task.done():
            server_task.cancel()
            server_task = None
        
        # 保存配置（不使用run_until_complete）
        asyncio.ensure_future(save_config())
        
        logger.info("VRChat OSC插件已卸载")
    except Exception as e:
        logger.error(f"VRChat OSC插件卸载失败: {e}")

async def handle_message(websocket, message_data):
    """
    处理WebSocket消息
    
    Args:
        websocket: WebSocket连接
        message_data: 消息数据
        
    Returns:
        bool: 消息是否被处理
    """
    # 声明全局变量
    global config, server_task, running
    
    # 检查是否是针对本插件的消息
    if message_data.get("type") == "plugin_vrchat_osc":
        # 处理配置更新
        if message_data.get("action") == "update_config":
            new_config = message_data.get("config", {})
            if new_config:
                # 更新配置
                config.update(new_config)
                
                # 保存配置
                await save_config()
                
                # 重启OSC服务器以应用新配置
                if running and server_task:
                    running = False
                    server_task.cancel()
                    server_task = None
                    server_task = asyncio.ensure_future(start_osc_server())
                
                # 发送成功响应
                await websocket.send(json.dumps({
                    "type": "plugin_vrchat_osc_response",
                    "action": "update_config",
                    "success": True,
                    "message": "配置已更新"
                }))
                
                return True
        
        # 处理获取配置请求
        elif message_data.get("action") == "get_config":
            # 发送当前配置
            await websocket.send(json.dumps({
                "type": "plugin_vrchat_osc_response",
                "action": "get_config",
                "config": config
            }))
            
            return True
            
        # 处理设置波形预设请求
        elif message_data.get("action") == "set_wave_preset":
            preset_name = message_data.get("preset", "Pulse")
            channel = message_data.get("channel", "both")
            
            success = False
            message = ""
            
            if not device or not device.is_connected:
                message = "设备未连接，无法设置波形"
            else:
                try:
                    if channel == "both" or channel == "A":
                        await device.set_wave_preset(preset_name, channel="A")
                    
                    if channel == "both" or channel == "B":
                        await device.set_wave_preset(preset_name, channel="B")
                    
                    success = True
                    message = f"已设置通道{channel}波形预设为{preset_name}"
                    logger.info(message)
                except Exception as e:
                    message = f"设置波形预设失败: {str(e)}"
                    logger.error(message)
            
            # 发送响应
            await websocket.send(json.dumps({
                "type": "plugin_vrchat_osc_response",
                "action": "set_wave_preset",
                "success": success,
                "message": message
            }))
            
            return True
        
        # 添加获取所有可用波形预设的处理
        elif message_data.get("action") == "get_wave_presets":
            if device and device.is_connected:
                try:
                    # 获取所有可用的波形预设
                    preset_names = device.get_wave_preset_names()
                    
                    # 发送响应
                    await websocket.send(json.dumps({
                        "type": "plugin_vrchat_osc_response",
                        "action": "get_wave_presets",
                        "presets": preset_names
                    }))
                except Exception as e:
                    await websocket.send(json.dumps({
                        "type": "plugin_vrchat_osc_response",
                        "action": "get_wave_presets",
                        "error": str(e)
                    }))
            else:
                await websocket.send(json.dumps({
                    "type": "plugin_vrchat_osc_response",
                    "action": "get_wave_presets",
                    "error": "设备未连接"
                }))
            
            return True
    
    # 消息未被处理
    return False

# 设置ws_server和device引用的函数
def set_ws_server(server):
    """设置WebSocket服务器引用"""
    global ws_server, device
    ws_server = server
    
    # 获取设备引用
    if hasattr(server, 'device'):
        device = server.device
        # 设备就绪后初始化波形
        if device and device.is_connected:
            asyncio.ensure_future(init_device_wave())

async def ensure_device_wave(channel: str, preset_name: str = None) -> None:
    """
    确保设备有波形设置，具有缓存和防抖动功能
    
    Args:
        channel: 设备通道 ("A" 或 "B")
        preset_name: 波形预设名称，如果为None则使用配置中的默认值
    """
    global wave_cache
    
    if not device or not device.is_connected:
        logger.warning(f"设备未连接，无法设置波形")
        return
    
    try:
        # 如果未指定预设名称，使用配置中设置的默认值
        if preset_name is None:
            channel_key = "default_channel_a" if channel == "A" else "default_channel_b"
            preset_name = config.get("wave_presets", {}).get(channel_key, "Pulse")
        
        # 检查波形是否已经设置以及上次更新时间
        current_time = time.time()
        last_change_key = f"{channel}_last_change"
        
        # 如果波形相同且更新间隔不足，则不重复设置
        if (wave_cache[channel] == preset_name and 
            current_time - wave_cache[last_change_key] < WAVE_UPDATE_INTERVAL):
            return
        
        # 更新缓存
        wave_cache[channel] = preset_name
        wave_cache[last_change_key] = current_time
        
        # 设置波形预设
        await device.set_wave_preset(preset_name, channel=channel)
        logger.debug(f"已设置通道{channel}波形预设为{preset_name}")
    except Exception as e:
        logger.error(f"设置波形预设失败: {str(e)}")

def set_waveform_preset(preset_name: str) -> bool:
    """
    设置波形预设
    
    Args:
        preset_name: 预设名称
        
    Returns:
        bool: 设置是否成功
    """
    global config, device
    
    try:
        # 检查配置是否已加载
        if config is None:
            logger.warning("配置尚未加载，无法设置波形预设")
            return False
            
        # 检查预设是否存在
        if preset_name not in config['wave_presets']:
            logger.error(f"波形预设 {preset_name} 不存在")
            return False
            
        # 获取预设配置
        preset = config['wave_presets'][preset_name]
        
        # 设置通道A和B的波形
        if 'channel_a' in preset and device and device.is_connected:
            asyncio.create_task(device.set_wave_preset(preset['channel_a'], channel='A'))
            
        if 'channel_b' in preset and device and device.is_connected:
            asyncio.create_task(device.set_wave_preset(preset['channel_b'], channel='B'))
            
        logger.info(f"已设置波形预设: {preset_name}")
        return True
        
    except Exception as e:
        logger.error(f"设置波形预设失败: {str(e)}")
        return False 