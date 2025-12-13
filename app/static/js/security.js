// Security Console JavaScript
document.addEventListener('DOMContentLoaded', () => {
    loadTokens();
    setupModal();
});

// Load honeytokens from API
async function loadTokens() {
    try {
        const res = await fetch('/api/security/honeytokens');
        if (!res.ok) throw new Error('API error');
        const tokens = await res.json();

        const tbody = document.getElementById('tokensTableBody');
        const table = document.getElementById('tokensTable');
        const noMsg = document.getElementById('noTokensMsg');

        tbody.innerHTML = '';

        // Update stats
        const activeCount = tokens.filter(t => t.is_active).length;
        const triggerCount = tokens.reduce((sum, t) => sum + (t.trigger_count || 0), 0);

        document.getElementById('stat-tokens').textContent = activeCount;
        document.getElementById('stat-triggers').textContent = triggerCount;

        if (tokens.length === 0) {
            table.style.display = 'none';
            noMsg.style.display = 'block';
            return;
        }

        table.style.display = 'table';
        noMsg.style.display = 'none';

        tokens.forEach(t => {
            const tr = document.createElement('tr');
            tr.className = t.trigger_count > 0 ? 'log-anomaly' : '';
            tr.innerHTML = `
                <td class="log-content">${maskToken(t.token)}</td>
                <td>${escapeHtml(t.type)}</td>
                <td>${escapeHtml(t.description || '--')}</td>
                <td class="${t.trigger_count > 0 ? 'label-anomaly' : ''}">${t.trigger_count || 0}</td>
                <td>${formatDate(t.created_at)}</td>
                <td>
                    <button class="control-button" style="padding:8px 16px; font-size:0.9em; background:#dc3545;" 
                            onclick="revokeToken(${t.id})">Revoke</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Failed to load tokens:', err);
        document.getElementById('stat-tokens').textContent = '!';
    }
}

function maskToken(token) {
    if (!token || token.length < 10) return '••••••••';
    return token.substring(0, 8) + '••••' + token.substring(token.length - 4);
}

function formatDate(dateStr) {
    if (!dateStr) return '--';
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Modal handling
function setupModal() {
    const modal = document.getElementById('tokenModal');
    const openBtn = document.getElementById('generateTokenBtn');
    const closeBtn = document.getElementById('closeModalBtn');
    const createBtn = document.getElementById('createTokenBtn');

    openBtn.addEventListener('click', () => {
        modal.style.display = 'flex';
        document.getElementById('generatedTokenBox').style.display = 'none';
        document.getElementById('tokenDesc').value = '';
    });

    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.style.display = 'none';
    });

    createBtn.addEventListener('click', createToken);
}

async function createToken() {
    const desc = document.getElementById('tokenDesc').value.trim();
    const type = document.getElementById('tokenType').value;
    const btn = document.getElementById('createTokenBtn');

    if (!desc) {
        alert('Please enter a description');
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        const res = await fetch('/api/security/honeytokens', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, description: desc })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed');
        }

        const newToken = await res.json();

        // Show generated token
        document.getElementById('generatedTokenText').textContent = newToken.token;
        document.getElementById('generatedTokenBox').style.display = 'block';

        // Reload table
        loadTokens();

    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generate Token';
    }
}

async function revokeToken(id) {
    if (!confirm('Revoke this token? It will no longer trigger alerts.')) return;

    try {
        const res = await fetch(`/api/security/honeytokens/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed');
        loadTokens();
    } catch (err) {
        alert('Failed to revoke: ' + err.message);
    }
}
