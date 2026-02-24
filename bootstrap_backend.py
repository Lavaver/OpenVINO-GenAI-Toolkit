import argparse
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llm_service import LLMService
from openai_api import router as openai_router
from auth import api_key_manager
from rich.console import Console
from asciiart import print_ascii_art

console = Console()

# 打印ASCII艺术
print_ascii_art()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在应用启动时加载模型
    parser = argparse.ArgumentParser(description="OpenVINO GenAI Web Server")
    parser.add_argument("model_path", help="Model Directory Path (Local OpenVINO Format Models)")
    parser.add_argument("-d", "--device", default="AUTO", help="Running Device (AUTO/CPU/GPU/NPU/Intel® Arc™)")
    parser.add_argument("--key", type=str, help="Specify a specific API key. Only requests with this key will be granted access.")
    parser.add_argument("--genkey", action="store_true", help="Generate a random API key in the format sk-[GUID]-localhost")
    
    args, _ = parser.parse_known_args()
    
    # 设置API密钥
    if args.genkey:
        generated_key = api_key_manager.generate_api_key()
        api_key_manager.set_api_key(generated_key)
        console.print(f"✅ A random API key has been generated: [aqua]{generated_key}[/aqua]")
        console.print(f"🔒 Please use this key in the Authorization header: Authorization: Bearer {generated_key}")
    elif args.key:
        api_key_manager.set_api_key(args.key)
        console.print(f"✅ The specified API key has been set: [aqua]{args.key}[/aqua]")
        console.print(f"🔒 Please use this key in the Authorization header: Authorization: Bearer {args.key}")
    else:
        api_key_manager.set_api_key(None)
        console.print("[yellow]⚠️ No API key has been set. Any request can access the service without authentication[/yellow].")
    
    # 加载模型并存储到应用状态
    app.state.llm = LLMService(args.model_path, args.device)
    
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
    return {"message": "OpenVINO GenAI API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="OpenVINO GenAI Web Server")
    parser.add_argument("model_path", help="Model Directory Path (Local OpenVINO Format Models)")
    parser.add_argument("-d", "--device", default="AUTO", help="Running Device (AUTO/CPU/GPU/NPU/Intel® Arc™)")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Server Port")
    parser.add_argument("--key", type=str, help="Specify a specific API key. Only requests with this key will be granted access.")
    parser.add_argument("--genkey", action="store_true", help="Generate a random API key in the format sk-[GUID]-localhost")
    args = parser.parse_args()
    
    uvicorn.run("__main__:app", host="0.0.0.0", port=args.port, reload=False)