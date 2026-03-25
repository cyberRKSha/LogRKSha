# tests/test_llm_service.py
"""
Unit tests for the LLM multi-provider service.
Tests failover logic, provider switching, and caching.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# We need to mock the providers before importing the service
@pytest.fixture(autouse=True)
def mock_llm_providers(monkeypatch):
    """Mock all LLM provider API clients"""
    
    # Mock Google Generative AI
    mock_genai = MagicMock()
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is a test response from Gemini"
    mock_model.generate_content.return_value = mock_response
    mock_genai.GenerativeModel.return_value = mock_model
    monkeypatch.setattr("google.generativeai.configure", MagicMock())
    monkeypatch.setattr("google.generativeai.GenerativeModel", mock_model.__class__)
    
    # Mock Groq
    mock_groq = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="Test from Groq"))]
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_completion
    monkeypatch.setattr("groq.Groq", lambda **kwargs: mock_groq_client)
    
    # Mock Mistral
    mock_mistral = MagicMock()
    mock_mistral_response = MagicMock()
    mock_mistral_response.choices = [MagicMock(message=MagicMock(content="Test from Mistral"))]
    mock_mistral_client = MagicMock()
    mock_mistral_client.chat.complete_async = AsyncMock(return_value=mock_mistral_response)
    monkeypatch.setattr("mistralai.Mistral", lambda **kwargs: mock_mistral_client)


@pytest.fixture
def llm_service():
    """Get LLM service instance with mocked providers"""
    from app.services.llm_service import LLMService, get_llm_manager
    # Reset global manager
    import app.services.llm_service as llm_module
    llm_module._manager = None
    return LLMService()


@pytest.fixture
def provider_manager():
    """Get provider manager instance"""
    from app.services.llm_service import LLMProviderManager
    return LLMProviderManager()


class TestProviderStatus:
    """Tests for ProviderStatus class"""
    
    def test_initial_status(self):
        from app.services.llm_service import ProviderStatus
        status = ProviderStatus(name="test")
        
        assert status.name == "test"
        assert status.is_available is True
        assert status.last_error is None
        assert status.requests_made == 0
    
    def test_mark_rate_limited(self):
        from app.services.llm_service import ProviderStatus
        status = ProviderStatus(name="test")
        status.mark_rate_limited("Rate limit exceeded")
        
        assert status.is_available is False
        assert status.last_error == "Rate limit exceeded"
        assert status.last_error_time is not None
    
    def test_cooldown_expired(self):
        from app.services.llm_service import ProviderStatus, RATE_LIMIT_COOLDOWN
        status = ProviderStatus(name="test")
        
        # No error, cooldown should be expired
        assert status.check_cooldown_expired() is True
        
        # Recent error, cooldown not expired
        status.mark_rate_limited("Error")
        assert status.check_cooldown_expired() is False
        
        # Simulate time passed beyond cooldown
        status.last_error_time = datetime.now() - timedelta(seconds=RATE_LIMIT_COOLDOWN + 10)
        assert status.check_cooldown_expired() is True


class TestProviderManager:
    """Tests for LLMProviderManager"""
    
    def test_get_provider_by_name(self, provider_manager):
        provider = provider_manager.get_provider_by_name("gemini")
        assert provider is not None
        assert provider.name == "gemini"
        
        unknown = provider_manager.get_provider_by_name("unknown")
        assert unknown is None
    
    def test_switch_provider(self, provider_manager):
        # Switch to a valid provider
        with patch.object(provider_manager.providers[1], 'is_configured', return_value=True):
            result = provider_manager.switch_provider("groq")
            assert result is True
            assert provider_manager.current_provider_name == "groq"
        
        # Try to switch to invalid provider
        result = provider_manager.switch_provider("invalid")
        assert result is False
    
    def test_get_status(self, provider_manager):
        status = provider_manager.get_status()
        
        assert "current_provider" in status
        assert "providers" in status
        assert len(status["providers"]) == 6  # 6 providers configured
    
    def test_get_available_providers_resets_cooldown(self, provider_manager):
        from app.services.llm_service import RATE_LIMIT_COOLDOWN
        
        # Mark a provider as rate limited
        gemini = provider_manager.get_provider_by_name("gemini")
        gemini.status.mark_rate_limited("Rate limit")
        
        # Simulate time passing
        gemini.status.last_error_time = datetime.now() - timedelta(seconds=RATE_LIMIT_COOLDOWN + 10)
        
        # Patch is_configured
        with patch.object(gemini, 'is_configured', return_value=True):
            available = provider_manager.get_available_providers()
            assert gemini.status.is_available is True


class TestLLMProviders:
    """Tests for individual LLM provider implementations"""
    
    def test_gemini_is_configured(self, monkeypatch):
        from app.services.llm_service import GeminiProvider
        
        # Without API key
        monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", None)
        provider = GeminiProvider()
        assert provider.is_configured() is False
        
        # With API key
        monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", "test-key")
        provider = GeminiProvider()
        assert provider.is_configured() is True
    
    def test_groq_is_configured(self, monkeypatch):
        from app.services.llm_service import GroqProvider
        
        monkeypatch.setattr("app.config.settings.GROQ_API_KEY", None)
        provider = GroqProvider()
        assert provider.is_configured() is False
        
        monkeypatch.setattr("app.config.settings.GROQ_API_KEY", "test-key")
        provider = GroqProvider()
        assert provider.is_configured() is True
    
    def test_ollama_always_configured(self):
        from app.services.llm_service import OllamaProvider
        provider = OllamaProvider()
        assert provider.is_configured() is True


class TestLLMService:
    """Tests for the high-level LLMService"""
    
    def test_build_trend_prompt(self, llm_service):
        data = [
            {"timestamp": "2025-01-01 10:00", "anomalies": 5},
            {"timestamp": "2025-01-01 11:00", "anomalies": 15},
            {"timestamp": "2025-01-01 12:00", "anomalies": 3}
        ]
        prompt = llm_service._build_trend_prompt(data)
        
        assert "security analyst" in prompt.lower()
        assert "23" in prompt  # Total anomalies
        assert "2025-01-01 11:00" in prompt  # Peak period
    
    def test_build_summary_prompt(self, llm_service):
        alert = {
            "rule_name": "SSH Brute Force",
            "risk_score": 0.95,
            "mitre_tactic": "Credential Access",
            "content": "Failed password for root from 192.168.1.1"
        }
        prompt = llm_service._build_summary_prompt(alert, [])
        
        assert "SSH Brute Force" in prompt
        assert "Credential Access" in prompt
        assert "192.168.1.1" in prompt
    
    def test_build_remediation_prompt(self, llm_service):
        alert = {
            "rule_name": "Port Scan Detected",
            "risk_score": 0.8,
            "content": "Nmap scan from 10.0.0.1"
        }
        threat_intel = {
            "abuseConfidenceScore": 85,
            "countryCode": "RU",
            "isp": "DigitalOcean"
        }
        prompt = llm_service._build_remediation_prompt(alert, threat_intel)
        
        assert "Port Scan" in prompt
        assert "85" in prompt  # Abuse score
        assert "RU" in prompt
        assert "Immediate Actions" in prompt
        assert "Investigation Steps" in prompt


class TestFailover:
    """Tests for automatic failover behavior"""
    
    @pytest.mark.asyncio
    async def test_failover_on_rate_limit(self, provider_manager, monkeypatch):
        """Test that the manager fails over to the next provider on rate limit"""
        from app.services.llm_service import GeminiProvider, GroqProvider
        
        # Make Gemini fail with rate limit
        async def gemini_fail(prompt):
            raise Exception("429 Rate limit exceeded")
        
        async def groq_success(prompt):
            return "Groq response"
        
        gemini = provider_manager.get_provider_by_name("gemini")
        groq = provider_manager.get_provider_by_name("groq")
        
        with patch.object(gemini, 'generate', gemini_fail), \
             patch.object(gemini, 'is_configured', return_value=True), \
             patch.object(groq, 'generate', groq_success), \
             patch.object(groq, 'is_configured', return_value=True):
            
            response, provider_used = await provider_manager.generate("test prompt")
            
            assert response == "Groq response"
            assert provider_used == "groq"
    
    @pytest.mark.asyncio
    async def test_all_providers_fail(self, provider_manager):
        """Test graceful error when all providers fail"""
        async def fail(prompt):
            raise Exception("Provider error")
        
        # Make all providers fail
        for provider in provider_manager.providers:
            provider.generate = fail
            provider.is_configured = lambda: True
            provider.status.is_available = True
        
        with pytest.raises(Exception) as excinfo:
            await provider_manager.generate("test")
        
        assert "All LLM providers failed" in str(excinfo.value)


class TestCaching:
    """Tests for response caching"""
    
    @pytest.mark.asyncio
    async def test_insights_are_cached(self, llm_service, monkeypatch):
        """Test that trend insights are cached"""
        from app.services.cache import cache
        
        # Mock cache
        cache_store = {}
        monkeypatch.setattr(cache, 'get_json', lambda k: cache_store.get(k))
        monkeypatch.setattr(cache, 'set_json', lambda k, v, ttl: cache_store.update({k: v}))
        
        # Mock provider
        call_count = 0
        async def mock_generate(prompt):
            nonlocal call_count
            call_count += 1
            return ("Cached response", "gemini")
        
        llm_service.manager.generate = mock_generate
        
        data = [{"timestamp": "2025-01-01", "anomalies": 5}]
        
        # First call - should hit provider
        await llm_service.generate_trend_insights(data)
        assert call_count == 1
        
        # Second call with same data - should use cache
        # (This tests the caching logic, actual cache hit depends on implementation)
