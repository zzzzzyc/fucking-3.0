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
        "listen_port": 9001,
        "throttle_interval_ms": 100, # 新增：强度更新节流间隔（毫秒）
        "strength_scale_factor": 0.1  # 新增：强度转换系数，默认
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

# 记录目标强度值和上次发送的强度值，用于节流
target_strength = {"A": 0, "B": 0}
last_sent_strength = {"A": -1, "B": -1} # 初始化为-1以确保首次更新
strength_sender_task = None
THROTTLE_INTERVAL = 0.1 # 默认节流间隔 (秒)

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
    global config
    value = sanitize_osc_param(args)
    logger.debug(f"通道A收到OSC消息: {address} = {value}")
    
    # 等待配置加载完成
    if not config:
        logger.warning("配置尚未加载，无法处理OSC消息")
        return
    
    # 根据配置的模式处理参数
    if config["channel_a"]["mode"] == "distance":
        asyncio.create_task(handle_distance_mode("A", value))
    elif config["channel_a"]["mode"] == "shock":
        asyncio.create_task(handle_shock_mode("A", value))

def handle_channel_b(address: str, *args: Any) -> None:
    """处理通道B的OSC消息"""
    global config
    value = sanitize_osc_param(args)
    logger.debug(f"通道B收到OSC消息: {address} = {value}")
    
    # 等待配置加载完成
    if not config:
        logger.warning("配置尚未加载，无法处理OSC消息")
        return
    
    # 根据配置的模式处理参数
    if config["channel_b"]["mode"] == "distance":
        asyncio.create_task(handle_distance_mode("B", value))
    elif config["channel_b"]["mode"] == "shock":
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
        # 将OSC参数限制在0.0到1.0之间
        clamped_value = max(0.0, min(1.0, float(value)))
        # logger.debug(f"Sanitized OSC value: {clamped_value}") # 添加日志记录
        return clamped_value
    
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
    
    # 更新目标强度值 (节流处理)
    update_target_strength(channel, target_strength)
    
    # 播报状态
    await broadcast_status(f"通道{channel} 距离: {value:.2f}, 归一化: {normalized_value:.2f}, 目标强度: {target_strength}")

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
        
        # 设置目标强度 (节流处理)
        update_target_strength(channel, strength_limit)
        
        # 2秒后恢复为0
        await broadcast_status(f"通道{channel} 触发电击，目标强度: {strength_limit}")
        
        # 创建任务在指定延迟后将目标强度设置回0
        asyncio.create_task(reset_target_strength_after_delay(channel, 2.0))

async def reset_target_strength_after_delay(channel: str, delay: float) -> None:
    """延迟后重置目标强度为0"""
    await asyncio.sleep(delay)
    update_target_strength(channel, 0) # 更新目标强度
    await broadcast_status(f"通道{channel} 电击结束，目标强度恢复为0")

# 修改: 不再直接发送，只更新目标值
def update_target_strength(channel: str, strength: int) -> None:
    """更新目标强度值，由节流任务发送"""
    global target_strength
    # 确保强度在0-100之间
    clamped_strength = max(0, min(100, strength))
    if target_strength[channel] != clamped_strength:
        target_strength[channel] = clamped_strength
        # logger.debug(f"通道 {channel} 目标强度更新为: {clamped_strength}") # 调试日志

# 新增: 节流发送强度任务
async def _throttled_strength_sender() -> None:
    """定期检查目标强度并发送更新到设备"""
    global last_sent_strength, running, device, THROTTLE_INTERVAL, config

    logger.info(f"启动强度节流发送任务，间隔: {THROTTLE_INTERVAL:.3f} 秒")
    
    # 默认强度转换系数为1.0
    strength_scale = 1.0
    
    # 尝试从配置获取强度转换系数
    try:
        strength_scale = config.get("osc", {}).get("strength_scale_factor", 1.0)
        if strength_scale <= 0:
            logger.warning(f"强度转换系数 ({strength_scale}) 不合法，重置为默认值 1.0")
            strength_scale = 1.0
        logger.info(f"使用强度转换系数: {strength_scale}，目标强度将乘以此系数")
    except Exception as e:
        logger.error(f"读取强度转换系数失败: {e}，使用默认值 1.0")
    
    error_count = 0
    while running:
        try:
            await asyncio.sleep(THROTTLE_INTERVAL)

            if not device:
                logger.debug("设备实例不存在，跳过本次发送 (等待设备连接)")
                continue
                
            if not device.is_connected:
                # 如果设备断开，重置上次发送状态，以便连接后立即发送
                if last_sent_strength["A"] != -1 or last_sent_strength["B"] != -1:
                    last_sent_strength = {"A": -1, "B": -1}
                    logger.debug("设备未连接，已重置上次发送状态")
                continue # 设备未连接，跳过本次发送

            # 应用强度转换系数计算实际发送强度 (先转换为浮点数，再取整)
            raw_ts_a = int(target_strength["A"] * float(strength_scale))
            raw_ts_b = int(target_strength["B"] * float(strength_scale))
            
            # 确保强度在有效范围内 (0-100)
            ts_a = max(0, min(100, raw_ts_a))
            ts_b = max(0, min(100, raw_ts_b))

            # 只有当目标强度与上次发送的强度不同时才发送
            if ts_a != last_sent_strength["A"] or ts_b != last_sent_strength["B"]:
                logger.debug(f"节流发送强度: A={ts_a} (原值: {target_strength['A']}×{strength_scale}={raw_ts_a}), " +
                           f"B={ts_b} (原值: {target_strength['B']}×{strength_scale}={raw_ts_b})")
                try:
                    # 不管怎样，发送前先检查设备连接状态
                    if not device.is_connected:
                        logger.warning("设备断开连接，跳过本次强度发送")
                        continue
                    
                    # 即使强度为0也发送，以便清除之前的强度设置
                    await device.set_strength(ts_a, ts_b)
                    last_sent_strength["A"] = ts_a
                    last_sent_strength["B"] = ts_b
                    
                    # 重置错误计数
                    if error_count > 0:
                        error_count = 0
                        
                    logger.info(f"通过节流任务设置强度成功: A={ts_a}, B={ts_b} (原始强度: A={target_strength['A']}, B={target_strength['B']})")
                except Exception as e:
                    error_count += 1
                    logger.error(f"节流发送强度失败 (第{error_count}次): {e}")
                    # 发送失败时重置 last_sent_strength 让下次强制重试
                    last_sent_strength = {"A": -1, "B": -1}
                    
                    # 如果连续失败超过5次，等待较长时间
                    if error_count >= 5:
                        logger.error(f"连续失败{error_count}次，暂停10秒后继续...")
                        await asyncio.sleep(10)
                        error_count = 0
        except asyncio.CancelledError:
            logger.info("强度节流任务被取消")
            break
        except Exception as e:
            logger.error(f"强度节流任务错误: {e}")
            # 短暂暂停后继续运行
            await asyncio.sleep(1)
            
    logger.info("强度节流任务结束")

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
    if config is None: # 检查config是否仍为None
        config = DEFAULT_CONFIG.copy()
        logger.info("使用默认配置")
        # 尝试创建配置文件...
        # 创建YAML配置文件
        try:
            with open(yaml_config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.info("已创建默认YAML配置文件")
        except Exception as e:
            logger.error(f"创建YAML配置文件失败: {str(e)}")
            # 尝试创建JSON配置
            try:
                with open(json_config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                logger.info("已创建默认JSON配置文件")
            except Exception as e:
                logger.error(f"创建JSON配置文件失败: {str(e)}")
    else:
        # 确保加载的配置包含必要的字段
        if "osc" not in config:
            config["osc"] = DEFAULT_CONFIG["osc"].copy()
        else:
            # 检查并添加缺少的字段
            for key, value in DEFAULT_CONFIG["osc"].items():
                if key not in config["osc"]:
                    config["osc"][key] = value
                    logger.info(f"配置中缺少 {key}，已添加默认值: {value}")

    # 更新节流间隔
    global THROTTLE_INTERVAL
    THROTTLE_INTERVAL = config.get("osc", {}).get("throttle_interval_ms", 100) / 1000.0
    THROTTLE_INTERVAL = max(0.05, THROTTLE_INTERVAL) # 限制最小间隔为50ms

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
    global server_task, strength_sender_task, running
    
    try:
        # 确保 running 标志为 True
        running = True
        
        # 创建任务链设置，确保顺序执行
        def config_loaded_callback(future):
            try:
                # 配置加载完成，可以继续初始化其他部分
                logger.info("配置加载完成，开始初始化OSC服务器和节流任务")
                
                # 创建服务器启动任务
                global server_task, strength_sender_task
                server_task = asyncio.ensure_future(start_osc_server())
                logger.info("OSC服务器任务已启动")
                
                # 创建强度节流发送任务
                strength_sender_task = asyncio.ensure_future(_throttled_strength_sender())
                logger.info("强度节流任务已启动")
                
                # 如果设备已连接，初始化波形
                if device and device.is_connected:
                    logger.info("设备已连接，初始化波形...")
                    asyncio.ensure_future(init_device_wave())
                else:
                    logger.warning("设备未连接，将在设备连接后初始化波形")
            except Exception as e:
                logger.error(f"初始化服务任务失败: {e}")
        
        # 先加载配置（异步），并设置回调
        logger.info("开始加载配置...")
        config_future = asyncio.ensure_future(load_config())
        config_future.add_done_callback(config_loaded_callback)
        
        logger.info("VRChat OSC插件已加载，等待配置和初始化完成")
        
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
    global running, server_task, osc_server, strength_sender_task
    
    try:
        # 停止OSC服务器和节流任务
        running = False
        
        # 取消强度节流任务
        if strength_sender_task and not strength_sender_task.done():
            strength_sender_task.cancel()
            logger.info("强度节流发送任务已取消")
            strength_sender_task = None
        
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
        # 检查设备实例是否改变或首次设置
        new_device_instance = server.device is not device
        device = server.device
        # 设备就绪后初始化波形 (仅在首次设置或设备实例改变时)
        if device and device.is_connected and new_device_instance:
            logger.info("检测到设备实例或首次设置，初始化波形...")
            asyncio.ensure_future(init_device_wave())
        # 重置上次发送强度，以便在新设备上强制发送初始强度
        global last_sent_strength
        last_sent_strength = {"A": -1, "B": -1}

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