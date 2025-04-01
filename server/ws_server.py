"""
DG-LAB WebSocket服务器实现
允许通过WebSocket接口控制DG-LAB设备
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Set, Callable
import websockets
from websockets.server import WebSocketServerProtocol

from core.dglab_device import DGLabDevice
from core.models import WaveSet

# 设置日志
logger = logging.getLogger(__name__)


class DGLabWebSocketServer:
    """DG-LAB WebSocket服务器"""
    
    def __init__(
        self, 
        host: str = "127.0.0.1", 
        port: int = 8080, 
        device: Optional[DGLabDevice] = None
    ):
        """
        初始化WebSocket服务器
        
        Args:
            host: 服务器主机地址
            port: 服务器端口
            device: 可选的DGLabDevice实例，如不提供则自动扫描连接
        """
        self.host = host
        self.port = port
        self.device = device
        self.server = None
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        self.plugins: Dict[str, Callable] = {}
        self.running = False
        self._update_task = None
        self._stop_event = asyncio.Event()
    
    async def start(self) -> None:
        """启动WebSocket服务器"""
        if self.running:
            logger.warning("服务器已经在运行中")
            return
        
        # 如果没有设备，尝试扫描连接
        if self.device is None:
            try:
                logger.info("正在扫描并连接DG-LAB设备...")
                self.device = await DGLabDevice.scan_and_connect()
            except Exception as e:
                logger.error(f"连接设备失败: {e}")
                raise RuntimeError(f"无法启动服务器，未找到设备: {e}")
        
        # 启动服务器
        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )
        
        self.running = True
        logger.info(f"WebSocket服务器已启动: ws://{self.host}:{self.port}")
        
        # 启动状态更新任务
        self._stop_event.clear()
        self._update_task = asyncio.create_task(self._update_clients_loop())
    
    async def stop(self) -> None:
        """停止WebSocket服务器"""
        if not self.running:
            logger.warning("服务器未运行")
            return
        
        # 停止状态更新任务
        if self._update_task:
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._update_task, timeout=2.0)
            except asyncio.TimeoutError:
                if not self._update_task.done():
                    self._update_task.cancel()
            self._update_task = None
        
        # 关闭所有客户端连接
        close_tasks = []
        for client_id, websocket in self.clients.items():
            close_tasks.append(websocket.close(1001, "服务器关闭"))
        
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # 断开设备连接
        if self.device:
            await self.device.disconnect()
        
        # 关闭服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        
        self.running = False
        logger.info("WebSocket服务器已停止")
    
    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """
        处理WebSocket客户端连接
        
        Args:
            websocket: WebSocket连接
        """
        # 生成客户端ID
        client_id = str(uuid.uuid4())
        
        # 添加到客户端列表
        self.clients[client_id] = websocket
        logger.info(f"客户端 {client_id} 已连接，当前客户端数量: {len(self.clients)}")
        
        try:
            # 发送初始状态
            await self._send_state(websocket)
            
            # 循环处理客户端消息
            async for message in websocket:
                try:
                    # 解析消息
                    data = json.loads(message)
                    await self._handle_message(websocket, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "无效的JSON格式"
                    }))
                except Exception as e:
                    logger.error(f"处理消息错误: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"处理请求错误: {str(e)}"
                    }))
        except websockets.exceptions.ConnectionClosedOK:
            logger.info(f"客户端 {client_id} 正常断开连接")
        except websockets.exceptions.ConnectionClosedError:
            logger.info(f"客户端 {client_id} 异常断开连接")
        except Exception as e:
            logger.error(f"处理客户端连接错误: {e}")
        finally:
            # 清理客户端
            if client_id in self.clients:
                del self.clients[client_id]
            logger.info(f"客户端 {client_id} 已断开连接，当前客户端数量: {len(self.clients)}")
    
    async def _handle_message(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]) -> None:
        """
        处理客户端消息
        
        Args:
            websocket: WebSocket连接
            data: 消息数据
        """
        message_type = data.get("type")
        
        if not message_type:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "消息缺少type字段"
            }))
            return
        
        # 处理不同类型的消息
        if message_type == "ping":
            await websocket.send(json.dumps({
                "type": "pong",
                "timestamp": data.get("timestamp", 0)
            }))
        
        elif message_type == "get_state":
            await self._send_state(websocket)
        
        elif message_type == "set_strength":
            try:
                channel_a = int(data.get("channel_a", 0))
                channel_b = int(data.get("channel_b", 0))
                
                await self.device.set_strength(channel_a, channel_b)
                await self._send_state(websocket)
            except Exception as e:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"设置强度错误: {str(e)}"
                }))
        
        elif message_type == "set_wave":
            try:
                channel = data.get("channel", "A")
                wave_x = int(data.get("wave_x", 0))
                wave_y = int(data.get("wave_y", 0))
                wave_z = int(data.get("wave_z", 0))
                
                await self.device.set_wave(wave_x, wave_y, wave_z, channel)
                await self._send_state(websocket)
            except Exception as e:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"设置波形错误: {str(e)}"
                }))
        
        elif message_type == "set_wave_preset":
            try:
                preset_name = data.get("preset_name")
                channel = data.get("channel", "A")
                
                if preset_name not in WaveSet.get_preset_names():
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"未知的波形预设: {preset_name}"
                    }))
                    return
                
                await self.device.set_wave_preset(preset_name, channel)
                await self._send_state(websocket)
            except Exception as e:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"设置波形预设错误: {str(e)}"
                }))
        
        elif message_type == "scan_devices":
            try:
                # 断开当前设备
                if self.device and self.device.is_connected:
                    await self.device.disconnect()
                
                # 扫描并连接新设备
                self.device = await DGLabDevice.scan_and_connect()
                
                # 广播设备状态更新
                await self._broadcast_state()
            except Exception as e:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"扫描设备错误: {str(e)}"
                }))
                
        elif message_type == "disconnect_device":
            try:
                if self.device:
                    await self.device.disconnect()
                    await self._broadcast_state()
            except Exception as e:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"断开设备错误: {str(e)}"
                }))
                
        elif message_type == "connect_device":
            try:
                device_address = data.get("device_address")
                if not device_address:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "未提供设备地址"
                    }))
                    return
                
                # 断开当前设备
                if self.device and self.device.is_connected:
                    await self.device.disconnect()
                
                # 创建新设备并连接
                logger.info(f"正在连接设备: {device_address}")
                from core.dglab_device import DGLabDevice
                self.device = DGLabDevice(device_address)
                await self.device.connect()
                
                # 广播设备状态更新
                await self._broadcast_state()
                
                await websocket.send(json.dumps({
                    "type": "success",
                    "message": f"成功连接到设备: {device_address}"
                }))
            except Exception as e:
                logger.error(f"连接设备错误: {e}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"连接设备错误: {str(e)}"
                }))
                
        # 为插件预留的消息处理
        elif message_type.startswith("plugin_"):
            plugin_name = message_type[7:]  # 移除"plugin_"前缀
            if plugin_name in self.plugins:
                try:
                    result = await self.plugins[plugin_name](self.device, data)
                    await websocket.send(json.dumps({
                        "type": f"plugin_{plugin_name}_result",
                        "result": result
                    }))
                except Exception as e:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"插件处理错误: {str(e)}"
                    }))
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"未找到插件: {plugin_name}"
                }))
        
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"未知的消息类型: {message_type}"
            }))
    
    async def _send_state(self, websocket: WebSocketServerProtocol) -> None:
        """
        发送设备状态到客户端
        
        Args:
            websocket: WebSocket连接
        """
        state = {
            "type": "state",
            "data": {
                "connected": False,
                "device_address": "",
                "battery": 0,
                "channel_a": {
                    "strength": 0,
                    "wave": [0, 0, 0]
                },
                "channel_b": {
                    "strength": 0,
                    "wave": [0, 0, 0]
                },
                "wave_presets": WaveSet.get_preset_names()
            }
        }
        
        # 如果设备已连接，获取真实状态
        if self.device and self.device.is_connected:
            device_state = await self.device.get_state()
            state["data"].update(device_state)
        
        await websocket.send(json.dumps(state))
    
    async def _broadcast_state(self) -> None:
        """广播设备状态到所有已连接的客户端"""
        if not self.clients:
            return
        
        state = {
            "type": "state",
            "data": {
                "connected": False,
                "device_address": "",
                "battery": 0,
                "channel_a": {
                    "strength": 0,
                    "wave": [0, 0, 0]
                },
                "channel_b": {
                    "strength": 0,
                    "wave": [0, 0, 0]
                },
                "wave_presets": WaveSet.get_preset_names()
            }
        }
        
        # 如果设备已连接，获取真实状态
        if self.device and self.device.is_connected:
            device_state = await self.device.get_state()
            state["data"].update(device_state)
        
        message = json.dumps(state)
        
        # 广播到所有客户端
        for websocket in self.clients.values():
            try:
                await websocket.send(message)
            except Exception as e:
                logger.error(f"向客户端广播状态失败: {e}")
    
    async def _update_clients_loop(self) -> None:
        """客户端状态更新循环"""
        logger.info("启动客户端状态更新循环")
        try:
            while not self._stop_event.is_set() and self.running:
                # 每5秒广播一次状态
                await self._broadcast_state()
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("客户端状态更新任务被取消")
        except Exception as e:
            logger.error(f"客户端状态更新循环出错: {e}")
        finally:
            logger.info("客户端状态更新循环结束")
    
    def register_plugin(self, name: str, handler: Callable) -> None:
        """
        注册插件处理函数
        
        Args:
            name: 插件名称
            handler: 处理函数，签名为 async def handler(device, data) -> Any
        """
        if name in self.plugins:
            logger.warning(f"插件 {name} 已存在，将被覆盖")
        
        self.plugins[name] = handler
        logger.info(f"插件 {name} 已注册") 