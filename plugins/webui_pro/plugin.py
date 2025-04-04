"""
DG-LAB（不)实用插件
"""

import logging
import json
import importlib
import sys
import time
import threading
import datetime
import asyncio
import random

# 设置日志
logger = logging.getLogger(__name__)

# 存储WebSocket服务器引用
ws_server = None

# 每日一言列表
daily_quotes = [
    "技术是为了解决问题，而不是创造问题。",
    "好的代码就像好的笑话，不需要解释。",
    "编程是思考，不仅仅是编码。",
    "调试的难度是写代码的两倍，所以写代码时要尽可能简洁。",
    "真正的程序员不会写注释，代码应该是自解释的。",
    "没有人能够做到一次编写完美的代码，但我们可以不断改进。",
    "简单是可靠的前提。",
    "写代码一时爽，重构火葬场。",
    "重构是为未来的自己节省时间。",
    "测试不会让你的代码更好，但会让你更有信心修改它。",
    "不要过早优化，99%的情况下你不需要它。",
    "复杂的问题往往有一个简单且错误的解决方案。",
    "代码写给人看，顺便给机器执行。",
    "电子产品的使用体验直接影响用户的情绪和健康。",
    "有一句话说得好：先让它工作，再让它好用。",
    "编程不仅仅是写代码，更是解决问题的艺术。",
    "DG-LAB设备，让你释放压力，享受生活。",
    "糟糕的界面会让好的功能变得一文不值。",
    "不同的设备，相同的体验。一致性是优秀设计的灵魂。",
    "今天的努力，是为了明天的便捷。",
    "用心设计每一个交互，让用户体验更加流畅。",
    "科技，是为了让生活更美好，而不是更复杂。",
    "简单不意味着缺乏功能，而是把复杂的事情变得简单。",
    "没有人关心你的代码多么聪明，他们只关心它是否解决了问题。",
    "直觉界面是最好的界面，用户不需要思考就能使用。"
]

# 获取WebUI插件的register_ui_extension函数
def get_webui_register_function():
    """获取WebUI插件的register_ui_extension函数"""
    try:
        # 确保webui模块已加载
        if "plugins.webui.plugin" not in sys.modules:
            time.sleep(1)  # 等待一小段时间，确保WebUI已初始化
            importlib.import_module("plugins.webui.plugin")
        
        # 获取模块引用
        webui_module = sys.modules.get("plugins.webui.plugin")
        if webui_module and hasattr(webui_module, "register_ui_extension"):
            logger.info("成功获取WebUI插件的register_ui_extension函数")
            return webui_module.register_ui_extension
        else:
            logger.warning("WebUI模块已加载，但未找到register_ui_extension函数")
            return None
    except Exception as e:
        logger.error(f"获取WebUI的register_ui_extension函数失败: {e}")
        return None

def set_ws_server(server):
    """设置WebSocket服务器引用"""
    global ws_server
    ws_server = server
    logger.info("已接收WebSocket服务器引用")
    
    # 打印WebSocket服务器对象的属性和方法
    logger.debug(f"WebSocket服务器对象类型: {type(server)}")
    logger.debug(f"WebSocket服务器可用方法: {[method for method in dir(server) if not method.startswith('_')]}")

def setup():
    """插件初始化函数"""
    logger.info("DG-LAB实用插件初始化中...")
    
    # 使用延迟注册，确保WebUI插件已完全初始化
    threading.Timer(2.0, register_extensions).start()
    
    logger.info("DG-LAB实用插件已初始化，将在2秒后注册UI扩展")

def register_extensions():
    """注册UI扩展"""
    logger.debug("开始注册DG-LAB实用插件UI扩展")
    
    # 获取注册函数
    register_ui_extension = get_webui_register_function()
    
    if not register_ui_extension:
        logger.error("无法获取WebUI插件的register_ui_extension函数，扩展注册失败")
        return
    
    # 1. 顶部通知栏
    success = register_ui_extension(
        "header", 
        "notification_bar",
        """
        <style>
        .notification-bar {
            background: linear-gradient(135deg, #4CAF50, #2196F3);
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            animation: fadeIn 0.5s ease-in-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        #notification-icon {
            font-size: 20px;
            margin-right: 12px;
        }
        
        #notification-message {
            flex: 1;
            font-size: 15px;
        }
        
        #dismiss-notification {
            background: none;
            border: none;
            color: white;
            font-size: 18px;
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.3s;
        }
        
        #dismiss-notification:hover {
            opacity: 1;
        }
        </style>
        <div class="notification-bar">
            <span id="notification-icon">👋</span>
            <span id="notification-message">欢迎使用DG-LAB设备控制系统，实用插件已加载</span>
            <button id="dismiss-notification">×</button>
        </div>
        """,
        """
        document.getElementById('dismiss-notification').addEventListener('click', function() {
            document.querySelector('.notification-bar').style.display = 'none';
        });
        """
    )
    logger.info(f"注册顶部通知栏: {'成功' if success else '失败'}")
    
    # 2. 控制面板 - 每日一言
    daily_quote = random.choice(daily_quotes)
    success = register_ui_extension(
        "control_panel", 
        "daily_quote",
        f"""
        <style>
        .quote-panel {{
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 15px;
            margin-bottom: 20px;
        }}
        
        .quote-panel h3 {{
            margin-top: 0;
            color: #333;
            font-size: 18px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 10px;
        }}
        
        .quote-content {{
            padding: 10px 0;
            position: relative;
        }}
        
        #daily-quote {{
            font-style: italic;
            color: #555;
            font-size: 16px;
            line-height: 1.6;
            margin: 10px 0 20px;
            padding-left: 20px;
            border-left: 3px solid #2196F3;
            transition: all 0.3s ease;
        }}
        
        .quote-refresh {{
            animation: quoteRefresh 0.5s ease;
        }}
        
        @keyframes quoteRefresh {{
            0% {{ opacity: 0; transform: translateY(10px); }}
            100% {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .quote-button {{
            background-color: #2196F3;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
            float: right;
        }}
        
        .quote-button:hover {{
            background-color: #0b7dda;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        </style>
        <div class="quote-panel">
            <h3>每日一言</h3>
            <div class="quote-content">
                <blockquote id="daily-quote">"{daily_quote}"</blockquote>
                <button id="refresh-quote" class="quote-button">换一条</button>
            </div>
        </div>
        """,
        f"""
        // 从后端获取的名言列表 (避免重复定义)
        const quotes = {json.dumps(daily_quotes, ensure_ascii=False)};
        
        document.getElementById('refresh-quote').addEventListener('click', function() {{
            const quoteElement = document.getElementById('daily-quote');
            const randomIndex = Math.floor(Math.random() * quotes.length);
            quoteElement.textContent = `"${{quotes[randomIndex]}}"`;
            
            // 添加过渡动画
            quoteElement.classList.add('quote-refresh');
            setTimeout(() => {{
                quoteElement.classList.remove('quote-refresh');
            }}, 500);
            
            logMessage('已更新每日一言');
        }});
        """
    )
    logger.info(f"注册每日一言: {'成功' if success else '失败'}")
    
    # 3. 底部Github项目链接
    success = register_ui_extension(
        "footer", 
        "github_link",
        """
        <style>
        .github-link {
            padding: 15px 0;
            text-align: center;
            margin-top: 20px;
            border-top: 1px solid #eee;
        }
        
        .github-link p {
            font-size: 14px;
            color: #666;
        }
        
        .github-link a {
            color: #2196F3;
            text-decoration: none;
            transition: all 0.3s;
            position: relative;
        }
        
        .github-link a:hover {
            color: #0b7dda;
        }
        
        .github-link a:after {
            content: '';
            position: absolute;
            width: 100%;
            height: 2px;
            bottom: -2px;
            left: 0;
            background-color: #2196F3;
            transform: scaleX(0);
            transition: transform 0.3s;
        }
        
        .github-link a:hover:after {
            transform: scaleX(1);
        }
        </style>
        <div class="github-link">
            <p>项目地址: <a href="https://github.com/zzzzzyc/fucking-3.0" target="_blank">github.com/zzzzzyc/fucking-3.0</a></p>
        </div>
        """,
        """
        // 给链接添加点击动画
        const githubLink = document.querySelector('.github-link a');
        if (githubLink) {
            githubLink.addEventListener('click', function(e) {
                // 打开链接
                window.open(this.href, '_blank');
                e.preventDefault();
                
                // 记录日志
                logMessage('打开项目地址: ' + this.href);
            });
        }
        """
    )
    logger.debug(f"注册Github项目链接: {'成功' if success else '失败'}")

async def handle_message(websocket, message_data):
    """处理WebSocket消息"""
    # 这个插件不处理任何WebSocket消息
    return False

def cleanup():
    """插件清理函数"""
    logger.info("DG-LAB实用插件已清理")