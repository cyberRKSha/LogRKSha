// static/js/ui.js
import * as api from './api.js';
import { animateCount, escapeHTML, formatRiskScore, getRiskRowClass, formatSequenceRisk, formatStatusBadge } from './utils.js';
import * as charts from './charts.js';
// import {} from './script.js'; 


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
             row.setAttribute('onclick', `showLogContext('${logData.timestamp}', '${escapedContent}')`);
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
        const escapedContent = (data.log || '-').replace(/'/g, "\\'");
        // row.setAttribute('onclick', `showLogContext('${data.timestamp}', '${escapedContent}')`);
        row.addEventListener('click', () => showLogContext(data.timestamp, data.log, data.id));
        row.insertCell(0).textContent = new Date(data.timestamp).toLocaleString();
        row.insertCell(1).innerHTML = `<span class="label-${labelText}">${labelText}</span>`;
        row.insertCell(2).textContent = data.verdict || 'N/A';
        row.insertCell(3).textContent = data.log || '-';
        row.insertCell(4).innerHTML = formatRiskScore(data.risk_score);
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
        if (event.target.tagName !== 'BUTTON') {
            const logId = alert.log_id || alert.id; // Get the ID from the alert object
            showLogContext(alert.timestamp, alert.content, alert.log_id || logId);
        }
    });

    row.insertCell(0).innerHTML = `<span class="status-badge status-${alert.status.toLowerCase()}">${alert.status}</span>`;
    row.insertCell(1).innerHTML = formatRiskScore(alert.risk_score);
    const contentCell = row.insertCell(2);
    contentCell.className = 'log-content';
    contentCell.textContent = alert.content;
    // Cell for Actions
    const actionsCell = row.insertCell(3);
    actionsCell.className = 'actions-cell';
    if (alert.status !== 'Closed') {
        // Create the "Acknowledge" button if the status is 'New'
        if (alert.status === 'New') {
            const ackBtn = document.createElement('button');
            ackBtn.className = 'action-btn';
            ackBtn.textContent = 'Acknowledge';
            ackBtn.addEventListener('click', () => updateAlertStatus(alert.id, 'Acknowledged'));
            actionsCell.appendChild(ackBtn);
        }
        
        // Create the "Close" button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'action-btn';
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

    // criticalAlertsCache[data.id] = data;

    const div = document.createElement('div');
    div.className = 'alert-critical fade-in';
    div.id = `critical-alert-${data.id}`;
    // div.setAttribute('data-log-id', data.id);
    
    const statusHTML = data.status ? formatStatusBadge(data.status) : '';
    const advice = data.advice || `(${data.rule_name || 'Anomaly'}) | Risk: ${(data.risk_score || 0).toFixed(2)}` || "No advice.";
    const log = data.log || data.content || "N/A";
    
    div.innerHTML = `
        <div class="alert-header">
            <strong>Critical Alert</strong>
            <div class="status-badge-cell id="critical-status-${data.id}">${statusHTML}</div>
        </div>
        ${advice}<br>
        <small>Ref Log: ${log}</small>
        <span class="alert-counter">(${data.count || 1}x)</span>
    `;
    container.prepend(div);
}

export function handleStatusUpdate(data) {
    const { alert_id, log_id, new_status } = data;
    // const newStatusLower = new_status.toLowerCase();

    // Update the main anomaly feed row
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
            // actionsCell.innerHTML = `<button class="action-btn" onclick="updateAlertStatus(${alert_id}, 'Closed')">Close</button>`;
            // 1. Clear the cell
            actionsCell.innerHTML = ''; 
            
            // 2. Create a new button element
            const closeBtn = document.createElement('button');
            closeBtn.className = 'action-btn';
            closeBtn.textContent = 'Close';
            
            // 3. Attach the click event using addEventListener
            closeBtn.addEventListener('click', () => updateAlertStatus(alert_id, 'Closed'));
            
            // 4. Add the new button to the cell
            actionsCell.appendChild(closeBtn);
        }
    }

    const criticalAlertDiv = document.getElementById(`critical-alert-${alert_id}`);
    if (criticalAlertDiv) {
        const statusCell = criticalAlertDiv.querySelector('.status-badge-cell');
        if (statusCell) {
            statusCell.innerHTML = formatStatusBadge(new_status);
        }
        // // Also update the object in our session cache
        // if (criticalAlertsCache[alert_id]) {
        //     criticalAlertsCache[alert_id].status = new_status;
        // }
    }

    // Find and update all other instances of this log (e.g., in search or review)
    const otherLogRows = document.querySelectorAll(`tr[data-log-id='${log_id}']`);
    otherLogRows.forEach(row => {
        const statusCell = row.querySelector('.status-badge-cell'); // We will add this class
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
    const modal = document.getElementById('log-context-modal');
    const modalBody = document.getElementById('modal-body');
    if (!modal || !modalBody) return;

    modalBody.innerHTML = '<p>Loading context...</p>';
    modal.style.display = 'flex';

    try {
        const contextLogs = await api.fetchLogContext(timestamp);
        
        if (contextLogs.length === 0) {
            modalBody.innerHTML = '<p>No surrounding log entries found.</p>';
            return;
        }

        const targetLog = contextLogs.find(log => log.content === originalLogContent);
        
        let explanationHTML = '';
        if (targetLog && targetLog.final_label === 1) { // Only explain anomalies
            if (targetLog.explanation) {
                // If it exists, display it immediately.
                explanationHTML = `
                    <div class="explanation-container">
                        <h4>Model Explanation (LIME)</h4>
                        ${targetLog.explanation}
                    </div>
                `;
            } else {
                explanationHTML = `
                    <div class="explanation-container" id="explanation-for-${targetLog.id}">
                        <h4>Model Explanation (LIME)</h4>
                        <p class="explanation-status">Generating explanation, please wait...</p>
                    </div>
                `;
                // Fetch the explanation asynchronously after the modal is visible
                api.fetchLogExplanation(targetLog.id)
                    .then(data => {
                        const explanationContainer = document.getElementById(`explanation-for-${targetLog.id}`);
                        if (data.explanation_html) {
                            explanationContainer.innerHTML = `<h4>Model Explanation (LIME)</h4>${data.explanation_html}`;
                        } else {
                            explanationContainer.innerHTML = `<h4>Model Explanation (LIME)</h4><p class="explanation-error">Explanation not available for this log.</p>`;
                        }
                    })
                    .catch(error => {
                    // Handle errors if the explanation fails to load
                    console.error("Failed to fetch LIME explanation:", error);
                    const explanationContainer = document.getElementById(`explanation-for-${targetLog.id}`);
                    if (explanationContainer) {
                        explanationContainer.innerHTML = `<h4>Model Explanation (LIME)</h4><p class="explanation-error">Could not load explanation.</p>`;
                    }
                });
            }
        }

        let timelineHTML = '<div class="timeline">';
        contextLogs.forEach(log => {
            const isTarget = log.content === originalLogContent;
            const labelText = log.final_label === 1 ? 'anomaly' : 'normal';
            const time = new Date(log.timestamp).toLocaleTimeString('en-US', { hour12: false });

            timelineHTML += `
                <div class="timeline-item ${isTarget ? 'target' : ''} label-${labelText}">
                    <div class="timeline-time">${time}</div>
                    <div class="timeline-dot"></div>
                    <div class="timeline-content">
                        <div class="timeline-header">
                            <span class="label-${labelText}">${labelText}</span>
                            <span class="timeline-risk">${formatRiskScore(log.risk_score)}</span>
                            <span class="timeline-source">[${log.source}]</span>
                        </div>
                        <p class="log-content">${escapeHTML(log.content)}</p>
                    </div>
                </div>
            `;
        });
        timelineHTML += '</div>';
        modalBody.innerHTML = explanationHTML + timelineHTML;

    } catch (error) {
        modalBody.innerHTML = '<p>Error loading log context.</p>';
        console.error('Error in showLogContext:', error);
    }
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

export function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    charts.updateAllChartColors();
}

export function autoScroll(containerId) {
    let container = document.getElementById(containerId);
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function pollTaskStatus(taskId) {
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
