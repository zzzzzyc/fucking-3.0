"""
DG-LAB 设备数据模型定义
包含通道、设备状态等数据模型
"""

import os
import yaml
import logging
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass, field


# 设置日志
logger = logging.getLogger(__name__)


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
    
    # 默认波形预设，当配置文件不可用时使用
    DEFAULT_WAVE_PRESET = {
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
    
    # 从配置文件加载的波形预设
    WAVE_PRESET = {}
    
    @classmethod
    def load_wave_presets(cls):
        """从配置文件加载波形预设"""
        config_path = os.path.join(os.getcwd(), "waveconfig.yaml")
        
        # 如果配置文件存在，尝试加载
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                
                if config and "presets" in config:
                    # 转换YAML列表格式为元组格式
                    presets_dict = {}
                    for name, waves in config["presets"].items():
                        preset_waves = []
                        for wave in waves:
                            if isinstance(wave, list) and len(wave) == 3:
                                preset_waves.append(tuple(wave))
                        if preset_waves:
                            presets_dict[name] = preset_waves
                    
                    cls.WAVE_PRESET = presets_dict
                    logger.info(f"已从配置文件加载 {len(cls.WAVE_PRESET)} 个波形预设")
                    return
            except Exception as e:
                logger.error(f"加载波形预设配置失败: {str(e)}")
        
        # 如果加载失败或配置文件不存在，使用默认预设
        cls.WAVE_PRESET = cls.DEFAULT_WAVE_PRESET.copy()
        logger.info("使用默认波形预设")
        
        # 尝试创建默认配置文件
        if not os.path.exists(config_path):
            try:
                # 转换为YAML友好格式
                yaml_config = {"presets": {}}
                for name, waves in cls.DEFAULT_WAVE_PRESET.items():
                    yaml_config["presets"][name] = [list(wave) for wave in waves]
                
                with open(config_path, "w", encoding="utf-8") as f:
                    yaml.dump(yaml_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                logger.info(f"已创建默认波形预设配置文件: {config_path}")
            except Exception as e:
                logger.error(f"创建波形预设配置文件失败: {str(e)}")
    
    @classmethod
    def get_preset(cls, name: str) -> List[Tuple[int, int, int]]:
        """获取预设波形"""
        # 如果预设集合为空，先加载预设
        if not cls.WAVE_PRESET:
            cls.load_wave_presets()
        
        return cls.WAVE_PRESET.get(name, cls.WAVE_PRESET.get("Constant", [(8, 512, 15)]))
    
    @classmethod
    def get_preset_names(cls) -> List[str]:
        """获取所有预设波形名称"""
        # 如果预设集合为空，先加载预设
        if not cls.WAVE_PRESET:
            cls.load_wave_presets()
            
        return list(cls.WAVE_PRESET.keys()) 