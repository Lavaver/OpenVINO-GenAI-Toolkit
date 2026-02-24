import json
import time
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from llm_service import LLMService
from auth import verify_api_key_dependency

router = APIRouter(prefix="/v1")

# 模型信息数据结构
class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "local"

class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]

# OpenAI ChatCompletion 请求格式
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "local-model"  # 忽略，仅用于占位
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 32768
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    stream: Optional[bool] = False

def build_prompt_from_messages(messages: List[ChatMessage]) -> str:
    """
    将消息列表转换为单字符串提示
    简单实现：提取最后一条用户消息作为输入，忽略历史（可扩展）
    """
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    raise HTTPException(status_code=400, detail="No user message found")

@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request, api_key: str = Depends(verify_api_key_dependency)):
    # 获取服务实例（在应用启动时设置）
    llm: LLMService = req.app.state.llm

    prompt = build_prompt_from_messages(request.messages)
    max_tokens = request.max_tokens
    temperature = request.temperature
    top_p = request.top_p
    stream = request.stream

    if not stream:
        # 非流式：生成完整文本后返回 JSON
        try:
            text = await llm.generate(prompt, max_tokens, temperature, top_p)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        # 构建 OpenAI 格式响应
        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "local-model",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        return JSONResponse(content=response)
    else:
        # 流式：使用 SSE 逐 token 发送
        async def generate():
            # 发送角色标识
            yield f"data: {json.dumps({'id': 'chatcmpl-xxx', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': 'local-model', 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
            try:
                async for token in llm.generate_stream(prompt, max_tokens, temperature, top_p):
                    # 每个 token 作为一个 delta
                    chunk = {
                        "id": "chatcmpl-xxx",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "local-model",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None
                            }
                        ]
                    }
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            # 结束标记
            yield f"data: {json.dumps({'id': 'chatcmpl-xxx', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': 'local-model', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

@router.get("/models")
async def list_models(api_key: str = Depends(verify_api_key_dependency)):
    models = [
        ModelInfo(
            id="Intel(R) OpenVINO(TM) GenAI Localhost Model",
            created=int(time.time())
        )
    ]
    
    response = ModelsResponse(data=models)
    return JSONResponse(content=response.dict())