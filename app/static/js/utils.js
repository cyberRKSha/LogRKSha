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
    // The span no longer needs a class; the parent <tr>'s class will style it.
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