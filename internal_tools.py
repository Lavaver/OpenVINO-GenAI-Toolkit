"""
Internal tools that can be invoked by the LLM via function/tool calls.
These tools are executed locally by the backend (or by the console) and
return textual summaries that the model can consume and report to the user.
"""
import json
import runtime_monitor

try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    psutil = None
    _HAS_PSUTIL = False

def llm_get_context(args=None, max_messages=20):
    """Return a concise textual summary of the current LLM context.

    Args may include 'max_messages' to control how many recent messages are shown.
    """
    try:
        try:
            mm = int(args.get('max_messages')) if isinstance(args, dict) and args.get('max_messages') else max_messages
        except Exception:
            mm = max_messages

        snap = runtime_monitor.get_snapshot(max_messages=mm)
        tokens = snap.get('tokens_estimate', 0)
        capacity = snap.get('capacity', 0)
        breakdown = snap.get('breakdown', {})

        parts = []
        parts.append(f"Context tokens estimate: {tokens} / {capacity} ({int(tokens*100/capacity) if capacity else 0}%)")
        parts.append("Breakdown:")
        for k, v in breakdown.items():
            parts.append(f" - {k}: {v}")

        parts.append("")
        parts.append("Recent messages:")
        msgs = snap.get('messages', [])[-mm:]
        for m in msgs:
            role = m.get('role') or 'unknown'
            name = m.get('name') or ''
            content = (m.get('content') or '').replace('\n', ' ')[:800]
            label = f"{role}{(' ('+name+')') if name else ''}: {content}"
            parts.append(label)

        return "\n".join(parts)
    except Exception as e:
        return f"Error getting context snapshot: {e}"


def llm_get_memory(args=None):
    """Return a textual summary of current system and process memory usage.
    """
    try:
        if _HAS_PSUTIL:
            vm = psutil.virtual_memory()
            proc = psutil.Process()
            rss = proc.memory_info().rss
            parts = []
            parts.append(f"System memory: total={int(vm.total/1024/1024)} MB, available={int(vm.available/1024/1024)} MB, used={int((vm.total-vm.available)/1024/1024)} MB ({vm.percent}%)")
            parts.append(f"Process RSS: {int(rss/1024/1024)} MB")
            return "\n".join(parts)
        else:
            return "psutil not installed; memory stats are unavailable. Install psutil to enable detailed memory monitoring."
    except Exception as e:
        return f"Error getting memory stats: {e}"
