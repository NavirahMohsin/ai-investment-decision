"""
LLM Service - Handles integration with Gemini and Groq APIs.

Primary: Gemini 2.0 Flash (via Google AI Studio) - 1M token context window
Fallback: OpenAI GPT OSS 120B (via Groq) - High-speed backup
"""

import json
import logging
import os
from typing import Optional, Any, Literal
from enum import Enum
import time

import google.generativeai as genai
from groq import Groq as GroqClient
import httpx
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Available LLM providers."""
    GEMINI = "gemini"
    GROQ = "groq"


class LLMConfig:
    """Configuration for LLM providers."""

    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI")
        self.groq_api_key = os.getenv("GROQ")
        
        if not self.gemini_api_key:
            logger.warning("GEMINI API key not found. Gemini will not be available.")
        if not self.groq_api_key:
            logger.warning("GROQ API key not found. Groq will not be available.")
        
        # Configure Gemini if available
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)


class LLMResponse(BaseModel):
    """Structured response from LLM."""
    content: str = Field(..., description="Main response content")
    provider: LLMProvider = Field(..., description="Which LLM provider was used")
    usage: Optional[dict] = Field(None, description="Token usage info if available")


class LLMService:
    """Service for interacting with multiple LLM providers with fallback."""

    def __init__(self):
        self.config = LLMConfig()
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self.gemini_available = bool(self.config.gemini_api_key)
        self.groq_available = bool(self.config.groq_api_key)
        self.groq_client = None
        
        if self.groq_available:
            self.groq_client = GroqClient(api_key=self.config.groq_api_key)
        
        logger.info(f"LLMService initialized - Gemini: {self.gemini_available}, Groq: {self.groq_available}")

    def _is_provider_available(self, provider: LLMProvider) -> bool:
        """Check if a provider is available."""
        if provider == LLMProvider.GEMINI:
            return self.gemini_available
        elif provider == LLMProvider.GROQ:
            return self.groq_available
        return False

    def is_available(self) -> bool:
        """Check if any LLM provider is available."""
        if os.getenv("TESTING") == "1":
            return False
        return self.gemini_available or self.groq_available

    def generate_text(self, prompt: str, max_tokens: int = 500) -> str:
        """Convenience method to generate plain text."""
        if os.getenv("TESTING") == "1":
            return "Simulated investment synthesis for testing."
        res = self.generate(prompt=prompt, max_tokens=max_tokens)
        return res.content if res else ""

    def _call_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[type[BaseModel]] = None,
    ) -> tuple[str, Optional[dict]]:
        """Call Gemini API with structured outputs support."""
        try:
            if not self.config.gemini_api_key:
                raise RuntimeError("Gemini API key not configured")
            
            logger.info(f"Calling Gemini with model: gemini-2.0-flash")
            
            # Build request with system instruction
            messages = []
            if system_prompt:
                messages.append({
                    "role": "user",
                    "parts": [{"text": system_prompt}]
                })
            
            messages.append({
                "role": "user",
                "parts": [{"text": prompt}]
            })

            response = genai.GenerativeModel("gemini-2.0-flash").generate_content(
                contents=messages,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            text_content = response.text
            
            # Extract usage if available
            usage = None
            if hasattr(response, "usage_metadata"):
                usage = {
                    "input_tokens": response.usage_metadata.prompt_token_count,
                    "output_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.prompt_token_count
                    + response.usage_metadata.candidates_token_count,
                }

            logger.info(f"Gemini call successful. Tokens: {usage}")
            return text_content, usage

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}", exc_info=True)
            raise

    def _call_groq(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[type[BaseModel]] = None,
    ) -> tuple[str, Optional[dict]]:
        """Call Groq API with structured outputs support."""
        try:
            messages = []
            
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            messages.append({
                "role": "user",
                "content": prompt
            })

            response_schema = None
            if response_format:
                # Groq uses JSON schema mode
                response_schema = {
                    "type": "json_object",
                    "description": response_format.__doc__ or "JSON response",
                }

            response = self.groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_schema if response_format else None,
            )

            text_content = response.choices[0].message.content
            
            # Extract usage
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            logger.info(f"Groq call successful. Tokens: {usage}")
            return text_content, usage

        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            raise

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        provider: Optional[LLMProvider] = None,
        response_format: Optional[type[BaseModel]] = None,
        fallback_to_groq: bool = True,
    ) -> LLMResponse:
        """
        Generate a response using the specified or preferred LLM provider.
        
        Args:
            prompt: The user prompt
            system_prompt: System instructions for the model
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens
            provider: Specific provider to use (defaults to Gemini)
            response_format: Pydantic model for structured output
            fallback_to_groq: Whether to fallback to Groq if primary fails
        
        Returns:
            LLMResponse with content and provider info
        """
        
        # Determine which provider to use
        if provider:
            primary_provider = provider
            fallback_provider = (
                LLMProvider.GROQ 
                if provider == LLMProvider.GEMINI 
                else LLMProvider.GEMINI
            )
        else:
            primary_provider = LLMProvider.GEMINI
            fallback_provider = LLMProvider.GROQ

        # Try primary provider
        if self._is_provider_available(primary_provider):
            try:
                logger.info(f"Using {primary_provider.value} as primary provider")
                content, usage = self._call_provider(
                    primary_provider,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens,
                    response_format,
                )
                
                return LLMResponse(
                    content=content,
                    provider=primary_provider,
                    usage=usage,
                )
            except Exception as e:
                logger.warning(
                    f"Primary provider {primary_provider.value} failed: {e}. "
                    f"{'Falling back to ' + fallback_provider.value if fallback_to_groq else 'No fallback'}"
                )
                if not fallback_to_groq:
                    raise
        else:
            logger.warning(f"Primary provider {primary_provider.value} not available. Gemini key: {bool(self.config.gemini_api_key)}, Groq key: {bool(self.config.groq_api_key)}")

        # Fallback to secondary provider
        if fallback_to_groq and self._is_provider_available(fallback_provider):
            logger.info(f"Using {fallback_provider.value} as fallback provider")
            try:
                content, usage = self._call_provider(
                    fallback_provider,
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens,
                    response_format,
                )
                
                return LLMResponse(
                    content=content,
                    provider=fallback_provider,
                    usage=usage,
                )
            except Exception as e:
                logger.error(f"Fallback provider {fallback_provider.value} also failed: {e}")
                raise

        # No providers available
        raise RuntimeError(
            f"No LLM providers available. Gemini: {self.gemini_available}, Groq: {self.groq_available}"
        )

    def _call_provider(
        self,
        provider: LLMProvider,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        response_format: Optional[type[BaseModel]],
    ) -> tuple[str, Optional[dict]]:
        """Dispatch to the appropriate provider."""
        for attempt in range(self.max_retries):
            try:
                if provider == LLMProvider.GEMINI:
                    return self._call_gemini(
                        prompt,
                        system_prompt,
                        temperature,
                        max_tokens,
                        response_format,
                    )
                elif provider == LLMProvider.GROQ:
                    return self._call_groq(
                        prompt,
                        system_prompt,
                        temperature,
                        max_tokens,
                        response_format,
                    )
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    raise

    def parse_json_response(
        self,
        response: LLMResponse,
        response_format: type[BaseModel],
    ) -> BaseModel:
        """Parse a JSON response into a Pydantic model."""
        try:
            json_obj = json.loads(response.content)
            return response_format(**json_obj)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response content: {response.content}")
            raise
        except ValidationError as e:
            logger.error(f"Failed to validate response schema: {e}")
            raise


# Singleton instance
_llm_service_instance = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
