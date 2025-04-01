# 设备监控插件

本插件提供设备状态监控功能，包括设备连接状态检查、自动重连和电池电量监控。

## 功能特性

- 定期检查设备状态
- 设备断开连接自动重连
- 电池低电量警告
- 状态日志记录
- 可配置的监控参数

## 配置说明

配置文件 `config.yaml` 包含以下设置：

```yaml
monitor:
  check_interval: 30      # 状态检查间隔（秒）
  battery_warning: 20     # 电池电量警告阈值（百分比）
  auto_reconnect: true    # 是否启用自动重连
  reconnect_interval: 5   # 重连尝试间隔（秒）
  max_reconnect_attempts: 3 # 最大重连尝试次数
```

## 使用方法

1. 插件会自动加载并开始监控设备状态
2. 状态更新会通过WebSocket广播到所有连接的客户端
3. 当发生以下情况时会收到通知：
   - 设备断开连接
   - 设备重新连接
   - 电池电量低于警告阈值
   - 重连失败

## 状态消息格式

插件发送的状态消息格式如下：

```json
{
    "type": "plugin_device_monitor",
    "message": "状态描述",
    "timestamp": "2024-01-01T12:00:00.000Z"
}
```

## 故障排除

1. 如果设备频繁断开连接：
   - 检查蓝牙连接是否稳定
   - 调整 `check_interval` 和 `reconnect_interval`
   - 增加 `max_reconnect_attempts`

2. 如果收到过多电池警告：
   - 调整 `battery_warning` 阈值
   - 增加 `check_interval`

3. 如果状态更新不及时：
   - 减少 `check_interval` 值
   - 检查系统日志中的错误信息 