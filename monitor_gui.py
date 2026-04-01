import tkinter as tk
from tkinter import ttk
import threading
import time
import runtime_monitor

try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    psutil = None
    _HAS_PSUTIL = False

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from i18n import _


def start_monitor_gui(poll_interval_ms: int = 1000):
    """
    Start the runtime monitor GUI. This blocks (Tk mainloop) and should be run in the main thread.
    """
    root = tk.Tk()
    root.title(_('gui.title'))
    root.geometry("1000x480")

    # Left: context window
    left = ttk.Frame(root)
    left.pack(side='left', fill='both', expand=True, padx=6, pady=6)

    title = ttk.Label(left, text=_('gui.context.window'), font=(None, 14, 'bold'))
    title.pack(anchor='w')

    tokens_label = ttk.Label(left, text=_('gui.tokens'))
    tokens_label.pack(anchor='w')

    breakdown_box = tk.Text(left, height=5, wrap='none')
    breakdown_box.pack(fill='x', pady=(4, 6))

    msgs_label = ttk.Label(left, text=_('gui.recent.messages'))
    msgs_label.pack(anchor='w')

    listbox = tk.Listbox(left)
    listbox.pack(fill='both', expand=True)

    btn_frame = ttk.Frame(left)
    btn_frame.pack(fill='x')

    def compress_conversation():
        runtime_monitor.clear()
        listbox.delete(0, tk.END)
        breakdown_box.delete('1.0', tk.END)
        tokens_label.config(text=_('gui.tokens'))

    compress_btn = ttk.Button(btn_frame, text=_('gui.compress.conversation'), command=compress_conversation)
    compress_btn.pack(side='left')

    # Right: memory graph
    right = ttk.Frame(root)
    right.pack(side='right', fill='y', padx=6, pady=6)

    mem_title = ttk.Label(right, text=_('gui.memory.usage'), font=(None, 14, 'bold'))
    mem_title.pack()

    canvas_w = 480
    canvas_h = 260
    mem_canvas = tk.Canvas(right, width=canvas_w, height=canvas_h, bg='#0b0b0b')
    mem_canvas.pack()

    mem_label = ttk.Label(right, text=_('gui.memory.used'))
    mem_label.pack(pady=(6,0))

    mem_history = []

    def update():
        snapshot = runtime_monitor.get_snapshot(200)
        tokens = snapshot.get('tokens_estimate', 0)
        capacity = snapshot.get('capacity', 192000)
        pct = int(tokens*100/capacity) if capacity else 0
        tokens_label.config(text=f"Tokens: {tokens}/{capacity} ({pct}%)")

        breakdown = snapshot.get('breakdown', {})
        breakdown_box.delete('1.0', tk.END)
        for k, v in breakdown.items():
            breakdown_box.insert(tk.END, f"{k}: {v}\n")

        # update listbox
        listbox.delete(0, tk.END)
        for m in snapshot.get('messages', [])[-200:]:
            role = m.get('role') or ''
            name = m.get('name') or ''
            content = (m.get('content') or '').replace('\n',' ')[:200]
            label = f"{role}{(' ('+name+')') if name else ''}: {content}"
            listbox.insert(tk.END, label)

        # memory
        try:
            if _HAS_PSUTIL:
                vm = psutil.virtual_memory()
                used_mb = int((vm.total - vm.available) / 1024 / 1024)
                mem_label.config(text=f"Used: {used_mb} MB ({vm.percent}%)")
                mem_history.append(vm.percent)
            else:
                mem_label.config(text=_('gui.psutil.not.installed'))
        except Exception:
            mem_label.config(text=_('gui.mem.read.error'))

        # draw history
        mem_canvas.delete('all')
        if mem_history:
            history = mem_history[-(canvas_w//2):]
            maxv = 100
            step_x = max(1, canvas_w / max(1, len(history)-1))
            prev = None
            for i, val in enumerate(history):
                x = i * step_x
                y = canvas_h - (val / maxv * canvas_h)
                if prev:
                    mem_canvas.create_line(prev[0], prev[1], x, y, fill='#66ff66', width=2)
                prev = (x, y)

        root.after(poll_interval_ms, update)

    root.after(1000, update)
    root.mainloop()