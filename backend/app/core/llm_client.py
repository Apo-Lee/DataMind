"""DeepSeek API 统一客户端 — function calling 支持"""

import asyncio
import json
from typing import Any

import httpx

from app.config import settings


class LLMClient:
    def __init__(self):
        self.base_url = settings.deepseek_base_url.rstrip("/")
        self.api_key = settings.deepseek_api_key
        self.model = settings.deepseek_model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict:
        """单轮对话，返回 message dict 或 tool_calls

        V2.6: 增加指数退避重试，应对 429/502/503 临时故障
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        max_retries = 3
        base_delay = 1.0
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(
                        f"{self.base_url}/v1/chat/completions",
                        headers=headers,
                        json=body,
                    )
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (429, 502, 503) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                raise
            except httpx.ConnectError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                raise
        raise RuntimeError("LLM chat failed after max retries")

    async def chat_with_tools(
        self, system_prompt: str, user_message: str, tools: list[dict],
        max_rounds: int = 5,
    ) -> list[dict]:
        """多轮 tool calling 对话

        NOTE (V2.5): 当前为 mock 模式 — tool 调用返回占位符字符串而非真实执行结果。
        这是因为工具执行器（数据库查询/计算/外部API）尚未与 LLM 的 function calling 对接。
        生产使用前需要实现真正的工具调度层，将 func_name/args 映射到实际执行逻辑。
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        history = []
        for _ in range(max_rounds):
            msg = await self.chat(messages, tools=tools)
            history.append(msg)
            if msg.get("content"):
                return history
            if msg.get("tool_calls"):
                messages.append(msg)
                for tc in msg["tool_calls"]:
                    func_name = tc["function"]["name"]
                    func_args = json.loads(tc["function"]["arguments"])
                    # TODO(V2.5): 实现真实的工具调用执行 — 将 func_name/func_args
                    # 映射到数据库查询、计算函数或外部 API 调用
                    tool_result = f"[Tool {func_name} called with {func_args}]"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result,
                    })
        return history


# 全局单例
llm_client = LLMClient()
