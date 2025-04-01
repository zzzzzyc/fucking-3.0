# DG-LAB 设备控制系统

这是一个用于控制 DG-LAB v2 设备的开源系统，支持蓝牙连接、多种工作模式和插件扩展。

## 功能特性

- **蓝牙连接**：自动扫描、连接和管理 DG-LAB 设备
- **多通道控制**：独立控制设备的 A/B 通道
- **波形预设**：提供多种波形预设，满足不同需求
- **插件系统**：支持功能扩展，包括：
  - WebUI：基于网页的控制界面
  - VRChat OSC：通过 OSC 协议接收 VRChat 参数控制设备
  - device_monitor：被从core赶出来的小功能
  - 更多插件正在开发中...

## 系统要求

- Python 3.8 或更高版本
- 支持蓝牙 4.0+ (BLE)
- DG-LAB V2 设备
- 我不造啊

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
venv\\scripts\\activate
pip install -r requirements.txt
```

3. 启动程序
```bash
venv\\scripts\\activate
python main.py
```

### 使用 WebUI

1. 启动程序后，打开浏览器访问 `http://localhost:8080`
2. 使用界面上的"扫描设备"按钮连接到 DG-LAB 设备
3. 通过控制面板调整强度和波形设置

### 使用 VRChat OSC 插件

1. 确保 VRChat 已设置为发送 OSC 消息（端口 9001）
2. 在 VRChat 中使用带有 OSC 参数的头像
3. 通过配置文件 `plugins/vrchat_osc/config.yaml` 设置触发参数和行为模式

## 配置

主要配置文件位于各插件目录下：

- WebUI 插件：`plugins/webui/config.yaml`
- VRChat OSC 插件：`plugins/vrchat_osc/config.yaml`

## 插件

### WebUI 插件

提供基于 Web 的控制界面，包括设备连接、强度控制、波形设置等功能。

### VRChat OSC 插件

监听 VRChat 发送的 OSC 消息，根据参数值控制设备行为。支持：

- **距离模式**：根据参数值线性调整强度
- **电击模式**：参数超过阈值时触发固定强度的电击
- **通配符匹配**：支持 `*` 匹配多个参数
- **波形预设**：为不同模式配置专用波形

## 开发计划

### 阶段一：核心功能完善（已完成）
- OSC 参数通配符支持
- 波形预设优化
- 设备状态监控

### 阶段二：工作模式优化（进行中）
- 距离模式改进（响应曲线、多参数聚合）
- 电击模式改进（可配置持续时间、冷却期）
- 错误处理与日志完善

### 阶段三：UI 集成
- 配置界面优化
- 数据可视化
- 高级控制面板

## 故障排除

如遇到问题，请尝试：

1. 启用调试模式 `python main.py --debug`
2. 检查蓝牙连接状态
3. 确认配置文件格式正确
4. 查看日志文件 `logs/dglab.log`

## 贡献

欢迎加我qq：3058073254 或发issue与pr
人手紧缺 目前为面向cursor编程 来人救一下啊（）这么伟大的省钱项目（

## 许可

[MIT 许可证](LICENSE) 