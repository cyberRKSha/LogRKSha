# app/services/llm_service.py
"""
Multi-provider LLM service with automatic failover.
Supports: Gemini, Groq, Mistral, OpenRouter, Together AI, Ollama
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

import httpx

from app.config import settings
from app.services.cache import cache

logger = logging.getLogger(__name__)

# Rate limit cooldown period (seconds)
RATE_LIMIT_COOLDOWN = 300  # 5 minutes


@dataclass
class ProviderStatus:
    """Tracks the status of an LLM provider"""
    name: str
    is_available: bool = True
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    requests_made: int = 0
    
    def mark_rate_limited(self, error_msg: str):
        self.is_available = False
        self.last_error = error_msg
        self.last_error_time = datetime.now()
    
    def check_cooldown_expired(self) -> bool:
        if self.last_error_time is None:
            return True
        return datetime.now() > self.last_error_time + timedelta(seconds=RATE_LIMIT_COOLDOWN)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "is_available": self.is_available,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "requests_made": self.requests_made
        }


class LLMProvider(ABC):
    """Base class for LLM providers"""
    
    name: str = "base"
    model: str = ""
    
    def __init__(self):
        self.status = ProviderStatus(name=self.name)
    
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate a response from the LLM"""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider has necessary API keys"""
        pass
    
    async def health_check(self) -> bool:
        """Quick health check - override in subclasses if needed"""
        return self.is_configured() and self.status.is_available


class GeminiProvider(LLMProvider):
    """Google Gemini provider - using new google.genai SDK"""
    
    name = "gemini"
    model = "gemini-2.0-flash"  # Stable model (not -exp)
    
    def __init__(self):
        super().__init__()
        self._client = None
    
    def is_configured(self) -> bool:
        return bool(settings.GEMINI_API_KEY)
    
    def _get_client(self):
        if self._client is None and self.is_configured():
            from google import genai
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client
    
    async def generate(self, prompt: str) -> str:
        client = self._get_client()
        if not client:
            raise ValueError("Gemini not configured")
        
        try:
            # Use the new genai SDK with timeout protection
            loop = asyncio.get_event_loop()
            
            def _generate():
                return client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
            
            # Add 30-second timeout to prevent hanging
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _generate),
                timeout=30.0
            )
            self.status.requests_made += 1
            return response.text
        except asyncio.TimeoutError:
            logger.error("Gemini request timed out after 30 seconds")
            raise TimeoutError("Gemini API request timed out after 30 seconds")
        except Exception as e:
            error_str = str(e).lower()
            # More precise rate limit detection - avoid false positives from words like "generate"
            is_rate_limited = (
                "429" in error_str or 
                "quota" in error_str or 
                "rate limit" in error_str or  # More specific than just "rate"
                "resource exhausted" in error_str or
                "too many requests" in error_str
            )
            if is_rate_limited:
                self.status.mark_rate_limited(str(e))
                logger.warning(f"Gemini rate limited: {e}")
            else:
                logger.error(f"Gemini error (not rate limited): {e}")
            raise


class GroqProvider(LLMProvider):
    """Groq provider - fast inference"""
    
    name = "groq"
    model = "llama-3.3-70b-versatile"
    
    def __init__(self):
        super().__init__()
        self._client = None
    
    def is_configured(self) -> bool:
        return bool(settings.GROQ_API_KEY)
    
    def _get_client(self):
        if self._client is None and self.is_configured():
            from groq import Groq
            self._client = Groq(api_key=settings.GROQ_API_KEY)
        return self._client
    
    async def generate(self, prompt: str) -> str:
        client = self._get_client()
        if not client:
            raise ValueError("Groq not configured")
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2048
                )
            )
            self.status.requests_made += 1
            return response.choices[0].message.content
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                self.status.mark_rate_limited(str(e))
            raise


class MistralProvider(LLMProvider):
    """Mistral AI provider"""
    
    name = "mistral"
    model = "mistral-small-latest"
    
    def __init__(self):
        super().__init__()
        self._client = None
    
    def is_configured(self) -> bool:
        return bool(settings.MISTRAL_API_KEY)
    
    def _get_client(self):
        if self._client is None and self.is_configured():
            from mistralai import Mistral
            self._client = Mistral(api_key=settings.MISTRAL_API_KEY)
        return self._client
    
    async def generate(self, prompt: str) -> str:
        client = self._get_client()
        if not client:
            raise ValueError("Mistral not configured")
        
        try:
            response = await client.chat.complete_async(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            self.status.requests_made += 1
            return response.choices[0].message.content
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                self.status.mark_rate_limited(str(e))
            raise


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider - aggregates multiple models"""
    
    name = "openrouter"
    model = "meta-llama/llama-3.3-70b-instruct:free"
    
    def is_configured(self) -> bool:
        return bool(settings.OPENROUTER_API_KEY)
    
    async def generate(self, prompt: str) -> str:
        if not self.is_configured():
            raise ValueError("OpenRouter not configured")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                self.status.requests_made += 1
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    self.status.mark_rate_limited(str(e))
                raise


class TogetherProvider(LLMProvider):
    """Together AI provider"""
    
    name = "together"
    model = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
    
    def is_configured(self) -> bool:
        return bool(settings.TOGETHER_API_KEY)
    
    async def generate(self, prompt: str) -> str:
        if not self.is_configured():
            raise ValueError("Together AI not configured")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.together.xyz/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.TOGETHER_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2048
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                self.status.requests_made += 1
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    self.status.mark_rate_limited(str(e))
                raise


class OllamaProvider(LLMProvider):
    """Ollama local provider - no rate limits, runs locally"""
    
    name = "ollama"
    model = "llama3.2"
    _models_available: Optional[List[str]] = None
    
    def is_configured(self) -> bool:
        """Check if Ollama is running and has models"""
        # We'll do a quick sync check - if Ollama isn't running, it's not configured
        try:
            import httpx
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{settings.OLLAMA_HOST}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                    self._models_available = models
                    return len(models) > 0
        except:
            pass
        return False
    
    async def health_check(self) -> bool:
        """Check if Ollama is actually running and has models"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.OLLAMA_HOST}/api/tags",
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    return len(models) > 0
                return False
        except:
            return False
    
    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            try:
                # First check if Ollama is running
                try:
                    tags_response = await client.get(
                        f"{settings.OLLAMA_HOST}/api/tags",
                        timeout=5.0
                    )
                    if tags_response.status_code != 200:
                        raise ValueError(f"Ollama not running at {settings.OLLAMA_HOST}. Start it with: ollama serve")
                    
                    data = tags_response.json()
                    available_models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                    
                    if not available_models:
                        raise ValueError(f"No Ollama models found. Pull one with: ollama pull {self.model}")
                    
                    # Use first available model if our default isn't available
                    model_to_use = self.model
                    if self.model not in available_models and self.model.split(":")[0] not in available_models:
                        model_to_use = available_models[0]
                        logger.info(f"Model {self.model} not found, using {model_to_use}")
                    
                except httpx.RequestError:
                    raise ValueError(f"Cannot connect to Ollama at {settings.OLLAMA_HOST}. Is Ollama running? Start with: ollama serve")
                
                response = await client.post(
                    f"{settings.OLLAMA_HOST}/api/generate",
                    json={
                        "model": model_to_use,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=120.0  # Ollama can be slow on first run
                )
                response.raise_for_status()
                self.status.requests_made += 1
                result = response.json()
                return result.get("response", "")
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    error_msg = f"Ollama model not found. Pull it with: ollama pull {self.model}"
                else:
                    error_msg = str(e)
                self.status.mark_rate_limited(error_msg)
                raise ValueError(error_msg)
            except ValueError:
                raise
            except Exception as e:
                self.status.mark_rate_limited(str(e))
                raise


class LLMProviderManager:
    """Manages multiple LLM providers with automatic failover"""
    
    def __init__(self):
        # Initialize all providers in priority order
        self.providers: List[LLMProvider] = [
            GeminiProvider(),
            GroqProvider(),
            MistralProvider(),
            OpenRouterProvider(),
            TogetherProvider(),
            OllamaProvider()
        ]
        self.current_provider_name = settings.LLM_DEFAULT_PROVIDER
    
    def get_provider_by_name(self, name: str) -> Optional[LLMProvider]:
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None
    
    def get_available_providers(self) -> List[LLMProvider]:
        """Get list of providers that are configured and available"""
        available = []
        for provider in self.providers:
            # Check if cooldown has expired
            if not provider.status.is_available and provider.status.check_cooldown_expired():
                provider.status.is_available = True
                provider.status.last_error = None
            
            if provider.is_configured() and provider.status.is_available:
                available.append(provider)
        return available
    
    async def generate(self, prompt: str) -> Tuple[str, str]:
        """
        Generate response with automatic failover.
        Returns: (response_text, provider_name_used)
        """
        available = self.get_available_providers()
        
        if not available:
            raise Exception("No LLM providers available. All providers are either not configured or rate-limited.")
        
        # Try current provider first if available
        current = self.get_provider_by_name(self.current_provider_name)
        if current and current in available:
            try:
                response = await current.generate(prompt)
                return response, current.name
            except Exception as e:
                logger.warning(f"Provider {current.name} failed: {e}")
                available.remove(current)
        
        # Failover to other providers
        for provider in available:
            try:
                logger.info(f"Failing over to provider: {provider.name}")
                response = await provider.generate(prompt)
                self.current_provider_name = provider.name
                return response, provider.name
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue
        
        raise Exception("All LLM providers failed")
    
    def switch_provider(self, provider_name: str) -> bool:
        """Manually switch to a specific provider"""
        provider = self.get_provider_by_name(provider_name)
        if provider and provider.is_configured():
            self.current_provider_name = provider_name
            # Reset the provider's rate limit status on manual switch
            provider.status.is_available = True
            provider.status.last_error = None
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        statuses = []
        for provider in self.providers:
            status = provider.status.to_dict()
            status["is_configured"] = provider.is_configured()
            status["is_current"] = provider.name == self.current_provider_name
            statuses.append(status)
        
        return {
            "current_provider": self.current_provider_name,
            "providers": statuses
        }


# Global manager instance
_manager: Optional[LLMProviderManager] = None

def get_llm_manager() -> LLMProviderManager:
    global _manager
    if _manager is None:
        _manager = LLMProviderManager()
    return _manager


class LLMService:
    """High-level service for AI-powered features"""
    
    def __init__(self):
        self.manager = get_llm_manager()
    
    async def generate_trend_insights(self, historical_data: List[dict]) -> Tuple[str, str]:
        """Generate natural language insights from historical trend data"""
        cache_key = f"ai:insights:{hash(json.dumps(historical_data, default=str))}"
        
        # Check cache
        cached = cache.get_json(cache_key)
        if cached:
            return cached["response"], cached["provider"]
        
        # Build prompt
        prompt = self._build_trend_prompt(historical_data)
        
        # Generate
        response, provider = await self.manager.generate(prompt)
        
        # Cache
        cache.set_json(cache_key, {"response": response, "provider": provider}, ttl=settings.LLM_CACHE_TTL)
        
        return response, provider
    
    async def summarize_incident(self, alert: dict, context_logs: List[dict]) -> Tuple[str, str]:
        """Generate executive summary for an incident"""
        cache_key = f"ai:summary:{alert.get('id', 'unknown')}"
        
        cached = cache.get_json(cache_key)
        if cached:
            return cached["response"], cached["provider"]
        
        prompt = self._build_summary_prompt(alert, context_logs)
        response, provider = await self.manager.generate(prompt)
        
        cache.set_json(cache_key, {"response": response, "provider": provider}, ttl=settings.LLM_CACHE_TTL * 24)
        
        return response, provider
    
    async def suggest_remediation(self, alert: dict, threat_intel: Optional[dict] = None) -> Tuple[str, str]:
        """Generate remediation suggestions for an alert"""
        cache_key = f"ai:remediation:{alert.get('id', 'unknown')}"
        
        cached = cache.get_json(cache_key)
        if cached:
            return cached["response"], cached["provider"]
        
        prompt = self._build_remediation_prompt(alert, threat_intel)
        response, provider = await self.manager.generate(prompt)
        
        cache.set_json(cache_key, {"response": response, "provider": provider}, ttl=settings.LLM_CACHE_TTL * 24)
        
        return response, provider
    
    def _build_trend_prompt(self, data: List[dict]) -> str:
        # Summarize the data
        total_anomalies = sum(d.get("anomalies", 0) for d in data)
        peak = max(data, key=lambda x: x.get("anomalies", 0)) if data else {}
        
        return f"""You are a security analyst AI assistant for a SIEM system called LogAD.
Analyze the following historical anomaly trend data and provide insights in a clear, actionable format.

DATA SUMMARY:
- Time range: {data[0].get('timestamp', 'N/A') if data else 'N/A'} to {data[-1].get('timestamp', 'N/A') if data else 'N/A'}
- Total anomalies: {total_anomalies}
- Peak period: {peak.get('timestamp', 'N/A')} with {peak.get('anomalies', 0)} anomalies
- Data points: {len(data)}

RAW DATA (last 20 points):
{json.dumps(data[-20:], indent=2, default=str)}

Provide a brief analysis (2-3 paragraphs) covering:
1. Overall trend assessment (increasing, decreasing, stable)
2. Notable spikes or patterns and possible causes
3. Recommendations for the security team

Keep the response concise and actionable. Use bullet points where appropriate.
Format your response in markdown."""
    
    def _build_summary_prompt(self, alert: dict, context_logs: List[dict]) -> str:
        return f"""You are a security analyst AI assistant for a SIEM system.
Generate an executive summary for the following security alert.

ALERT DETAILS:
- Rule Name: {alert.get('rule_name', 'Unknown')}
- Risk Score: {alert.get('risk_score', 'N/A')}
- MITRE Tactic: {alert.get('mitre_tactic', 'N/A')}
- MITRE Technique: {alert.get('mitre_technique', 'N/A')}
- Log Content: {alert.get('content', 'N/A')[:500]}

SURROUNDING CONTEXT (±10 seconds):
{json.dumps([{
    'timestamp': l.get('timestamp'),
    'content': l.get('content', '')[:200],
    'label': 'anomaly' if l.get('final_label') == 1 else 'normal'
} for l in context_logs[:10]], indent=2, default=str)}

Provide a 1-2 paragraph executive summary that:
1. Explains what happened in plain English
2. Assesses the severity and potential impact
3. Identifies any attack patterns or indicators of compromise

Format in markdown. Be concise."""
    
    def _build_remediation_prompt(self, alert: dict, threat_intel: Optional[dict]) -> str:
        threat_info = ""
        if threat_intel:
            threat_info = f"""
THREAT INTELLIGENCE:
- Abuse Confidence Score: {threat_intel.get('abuseConfidenceScore', 'N/A')}%
- Country: {threat_intel.get('countryCode', 'N/A')}
- ISP: {threat_intel.get('isp', 'N/A')}
- Total Reports: {threat_intel.get('totalReports', 'N/A')}
"""
        
        return f"""You are a security analyst AI assistant for a SIEM system.
Suggest specific remediation steps for the following security alert.

ALERT DETAILS:
- Rule Name: {alert.get('rule_name', 'Unknown')}
- Risk Score: {alert.get('risk_score', 'N/A')}
- MITRE Tactic: {alert.get('mitre_tactic', 'N/A')}
- MITRE Technique: {alert.get('mitre_technique', 'N/A')}
- Log Content: {alert.get('content', 'N/A')[:500]}
{threat_info}

Provide remediation steps in markdown format:

## Immediate Actions
List 2-3 specific commands or actions to contain the threat.

## Investigation Steps
List 3-4 steps to investigate the scope and impact.

## Long-term Recommendations
List 2-3 preventive measures.

Be specific with commands (use Linux/UFW). Include example commands where applicable."""


# Convenience function
async def get_llm_service() -> LLMService:
    return LLMService()
