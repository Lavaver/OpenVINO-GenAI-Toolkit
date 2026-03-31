import asyncio
import threading
import time
import openvino_genai as ov_genai
from rich.console import Console
from wintoast import sendToast

console = Console()

class LLMService:
    def __init__(self, model_path: str, device: str = "AUTO"):
        self.model_path = model_path.strip('"')
        self.device = device
        self.pipe = None
        self._load_model()
        # 使用 threading.Lock 而不是 asyncio.Lock 来确保线程安全
        import threading
        self._lock = threading.Lock()

    def _load_model(self):
        """Load model to the specified device"""
        try:
            console.print(f"[dim]🔄 Loading model {self.model_path} to device {self.device}...[/dim]")
            console.print("[dim]   Please wait a moment. The model requires some time to load. Once completed, the API/Console Client will be available immediately.[/dim]")
            # 使用chat模板加载tokenizer以获得更好的对话支持
            self.pipe = ov_genai.LLMPipeline(self.model_path, device=self.device, config={"chat_template": "chatml"})
            console.print(f"[dim]✅ Model loaded successfully. Running device: {self.device}[/dim]")
            sendToast("Model Load Success", f"Model {self.model_path} loaded successfully on device {self.device}")
        except RuntimeError as e:
            console.print(f"[red]⚠️ Device {self.device} failed to load. Switching to automatic mode.[/red]")
            sendToast("Model Load Error", f"Device {self.device} failed to load. Switched to AUTO mode. Error: {e}")

            self.pipe = ov_genai.LLMPipeline(self.model_path, device="AUTO", config={"chat_template": "chatml"})
            console.print("[dim]✅ The model has switched to AUTO device operation.[/dim]")

    def _build_prompt(self, user_input: str) -> str:
        """Build prompt for the model"""
        # 直接返回用户输入，由OpenAI API的system消息控制
        return user_input

    # ----- 同步生成（非流式）-----
    def _sync_generate(self, prompt: str, max_tokens: int, temperature: float, top_p: float, add_system_prompt: bool = True) -> str:
        """Generate response synchronously"""
        with self._lock:  # 使用线程锁确保同一时间只有一个请求
            if add_system_prompt:
                prompt = self._build_prompt(prompt)
            result = self.pipe.generate(
                inputs=prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True
            )
            # 确保返回字符串类型的结果
            return str(result) if result is not None else ""

    # ----- 异步生成（流式）-----
    async def generate_stream(self, user_input: str, max_tokens: int, temperature: float, top_p: float):
        """
        Asynchronous generator that produces tokens one by one.
        Uses a queue and threading to achieve non-blocking streaming output.
        """
        with self._lock:  # 使用线程锁确保同一时间只有一个请求
            if self._build_prompt is not None:
                prompt = self._build_prompt(user_input)
            else:
                prompt = user_input
            queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            # 同步 streamer 回调（在生成线程中被调用）
            def streamer(token: str) -> bool:
                # 通过事件循环线程安全地将 token 放入异步队列
                # 确保token是字符串类型
                token_str = str(token) if token is not None else ""
                loop.call_soon_threadsafe(queue.put_nowait, token_str)
                return False  # 继续生成

            def target():
                """Thread target function that generates tokens and puts them into the queue."""
                try:
                    self.pipe.generate(
                        inputs=prompt,
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

            thread = threading.Thread(target=target, daemon=True)
            thread.start()

            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                
                # 确保输出项是字符串类型
                token = str(item) if item is not None else ""
                yield token

    # ----- 带工具调用检测的异步生成（流式）-----
    async def generate_stream_with_tool_detection(self, user_input: str, max_tokens: int, temperature: float, top_p: float):
        """
        Asynchronous generator that produces tokens one by one.
        Includes tool call detection in the stream.
        If a tool call pattern is detected, returns the full content immediately.
        """
        with self._lock:  # 使用线程锁确保同一时间只有一个请求
            if self._build_prompt is not None:
                prompt = self._build_prompt(user_input)
            else:
                prompt = user_input
            queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            # 同步 streamer 回调（在生成线程中被调用）
            def streamer(token: str) -> bool:
                # 通过事件循环线程安全地将 token 放入异步队列
                # 确保token是字符串类型
                token_str = str(token) if token is not None else ""
                loop.call_soon_threadsafe(queue.put_nowait, token_str)
                return False  # 继续生成

            def target():
                """Thread target function that generates tokens and puts them into the queue."""
                try:
                    self.pipe.generate(
                        inputs=prompt,
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

            thread = threading.Thread(target=target, daemon=True)
            thread.start()

            # 缓冲区用于检测工具调用
            buffer = ""
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                
                # 确保输出项是字符串类型
                token = str(item) if item is not None else ""
                
                # 将token添加到缓冲区
                buffer += token
                
                # 检查缓冲区中是否包含工具调用模式
                # 检查常见的工具调用模式，优先检查最可能的模式
                if ('<' in buffer and ('function_calls' in buffer or 'invoke' in buffer)) or \
                   ('TOOL_CALL:' in buffer) or \
                   ('"tool_calls"' in buffer):
                    # 如果检测到工具调用模式，立即返回完整缓冲区
                    yield buffer
                    break
                
                # 否则，正常流式输出
                yield token

    # ----- 异步非流式生成（用于API）-----
    async def generate(self, user_input: str, max_tokens: int, temperature: float, top_p: float) -> str:
        """
        Asynchronously generates a complete response for the given user input.
        If user_input contains 'System:' prefix, use it directly without adding default system prompt.
        """
        loop = asyncio.get_event_loop()
        # 使用线程锁，而不是async锁
        with self._lock:
            # 检查用户输入是否已经包含系统消息
            add_system_prompt = not user_input.strip().startswith("System:")
            result = await loop.run_in_executor(
                None, self._sync_generate, user_input, max_tokens, temperature, top_p, add_system_prompt
            )
            # 确保返回字符串类型的结果
            return str(result) if result is not None else ""
    
    # ----- 直接生成（不添加系统提示）-----
    async def generate_direct(self, prompt: str, max_tokens: int, temperature: float, top_p: float) -> str:
        """
        Asynchronously generates a complete response using the provided prompt directly.
        Does not add system prompt.
        """
        loop = asyncio.get_event_loop()
        # 使用线程锁，而不是async锁
        with self._lock:
            # 直接使用传入的提示词，不添加任何系统提示
            # 确保提示词能够正确传递给模型
            # 使用 functools.partial 绑定关键字参数
            import functools
            partial_func = functools.partial(
                self.pipe.generate,
                inputs=prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True
            )
            result = await loop.run_in_executor(None, partial_func)
            # 确保返回字符串类型的结果
            return str(result) if result is not None else ""