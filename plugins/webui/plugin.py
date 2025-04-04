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
import importlib
import time
import traceback

# 设置日志
logger = logging.getLogger(__name__)

# 存储WebSocket服务器引用
ws_server = None

# AB通道同步状态
channel_sync_enabled = False

# 添加UI扩展存储
ui_extensions = {
    "header": [],
    "control_panel": [],
    "footer": []
}

# 添加扩展点注册API
def register_ui_extension(extension_point, name, html, js=None):
    """
    注册UI扩展到WebUI
    
    Args:
        extension_point: 扩展点('header', 'control_panel', 'footer')
        name: 扩展名称
        html: HTML内容
        js: JavaScript代码(可选)
    
    Returns:
        bool: 注册是否成功
    """
    if extension_point in ui_extensions:
        ui_extensions[extension_point].append({
            "name": name,
            "html": html,
            "js": js
        })
        logger.info(f"已注册UI扩展: {name} 到 {extension_point}")
        return True
    return False

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
        html_path = Path(__file__).parent / "static" / "index.html"
        
        try:
            with open(html_path, encoding="utf-8") as f:
                content = f.read()
            
            # 替换占位符
            content = content.replace("{{WS_HOST}}", ws_server.host)
            content = content.replace("{{WS_PORT}}", str(ws_server.port))
            
            # 注入UI扩展 - 修复字符串替换逻辑
            for point, extensions in ui_extensions.items():
                logger.debug(f"扩展点 {point} 有 {len(extensions)} 个扩展")
                for ext in extensions:
                    logger.debug(f"处理扩展: {ext['name']} (HTML长度: {len(ext['html'])})")
                
                # 为每个扩展点生成HTML和JS
                extension_html = ""
                extension_js = ""
                
                for ext in extensions:
                    logger.info(f"正在注入扩展: {ext['name']} 到 {point}")
                    extension_html += f'<div class="ui-extension" data-name="{ext["name"]}">{ext["html"]}</div>\n'
                    if ext.get("js"):
                        extension_js += f"// {ext['name']} 扩展JS\n{ext['js']}\n"
                
                # 执行字符串替换 - 使用简单字符串格式
                placeholder_html = "{{EXTENSIONS_" + point.upper() + "}}"
                placeholder_js = "{{EXTENSIONS_JS_" + point.upper() + "}}"
                
                logger.debug(f"查找占位符: '{placeholder_html}'")
                if placeholder_html in content:
                    logger.debug(f"找到占位符 '{placeholder_html}'，进行替换")
                    content = content.replace(placeholder_html, extension_html)
                    content = content.replace(placeholder_js, extension_js)
            
            return web.Response(text=content, content_type="text/html")
        except FileNotFoundError:
            logger.error(f"HTML文件不存在: {html_path}")
            return web.Response(text="HTML文件未找到，请确保index.html文件存在于static目录中", status=404)
        except Exception as e:
            logger.error(f"生成HTML时出错: {str(e)}")
            return web.Response(text=f"生成页面时出错: {str(e)}", status=500)
    
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
        # 创建静态目录
        static_path = Path(__file__).parent / "static"
        if not static_path.exists():
            static_path.mkdir()
        
        # 创建并启动WebUI
        webui_instance = WebUI()
        webui_instance.start()
        
        # 注册AB通道同步控件
        register_ui_extension(
            "control_panel", 
            "channel_sync",
            """
            <div class="sync-control-panel">
                <h3>通道控制</h3>
                <div class="sync-control">
                    <label class="switch">
                        <input type="checkbox" id="ab-channel-sync">
                        <span class="slider round"></span>
                    </label>
                    <span class="sync-label">A/B通道同步</span>
                    <div class="sync-description">启用后，A通道的设置将自动同步至B通道</div>
                </div>
            </div>
            """,
            """
            document.getElementById('ab-channel-sync').addEventListener('change', function() {
                const syncEnabled = this.checked;
                
                sendMessage({
                    type: 'channel_sync_change',
                    enabled: syncEnabled
                });
                
                logMessage('A/B通道同步已' + (syncEnabled ? '启用' : '禁用'));
            });
            
            // 监听WebSocket消息更新同步状态
            window.addEventListener('websocketMessage', function(event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'sync_status_updated') {
                        document.getElementById('ab-channel-sync').checked = data.enabled;
                    }
                } catch (e) {
                    console.error('处理同步状态消息错误:', e);
                }
            });
            """
        )
        
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
    global channel_sync_enabled
    
    # 处理通道同步设置消息
    if message_data.get("type") == "channel_sync_change":
        try:
            enabled = message_data.get("enabled", False)
            channel_sync_enabled = enabled
            
            logger.info(f"A/B通道同步已{'启用' if enabled else '禁用'}")
            
            # 广播状态变化
            await broadcast_sync_status()
            
            # 如果启用同步，并且设备已连接，则进行首次同步
            if enabled and ws_server and ws_server.device and ws_server.device.is_connected:
                # 获取A通道的当前设置
                device_state = await ws_server.device.get_state()
                if "channel_a" in device_state and "channel_b" in device_state:
                    # 将A通道的波形和强度设置复制到B通道
                    if "wave" in device_state["channel_a"] and len(device_state["channel_a"]["wave"]) >= 3:
                        # 设置B通道的波形
                        await ws_server.device.set_wave(
                            "B", 
                            device_state["channel_a"]["wave"][0], 
                            device_state["channel_a"]["wave"][1], 
                            device_state["channel_a"]["wave"][2]
                        )
                    
                    # 设置B通道的强度
                    if "strength" in device_state["channel_a"]:
                        await ws_server.device.set_strength("B", device_state["channel_a"]["strength"])
                    
                    # 发送更新后的状态
                    await ws_server._send_state(websocket)
            
            return True
        except Exception as e:
            logger.error(f"处理通道同步设置错误: {e}")
            logger.error(traceback.format_exc())
            return False
    
    # 不需要在后端处理同步了，前端已经处理并发送了正确格式的消息
    # 其他类型的消息由默认处理器处理
    return False

def create_static_files():
    """创建静态文件目录"""
    # 创建静态文件目录
    static_path = Path(__file__).parent / "static"
    if not static_path.exists():
        static_path.mkdir()
        logger.info("已创建静态文件目录")
    else:
        logger.info("静态文件目录已存在")

# 设置插件钩子，允许加载时注入WebSocket服务器引用
def set_ws_server(server):
    """设置WebSocket服务器引用"""
    global ws_server
    ws_server = server
    logger.info("WebUI已接收WebSocket服务器引用")
    
    # 如果启用了通道同步，广播状态
    if channel_sync_enabled:
        asyncio.create_task(broadcast_sync_status())

async def broadcast_extension_added(area, extension_id):
    """向所有客户端广播新的扩展"""
    if not ws_server or not hasattr(ws_server, 'clients'):
        return
    
    extension = ui_extensions[area][extension_id]
    if not extension:
        return
    
    message = {
        "type": "extension_added",
        "area": area,
        "extension_id": extension_id,
        "html": extension["html"],
        "js": extension["js"]
    }
    
    try:
        for client in ws_server.clients:
            try:
                await client.send(json.dumps(message))
            except Exception as e:
                logger.error(f"向客户端发送扩展更新失败: {e}")
    except Exception as e:
        logger.error(f"广播扩展更新失败: {e}")

async def broadcast_sync_status():
    """向所有客户端广播通道同步状态"""
    if not ws_server or not hasattr(ws_server, 'clients'):
        return
    
    message = {
        "type": "sync_status_updated",
        "enabled": channel_sync_enabled,
        "message": f"A/B通道同步已{'启用' if channel_sync_enabled else '禁用'}"
    }
    
    try:
        for client in ws_server.clients:
            try:
                await client.send(json.dumps(message))
            except Exception as e:
                logger.error(f"向客户端发送同步状态更新失败: {e}")
    except Exception as e:
        logger.error(f"广播同步状态失败: {e}") 