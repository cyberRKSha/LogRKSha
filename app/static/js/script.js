let ws;
let historicalChart;
let normalCount = 0;
let anomalyCount = 0;
let totalCount = 0;
let sessionCount = 0;

// === INITIALIZATION ===
window.onload = () => {
    initializeStats();
    connectWebSocket();
    fetchTrainingStats();
    initHistoricalChart();
    setupEventListeners();
    loadInitialAnomalies();
};

function connectWebSocket() {
    ws = new WebSocket("ws://" + window.location.host + "/ws");
    ws.onmessage = handleWebSocketMessage;
    ws.onclose = () => { console.log("WebSocket disconnected. Will try to reconnect..."); setTimeout(connectWebSocket, 5000); };
    ws.onerror = (error) => { console.error("WebSocket error:", error); };
}

// Animate a number smoothly
function animateCount(id, newCount) {
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

// === DATA FETCHING FUNCTIONS ===
async function fetchTrainingStats() {
    try {
        const response = await fetch('/api/training_stats');
        const stats = await response.json();
        document.getElementById('trainedTotal').textContent = stats.total;
        document.getElementById('trainedNormal').textContent = stats.normal;
        document.getElementById('trainedAnomaly').textContent = stats.anomaly;
    } catch (error) {
        console.error('Error fetching training stats:', error);
    }
}

async function initHistoricalChart() {
    try {
        const response = await fetch('/api/historical-trends', { cache: 'no-store' });
        const data = await response.json();

        // Get references to the HTML elements
        const chartCanvas = document.getElementById('historicalChart');
        const chartMessage = document.getElementById('historicalChartMessage');
        const textColor = getComputedStyle(document.body).getPropertyValue('--text-color-primary');

        if (historicalChart) {
            historicalChart.destroy(); // Always destroy the old chart
        }

        // Check if data is empty
        if (!data || data.length === 0) {
            chartCanvas.style.display = 'none'; // HIDE the canvas
            chartMessage.style.display = 'block'; // SHOW the message div
            chartMessage.textContent = 'No historical anomaly data available. Please review logs to populate this chart.';
            return;
        }

        // If data exists, reverse the visibility
        chartCanvas.style.display = 'block'; // SHOW the canvas
        chartMessage.style.display = 'none'; // HIDE the message div

        const ctx = chartCanvas.getContext('2d');
        const labels = data.map(d => d.timestamp);
        const anomalyData = data.map(d => d.anomalies);

        historicalChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{ 
                    label: 'Anomalies per Hour', 
                    data: anomalyData, 
                    borderColor: '#dc3545', 
                    backgroundColor: 'rgba(220, 53, 69, 0.2)', 
                    fill: true, 
                    tension: 0.4 
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: textColor }, grid: { color: 'rgba(128, 128, 128, 0.1)' } },
                    y: { beginAtZero: true, ticks: { stepSize: 1, color: textColor }, grid: { color: 'rgba(128, 128, 128, 0.2)' } }
                },
                plugins: { 
                    legend: { labels: { color: textColor } } 
                }
            }
        });
    } catch (error) {
        console.error('Error fetching historical data:', error);
    }
}

// === WEBSOCKET HANDLER ===
function handleWebSocketMessage(event) {
    const msg = JSON.parse(event.data);
    switch (msg.type) {
        case "session_update":
            // BUG FIX: Directly update the global sessionCount variable.
            sessionCount = msg.count;
            break;
        case "log":
            // This part was correct.
            renderLogRow(msg.data);
            break;
        case "new_actionable_alert":
            // This handles adding new rows to our actionable anomaly feed
            renderAnomalyFeedRow(msg.data, true); 
            break;
        case "alert":
            // This part was correct.
            renderAlertRow(msg.data, true); // Pass 'isNew' flag
            break;
        case "alert_status_update":
            handleStatusUpdate(msg.data);
            break;
    }
    // This call will now work correctly because of the fix in updateStatsUI.
    updateStatsUI();
}


// Toggle dark mode and update chart text colors
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const newTextColor = getComputedStyle(document.body).getPropertyValue('--text-color-primary');
    if (historicalChart) {
        historicalChart.options.plugins.legend.labels.color = newTextColor;
        historicalChart.options.scales.x.ticks.color = newTextColor;
        historicalChart.options.scales.y.ticks.color = newTextColor;
        historicalChart.update();
    }
}

// === UI RENDERING FUNCTIONS ===
function renderLogRow(data) {
    const tableBody = document.getElementById("logsTableBody");
    if (!tableBody) return;
    const row = tableBody.insertRow(0);

    row.setAttribute('data-log-id', data.id);

    row.className = 'fade-in log-row-clickable';
    const escapedContent = (data.log || '-').replace(/'/g, "\\'");
    row.setAttribute('onclick', `showLogContext('${data.timestamp}', '${escapedContent}')`);
    const labelText = (data.label || 'unknown').toLowerCase().trim();
    
    row.insertCell(0).textContent = new Date(data.timestamp).toLocaleString();
    row.insertCell(1).innerHTML = `<span class="label-${labelText}">${labelText}</span>`;
    row.insertCell(2).textContent = data.verdict || 'N/A';
    row.insertCell(3).textContent = data.log || '-';
    row.insertCell(4).innerHTML = formatRiskScore(data.risk_score);

    if (labelText === 'anomaly') {
        row.classList.add('log-anomaly');
        anomalyCount++;
        totalCount++;
        renderAnomalyFeedRow(data);
    } else {
        normalCount++;
    }
    totalCount++;
    updateStatsUI()
}

function renderAnomalyFeedRow(alert, isNew) {
    const tableBody = document.getElementById("anomalyFeedTableBody");
    if (!tableBody) return;
    
    const riskClass = getRiskRowClass(alert.risk_score);
    const row = tableBody.insertRow(0);
    row.id = `alert-row-${alert.id}`;
    // row.className = 'fade-in log-anomaly log-row-clickable ${riskClass}';
    row.className = `${isNew ? 'fade-in' : ''} log-row-clickable ${riskClass}`;
    row.setAttribute('onclick', `if (event.target.tagName !== 'BUTTON') showLogContext('${alert.timestamp}', '${alert.content.replace(/'/g, "\\'")}')`);

    // const escapedContent = (data.log || '-').replace(/'/g, "\\'");
    // row.setAttribute('onclick', `showLogContext('${data.timestamp}', '${escapedContent}')`);
    // row.insertCell(0).textContent = new Date(data.timestamp).toLocaleString();
    // row.insertCell(1).textContent = data.verdict || 'N/A';
    // row.insertCell(2).textContent = data.log || '-';
    // row.insertCell(3).innerHTML = formatRiskScore(data.risk_score);

    // Cell for Status
    row.insertCell(0).innerHTML = `<span class="status-badge status-${alert.status.toLowerCase()}">${alert.status}</span>`;
    // Cell for Risk
    row.insertCell(1).innerHTML = formatRiskScore(alert.risk_score);
    // Cell for Content
    const contentCell = row.insertCell(2);
    contentCell.className = 'log-content';
    contentCell.textContent = alert.content;
    // Cell for Actions
    const actionsCell = row.insertCell(3);
    actionsCell.className = 'actions-cell';
    if (alert.status !== 'Closed') {
        actionsCell.innerHTML = `
            ${alert.status === 'New' ? `<button class="action-btn" onclick="updateAlertStatus(${alert.id}, 'Acknowledged')">Acknowledge</button>` : ''}
            <button class="action-btn" onclick="updateAlertStatus(${alert.id}, 'Closed')">Close</button>
        `;
    } else {
        actionsCell.innerHTML = '<span class="status-closed-text">Closed</span>';
    }

}

// function renderAlertRow(data, isNew) {
//     const container = document.getElementById("alertsContainer");
//     if (!container) return;
//     const div = document.createElement('div');
//     div.className = isNew ? 'alert-critical fade-in' : 'alert-critical';
//     div.innerHTML = `<strong>Critical:</strong> ${data.advice || "No advice."}<br><small>Ref Log: ${data.log || "N/A"}</small>`;
//     container.appendChild(div);
//     if (isNew) autoScroll(container);
// }

function renderAlertRow(data) {
    const container = document.getElementById("alertsContainer");
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'alert-critical fade-in';
    
    const statusHTML = data.status ? formatStatusBadge(data.status) : '';
    
    div.innerHTML = `
        <div class="alert-header">
            <strong>Critical Alert</strong>
            ${statusHTML}
        </div>
        ${data.advice || "No advice."}<br>
        <small>Ref Log: ${data.log || "N/A"}</small>
    `;
    container.prepend(div);
}

function updateStatsUI() {
    animateCount('totalLogs', totalCount);
    animateCount('normalCount', normalCount);
    animateCount('anomalyCount', anomalyCount);
    animateCount('sessionCount', sessionCount);
    document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
}

function autoScroll(containerId) {
    let container = document.getElementById(containerId);
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// setupEventListeners and handleQuickSearch remain the same as the last version
function setupEventListeners() {
    const applyBtn = document.getElementById('applyFiltersBtn');
    if (applyBtn) { applyBtn.addEventListener('click', filterLogs); }
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (darkModeToggle) { darkModeToggle.addEventListener('click', toggleDarkMode); }
    const searchBtn = document.getElementById('searchBtn');
    if (searchBtn) { searchBtn.addEventListener('click', searchLogs); }
    const quickSearchContainer = document.querySelector('.quick-searches');
    if (quickSearchContainer) { quickSearchContainer.addEventListener('click', handleQuickSearch); }
    const manualSearchInputs = document.querySelectorAll('.investigation-controls input, .investigation-controls select');
    manualSearchInputs.forEach(input => {
        input.addEventListener('input', () => {
            document.querySelectorAll('.quick-search-btn.active').forEach(btn => btn.classList.remove('active'));
            document.querySelector('.investigation-controls').classList.add('manual-search-active');
        });
    });
    setupReviewInterfaceListeners();

    document.getElementById('retrainBtn')?.addEventListener('click', handleRetrainClick);

    const modal = document.getElementById('log-context-modal');
    const closeBtn = document.getElementById('modal-close-btn');
    if (modal && closeBtn) {
        closeBtn.onclick = () => { modal.style.display = 'none'; };
        modal.onclick = (event) => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        };
    }
}

function handleQuickSearch(event) {
    const target = event.target;
    if (!target.classList.contains('quick-search-btn')) return;
    document.querySelectorAll('.quick-search-btn.active').forEach(btn => btn.classList.remove('active'));
    document.querySelector('.investigation-controls').classList.remove('manual-search-active');
    const keywordInput = document.getElementById('searchKeyword');
    const startTimeInput = document.getElementById('searchStartTime');
    const endTimeInput = document.getElementById('searchEndTime');
    const labelInput = document.getElementById('searchLabel');
    const sourceInput = document.getElementById('searchSource');
    keywordInput.value = '';
    startTimeInput.value = '';
    endTimeInput.value = '';
    labelInput.value = '';
    sourceInput.value = '';
    if (target.classList.contains('clear-btn')) {
        document.getElementById('searchResultsBody').innerHTML = '';
        return;
    }
    target.classList.add('active');
    const keyword = target.dataset.keyword;
    const label = target.dataset.label;
    const hours = target.dataset.hours;
    if (keyword) keywordInput.value = keyword;
    if (label) labelInput.value = label;
    if (hours) {
        const now = new Date();
        const startTime = new Date(now.getTime() - hours * 60 * 60 * 1000);
        const endTime = new Date(now.getTime() + 60 * 1000);
        const formatForInput = (date) => {
            const tzoffset = date.getTimezoneOffset() * 60000;
            const localISOTime = (new Date(date - tzoffset)).toISOString().slice(0, 16);
            return localISOTime;
        };
        startTimeInput.value = formatForInput(startTime);
        endTimeInput.value = formatForInput(now);
    }
    searchLogs();
}

// searchLogs remains the same
async function searchLogs() {
    const searchBtn = document.getElementById('searchBtn');
    const searchBtnText = searchBtn.querySelector('.search-text');
    const spinner = searchBtn.querySelector('.spinner');
    searchBtnText.style.display = 'none';
    spinner.style.display = 'block';
    searchBtn.disabled = true;
    const resultsBody = document.getElementById("searchResultsBody");
    resultsBody.innerHTML = '<tr><td colspan="4">Searching...</td></tr>';
    const searchCriteria = {
        keyword: document.getElementById('searchKeyword').value || null,
        start_time: document.getElementById('searchStartTime').value || null,
        end_time: document.getElementById('searchEndTime').value || null,
        label: document.getElementById('searchLabel').value ? parseInt(document.getElementById('searchLabel').value) : null,
        source: document.getElementById('searchSource').value || null,
    };
    try {
        const response = await fetch('/api/search_logs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(searchCriteria)
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const results = await response.json();
        resultsBody.innerHTML = '';
        if (results.length === 0) {
            resultsBody.innerHTML = '<tr><td colspan="4">No logs found matching your criteria.</td></tr>';
            return;
        }
        results.forEach(log => {
            let row = resultsBody.insertRow();
            const riskClass = getRiskRowClass(log.risk_score);

            row.className = 'log-row-clickable ${riskClass}';
            const escapedContent = log.content.replace(/'/g, "\\'");
            row.setAttribute('onclick', `showLogContext('${log.timestamp}', '${escapedContent}')`);
            let labelText = log.final_label === 1 ? 'anomaly' : 'normal';
            row.insertCell(0).textContent = new Date(log.timestamp).toLocaleString();
            row.insertCell(1).innerHTML = `<div class="status-badge-cell">${formatStatusBadge(log.status)}</div>`;
            // row.insertCell(1).innerHTML = `<div class="status-badge-cell">${formatStatusBadge(log.status)}</div>'; 
            row.insertCell(2).innerHTML = `<span class="label-${labelText}">${labelText}</span>`;
            row.insertCell(3).textContent = log.source;
            row.insertCell(4).textContent = log.content;
            row.insertCell(5).innerHTML = formatRiskScore(log.risk_score);
            
            if (log.final_label === 1 && !riskClass) {
                row.classList.add('risk-row-yellow');
            }
        });
    } catch (error) {
        console.error('Error fetching search results:', error);
        resultsBody.innerHTML = '<tr><td colspan="5">An error occurred while searching.</td></tr>';
    } finally {
        searchBtnText.style.display = 'inline';
        spinner.style.display = 'none';
        searchBtn.disabled = false;
    }
}

setInterval(() => {
    document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
}, 60000);

// PASTE THIS ENTIRE BLOCK AT THE END OF script.js

function setupReviewInterfaceListeners() {
    const reviewBtn = document.getElementById('reviewLogsBtn');
    if (reviewBtn) {
        reviewBtn.addEventListener('click', () => loadReviewInterface());
    }
}

async function loadReviewInterface(sortBy = '1') {
    const mainDashboard = document.querySelector('.dashboard-layout');
    const reviewContainer = document.getElementById('review-interface-container');
    
    if (!reviewContainer) return;

    mainDashboard.style.display = 'none';
    reviewContainer.style.display = 'block';
    reviewContainer.innerHTML = '<h2>Loading logs for review...</h2>';

    try {
        let url = '/api/review/pending';
        if (sortBy !== null) {
            url += `?sort_by=${sortBy}`;
        }
        const response = await fetch(url);
        const entries = await response.json();

        const sortButtonsHTML = `
            <div class="filter-buttons">
                <a href="javascript:void(0);" onclick="loadReviewInterface(null)" class="control-button ${sortBy === null ? 'active' : ''}">Show All</a>
                <a href="javascript:void(0);" onclick="loadReviewInterface('1')" class="control-button ${sortBy === '1' ? 'active' : ''}">Sort by Anomaly</a>
                <a href="javascript:void(0);" onclick="loadReviewInterface('0')" class="control-button ${sortBy === '0' ? 'active' : ''}">Sort by Normal</a>
            </div>
        `;

        let contentHTML;
        if (entries.length === 0) {
            contentHTML = `<p class="review-no-logs">No pending logs to review. Great job!</p>`;
        } else {
            let tableRows = '';
            entries.forEach(entry => {
                // The risk_score is now available in the 'entry' object from the API
                const riskClass = getRiskRowClass(entry.risk_score);
                tableRows += `
                    <tr class="${riskClass}" data-log-id="${entry.id}">
                        <td>${new Date(entry.timestamp).toLocaleString()}</td>
                        <td>${entry.source}</td>
                        <td><div class="status-badge-cell">${formatStatusBadge(entry.status)}</div></td>
                        <td class="log-content">${entry.content}</td>
                        <td>${formatRiskScore(entry.risk_score)}</td>
                        <td>
                          <div class="label-chooser" data-log-id="${entry.id}">
                            <input type="radio" id="normal_${entry.id}" name="label_${entry.id}" value="0" ${entry.final_label == 0 ? 'checked' : ''}>
                            <label for="normal_${entry.id}" class="label-normal">Normal</label>
                            <input type="radio" id="anomaly_${entry.id}" name="label_${entry.id}" value="1" ${entry.final_label == 1 ? 'checked' : ''}>
                            <label for="anomaly_${entry.id}" class="label-anomaly">Anomaly</label>
                          </div>
                        </td>
                    </tr>
                `;
            });
            contentHTML = `
                <table class="review-table">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Source</th>
                            <th>Status</th>
                            <th>Content</th>
                            <th>Risk Score</th>
                            <th>Correct Label?</th>
                        </tr>
                    </thead>
                    <tbody>${tableRows}</tbody>
                </table>
                <div class="review-actions"><button id="save-reviews-btn" class="submit-button">Save</button></div>
            `;
        }

        reviewContainer.innerHTML = `
            <div class="review-header">
                <h1>Log Review</h1>
                <button id="close-review-btn" class="control-button">Back to Dashboard</button>
            </div>
            ${sortButtonsHTML}
            ${contentHTML}
        `;

        document.getElementById('close-review-btn').addEventListener('click', closeReviewInterface);
        if (entries.length > 0) {
            document.getElementById('save-reviews-btn').addEventListener('click', saveReviews);
        }

    } catch (error) {
        reviewContainer.innerHTML = '<h2>Error loading logs. Please try again later.</h2>';
        console.error("Failed to load review logs:", error);
    }
}

function closeReviewInterface() {
    const mainDashboard = document.querySelector('.dashboard-layout');
    const reviewContainer = document.getElementById('review-interface-container');
    reviewContainer.style.display = 'none';
    mainDashboard.style.display = 'block'; // Or 'block', whatever its default is
}

async function saveReviews() {
    const choosers = document.querySelectorAll('.label-chooser');
    const updates = [];
    choosers.forEach(chooser => {
        const logId = chooser.dataset.logId;
        const selectedRadio = chooser.querySelector('input[type="radio"]:checked');
        if (selectedRadio) {
            updates.push({
                id: parseInt(logId),
                new_label: parseInt(selectedRadio.value)
            });
        }
    });

    if (updates.length === 0) {
        alert("No logs have been reviewed.");
        return;
    }

    const saveBtn = document.getElementById('save-reviews-btn');
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;

    try {
        const response = await fetch('/api/review/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        const result = await response.json();
        if (result.status === 'ok') {
            alert(`Successfully updated ${result.updated_count} logs!`);
            loadReviewInterface(); // Refresh the review list
        }
    } catch (error) {
        alert("Failed to save reviews.");
        console.error("Error saving reviews:", error);
    } finally {
        saveBtn.textContent = 'Save';
        saveBtn.disabled = false;
    }
}





// ===============================================================
// ===       NEW INTERACTIVE LOG CORRELATION (MODAL)           ===
// ===============================================================

/**
 * Shows the log context modal and fetches the relevant log data.
 * @param {string} timestamp - The ISO format timestamp of the log to center on.
 */
async function showLogContext(timestamp, originalLogContent) {
    const modal = document.getElementById('log-context-modal');
    const modalBody = document.getElementById('modal-body');
    if (!modal || !modalBody) return;

    modalBody.innerHTML = '<p>Loading context...</p>';
    modal.style.display = 'flex';

    try {
        const response = await fetch(`/api/logs/context?timestamp=${encodeURIComponent(timestamp)}`);
        const contextLogs = await response.json();
        
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
                fetch(`/api/logs/${targetLog.id}/explain`)
                    .then(res => res.json())
                    .then(data => {
                        const explanationContainer = document.getElementById(`explanation-for-${targetLog.id}`);
                        if (data.explanation_html) {
                            explanationContainer.innerHTML = `<h4>Model Explanation (LIME)</h4>${data.explanation_html}`;
                        } else {
                            explanationContainer.innerHTML = `<h4>Model Explanation (LIME)</h4><p class="explanation-error">Explanation not available for this log.</p>`;
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
                        <p class="log-content">${log.content}</p>
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

/**
 * Creates the HTML for the action cell, including the context icon.
 * @param {string} timestamp - The ISO timestamp for the log.
 * @param {string} logContent - The raw content of the log.
 */
// function createActionCell(timestamp, logContent) {
//     // We escape single quotes in the log content to prevent breaking the onclick attribute
//     const escapedContent = logContent.replace(/'/g, "\\'");
//     return `
//         <span class="context-icon" onclick="showLogContext('${timestamp}', '${escapedContent}')" title="Show Context">
//             <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
//         </span>
//     `;
// }

/**
 * Creates a styled HTML span for an alert's status.
 * @param {string} status - The status text (e.g., 'New', 'Acknowledged', 'Closed').
 */
function formatStatusBadge(status) {
    if (!status) {
        return ''; // Return an empty string if there's no status
    }
    const statusClass = status.toLowerCase();
    return `<span class="status-badge status-${statusClass}">${status}</span>`;
}

async function handleRetrainClick() {
    const retrainBtn = document.getElementById('retrainBtn');
    retrainBtn.disabled = true;

    try {
        const response = await fetch('/api/model/retrain', { method: 'POST' });
        const result = await response.json();

        // Use our new toast system to show progress
        showToast(result.message, 'info', 'retrain');

    } catch (error) {
        showToast('Error starting retraining.', 'error');
        console.error('Retraining request failed:', error);
    } finally {
        // Re-enable the button after a short delay to prevent spamming
        setTimeout(() => {
            retrainBtn.disabled = false;
        }, 3000);
    }
}

/**
 * Displays a toast notification with an optional progress bar.
 * @param {string} message - The message to display.
 * @param {string} type - 'success', 'error', or 'info'.
 * @param {string|null} taskId - An ID for a task to poll for progress.
 */
function showToast(message, type = 'info', taskId = null) {
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

/**
 * Periodically checks the status of a background task.
 * @param {string} taskId - The ID of the task to poll.
 */
function pollTaskStatus(taskId) {
    const intervalId = setInterval(async () => {
        try {
            const response = await fetch(`/api/model/retrain/status`);
            const data = await response.json();
            
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


/**
 * Formats the risk score with color-coding.
 * @param {number} score - The risk score from 0.0 to 1.0.
 */
function formatRiskScore(score) {
    const finalScore = score || 0;
    // The span no longer needs a class; the parent <tr>'s class will style it.
    return `<span>${finalScore.toFixed(2)}</span>`;
}

function getRiskRowClass(score) {
    if (score === undefined || score === null || score === 0) return '';
    if (score > 0.8) return 'risk-row-critical'; // Red background
    if (score >= 0.7) return 'risk-row-orange';  // Orange background
    // Any remaining anomaly will be yellow. The check for 'anomaly' is done in the calling function.
    return 'risk-row-yellow';   
}


async function loadInitialAnomalies() {
    const tableBody = document.getElementById('anomalyFeedTableBody');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="4" class="no-alerts-row">Loading alerts...</td></tr>';
    
    try {
        const response = await fetch('/api/alerts');
        const alerts = await response.json();
        
        tableBody.innerHTML = ''; // Clear loading message
        if (alerts.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" class="no-alerts-row">No open alerts. System is clear.</td></tr>';
            return;
        }
        alerts.forEach(alert => renderAnomalyFeedRow(alert, false)); 

    } catch (error) {
        console.error("Failed to load initial anomalies:", error);
        tableBody.innerHTML = '<tr><td colspan="4" class="no-alerts-row">Failed to load alerts.</td></tr>';
    }
}

async function updateAlertStatus(alertId, newStatus) {
    try {
        await fetch(`/api/alerts/${alertId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        // Visually update the row without a full refresh
        const row = document.getElementById(`alert-row-${alertId}`);
        if (newStatus === 'Closed') {
            row.style.opacity = '0.5';
            row.querySelector('.actions-cell').innerHTML = '<span class="status-closed-text">Closed</span>';
        } else if (newStatus === 'Acknowledged') {
            row.querySelector('.actions-cell').innerHTML = `<button class="action-btn" onclick="updateAlertStatus(${alertId}, 'Closed')">Close</button>`;
            row.querySelector('.status-badge').className = 'status-badge status-acknowledged';
            row.querySelector('.status-badge').textContent = 'Acknowledged';
        } else {
            loadInitialAnomalies(); // Refresh the list for other changes
        }
    } catch (error) {
        console.error("Failed to update alert status:", error);
    }
}

function handleStatusUpdate(data) {
    const { alert_id, log_id, new_status } = data;

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
            actionsCell.innerHTML = `<button class="action-btn" onclick="updateAlertStatus(${alert_id}, 'Closed')">Close</button>`;
        }
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