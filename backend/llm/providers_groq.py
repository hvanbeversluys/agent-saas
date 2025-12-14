"""
Groq Provider - FREE and FAST LLM inference.
https://console.groq.com/

Groq offers free access to Llama and Mixtral models with very fast inference.
This is the recommended default for cost-effective development.
"""
import time
from typing import Optional, List, Dict, Any, AsyncIterator

import httpx
import structlog

from .base import LLMProvider, LLMResponse, Message, TokenUsage
from .providers import register_provider

logger = structlog.get_logger()

GROQ_API_BASE = "https://api.groq.com/openai/v1"


@register_provider("groq")
class GroqProvider(LLMProvider):
    """
    Groq LLM Provider - FREE tier available!
    
    Models:
    - llama-3.1-70b-versatile: Best quality, good for complex tasks
    - llama-3.1-8b-instant: Fastest, good for simple tasks
    - mixtral-8x7b-32768: Good balance, large context window
    - llama3-groq-70b-8192-tool-use-preview: Best for tool/function calling
    
    Rate limits (free tier):
    - 30 requests/minute
    - 14,400 requests/day
    - 6,000 tokens/minute
    """
    
    name = "groq"
    supports_streaming = True
    supports_tools = True
    supports_vision = False
    
    # Updated models list - December 2024
    # See: https://console.groq.com/docs/models
    MODELS = [
        "llama-3.3-70b-versatile",      # Latest Llama 3.3
        "llama-3.1-8b-instant",          # Fast, small
        "llama-3.2-90b-vision-preview",  # Vision capable
        "llama3-groq-70b-8192-tool-use-preview",  # Tool use
        "mixtral-8x7b-32768",            # Large context
        "gemma2-9b-it",                  # Google Gemma
    ]
    
    def _configure(self, **kwargs):
        self.default_model = kwargs.get("default_model", "llama-3.3-70b-versatile")
        self.timeout = kwargs.get("timeout", 30.0)
    
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
        """Generate completion using Groq API."""
        model = model or self.default_model
        start_time = time.time()
        
        # Build request
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
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{GROQ_API_BASE}/chat/completions",
                json=request_data,
                headers=headers,
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(
                    "Groq API error",
                    status_code=response.status_code,
                    error=error_detail,
                )
                raise Exception(f"Groq API error: {response.status_code} - {error_detail}")
            
            data = response.json()
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Parse response
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
        """Stream completion using Groq API."""
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
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{GROQ_API_BASE}/chat/completions",
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
                        if chunk["choices"][0]["delta"].get("content"):
                            yield chunk["choices"][0]["delta"]["content"]
