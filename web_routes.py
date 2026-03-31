from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from llm_service import LLMService

router = APIRouter()
templates = Jinja2Templates(directory="templates")

class ChatRequest(BaseModel):
    prompt: str
    max_tokens: int = 32768
    temperature: float = 0.7
    top_p: float = 0.9

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Return the chat interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/api/chat")
async def chat_stream(request: ChatRequest, req: Request):
    """SSE endpoint for streaming chat responses"""
    llm: LLMService = req.app.state.llm

    async def generate():
        """Stream chat responses using SSE"""
        try:
            async for token in llm.generate_stream(
                request.prompt,
                request.max_tokens,
                request.temperature,
                request.top_p
            ):
                # Directly send the token string (frontend and console parse the <think> tag themselves)
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")