// static/js/ui.js
import * as api from './api.js';
import { animateCount, escapeHTML, formatRiskScore, getRiskRowClass, formatSequenceRisk, formatStatusBadge, showToast } from './utils.js';


export function updateStatsOnScreen(total, normal, anomaly, sessionCount) {
    animateCount('totalLogs', total);
    animateCount('normalCount', normal);
    animateCount('anomalyCount', anomaly);
    animateCount('sessionCount', sessionCount);

    const lastUpdatedEl = document.getElementById("lastUpdated");
    if (lastUpdatedEl) {
        lastUpdatedEl.textContent = new Date().toLocaleString();
    }
}

export function renderRestoredLogs(logs) {
    const tableBody = document.getElementById("logsTableBody");
    if (!logs || !tableBody) return;

    tableBody.innerHTML = '';
    // Re-render each log from the cache, oldest first
    logs.slice().reverse().forEach(logData => {
        // This is a simplified render, you can expand it if needed
        const row = tableBody.insertRow(0);
        const labelText = (logData.label || 'unknown').toLowerCase().trim();
        const escapedContent = (logData.log || '-').replace(/'/g, "\\'");
        row.className = 'log-row-clickable';
        row.addEventListener('click', () => showLogContext(logData.timestamp, logData.log, logData.id));
        row.insertCell(0).textContent = new Date(logData.timestamp).toLocaleString();
        row.insertCell(1).innerHTML = `<span class="label-${labelText}">${labelText}</span>`;
        row.insertCell(2).textContent = logData.verdict || 'N/A';
        row.insertCell(3).textContent = logData.log || '-';
        row.insertCell(4).innerHTML = formatRiskScore(logData.risk_score);
        row.insertCell(5).innerHTML = formatSequenceRisk(logData.sequence_risk);
        if (labelText === 'anomaly') {
            row.classList.add(getRiskRowClass(logData.risk_score));
        }
    });
}

export function renderLogRow(data, shouldUpdateState = true) {
    const tableBody = document.getElementById("logsTableBody");
    if (!tableBody) return;

    if (tableBody) {
        const row = shouldUpdateState ? tableBody.insertRow(0) : tableBody.insertRow(-1);
        const labelText = (data.label || 'unknown').toLowerCase().trim();
        row.className = 'fade-in log-row-clickable';

        row.addEventListener('click', () => showLogContext(data.timestamp, data.log, data.id));

        // Timestamp
        row.insertCell(0).textContent = new Date(data.timestamp).toLocaleString();

        // Enhanced Label Pill
        const labelIcon = labelText === 'normal'
            ? '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>'
            : '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
        row.insertCell(1).innerHTML = `<span class="label-pill ${labelText}">${labelIcon} ${labelText}</span>`;

        // Verdict
        row.insertCell(2).textContent = data.verdict || 'N/A';

        // Content with cell styling
        const contentCell = row.insertCell(3);
        contentCell.className = 'content-cell';
        contentCell.textContent = data.log || '-';

        // Risk Score (now progress bar)
        row.insertCell(4).innerHTML = formatRiskScore(data.risk_score);

        // Sequence Risk
        row.insertCell(5).innerHTML = formatSequenceRisk(data.sequence_risk);

        if (data.label === 'anomaly') {
            row.classList.add(getRiskRowClass(data.risk_score) || 'log-anomaly');
        }
    }
}

export function renderAnomalyFeedRow(alert, isNew) {
    const tableBody = document.getElementById("anomalyFeedTableBody");
    if (!tableBody) return;

    const noAlertsRow = tableBody.querySelector('.no-alerts-row');
    if (noAlertsRow) noAlertsRow.remove();

    const row = tableBody.insertRow(0);
    row.id = `alert-row-${alert.id}`;
    row.className = `${isNew ? 'fade-in' : ''} log-row-clickable ${getRiskRowClass(alert.risk_score)}`;

    row.addEventListener('click', (event) => {
        // Only trigger if the click was not on a button inside the row
        if (event.target.tagName !== 'BUTTON' && event.target.tagName !== 'A') {
            showLogContext(alert.timestamp, alert.content, alert.log_id);
        }
    });

    let techniqueLink = 'N/A';
    if (alert.mitre_technique) {
        const techniqueUrl = alert.mitre_technique.replace('.', '/');
        techniqueLink = `<a href="https://attack.mitre.org/techniques/${techniqueUrl}/" target="_blank" title="View on MITRE ATT&CK®">${alert.mitre_technique}</a>`;
    }

    row.insertCell(0).innerHTML = `<span class="status-badge status-${alert.status.toLowerCase()}">${alert.status}</span>`;
    row.insertCell(1).innerHTML = formatRiskScore(alert.risk_score);

    // Threat Intel Badge Logic
    let intelBadge = '';
    if (alert.threat_intel) {
        let ti = alert.threat_intel;
        if (typeof ti === 'string') {
            try { ti = JSON.parse(ti); } catch (e) { }
        }
        if (ti && ti.abuseConfidenceScore !== undefined) {
            const score = ti.abuseConfidenceScore;
            const country = ti.countryCode || '?';
            const colorClass = score > 50 ? 'text-critical' : 'text-warning'; // utilizing existing or simple classes
            intelBadge = `<span class="ti-badge ${colorClass}" title="AbuseIPDB Score: ${score}% (${ti.isp})"> 🌐 ${country} ${score}%</span>`;
        }
    }

    row.insertCell(2).innerHTML = escapeHTML(alert.content) + intelBadge;
    row.insertCell(3).textContent = alert.rule_description || 'N/A';
    row.insertCell(4).innerHTML = techniqueLink;
    // Cell for Actions
    const actionsCell = row.insertCell(5);
    actionsCell.className = 'actions-cell';
    if (alert.status !== 'Closed') {
        // Create the "Acknowledge" button if the status is 'New'
        if (alert.status === 'New') {
            const ackBtn = document.createElement('button');
            ackBtn.className = 'action-btn btn-acknowledge';
            ackBtn.textContent = 'Acknowledge';
            ackBtn.addEventListener('click', () => updateAlertStatus(alert.id, 'Acknowledged'));
            actionsCell.appendChild(ackBtn);
        }

        // Create the "Close" button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'action-btn btn-close';
        closeBtn.textContent = 'Close';
        closeBtn.addEventListener('click', () => updateAlertStatus(alert.id, 'Closed'));
        actionsCell.appendChild(closeBtn);

    } else {
        actionsCell.innerHTML = '<span class="status-closed-text">Closed</span>';
    }
}

export function renderAlertRow(data) {
    const container = document.getElementById("alertsContainer");
    if (!container) return;

    const div = document.createElement('div');
    div.className = 'alert-card-enhanced fade-in';
    div.id = `critical-alert-${data.id}`;

    const statusHTML = data.status ? formatStatusBadge(data.status) : '';
    const advice = data.advice || `(${data.rule_name || 'Anomaly Detected'})`;
    const log = escapeHTML(data.log || data.content || "N/A");
    const riskScore = (data.risk_score || 0).toFixed(2);

    // Threat intel badge
    let threatBadge = '';
    if (data.threat_intel) {
        let ti = data.threat_intel;
        if (typeof ti === 'string') try { ti = JSON.parse(ti); } catch (e) { }
        if (ti && ti.abuseConfidenceScore) {
            const scoreClass = ti.abuseConfidenceScore > 60 ? 'critical' : ti.abuseConfidenceScore > 30 ? 'high' : 'medium';
            threatBadge = `<span class="sigma-severity-badge ${scoreClass}">${ti.abuseConfidenceScore}% Risk</span>`;
        }
    }

    div.innerHTML = `
        <div class="alert-card-header">
            <span class="alert-card-title">🚨 ${escapeHTML(advice)}</span>
            <div style="display: flex; gap: 8px; align-items: center;">
                ${threatBadge}
                ${statusHTML}
            </div>
        </div>
        <div class="alert-card-content">${log}</div>
        <div class="alert-card-meta">
            <span>Risk Score: <strong>${riskScore}</strong></span>
            <span>Count: <strong>${data.count || 1}x</strong></span>
            <span style="margin-left: auto; color: var(--button-primary); cursor: pointer;" class="view-remediation-link" data-alert-id="${data.id}">View Remediation →</span>
        </div>
    `;

    // Click handler for "View Remediation" link
    div.querySelector('.view-remediation-link')?.addEventListener('click', (e) => {
        e.stopPropagation();
        openAlertSidePanel(data);
    });

    container.prepend(div);
}

// Open side panel with mock remediation content
export function openAlertSidePanel(alertData) {
    const sidePanel = document.getElementById('alert-side-panel');
    const sidePanelBody = document.getElementById('side-panel-body');
    const sidePanelOverlay = document.getElementById('side-panel-overlay');

    if (!sidePanel || !sidePanelBody) return;

    const ruleName = alertData.rule_name || 'Security Anomaly';
    const riskScore = (alertData.risk_score || 0).toFixed(2);

    // Mock remediation content
    sidePanelBody.innerHTML = `
        <div class="remediation-section">
            <h4>
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path></svg>
                Alert Summary
            </h4>
            <div style="background: var(--card-bg); padding: 15px; border-radius: 8px; border: 1px solid var(--border-color);">
                <p style="margin: 0 0 10px 0;"><strong>Rule:</strong> ${escapeHTML(ruleName)}</p>
                <p style="margin: 0 0 10px 0;"><strong>Risk Score:</strong> ${riskScore}</p>
                <p style="margin: 0;"><strong>Log:</strong> <code style="font-size: 0.85em;">${escapeHTML(alertData.log || alertData.content || 'N/A')}</code></p>
            </div>
        </div>

        <div class="remediation-section">
            <h4>
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                Recommended Actions
            </h4>
            <ul class="remediation-steps">
                <li>
                    <span class="step-number">1</span>
                    <span>Isolate the affected system from the network to prevent lateral movement.</span>
                </li>
                <li>
                    <span class="step-number">2</span>
                    <span>Review recent authentication logs for unusual login patterns.</span>
                </li>
                <li>
                    <span class="step-number">3</span>
                    <span>Check for persistence mechanisms (cron jobs, startup scripts).</span>
                </li>
                <li>
                    <span class="step-number">4</span>
                    <span>Scan for malware or unauthorized software installations.</span>
                </li>
            </ul>
        </div>

        <div class="remediation-section">
            <h4>
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                Mitigation Steps
            </h4>
            <ul class="remediation-steps">
                <li>
                    <span class="step-number">1</span>
                    <span>Reset credentials for any affected accounts.</span>
                </li>
                <li>
                    <span class="step-number">2</span>
                    <span>Enable multi-factor authentication if not already active.</span>
                </li>
                <li>
                    <span class="step-number">3</span>
                    <span>Update firewall rules to block suspicious IP addresses.</span>
                </li>
            </ul>
        </div>

        <div class="side-panel-ai-section">
            <div class="side-panel-ai-header">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12a10 10 0 0 1 10-10z"></path>
                    <path d="M12 6v6l4 2"></path>
                </svg>
                <h4>AI-Powered Analysis</h4>
            </div>
            <div class="side-panel-ai-buttons">
                <button class="side-panel-ai-btn summary-btn" id="ai-summary-btn" data-alert-id="${alertData.id}">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                    </svg>
                    Generate Summary
                </button>
                <button class="side-panel-ai-btn remediation-btn" id="ai-remediation-btn" data-alert-id="${alertData.id}">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                    Get AI Remediation
                </button>
            </div>
            <div id="ai-result-container"></div>
        </div>
    `;

    // Open panel
    sidePanel.classList.add('open');
    if (sidePanelOverlay) sidePanelOverlay.style.display = 'block';

    // AI Button Event Handlers
    const summaryBtn = document.getElementById('ai-summary-btn');
    const remediationBtn = document.getElementById('ai-remediation-btn');
    const resultContainer = document.getElementById('ai-result-container');

    if (summaryBtn) {
        summaryBtn.addEventListener('click', async () => {
            summaryBtn.classList.add('loading');
            summaryBtn.innerHTML = '<span class="btn-spinner"></span> Generating...';

            try {
                const response = await fetch(`/api/ai/summarize/${alertData.id}`);
                const data = await response.json();

                if (response.ok) {
                    resultContainer.innerHTML = renderAIResult('AI Summary', data.content, data.provider);
                } else {
                    resultContainer.innerHTML = renderAIError(data.detail || 'Failed to generate summary');
                }
            } catch (err) {
                console.error('AI Summary error:', err);
                resultContainer.innerHTML = renderAIError('Failed to connect to AI service');
            } finally {
                summaryBtn.classList.remove('loading');
                summaryBtn.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                        <line x1="16" y1="13" x2="8" y2="13"></line>
                        <line x1="16" y1="17" x2="8" y2="17"></line>
                    </svg>
                    Generate Summary
                `;
            }
        });
    }

    if (remediationBtn) {
        remediationBtn.addEventListener('click', async () => {
            remediationBtn.classList.add('loading');
            remediationBtn.innerHTML = '<span class="btn-spinner"></span> Generating...';

            try {
                const response = await fetch(`/api/ai/remediation/${alertData.id}`);
                const data = await response.json();

                if (response.ok) {
                    resultContainer.innerHTML = renderAIResult('AI Remediation Steps', data.content, data.provider);
                } else {
                    resultContainer.innerHTML = renderAIError(data.detail || 'Failed to generate remediation');
                }
            } catch (err) {
                console.error('AI Remediation error:', err);
                resultContainer.innerHTML = renderAIError('Failed to connect to AI service');
            } finally {
                remediationBtn.classList.remove('loading');
                remediationBtn.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                    Get AI Remediation
                `;
            }
        });
    }
}

// Helper function to render AI results with markdown support
function renderAIResult(title, content, provider) {
    const renderedContent = renderAIMarkdown(content);
    return `
        <div class="side-panel-ai-result">
            <div class="side-panel-ai-result-header">
                <span class="side-panel-ai-result-title">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12a10 10 0 0 1 10-10z"></path>
                    </svg>
                    ${title}
                </span>
                <span class="side-panel-ai-result-provider">via ${provider || 'AI'}</span>
            </div>
            <div class="side-panel-ai-result-content ai-content-wrapper">
                ${renderedContent}
            </div>
        </div>
    `;
}

function renderAIError(message) {
    return `
        <div class="side-panel-ai-result" style="border-color: var(--text-red);">
            <p style="color: var(--text-red); margin: 0;">⚠️ ${message}</p>
        </div>
    `;
}

function renderAIMarkdown(content) {
    let html = content;

    // Escape HTML
    html = html.replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h4 class="ai-section-title ai-h4"><span class="ai-title-icon">▸</span>$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 class="ai-section-title ai-h3"><span class="ai-title-icon">◆</span>$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2 class="ai-section-title ai-h2"><span class="ai-title-icon">★</span>$1</h2>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="ai-highlight">$1</strong>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code class="ai-inline-code">$1</code>');

    // Bullet points
    html = html.replace(/^[\-\*•] (.+)$/gm, '<li class="ai-list-item"><span class="ai-bullet">●</span><span class="ai-list-content">$1</span></li>');

    // Numbered lists
    html = html.replace(/^(\d+)\. (.+)$/gm, '<li class="ai-list-item ai-numbered"><span class="ai-number">$1</span><span class="ai-list-content">$2</span></li>');

    // Wrap lists
    html = html.replace(/(<li class="ai-list-item[^"]*">[\s\S]*?<\/li>\n?)+/g, (match) => `<ul class="ai-list">${match}</ul>`);

    // Paragraphs
    html = html.replace(/\n\n+/g, '</p><p class="ai-paragraph">');
    html = html.replace(/\n/g, '<br>');

    return `<p class="ai-paragraph">${html}</p>`;
}

export function handleStatusUpdate(data) {
    const { alert_id, log_id, new_status } = data;

    // Update the main anomaly feed row (Flagged section)
    const anomalyRow = document.getElementById(`alert-row-${alert_id}`);
    if (anomalyRow) {
        const statusBadge = anomalyRow.querySelector('.status-badge');
        const actionsCell = anomalyRow.querySelector('.actions-cell');

        statusBadge.className = `status-badge status-${new_status.toLowerCase()}`;
        statusBadge.textContent = new_status;

        if (new_status === 'Closed') {
            anomalyRow.style.opacity = '0.5';
            actionsCell.innerHTML = '<span class="status-closed-text">Closed</span>';
        } else if (new_status === 'Acknowledged') {
            actionsCell.innerHTML = '';
            const closeBtn = document.createElement('button');
            closeBtn.className = 'action-btn btn-close';
            closeBtn.textContent = 'Close';
            closeBtn.addEventListener('click', () => updateAlertStatus(alert_id, 'Closed'));
            actionsCell.appendChild(closeBtn);
        }
    }

    // Sync status to Alerts panel (critical alerts)
    const criticalAlertDiv = document.getElementById(`critical-alert-${alert_id}`);
    if (criticalAlertDiv) {
        // Update status badge in alert card header
        const statusBadgeCell = criticalAlertDiv.querySelector('.status-badge');
        if (statusBadgeCell) {
            statusBadgeCell.className = `status-badge status-${new_status.toLowerCase()}`;
            statusBadgeCell.textContent = new_status;
        }
        // If closed, dim the alert card
        if (new_status === 'Closed') {
            criticalAlertDiv.style.opacity = '0.5';
        }
    }

    // Find and update all other instances of this log (e.g., in search or review)
    const otherLogRows = document.querySelectorAll(`tr[data-log-id='${log_id}']`);
    otherLogRows.forEach(row => {
        const statusCell = row.querySelector('.status-badge-cell');
        if (statusCell) {
            statusCell.innerHTML = formatStatusBadge(new_status);
        }
    });
}

export async function updateAlertStatus(alertId, newStatus) {
    const rowElement = document.getElementById(`alert-row-${alertId}`);
    if (!rowElement) {
        console.error(`Alert row with ID ${alertId} not found.`);
        return;
    }

    try {
        const apiResponse = await api.postAlertStatusUpdate(alertId, newStatus);

        console.log('Server Response:', apiResponse);

        if (!apiResponse.message) {
            throw new Error('API response did not contain a success message.');
        }

        if (newStatus === 'Closed') {
            rowElement.style.opacity = '0.5';
            const actionsCell = rowElement.querySelector('.actions-cell');
            if (actionsCell) {
                actionsCell.innerHTML = '<span class="status-closed-text">Closed</span>';
            }
        } else if (newStatus === 'Acknowledged') {
            const actionsCell = rowElement.querySelector('.actions-cell');
            const statusBadge = rowElement.querySelector('.status-badge');

            if (actionsCell) {
                // Important: Avoid using onclick strings; use addEventListener instead
                // for better compatibility with modern JavaScript modules.
                actionsCell.innerHTML = `<button class="action-btn">Close</button>`;
                actionsCell.querySelector('button').addEventListener('click', () => updateAlertStatus(alertId, 'Closed'));
            }
            if (statusBadge) {
                statusBadge.className = 'status-badge status-acknowledged';
                statusBadge.textContent = 'Acknowledged';
            }
        } else {
            loadInitialAnomalies(); // Refresh the list for other changes
        }
    } catch (error) {
        console.error("Failed to update alert status:", error);
    }
}

export function handleAlertUpdate(data) {
    const alertElement = document.getElementById(`alert-${data.id}`);
    if (alertElement) {
        const counter = alertElement.querySelector('.alert-counter');
        if (counter) {
            counter.textContent = `(${data.count}x)`;
            // Add a brief animation to draw attention to the update
            counter.classList.add('flash');
            setTimeout(() => counter.classList.remove('flash'), 500);
        }
    }
}

export function updateMonitoringStatusUI(isActive) {
    const button = document.getElementById('monitoring-toggle-btn');
    if (!button) return;
    const text = button.querySelector('.text');

    if (isActive) {
        button.classList.add('active');
        button.classList.remove('paused');
        text.textContent = 'Monitoring';
    } else {
        button.classList.add('paused');
        button.classList.remove('active');
        text.textContent = 'Resume';
    }
}

export async function showLogContext(timestamp, originalLogContent, logId) {
    console.log('showLogContext called with', timestamp, originalLogContent, logId);

    const modal = document.getElementById('log-context-modal');
    const tabTimeline = document.getElementById('tab-timeline');
    const tabThreatIntel = document.getElementById('tab-threat-intel');
    const tabLime = document.getElementById('tab-lime');
    const modalSummary = document.getElementById('modal-log-summary');

    if (!modal || !tabTimeline) return;

    // Reset tabs to default state
    document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.modal-tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('.modal-tab[data-tab="timeline"]').classList.add('active');
    tabTimeline.classList.add('active');

    // Show loading state
    tabTimeline.innerHTML = '<p>Loading context...</p>';
    tabThreatIntel.innerHTML = '<p>No threat intelligence data available.</p>';
    tabLime.innerHTML = '<p>No model explanation available.</p>';
    modalSummary.innerHTML = '';
    modal.style.display = 'flex';

    try {
        const contextLogs = await api.fetchLogContext(timestamp);
        const targetLog = contextLogs.find(log => log.id === logId);

        if (contextLogs.length === 0) {
            tabTimeline.innerHTML = '<p>No surrounding log entries found.</p>';
            return;
        }

        if (!targetLog) {
            tabTimeline.innerHTML = '<p>Could not find the specific log entry.</p>';
            return;
        }

        // Populate modal summary
        const labelClass = targetLog.final_label === 1 ? 'anomaly' : 'normal';
        modalSummary.innerHTML = `
            <span class="badge">${labelClass.toUpperCase()}</span>
            <span class="badge">Risk: ${(targetLog.risk_score || 0).toFixed(2)}</span>
            <span class="badge">Source: ${targetLog.source || 'Unknown'}</span>
        `;

        // === TAB 1: Timeline ===
        let timelineHTML = '<div class="timeline-enhanced">';
        contextLogs.forEach(log => {
            const isTarget = log.id === logId;
            const labelText = log.final_label === 1 ? 'anomaly' : 'normal';
            const time = new Date(log.timestamp).toLocaleTimeString('en-US', { hour12: false });

            timelineHTML += `
                <div class="timeline-item-enhanced ${isTarget ? 'target' : ''} label-${labelText}">
                    <div class="timeline-item-header">
                        <span class="timeline-item-time">⏱️ ${time}</span>
                        <span class="label-pill ${labelText}">${labelText}</span>
                    </div>
                    <div class="timeline-item-content">${escapeHTML(log.content)}</div>
                </div>
            `;
        });
        timelineHTML += '</div>';
        tabTimeline.innerHTML = timelineHTML;

        // === TAB 2: Threat Intelligence ===
        if (targetLog.threat_intel) {
            let intel = targetLog.threat_intel;
            if (typeof intel === 'string') try { intel = JSON.parse(intel); } catch (e) { }

            const score = intel.abuseConfidenceScore || 0;
            let scoreClass = 'low';
            if (score > 80) scoreClass = 'critical';
            else if (score > 60) scoreClass = 'high';
            else if (score > 30) scoreClass = 'medium';

            tabThreatIntel.innerHTML = `
                <div class="threat-intel-card">
                    <div class="threat-intel-header">
                        <div class="threat-score-gauge ${scoreClass}">${score}%</div>
                        <div>
                            <h4 style="margin: 0 0 5px 0;">AbuseIPDB Report</h4>
                            <p style="margin: 0; color: var(--text-color-secondary);">IP Reputation Score</p>
                        </div>
                    </div>
                    <div class="threat-intel-details">
                        <div class="threat-intel-detail">
                            <label>Country</label>
                            <span>${intel.countryCode || 'N/A'}</span>
                        </div>
                        <div class="threat-intel-detail">
                            <label>ISP</label>
                            <span>${escapeHTML(intel.isp || 'N/A')}</span>
                        </div>
                        <div class="threat-intel-detail">
                            <label>Total Reports</label>
                            <span>${intel.totalReports || 0}</span>
                        </div>
                        <div class="threat-intel-detail">
                            <label>Last Reported</label>
                            <span>${intel.lastReportedAt ? new Date(intel.lastReportedAt).toLocaleDateString() : 'N/A'}</span>
                        </div>
                    </div>
                </div>
            `;
        } else {
            tabThreatIntel.innerHTML = `
                <div class="threat-intel-card" style="text-align: center; padding: 40px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-color-secondary)" stroke-width="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                    <h4 style="margin: 15px 0 5px 0;">No Threat Intelligence Available</h4>
                    <p style="color: var(--text-color-secondary);">No IP address was extracted or no reputation data found.</p>
                </div>
            `;
        }

        // === TAB 3: LIME Explanation ===
        if (targetLog.final_label === 1) {
            if (targetLog.explanation) {
                tabLime.innerHTML = `
                    <div class="lime-explanation-card">
                        <h4 style="margin: 0 0 20px 0; display: flex; align-items: center; gap: 10px;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--button-primary)" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
                            LIME Feature Importance
                        </h4>
                        ${targetLog.explanation}
                    </div>
                `;
            } else {
                tabLime.innerHTML = `
                    <div class="lime-explanation-card" id="explanation-for-${targetLog.id}">
                        <h4 style="margin: 0 0 20px 0;">Generating Explanation...</h4>
                        <p>Please wait while the model explanation is being generated.</p>
                    </div>
                `;
                // Fetch asynchronously
                api.fetchLogExplanation(targetLog.id)
                    .then(data => {
                        const container = document.getElementById(`explanation-for-${targetLog.id}`);
                        if (container && data.explanation_html) {
                            container.innerHTML = `
                                <h4 style="margin: 0 0 20px 0; display: flex; align-items: center; gap: 10px;">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--button-primary)" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
                                    LIME Feature Importance
                                </h4>
                                ${data.explanation_html}
                            `;
                        } else if (container) {
                            container.innerHTML = '<p>Explanation not available for this log.</p>';
                        }
                    })
                    .catch(err => {
                        console.error('LIME fetch error:', err);
                        const container = document.getElementById(`explanation-for-${targetLog.id}`);
                        if (container) container.innerHTML = '<p>Could not load explanation.</p>';
                    });
            }
        } else {
            tabLime.innerHTML = `
                <div class="lime-explanation-card" style="text-align: center; padding: 40px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-color-secondary)" stroke-width="1.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    <h4 style="margin: 15px 0 5px 0;">No Explanation Needed</h4>
                    <p style="color: var(--text-color-secondary);">This log was classified as normal. LIME explanations are only generated for anomalies.</p>
                </div>
            `;
        }

        // === TAB 4: Notes (Phase 5) ===
        const tabNotes = document.getElementById('tab-notes');
        if (tabNotes) {
            tabNotes.innerHTML = `
                <div class="notes-section">
                    <div class="notes-input-area">
                        <textarea id="new-note-input" placeholder="Add investigation note..." rows="3" 
                            style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--card-border); background: var(--card-dark-bg); color: var(--text-color); resize: vertical;"></textarea>
                        <button id="add-note-btn" class="btn-primary" style="margin-top: 8px;" data-log-id="${logId}">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                            Add Note
                        </button>
                    </div>
                    <div id="notes-list" class="notes-list" style="margin-top: 20px;">
                        <p style="color: var(--text-color-secondary);">Loading notes...</p>
                    </div>
                </div>
            `;
            // Fetch existing notes for this alert
            loadAlertNotes(logId);

            // Add note button handler
            document.getElementById('add-note-btn')?.addEventListener('click', async () => {
                const noteInput = document.getElementById('new-note-input');
                const noteText = noteInput?.value?.trim();
                if (!noteText) return;

                try {
                    const response = await fetch(`/api/alerts/${logId}/notes`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ note: noteText })
                    });
                    if (response.ok) {
                        noteInput.value = '';
                        loadAlertNotes(logId);
                        showToast('Note added successfully', 'success');
                    }
                } catch (err) {
                    console.error('Failed to add note:', err);
                    showToast('Failed to add note', 'error');
                }
            });
        }

        // === TAB 5: Session Replay (Phase 5) ===
        const tabSession = document.getElementById('tab-session');
        if (tabSession) {
            // Extract IP from log content for session lookup
            const ipMatch = originalLogContent?.match(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/);
            const sessionKey = ipMatch ? ipMatch[0] : null;

            if (sessionKey) {
                tabSession.innerHTML = `
                    <div class="session-replay-header" style="margin-bottom: 16px;">
                        <h4 style="margin: 0; display: flex; align-items: center; gap: 8px;">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--button-primary)" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            Session Timeline: ${sessionKey}
                        </h4>
                    </div>
                    <div id="session-timeline-content" style="max-height: 400px; overflow-y: auto;">
                        <p>Loading session data...</p>
                    </div>
                `;
                loadSessionTimeline(sessionKey);
            } else {
                tabSession.innerHTML = `
                    <div style="text-align: center; padding: 40px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-color-secondary)" stroke-width="1.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
                        <h4 style="margin: 15px 0 5px 0;">No Session Data</h4>
                        <p style="color: var(--text-color-secondary);">Could not extract IP address from this log for session replay.</p>
                    </div>
                `;
            }
        }

    } catch (error) {
        tabTimeline.innerHTML = '<p>Error loading log context.</p>';
        console.error('Error in showLogContext:', error);
    }
}

// Helper function to load alert notes
async function loadAlertNotes(alertId) {
    const notesList = document.getElementById('notes-list');
    if (!notesList) return;

    try {
        const response = await fetch(`/api/alerts/${alertId}/notes`);
        const notes = await response.json();

        if (!notes || notes.length === 0) {
            notesList.innerHTML = '<p style="color: var(--text-color-secondary); text-align: center;">No notes yet. Add the first note above.</p>';
            return;
        }

        notesList.innerHTML = notes.map(note => `
            <div class="note-item" style="background: var(--card-dark-bg); padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 3px solid var(--button-primary);">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="font-weight: 600; color: var(--text-color);">${escapeHTML(note.username || 'Unknown')}</span>
                    <span style="color: var(--text-color-secondary); font-size: 12px;">${new Date(note.created_at).toLocaleString()}</span>
                </div>
                <p style="margin: 0; color: var(--text-color);">${escapeHTML(note.note)}</p>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load notes:', err);
        notesList.innerHTML = '<p style="color: var(--danger-color);">Failed to load notes.</p>';
    }
}

// Helper function to load session timeline
async function loadSessionTimeline(sessionKey) {
    const container = document.getElementById('session-timeline-content');
    if (!container) return;

    try {
        const response = await fetch(`/api/sessions/${encodeURIComponent(sessionKey)}/timeline`);
        const logs = await response.json();

        if (!logs || logs.length === 0) {
            container.innerHTML = '<p style="color: var(--text-color-secondary); text-align: center;">No session data found for this IP.</p>';
            return;
        }

        container.innerHTML = `
            <div class="session-chain" style="display: flex; flex-direction: column; gap: 8px;">
                ${logs.map((log, i) => {
            const isAnomaly = log.verdict !== 'Normal';
            const time = new Date(log.timestamp).toLocaleTimeString('en-US', { hour12: false });
            const mitre = log.mitre_technique ? `<span class="badge" style="background: var(--accent-purple); font-size: 10px;">${log.mitre_technique}</span>` : '';

            return `
                        <div class="session-event" style="display: flex; align-items: flex-start; gap: 12px; ${isAnomaly ? 'background: rgba(239, 68, 68, 0.1); padding: 8px; border-radius: 8px;' : ''}">
                            <div style="display: flex; flex-direction: column; align-items: center; width: 60px; flex-shrink: 0;">
                                <span style="font-size: 11px; color: var(--text-color-secondary);">${time}</span>
                                <div style="width: 2px; height: 20px; background: var(--card-border); margin-top: 4px;"></div>
                            </div>
                            <div style="flex: 1;">
                                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                    <span class="badge" style="background: ${isAnomaly ? 'var(--danger-color)' : 'var(--success-color)'}; font-size: 10px;">${log.verdict || 'Normal'}</span>
                                    ${mitre}
                                </div>
                                <p style="margin: 0; font-family: monospace; font-size: 12px; color: var(--text-color); word-break: break-all;">${escapeHTML(log.content?.substring(0, 200) || '-')}${log.content?.length > 200 ? '...' : ''}</p>
                            </div>
                        </div>
                    `;
        }).join('')}
            </div>
        `;
    } catch (err) {
        console.error('Failed to load session timeline:', err);
        container.innerHTML = '<p style="color: var(--danger-color);">Failed to load session data.</p>';
    }
}

// export function toggleDarkMode() {
//     document.body.classList.toggle('dark-mode');
//     charts.updateAllChartColors();
// }

export function autoScroll(containerId) {
    let container = document.getElementById(containerId);
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

export function pollTaskStatus(taskId) {
    const intervalId = setInterval(async () => {
        try {
            const data = await api.fetchRetrainStatus();

            const progressBar = document.getElementById(`progress-${taskId}`);
            const toastMessage = document.getElementById(`toast-message-${taskId}`);

            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(intervalId); // Stop polling
                if (progressBar) {
                    progressBar.style.display = 'none'; // Hide progress bar
                }
                if (toastMessage) {
                    toastMessage.textContent = data.message;
                    // Change toast color based on final status
                    const toast = toastMessage.parentElement;
                    toast.className = `toast ${data.status === 'completed' ? 'success' : 'error'}`;
                }
                // Auto-dismiss the final status message
                setTimeout(() => {
                    const toast = toastMessage.parentElement;
                    toast.style.animation = 'slideOutFadeOut 0.5s ease forwards';
                    setTimeout(() => toast.remove(), 500);
                }, 7000);
            }
        } catch (error) {
            console.error('Polling failed:', error);
            clearInterval(intervalId); // Stop polling on error
        }
    }, 2000); // Check status every 2 seconds
}

function createThreatIntelHTML(intel) {
    if (!intel) return '';

    const score = intel.abuseConfidenceScore || 0;
    let scoreClass = 'risk-low';
    let scoreLabel = 'Low';
    if (score > 80) { scoreClass = 'risk-critical'; scoreLabel = 'Critical'; }
    else if (score > 60) { scoreClass = 'risk-high'; scoreLabel = 'High'; }
    else if (score > 30) { scoreClass = 'risk-low-medium'; scoreLabel = 'Medium'; }

    return `
        <div class="threat-intel-report">
            <h4>
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                Threat Intelligence Report (AbuseIPDB)
            </h4>
            <div class="threat-intel-grid">
                <div><strong>Abuse Score:</strong> <span class="${scoreClass}">${score}% (${scoreLabel})</span></div>
                <div><strong>Country:</strong> ${escapeHTML(intel.countryCode || 'N/A')}</div>
                <div><strong>ISP:</strong> ${escapeHTML(intel.isp || 'N/A')}</div>
                <div><strong>Total Reports:</strong> ${intel.totalReports || 0}</div>
            </div>
        </div>
    `;
}

export function renderRestoredAnomalies(anomalies) {
    const tableBody = document.getElementById("anomalyFeedTableBody");
    if (!anomalies || !tableBody) return;

    tableBody.innerHTML = '';
    // Re-render each anomaly from the cache, oldest first
    anomalies.slice().reverse().forEach(alertData => {
        renderAnomalyFeedRow(alertData, false); // "false" because it's not a new, animated entry
    });
}

export function renderSigmaMatchRow(data) {
    const container = document.getElementById("sigmaDetectionsContainer");
    if (!container) return;

    // Remove the placeholder if it exists
    const placeholder = container.querySelector('.no-alerts-placeholder');
    if (placeholder) placeholder.remove();

    const div = document.createElement('div');
    const level = data.level.toLowerCase();

    // Enhanced sigma detection card structure
    div.className = `sigma-detection-card level-${level} fade-in`;

    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false });

    div.innerHTML = `
        <div class="sigma-card-header">
            <div class="sigma-card-title">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
                ${escapeHTML(data.title)}
            </div>
            <span class="sigma-severity-badge ${level}">${escapeHTML(data.level)}</span>
        </div>
        <div class="sigma-card-body">
            <div class="sigma-log-content">${escapeHTML(data.log)}</div>
            <div class="sigma-cause-section">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
                <span class="sigma-cause-text">${escapeHTML(data.description || data.title)} - Potential security incident detected by Sigma rule.</span>
            </div>
        </div>
        <div class="sigma-card-footer">
            <span>⏱️ ${timestamp}</span>
            <span>Rule: ${escapeHTML(data.rule_id || 'N/A')}</span>
        </div>
    `;
    container.prepend(div);

    // Keep the panel from getting too long
    while (container.children.length > 30) {
        container.removeChild(container.lastChild);
    }
}