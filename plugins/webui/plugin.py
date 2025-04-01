"""
WebUI 插件
提供Web用户界面控制DG-LAB设备
"""

import os
import asyncio
import logging
import threading
import json
from aiohttp import web
from pathlib import Path

# 设置日志
logger = logging.getLogger(__name__)

# 存储WebSocket服务器引用
ws_server = None

class WebUI:
    """WebUI 插件类"""
    
    def __init__(self, host="127.0.0.1", port=5000):
        """
        初始化WebUI
        
        Args:
            host: Web服务器主机地址
            port: Web服务器端口
        """
        self.host = host
        self.port = port
        self.app = web.Application()
        self.setup_routes()
        self.runner = None
        self.site = None
        self.thread = None
        self.running = False
    
    def setup_routes(self):
        """设置Web路由"""
        # 静态文件目录
        static_path = Path(__file__).parent / "static"
        if not static_path.exists():
            static_path.mkdir()
        
        # 设置路由
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/api/config", self.handle_config)
        self.app.router.add_static("/static", static_path)
    
    async def handle_index(self, request):
        """处理主页请求"""
        with open(Path(__file__).parent / "static" / "index.html", encoding="utf-8") as f:
            content = f.read()
        
        # 替换占位符
        content = content.replace("{{WS_HOST}}", ws_server.host)
        content = content.replace("{{WS_PORT}}", str(ws_server.port))
        
        return web.Response(text=content, content_type="text/html")
    
    async def handle_config(self, request):
        """处理配置API请求"""
        config = {
            "ws_host": ws_server.host,
            "ws_port": ws_server.port,
            "device_connected": ws_server.device is not None and ws_server.device.is_connected
        }
        return web.json_response(config)
    
    async def start_server(self):
        """启动Web服务器"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            logger.info(f"WebUI服务器已启动: http://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"启动WebUI服务器失败: {e}")
            raise
    
    async def stop_server(self):
        """停止Web服务器"""
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
            self.site = None
            logger.info("WebUI服务器已停止")
    
    def run_in_thread(self):
        """在线程中运行Web服务器"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.start_server())
            self.running = True
            loop.run_forever()
        except Exception as e:
            logger.error(f"WebUI服务器线程错误: {e}")
        finally:
            loop.run_until_complete(self.stop_server())
            loop.close()
            self.running = False
    
    def start(self):
        """启动WebUI服务"""
        if self.running:
            logger.warning("WebUI服务器已在运行")
            return
        
        self.thread = threading.Thread(target=self.run_in_thread)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """停止WebUI服务"""
        if not self.running:
            return
        
        # 获取线程的事件循环并调用停止
        if self.thread and self.thread.is_alive():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.stop_server())
            loop.close()
            
            # 等待线程结束
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                logger.warning("WebUI线程未能正常结束")
            
            self.thread = None

# 全局WebUI实例
webui_instance = None

def setup():
    """插件设置函数，加载插件时调用"""
    global webui_instance
    
    try:
        # 创建静态目录和HTML文件
        create_static_files()
        
        # 创建并启动WebUI
        webui_instance = WebUI()
        webui_instance.start()
        
        logger.info("WebUI插件已加载")
    except Exception as e:
        logger.error(f"WebUI插件加载失败: {e}")
        raise

def cleanup():
    """插件清理函数，卸载插件时调用"""
    global webui_instance
    
    if webui_instance:
        webui_instance.stop()
        webui_instance = None
        logger.info("WebUI插件已卸载")

async def handle_message(websocket, message_data):
    """
    处理WebSocket消息
    
    Args:
        websocket: WebSocket连接
        message_data: 消息数据
        
    Returns:
        bool: 消息是否被处理
    """
    # 这里我们不处理任何消息，只是将WebUI作为前端展示
    return False

def create_static_files():
    """创建静态文件"""
    # 创建静态文件目录
    static_path = Path(__file__).parent / "static"
    if not static_path.exists():
        static_path.mkdir()
    
    # 创建index.html
    index_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DG-LAB 设备控制</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <h1>DG-LAB 设备控制面板</h1>
        
        <div class="status-panel">
            <div id="connection-status" class="status-indicator">
                <span class="status-dot disconnected"></span>
                <span class="status-text">WebSocket: 未连接</span>
            </div>
            <div id="device-status" class="status-indicator">
                <span class="status-dot disconnected"></span>
                <span class="status-text">设备: 未连接</span>
            </div>
            <div id="battery-status" class="status-indicator">
                <span class="status-text">电量: --</span>
            </div>
        </div>
        
        <div class="control-panel">
            <div class="channel-controls">
                <div class="channel">
                    <h2>通道 A</h2>
                    <div class="strength-control">
                        <label for="strength-a">强度</label>
                        <input type="range" id="strength-a" min="0" max="100" value="0">
                        <span id="strength-a-value">0</span>
                    </div>
                    
                    <div class="wave-control">
                        <h3>波形参数</h3>
                        <div class="wave-params">
                            <div>
                                <label for="wave-a-x">X</label>
                                <input type="range" id="wave-a-x" min="0" max="31" value="5">
                                <span id="wave-a-x-value">5</span>
                            </div>
                            <div>
                                <label for="wave-a-y">Y</label>
                                <input type="range" id="wave-a-y" min="0" max="1023" value="95">
                                <span id="wave-a-y-value">95</span>
                            </div>
                            <div>
                                <label for="wave-a-z">Z</label>
                                <input type="range" id="wave-a-z" min="0" max="31" value="20">
                                <span id="wave-a-z-value">20</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="presets">
                        <h3>预设波形</h3>
                        <div class="preset-buttons">
                            <button class="preset-btn" data-channel="A" data-preset="Smooth">平滑</button>
                            <button class="preset-btn" data-channel="A" data-preset="Going_Faster">加速</button>
                            <button class="preset-btn" data-channel="A" data-preset="Waves">波浪</button>
                            <button class="preset-btn" data-channel="A" data-preset="Intense">强烈</button>
                        </div>
                    </div>
                </div>
                
                <div class="channel">
                    <h2>通道 B</h2>
                    <div class="strength-control">
                        <label for="strength-b">强度</label>
                        <input type="range" id="strength-b" min="0" max="100" value="0">
                        <span id="strength-b-value">0</span>
                    </div>
                    
                    <div class="wave-control">
                        <h3>波形参数</h3>
                        <div class="wave-params">
                            <div>
                                <label for="wave-b-x">X</label>
                                <input type="range" id="wave-b-x" min="0" max="31" value="5">
                                <span id="wave-b-x-value">5</span>
                            </div>
                            <div>
                                <label for="wave-b-y">Y</label>
                                <input type="range" id="wave-b-y" min="0" max="1023" value="95">
                                <span id="wave-b-y-value">95</span>
                            </div>
                            <div>
                                <label for="wave-b-z">Z</label>
                                <input type="range" id="wave-b-z" min="0" max="31" value="20">
                                <span id="wave-b-z-value">20</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="presets">
                        <h3>预设波形</h3>
                        <div class="preset-buttons">
                            <button class="preset-btn" data-channel="B" data-preset="Smooth">平滑</button>
                            <button class="preset-btn" data-channel="B" data-preset="Going_Faster">加速</button>
                            <button class="preset-btn" data-channel="B" data-preset="Waves">波浪</button>
                            <button class="preset-btn" data-channel="B" data-preset="Intense">强烈</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="device-controls">
                <button id="scan-btn">扫描设备</button>
                <button id="disconnect-btn">断开连接</button>
            </div>
            
            <div class="manual-connect">
                <h3>手动连接设备</h3>
                <div class="manual-connect-form">
                    <input type="text" id="device-address" placeholder="输入设备蓝牙地址" />
                    <button id="manual-connect-btn">连接</button>
                </div>
                <p class="hint">设备地址格式示例: XX:XX:XX:XX:XX:XX</p>
            </div>
        </div>
        
        <div class="log-panel">
            <h3>日志</h3>
            <div id="log-content"></div>
        </div>
    </div>
    
    <script>
        // WebSocket配置
        const wsHost = '{{WS_HOST}}';
        const wsPort = '{{WS_PORT}}';
        const wsUrl = `ws://${wsHost}:${wsPort}`;
        
        let ws = null;
        let reconnectTimer = null;
        let deviceConnected = false;
        let lastState = {};
        
        // 初始化函数
        function init() {
            connectWebSocket();
            setupEventListeners();
        }
        
        // 连接WebSocket
        function connectWebSocket() {
            if (ws) {
                ws.close();
            }
            
            logMessage('正在连接WebSocket...');
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                logMessage('WebSocket连接成功');
                updateConnectionStatus(true);
                clearInterval(reconnectTimer);
                
                // 获取初始状态
                sendMessage({ type: 'get_state' });
            };
            
            ws.onclose = () => {
                logMessage('WebSocket连接断开');
                updateConnectionStatus(false);
                updateDeviceStatus(false);
                
                // 自动重连
                if (!reconnectTimer) {
                    reconnectTimer = setInterval(() => {
                        logMessage('尝试重新连接...');
                        connectWebSocket();
                    }, 5000);
                }
            };
            
            ws.onerror = (error) => {
                logMessage(`WebSocket错误: ${error.message}`);
            };
            
            ws.onmessage = (event) => {
                try {
                    // 将接收到的内容记录到日志
                    logMessage(`收到WebSocket消息: ${event.data.substring(0, 100)}${event.data.length > 100 ? '...' : ''}`);
                    
                    const data = JSON.parse(event.data);
                    handleMessage(data);
                } catch (e) {
                    logMessage(`消息解析错误: ${e.message}`);
                }
            };
        }
        
        // 发送消息
        function sendMessage(data) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(data));
            } else {
                logMessage('WebSocket未连接，无法发送消息');
            }
        }
        
        // 处理接收的消息
        function handleMessage(data) {
            if (data.type === 'state') {
                lastState = data;
                
                // 检查数据格式
                if (data.data) {
                    // 如果状态在data子对象中
                    const stateData = data.data;
                    updateDeviceStatus(stateData.connected);
                    updateBatteryStatus(stateData.battery);
                    
                    if (stateData.channel_a) {
                        updateStrengthValues(
                            stateData.channel_a.strength || 0, 
                            stateData.channel_b?.strength || 0
                        );
                        
                        // 检查波形数据的格式
                        if (Array.isArray(stateData.channel_a.wave) && stateData.channel_a.wave.length >= 3) {
                            updateWaveParams('A', stateData.channel_a.wave[0], stateData.channel_a.wave[1], stateData.channel_a.wave[2]);
                        } else {
                            updateWaveParams(
                                'A',
                                stateData.channel_a.wave_x || 0,
                                stateData.channel_a.wave_y || 0,
                                stateData.channel_a.wave_z || 0
                            );
                        }
                        
                        if (stateData.channel_b && Array.isArray(stateData.channel_b.wave) && stateData.channel_b.wave.length >= 3) {
                            updateWaveParams('B', stateData.channel_b.wave[0], stateData.channel_b.wave[1], stateData.channel_b.wave[2]);
                        } else if (stateData.channel_b) {
                            updateWaveParams(
                                'B',
                                stateData.channel_b.wave_x || 0,
                                stateData.channel_b.wave_y || 0,
                                stateData.channel_b.wave_z || 0
                            );
                        }
                    }
                } else {
                    // 直接使用data对象
                    updateDeviceStatus(data.connected);
                    updateBatteryStatus(data.battery);
                    updateStrengthValues(data.channel_a?.strength || 0, data.channel_b?.strength || 0);
                    updateWaveParams(
                        'A', 
                        data.channel_a?.wave_x || 0, 
                        data.channel_a?.wave_y || 0, 
                        data.channel_a?.wave_z || 0
                    );
                    updateWaveParams(
                        'B', 
                        data.channel_b?.wave_x || 0, 
                        data.channel_b?.wave_y || 0, 
                        data.channel_b?.wave_z || 0
                    );
                }
                
                // 记录状态日志
                logMessage(`设备状态: ${data.data?.connected || data.connected ? '已连接' : '未连接'}`);
            } else if (data.type === 'error') {
                logMessage(`错误: ${data.message}`);
            } else {
                // 记录其他类型消息
                logMessage(`收到消息: ${data.type}`);
            }
        }
        
        // 设置事件监听器
        function setupEventListeners() {
            // 强度控制
            const strengthA = document.getElementById('strength-a');
            const strengthB = document.getElementById('strength-b');
            
            strengthA.addEventListener('input', () => {
                const value = strengthA.value;
                document.getElementById('strength-a-value').textContent = value;
            });
            
            strengthA.addEventListener('change', () => {
                sendMessage({
                    type: 'set_strength',
                    channel_a: parseInt(strengthA.value),
                    channel_b: parseInt(strengthB.value)
                });
            });
            
            strengthB.addEventListener('input', () => {
                const value = strengthB.value;
                document.getElementById('strength-b-value').textContent = value;
            });
            
            strengthB.addEventListener('change', () => {
                sendMessage({
                    type: 'set_strength',
                    channel_a: parseInt(strengthA.value),
                    channel_b: parseInt(strengthB.value)
                });
            });
            
            // 波形参数控制
            setupWaveParamControls('a');
            setupWaveParamControls('b');
            
            // 预设按钮
            document.querySelectorAll('.preset-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const channel = btn.getAttribute('data-channel');
                    const preset = btn.getAttribute('data-preset');
                    
                    sendMessage({
                        type: 'set_wave_preset',
                        channel: channel,
                        preset_name: preset
                    });
                    
                    logMessage(`应用预设: ${preset} 到通道 ${channel}`);
                });
            });
            
            // 设备控制按钮
            document.getElementById('scan-btn').addEventListener('click', () => {
                sendMessage({ type: 'scan_devices' });
                logMessage('正在扫描设备...');
                
                // 添加超时检查 - 5秒后检查是否已连接
                setTimeout(() => {
                    if (!deviceConnected) {
                        logMessage('扫描超时或未发现设备，请确认设备已开启且在范围内');
                        
                        // 再次请求状态更新
                        sendMessage({ type: 'get_state' });
                    }
                }, 5000);
            });
            
            document.getElementById('disconnect-btn').addEventListener('click', () => {
                sendMessage({ type: 'disconnect_device' });
                logMessage('正在断开设备连接...');
            });
            
            // 手动连接按钮
            document.getElementById('manual-connect-btn').addEventListener('click', () => {
                const deviceAddress = document.getElementById('device-address').value.trim();
                if (!deviceAddress) {
                    logMessage('错误: 请输入设备地址');
                    return;
                }
                
                sendMessage({
                    type: 'connect_device',
                    device_address: deviceAddress
                });
                
                logMessage(`正在连接设备: ${deviceAddress}`);
            });
        }
        
        // 设置波形参数控制
        function setupWaveParamControls(channel) {
            const xControl = document.getElementById(`wave-${channel}-x`);
            const yControl = document.getElementById(`wave-${channel}-y`);
            const zControl = document.getElementById(`wave-${channel}-z`);
            
            // X参数
            xControl.addEventListener('input', () => {
                const value = xControl.value;
                document.getElementById(`wave-${channel}-x-value`).textContent = value;
            });
            
            xControl.addEventListener('change', () => {
                sendWaveParams(channel.toUpperCase());
            });
            
            // Y参数
            yControl.addEventListener('input', () => {
                const value = yControl.value;
                document.getElementById(`wave-${channel}-y-value`).textContent = value;
            });
            
            yControl.addEventListener('change', () => {
                sendWaveParams(channel.toUpperCase());
            });
            
            // Z参数
            zControl.addEventListener('input', () => {
                const value = zControl.value;
                document.getElementById(`wave-${channel}-z-value`).textContent = value;
            });
            
            zControl.addEventListener('change', () => {
                sendWaveParams(channel.toUpperCase());
            });
        }
        
        // 发送波形参数
        function sendWaveParams(channel) {
            const channelLower = channel.toLowerCase();
            const x = parseInt(document.getElementById(`wave-${channelLower}-x`).value);
            const y = parseInt(document.getElementById(`wave-${channelLower}-y`).value);
            const z = parseInt(document.getElementById(`wave-${channelLower}-z`).value);
            
            sendMessage({
                type: 'set_wave',
                channel: channel,
                wave_x: x,
                wave_y: y,
                wave_z: z
            });
            
            logMessage(`设置通道 ${channel} 波形参数: X=${x}, Y=${y}, Z=${z}`);
        }
        
        // 更新连接状态
        function updateConnectionStatus(connected) {
            const element = document.getElementById('connection-status');
            const dot = element.querySelector('.status-dot');
            const text = element.querySelector('.status-text');
            
            if (connected) {
                dot.className = 'status-dot connected';
                text.textContent = 'WebSocket: 已连接';
            } else {
                dot.className = 'status-dot disconnected';
                text.textContent = 'WebSocket: 未连接';
            }
        }
        
        // 更新设备状态
        function updateDeviceStatus(connected) {
            deviceConnected = connected;
            
            const element = document.getElementById('device-status');
            const dot = element.querySelector('.status-dot');
            const text = element.querySelector('.status-text');
            
            if (connected) {
                dot.className = 'status-dot connected';
                text.textContent = 'DG-LAB: 已连接';
            } else {
                dot.className = 'status-dot disconnected';
                text.textContent = 'DG-LAB: 未连接';
            }
        }
        
        // 更新电池状态
        function updateBatteryStatus(battery) {
            const element = document.getElementById('battery-status');
            const text = element.querySelector('.status-text');
            
            if (battery != null) {
                text.textContent = `电量: ${battery}%`;
            } else {
                text.textContent = '电量: --';
            }
        }
        
        // 更新强度值
        function updateStrengthValues(strengthA, strengthB) {
            const aInput = document.getElementById('strength-a');
            const bInput = document.getElementById('strength-b');
            const aValue = document.getElementById('strength-a-value');
            const bValue = document.getElementById('strength-b-value');
            
            aInput.value = strengthA;
            aValue.textContent = strengthA;
            
            bInput.value = strengthB;
            bValue.textContent = strengthB;
        }
        
        // 更新波形参数
        function updateWaveParams(channel, x, y, z) {
            const channelLower = channel.toLowerCase();
            
            const xInput = document.getElementById(`wave-${channelLower}-x`);
            const yInput = document.getElementById(`wave-${channelLower}-y`);
            const zInput = document.getElementById(`wave-${channelLower}-z`);
            
            const xValue = document.getElementById(`wave-${channelLower}-x-value`);
            const yValue = document.getElementById(`wave-${channelLower}-y-value`);
            const zValue = document.getElementById(`wave-${channelLower}-z-value`);
            
            xInput.value = x;
            xValue.textContent = x;
            
            yInput.value = y;
            yValue.textContent = y;
            
            zInput.value = z;
            zValue.textContent = z;
        }
        
        // 添加日志消息
        function logMessage(message) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString();
            const logElement = document.getElementById('log-content');
            
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `<span class="log-time">[${timeStr}]</span> ${message}`;
            
            logElement.appendChild(entry);
            logElement.scrollTop = logElement.scrollHeight;
            
            // 最多保留50条日志
            while (logElement.children.length > 50) {
                logElement.removeChild(logElement.firstChild);
            }
        }
        
        // 页面加载完成后初始化
        window.addEventListener('load', init);
    </script>
</body>
</html>
    """
    
    # 创建style.css
    style_css = """/* 全局样式 */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: 'Microsoft YaHei', Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f5f5f5;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background-color: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    padding: 20px;
}

h1 {
    text-align: center;
    margin-bottom: 20px;
    color: #333;
}

/* 状态面板 */
.status-panel {
    display: flex;
    justify-content: space-between;
    background-color: #f9f9f9;
    padding: 15px;
    border-radius: 5px;
    margin-bottom: 20px;
}

.status-indicator {
    display: flex;
    align-items: center;
}

.status-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 8px;
}

.connected {
    background-color: #4CAF50;
    box-shadow: 0 0 5px #4CAF50;
}

.disconnected {
    background-color: #F44336;
    box-shadow: 0 0 5px #F44336;
}

.status-text {
    font-weight: 500;
}

/* 控制面板 */
.control-panel {
    margin-bottom: 20px;
}

.channel-controls {
    display: flex;
    gap: 20px;
    margin-bottom: 20px;
}

.channel {
    flex: 1;
    padding: 15px;
    border: 1px solid #ddd;
    border-radius: 5px;
    background-color: #f9f9f9;
}

.channel h2 {
    margin-bottom: 15px;
    padding-bottom: 5px;
    border-bottom: 1px solid #ddd;
}

.strength-control {
    margin-bottom: 20px;
}

.strength-control label {
    display: block;
    margin-bottom: 8px;
    font-weight: 500;
}

input[type="range"] {
    width: 100%;
    margin-bottom: 5px;
}

.wave-control {
    margin-bottom: 20px;
}

.wave-control h3 {
    margin-bottom: 10px;
}

.wave-params {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.wave-params > div {
    display: flex;
    align-items: center;
}

.wave-params label {
    width: 30px;
    font-weight: 500;
}

.wave-params span {
    width: 40px;
    text-align: right;
}

.presets h3 {
    margin-bottom: 10px;
}

.preset-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}

.preset-btn {
    padding: 8px;
    background-color: #eee;
    border: 1px solid #ddd;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
}

.preset-btn:hover {
    background-color: #ddd;
}

.device-controls {
    display: flex;
    justify-content: center;
    gap: 20px;
}

.device-controls button {
    padding: 10px 20px;
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
}

.device-controls button:hover {
    background-color: #0b7dda;
}

/* 日志面板 */
.log-panel {
    padding: 15px;
    border: 1px solid #ddd;
    border-radius: 5px;
    background-color: #f9f9f9;
}

.log-panel h3 {
    margin-bottom: 10px;
}

#log-content {
    height: 150px;
    overflow-y: auto;
    padding: 10px;
    background-color: #fff;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-family: monospace;
    font-size: 14px;
}

.log-entry {
    margin-bottom: 5px;
}

.log-time {
    color: #888;
    margin-right: 5px;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .channel-controls {
        flex-direction: column;
    }
}

/* 手动连接区域 */
.manual-connect {
    margin-top: 20px;
    padding: 15px;
    border: 1px solid #ddd;
    border-radius: 5px;
    background-color: #f9f9f9;
}

.manual-connect h3 {
    margin-bottom: 10px;
}

.manual-connect-form {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}

.manual-connect-form input {
    flex-grow: 1;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.manual-connect-form button {
    padding: 8px 15px;
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.hint {
    font-size: 0.85em;
    color: #666;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .channel-controls {
        flex-direction: column;
    }
}
"""
    
    # 写入文件
    with open(Path(__file__).parent / "static" / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    
    with open(Path(__file__).parent / "static" / "style.css", "w", encoding="utf-8") as f:
        f.write(style_css)
    
    logger.info("WebUI静态文件已创建")

# 设置插件钩子，允许加载时注入WebSocket服务器引用
def set_ws_server(server):
    """设置WebSocket服务器引用"""
    global ws_server
    ws_server = server 