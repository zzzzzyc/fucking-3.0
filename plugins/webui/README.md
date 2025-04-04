# WebUI 插件

本插件为DG-LAB设备控制服务提供Web用户界面，允许通过浏览器直接控制设备。

## 功能特性

- 直观的Web界面控制DG-LAB设备
- 实时显示设备状态和电池电量
- 独立控制A/B两个通道的强度和波形参数
- 内置多种波形预设
- 实时操作日志
- 自动重连WebSocket
- **插件扩展机制**：允许其他插件向WebUI添加自定义UI元素

## 使用方法

1. 启动DG-LAB设备控制服务时确保加载此插件：
   ```bash
   python main.py
   ```

2. 插件启动后，使用浏览器访问：
   ```
   http://127.0.0.1:5000
   ```

3. 通过界面连接设备并进行控制

## 波形参数说明

依据DG-LAB V2设备协议，波形控制模块使用X、Y、Z三个参数：

- **X参数**：范围0-31，连续X毫秒发出X个脉冲
- **Y参数**：范围0-1023，X个脉冲过后间隔Y毫秒再发出下一组脉冲
- **Z参数**：范围0-31，控制脉冲宽度，实际脉冲宽度为Z×5μs


## 预设波形

插件内置多种波形预设

## 插件扩展机制

WebUI插件现在支持扩展点机制，允许其他插件向用户界面添加自定义UI元素：

### 扩展点位置

- **头部扩展区域**（Header）：位于页面顶部
- **控制面板扩展区域**（Control Panel）：位于主控制面板下方
- **底部扩展区域**（Footer）：位于页面底部

### 使用方法

在其他插件中导入并使用`register_ui_extension`函数：

```python
try:
    from plugins.webui.plugin import register_ui_extension
except ImportError:
    register_ui_extension = None

def setup():
    if register_ui_extension:
        register_ui_extension(
            "control_panel",  # 扩展点位置："header", "control_panel", "footer"
            "my_extension",   # 扩展名称（唯一标识符）
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

### 扩展开发注意事项

1. 确保WebUI插件在您的插件之前加载
2. 使用适当的CSS类以保持风格一致（可参考`webui_pro`插件）
3. JavaScript代码可以使用WebUI已定义的函数，如`sendMessage()`和`logMessage()`

## 故障排除

1. 如果无法连接WebSocket，请确认：
   - 主服务正常运行
   - 防火墙未阻止连接
   - 主服务和WebUI地址设置正确

2. 如果无法找到设备：
   - 检查设备是否开启
   - 确认蓝牙连接正常
   - 使用"扫描设备"按钮重新扫描

3. 如果插件扩展不显示：
   - 确保扩展插件正确注册了UI元素
   - 检查插件加载顺序（WebUI插件必须先加载）
   - 查看控制台日志是否有错误信息

## 技术信息

- 使用aiohttp提供Web服务
- 使用WebSocket与主服务通信
- 使用原生JavaScript实现前端功能
- 支持插件扩展机制 