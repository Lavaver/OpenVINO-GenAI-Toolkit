import argparse
import time
import threading
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.box import ROUNDED
from llm_service import LLMService
from asciiart import print_ascii_art
from wintoast import sendToast
from copilot_calls import parse_tool_call, extract_available_tool_names
from openai_api import build_prompt_from_messages, ChatMessage
import internal_tools
import json
import ast
import operator as _operator

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from i18n import _

THINK_START = "<think>"
THINK_END = "</think>"

def main():
    # 打印ASCII艺术
    print_ascii_art()
    parser = argparse.ArgumentParser(description="OpenVINO GenAI Console Client")
    parser.add_argument("model_path", help=_('cli.model_path.help'))
    parser.add_argument("prompt", nargs='?', default=None, help=_('cli.prompt.help'))
    parser.add_argument("-d", "--device", default="AUTO", help=_('cli.device.help'))
    parser.add_argument("-m", "--max-tokens", type=int, default=32768, help=_('cli.max_tokens.help'))
    parser.add_argument("-t", "--temperature", type=float, default=0.7, help=_('cli.temperature.help'))
    parser.add_argument("-p", "--top-p", type=float, default=0.9, help=_('cli.top_p.help'))
    parser.add_argument("-s", "--stream", action="store_true", help=_('cli.stream.help'))
    parser.add_argument("-b", "--box",default="ROUNDED", help=_('cli.box.help'))

    args = parser.parse_args()
    console = Console()
    console.clear()

    # 已移除 MCP 支持（保持简洁的本地控制台会话）

    # 初始化服务
    llm = LLMService(args.model_path, args.device)

    # --- 工具注册（示例：echo/time/calc/read_file） ---
    def _safe_eval(expr: str):
        """Safely evaluate a simple arithmetic expression using AST."""
        operators = {
            ast.Add: _operator.add,
            ast.Sub: _operator.sub,
            ast.Mult: _operator.mul,
            ast.Div: _operator.truediv,
            ast.FloorDiv: _operator.floordiv,
            ast.Mod: _operator.mod,
            ast.Pow: _operator.pow,
            ast.USub: _operator.neg,
        }

        def _eval(node):
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError("Unsupported constant type")
            if isinstance(node, ast.Num):
                return node.n
            if isinstance(node, ast.BinOp):
                left = _eval(node.left)
                right = _eval(node.right)
                op_type = type(node.op)
                if op_type in operators:
                    return operators[op_type](left, right)
                raise ValueError("Unsupported binary operator")
            if isinstance(node, ast.UnaryOp):
                operand = _eval(node.operand)
                op_type = type(node.op)
                if op_type in operators:
                    return operators[op_type](operand)
                raise ValueError("Unsupported unary operator")
            raise ValueError("Unsupported expression")

        parsed = ast.parse(expr, mode="eval")
        return _eval(parsed.body)

    def tool_echo(args):
        return str(args)

    def tool_time(args):
        return time.ctime()

    def tool_calc(args):
        if isinstance(args, dict):
            expr = args.get("expr") or args.get("expression") or args.get("content") or ""
        else:
            expr = str(args)
        try:
            res = _safe_eval(str(expr))
            return str(res)
        except Exception as e:
            return f"Calc error: {e}"

    def tool_read_file(args):
        if isinstance(args, dict):
            path = args.get("path") or args.get("file") or args.get("filename")
        else:
            path = str(args)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            # 限制输出长度以避免控制台被塞满
            return data[:4000]
        except Exception as e:
            return f"Read file error: {e}"

    tools_registry = {
        "echo": {"func": tool_echo, "desc": "Echo input back"},
        "time": {"func": tool_time, "desc": "Return current system time"},
        "calc": {"func": tool_calc, "desc": "Evaluate arithmetic expression (arg key: expr)"},
        "read_file": {"func": tool_read_file, "desc": "Read a local file (arg key: path)"},
        "llm_get_context": {"func": (lambda args: internal_tools.llm_get_context(args)), "desc": "Get LLM context snapshot"},
        "llm_get_memory": {"func": (lambda args: internal_tools.llm_get_memory(args)), "desc": "Get system/process memory stats"},
    }

    tool_names = list(tools_registry.keys())

    # 会话状态和上下文
    messages = []
    previous_tool_calls_args = {}

    # 启动交互式会话（长驻）
    console.print(f"[dim]{_('console.session.started')}[/dim]")

    # 初始用户输入
    if args.prompt:
        user_input = args.prompt
    else:
        user_input = console.input(f"You: ")

    try:
        while True:
            if not user_input:
                user_input = console.input("You: ")
                continue

            cmd = user_input.strip()
            cmd_lower = cmd.lower()
            if cmd_lower in ("/exit", "exit", "quit"):
                console.print(f"[green]{_('console.session.ended')}[/green]")
                break

            if cmd_lower in ("/tools", "tools"):
                console.print(_('console.tools.available'))
                for n, t in tools_registry.items():
                    console.print(f" - {n}: {t.get('desc')}")
                user_input = console.input("You: ")
                continue

            if cmd_lower in ("/help", "help"):
                console.print(f"[bold]{_('console.commands.title')}[/bold]")
                console.print(_('console.commands.help'))
                console.print(_('console.commands.tools'))
                console.print(_('console.commands.history'))
                console.print(_('console.commands.save'))
                console.print(_('console.commands.set'))
                console.print(_('console.commands.model'))
                console.print(_('console.commands.last'))
                console.print(_('console.commands.reset'))
                console.print(_('console.commands.exit'))
                user_input = console.input("You: ")
                continue

            if cmd_lower in ("/model", "model"):
                console.print(_('console.model.path', path=llm.model_path))
                user_input = console.input("You: ")
                continue

            if cmd_lower in ("/last", "/lastreply"):
                last_assistant = next((m for m in reversed(messages) if getattr(m, 'role', '') == 'assistant'), None)
                if last_assistant:
                    console.print(Panel(Markdown(last_assistant.content), title=_('console.last.reply'), box=ROUNDED, border_style="cyan", padding=(0,1)))
                else:
                    console.print(f"[dim]{_('console.no.replies')}[/dim]")
                user_input = console.input("You: ")
                continue

            if cmd_lower.startswith("/history"):
                parts = cmd.split()
                n = None
                if len(parts) > 1:
                    try:
                        n = int(parts[1])
                    except Exception:
                        n = None
                msgs = messages[-n:] if n else messages
                console.print(f"[bold]{_('console.history.title')}[/bold]")
                start_idx = max(1, len(messages) - len(msgs) + 1)
                for i, m in enumerate(msgs, start=start_idx):
                    role = getattr(m, 'role', 'unknown')
                    name = getattr(m, 'name', None)
                    content = (getattr(m, 'content', '') or '')[:1000].replace("\n", " ")
                    label = f"{i}.{role}" + (f" ({name})" if name else "")
                    console.print(f"{label}: {content}")
                user_input = console.input("You: ")
                continue

            if cmd_lower.startswith("/save"):
                parts = cmd.split()
                fname = parts[1] if len(parts) > 1 else f"session_{int(time.time())}.json"
                try:
                    def _msg_to_dict(m):
                        return {"role": getattr(m, 'role', None), "name": getattr(m, 'name', None), "content": getattr(m, 'content', None)}
                    payload = [_msg_to_dict(m) for m in messages]
                    with open(fname, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False, indent=2)
                    console.print(f"[green]{_('console.save.success', filename=fname)}[/green]")
                except Exception as e:
                    console.print(f"[red]{_('console.save.failed', error=e)}[/red]")
                user_input = console.input("You: ")
                continue

            if cmd_lower.startswith("/set "):
                parts = cmd.split()
                if len(parts) < 3:
                    console.print(f"[yellow]{_('console.set.usage')}[/yellow]")
                    user_input = console.input("You: ")
                    continue
                _, param, value = parts[0], parts[1], parts[2]
                p = param.lower()
                try:
                    if p in ("temperature", "temp"):
                        args.temperature = float(value)
                        console.print(_('console.set.temperature', value=args.temperature))
                    elif p in ("top_p", "topp"):
                        args.top_p = float(value)
                        console.print(_('console.set.top_p', value=args.top_p))
                    elif p in ("max_tokens", "max-tokens", "max"):
                        args.max_tokens = int(value)
                        console.print(_('console.set.max_tokens', value=args.max_tokens))
                    elif p == "stream":
                        args.stream = value.lower() in ("1","true","on","yes")
                        console.print(_('console.set.stream', value=args.stream))
                    else:
                        console.print(f"[yellow]{_('console.set.unknown', param=param)}[/yellow]")
                except Exception as e:
                    console.print(f"[red]{_('console.set.failed', error=e)}[/red]")
                user_input = console.input("You: ")
                continue

            if cmd_lower in ("/reset", "reset"):
                messages = []
                previous_tool_calls_args = {}
                console.print(f"[dim]{_('console.context.cleared')}[/dim]")
                user_input = console.input("You: ")
                continue

            # 添加用户消息
            messages.append(ChatMessage(role="user", content=user_input))

            # 运行生成并处理可能的工具调用（会循环直到没有工具调用）
            import asyncio

            while True:
                model_name = os.path.basename(llm.model_path.strip('"'))
                is_qwen_model = 'qwen' in model_name.lower()
                prompt = build_prompt_from_messages(messages, is_qwen_model)

                if args.stream:
                    # 简化的流式：在检测到工具调用时停止当前流并执行工具
                    raw = ""
                    async def _stream_once():
                        nonlocal raw
                        async for token in llm.generate_stream_with_tool_detection(prompt, args.max_tokens, args.temperature, args.top_p):
                            raw += str(token)
                            console.print(str(token), end="", highlight=False)
                            # 检查是否为工具调用
                            maybe = parse_tool_call(raw, is_qwen_model, available_tools=tool_names, context=previous_tool_calls_args)
                            if maybe:
                                return maybe, raw
                        return None, raw

                    maybe_call, raw_text = asyncio.run(_stream_once())
                    console.print("\n")
                    if maybe_call:
                        tool_payload = maybe_call
                    else:
                        # 没有工具调用，将流文本作为assistant回复
                        messages.append(ChatMessage(role="assistant", content=raw_text))
                        break
                else:
                    text = asyncio.run(llm.generate(prompt, args.max_tokens, args.temperature, args.top_p))
                    # 检测工具调用
                    tool_payload = parse_tool_call(text, is_qwen_model, available_tools=tool_names, context=previous_tool_calls_args)
                    if not tool_payload:
                        # 普通回复
                        messages.append(ChatMessage(role="assistant", content=text))
                        console.print(Panel(Markdown(text), title=f"✨ {_('console.answer.title')}", box=ROUNDED, border_style="magenta", padding=(0,1)))
                        break

                # 处理工具调用
                if tool_payload and "tool_calls" in tool_payload:
                    toolCall = tool_payload.get("tool_calls")[0]
                    fname = toolCall.get("function", {}).get("name")
                    fargs_raw = toolCall.get("function", {}).get("arguments", "{}")
                    try:
                        fargs = json.loads(fargs_raw) if isinstance(fargs_raw, str) else fargs_raw
                    except Exception:
                        fargs = fargs_raw

                    # 自动修正/模糊匹配已在 copilot_calls 中处理，直接查找工具实现
                    if fname in tools_registry:
                        try:
                            result = tools_registry[fname]["func"](fargs)
                        except Exception as e:
                            result = _('tool.execution.error', error=e)
                    else:
                        result = _('tool.call.not.available', function=fname, tools=', '.join(tool_names))

                    # 将工具结果作为 tool 角色消息加入上下文，并记录参数用于后续合并
                    messages.append(ChatMessage(role="tool", name=fname, content=str(result)))
                    previous_tool_calls_args[fname] = fargs
                    # 继续循环以生成 assistant 对工具结果的后续回复
                    continue
                else:
                    # 没有有效工具调用（兜底）
                    break

            # 等待下一轮用户输入
            user_input = console.input("You: ")
    except KeyboardInterrupt:
        console.print(f"\n[red]{_('console.interrupted.message')}[/red]")
    finally:
        sendToast(_('console.session.title'), _('console.session.finished'))

if __name__ == "__main__":
    main()