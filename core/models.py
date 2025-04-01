"""
DG-LAB 设备数据模型定义
包含通道、设备状态等数据模型
"""

from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass, field


@dataclass
class ChannelA:
    """A通道数据模型"""
    strength: int = 0
    wave_x: int = 0
    wave_y: int = 0  
    wave_z: int = 0

    @property
    def wave(self) -> Tuple[int, int, int]:
        """获取波形参数元组"""
        return (self.wave_x, self.wave_y, self.wave_z)
    
    @wave.setter
    def wave(self, value: Tuple[int, int, int]):
        """设置波形参数"""
        self.wave_x, self.wave_y, self.wave_z = value


@dataclass
class ChannelB:
    """B通道数据模型"""
    strength: int = 0
    wave_x: int = 0
    wave_y: int = 0
    wave_z: int = 0
    
    @property
    def wave(self) -> Tuple[int, int, int]:
        """获取波形参数元组"""
        return (self.wave_x, self.wave_y, self.wave_z)
    
    @wave.setter
    def wave(self, value: Tuple[int, int, int]):
        """设置波形参数"""
        self.wave_x, self.wave_y, self.wave_z = value


@dataclass
class DGLabState:
    """DG-LAB设备状态数据模型"""
    channel_a: ChannelA = field(default_factory=ChannelA)
    channel_b: ChannelB = field(default_factory=ChannelB)
    battery: int = 0
    connected: bool = False
    device_address: str = ""


# 默认波形预设
class WaveSet:
    """波形预设集合"""
    
    WAVE_PRESET = {
        "Going_Faster": [
            (5, 135, 20),
            (5, 125, 20),
            (5, 115, 20),
            (5, 105, 20),
            (5, 95, 20),
            (4, 86, 20),
            (4, 76, 20),
            (4, 66, 20),
            (3, 57, 20),
            (3, 47, 20),
            (3, 37, 20),
            (2, 28, 20),
            (2, 18, 20),
            (1, 14, 20),
            (1, 9, 20),
        ],
        "Constant": [
            (8, 512, 15),
        ],
        "Pulse": [
            (10, 600, 15),
            (0, 0, 0),
        ],
        "Wave": [
            (5, 200, 10),
            (8, 300, 15),
            (12, 400, 20),
            (15, 500, 25),
            (12, 400, 20),
            (8, 300, 15),
        ],
        "Intense": [
            (15, 700, 25),
            (20, 800, 30),
            (25, 900, 30),
            (20, 800, 30),
            (15, 700, 25),
            (0, 0, 0),
        ],
        "Rhythm": [
            (15, 600, 20),
            (0, 0, 0),
            (15, 600, 20),
            (0, 0, 0),
            (15, 600, 20),
            (0, 0, 0),
        ],
    }
    
    @classmethod
    def get_preset(cls, name: str) -> List[Tuple[int, int, int]]:
        """获取预设波形"""
        return cls.WAVE_PRESET.get(name, cls.WAVE_PRESET["Constant"])
    
    @classmethod
    def get_preset_names(cls) -> List[str]:
        """获取所有预设波形名称"""
        return list(cls.WAVE_PRESET.keys()) 