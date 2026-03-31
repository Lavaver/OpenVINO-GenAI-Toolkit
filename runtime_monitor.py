import threading
import json
from collections import deque

_lock = threading.Lock()
_messages = deque(maxlen=2000)
_tools = []
_capacity_tokens = 192000

def _flatten_content(c):
    try:
        if c is None:
            return ""
        if isinstance(c, str):
            return c
        if isinstance(c, (list, dict)):
            return json.dumps(c, ensure_ascii=False)
        return str(c)
    except Exception:
        return str(c)

def add_messages(messages):
    """
    Add a list of messages to the in-memory context monitor.
    Each message may be a pydantic model or a plain dict; we convert to a simple dict.
    """
    try:
        with _lock:
            for m in messages:
                try:
                    # If pydantic model
                    if hasattr(m, 'dict'):
                        md = m.dict()
                    elif isinstance(m, dict):
                        md = m
                    else:
                        # unknown object
                        md = {"role": getattr(m, 'role', None), "name": getattr(m, 'name', None), "content": getattr(m, 'content', None)}

                    role = md.get('role')
                    name = md.get('name')
                    content = _flatten_content(md.get('content'))
                    _messages.append({"role": role, "name": name, "content": content})
                except Exception:
                    continue
    except Exception:
        pass

def add_tools(tools):
    """Register tool definitions (list of dicts)."""
    try:
        with _lock:
            _tools.clear()
            if tools:
                for t in tools:
                    try:
                        if isinstance(t, dict):
                            _tools.append(t)
                        else:
                            _tools.append({"name": getattr(t, 'name', str(t)), "desc": getattr(t, 'description', '')})
                    except Exception:
                        continue
    except Exception:
        pass

def clear():
    with _lock:
        _messages.clear()
        _tools.clear()

def get_snapshot(max_messages=200):
    """
    Return a snapshot used by the GUI: token estimate, capacity, breakdown, recent messages and tools.
    """
    with _lock:
        msgs = list(_messages)
        tools = list(_tools)

    # Estimate tokens: rough heuristic 4 chars per token
    char_count = sum(len((m.get('content') or '')) for m in msgs)
    tokens = max(0, int(char_count / 4))
    capacity = _capacity_tokens

    # Breakdown
    breakdown = {
        'System Instructions': 0,
        'Tool Definitions': 0,
        'User Context': 0,
        'Tool Results': 0,
        'Files': 0,
    }
    for m in msgs:
        role = (m.get('role') or '').lower()
        length = len(m.get('content') or '')
        t = int(length / 4)
        if role == 'system':
            breakdown['System Instructions'] += t
        elif role == 'tool':
            breakdown['Tool Results'] += t
        elif role == 'user':
            breakdown['User Context'] += t
        elif role == 'assistant':
            # treat assistant text as user-facing content
            breakdown['User Context'] += t
        else:
            breakdown['User Context'] += t

    # tool definitions token estimate
    tool_def_chars = sum(len(json.dumps(t, ensure_ascii=False)) for t in tools)
    breakdown['Tool Definitions'] = int(tool_def_chars / 4)

    # files - placeholder (no file monitoring implemented)
    breakdown['Files'] = 0

    # prepare recent messages
    recent = msgs[-max_messages:]

    return {
        'tokens_estimate': tokens,
        'capacity': capacity,
        'breakdown': breakdown,
        'messages': recent,
        'tools': tools
    }
