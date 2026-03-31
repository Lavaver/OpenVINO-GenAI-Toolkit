import json
import time
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any, Union
from llm_service import LLMService
from auth import verify_api_key_dependency
from copilot_calls import parse_tool_call, build_tool_call_json, extract_available_tool_names
import runtime_monitor
import internal_tools


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='openai_api.log',
    filemode='a'
)

logger = logging.getLogger(__name__)

# Optional OpenAI SDK integration (imported if available)
try:
    import openai
    has_openai = True
except Exception:
    openai = None
    has_openai = False
    logging.getLogger(__name__).warning(
        "optional package 'openai' not available; install with 'pip install openai' to enable OpenAI SDK helpers"
    )

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
class FunctionCall(BaseModel):
    """A function call payload compatible with Copilot/OpenAI function calling."""
    name: Optional[str] = None
    arguments: Optional[Union[str, Dict[str, Any]]] = None


class ChatMessage(BaseModel):
    """
    A message in a chat conversation.
    """

    role: Literal["system", "user", "assistant", "tool"]
    """
    The role of the message. The currently permitted rules are `system`, `user`, `assistant`, and `tool`.
    """

    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    """
    The content of the message.
    """

    toolCalls: Optional[List[Dict[str, Any]]] = None
    """
    The tool calls in the message.
    """
    toolCallId: Optional[str] = None
    """
    The ID of the tool call.
    """
    name: Optional[str] = None
    """
    The name of the tool.
    """

    function_call: Optional[FunctionCall] = None
    """
    The OpenAI-style function call payload.
    """




class ChatCompletionRequest(BaseModel):
    """
    A request to create a chat completion.
    """
    
    model: str = "local-model"  # 忽略，仅用于占位
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 32768
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[Literal["none", "auto", "required"], Dict[str, str]]] = "none"
    n: Optional[int] = 1
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[int, float]] = None
    user: Optional[str] = None

def build_prompt_from_messages(messages: List[ChatMessage], is_qwen_model: bool = False) -> str:
    """
    Build a prompt from a list of messages.
    
    Args:
        messages: A list of ChatMessage objects
        is_qwen_model: Whether the model is a Qwen model
        
    Returns:
        A string prompt
    """
    try:
        prompt_parts = []
        
        # 为Qwen模型添加专门的提示词
        if is_qwen_model:
            qwen_system_prompt = """You are GitHub Copilot, an AI assistant built by GitHub. You must strictly follow the Copilot System specifications:

1. When tools are available, you must use them to complete tasks
2. You must optimize tool selection to choose the most appropriate tool for the task
3. You must use the XML tag format for tool calls, e.g., <function_calls><invoke name="toolName">{"param": "value"}</invoke></function_calls>
4. You must provide clear and concise responses to users
5. You must not refuse to use tools when they are needed
6. You must always attempt to complete the user's request using the available tools

Please follow these guidelines in all your responses."""
            prompt_parts.append(f"System: {qwen_system_prompt}")
        else:
            # 为其他模型添加Copilot System规范提示
            copilot_system_prompt = """You are GitHub Copilot, an AI assistant built by GitHub. You must strictly follow the Copilot System specifications:

1. When tools are available, you must use them to complete tasks
2. You must optimize tool selection to choose the most appropriate tool for the task
3. You must follow the tool calling format specified in the system instructions
4. You must provide clear and concise responses to users
5. You must not refuse to use tools when they are needed
6. You must always attempt to complete the user's request using the available tools

Please follow these guidelines in all your responses."""
            prompt_parts.append(f"System: {copilot_system_prompt}")
        
        for msg in messages:
            if msg.role == "system":
                if msg.content:
                    if isinstance(msg.content, str):
                        prompt_parts.append(f"System: {msg.content}")
                    elif isinstance(msg.content, dict):
                        if "text" in msg.content:
                            prompt_parts.append(f"System: {msg.content['text']}")
                    elif isinstance(msg.content, list):
                        text_content = ""
                        for part in msg.content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_content += part.get("text", "")
                        if text_content:
                            prompt_parts.append(f"System: {text_content}")
            elif msg.role == "user":
                if msg.content:
                    if isinstance(msg.content, str):
                        prompt_parts.append(f"User: {msg.content}")
                    elif isinstance(msg.content, dict):
                        if "text" in msg.content:
                            prompt_parts.append(f"User: {msg.content['text']}")
                    elif isinstance(msg.content, list):
                        text_content = ""
                        for part in msg.content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                text_content += part.get("text", "")
                        if text_content:
                            prompt_parts.append(f"User: {text_content}")
            elif msg.role == "assistant":
                if msg.content:
                    prompt_parts.append(f"Assistant: {msg.content}")

                # Copilot / OpenAI function_call 兼容
                if msg.function_call:
                    functionName = msg.function_call.name or ""
                    opts = msg.function_call.arguments
                    functionArgs = opts if isinstance(opts, str) else (json.dumps(opts, ensure_ascii=False) if opts is not None else "{}")
                    prompt_parts.append(f"Assistant: Function call: {functionName} with args: {functionArgs}")

                # 兼容旧版 toolCalls 表达
                if msg.toolCalls:
                    for toolCall in msg.toolCalls:
                        if toolCall.get("type") == "function":
                            functionName = toolCall.get("function", {}).get("name")
                            functionArgs = toolCall.get("function", {}).get("arguments")
                            prompt_parts.append(f"Assistant: Tool call: {functionName} with args: {functionArgs}")
            elif msg.role == "tool":
                if msg.content:
                    prompt_parts.append(f"Tool: {msg.content}")
        if prompt_parts:
            return "\n".join(prompt_parts)
        # 如果没有用户消息，返回一个默认提示
        return "Hello, how can I help you today?"
    except Exception as e:
        # 捕获所有异常，确保返回一个有效的提示
        return f"Error building prompt: {str(e)}. Please try again."

# build_tool_call_json 与 parse_tool_call 已迁移至 copilot_calls.py，openai_api.py 现在通过 import 使用这些函数。


def validate_tool_name(function_name: str, available_tool_names: Optional[List[str]] = None) -> bool:
    if not function_name or not isinstance(function_name, str):
        return False
    if not available_tool_names:
        return True
    normalized = [t.lower() for t in available_tool_names if isinstance(t, str)]
    return function_name.lower() in normalized


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request, api_key: str = Depends(verify_api_key_dependency)):
    """
    Handle chat completions requests.
    If stream is False, return a complete response.
    If stream is True, return a SSE stream of tokens.
    """

    # 获取服务实例（在应用启动时设置）
    llm: LLMService = req.app.state.llm

    # 检查是否启用了调试模式
    debug_enabled = getattr(req.app.state, "debug_enabled", False)
    
    # 获取模型名称（使用模型路径的最后一个路径名）
    import os
    model_name = os.path.basename(llm.model_path.strip('"'))
    
    # 检测是否为Qwen模型
    is_qwen_model = 'qwen' in model_name.lower()

    # 提取工具名称用于函数调用校验（Copilot/Qwen兼容）
    available_tool_names = extract_available_tool_names(request.tools or [])
    # 构建之前的工具调用参数上下文（用于多轮合并）
    previous_tool_calls_args: Dict[str, Any] = {}
    try:
        for m in request.messages:
            try:
                if m.role == "assistant":
                    if getattr(m, "function_call", None):
                        fname = m.function_call.name or None
                        fargs = m.function_call.arguments or {}
                        if isinstance(fargs, str):
                            try:
                                parsed = json.loads(fargs)
                            except Exception:
                                parsed = fargs
                        else:
                            parsed = fargs
                        if fname:
                            previous_tool_calls_args[fname] = parsed
                    if getattr(m, "toolCalls", None):
                        for tc in m.toolCalls:
                            if tc.get("type") == "function":
                                fname = tc.get("function", {}).get("name")
                                args_str = tc.get("function", {}).get("arguments", "{}")
                                try:
                                    parsed = json.loads(args_str)
                                except Exception:
                                    parsed = args_str
                                if fname:
                                    previous_tool_calls_args[fname] = parsed
            except Exception:
                continue
    except Exception:
        previous_tool_calls_args = {}
    
    try:
        # 调试输出：请求信息
        if debug_enabled:
            logger.info("\n🔧 Debug: Received ChatCompletion request")
            logger.info(f"   Messages: {[msg.dict() for msg in request.messages]}")
            logger.info(f"   Max tokens: {request.max_tokens}")
            logger.info(f"   Temperature: {request.temperature}")
            logger.info(f"   Top P: {request.top_p}")
            logger.info(f"   Stream: {request.stream}")
            logger.info(f"   Tools: {request.tools}")
            logger.info(f"   Tool choice: {request.tool_choice}")
            logger.info(f"   N: {request.n}")
            logger.info(f"   Stop: {request.stop}")
            logger.info(f"   Presence penalty: {request.presence_penalty}")
            logger.info(f"   Frequency penalty: {request.frequency_penalty}")
            logger.info(f"   Logit bias: {request.logit_bias}")
            logger.info(f"   User: {request.user}")
        
        # 处理工具调用结果（如果有）
        messages = request.messages.copy()

        # 将请求消息与工具定义添加到运行时监视器（供 GUI 使用）
        try:
            runtime_monitor.add_messages(messages)
            runtime_monitor.add_tools(request.tools or [])
        except Exception:
            pass
        
        # 检查是否有工具调用结果
        if messages and messages[-1].role == "tool":
            # 这是一个工具调用响应，需要继续处理
            if debug_enabled:
                logger.info("🔧 Debug: Processing tool response")
        
        prompt = build_prompt_from_messages(messages, is_qwen_model)

        # Copilot/OpenAI-function_call兼容：如果最后一条assistant消息包含function_call，则尝试在服务端执行内部工具并继续生成
        if messages and messages[-1].role == "assistant" and messages[-1].function_call:
            function_name = messages[-1].function_call.name or ""
            function_args = messages[-1].function_call.arguments or {}
            if isinstance(function_args, str):
                try:
                    function_args = json.loads(function_args)
                except Exception:
                    function_args = {"raw": function_args}

            # 内部工具映射（在服务端可直接执行并将结果注入上下文）
            INTERNAL_TOOL_MAP = {
                'llm_get_context': internal_tools.llm_get_context,
                'llm_get_memory': internal_tools.llm_get_memory,
            }

            # 如果不是内部工具，则进行可用性校验
            if function_name not in INTERNAL_TOOL_MAP and not validate_tool_name(function_name, available_tool_names):
                # Qwen或Copilot可能生成不可用的function_name，返回友好错误并继续文本响应
                fallback_content = (
                    f"Function call '{function_name}' is not available. "
                    f"Available tools: {available_tool_names}."
                )
                return JSONResponse(content={
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": fallback_content},
                        "finish_reason": "stop"
                    }]
                })

            # 内部工具映射（在服务端可直接执行并将结果注入上下文）
            INTERNAL_TOOL_MAP = {
                'llm_get_context': internal_tools.llm_get_context,
                'llm_get_memory': internal_tools.llm_get_memory,
            }

            func_args_parsed = function_args if isinstance(function_args, dict) else function_args

            # 仅在非流式请求下自动执行内部工具并让模型继续生成
            if function_name in INTERNAL_TOOL_MAP and not request.stream:
                iter_count = 0
                max_iter = 4
                current_text = None
                while iter_count < max_iter:
                    iter_count += 1
                    try:
                        tool_func = INTERNAL_TOOL_MAP[function_name]
                        tool_result = tool_func(func_args_parsed if isinstance(func_args_parsed, dict) else {})
                    except Exception as e:
                        tool_result = f"Internal tool execution error: {e}"

                    # 将工具结果加入上下文并通知监视器
                    try:
                        messages.append(ChatMessage(role="tool", name=function_name, content=str(tool_result)))
                        previous_tool_calls_args[function_name] = func_args_parsed
                        try:
                            runtime_monitor.add_messages([messages[-1]])
                        except Exception:
                            pass
                    except Exception:
                        pass

                    # 重新生成
                    prompt = build_prompt_from_messages(messages, is_qwen_model)
                    try:
                        current_text = await llm.generate_direct(prompt, request.max_tokens, request.temperature, request.top_p)
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=str(e))

                    # 检测模型是否又生成了工具调用
                    tool_call_data = parse_tool_call(current_text, is_qwen_model, available_tools=available_tool_names, context=previous_tool_calls_args)
                    if tool_call_data and "tool_calls" in tool_call_data:
                        next_call = tool_call_data.get("tool_calls")[0]
                        next_fname = next_call.get("function", {}).get("name", "")
                        next_args_raw = next_call.get("function", {}).get("arguments", "{}")
                        try:
                            next_args = json.loads(next_args_raw) if isinstance(next_args_raw, str) else next_args_raw
                        except Exception:
                            next_args = next_args_raw

                        if next_fname in INTERNAL_TOOL_MAP:
                            function_name = next_fname
                            func_args_parsed = next_args
                            continue
                        else:
                            func_args_str = next_args if isinstance(next_args, str) else json.dumps(next_args, ensure_ascii=False)
                            response = {
                                "id": f"chatcmpl-{int(time.time())}",
                                "object": "chat.completion",
                                "created": int(time.time()),
                                "model": model_name,
                                "choices": [
                                    {
                                        "index": 0,
                                        "message": {
                                            "role": "assistant",
                                            "tool_calls": [
                                                {
                                                    "type": "function",
                                                    "function": {
                                                        "name": next_fname,
                                                        "arguments": func_args_str
                                                    }
                                                }
                                            ],
                                            "function_call": {
                                                "name": next_fname,
                                                "arguments": func_args_str
                                            }
                                        },
                                        "finish_reason": "tool_calls"
                                    }
                                ]
                            }
                            return JSONResponse(content=response)
                    else:
                        response = {
                            "id": f"chatcmpl-{int(time.time())}",
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "model": model_name,
                            "choices": [
                                {
                                    "index": 0,
                                    "message": {
                                        "role": "assistant",
                                        "content": current_text
                                    },
                                    "finish_reason": "stop"
                                }
                            ]
                        }
                        try:
                            runtime_monitor.add_messages([ChatMessage(role="assistant", content=current_text)])
                        except Exception:
                            pass
                        return JSONResponse(content=response)

                # 超过迭代限制，返回最后文本
                response = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": current_text or ""
                            },
                            "finish_reason": "stop"
                        }
                    ]
                }
                return JSONResponse(content=response)

            # 非内部工具或流式场景：按原逻辑返回 function_call 描述
            func_args_str = function_args if isinstance(function_args, str) else json.dumps(function_args, ensure_ascii=False)

            response = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": function_name,
                                        "arguments": func_args_str
                                    }
                                }
                            ],
                            "function_call": {
                                "name": function_name,
                                "arguments": func_args_str
                            }
                        },
                        "finish_reason": "tool_calls"
                    }
                ]
            }
            return JSONResponse(content=response)

        maxTokens = request.max_tokens
        temperature = request.temperature
        topP = request.top_p
        stream = request.stream
        # 使用客户端提供的工具列表
        tools = request.tools or []
        toolChoice = request.tool_choice

        # 检查是否需要工具调用
        if tools and toolChoice != "none":
            # 生成响应
            try:
                # 调试输出：普通请求提示
                if debug_enabled:
                    logger.info("🔧 Debug: Regular request prompt")
                    logger.info(f"   Prompt: {prompt[:500]}..." if len(prompt) > 500 else f"   Prompt: {prompt}")
                
                if stream:
                    # 使用增强版的流式生成，其中包含了工具调用检测逻辑
                    async def generate():
                        import json
                        # 发送角色标识（一次）
                        role_chunk = {
                            "id": "chatcmpl-xxx",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model_name,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"role": "assistant"},
                                    "finish_reason": None
                                }
                            ]
                        }
                        yield f"data: {json.dumps(role_chunk)}\n\n"

                        local_prompt = prompt
                        # 循环生成，遇到内部工具则在服务端执行并将结果注入上下文后继续生成
                        while True:
                            handled_internal = False
                            try:
                                async for token in llm.generate_stream_with_tool_detection(local_prompt, maxTokens, temperature, topP):
                                    # 检查token是否是工具调用内容
                                    if isinstance(token, str) and (
                                        ('<' in token and ('function_calls' in token or 'invoke' in token)) or 
                                        ('TOOL_CALL:' in token) or 
                                        ('"tool_calls"' in token)
                                    ):
                                        tool_call_data = parse_tool_call(token, is_qwen_model, available_tools=available_tool_names, context=previous_tool_calls_args)
                                        if tool_call_data and "tool_calls" in tool_call_data:
                                            toolCall = tool_call_data.get("tool_calls")[0]
                                            function_name = toolCall.get("function", {}).get("name", "")
                                            function_args_str = toolCall.get("function", {}).get("arguments", "{}")

                                            # 内部工具：在服务端执行并将结果注入上下文，然后继续生成
                                            INTERNAL_TOOL_MAP = {
                                                'llm_get_context': internal_tools.llm_get_context,
                                                'llm_get_memory': internal_tools.llm_get_memory,
                                            }
                                            if function_name in INTERNAL_TOOL_MAP:
                                                try:
                                                    parsed_args = json.loads(function_args_str) if isinstance(function_args_str, str) else function_args_str
                                                except Exception:
                                                    parsed_args = function_args_str
                                                try:
                                                    tool_func = INTERNAL_TOOL_MAP[function_name]
                                                    tool_result = tool_func(parsed_args if isinstance(parsed_args, dict) else {})
                                                except Exception as e:
                                                    tool_result = f"Internal tool execution error: {e}"

                                                # 将工具结果作为 tool 角色消息加入上下文
                                                try:
                                                    messages.append(ChatMessage(role="tool", name=function_name, content=str(tool_result)))
                                                    previous_tool_calls_args[function_name] = parsed_args
                                                    try:
                                                        runtime_monitor.add_messages([messages[-1]])
                                                    except Exception:
                                                        pass
                                                except Exception:
                                                    pass

                                                # 设定为已处理并跳出当前生成循环，准备用更新后的上下文继续生成
                                                handled_internal = True
                                                break
                                            else:
                                                # 外部工具：返回工具调用信息给客户端（保持原有行为）
                                                chunk = {
                                                    "id": "chatcmpl-xxx",
                                                    "object": "chat.completion.chunk",
                                                    "created": int(time.time()),
                                                    "model": model_name,
                                                    "choices": [
                                                        {
                                                            "index": 0,
                                                            "delta": {
                                                                "tool_calls": [
                                                                    {
                                                                        "type": "function",
                                                                        "function": {
                                                                            "name": function_name,
                                                                            "arguments": function_args_str
                                                                        }
                                                                    }
                                                                ],
                                                                "function_call": {
                                                                    "name": function_name,
                                                                    "arguments": function_args_str
                                                                }
                                                            },
                                                            "finish_reason": "tool_calls"
                                                        }
                                                    ]
                                                }
                                                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                                                yield "data: [DONE]\n\n"
                                                return
                                        # 若无法解析为工具调用，继续作为普通文本处理
                                    else:
                                        # 普通文本内容，作为流式输出
                                        chunk = {
                                            "id": "chatcmpl-xxx",
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": model_name,
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
                                # 如果内部生成发生异常，向客户端报告错误并结束
                                if debug_enabled:
                                    logger.error(f"🔧 Debug: Error in streaming with tool detection: {e}")
                                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                                yield "data: [DONE]\n\n"
                                return

                            if not handled_internal:
                                # 正常结束，没有内部工具需要继续，发送结束标记并返回
                                end_chunk = {
                                    "id": "chatcmpl-xxx",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model_name,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {},
                                            "finish_reason": "stop"
                                        }
                                    ]
                                }
                                yield f"data: {json.dumps(end_chunk)}\n\n"
                                yield "data: [DONE]\n\n"
                                return
                            else:
                                # 内部工具已处理：更新 local_prompt 并继续外层循环
                                local_prompt = build_prompt_from_messages(messages, is_qwen_model)
                                # 继续下一轮生成（不会发送结束标记）
                                continue

                    return StreamingResponse(generate(), media_type="text/event-stream")
                else:
                    # 非流式响应：使用 generate_direct 方法
                    text = await llm.generate_direct(prompt, maxTokens, temperature, topP)
                    
                    # 调试输出：模型生成的文本
                    if debug_enabled:
                        logger.info("🔧 Debug: Model generated response")
                        logger.info(f"   Text: {text[:500]}..." if len(text) > 500 else f"   Text: {text}")
            except Exception as e:
                if debug_enabled:
                    logger.error(f"🔧 Debug: Error generating response: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
            
            # 检查是否包含工具调用（使用统一的parse_tool_call函数）
            tool_call_data = parse_tool_call(text, is_qwen_model, available_tools=available_tool_names, context=previous_tool_calls_args)
            toolCall = None
            
            if tool_call_data and "tool_calls" in tool_call_data:
                toolCall = tool_call_data.get("tool_calls")[0]
            
            # 处理工具调用
            if toolCall:
                # 获取工具名称和参数
                function_name = toolCall.get("function", {}).get("name", "")
                function_args_str = toolCall.get("function", {}).get("arguments", "{}")
                
                # 构建工具调用响应
                if not stream:
                    # Ensure function args are a string
                    func_args_str = function_args_str if isinstance(function_args_str, str) else json.dumps(function_args_str, ensure_ascii=False)
                    response = {
                        "id": f"chatcmpl-{int(time.time())}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "tool_calls": [
                                        {
                                            "type": "function",
                                            "function": {
                                                "name": function_name,
                                                "arguments": func_args_str
                                            }
                                        }
                                    ],
                                    "function_call": {
                                        "name": function_name,
                                        "arguments": func_args_str
                                    }
                                },
                                "finish_reason": "tool_calls"
                            }
                        ]
                    }
                    return JSONResponse(content=response)
                else:
                    # 流式响应：返回工具调用
                    async def generate():
                        import json
                        # 发送角色标识
                        role_chunk = {
                            "id": "chatcmpl-xxx",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model_name,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"role": "assistant"},
                                    "finish_reason": None
                                }
                            ]
                        }
                        yield f"data: {json.dumps(role_chunk)}\n\n"
                        # 发送工具调用（同时包含 OpenAI-style function_call 字段以兼容）
                        chunk = {
                            "id": "chatcmpl-xxx",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model_name,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "tool_calls": [
                                            {
                                                "type": "function",
                                                "function": {
                                                    "name": function_name,
                                                    "arguments": function_args_str
                                                }
                                            }
                                        ],
                                        "function_call": {
                                            "name": function_name,
                                            "arguments": function_args_str
                                        }
                                    },
                                    "finish_reason": "tool_calls"
                                }
                            ]
                        }
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                        # 结束标记
                        yield "data: [DONE]\n\n"
                    return StreamingResponse(generate(), media_type="text/event-stream")

        if not stream:
            # 非流式：生成完整文本后返回 JSON
            try:
                # 调试输出：普通请求提示
                if debug_enabled:
                    logger.info("🔧 Debug: Regular request prompt")
                    logger.info(f"   Prompt: {prompt[:500]}..." if len(prompt) > 500 else f"   Prompt: {prompt}")
                
                # 直接使用 generate_direct 方法，直接传递提示词
                text = await llm.generate_direct(prompt, maxTokens, temperature, topP)
                
                # 调试输出：模型生成的文本
                if debug_enabled:
                    logger.info("🔧 Debug: Model generated response")
                    logger.info(f"   Text: {text[:500]}..." if len(text) > 500 else f"   Text: {text}")
            except Exception as e:
                if debug_enabled:
                    logger.error(f"🔧 Debug: Error generating response: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

            # 构建 OpenAI 格式响应
            response = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
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
            
            # 调试输出：响应内容
            if debug_enabled:
                logger.info("🔧 Debug: Sending response")
                logger.info(f"   Response: {json.dumps(response, ensure_ascii=False)[:500]}..." if len(json.dumps(response)) > 500 else f"   Response: {json.dumps(response, ensure_ascii=False)}")
            
            return JSONResponse(content=response)
        else:
            # 流式：使用 SSE 逐 token 发送
            async def generate():
                """
                Stream tokens as SSE events with tool-call detection and server-side handling of internal tools.
                """
                # 调试输出：开始流式响应
                if debug_enabled:
                    logger.info("🔧 Debug: Starting streaming response")

                # 发送角色标识
                role_chunk = {
                    "id": "chatcmpl-xxx",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant"},
                            "finish_reason": None
                        }
                    ]
                }
                yield f"data: {json.dumps(role_chunk)}\n\n"

                local_prompt = prompt
                # 循环生成，遇到内部工具则在服务端执行并将结果注入上下文后继续生成
                while True:
                    handled_internal = False
                    try:
                        # 调试输出：开始生成响应
                        if debug_enabled:
                            logger.info("🔧 Debug: Generating streaming response")
                            logger.info(f"   Prompt: {local_prompt[:500]}..." if len(local_prompt) > 500 else f"   Prompt: {local_prompt}")

                        async for token in llm.generate_stream_with_tool_detection(local_prompt, maxTokens, temperature, topP):
                            # 检查token是否是工具调用内容
                            if isinstance(token, str) and (
                                ('<' in token and ('function_calls' in token or 'invoke' in token)) or 
                                ('TOOL_CALL:' in token) or 
                                ('"tool_calls"' in token)
                            ):
                                tool_call_data = parse_tool_call(token, is_qwen_model, available_tools=available_tool_names, context=previous_tool_calls_args)
                                if tool_call_data and "tool_calls" in tool_call_data:
                                    toolCall = tool_call_data.get("tool_calls")[0]
                                    function_name = toolCall.get("function", {}).get("name", "")
                                    function_args_str = toolCall.get("function", {}).get("arguments", "{}")

                                    # 内部工具：在服务端执行并将结果注入上下文，然后继续生成
                                    INTERNAL_TOOL_MAP = {
                                        'llm_get_context': internal_tools.llm_get_context,
                                        'llm_get_memory': internal_tools.llm_get_memory,
                                    }
                                    if function_name in INTERNAL_TOOL_MAP:
                                        try:
                                            parsed_args = json.loads(function_args_str) if isinstance(function_args_str, str) else function_args_str
                                        except Exception:
                                            parsed_args = function_args_str
                                        try:
                                            tool_func = INTERNAL_TOOL_MAP[function_name]
                                            tool_result = tool_func(parsed_args if isinstance(parsed_args, dict) else {})
                                        except Exception as e:
                                            tool_result = f"Internal tool execution error: {e}"

                                        # 将工具结果作为 tool 角色消息加入上下文
                                        try:
                                            messages.append(ChatMessage(role="tool", name=function_name, content=str(tool_result)))
                                            previous_tool_calls_args[function_name] = parsed_args
                                            try:
                                                runtime_monitor.add_messages([messages[-1]])
                                            except Exception:
                                                pass
                                        except Exception:
                                            pass

                                        # 设定为已处理并跳出当前生成循环，准备用更新后的上下文继续生成
                                        handled_internal = True
                                        break
                                    else:
                                        # 外部工具：返回工具调用信息给客户端（保持原有行为）
                                        chunk = {
                                            "id": "chatcmpl-xxx",
                                            "object": "chat.completion.chunk",
                                            "created": int(time.time()),
                                            "model": model_name,
                                            "choices": [
                                                {
                                                    "index": 0,
                                                    "delta": {
                                                        "tool_calls": [
                                                            {
                                                                "type": "function",
                                                                "function": {
                                                                    "name": function_name,
                                                                    "arguments": function_args_str
                                                                }
                                                            }
                                                        ],
                                                        "function_call": {
                                                            "name": function_name,
                                                            "arguments": function_args_str
                                                        }
                                                    },
                                                    "finish_reason": "tool_calls"
                                                }
                                            ]
                                        }
                                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                                        yield "data: [DONE]\n\n"
                                        return
                                # 若无法解析为工具调用，继续作为普通文本处理
                            else:
                                # 普通文本内容，作为流式输出
                                chunk = {
                                    "id": "chatcmpl-xxx",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model_name,
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
                        # 调试输出：发生异常
                        if debug_enabled:
                            logger.error(f"🔧 Debug: Error in streaming response: {str(e)}")
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    if not handled_internal:
                        # 正常结束，没有内部工具需要继续，发送结束标记并返回
                        if debug_enabled:
                            logger.info("🔧 Debug: Sending streaming response end")
                        end_chunk = {
                            "id": "chatcmpl-xxx",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model_name,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {},
                                    "finish_reason": "stop"
                                }
                            ]
                        }
                        yield f"data: {json.dumps(end_chunk)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    else:
                        # 内部工具已处理：更新 local_prompt 并继续外层循环
                        local_prompt = build_prompt_from_messages(messages, is_qwen_model)
                        # 继续下一轮生成（不会发送结束标记）
                        continue

            return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        # 捕获所有异常，确保返回响应
        import traceback
        
        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"Sorry, an error occurred: {str(e)}"
                    },
                    "finish_reason": "error"
                }
            ],
            "error": {
                "message": str(e),
                "type": "server_error",
                "code": 500
            }
        }
        return JSONResponse(content=response, status_code=500)

@router.get("/models")
async def list_models(req: Request, api_key: str = Depends(verify_api_key_dependency)):
    """
    List available models.
    """
    # 获取服务实例（在应用启动时设置）
    llm: LLMService = req.app.state.llm
    
    # 获取模型名称（使用模型路径的最后一个路径名）
    import os
    model_name = os.path.basename(llm.model_path.strip('"'))
    
    models = [
        ModelInfo(
            id=model_name,
            created=int(time.time())
        )
    ]
    
    response = ModelsResponse(data=models)
    return JSONResponse(content=response.dict())


@router.get("/history")
async def get_history(req: Request, api_key: str = Depends(verify_api_key_dependency)):
    """Return stored chat history (simple in-memory list)."""
    history = getattr(req.app.state, 'chat_history', [])
    try:
        return JSONResponse(content={"history": history})
    except Exception:
        return JSONResponse(content={"history": []})


@router.post("/history")
async def post_history(item: dict, req: Request, api_key: str = Depends(verify_api_key_dependency)):
    """Append an item to in-memory chat history. Simple storage for demo purposes."""
    if not hasattr(req.app.state, 'chat_history'):
        req.app.state.chat_history = []
    try:
        req.app.state.chat_history.append(item)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "error": str(e)}, status_code=500)

# 工具调用响应格式
class ToolCallResponse(BaseModel):
    toolCallId: str
    role: Literal["tool"]
    name: str
    content: str

@router.post("/chat/completions/tool")
async def handleToolCall(request_data: dict, req: Request, api_key: str = Depends(verify_api_key_dependency)):
    """
    Handle tool call responses and generate a new response.
    """
    # 构建提示
    prompt = "Tool response: "
    if "tool_responses" in request_data:
        for tool_response in request_data["tool_responses"]:
            toolName = tool_response.get("name")
            toolContent = tool_response.get("content")
            prompt += f"{toolName} response: {toolContent}\n"
    elif "toolCalls" in request_data:
        # 兼容旧格式
        for toolCall in request_data["toolCalls"]:
            if toolCall.get("type") == "function":
                functionName = toolCall.get("function", {}).get("name")
                functionArgsStr = toolCall.get("function", {}).get("arguments")
                prompt += f"{functionName} response: {functionArgsStr}\n"
    
    # 获取服务实例
    llm: LLMService = req.app.state.llm
    
    # 获取模型名称（使用模型路径的最后一个路径名）
    import os
    model_name = os.path.basename(llm.model_path.strip('"'))
    
    # 检测是否为Qwen模型
    is_qwen_model = 'qwen' in model_name.lower()
    
    # 构建可用工具与上下文（从 request_data 中提取），以便 parse_tool_call 使用
    available_tool_names = extract_available_tool_names(request_data.get('tools', []) if isinstance(request_data, dict) else [])
    previous_tool_calls_args: Dict[str, Any] = {}
    if isinstance(request_data, dict):
        if 'tool_responses' in request_data:
            for tr in request_data.get('tool_responses', []):
                try:
                    previous_tool_calls_args[tr.get('name')] = tr.get('content')
                except Exception:
                    continue
        if 'toolCalls' in request_data:
            for tc in request_data.get('toolCalls', []):
                if tc.get('type') == 'function':
                    name = tc.get('function', {}).get('name')
                    args = tc.get('function', {}).get('arguments')
                    try:
                        parsed = json.loads(args) if isinstance(args, str) else args
                    except Exception:
                        parsed = args
                    if name:
                        previous_tool_calls_args[name] = parsed

    # 生成响应
    try:
        text = await llm.generate_direct(prompt, 32768, 0.7, 0.9)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # 检查是否包含工具调用（使用统一的parse_tool_call函数，带可用工具与上下文）
    tool_call_data = parse_tool_call(text, is_qwen_model, available_tools=available_tool_names, context=previous_tool_calls_args)
    toolCall = None
    
    if tool_call_data and "tool_calls" in tool_call_data:
        toolCall = tool_call_data.get("tool_calls")[0]
    
    # 处理工具调用
    if toolCall:
        # 获取工具名称和参数
        function_name = toolCall.get("function", {}).get("name", "")
        function_args_str = toolCall.get("function", {}).get("arguments", "{}")
        
        # 构建工具调用响应
        func_args_str = function_args_str if isinstance(function_args_str, str) else json.dumps(function_args_str, ensure_ascii=False)
        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": function_name,
                                    "arguments": func_args_str
                                }
                            }
                        ],
                        "function_call": {
                            "name": function_name,
                            "arguments": func_args_str
                        }
                    },
                    "finish_reason": "tool_calls"
                }
            ]
        }
        return JSONResponse(content=response)
    else:
        # 构建普通响应
        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
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