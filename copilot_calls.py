import json
import re
import difflib
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def _normalize_tool_calls_payload(payload: dict) -> Optional[dict]:
    """Normalize payload to OpenAI standard tool_calls format."""
    if not isinstance(payload, dict):
        return None

    if "tool_calls" in payload:
        return {"tool_calls": payload.get("tool_calls")}

    if "toolCalls" in payload:
        return {"tool_calls": payload.get("toolCalls")}

    if "function_call" in payload:
        func = payload.get("function_call")
        if not isinstance(func, dict):
            return None
        name = func.get("name")
        if not name:
            return None
        args = func.get("arguments", {})
        # Allow string arguments or dict
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                # leave as string if not JSON
                pass

        return {
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False)
                    }
                }
            ]
        }

    return None


def build_tool_call_json(tool_call_str: str) -> Optional[dict]:
    """Parse legacy TOOL_CALL formats into canonical tool_calls payload."""
    if not isinstance(tool_call_str, str) or not tool_call_str.strip():
        return None

    text = tool_call_str.strip()

    try:
        if text.startswith("TOOL_CALL:"):
            tool_call_data = text[len("TOOL_CALL:"):]
            if ":" in tool_call_data:
                tool_name, args_str = tool_call_data.split(":", 1)
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {"raw": args_str}

                return {
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": tool_name.strip(),
                                "arguments": json.dumps(args, ensure_ascii=False)
                            }
                        }
                    ]
                }

        if text.startswith("TOOL_CALL_"):
            tool_name = text[len("TOOL_CALL_"):].strip()
            return {
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps({}, ensure_ascii=False)
                        }
                    }
                ]
            }

    except Exception as ex:
        logger.warning("build_tool_call_json parse failed: %s", ex)

    return None


def parse_tool_call(text: str, is_qwen_model: bool = False, available_tools: Optional[List[str]] = None, context: Optional[Dict[str, Any]] = None) -> Optional[dict]:
    """Parse a string from model output into tool_calls payload.

    Supports OpenAI function_call, old tool_calls, TOOL_CALL formats, Qwen XML format.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    text = text.strip()

    # 1) Try explicit JSON detection
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            extracted = json.loads(json_match.group(0))
            parsed = _normalize_tool_calls_payload(extracted)
            if parsed:
                # 如果提供了上下文，则尝试合并参数
                if context:
                    _merge_with_context(parsed, context)
                if _validate_tool_calls(parsed, available_tools):
                    return parsed
        except Exception:
            pass

    # 2) Try legacy TOOL_CALL format
    legacy = build_tool_call_json(text)
    if legacy:
        if context:
            _merge_with_context(legacy, context)
        if _validate_tool_calls(legacy, available_tools):
            return legacy

    # 3) Try Qwen XML style
    xml_match = re.search(r'<function_calls>\s*<invoke\s+name=["\']([^"\']+)["\']>([\s\S]*?)</invoke>\s*</function_calls>', text, re.IGNORECASE)
    if xml_match:
        tool_name = xml_match.group(1)
        args_str = xml_match.group(2).strip()
        try:
            args = json.loads(args_str)
        except Exception:
            # fallback: raw content as argument value
            args = {"content": args_str}

        parsed = {
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args, ensure_ascii=False)
                    }
                }
            ]
        }
        if context:
            _merge_with_context(parsed, context)
        if _validate_tool_calls(parsed, available_tools):
            return parsed
        else:
            return None

    # 4) Fallback for Qwen simple tags <toolName>{...}</toolName>
    xml_simple = re.search(r'<([a-zA-Z0-9_]+)>([\s\S]*?)</\1>', text)
    if xml_simple:
        tool_name = xml_simple.group(1)
        args_str = xml_simple.group(2).strip()
        try:
            args = json.loads(args_str)
        except Exception:
            args = {"content": args_str}

        parsed = {
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args, ensure_ascii=False)
                    }
                }
            ]
        }
        if context:
            _merge_with_context(parsed, context)
        if _validate_tool_calls(parsed, available_tools):
            return parsed

    if is_qwen_model:
        # Qwen may also output natural-language tool directives
        qwen_direct = re.search(r'工具[:：]\s*([a-zA-Z0-9_]+)\s*(\{[\s\S]*\})?', text)
        if qwen_direct:
            tool_name = qwen_direct.group(1)
            args_str = qwen_direct.group(2) or "{}"
            try:
                args = json.loads(args_str)
            except Exception:
                args = {"content": args_str.strip()}

            parsed = {
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(args, ensure_ascii=False)
                        }
                    }
                ]
            }
            if context:
                _merge_with_context(parsed, context)
            if _validate_tool_calls(parsed, available_tools):
                return parsed

    return None


def _merge_with_context(parsed_payload: dict, context: Dict[str, Any]) -> None:
    """Merge existing parsed tool call arguments with previous context arguments.

    This function mutates parsed_payload in place. It tries to parse JSON
    arguments and will prefer newer keys from the parsed payload while filling
    missing keys from the provided context.
    """
    try:
        if not parsed_payload or "tool_calls" not in parsed_payload:
            return
        calls = parsed_payload.get("tool_calls", [])
        for call in calls:
            func = call.get("function", {})
            name = func.get("name")
            args_str = func.get("arguments", "{}")

            # parse current args
            try:
                cur_args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except Exception:
                cur_args = args_str

            # find previous args from context (case-insensitive)
            prev_args = None
            if isinstance(context, dict):
                if name in context:
                    prev_args = context[name]
                else:
                    lower_map = {k.lower(): k for k in context.keys()}
                    if name and name.lower() in lower_map:
                        prev_args = context[lower_map[name.lower()]]

            # parse previous args if string
            if isinstance(prev_args, str):
                try:
                    prev_args = json.loads(prev_args)
                except Exception:
                    prev_args = prev_args

            # Merge when both are dicts
            if isinstance(prev_args, dict) and isinstance(cur_args, dict):
                merged = {**prev_args, **cur_args}
                call["function"]["arguments"] = json.dumps(merged, ensure_ascii=False)
            else:
                # If current args empty, fall back to previous
                if (cur_args == {} or cur_args is None or cur_args == "") and prev_args is not None:
                    call["function"]["arguments"] = json.dumps(prev_args, ensure_ascii=False) if isinstance(prev_args, dict) else json.dumps({"content": str(prev_args)}, ensure_ascii=False)
                else:
                    # Ensure it's a JSON string
                    if isinstance(cur_args, dict):
                        call["function"]["arguments"] = json.dumps(cur_args, ensure_ascii=False)
                    else:
                        call["function"]["arguments"] = json.dumps({"content": str(cur_args)}, ensure_ascii=False)
    except Exception as e:
        logger.debug("Failed merging context into tool call payload: %s", e)


def _validate_tool_calls(payload: dict, available_tools: Optional[List[str]] = None) -> bool:
    """Validate tool_calls for valid structure and optional tool availability."""
    if not payload or "tool_calls" not in payload:
        return False

    calls = payload.get("tool_calls")
    if not isinstance(calls, list) or len(calls) == 0:
        return False

    for call in calls:
        if not isinstance(call, dict):
            return False
        if call.get("type") != "function":
            return False
        func = call.get("function")
        if not isinstance(func, dict):
            return False
        name = func.get("name")
        args = func.get("arguments")
        if not name or not isinstance(name, str):
            return False
        if not isinstance(args, str):
            return False

        if available_tools is not None:
            tool_names = [str(t).strip() for t in available_tools if t is not None]
            if name not in tool_names and name.lower() not in [t.lower() for t in tool_names]:
                # 尝试模糊匹配并自动修正（容忍大小写/小幅拼写差异）
                lower_tool_map = {t.lower(): t for t in tool_names}
                close = difflib.get_close_matches(name.lower(), list(lower_tool_map.keys()), n=1, cutoff=0.6)
                if close:
                    corrected = lower_tool_map.get(close[0])
                    logger.info("Auto-correcting tool name '%s' -> '%s' using fuzzy match", name, corrected)
                    func['name'] = corrected
                else:
                    logger.warning("Tool name '%s' not found in available tools %s", name, tool_names)
                    return False

    return True


def extract_available_tool_names(tools: Optional[List[Dict[str, Any]]]) -> List[str]:
    if not tools:
        return []
    names = []
    for t in tools:
        if isinstance(t, dict):
            n = t.get("name") or t.get("id") or t.get("tool_name")
            if isinstance(n, str) and n.strip():
                names.append(n.strip())
    return names
