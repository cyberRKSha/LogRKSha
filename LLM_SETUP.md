# LLM Provider Setup Guide

This project supports multiple LLM providers with automatic failover. To enable AI features (Incident Summarization, Trend Analysis, Remediation), you need to configure at least one provider.

> [!NOTE]
> All providers listed below offer a **Free Tier** that is sufficient for testing these features.

## 1. Google Gemini (Recommended Default)
- **Free Limit:** 15 Requests Per Minute (RPM), 1 Million tokens/day.
- **Get Key:**
  1. Go to [Google AI Studio](https://aistudio.google.com/).
  2. Click "Get API key" in the top left.
  3. Click "Create API key".
  4. Copy the key.
- **Config:** `GEMINI_API_KEY=your_key_here`

## 2. Groq (Fastest)
- **Free Limit:** 30 RPM, 14,400 requests/day.
- **Get Key:**
  1. Go to [Groq Console](https://console.groq.com/keys).
  2. Login (GitHub/Google).
  3. Click "Create API Key".
  4. Copy the key.
- **Config:** `GROQ_API_KEY=your_key_here`

## 3. Mistral AI
- **Free Limit:** 1 Request Per Second (experimental).
- **Get Key:**
  1. Go to [Mistral Console](https://console.mistral.ai/).
  2. Create an account.
  3. Go to "API Keys" section.
  4. Create a new key.
- **Config:** `MISTRAL_API_KEY=your_key_here`

## 4. OpenRouter (Aggregator)
- **Free Limit:** Varies (some models are free).
- **Get Key:**
  1. Go to [OpenRouter](https://openrouter.ai/).
  2. Sign up/Login.
  3. Go to [Keys](https://openrouter.ai/keys) and create a key.
- **Config:** `OPENROUTER_API_KEY=your_key_here`

## 5. Together AI
- **Free Limit:** $5 free credit for new accounts (check current offer).
- **Get Key:**
  1. Go to [Together AI](https://api.together.xyz/).
  2. Sign up.
  3. Find API Key in settings.
- **Config:** `TOGETHER_API_KEY=your_key_here`

## 6. Ollama (Local - Privacy Focused)
- **Free Limit:** Unlimited (runs on your hardware).
- **Setup:**
  1. Install [Ollama](https://ollama.com/).
  2. Run: `ollama run llama3` (or any other supported model).
  3. Ensure it's running on port 11434 (default).
- **Config:** No key needed. Default URL: `http://localhost:11434`

---

## Configuration

Add the keys to your `.env` file in the project root:

```ini
# LLM Providers (Add at least one)
GEMINI_API_KEY="AIzb..."
GROQ_API_KEY="gsk_..."
MISTRAL_API_KEY="..."
OPENROUTER_API_KEY="sk-or-..."
TOGETHER_API_KEY="..."

# Optional: Set default provider (gemini, groq, mistral, openrouter, together, ollama)
LLM_DEFAULT_PROVIDER="gemini"
```
