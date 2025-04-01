# VRChat OSC 插件

本插件用于监听 VRChat 发送的 OSC 消息，并根据接收到的参数值控制 DG-LAB 设备的各项功能。

## 功能特性

- **OSC 参数监听**：接收 VRChat 发送的 OSC 参数
- **通配符匹配**：支持使用 `*` 匹配多个参数路径
- **多种工作模式**：
  - **距离模式**：根据参数值线性调整强度
  - **电击模式**：参数值超过阈值时触发电击
- **波形预设**：为不同模式自动选择合适的波形
- **参数映射**：将 OSC 参数值映射到设备强度范围
- **WebSocket 状态广播**：将状态信息推送到 WebUI

## 配置说明

配置文件位于 `plugins/vrchat_osc/config.yaml`，支持以下设置：

### OSC 服务器设置

```yaml
osc:
  listen_host: 127.0.0.1  # 监听地址
  listen_port: 9001       # 监听端口，与 VRChat 默认端口一致
```

### 通道配置

每个通道（A/B）可以独立配置：

```yaml
channel_a:
  # OSC 参数列表，支持通配符(*)匹配多个参数
  avatar_params:
    - "/avatar/parameters/pcs/contact/enterPass"    # 精确匹配
    - "/avatar/parameters/pcs/*"                    # 匹配所有 pcs 下的参数
  
  # 工作模式: distance(距离模式) 或 shock(电击模式)
  mode: "distance"
  
  # 强度限制 (0-100)
  strength_limit: 100
  
  # 触发范围设置
  trigger_range:
    bottom: 0.0  # 低于此值不触发
    top: 1.0     # 高于此值视为最大强度
```

### 波形预设配置

```yaml
wave_presets:
  # 每个通道的默认波形预设
  default_channel_a: "Pulse"
  default_channel_b: "Pulse"
  
  # 各模式使用的波形预设
  distance_mode: "Wave"    # 距离模式下使用的波形
  shock_mode: "Pulse"      # 电击模式下使用的波形
```

## 使用方法

1. 确保 VRChat 已正确配置为发送 OSC 消息：
   - 启用 OSC 功能
   - 设置发送地址为 `127.0.0.1`
   - 设置发送端口为 `9001`

2. 在 VRChat 中使用带有符合配置的 OSC 参数的头像
   - 参数名称需要匹配配置文件中的 `avatar_params`
   - 参数类型可以是浮点数、整数或布尔值

3. 根据使用场景调整配置：
   - 距离模式：适合连续渐变的场景，如按压、接近等
   - 电击模式：适合瞬时触发的场景，如点击、碰撞等

## 通配符匹配示例

本插件支持使用通配符 `*` 来匹配多个 OSC 参数：

```yaml
avatar_params:
  - "/avatar/parameters/*/Proximity"   # 匹配所有包含 Proximity 的参数
  - "/avatar/parameters/Touch/*"       # 匹配 Touch 目录下的所有参数
  - "*/Vibration"                      # 匹配任何以 Vibration 结尾的参数
```

## 工作模式详解

### 距离模式（Distance Mode）

- 将参数值线性映射到强度范围
- 适合表示距离、压力或进度的场景
- 参数值在 `bottom` 和 `top` 之间时，强度从 0 到 `strength_limit` 线性变化
- 使用 `distance_mode` 指定的波形预设

### 电击模式（Shock Mode）

- 参数值超过 `bottom` 阈值时触发固定强度的电击
- 电击强度为 `strength_limit` 指定的值
- 电击持续 2 秒后自动停止
- 使用 `shock_mode` 指定的波形预设

## 状态消息

通过 WebSocket 广播的状态消息格式：

```json
{
  "type": "plugin_vrchat_osc",
  "message": "通道A 距离: 0.75, 归一化: 0.75, 强度: 75"
}
```

## 错误排除

1. 如果 OSC 参数没有触发：
   - 确认 VRChat OSC 设置正确
   - 检查参数名称是否匹配
   - 使用 debug 模式启动服务：`python main.py --debug`

2. 如果设备反应不正确：
   - 检查波形预设配置
   - 确认工作模式配置符合需求
   - 调整触发范围设置

## VRChat参数参考

常用的参数：
- `/avatar/parameters/pcs/contact/enterPass` - PCS触发入口
- `/avatar/parameters/lms-penis-proximityA` - LMS触发

## 安全须知

请确保在使用前了解并遵守以下安全指南:

1. 设备的使用必须在设定的规格和参数范围内
2. 不要在以下情况使用:
   - 心脏问题或装有心脏起搏器
   - 怀孕期间
   - 癫痫病史
3. 避免在颈部以上区域使用

## 问题排查

- OSC消息未触发：请检查VRChat OSC设置和端口号
- 无法连接设备：确保DG-LAB设备已正确连接

## 技术细节

本插件基于以下技术:
- Python-OSC库处理OSC协议
- DG-LAB设备控制API 