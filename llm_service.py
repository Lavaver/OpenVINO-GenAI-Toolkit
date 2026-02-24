import asyncio
import threading
import time
import openvino_genai as ov_genai
from rich.console import Console

console = Console()

class LLMService:
    def __init__(self, model_path: str, device: str = "AUTO"):
        self.model_path = model_path
        self.device = device
        self.pipe = None
        self._load_model()
        self._lock = asyncio.Lock()

    def _load_model(self):
        """加载模型（同步，阻塞）"""
        try:
            self.pipe = ov_genai.LLMPipeline(self.model_path, device=self.device)
            console.print(f"[dim]✅ 模型加载成功，运行设备：{self.device}[/dim]")
        except RuntimeError as e:
            console.print(f"[red]⚠️ 设备 {self.device} 加载失败，自动切换到 AUTO 模式[/red]")
            self.pipe = ov_genai.LLMPipeline(self.model_path, device="AUTO")
            console.print("[dim]✅ 模型已切换到 AUTO 设备运行[/dim]")

    def _build_prompt(self, user_input: str) -> str:
        """构建提示词（与原始脚本一致）"""
        system_prompt = f"""
你是运行在 Intel(R) OpenVINO(TM) GenAI Platform 上的 {self.model_path} 本地大语言模型，当前为本地模型会话（非云端调用）。
请遵循以下规则回答用户问题：
1. 首先输出思考过程（用于展示你的推理逻辑），思考过程用 <think> 包裹（仅作为分隔符，不显示给用户）；
2. 思考过程完成后，输出正式回答，回答需结构清晰、内容准确、语言流畅；
3. 正式回答优先使用Markdown格式（标题、列表、加粗等），提升可读性；
4. 保持回答的专业性和准确性，基于事实作答；
5. 思考过程需详细但不冗余，体现完整的推理逻辑。

用户当前问题：
"""
        return system_prompt + user_input

    # ----- 同步生成（非流式）-----
    def _sync_generate(self, prompt: str, max_tokens: int, temperature: float, top_p: float) -> str:
        """同步调用模型生成（在线程中运行）"""
        return self.pipe.generate(
            prompt,
            max_new_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True
        )

    # ----- 异步生成（流式）-----
    async def generate_stream(self, user_input: str, max_tokens: int, temperature: float, top_p: float):
        """
        异步生成器，产生 token 字符串（包含 <think> 等标签）
        使用队列和线程实现非阻塞流式输出
        """
        prompt = self._build_prompt(user_input)
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        # 同步 streamer 回调（在生成线程中被调用）
        def streamer(token: str) -> bool:
            # 通过事件循环线程安全地将 token 放入异步队列
            loop.call_soon_threadsafe(queue.put_nowait, token)
            return False  # 继续生成

        def target():
            """在线程中运行同步生成，并将结果或异常放入队列"""
            try:
                self.pipe.generate(
                    prompt,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    streamer=streamer,
                    do_sample=True
                )
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)  # 结束标记

        async with self._lock:  # 保证串行推理
            thread = threading.Thread(target=target, daemon=True)
            thread.start()

            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item

    # ----- 异步非流式生成（用于API）-----
    async def generate(self, user_input: str, max_tokens: int, temperature: float, top_p: float) -> str:
        """异步非流式生成（返回完整文本）"""
        prompt = self._build_prompt(user_input)
        loop = asyncio.get_event_loop()
        async with self._lock:
            return await loop.run_in_executor(
                None, self._sync_generate, prompt, max_tokens, temperature, top_p
            )