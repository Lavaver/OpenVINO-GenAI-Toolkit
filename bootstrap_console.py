import argparse
import time
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.box import ROUNDED
from llm_service import LLMService
from asciiart import print_ascii_art

THINK_START = "<think>"
THINK_END = "</think>"

def main():
    # 打印ASCII艺术
    print_ascii_art()
    parser = argparse.ArgumentParser(description="OpenVINO GenAI Console Client")
    parser.add_argument("model_path", help="Path to the local OpenVINO model directory")
    parser.add_argument("prompt", help="User input question or prompt")
    parser.add_argument("-d", "--device", default="AUTO", help="Device to run on (AUTO/CPU/GPU/NPU/Intel® Arc™)")
    parser.add_argument("-m", "--max-tokens", type=int, default=32768, help="Maximum number of tokens to generate")
    parser.add_argument("-t", "--temperature", type=float, default=0.7, help="Generation temperature (0-1, higher is more random)")
    parser.add_argument("-p", "--top-p", type=float, default=0.9, help="Top-P sampling (0-1, higher is more random)")
    parser.add_argument("-s", "--stream", action="store_true", help="Enable streaming output (recommended)")

    args = parser.parse_args()
    console = Console()
    console.clear()

    # 初始化服务
    llm = LLMService(args.model_path, args.device)

    if args.stream:
        # 流式模式（与原始脚本类似，但使用 LLMService）
        raw_text = ""
        is_thinking_done = False
        think_start_time = time.time()
        think_elapsed = 0.0

        def render_live_content():
            nonlocal think_elapsed
            clean_text = raw_text.replace(THINK_START, "").strip()

            thought_content = ""
            answer_content = ""
            if THINK_END in clean_text:
                split_result = clean_text.split(THINK_END, 1)
                thought_content = split_result[0].strip()
                answer_content = split_result[1].strip()
            else:
                thought_content = clean_text

            # 实时计时
            if not is_thinking_done:
                think_elapsed = time.time() - think_start_time

            thought_title = f"🧠 AI Thought Process • Took {think_elapsed:.1f}s" if thought_content else "🧠 AI Thought Process"
            thought_panel = Panel(
                Text(thought_content, style="italic grey50"),
                title=thought_title,
                box=ROUNDED,
                border_style="blue",
                padding=(0, 1)
            ) if thought_content else Text("")

            answer_render = Markdown(answer_content) if answer_content else Text("Answer is being generated...", style="dim")
            answer_panel = Panel(
                answer_render,
                title="✨ Answer",
                box=ROUNDED,
                border_style="magenta",
                padding=(0, 1)
            )

            render_parts = []
            if thought_content:
                render_parts.append(thought_panel)
                render_parts.append(Text("\n"))
            render_parts.append(answer_panel)
            return Group(*render_parts)

        with Live(render_live_content(), console=console, refresh_per_second=20, auto_refresh=True) as live:
            try:
                # 使用 LLMService 的流式生成
                async def run_stream():
                    nonlocal raw_text, is_thinking_done
                    async for token in llm.generate_stream(args.prompt, args.max_tokens, args.temperature, args.top_p):
                        raw_text += token
                        if THINK_END in raw_text and not is_thinking_done:
                            is_thinking_done = True
                        live.update(render_live_content())
                # 由于是命令行，我们用 asyncio.run 运行异步生成器
                import asyncio
                asyncio.run(run_stream())
            except KeyboardInterrupt:
                console.print("\n[yellow]⚠️  Answer generation has been interrupted[/yellow]")
            finally:
                # 最终统计
                clean_text = raw_text.replace(THINK_START, "").strip()
                if THINK_END in clean_text:
                    final_thought, final_answer = clean_text.split(THINK_END, 1)
                    final_thought = final_thought.strip()
                    final_answer = final_answer.strip()
                else:
                    final_thought = ""
                    final_answer = clean_text.strip()
                console.print(f"\n[green]✅ Local session completed![/green]")
                console.print(f"[dim]📊 Statistics: Thought content {len(final_thought)} chars | Answer content {len(final_answer)} chars | Thought time {think_elapsed:.1f}s[/dim]")
    else:
        # 非流式模式
        console.print("\n[dim blue]>>> Non-Streaming Generation Mode <<<[/dim blue]\n")
        import asyncio
        raw_text = asyncio.run(llm.generate(args.prompt, args.max_tokens, args.temperature, args.top_p))
        clean_text = raw_text.replace(THINK_START, "").strip()
        if THINK_END in clean_text:
            final_thought, final_answer = clean_text.split(THINK_END, 1)
            final_thought = final_thought.strip()
            final_answer = final_answer.strip()
        else:
            final_thought = ""
            final_answer = clean_text.strip()

        final_parts = []
        if final_thought:
            final_parts.append(Panel(
                Text(final_thought, style="italic grey50"),
                title="🧠 AI Thought Process",
                box=ROUNDED,
                border_style="blue",
                padding=(0, 1)
            ))
            final_parts.append(Text("\n"))
        final_parts.append(Panel(
            Markdown(final_answer),
            title="✨ Answer",
            box=ROUNDED,
            border_style="magenta",
            padding=(0, 1)
        ))
        console.print(Group(*final_parts))
        console.print(f"\n[green]✅ Local session completed![/green]")
        console.print(f"[dim]📊 Statistics: Thought content {len(final_thought)} chars | Answer content {len(final_answer)} chars[/dim]")

if __name__ == "__main__":
    main()