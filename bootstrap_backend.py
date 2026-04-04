import argparse
from contextlib import asynccontextmanager
import subprocess
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llm_service import LLMService
from openai_api import router as openai_router
from auth import api_key_manager
from rich.console import Console
from asciiart import print_ascii_art
from wintoast import sendToast
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from i18n import localize
from config import MODEL_PATH, DEVICE, HOST, PORT, API_KEY, AUTO_GENERATE_KEY, DEBUG, generate_config

console = Console()

# 打印ASCII艺术
print_ascii_art()



# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description=localize('cli.description.backend'))
    parser.add_argument("model_path", nargs='?', help=localize('cli.model_path.help'))
    parser.add_argument("-d", "--device", default="AUTO", help=localize('cli.device.help'))
    parser.add_argument("-p", "--port", type=int, default=8000, help=localize('cli.port.help'))
    parser.add_argument("--key", type=str, help=localize('cli.key.help'))
    parser.add_argument("--genkey", action="store_true", help=localize('cli.genkey.help'))
    parser.add_argument("--api-custom", action="store_true", help=localize('cli.api_custom.help'))
    parser.add_argument("--debug", action="store_true", help=localize('cli.debug.help'))
    parser.add_argument("--nogui", action="store_true", help=localize('cli.nogui.help'))
    parser.add_argument("--genconf", action="store_true", help=localize('cli.genconf.help'))
    parser.add_argument("-S", "--sync", action="store_true", help=localize('cli.sync.help'))
    return parser.parse_args()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在应用启动时加载模型
    args = parse_args()
    
    # MCP support removed; keep state variables for compatibility
    app.state.mcp_enabled = False
    app.state.mcp_features = []
    app.state.mcp_server = None
    
    # 设置API密钥
    if args.genkey or AUTO_GENERATE_KEY:
        generated_key = api_key_manager.generate_api_key()
        api_key_manager.set_api_key(generated_key)
        console.print(f"✅ {localize('server.api.key.generated', key=generated_key)}")
        console.print(f"🔒 {localize('server.api.key.instruction')}")   
    elif args.key or API_KEY:
        api_key = args.key if args.key else API_KEY
        api_key_manager.set_api_key(api_key)
        console.print(f"✅ {localize('server.api.key.set', key=api_key)}")
        console.print(f"🔒 {localize('server.api.key.instruction')}")   
    else:
        api_key_manager.set_api_key(None)
        console.print(f"[yellow]⚠️ {localize('server.api.key.not.set')}[/yellow].")
        sendToast("API Key Not Set", localize('server.api.key.not.set'))
    
    # 加载模型并存储到应用状态
    model_path = args.model_path if args.model_path else MODEL_PATH
    device = args.device if args.device else DEVICE
    sync = getattr(args, 'sync', False)  # 获取 sync 参数，默认为 False
    app.state.llm = LLMService(model_path, device, sync)
    
    # 启用调试模式
    debug_mode = args.debug or DEBUG
    app.state.debug_enabled = debug_mode
    if debug_mode:
        console.print(f"🔧 {localize('server.debug.enabled')}")
    
    # 启用自定义API参数
    app.state.api_custom = args.api_custom
    if args.api_custom:
        console.print(f"✅ {localize('server.api.custom.enabled')}")
    
    yield
    # 清理代码（如果需要的话）

app = FastAPI(title="OpenVINO GenAI API", lifespan=lifespan)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(openai_router)

@app.get("/")
async def root():
    return {"message": localize('api.running')}

@app.get("/health")
async def health_check():
    return {"status": localize('api.healthy')}

if __name__ == "__main__":
    args = parse_args()
    
    # 处理 --genconf 参数
    if args.genconf:
        config_path = generate_config(args)
        console.print(f"✅ {localize('config.generated', path=config_path)}")
        console.print(f"📝 {localize('config.edit.instruction')}")
        exit(0)
    
    # 确保提供了 model_path
    if not args.model_path and not MODEL_PATH:
        console.print("[red]Error: No model path provided. Please specify a model path or set it in usrconfig.conf.[/red]")
        exit(1)
    
    import uvicorn

    # 使用配置文件中的值，命令行参数优先级更高
    host = HOST
    port = args.port if args.port else PORT

    if args.nogui:
        # Run server normally without GUI
        uvicorn.run("__main__:app", host=host, port=port, reload=False)
    else:
        # Start uvicorn in a background thread and run GUI in main thread
        def run_server():
            uvicorn.run("__main__:app", host=host, port=port, reload=False)

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Start monitor GUI (blocks)
        try:
            from monitor_gui import start_monitor_gui
            start_monitor_gui()
        except Exception as e:
            console.print(f"[red]Failed to start monitor GUI: {e}[/red]")
            server_thread.join()