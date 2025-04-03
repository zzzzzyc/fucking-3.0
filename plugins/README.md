# DG-LAB 插件系统

插件系统是DG-LAB设备控制服务的核心扩展机制，允许在不修改核心代码的情况下添加新功能。本目录包含所有可用的插件和插件加载器。

## 目录结构

```
plugins/
├── device_monitor/  # 设备监控插件
├── vrchat_osc/      # VRChat OSC集成插件
├── webui/           # Web用户界面插件
├── plugin_loader.py # 插件加载器
└── __init__.py
```

## 可用插件

### WebUI 插件

WebUI插件提供基于Web的用户界面，允许通过浏览器直观地控制DG-LAB设备。

#### 主要功能

- 直观的Web控制界面
- 实时设备状态和电池电量显示
- A/B通道的独立强度和波形控制
- 动态加载的波形预设选择
- 实时操作日志

#### 使用方法

1. 服务启动后，使用浏览器访问：`http://127.0.0.1:5000`
2. 使用"扫描设备"按钮连接DG-LAB设备
3. 通过界面控制设备强度和波形设置

### VRChat OSC 插件

VRChat OSC插件允许通过VRChat发送的OSC消息控制DG-LAB设备，实现与VR世界的互动。

#### 主要功能

- 接收VRChat发送的OSC消息
- 支持通配符(`*`)匹配多个参数路径
- 提供距离模式和电击模式两种工作模式
- 自动应用适合不同模式的波形预设
- 参数值到设备强度的智能映射

#### 配置文件

位于`plugins/vrchat_osc/config.yaml`：

```yaml
osc:
  listen_host: 127.0.0.1
  listen_port: 9001

channel_a:
  avatar_params:
    - "/avatar/parameters/pcs/contact/enterPass"
    - "/avatar/parameters/pcs/*"  # 通配符匹配
  mode: "distance"  # 或 "shock"
  strength_limit: 100
  trigger_range:
    bottom: 0.0
    top: 1.0

# channel_b配置类似...

wave_presets:
  default_channel_a: "Pulse"
  default_channel_b: "Pulse"
  distance_mode: "Wave"
  shock_mode: "Pulse"
```

#### 工作模式

1. **距离模式**：根据参数值线性调整强度，适合连续反馈
2. **电击模式**：参数值超过阈值时触发固定强度，适合瞬时反馈

### 设备监控插件

设备监控插件提供设备状态监控、自动重连和警告功能，增强系统稳定性。

#### 主要功能

- 定期检查设备连接状态
- 设备断开后自动尝试重连
- 电池低电量警告
- 状态信息广播到WebUI

#### 配置文件

位于`plugins/device_monitor/config.yaml`：

```yaml
monitor:
  check_interval: 30       # 状态检查间隔（秒）
  battery_warning: 20      # 电池电量警告阈值（百分比）
  auto_reconnect: true     # 是否启用自动重连
  reconnect_interval: 5    # 重连尝试间隔（秒）
  max_reconnect_attempts: 3 # 最大重连尝试次数
```

## 插件系统工作原理

DG-LAB的插件系统基于Python模块动态加载机制，通过`plugin_loader.py`实现插件的发现、加载和管理。

### 插件加载流程

1. 系统启动时，插件加载器扫描`plugins`目录
2. 对于每个包含`plugin.py`的子目录，尝试加载为插件
3. 检查插件是否符合接口要求（必须包含`setup`和`handle_message`函数）
4. 调用插件的`setup`函数进行初始化
5. 注册插件的消息处理函数到WebSocket服务器

### 插件通信机制

插件通过两种主要方式与系统交互：

1. **WebSocket服务器引用**：插件可以实现`set_ws_server`函数接收WebSocket服务器引用
2. **消息处理函数**：系统调用插件的`handle_message`函数处理WebSocket消息

## 开发新插件

### 插件结构

一个标准的DG-LAB插件应包含以下文件：

```
my_plugin/
├── plugin.py     # 插件主程序
├── config.yaml   # 配置文件（可选）
└── README.md     # 文档（推荐）
```

### 插件接口要求

每个插件的`plugin.py`必须实现以下函数：

1. **setup()**：
   - 初始化插件
   - 加载配置
   - 创建必要的资源

2. **async handle_message(websocket, message_data)**：
   - 处理WebSocket消息
   - 返回是否处理了消息

3. **set_ws_server(server)**（可选）：
   - 接收WebSocket服务器引用
   - 用于向所有客户端广播消息

4. **cleanup()**（可选）：
   - 清理插件资源
   - 释放连接
   - 停止线程或任务

### 插件模板示例

```python
"""
示例插件模板
"""

import logging
import os
import yaml
from typing import Dict, Any

# 设置日志
logger = logging.getLogger(__name__)

# 全局变量
ws_server = None
config = None

# 默认配置
DEFAULT_CONFIG = {
    "option": "value"
}

def set_ws_server(server):
    """设置WebSocket服务器引用"""
    global ws_server
    ws_server = server

async def load_config():
    """加载插件配置"""
    global config
    
    # 配置文件路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.yaml")
    
    # 尝试加载配置
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.info("已加载配置文件")
        except Exception as e:
            logger.error(f"加载配置失败: {str(e)}")
            config = DEFAULT_CONFIG.copy()
    else:
        config = DEFAULT_CONFIG.copy()
        # 创建默认配置文件
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False)
            logger.info("已创建默认配置文件")
        except Exception as e:
            logger.error(f"创建配置文件失败: {str(e)}")

def setup():
    """插件初始化函数"""
    # 加载配置
    import asyncio
    asyncio.create_task(load_config())
    
    logger.info("示例插件已初始化")

async def handle_message(websocket, message_data: Dict[str, Any]) -> bool:
    """
    处理WebSocket消息
    
    Args:
        websocket: WebSocket连接
        message_data: 消息数据
        
    Returns:
        bool: 消息是否被处理
    """
    # 检查消息是否由本插件处理
    if message_data.get("type") != "plugin_example":
        return False
        
    # 处理消息
    action = message_data.get("action")
    if action == "hello":
        # 回复消息
        await websocket.send(json.dumps({
            "type": "plugin_example_response",
            "message": "Hello from example plugin!"
        }))
        return True
        
    return False

def cleanup():
    """插件清理函数"""
    logger.info("示例插件已清理")
```

### 开发建议

1. **使用异步编程**：所有消息处理函数都应是异步函数
2. **错误处理**：捕获并记录所有异常，避免插件崩溃影响整个系统
3. **配置管理**：使用YAML格式的配置文件，提供默认配置
4. **资源清理**：在`cleanup`函数中释放所有资源
5. **文档**：创建详细的README.md说明插件功能和配置

## 常见问题

### 插件加载失败

可能原因：
- `setup`或`handle_message`函数缺失
- `handle_message`不是异步函数
- 插件代码语法错误
- 依赖库缺失

解决方法：
- 检查插件结构是否符合要求
- 使用调试模式启动程序获取详细错误信息
- 检查日志输出

### 插件无法与设备通信

可能原因：
- 设备未连接或连接不稳定
- 插件权限不足
- WebSocket服务器引用未正确设置

解决方法：
- 确保设备已正确连接
- 检查`set_ws_server`函数是否正确实现
- 确保在使用设备前检查设备状态 