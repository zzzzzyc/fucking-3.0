# DG-LAB 设备控制系统

这是一个用于控制 DG-LAB v2 设备的开源系统，支持蓝牙连接、多种工作模式和插件扩展。该项目使用Python编写，提供了强大的可扩展性和灵活的配置选项。

## 功能特性

- **蓝牙连接**：自动扫描、连接和管理 DG-LAB 设备
- **多通道控制**：独立控制设备的 A/B 通道，可分别设置强度和波形
- **波形预设系统**：提供多种可自定义波形预设，满足不同需求
- **WebSocket接口**：提供标准化的WebSocket通信接口，方便扩展和集成
- **插件系统**：支持功能扩展，目前包含以下插件：
  - **WebUI**：基于Web的用户界面，提供直观的设备控制，支持界面扩展
  - **高级控制面板**：扩展WebUI功能，添加高级波形控制选项
  - **VRChat OSC**：通过OSC协议接收VRChat参数控制设备，支持通配符匹配
  - **设备监控**：提供设备状态监控、自动重连和电池电量警告等功能

## 系统要求

- Python 3.8 或更高版本
- 支持蓝牙 4.0+ (BLE)
- DG-LAB V2 设备
- 操作系统：Windows 11(已测试) Windows 10 , macos , linux (理论上)

## 项目结构

```
dglab-control/
├── core/                # 核心功能模块
│   ├── bluetooth.py     # 蓝牙通信基础功能
│   ├── dglab_device.py  # DG-LAB设备控制类
│   └── models.py        # 数据模型和波形预设
├── plugins/             # 插件目录
│   ├── advanced_panel/  # 高级控制面板插件
│   ├── device_monitor/  # 设备监控插件
│   ├── vrchat_osc/      # VRChat OSC插件
│   ├── webui/           # Web用户界面插件
│   └── plugin_loader.py # 插件加载器
├── server/              # 服务器模块
│   └── ws_server.py     # WebSocket服务器
├── main.py              # 主程序入口
├── waveconfig.yaml      # 波形预设配置
└── requirements.txt     # 依赖项列表
```

## 快速开始

### 安装

1. 克隆仓库
```bash
git clone https://github.com/your-username/dglab-control.git
cd dglab-control
```

2. 安装依赖
```bash
python -m venv venv
# Windows
venv\\Scripts\\activate
# Linux/macOS
source venv/bin/activate
pip install -r requirements.txt
```

3. 启动程序
```bash
python main.py
```

### 命令行参数

程序支持多种命令行参数以自定义运行方式：

```bash
python main.py [options]

选项:
  --host HOST           指定WebSocket服务器监听地址 (默认: 127.0.0.1)
  --port PORT           指定WebSocket服务器监听端口 (默认: 8080)
  --device-address ADDR 直接连接指定地址的设备，跳过扫描
  --no-scan             禁用设备自动扫描
  --plugins-dir DIR     指定插件目录 (默认: plugins)
  --no-plugins          不加载任何插件
  --debug               启用调试日志
```

### 使用 WebUI

1. 启动程序后，打开浏览器访问 `http://localhost:5000`
2. 使用界面上的"扫描设备"按钮连接到 DG-LAB 设备
3. 通过控制面板调整强度和波形设置
4. 可以使用预设波形快速切换不同的模式

### 使用 VRChat OSC 插件

1. 确保 VRChat 已设置为发送 OSC 消息（默认使用端口 9001）
2. 在 VRChat 中使用带有 OSC 参数的avater
3. 通过配置文件 `plugins/vrchat_osc/config.yaml` 设置触发参数和行为模式
4. 插件将自动监听指定参数并根据配置控制设备

## 详细配置说明

### 波形预设配置 (waveconfig.yaml)

波形预设定义了设备的波形。每个预设包含一系列三元组 `[wave_x, wave_y, wave_z]`，设备会按顺序循环这些参数：

```yaml
presets:
  # 预设名称:
  Pulse:
    - [10, 600, 15]  # 第一组参数 [x, y, z]
    - [0, 0, 0]      # 第二组参数
  
  # 更多预设...
```

参数说明:
- **wave_x**: 波形宽度 (0-31)
- **wave_y**: 波形强度 (0-1023)
- **wave_z**: 波形频率 (0-31)
- **(应该是吧)(())

### WebUI 插件

WebUI 插件提供基于Web的设备控制界面，启动后可以通过浏览器访问。

#### 功能:
- 设备连接和断开
- 强度和波形参数调整
- 波形预设选择
- 设备状态监控
- 操作日志
- **插件扩展机制**：允许其他插件向WebUI添加自定义功能

默认访问地址: `http://localhost:5000`

#### WebUI 扩展机制

WebUI插件现在支持扩展点机制，允许其他插件向用户界面添加自定义元素：

1. **扩展点位置**:
   - 头部扩展区域（Header）：位于页面顶部
   - 控制面板扩展区域（Control Panel）：位于主控制面板下方
   - 底部扩展区域（Footer）：位于页面底部

2. **如何创建扩展插件**:
   ```python
   # 在自定义插件中添加
   from plugins.webui.plugin import register_ui_extension
   
   def setup():
       # 注册UI扩展
       register_ui_extension(
           "control_panel",  # 扩展点位置
           "my_extension",   # 扩展名称
           """
           <div class="my-ui-extension">
               <h3>我的扩展</h3>
               <!-- HTML内容 -->
           </div>
           """,
           """
           // JavaScript代码
           document.getElementById('my-button').addEventListener('click', function() {
               // 按钮点击逻辑
           });
           """
       )
   ```

3. **现有扩展示例**:
   - **高级控制面板**插件：添加了波形循环速度、混合模式等高级控制选项

### 高级控制面板插件

高级控制面板插件是WebUI扩展机制的示例实现，提供更高级的设备控制功能。

#### 功能:
- 波形循环速度调整
- 波形混合模式选择（顺序、混合、随机）
- A/B通道同步控制
- 帮助信息面板

### VRChat OSC 插件

VRChat OSC 插件能够接收来自 VRChat 的 OSC 消息并控制设备。

#### 配置文件 (plugins/vrchat_osc/config.yaml):

```yaml
osc:
  listen_host: 127.0.0.1
  listen_port: 9001

channel_a:
  # OSC 参数列表，支持通配符(*)
  avatar_params:
    - "/avatar/parameters/pcs/contact/enterPass"
    - "/avatar/parameters/pcs/*"  # 匹配所有 pcs 下的参数
  
  # 工作模式: distance(距离模式) 或 shock(电击模式)
  mode: "distance"
  
  # 强度限制 (0-100)
  strength_limit: 100
  
  # 触发范围
  trigger_range:
    bottom: 0.0  # 低于此值不触发
    top: 1.0     # 高于此值视为最大强度

# channel_b 配置类似...

wave_presets:
  # 默认波形预设
  default_channel_a: "Pulse"
  default_channel_b: "Pulse"
  
  # 各模式使用的预设
  distance_mode: "Wave"
  shock_mode: "Pulse"
```

#### 工作模式:

1. **距离模式 (distance)**:
   - 根据参数值线性调整强度
   - 参数从 bottom 到 top 对应强度从 0 到 strength_limit

2. **电击模式 (shock)**:
   - 参数值超过阈值时触发固定强度的电击
   - 触发后会自动恢复到 0

### 设备监控插件

设备监控插件提供自动化的设备状态监控功能。

#### 配置文件 (plugins/device_monitor/config.yaml):

```yaml
monitor:
  check_interval: 30       # 状态检查间隔（秒）
  battery_warning: 20      # 电池电量警告阈值（百分比）
  auto_reconnect: true     # 是否启用自动重连
  reconnect_interval: 5    # 重连尝试间隔（秒）
  max_reconnect_attempts: 3 # 最大重连尝试次数
```

#### 功能:
- 定期检查设备连接状态
- 断开时自动尝试重连
- 低电量警告
- 状态信息广播到 WebUI

## 开发计划

### 阶段一：核心功能完善（已完成）
- OSC 参数通配符支持
- 波形预设优化与外部配置
- 设备状态监控

### 阶段二：工作模式优化（进行中）
- 改进改进改进改进改进改进改进
- 修bug修bug修bug修bug修bug修bug
- 错误处理与日志完善
- 基本复现官方app功能

### 阶段三：UI与插件扩展（进行中）
- WebUI插件扩展机制
- 高级控制面板插件
- 更多自定义UI组件
- 扩展API完善

### 阶段四：（计划中）
- 优化优化优化优化优化优化优化
- 新功能新功能新功能新功能新功能新功能

## 开发插件

### 标准插件结构

要创建新插件，请遵循以下结构：

```
plugins/your_plugin/
├── plugin.py       # 主插件文件
└── README.md       # 插件文档
```

`plugin.py` 必须包含以下函数：

```python
def setup():
    """插件初始化函数"""
    pass

async def handle_message(websocket, message_data):
    """处理WebSocket消息"""
    return False  # 返回True表示消息已处理，False表示未处理

def cleanup():
    """插件清理函数"""
    pass
```

### 创建WebUI扩展

要向WebUI添加自定义功能，可以使用`register_ui_extension`函数：

```python
try:
    from plugins.webui.plugin import register_ui_extension
except ImportError:
    register_ui_extension = None

def setup():
    if register_ui_extension:
        register_ui_extension(
            extension_point,  # "header", "control_panel", "footer"
            name,            # 唯一标识符
            html_content,    # HTML内容
            js_content       # JavaScript代码（可选）
        )
```

## 故障排除

如遇到问题，请尝试：

1. 启用调试模式 `python main.py --debug`
2. 检查蓝牙连接状态，确保设备已开启并在范围内
3. 确认配置文件格式正确
4. 检查端口冲突，特别是 OSC 监听端口（默认 9001）
5. 查看日志输出以获取详细错误信息

常见问题：
- **设备无法连接**: 确保蓝牙已启用，设备已开启且电量充足
- **OSC 消息不触发**: 检查 VRChat OSC 设置和插件配置中的参数路径是否匹配
- **WebUI 无法访问**: 检查防火墙设置，确保端口 5000 未被占用
- **插件加载失败**: 检查插件结构和必要函数是否正确实现

## 贡献

欢迎加我qq：3058073254 或发issue与pr
人手紧缺 目前为面向cursor编程 来人救一下啊（）这么伟大的省钱项目（

## 许可

[MIT 许可证](LICENSE) 