import argparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llm_service import LLMService
from openai_api import router as openai_router

app = FastAPI(title="OpenVINO GenAI API")

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

@app.on_event("startup")
async def startup_event():
    # 在应用启动时加载模型
    parser = argparse.ArgumentParser(description="OpenVINO GenAI Web Server")
    parser.add_argument("model_path", help="模型目录路径（本地OpenVINO格式模型）")
    parser.add_argument("-d", "--device", default="AUTO", help="运行设备（AUTO/CPU/GPU/NPU/Intel® Arc™）")
    args, _ = parser.parse_known_args()
    
    # 加载模型并存储到应用状态
    app.state.llm = LLMService(args.model_path, args.device)

@app.get("/")
async def root():
    return {"message": "OpenVINO GenAI API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="OpenVINO GenAI Web Server")
    parser.add_argument("model_path", help="模型目录路径（本地OpenVINO格式模型）")
    parser.add_argument("-d", "--device", default="AUTO", help="运行设备（AUTO/CPU/GPU/NPU/Intel® Arc™）")
    parser.add_argument("-p", "--port", type=int, default=8000, help="服务器端口")
    args = parser.parse_args()
    
    uvicorn.run("app:app", host="0.0.0.0", port=args.port, reload=False)