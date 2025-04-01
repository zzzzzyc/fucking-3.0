"""
DG-LAB 设备控制核心模块
负责与DG-LAB V2设备进行蓝牙通信
"""

from .dglab_device import DGLabDevice
from .models import ChannelA, ChannelB, WaveSet

__all__ = ['DGLabDevice', 'ChannelA', 'ChannelB', 'WaveSet'] 