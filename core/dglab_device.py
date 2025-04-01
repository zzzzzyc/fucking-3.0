"""
DG-LAB设备控制接口
提供设备控制的高级API
"""

import asyncio
import logging
from typing import List, Tuple, Dict, Optional, Any, Union
from bleak import BleakClient
from bleak.exc import BleakError

from .bluetooth import (
    scan_devices, 
    get_battery_level, 
    get_strength, 
    set_strength,
    set_wave,
    DeviceUUID
)
from .models import ChannelA, ChannelB, DGLabState, WaveSet

# 设置日志
logger = logging.getLogger(__name__)


class DGLabDevice:
    """DG-LAB设备控制类"""
    
    def __init__(self, device_address: Optional[str] = None):
        """
        初始化DG-LAB设备控制
        
        Args:
            device_address: 设备蓝牙地址，如不提供则需后续扫描连接
        """
        self.state = DGLabState()
        self.state.device_address = device_address
        self.client: Optional[BleakClient] = None
        self.wave_task: Optional[asyncio.Task] = None
        self._channel_a_wave_set: List[Tuple[int, int, int]] = []
        self._channel_b_wave_set: List[Tuple[int, int, int]] = []
        self._wave_index_a: int = 0
        self._wave_index_b: int = 0
        self._stop_event = asyncio.Event()
    
    @property
    def is_connected(self) -> bool:
        """设备是否已连接"""
        return self.state.connected and self.client is not None and self.client.is_connected
    
    @property
    def device_address(self) -> str:
        """获取设备地址"""
        return self.state.device_address
    
    @classmethod
    async def scan_and_connect(cls, timeout: float = 5.0) -> 'DGLabDevice':
        """
        扫描并连接信号最强的DG-LAB设备
        
        Args:
            timeout: 扫描超时时间（秒）
            
        Returns:
            DGLabDevice: 已连接的设备控制对象
            
        Raises:
            RuntimeError: 未找到设备时抛出
        """
        devices = await scan_devices(timeout)
        if not devices:
            raise RuntimeError("未找到DG-LAB V2设备")
        
        # 按信号强度排序，连接信号最强的设备
        devices.sort(key=lambda x: x[1], reverse=True)
        best_device = devices[0]
        
        logger.info(f"连接信号最强的设备: {best_device[2]} ({best_device[0]})")
        device = cls(best_device[0])
        await device.connect()
        return device
    
    async def connect(self, timeout: float = 20.0) -> None:
        """
        连接到设备
        
        Args:
            timeout: 连接超时时间（秒）
            
        Raises:
            RuntimeError: 设备地址未设置时抛出
            TimeoutError: 连接超时时抛出
            BleakError: 连接失败时抛出
        """
        if not self.state.device_address:
            raise RuntimeError("设备地址未设置，请先扫描或手动设置地址")
        
        if self.is_connected:
            logger.info("设备已连接")
            return
        
        logger.info(f"正在连接设备: {self.state.device_address}")
        
        try:
            # 创建客户端并连接
            self.client = BleakClient(self.state.device_address, timeout=timeout)
            await self.client.connect()
            
            # 等待服务发现完成
            await asyncio.sleep(1)
            
            # 验证设备服务
            services = self.client.services
            service_uuids = [service.uuid for service in services]
            
            if (DeviceUUID.SERVICE_BATTERY in service_uuids and 
                DeviceUUID.SERVICE_ESTIM in service_uuids):
                logger.info("设备连接成功，已验证为DG-LAB V2设备")
                self.state.connected = True
                
                # 更新初始状态
                await self.update_battery()
                await self.update_strength()
                
                # 设置初始波形和强度
                await self.set_strength(1, 1)  # 设置初始强度为最小值1（而不是0）
                await self.set_wave(0, 0, 0, channel='A')
                await self.set_wave(0, 0, 0, channel='B')
                
                # 重置波形设置
                self._channel_a_wave_set = []
                self._channel_b_wave_set = []
                
                # 启动波形控制
                self._start_wave_control()
            else:
                await self.client.disconnect()
                self.client = None
                raise BleakError("连接的设备不是DG-LAB V2设备")
                
        except asyncio.TimeoutError:
            logger.error("连接超时")
            self.client = None
            raise TimeoutError("连接设备超时")
        except BleakError as e:
            logger.error(f"蓝牙连接错误: {e}")
            self.client = None
            raise
    
    async def disconnect(self) -> None:
        """断开设备连接"""
        if not self.is_connected:
            logger.info("设备未连接")
            return
        
        # 停止波形控制任务
        if self.wave_task:
            self._stop_event.set()
            try:
                await asyncio.wait_for(self.wave_task, timeout=2.0)
            except asyncio.TimeoutError:
                if not self.wave_task.done():
                    self.wave_task.cancel()
            self.wave_task = None
        
        # 断开连接
        try:
            logger.info("断开设备连接")
            await self.client.disconnect()
        except Exception as e:
            logger.error(f"断开连接时发生错误: {e}")
        finally:
            self.client = None
            self.state.connected = False
    
    async def update_battery(self) -> int:
        """
        更新电池电量
        
        Returns:
            int: 电池电量百分比
        """
        if not self.is_connected:
            raise RuntimeError("设备未连接")
        
        battery = await get_battery_level(self.client)
        self.state.battery = battery
        logger.info(f"电池电量: {battery}%")
        return battery
    
    async def update_strength(self) -> Tuple[int, int]:
        """
        更新强度信息，但不覆盖当前UI设置的值
        
        Returns:
            Tuple[int, int]: (通道A强度, 通道B强度)
        """
        if not self.is_connected:
            raise RuntimeError("设备未连接")
        
        # 读取设备当前强度值，但只记录在日志中，不更新UI
        strength_a, strength_b = await get_strength(self.client)
        logger.debug(f"设备返回的强度: A={strength_a}, B={strength_b}，UI显示值: A={self.state.channel_a.strength}, B={self.state.channel_b.strength}")
        
        # 返回UI中设置的值，而不是设备返回的值
        return self.state.channel_a.strength, self.state.channel_b.strength
    
    async def set_strength(self, strength_a: int, strength_b: int) -> Tuple[int, int]:
        """
        设置设备强度
        
        Args:
            strength_a: 通道A强度 (0-100)
            strength_b: 通道B强度 (0-100)
            
        Returns:
            Tuple[int, int]: (通道A强度, 通道B强度)
        """
        if not self.is_connected:
            raise RuntimeError("设备未连接")
        
        # 强度值限制在0-100范围内
        strength_a = max(0, min(100, strength_a))
        strength_b = max(0, min(100, strength_b))
        
        # 先更新UI状态，无论发送是否成功
        self.state.channel_a.strength = strength_a
        self.state.channel_b.strength = strength_b
        
        # 然后发送到设备
        success = await set_strength(self.client, strength_a, strength_b)
        if success:
            logger.info(f"强度设置成功: A={strength_a}, B={strength_b}")
        else:
            logger.error("强度设置失败")
        
        # 始终返回UI设置的值
        return self.state.channel_a.strength, self.state.channel_b.strength
    
    async def set_wave(
        self, 
        wave_x: int, 
        wave_y: int, 
        wave_z: int, 
        channel: str = 'A'
    ) -> bool:
        """
        设置波形参数
        
        Args:
            wave_x: 波形X参数 (0-100)
            wave_y: 波形Y参数 (0-255)
            wave_z: 波形Z参数 (0-255)
            channel: 通道 ('A' 或 'B')
            
        Returns:
            bool: 设置是否成功
        """
        if not self.is_connected:
            raise RuntimeError("设备未连接")
        
        channel = channel.upper()
        if channel not in ['A', 'B']:
            raise ValueError("通道必须是 'A' 或 'B'")
        
        success = await set_wave(
            self.client, 
            channel, 
            wave_x, 
            wave_y, 
            wave_z
        )
        
        if success:
            if channel == 'A':
                self.state.channel_a.wave_x = wave_x
                self.state.channel_a.wave_y = wave_y
                self.state.channel_a.wave_z = wave_z
            else:
                self.state.channel_b.wave_x = wave_x
                self.state.channel_b.wave_y = wave_y
                self.state.channel_b.wave_z = wave_z
                
        #    logger.debug(f"设置通道{channel}波形成功: X={wave_x}, Y={wave_y}, Z={wave_z}")
        else:
            logger.error(f"设置通道{channel}波形失败")
        
        return success
    
    async def set_wave_preset(
        self, 
        preset_name: str, 
        channel: str = 'A'
    ) -> bool:
        """
        使用预设波形
        
        Args:
            preset_name: 预设波形名称
            channel: 通道 ('A' 或 'B')
            
        Returns:
            bool: 设置是否成功
        """
        wave_set = WaveSet.get_preset(preset_name)
        
        channel = channel.upper()
        if channel not in ['A', 'B']:
            raise ValueError("通道必须是 'A' 或 'B'")
        
        if channel == 'A':
            self._channel_a_wave_set = wave_set
            self._wave_index_a = 0
        else:
            self._channel_b_wave_set = wave_set
            self._wave_index_b = 0
        
        logger.info(f"设置通道{channel}波形预设: {preset_name}")
        return True
    
    def _start_wave_control(self) -> None:
        """启动波形控制任务"""
        if self.wave_task and not self.wave_task.done():
            return
            
        self._stop_event.clear()
        self.wave_task = asyncio.create_task(self._wave_control_loop())
    
    async def _wave_control_loop(self) -> None:
        """波形控制循环，自动切换波形"""
        logger.info("启动波形控制循环")
        try:
            while not self._stop_event.is_set() and self.is_connected:
                # 处理通道A波形
                if self._channel_a_wave_set:
                    wave = self._channel_a_wave_set[self._wave_index_a]
                    await self.set_wave(wave[0], wave[1], wave[2], channel='A')
                    self._wave_index_a = (self._wave_index_a + 1) % len(self._channel_a_wave_set)
                
                # 处理通道B波形
                if self._channel_b_wave_set:
                    wave = self._channel_b_wave_set[self._wave_index_b]
                    await self.set_wave(wave[0], wave[1], wave[2], channel='B')
                    self._wave_index_b = (self._wave_index_b + 1) % len(self._channel_b_wave_set)
                
                # 等待
                await asyncio.sleep(0.1)  # 改回官方建议的0.1秒，确保波形输出符合规范
        except asyncio.CancelledError:
            logger.info("波形控制任务被取消")
        except Exception as e:
            logger.error(f"波形控制循环出错: {e}")
        finally:
            logger.info("波形控制循环结束")
            
    async def get_state(self) -> Dict[str, Any]:
        """
        获取设备完整状态
        
        Returns:
            Dict: 设备状态信息
        """
        # 只读取电池电量，不读取强度，因为我们不想用设备值覆盖UI值
        if self.is_connected:
            await self.update_battery()
            # 不再调用 await self.update_strength()
        
        return {
            "connected": bool(self.is_connected),  # 确保是布尔值
            "device_address": self.state.device_address,
            "battery": self.state.battery,
            "channel_a": {
                "strength": self.state.channel_a.strength,
                "wave": self.state.channel_a.wave
            },
            "channel_b": {
                "strength": self.state.channel_b.strength,
                "wave": self.state.channel_b.wave
            },
            "wave_presets": WaveSet.get_preset_names()
        } 