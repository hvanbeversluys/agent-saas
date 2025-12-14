"""
OpenAI Provider - GPT models.
https://platform.openai.com/

Industry standard with excellent quality across all tasks.
"""
import time
from typing import Optional, List, Dict, Any, AsyncIterator

import httpx
import structlog

from .base import LLMProvider, LLMResponse, Message, TokenUsage
from .providers import register_provider

logger = structlog.get_logger()

OPENAI_API_BASE = "https://api.openai.com/v1"


@register_provider("openai")
class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM Provider.
    
    Models:
    - gpt-4o: Best overall quality
    - gpt-4o-mini: Fast and cheap, good quality
    - gpt-4-turbo: High quality, large context
    - gpt-3.5-turbo: Fastest, cheapest
    
    Pricing (per 1M tokens):
    - gpt-4o: $5 input / $15 output
    - gpt-4o-mini: $0.15 input / $0.60 output
    - gpt-3.5-turbo: $0.50 input / $1.50 output
    """
    
    name = "openai"
    supports_streaming = True
    supports_tools = True
    supports_vision = True
    
    MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
    ]
    
    def _configure(self, **kwargs):
        self.default_model = kwargs.get("default_model", "gpt-4o-mini")
        self.timeout = kwargs.get("timeout", 60.0)
        self.organization = kwargs.get("organization")
    
    @property
    def available_models(self) -> List[str]:
        return self.MODELS
    
    async def complete(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using OpenAI API."""
        model = model or self.default_model
        start_time = time.time()
        
        request_data = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
        }
        
        if max_tokens:
            request_data["max_tokens"] = max_tokens
        
        if tools:
            request_data["tools"] = tools
            request_data["tool_choice"] = kwargs.get("tool_choice", "auto")
        
        # Additional options
        if kwargs.get("response_format"):
            request_data["response_format"] = kwargs["response_format"]
        if kwargs.get("seed"):
            request_data["seed"] = kwargs["seed"]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{OPENAI_API_BASE}/chat/completions",
                json=request_data,
                headers=headers,
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(
                    "OpenAI API error",
                    status_code=response.status_code,
                    error=error_detail,
                )
                raise Exception(f"OpenAI API error: {response.status_code} - {error_detail}")
            
            data = response.json()
        
        latency_ms = (time.time() - start_time) * 1000
        
        choice = data["choices"][0]
        message = choice["message"]
        
        usage = TokenUsage(
            prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
            total_tokens=data.get("usage", {}).get("total_tokens", 0),
        )
        
        return LLMResponse(
            content=message.get("content", ""),
            model=model,
            provider=self.name,
            usage=usage,
            finish_reason=choice.get("finish_reason"),
            tool_calls=message.get("tool_calls"),
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
        """Stream completion using OpenAI API."""
        model = model or self.default_model
        
        request_data = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        
        if max_tokens:
            request_data["max_tokens"] = max_tokens
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{OPENAI_API_BASE}/chat/completions",
                json=request_data,
                headers=headers,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        
                        import json
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        if delta.get("content"):
                            yield delta["content"]
