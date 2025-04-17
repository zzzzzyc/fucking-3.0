# DG-LAB HTTP API 插件

该插件提供了一个 HTTP 接口，用于控制已连接的 DG-LAB 设备。
其实现基于 `webui` 插件中观察到的交互模式。

## 配置

插件的行为可以在 `plugins/http_api/config.yaml` 文件中配置：

```yaml
http_api:
  host: "127.0.0.1"  # 服务器监听的 IP 地址或主机名
  port: 8081         # 服务器监听的端口
```

请确保指定的端口未被其他应用程序占用（例如，WebUI 插件通常使用端口 5000）。

## API 端点

当插件加载且服务器运行后，以下端点可用：

### 获取设备状态

- **URL:** `/status`
- **方法:** `GET`
- **描述:** 获取已连接设备的当前状态 (使用 `device.get_state()`)。
- **成功响应 (200 OK):** 具体结构取决于 `device.get_state()` 的返回，但可能类似于：
  ```json
  {
    "connected": true,
    "battery": 85,
    "channel_a": {
      "strength": 50,
      "wave": [10, 600, 15],
      "preset": "Pulse"
    },
    "channel_b": {
      "strength": 60,
      "wave": [5, 500, 10],
      "preset": "Wave"
    }
    // ... 其他状态字段
  }
  ```
- **错误响应 (404 Not Found):** 如果设备未连接。
  ```json
  {
    "error": "Device not connected"
  }
  ```
- **错误响应 (500 Internal Server Error):** 如果获取状态时出错。
  ```json
  {
    "error": "Failed to get device state"
  }
  ```

### 设置通道强度

- **URL:** `/control/strength`
- **方法:** `POST`
- **描述:** 设置指定通道的强度 (使用 `device.set_strength()`)。插件内部会自动获取另一个通道的当前强度，以向设备发送完整的命令。
- **请求体 (JSON):**
  ```json
  {
    "channel": "a",     // 或 "b"
    "strength": 75     // 0 到 100 之间的整数
  }
  ```
- **成功响应 (200 OK):**
  ```json
  {
    "status": "success",
    "channel": "a",
    "strength": 75 // 反映了为指定通道设置的强度值
  }
  ```
- **错误响应 (400 Bad Request):** 如果参数缺失、无效或 JSON 格式错误。
- **错误响应 (404 Not Found):** 如果设备未连接。
- **错误响应 (500 Internal Server Error):** 如果命令在设备端执行失败，或获取当前状态失败。

### 设置通道波形预设

- **URL:** `/control/waveform`
- **方法:** `POST`
- **描述:** 使用预设名称设置指定通道的波形 (尝试使用 `device.set_waveform_preset()`)。
- **请求体 (JSON):**
  ```json
  {
    "channel": "b",        // 或 "a"
    "preset": "Rumble"    // 有效波形预设的名称 (字符串)
  }
  ```
- **成功响应 (200 OK):**
  ```json
  {
    "status": "success",
    "channel": "b",
    "preset": "Rumble"
  }
  ```
- **错误响应 (400 Bad Request):** 如果参数缺失、无效或 JSON 格式错误。
- **错误响应 (404 Not Found):** 如果设备未连接。
- **错误响应 (501 Not Implemented):** 如果设备对象没有 `set_waveform_preset` 方法。
- **错误响应 (500 Internal Server Error):** 如果命令执行失败（例如，设备端预设名称无效，或其他设备错误）。

## 使用示例 (使用 curl)

```bash
# 获取状态
curl http://127.0.0.1:8081/status

# 设置通道 A 强度为 50
curl -X POST -H "Content-Type: application/json" -d '{"channel": "a", "strength": 50}' http://127.0.0.1:8081/control/strength

# 设置通道 B 波形为 "Pulse" 预设
curl -X POST -H "Content-Type: application/json" -d '{"channel": "b", "preset": "Pulse"}' http://127.0.0.1:8081/control/waveform
