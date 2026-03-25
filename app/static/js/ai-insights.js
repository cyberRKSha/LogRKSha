// app/static/js/ai-insights.js
/**
 * AI Insights Panel - Client-side logic
 * Handles fetching AI insights, provider switching, and UI updates
 */

class AIInsightsPanel {
    constructor() {
        this.panel = document.getElementById('ai-insights-panel');
        this.providerBadge = document.getElementById('ai-provider-badge');
        this.content = document.getElementById('ai-insights-content');
        this.loading = document.getElementById('ai-loading');
        this.response = document.getElementById('ai-response');
        this.error = document.getElementById('ai-error');
        this.refreshBtn = document.getElementById('ai-refresh-btn');
        this.retryBtn = document.getElementById('ai-retry-btn');
        this.dropdownBtn = document.getElementById('ai-dropdown-btn');
        this.dropdownMenu = document.getElementById('ai-dropdown-menu');

        this.currentProvider = 'gemini';
        this.isLoading = false;

        this.init();
    }

    init() {
        // Bind event listeners
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => this.fetchInsights());
        }
        if (this.retryBtn) {
            this.retryBtn.addEventListener('click', () => this.fetchInsights());
        }
        if (this.dropdownBtn) {
            this.dropdownBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleDropdown();
            });
        }

        // Provider switch buttons
        document.querySelectorAll('.ai-dropdown-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const provider = e.target.dataset.provider;
                this.switchProvider(provider);
            });
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', () => this.closeDropdown());

        // Fetch initial insights after a short delay
        setTimeout(() => this.fetchInsights(), 2000);

        // Also fetch provider status
        this.fetchProviderStatus();
    }

    toggleDropdown() {
        if (this.dropdownMenu) {
            this.dropdownMenu.classList.toggle('show');
        }
    }

    closeDropdown() {
        if (this.dropdownMenu) {
            this.dropdownMenu.classList.remove('show');
        }
    }

    showLoading() {
        this.isLoading = true;
        if (this.loading) this.loading.style.display = 'flex';
        if (this.response) this.response.style.display = 'none';
        if (this.error) this.error.style.display = 'none';
        if (this.refreshBtn) this.refreshBtn.classList.add('spinning');
    }

    showResponse(content, provider) {
        this.isLoading = false;
        if (this.loading) this.loading.style.display = 'none';
        if (this.error) this.error.style.display = 'none';
        if (this.refreshBtn) this.refreshBtn.classList.remove('spinning');

        if (this.response) {
            this.response.style.display = 'block';
            // Render markdown-like content
            this.response.innerHTML = this.renderContent(content);
        }

        if (this.providerBadge && provider) {
            this.providerBadge.textContent = `via ${this.formatProviderName(provider)}`;
            this.currentProvider = provider;
        }
    }

    showError(message) {
        this.isLoading = false;
        if (this.loading) this.loading.style.display = 'none';
        if (this.response) this.response.style.display = 'none';
        if (this.refreshBtn) this.refreshBtn.classList.remove('spinning');

        if (this.error) {
            this.error.style.display = 'flex';
            const errorText = this.error.querySelector('p');
            if (errorText) {
                errorText.textContent = `⚠️ ${message || 'Failed to generate insights'}`;
            }
        }
    }

    formatProviderName(provider) {
        const names = {
            'gemini': 'Gemini',
            'groq': 'Groq',
            'mistral': 'Mistral',
            'openrouter': 'OpenRouter',
            'together': 'Together AI',
            'ollama': 'Ollama'
        };
        return names[provider] || provider;
    }

    renderContent(content) {
        // Enhanced markdown rendering with modern styling
        let html = content;

        // First, escape any existing HTML
        html = html.replace(/</g, '&lt;').replace(/>/g, '&gt;');

        // Preserve emojis and special characters
        // Parse headers into styled sections
        html = html.replace(/^### (.+)$/gm, '<h4 class="ai-section-title ai-h4"><span class="ai-title-icon">▸</span>$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 class="ai-section-title ai-h3"><span class="ai-title-icon">◆</span>$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h2 class="ai-section-title ai-h2"><span class="ai-title-icon">★</span>$1</h2>');

        // Bold text with highlight
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="ai-highlight">$1</strong>');

        // Italic text
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

        // Inline code with styling
        html = html.replace(/`([^`]+)`/g, '<code class="ai-inline-code">$1</code>');

        // Code blocks (triple backticks)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre class="ai-code-block"><code class="language-${lang || 'text'}">${code.trim()}</code></pre>`;
        });

        // Bullet points with icons
        html = html.replace(/^[\-\*•] (.+)$/gm, '<li class="ai-list-item"><span class="ai-bullet">●</span><span class="ai-list-content">$1</span></li>');

        // Numbered lists with styled numbers
        html = html.replace(/^(\d+)\. (.+)$/gm, '<li class="ai-list-item ai-numbered"><span class="ai-number">$1</span><span class="ai-list-content">$2</span></li>');

        // Wrap consecutive list items in ul
        html = html.replace(/(<li class="ai-list-item[^"]*">[\s\S]*?<\/li>\n?)+/g, (match) => {
            return `<ul class="ai-list">${match}</ul>`;
        });

        // Paragraphs - double newlines become paragraph breaks
        html = html.replace(/\n\n+/g, '</p><p class="ai-paragraph">');

        // Single newlines become line breaks (except after list items)
        html = html.replace(/(?<!<\/li>)\n(?!<)/g, '<br>');

        // Highlight key metrics and numbers
        html = html.replace(/(\d+(?:,\d{3})*(?:\.\d+)?)\s*(anomalies|alerts|requests|errors|events)/gi,
            '<span class="ai-metric"><span class="ai-metric-value">$1</span> <span class="ai-metric-label">$2</span></span>');

        // Highlight timestamps
        html = html.replace(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)/g,
            '<span class="ai-timestamp">$1</span>');

        // Highlight IP addresses
        html = html.replace(/\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b/g,
            '<span class="ai-ip">$1</span>');

        // Wrap in container with fade-in animation
        return `
            <div class="ai-content-wrapper ai-fade-in">
                <p class="ai-paragraph">${html}</p>
            </div>
        `;
    }

    async fetchInsights() {
        if (this.isLoading) return;

        this.showLoading();

        try {
            const response = await fetch('/api/ai/insights?interval=h', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to fetch insights');
            }

            const data = await response.json();
            this.showResponse(data.content, data.provider);

        } catch (err) {
            console.error('AI Insights error:', err);
            this.showError(err.message);
        }
    }

    async fetchProviderStatus() {
        try {
            const response = await fetch('/api/ai/providers/status');
            if (response.ok) {
                const data = await response.json();
                this.updateProviderDropdown(data);
                if (data.current_provider) {
                    this.currentProvider = data.current_provider;
                    if (this.providerBadge) {
                        this.providerBadge.textContent = `via ${this.formatProviderName(data.current_provider)}`;
                    }
                }
            }
        } catch (err) {
            console.error('Failed to fetch provider status:', err);
        }
    }

    updateProviderDropdown(status) {
        if (!this.dropdownMenu) return;

        const items = this.dropdownMenu.querySelectorAll('.ai-dropdown-item');
        items.forEach(item => {
            const provider = item.dataset.provider;
            const providerStatus = status.providers?.find(p => p.name === provider);

            if (providerStatus) {
                // Update visual state
                item.classList.remove('active', 'unavailable', 'rate-limited');

                if (providerStatus.is_current) {
                    item.classList.add('active');
                    item.innerHTML = `✓ ${this.formatProviderName(provider)}`;
                } else if (!providerStatus.is_configured) {
                    item.classList.add('unavailable');
                    item.innerHTML = `${this.formatProviderName(provider)} <span class="status-badge">No Key</span>`;
                } else if (!providerStatus.is_available) {
                    item.classList.add('rate-limited');
                    item.innerHTML = `${this.formatProviderName(provider)} <span class="status-badge">Rate Limited</span>`;
                } else {
                    item.innerHTML = this.formatProviderName(provider);
                }
            }
        });
    }

    async switchProvider(provider) {
        this.closeDropdown();

        try {
            const response = await fetch('/api/ai/providers/switch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ provider })
            });

            if (response.ok) {
                const data = await response.json();
                this.currentProvider = provider;
                if (this.providerBadge) {
                    this.providerBadge.textContent = `via ${this.formatProviderName(provider)}`;
                }
                // Refresh insights with new provider
                this.fetchInsights();
                // Update dropdown status
                this.fetchProviderStatus();
            } else {
                const error = await response.json();
                console.error('Failed to switch provider:', error);
                // Show toast notification
                if (window.showToast) {
                    window.showToast(`Cannot switch to ${this.formatProviderName(provider)}: ${error.detail}`);
                }
            }
        } catch (err) {
            console.error('Provider switch error:', err);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.aiInsightsPanel = new AIInsightsPanel();
});

// Export for use in other modules if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AIInsightsPanel;
}
