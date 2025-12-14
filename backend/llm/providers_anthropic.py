"""
Anthropic Provider - Claude models.
https://console.anthropic.com/

Excellent for coding, analysis, and nuanced tasks.
"""
import time
from typing import Optional, List, Dict, Any, AsyncIterator

import httpx
import structlog

from .base import LLMProvider, LLMResponse, Message, MessageRole, TokenUsage
from .providers import register_provider

logger = structlog.get_logger()

ANTHROPIC_API_BASE = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"


@register_provider("anthropic")
class AnthropicProvider(LLMProvider):
    """
    Anthropic LLM Provider (Claude).
    
    Models:
    - claude-3-5-sonnet-20241022: Best balance of quality and speed
    - claude-3-5-haiku-20241022: Fastest, cheapest
    - claude-3-opus-20240229: Highest quality
    
    Pricing (per 1M tokens):
    - Claude 3.5 Sonnet: $3 input / $15 output
    - Claude 3.5 Haiku: $0.25 input / $1.25 output
    - Claude 3 Opus: $15 input / $75 output
    """
    
    name = "anthropic"
    supports_streaming = True
    supports_tools = True
    supports_vision = True
    
    MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]
    
    def _configure(self, **kwargs):
        self.default_model = kwargs.get("default_model", "claude-3-5-haiku-20241022")
        self.timeout = kwargs.get("timeout", 60.0)
    
    @property
    def available_models(self) -> List[str]:
        return self.MODELS
    
    def _convert_messages(self, messages: List[Message]) -> tuple[Optional[str], List[Dict]]:
        """
        Convert messages to Anthropic format.
        Anthropic requires system message to be separate.
        """
        system_message = None
        converted = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_message = msg.content
            else:
                role = "user" if msg.role == MessageRole.USER else "assistant"
                converted.append({
                    "role": role,
                    "content": msg.content,
                })
        
        return system_message, converted
    
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using Anthropic API."""
        model = model or self.default_model
        start_time = time.time()
        
        system_message, converted_messages = self._convert_messages(messages)
        
        request_data = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
        }
        
        if system_message:
            request_data["system"] = system_message
        
        if tools:
            # Convert OpenAI-style tools to Anthropic format
            anthropic_tools = []
            for tool in tools:
                if tool.get("type") == "function":
                    func = tool["function"]
                    anthropic_tools.append({
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    })
            request_data["tools"] = anthropic_tools
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{ANTHROPIC_API_BASE}/messages",
                json=request_data,
                headers=headers,
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(
                    "Anthropic API error",
                    status_code=response.status_code,
                    error=error_detail,
                )
                raise Exception(f"Anthropic API error: {response.status_code} - {error_detail}")
            
            data = response.json()
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Extract text content
        content = ""
        tool_calls = None
        
        for block in data.get("content", []):
            if block["type"] == "text":
                content = block["text"]
            elif block["type"] == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": block["input"],
                    }
                })
        
        usage = TokenUsage(
            prompt_tokens=data.get("usage", {}).get("input_tokens", 0),
            completion_tokens=data.get("usage", {}).get("output_tokens", 0),
            total_tokens=(
                data.get("usage", {}).get("input_tokens", 0) +
                data.get("usage", {}).get("output_tokens", 0)
            ),
        )
        
        return LLMResponse(
            content=content,
            model=model,
            provider=self.name,
            usage=usage,
            finish_reason=data.get("stop_reason"),
            tool_calls=tool_calls,
            raw_response=data,
            latency_ms=latency_ms,
        )
    
    async def stream(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion using Anthropic API."""
        model = model or self.default_model
        
        system_message, converted_messages = self._convert_messages(messages)
        
        request_data = {
            "model": model,
            "messages": converted_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": True,
        }
        
        if system_message:
            request_data["system"] = system_message
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{ANTHROPIC_API_BASE}/messages",
                json=request_data,
                headers=headers,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        data = json.loads(line[6:])
                        
                        if data["type"] == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
