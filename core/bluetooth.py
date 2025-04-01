"""
DG-LAB V2 蓝牙通信模块
负责设备扫描和基础蓝牙通信功能
"""

import asyncio
import logging
from typing import List, Tuple, Dict, Optional, Any
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice

# 设置日志
logger = logging.getLogger(__name__)

# DG-LAB V2设备特征UUID
class DeviceUUID:
    """DG-LAB V2设备UUID定义"""
    
    # 设备名称前缀
    DEVICE_NAME_PREFIX = "D-LAB ESTIM"
    
    # 服务UUID
    SERVICE_BATTERY = "955a180a-0fe2-f5aa-a094-84b8d4f3e8ad"
    SERVICE_ESTIM = "955a180b-0fe2-f5aa-a094-84b8d4f3e8ad"
    
    # 特征UUID
    CHAR_BATTERY = "955a1500-0fe2-f5aa-a094-84b8d4f3e8ad"
    CHAR_ESTIM_POWER = "955a1504-0fe2-f5aa-a094-84b8d4f3e8ad"
    CHAR_ESTIM_B = "955a1505-0fe2-f5aa-a094-84b8d4f3e8ad"
    CHAR_ESTIM_A = "955a1506-0fe2-f5aa-a094-84b8d4f3e8ad"


async def scan_devices(timeout: float = 5.0) -> List[Tuple[str, int, str]]:
    """
    扫描周围的DG-LAB V2设备
    
    Args:
        timeout: 扫描超时时间（秒）
        
    Returns:
        List[Tuple[str, int, str]]: 设备列表，每项为(地址, RSSI强度, 设备名称)
    """
    logger.info(f"开始扫描DG-LAB V2设备，超时: {timeout}秒")
    
    devices = await BleakScanner.discover(return_adv=True)
    
    # 过滤出DG-LAB V2设备
    dglab_devices = []
    for device, adv_data in devices.values():
        if device.name and DeviceUUID.DEVICE_NAME_PREFIX in device.name:
            logger.info(f"找到设备: {device.name} ({device.address}), RSSI: {adv_data.rssi}")
            dglab_devices.append((device.address, adv_data.rssi, device.name))
    
    if not dglab_devices:
        logger.warning("未找到DG-LAB V2设备")
    else:
        logger.info(f"找到 {len(dglab_devices)} 个DG-LAB V2设备")
    
    return dglab_devices


async def get_battery_level(client: BleakClient) -> int:
    """
    获取设备电池电量
    
    Args:
        client: 已连接的BleakClient实例
        
    Returns:
        int: 电池电量百分比
    """
    value = await client.read_gatt_char(DeviceUUID.CHAR_BATTERY)
    battery_level = value[0]
    logger.debug(f"电池电量: {battery_level}%")
    return battery_level


async def get_strength(client: BleakClient) -> Tuple[int, int]:
    """
    获取设备当前强度
    
    Args:
        client: 已连接的BleakClient实例
        
    Returns:
        Tuple[int, int]: (通道A强度, 通道B强度)
    """
    try:
        value = await client.read_gatt_char(DeviceUUID.CHAR_ESTIM_POWER)
        
        # 获取原始字节
        array = bytes(value)
        logger.debug(f"读取强度原始字节: {array.hex()}")
        
        # 解码为24位整数
        raw_value = int.from_bytes(array[:3], byteorder="little")
        logger.debug(f"读取强度原始24位整数: {raw_value} (二进制: {bin(raw_value)})")
        
        # 从24位整数中提取两个强度值
        # 我们发现设备返回的是设置值的两倍，所以在这里除以2
        strength_a_raw = ((raw_value >> 11) & 0x7FF) // 2  # 取高13位再除以2
        strength_b_raw = (raw_value & 0x7FF) // 2  # 取低11位再除以2
        logger.debug(f"解析后的原始强度值(已调整): A={strength_a_raw} (二进制: {bin(strength_a_raw)}), B={strength_b_raw} (二进制: {bin(strength_b_raw)})")
        
        # 将设备范围(0-1023)转换为应用范围(0-100)
        channel_a = min(100, max(0, int(strength_a_raw * 100 / 1023)))
        channel_b = min(100, max(0, int(strength_b_raw * 100 / 1023)))
        
        logger.debug(f"当前强度: A={channel_a}, B={channel_b} (调整后原始值: A={strength_a_raw}, B={strength_b_raw})")
        return channel_a, channel_b
    except Exception as e:
        logger.error(f"获取强度错误: {e}")
        return 0, 0


async def set_strength(client: BleakClient, channel_a: int, channel_b: int) -> bool:
    """
    设置设备强度
    
    Args:
        client: 已连接的BleakClient实例
        channel_a: 通道A强度 (0-100)
        channel_b: 通道B强度 (0-100)
        
    Returns:
        bool: 设置是否成功
    """
    # 强度值限制在0-100范围内
    channel_a = max(0, min(100, channel_a))
    channel_b = max(0, min(100, channel_b))
    
    # 将0-100的强度值换算为设备原生的0-1023范围
    strength_a = int(channel_a * 1023 / 100)
    strength_b = int(channel_b * 1023 / 100)
    
    # 限制在有效范围内
    strength_a = min(1023, max(0, strength_a))
    strength_b = min(1023, max(0, strength_b))
    logger.debug(f"转换后的原始强度值: A={strength_a} (二进制: {bin(strength_a)}), B={strength_b} (二进制: {bin(strength_b)})")
    
    try:
        # 我们发现需要将值乘以2才能匹配设备读取的值
        strength_a = strength_a * 2
        strength_b = strength_b * 2
        logger.debug(f"调整后的原始强度值(已乘2): A={strength_a} (二进制: {bin(strength_a)}), B={strength_b} (二进制: {bin(strength_b)})")
        
        # 按照设备要求的格式打包数据
        # 使用位操作将两个强度值合并为一个24位的整数
        # 然后转换为3字节的little-endian格式
        combined_value = (strength_a << 11) + strength_b
        logger.debug(f"合并后的24位整数: {combined_value} (二进制: {bin(combined_value)})")
        
        array = combined_value.to_bytes(3, byteorder="little")
        
        logger.debug(f"设置强度原始字节: {array.hex()} (原始值: A={strength_a//2}, B={strength_b//2})")
        
        await client.write_gatt_char(
            DeviceUUID.CHAR_ESTIM_POWER, 
            bytearray(array),
            response=False
        )
        return True
    except Exception as e:
        logger.error(f"设置强度错误: {e}")
        return False


async def set_wave(
    client: BleakClient, 
    channel: str, 
    wave_x: int, 
    wave_y: int, 
    wave_z: int
) -> bool:
    """
    设置波形参数
    
    Args:
        client: 已连接的BleakClient实例
        channel: 通道 ('A' 或 'B')
        wave_x: 波形X参数 (0-31)
        wave_y: 波形Y参数 (0-1023)
        wave_z: 波形Z参数 (0-31)
        
    Returns:
        bool: 设置是否成功
    """
    # 参数值限制在合理范围内
    wave_x = max(0, min(31, wave_x))
    wave_y = max(0, min(1023, wave_y))
    wave_z = max(0, min(31, wave_z))
    
    try:
        # 使用位操作将三个波形参数合并为一个24位整数
        # Z参数在高8位，Y参数在中间10位，X参数在低5位
        value = ((wave_z << 15) + (wave_y << 5) + wave_x)
        array = value.to_bytes(3, byteorder="little")
        
    #    logger.debug(f"设置通道{channel}波形原始字节: {array.hex()}")
        
        # 根据通道选择特征UUID
        char_uuid = DeviceUUID.CHAR_ESTIM_A if channel == 'A' else DeviceUUID.CHAR_ESTIM_B
        
        await client.write_gatt_char(
            char_uuid, 
            bytearray(array),
            response=False
        )
        return True
    except Exception as e:
        logger.error(f"设置波形错误: {e}")
        return False 