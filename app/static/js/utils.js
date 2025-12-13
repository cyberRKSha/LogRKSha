import { pollTaskStatus } from './ui.js';

export function animateCount(id, newCount) {
    let el = document.getElementById(id);
    if (!el) return;
    let current = parseInt(el.textContent) || 0;
    let diff = newCount - current;
    if (diff === 0) return;
    let step = Math.abs(diff) < 20 ? diff : diff / 20;
    let i = 0;
    let interval = setInterval(() => {
        i++;
        let nextValue = Math.round(current + step * i);
        if ((step > 0 && nextValue >= newCount) || (step < 0 && nextValue <= newCount)) {
            el.textContent = newCount;
            clearInterval(interval);
        } else {
            el.textContent = nextValue;
        }
    }, 20);
}

// Helper to prevent HTML injection from log content
export function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

export function formatRiskScore(score) {
    const finalScore = score || 0;
    const percentage = Math.min(finalScore * 100, 100);
    let riskClass = 'low';
    if (finalScore > 0.8) riskClass = 'critical';
    else if (finalScore >= 0.7) riskClass = 'high';
    else if (finalScore >= 0.4) riskClass = 'medium';

    return `
        <div class="risk-score-bar" title="Risk: ${finalScore.toFixed(2)}">
            <div class="risk-bar-track">
                <div class="risk-bar-fill ${riskClass}" style="width: ${percentage}%"></div>
            </div>
            <span class="risk-score-value">${finalScore.toFixed(2)}</span>
        </div>
    `;
}

// Original simple format for backwards compatibility
export function formatRiskScoreSimple(score) {
    const finalScore = score || 0;
    return `<span>${finalScore.toFixed(2)}</span>`;
}

export function getRiskRowClass(score) {
    if (score === undefined || score === null || score === 0) return '';
    if (score > 0.8) return 'risk-row-critical'; // Red background
    if (score >= 0.7) return 'risk-row-orange';  // Orange background
    // Any remaining anomaly will be yellow. The check for 'anomaly' is done in the calling function.
    return 'risk-row-yellow';
}

export function formatSequenceRisk(score) {
    const finalScore = score || 0;
    const percentage = finalScore * 100;
    let riskClass = 'low';
    if (percentage > 90) {
        riskClass = 'critical';
    } else if (percentage > 70) {
        riskClass = 'high';
    } else if (percentage > 40) {
        riskClass = 'medium';
    }

    return `
        <div class="risk-bar-container" title="Behavioral Risk: ${percentage.toFixed(0)}%">
            <div class="risk-bar-fill ${riskClass}" style="width: ${percentage}%;">
                ${finalScore.toFixed(2)}
            </div>
        </div>
    `;
}

export function formatStatusBadge(status) {
    if (!status) {
        return ''; // Return an empty string if there's no status
    }
    const statusClass = status.toLowerCase();
    return `<span class="status-badge status-${statusClass}">${status}</span>`;
}

export function showToast(message, type = 'info', taskId = null) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let progressBarHTML = '';
    if (taskId) {
        progressBarHTML = `<div class="toast-progress-bar" id="progress-${taskId}"></div>`;
    }

    toast.innerHTML = `
        <span id="toast-message-${taskId}">${message}</span>
        ${progressBarHTML}
    `;

    container.appendChild(toast);

    if (taskId) {
        pollTaskStatus(taskId);
    } else {
        // Auto-dismiss non-progress toasts after 5 seconds
        setTimeout(() => {
            toast.style.animation = 'slideOutFadeOut 0.5s ease forwards';
            setTimeout(() => toast.remove(), 500);
        }, 5000);
    }
}