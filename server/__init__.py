"""
DG-LAB 设备控制服务器模块
提供WebSocket接口让其他程序控制设备
"""

from .ws_server import DGLabWebSocketServer

__all__ = ['DGLabWebSocketServer'] 