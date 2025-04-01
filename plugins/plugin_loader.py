"""
DG-LAB 插件加载器
负责发现、加载和管理插件
"""

import asyncio
import importlib
import importlib.util
import inspect
import logging
import os
import sys
from typing import Dict, List, Any, Optional, Callable

from server.ws_server import DGLabWebSocketServer

# 设置日志
logger = logging.getLogger(__name__)


class PluginLoader:
    """DG-LAB 插件加载器"""
    
    def __init__(self, server: DGLabWebSocketServer, plugins_dir: str = "plugins"):
        """
        初始化插件加载器
        
        Args:
            server: WebSocket服务器实例
            plugins_dir: 插件目录路径
        """
        self.server = server
        self.plugins_dir = plugins_dir
        self.loaded_plugins: Dict[str, Any] = {}
    
    def discover_plugins(self) -> List[str]:
        """
        发现可用插件
        
        Returns:
            List[str]: 发现的插件模块名称列表
        """
        plugin_modules = []
        
        # 获取plugins目录下的所有目录（每个目录是一个插件）
        try:
            items = os.listdir(self.plugins_dir)
            for item in items:
                plugin_dir = os.path.join(self.plugins_dir, item)
                
                # 检查是否是目录
                if os.path.isdir(plugin_dir):
                    # 检查是否有plugin.py文件
                    plugin_file = os.path.join(plugin_dir, "plugin.py")
                    if os.path.isfile(plugin_file):
                        plugin_modules.append(item)
        except Exception as e:
            logger.error(f"发现插件时出错: {e}")
        
        logger.info(f"发现 {len(plugin_modules)} 个插件: {', '.join(plugin_modules)}")
        return plugin_modules
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        加载单个插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 加载是否成功
        """
        if plugin_name in self.loaded_plugins:
            logger.warning(f"插件 {plugin_name} 已加载")
            return True
        
        try:
            # 构建插件模块路径
            plugin_dir = os.path.join(self.plugins_dir, plugin_name)
            plugin_file = os.path.join(plugin_dir, "plugin.py")
            
            # 检查插件文件是否存在
            if not os.path.isfile(plugin_file):
                logger.error(f"插件 {plugin_name} 的plugin.py文件不存在")
                return False
            
            # 加载插件模块
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_name}.plugin", 
                plugin_file
            )
            
            if spec is None or spec.loader is None:
                logger.error(f"无法加载插件 {plugin_name} 的规范")
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # 检查插件是否有必要的属性和方法
            if not hasattr(module, "setup") or not callable(module.setup):
                logger.error(f"插件 {plugin_name} 缺少setup函数")
                return False
            
            if not hasattr(module, "handle_message") or not callable(module.handle_message):
                logger.error(f"插件 {plugin_name} 缺少handle_message函数")
                return False
            
            # 检查handle_message是否为异步函数
            if not inspect.iscoroutinefunction(module.handle_message):
                logger.error(f"插件 {plugin_name} 的handle_message不是异步函数")
                return False
            
            # 检查是否有set_ws_server方法，如果有则注入WebSocket服务器引用
            if hasattr(module, "set_ws_server") and callable(module.set_ws_server):
                module.set_ws_server(self.server)
                logger.info(f"插件 {plugin_name} 注入WebSocket服务器引用")
            
            # 调用插件的setup函数
            module.setup()
            
            # 注册插件的消息处理函数
            self.server.register_plugin(plugin_name, module.handle_message)
            
            # 存储已加载的插件
            self.loaded_plugins[plugin_name] = module
            
            logger.info(f"插件 {plugin_name} 加载成功")
            return True
            
        except Exception as e:
            logger.error(f"加载插件 {plugin_name} 时出错: {e}")
            return False
    
    def load_all_plugins(self) -> Dict[str, bool]:
        """
        加载所有发现的插件
        
        Returns:
            Dict[str, bool]: 插件加载结果字典，键为插件名称，值为是否加载成功
        """
        plugins = self.discover_plugins()
        results = {}
        
        for plugin_name in plugins:
            results[plugin_name] = self.load_plugin(plugin_name)
        
        return results
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 卸载是否成功
        """
        if plugin_name not in self.loaded_plugins:
            logger.warning(f"插件 {plugin_name} 未加载")
            return False
        
        try:
            # 调用插件的cleanup函数（如果有）
            module = self.loaded_plugins[plugin_name]
            if hasattr(module, "cleanup") and callable(module.cleanup):
                module.cleanup()
            
            # 从加载的插件列表中删除
            del self.loaded_plugins[plugin_name]
            
            # 从服务器的插件注册中删除
            if plugin_name in self.server.plugins:
                del self.server.plugins[plugin_name]
            
            logger.info(f"插件 {plugin_name} 卸载成功")
            return True
            
        except Exception as e:
            logger.error(f"卸载插件 {plugin_name} 时出错: {e}")
            return False
    
    def unload_all_plugins(self) -> None:
        """卸载所有插件"""
        plugin_names = list(self.loaded_plugins.keys())
        
        for plugin_name in plugin_names:
            self.unload_plugin(plugin_name)
    
    def create_plugin_template(self, plugin_name: str) -> bool:
        """
        创建插件模板
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            bool: 创建是否成功
        """
        try:
            # 创建插件目录
            plugin_dir = os.path.join(self.plugins_dir, plugin_name)
            if os.path.exists(plugin_dir):
                logger.error(f"插件目录 {plugin_dir} 已存在")
                return False
            
            os.makedirs(plugin_dir)
            
            # 创建插件文件
            plugin_file = os.path.join(plugin_dir, "plugin.py")
            with open(plugin_file, "w", encoding="utf-8") as f:
                f.write(f'''"""
{plugin_name} 插件
描述：这是一个示例插件模板
"""

import logging
from typing import Dict, Any

# 设置日志
logger = logging.getLogger(__name__)


def setup() -> None:
    """
    插件初始化函数
    在插件被加载时调用
    """
    logger.info("{plugin_name} 插件已初始化")


async def handle_message(device, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理WebSocket消息
    
    Args:
        device: DGLabDevice实例
        data: 消息数据
        
    Returns:
        Dict[str, Any]: 处理结果
    """
    # 在这里实现您的插件逻辑
    logger.info(f"收到消息: {{data}}")
    
    # 返回处理结果
    return {{"status": "success"}}


def cleanup() -> None:
    """
    插件清理函数
    在插件被卸载时调用
    """
    logger.info("{plugin_name} 插件已清理")
''')
            
            # 创建README.md
            readme_file = os.path.join(plugin_dir, "README.md")
            with open(readme_file, "w", encoding="utf-8") as f:
                f.write(f'''# {plugin_name} 插件

## 描述
这是一个DG-LAB设备控制插件

## 使用方法
1. 确保插件已加载
2. 通过WebSocket发送以下格式的消息:

```json
{{
  "type": "plugin_{plugin_name}",
  "action": "your_action",
  "params": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}
```

## 支持的操作
- 操作1：描述
- 操作2：描述

## 版本历史
- 1.0.0: 初始版本
''')
            
            logger.info(f"插件模板 {plugin_name} 创建成功")
            return True
            
        except Exception as e:
            logger.error(f"创建插件模板 {plugin_name} 时出错: {e}")
            return False 