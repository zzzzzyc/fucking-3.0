"""
DG-LAB HTTP API Plugin (v2 - Based on webui structure)
Allows controlling the device via HTTP requests using patterns from webui.
"""

import asyncio
import logging
import os
import yaml
import threading
import traceback
import json
from typing import Dict, Any, Optional

from aiohttp import web

# Assume DGLabDevice structure based on webui usage and READMEs
# If core.dglab_device is available, use actual import
try:
    # Adjust path if necessary based on your project structure
    from server.ws_server import DGLabWebSocketServer
    from core.dglab_device import DGLabDevice
except ImportError:
    logger.warning("Could not import server or core modules. Using placeholder classes.")
    # Define dummy classes for structure if modules are not found
    class DGLabWebSocketServer:
        device: Optional['DGLabDevice'] = None
        host: str = "unknown"
        port: int = 0
    class DGLabDevice:
        async def set_strength(self, channel: str, value: int): pass
        async def set_waveform_preset(self, channel: str, preset_name: str): pass
        def is_connected(self) -> bool: return False
        async def get_state(self) -> Dict[str, Any]: return {} # Based on webui usage

# Setup logger
logger = logging.getLogger(__name__)

# --- Global Variables ---
ws_server: Optional[DGLabWebSocketServer] = None
config: Dict[str, Any] = {}
http_runner: Optional[web.AppRunner] = None
http_site: Optional[web.TCPSite] = None
http_thread: Optional[threading.Thread] = None
http_loop: Optional[asyncio.AbstractEventLoop] = None
shutdown_event = asyncio.Event() # Used in the server thread loop


# Default configuration
DEFAULT_CONFIG = {
    "http_api": {
        "host": "127.0.0.1",
        "port": 8081 # Different port than WebUI
    }
}

# --- Plugin Lifecycle Functions ---

def set_ws_server(server: DGLabWebSocketServer):
    """Sets the WebSocket server instance (called by plugin loader)."""
    global ws_server
    ws_server = server
    logger.info("HTTP API Plugin: WebSocket server instance received.")

async def load_config():
    """Loads plugin configuration from config.yaml."""
    global config
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.yaml")

    loaded_config = DEFAULT_CONFIG.copy()

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f)
                if user_config and 'http_api' in user_config:
                    loaded_config['http_api'].update(user_config.get('http_api', {}))
            logger.info("HTTP API Plugin: Loaded configuration from config.yaml")
        except Exception as e:
            logger.error(f"HTTP API Plugin: Failed to load config: {e}, using defaults.")
            logger.error(traceback.format_exc())
            config = DEFAULT_CONFIG.copy() # Ensure config is reset to default on error
            return # Exit if config load fails catastrophically
    else:
        logger.info("HTTP API Plugin: config.yaml not found, using default configuration.")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
            logger.info("HTTP API Plugin: Created default config.yaml.")
        except Exception as e:
            logger.error(f"HTTP API Plugin: Failed to create default config.yaml: {e}")
            logger.error(traceback.format_exc())

    config = loaded_config

# --- HTTP Server Implementation (Threaded like webui) ---

def run_http_server_thread():
    """Target function for the HTTP server thread."""
    global http_loop, http_runner, http_site

    http_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(http_loop)

    host = config.get('http_api', {}).get('host', DEFAULT_CONFIG['http_api']['host'])
    port = config.get('http_api', {}).get('port', DEFAULT_CONFIG['http_api']['port'])

    async def start():
        app = web.Application()
        # Define routes within the async context where the loop is running
        app.add_routes([
            web.get('/status', handle_get_status),
            web.post('/control/strength', handle_set_strength), # Renamed from intensity
            web.post('/control/waveform', handle_set_waveform),
        ])

        runner = web.AppRunner(app)
        await runner.setup()
        http_runner = runner # Store runner for cleanup

        site = web.TCPSite(runner, host, port)
        await site.start()
        http_site = site # Store site for potential status checks (optional)
        logger.info(f"HTTP API Plugin: Server started in thread at http://{host}:{port}")
        # Keep running until shutdown is requested
        await shutdown_event.wait()
        logger.info("HTTP API Plugin: Shutdown signal received in server thread.")


    async def stop():
        logger.info("HTTP API Plugin: Stopping server in thread...")
        if http_runner:
            await http_runner.cleanup()
            logger.info("HTTP API Plugin: Server runner cleaned up.")
        else:
             logger.info("HTTP API Plugin: Server runner was not found for cleanup.")


    try:
        http_loop.run_until_complete(start())
    except OSError as e:
        logger.error(f"HTTP API Plugin: Failed to start server on {host}:{port} - {e}. Port might be in use.")
        logger.error(traceback.format_exc())
    except Exception as e:
        logger.error(f"HTTP API Plugin: Server thread encountered an error: {e}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("HTTP API Plugin: Server thread shutting down...")
        # Ensure cleanup runs even if start() fails or run_forever is interrupted
        if http_loop.is_running():
            http_loop.run_until_complete(stop())
        http_loop.close()
        logger.info("HTTP API Plugin: Server thread event loop closed.")


# --- HTTP Request Handlers ---

async def get_device() -> Optional[DGLabDevice]:
    """Helper to safely get the connected device instance."""
    if ws_server and ws_server.device and ws_server.device.is_connected: 
        return ws_server.device
    return None

async def handle_get_status(request: web.Request) -> web.Response:
    """Handles GET /status requests. Uses get_state() like webui."""
    device = await get_device()
    if not device:
        return web.json_response({"error": "Device not connected"}, status=404)

    try:
        # Use get_state() as observed in webui plugin's sync logic
        state = await device.get_state()
        return web.json_response(state, status=200)
    except Exception as e:
        logger.error(f"HTTP API Error getting state: {e}")
        logger.error(traceback.format_exc())
        return web.json_response({"error": "Failed to get device state"}, status=500)

async def handle_set_strength(request: web.Request) -> web.Response:
    """Handles POST /control/strength requests. Uses set_strength()."""
    device = await get_device()
    if not device:
        return web.json_response({"error": "Device not connected"}, status=404)

    try:
        # Get current state first to know the strength of the *other* channel
        current_state = await device.get_state()
        current_strength_a = current_state.get('channel_a', {}).get('strength', 0) # Default to 0 if not found
        current_strength_b = current_state.get('channel_b', {}).get('strength', 0) # Default to 0 if not found
        
        data = await request.json()
        channel = data.get("channel")
        strength = data.get("strength") # Changed from intensity

        if channel not in ['a', 'b'] or not isinstance(strength, int) or not (0 <= strength <= 100):
            return web.json_response({"error": "Invalid parameters. Required: channel ('a' or 'b'), strength (integer 0-100)"}, status=400)

        # Fix TypeError: Call set_strength providing BOTH strength arguments
        if channel == 'a':
            await device.set_strength(strength_a=strength, strength_b=current_strength_b)
        else: # channel == 'b'
            await device.set_strength(strength_a=current_strength_a, strength_b=strength)

        logger.info(f"HTTP API: Set strength: Channel {channel}, New Strength {strength}")
        # Return the strength that was set, along with the channel
        return web.json_response({"status": "success", "channel": channel, "strength": strength}, status=200)

    except json.JSONDecodeError:
         return web.json_response({"error": "Invalid JSON format in request body"}, status=400)
    except Exception as e:
        logger.error(f"HTTP API Error setting strength: {e}")
        logger.error(traceback.format_exc())
        return web.json_response({"error": f"Failed to set strength: {e}"}, status=500)

async def handle_set_waveform(request: web.Request) -> web.Response:
    """Handles POST /control/waveform requests. Uses set_waveform_preset()."""
    device = await get_device()
    if not device:
        return web.json_response({"error": "Device not connected"}, status=404)

    try:
        data = await request.json()
        channel = data.get("channel")
        preset_name = data.get("preset")

        if channel not in ['a', 'b'] or not isinstance(preset_name, str) or not preset_name:
             return web.json_response({"error": "Invalid parameters. Required: channel ('a' or 'b'), preset (string name)"}, status=400)

        # Assuming set_waveform_preset exists based on READMEs/general structure
        await device.set_waveform_preset(channel, preset_name)
        logger.info(f"HTTP API: Set waveform preset: Channel {channel}, Preset {preset_name}")
        return web.json_response({"status": "success", "channel": channel, "preset": preset_name}, status=200)

    except json.JSONDecodeError:
         return web.json_response({"error": "Invalid JSON format in request body"}, status=400)
    except AttributeError:
         logger.error("HTTP API Error: device object likely missing 'set_waveform_preset' method.")
         return web.json_response({"error": "Server configuration error: Cannot set waveform by preset name."}, status=501) # 501 Not Implemented
    except Exception as e:
        # Catch potential errors if preset name is invalid on the device side
        logger.error(f"HTTP API Error setting waveform preset: {e}")
        logger.error(traceback.format_exc())
        return web.json_response({"error": f"Failed to set waveform preset: {e}"}, status=500)


# --- Plugin Setup and Cleanup ---

def setup():
    """Plugin initialization function (called by plugin loader)."""
    global http_thread
    logger.info("Initializing HTTP API Plugin...")

    # Load config synchronously first
    # asyncio.run(load_config()) # Removed: Cannot call asyncio.run from running loop
    load_config() # Call synchronously now

    # Start the server in a separate thread
    if not http_thread or not http_thread.is_alive():
        shutdown_event.clear() # Ensure event is clear before starting
        http_thread = threading.Thread(target=run_http_server_thread, daemon=True)
        http_thread.start()
        logger.info("HTTP API Plugin server thread started.")
    else:
        logger.warning("HTTP API Plugin server thread already running.")

    logger.info("HTTP API Plugin initialized.")

async def handle_message(websocket, message_data: Dict[str, Any]) -> bool:
    """Handles WebSocket messages (not used by this plugin)."""
    return False # This plugin uses HTTP, not direct WS messages

def cleanup():
    """Plugin cleanup function (called by plugin loader)."""
    global http_thread, http_loop
    logger.info("Cleaning up HTTP API Plugin...")

    if http_thread and http_thread.is_alive():
        logger.info("Requesting HTTP server thread shutdown...")
        if http_loop and http_loop.is_running():
            # Signal the server loop to stop
            http_loop.call_soon_threadsafe(shutdown_event.set)

            # Wait for the thread to finish
            http_thread.join(timeout=5.0)
            if http_thread.is_alive():
                logger.warning("HTTP API Plugin: Server thread did not terminate gracefully.")
            else:
                logger.info("HTTP API Plugin: Server thread terminated.")
        else:
            logger.warning("HTTP API Plugin: Server thread loop not found or not running during cleanup.")

    else:
        logger.info("HTTP API Plugin: Server thread was not running.")

    http_thread = None
    http_loop = None
    logger.info("HTTP API Plugin cleanup finished.") 
