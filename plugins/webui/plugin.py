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
        html_path = Path(__file__).parent / "static" / "index.html"
        
        try:
            with open(html_path, encoding="utf-8") as f:
                content = f.read()
            
            # 替换占位符
            content = content.replace("{{WS_HOST}}", ws_server.host)
            content = content.replace("{{WS_PORT}}", str(ws_server.port))
            
            return web.Response(text=content, content_type="text/html")
        except FileNotFoundError:
            logger.error(f"HTML文件不存在: {html_path}")
            return web.Response(text="HTML文件未找到，请确保index.html文件存在于static目录中", status=404)
    
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