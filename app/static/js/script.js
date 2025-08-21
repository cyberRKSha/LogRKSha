let ws;
let historicalChart;
let normalCount = 0;
let anomalyCount = 0;
let totalCount = 0;
let sessionCount = 0;
let sessionCriticalAlerts = {};
let liveLogsCache = [];
let criticalAlertsCache = {};
let liveSparklineChart;
const sparklineData = {
    labels: Array(50).fill(''),
    normal: Array(50).fill(0),
    anomaly: Array(50).fill(0)
};

// === INITIALIZATION ===
window.onload = () => {
    initializeMonitoringStatus();
    restoreSessionStats();
    restoreCriticalAlerts();
    setupEventListeners();
    connectWebSocket();
    fetchTrainingStats();
    initHistoricalChart();
    loadInitialAnomalies();
    setupKeyboardShortcuts();
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
    if (!el) return;handleLabelToggleClick
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
            sessionCount = msg.count;
            updateStatsUI();
            break;
        case "log":
            liveLogsCache.unshift(msg.data); // Add to the beginning of the array
            // if (liveLogsCache.length > 500) { // Keep the cache at a max of 50 logs
            //     liveLogsCache.pop();
            // }
            renderLogRow(msg.data, true);
            updateLiveSparkline(msg.data.label); // <-- ADD THIS LINE
            if (msg.data.is_alert && msg.data.alert_info) {
                renderAnomalyFeedRow(msg.data.alert_info, true);
            }
            break;
        case "new_actionable_alert":
            // This handles adding new rows to our actionable anomaly feed
            if (msg.data) {
                renderAnomalyFeedRow(msg.data, true);
            }
            break;
        case "new_alert":
            criticalAlertsCache[msg.data.id] = msg.data; // Add or update the alert
            renderAlertRow(msg.data);
            sessionStorage.setItem('criticalAlerts', JSON.stringify(criticalAlertsCache)); // Save to session
            break;
        case "alert_update":
            if (criticalAlertsCache[msg.data.id]) {
                criticalAlertsCache[msg.data.id].count = msg.data.count;
            }
            handleAlertUpdate(msg.data);
            sessionStorage.setItem('criticalAlerts', JSON.stringify(criticalAlertsCache)); // Save to session
            break;
        case "alert_status_update":
            if (criticalAlertsCache[msg.data.alert_id]) {
                criticalAlertsCache[msg.data.alert_id].status = msg.data.new_status;
            }
            handleStatusUpdate(msg.data);
            sessionStorage.setItem('criticalAlerts', JSON.stringify(criticalAlertsCache)); // Save to session
            break;
        case "monitoring_status_update":
            // THE FIX: Call the correct function to update the button's visual state
            updateMonitoringStatusUI(msg.data.is_active);
            break;
    }
    // This call will now work correctly because of the fix in updateStatsUI.
    updateStatsUI();
}


function updateStatsUI() {
    animateCount('totalLogs', totalCount);
    animateCount('normalCount', normalCount);
    animateCount('anomalyCount', anomalyCount);
    animateCount('sessionCount', sessionCount);
    // animateCount('lastUpdated', new Date().toLocaleString());
    const now = new Date();
    const formattedTime = now.toLocaleString();
    const lastUpdatedEl = document.getElementById("lastUpdated");
    if (lastUpdatedEl) {
        lastUpdatedEl.textContent = formattedTime;
    }
    
    sessionStorage.setItem('sessionStats', JSON.stringify({
        total: totalCount,
        normal: normalCount,
        anomaly: anomalyCount
    }));
    sessionStorage.setItem('liveLogs', JSON.stringify(liveLogsCache));
}

function restoreSessionStats() {
    const stats = JSON.parse(sessionStorage.getItem('sessionStats'));
    if (stats) {
        totalCount = stats.total || 0;
        normalCount = stats.normal || 0;
        anomalyCount = stats.anomaly || 0;
    }

    // Restore the actual log entries
    const logs = JSON.parse(sessionStorage.getItem('liveLogs'));
    const tableBody = document.getElementById("logsTableBody");
    if (logs && tableBody) {
        liveLogsCache = logs;
        tableBody.innerHTML = ''; // Clear the table first
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
function renderLogRow(data, shouldUpdateState = true) {
    
    totalCount++;
    
    if (data.label === 'anomaly') {
        anomalyCount++;
        // row.classList.add('log-anomaly');
        // renderAnomalyFeedRow(data, true);
    } else {
        normalCount++;
    }
    const tableBody = document.getElementById("logsTableBody");
    if (!tableBody) return;
    
    if (tableBody) {
        const row = shouldUpdateState ? tableBody.insertRow(0) : tableBody.insertRow(-1);
        const labelText = (data.label || 'unknown').toLowerCase().trim();
        row.className = 'fade-in log-row-clickable';
        // row.setAttribute('data-log-id', data.id);
        const escapedContent = (data.log || '-').replace(/'/g, "\\'");
        row.setAttribute('onclick', `showLogContext('${data.timestamp}', '${escapedContent}')`);
        
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

    if (data.is_alert && data.alert_info) {
        // The data.alert_info object has everything renderAnomalyFeedRow needs
        renderAnomalyFeedRow(data.alert_info, true);
    }
    updateStatsUI()

}


function renderAnomalyFeedRow(alert, isNew) {
    const tableBody = document.getElementById("anomalyFeedTableBody");
    if (!tableBody) return;
    
    const noAlertsRow = tableBody.querySelector('.no-alerts-row');
    if (noAlertsRow) noAlertsRow.remove();

    const riskClass = getRiskRowClass(alert.risk_score);
    const row = tableBody.insertRow(0);
    row.id = `alert-row-${alert.id}`;
    // row.className = 'fade-in log-anomaly log-row-clickable ${riskClass}';
    row.className = `${isNew ? 'fade-in' : ''} log-row-clickable ${riskClass}`;
    row.setAttribute('onclick', `if (event.target.tagName !== 'BUTTON') showLogContext('${alert.timestamp}', '${alert.content.replace(/'/g, "\\'")}')`);

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

function renderAlertRow(data) {
    const container = document.getElementById("alertsContainer");
    if (!container) return;

    sessionCriticalAlerts[data.id] = data;

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

async function refreshCriticalAlerts() {
    const container = document.getElementById("alertsContainer");
    if (!container) return;

    try {
        const response = await fetch('/api/anomalies/all');
        const dbAlerts = await response.json();
        
        // Loop through the alerts currently displayed in the panel (our session cache)
        // for (const alertId in sessionCriticalAlerts) {
        //     const sessionAlert = sessionCriticalAlerts[alertId];
            
        //     // Find the corresponding alert from the database
        //     const dbAlert = dbAlerts.find(d => d.id == alertId);

        //     // If the alert is found in the DB, update its status
        //     if (dbAlert && sessionAlert.status !== dbAlert.status) {
        //         console.log(`Refreshing status for alert ${alertId} to ${dbAlert.status}`);
        //         handleStatusUpdate({ alert_id: alertId, new_status: dbAlert.status });
        //     } 
        //     // If the alert is NOT in the DB (meaning it's 'Closed'), we can optionally remove it
        //     else if (!dbAlert) {
        //         const alertDiv = document.getElementById(`critical-alert-${alertId}`);
        //         if (alertDiv) {
        //             alertDiv.style.opacity = '0.5'; // Fade it out instead of removing
        //             const statusCell = alertDiv.querySelector('.status-badge-cell');
        //             if(statusCell) statusCell.innerHTML = formatStatusBadge("Closed");
        //         }
        //     }
        //     else {
        //     // If no, display a helpful message in the panel
        //     container.innerHTML = '<div class="alert-info">No open critical alerts.</div>';
        //     }
        // }

        const container = document.getElementById("alertsContainer");
        if (!container) return;

        // 2. Clear only the visual panel and the specific cache for critical alerts.
        container.innerHTML = '';
        criticalAlertsCache = {};

        // 3. Check if the database returned any open alerts.
        if (dbAlerts && dbAlerts.length > 0) {
            // If yes, redraw the panel and rebuild the cache with the fresh data.
            dbAlerts.slice().reverse().forEach(alertData => {
                criticalAlertsCache[alertData.id] = alertData;
                renderAlertRow(alertData);
            });
        } else {
            // If no, display a helpful message in the now-empty panel.
            container.innerHTML = '<div class="alert-info">No open critical alerts.</div>';
        }

        // 4. IMPORTANT: Save the newly refreshed cache back to the browser's session.
        sessionStorage.setItem('criticalAlerts', JSON.stringify(criticalAlertsCache));

        showToast("Critical alerts panel refreshed.", "success");
    } catch (error) {
        console.error("Failed to refresh critical alerts:", error);
        showToast("Failed to refresh alerts.", "error");
    }
}



function restoreCriticalAlerts() {
    const alerts = JSON.parse(sessionStorage.getItem('criticalAlerts'));
    const container = document.getElementById("alertsContainer");
    if (alerts && container) {
        criticalAlertsCache = alerts;
        container.innerHTML = ''; // Clear container
        // Render each alert from the cache
        Object.values(alerts).forEach(alertData => renderAlertRow(alertData));
    }
}

function handleAlertUpdate(data) {
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

function handleStatusUpdate(data) {
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
            actionsCell.innerHTML = `<button class="action-btn" onclick="updateAlertStatus(${alert_id}, 'Closed')">Close</button>`;
        }
    }

    const criticalAlertDiv = document.getElementById(`critical-alert-${alert_id}`);
    if (criticalAlertDiv) {
        const statusCell = criticalAlertDiv.querySelector('.status-badge-cell');
        if (statusCell) {
            statusCell.innerHTML = formatStatusBadge(new_status);
        }
        // Also update the object in our session cache
        if (sessionCriticalAlerts[alert_id]) {
            sessionCriticalAlerts[alert_id].status = new_status;
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
    setupReviewPageListeners();

    document.getElementById('retrainBtn')?.addEventListener('click', handleRetrainClick);
    document.getElementById('refresh-alerts-btn')?.addEventListener('click', refreshCriticalAlerts);
    document.getElementById('monitoring-toggle-btn')?.addEventListener('click', handleMonitoringToggle);
    document.getElementById('clusterSortBy')?.addEventListener('change', fetchAndRenderClusters);
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

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (event) => {
            event.preventDefault(); // Stop the link's default behavior
            window.location.href = '/logout'; // Force the browser to navigate to the logout page
        });
    }

    document.getElementById('securityBtn')?.addEventListener('click', () => {
        window.location.href = '/security';
    });
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
            row.insertCell(6).innerHTML = formatSequenceRisk(log.sequence_risk);
            
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
        
        if (alerts.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" class="no-alerts-row">No open alerts. System is clear.</td></tr>';
            return;
        }

        const rowsHtml = alerts.map(alert => {
            const riskClass = getRiskRowClass(alert.risk_score);
            const escapedContent = alert.content.replace(/'/g, "\\'");

            // Determine actions based on status
            let actionsHtml = '<span class="status-closed-text">Closed</span>';
            if (alert.status !== 'Closed') {
                actionsHtml = `
                    ${alert.status === 'New' ? `<button class="action-btn" onclick="updateAlertStatus(${alert.id}, 'Acknowledged')">Acknowledge</button>` : ''}
                    <button class="action-btn" onclick="updateAlertStatus(${alert.id}, 'Closed')">Close</button>
                `;
            }

            return `
                <tr id="alert-row-${alert.id}" class="log-row-clickable ${riskClass}" onclick="if (event.target.tagName !== 'BUTTON') showLogContext('${alert.timestamp}', '${escapedContent}')">
                    <td><span class="status-badge status-${alert.status.toLowerCase()}">${alert.status}</span></td>
                    <td>${formatRiskScore(alert.risk_score)}</td>
                    <td class="log-content">${alert.content}</td>
                    <td class="actions-cell">${actionsHtml}</td>
                </tr>
            `;
        }).join('');

        tableBody.innerHTML = rowsHtml;
        // alerts.forEach(alert => renderAnomalyFeedRow(alert, false)); 

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






async function initializeMonitoringStatus() {
    try {
        const response = await fetch('/api/monitoring/status');
        const data = await response.json();
        updateMonitoringStatusUI(data.is_active);
    } catch (error) {
        console.error("Failed to get initial monitoring status:", error);
        updateMonitoringStatusUI(false);
    }
}

function updateMonitoringStatusUI(isActive) {
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

async function handleMonitoringToggle() {
    const button = document.getElementById('monitoring-toggle-btn');
    // Determine the new state by checking if the 'active' class is currently present
    const newStatus = !button.classList.contains('active');
    
    try {
        await fetch('/api/monitoring/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: newStatus })
        });
        updateMonitoringStatusUI(newStatus);
        // The UI will be updated via the WebSocket broadcast for consistency
    } catch (error) {
        console.error("Failed to toggle monitoring status:", error);
        // Optionally, revert the button state on failure
    }
}



function setupReviewPageListeners() {
    // Listener for the main button on the dashboard to open the page
    document.getElementById('openReviewPageBtn')?.addEventListener('click', openReviewInterface);
    
    // Listener for the back button inside the review page
    document.getElementById('close-review-btn')?.addEventListener('click', closeReviewInterface);

    // Add listeners for the tab buttons
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => switchReviewTab(button.dataset.tab));
    });
    
    // Listener for the Prepare/Refresh button
    document.getElementById('prepare-clusters-btn')?.addEventListener('click', prepareClusters);
}

function openReviewInterface() {
    document.querySelector('.dashboard-layout').style.display = 'none';
    document.getElementById('review-interface-container').style.display = 'block';
    // Automatically load the default tab's content
    fetchAndRenderClusters();
    fetchAndRenderNoiseLogs();
}

function closeReviewInterface() {
    document.getElementById('review-interface-container').style.display = 'none';
    document.querySelector('.dashboard-layout').style.display = 'block';
}

function switchReviewTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(content => { content.style.display = 'none'; });
    document.querySelectorAll('.tab-btn').forEach(button => { button.classList.remove('active'); });
    document.getElementById(tabId).style.display = 'block';
    document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add('active');

    if (tabId === 'smart-review') {
        fetchAndRenderClusters();
        fetchAndRenderNoiseLogs();
    } else if (tabId === 'manual-review') {
        loadManualReviewLogs();
    }
}

function loadManualReviewLogs() {
    const container = document.getElementById('manual-log-container');
    
    // Set up the event listener for the "Apply" button
    document.getElementById('applySortBtn').addEventListener('click', () => {
        const sortBy = document.getElementById('sortBySelect').value;
        const sortOrder = document.getElementById('sortOrderSelect').value;
        fetchAndRenderManualLogs(sortBy, sortOrder);
    });

    // Initial load with default sorting (newest first)
    fetchAndRenderManualLogs('timestamp', 'desc');
}

async function fetchAndRenderClusters() {
    const clusterContainer = document.getElementById('cluster-container');
    clusterContainer.innerHTML = '<h4>Loading clusters...</h4>';
    const sortBy = document.getElementById('clusterSortBy').value;
    const sortOrder = (sortBy === 'confidence') ? 'asc' : 'desc';

    try {
        const response = await fetch(`/api/review/clusters?sort_by=${sortBy}&sort_order=${sortOrder}`);
        const clusters = await response.json();
        if (clusters.length === 0) {
            clusterContainer.innerHTML = '<h4>No pending clusters to review. Click "Prepare" to process new logs.</h4>';
            return;
        }
        clusterContainer.innerHTML = '';
        clusters.forEach(cluster => {
            const card = document.createElement('div');
            card.className = 'cluster-card';
            card.id = `cluster-card-${cluster.cluster_id}`;
            card.setAttribute('tabindex', '0');
            card.innerHTML = `
                <div class="cluster-header">
                    <span class="cluster-title">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
                        <span>${cluster.name || 'Unnamed Cluster'}</span>
                    </span>
                    <span class="cluster-log-count">${cluster.log_count} Logs</span>
                </div>
                <div class="cluster-body" data-cluster-id="${cluster.cluster_id}">
                    <p><strong>Representative Log:</strong> (Click to see all ${cluster.log_count} logs)</p>
                    <div class="cluster-representative-log">${escapeHTML(cluster.representative_log)}</div>
                </div>
                <div class="cluster-meta">
                    <span>First Seen: ${new Date(cluster.first_seen).toLocaleString()}</span> | 
                    <span>Confidence: <strong>${(cluster.confidence * 100).toFixed(0)}%</strong></span>
                </div>
                <div class="cluster-actions">
                    <div class="label-toggle-switch" data-label="0"></div>
                    <button class="save-cluster-btn">Save</button>
                </div>
            `;
            clusterContainer.appendChild(card);
        });

        // Add event listeners for the new workflow
        document.querySelectorAll('#cluster-container .cluster-body').forEach(body => {
            body.addEventListener('click', () => openClusterDetailModal(body.dataset.clusterId));
        });
        document.querySelectorAll('.label-toggle-switch').forEach(button => {
            button.addEventListener('click', handleLabelToggleClick);
        });
        document.querySelectorAll('.save-cluster-btn').forEach(button => {
            button.addEventListener('click', handleSaveClusterClick);
        });

    } catch (error) {
        console.error("Failed to fetch clusters:", error);
        clusterContainer.innerHTML = '<h4>Error loading clusters. Please try again.</h4>';
    }
}

async function fetchAndRenderManualLogs(sortBy, sortOrder) {
    const container = document.getElementById('manual-log-table-container');
    container.innerHTML = '<h4>Loading logs...</h4>';

    try {
        const response = await fetch('/api/review/manual_logs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sort_by: sortBy, sort_order: sortOrder })
        });
        const entries = await response.json();

        if (entries.length === 0) {
            container.innerHTML = '<h4>No pending logs to review.</h4>';
            return;
        }

        let tableRows = '';
        entries.forEach(entry => {
            const riskClass = getRiskRowClass(entry.risk_score);
            tableRows += `
                <tr class="${riskClass}" data-log-id="${entry.id}">
                    <td>${new Date(entry.timestamp).toLocaleString()}</td>
                    <td>${entry.source}</td>
                    <td class="log-content">${escapeHTML(entry.content)}</td>
                    <td>${entry.risk_score.toFixed(2)}</td>
                    <td>${formatSequenceRisk(entry.sequence_risk)}</td>
                    <td>
                        <div class="label-chooser" data-log-id="${entry.id}">
                            <input type="radio" id="normal_${entry.id}" name="label_${entry.id}" value="0" ${entry.predicted_label == 0 ? 'checked' : ''}>
                            <label for="normal_${entry.id}" class="label-normal">Normal</label>
                            <input type="radio" id="anomaly_${entry.id}" name="label_${entry.id}" value="1" ${entry.predicted_label == 1 ? 'checked' : ''}>
                            <label for="anomaly_${entry.id}" class="label-anomaly">Anomaly</label>
                        </div>
                    </td>
                </tr>
            `;
        });

        container.innerHTML = `
            <table class="review-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Source</th>
                        <th>Content</th>
                        <th>Risk Score</th>
                        <th>Sequence Risk</th>
                        <th>Label?</th>
                    </tr>
                </thead>
                <tbody>${tableRows}</tbody>
            </table>
            <div class="review-actions">
                <button id="save-reviews-btn" class="submit-button">Save</button>
            </div>
        `;
        
        // Add event listener to the new "Save" button
        document.getElementById('save-reviews-btn').addEventListener('click', (event) => {
            // It calls the SAME saveReviews function, but with the manual review selector
            saveReviews('#manual-review .label-chooser', event.target);
        });

    } catch (error) {
        console.error("Failed to fetch manual logs:", error);
        container.innerHTML = '<h4>Error loading logs. Please try again.</h4>';
    }
}

async function fetchAndRenderNoiseLogs() {
    const noiseContainer = document.getElementById('noise-container');
    noiseContainer.innerHTML = '<h4>Loading unclustered logs...</h4>';
    try {
        const response = await fetch('/api/review/noise');
        const noiseLogs = await response.json();

        noiseContainer.innerHTML = ''; // Clear loading message
        if (noiseLogs.length === 0) {
            noiseContainer.innerHTML = '<p>No unclustered logs to review.</p>';
            return;
        }

        noiseLogs.forEach(log => {
            const card = document.createElement('div');
            const modelPredictionClass = log.predicted_label === 1 ? 'model-anomaly' : 'model-normal';
            card.className = `cluster-card ${modelPredictionClass}`;
            card.id = `cluster-card-${log.cluster_id}`;

            const isAnomaly = log.predicted_label === 1;
            card.innerHTML = `
                <div class="cluster-header">
                    <span class="cluster-title">${log.name}</span>
                    <span class="cluster-log-count">1 Log</span>
                </div>
                <div class="cluster-representative-log">${escapeHTML(log.representative_log)}</div>
                <div class="cluster-actions">
                    <div class="label-toggle-switch ${isAnomaly ? 'is-anomaly' : ''}" data-label="${isAnomaly ? 1 : 0}"></div>
                    <button class="save-cluster-btn">Save</button>
                </div>
            `;
            noiseContainer.appendChild(card);
        });
        // Re-use the same event listeners from the main cluster cards
        document.querySelectorAll('#noise-container .label-toggle-switch').forEach(button => {
            button.addEventListener('click', handleLabelToggleClick);
        });
        document.querySelectorAll('#noise-container .save-cluster-btn').forEach(button => {
            button.addEventListener('click', handleSaveClusterClick);
        });

    } catch (error) {
        console.error("Failed to fetch noise logs:", error);
        noiseContainer.innerHTML = '<h4>Error loading unclustered logs.</h4>';
    }
}

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ensure we are on the review page and not in an input field
        const reviewContainerVisible = document.getElementById('review-interface-container').style.display === 'block';
        if (!reviewContainerVisible || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
            return;
        }

        const focusedCard = document.activeElement;
        if (!focusedCard.classList.contains('cluster-card')) return;

        switch(e.key.toLowerCase()) {
            case 'n': // Mark as Normal
                focusedCard.querySelector('.mark-normal-btn').click();
                break;
            case 'a': // Mark as Anomaly
                focusedCard.querySelector('.mark-anomaly-btn').click();
                break;
            case 's': // Save
            case 'enter':
                e.preventDefault(); // Prevent default Enter behavior
                const saveBtn = focusedCard.querySelector('.save-cluster-btn');
                if (saveBtn && saveBtn.style.display !== 'none') {
                    saveBtn.click();
                }
                break;
            case 'arrowdown':
                e.preventDefault();
                const nextCard = focusedCard.nextElementSibling;
                if (nextCard) nextCard.focus();
                break;
            case 'arrowup':
                e.preventDefault();
                const prevCard = focusedCard.previousElementSibling;
                if (prevCard) prevCard.focus();
                break;
        }
    });
}

async function prepareClusters() {
    const btn = document.getElementById('prepare-clusters-btn');
    const originalText = btn.textContent;
    
    // --- ADD THIS ---
    btn.innerHTML = `<div class="spinner" style="width: 18px; height: 18px; border-width: 2px;"></div> Preparing...`;
    btn.disabled = true;

    showToast('Starting log clustering process in the background...', 'info');
    try {
        const response = await fetch('/api/review/prepare', { method: 'POST' });
        const result = await response.json();
        showToast(result.message, 'success');
        setTimeout(() => {fetchAndRenderClusters(); fetchAndRenderNoiseLogs();}, 2000); // Refresh view after a delay
    } catch (error) {
        showToast('Failed to start clustering process.', 'error');
    } finally {
        // --- ADD THIS ---
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

function handleLabelToggleClick(event) {
    const toggle = event.target;
    const card = toggle.closest('.cluster-card');
    toggle.classList.toggle('is-anomaly');

    const newLabel = toggle.classList.contains('is-anomaly') ? '1' : '0';

    card.dataset.selectedLabel = newLabel;

    toggle.classList.add('active');
}

async function handleSaveClusterClick(event) {
    const button = event.target;
    const card = button.closest('.cluster-card');
    const clusterId = card.id.replace('cluster-card-', '');
    let newLabel = card.dataset.selectedLabel;

    if (newLabel === undefined) {
        const toggle = card.querySelector('.label-toggle-switch');
        if (toggle && toggle.dataset.label) {
            newLabel = toggle.dataset.label;
        } else {
            // If we still can't find a label, show an error.
            showToast('Could not determine label.', 'error');
            return;
        }
    }

    button.textContent = 'Saving...';
    button.disabled = true;

    try {
        // This is the same API call as before
        const response = await fetch(`/api/review/clusters/${clusterId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_label: parseInt(newLabel) })
        });
        const result = await response.json();
        if (result.status === 'ok') {
            showToast(`Cluster ${clusterId} labeled successfully (${result.updated_count} logs).`, 'success');
            card.remove();
        } else { throw new Error(result.message); }
    } catch (error) {
        showToast(`Failed to label cluster ${clusterId}.`, 'error');
        button.textContent = 'Save';
        button.disabled = false;
    }
}

async function saveReviews(selector, saveButtonElement) {
    const choosers = document.querySelectorAll(selector);
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
        showToast("No changes to save.", "info");
        return;
    }

    if (saveButtonElement) {
        saveButtonElement.textContent = 'Saving...';
        saveButtonElement.disabled = true;
    }

    try {
        const response = await fetch('/api/review/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        const result = await response.json();
        if (result.status === 'ok') {
            showToast(`Successfully updated ${result.updated_count} logs!`, 'success');
            
            showToast('Refreshing clusters with remaining logs...', 'info');
            await prepareClusters();
            // Refresh the manual review table to show remaining logs
            loadManualReviewLogs();
        } else {
            throw new Error(result.message || "Unknown error saving reviews.");
        }
    } catch (error) {
        showToast("Failed to save reviews.", "error");
        if (saveButtonElement) {
            saveButtonElement.textContent = 'Save Changes';
            saveButtonElement.disabled = false;
        }
    } finally {
        // The button will disappear on successful refresh, so no need to re-enable
    }
}

// Helper to prevent HTML injection from log content
function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}


async function openClusterDetailModal(clusterId) {
    const modal = document.getElementById('cluster-detail-modal');
    const title = document.getElementById('cluster-modal-title');
    const body = document.getElementById('cluster-modal-body');
    const closeBtn = document.getElementById('cluster-modal-close-btn');

    title.textContent = `Logs for ${clusterId}`;
    body.innerHTML = '<h4>Loading logs...</h4>';
    modal.style.display = 'flex';
    
    closeBtn.onclick = () => { modal.style.display = 'none'; };
    
    const response = await fetch(`/api/review/clusters/${clusterId}/logs`);
    const logs = await response.json();

    let tableRows = '';
    logs.forEach(log => {
        tableRows += `
            <tr>
                <td class="log-content">${escapeHTML(log.content)}</td>
                <td>${log.risk_score.toFixed(2)}</td>
                <td>${formatSequenceRisk(log.sequence_risk)}</td>
                <td>
                    <div class="label-chooser" data-log-id="${log.id}">
                        <input type="radio" id="modal_normal_${log.id}" name="modal_label_${log.id}" value="0" ${log.predicted_label == 0 ? 'checked' : ''}>
                        <label for="modal_normal_${log.id}" class="label-normal">Normal</label>
                        <input type="radio" id="modal_anomaly_${log.id}" name="modal_label_${log.id}" value="1" ${log.predicted_label == 1 ? 'checked' : ''}>
                        <label for="modal_anomaly_${log.id}" class="label-anomaly">Anomaly</label>
                    </div>
                </td>
            </tr>
        `;
    });

    body.innerHTML = `
        <table class="review-table">
            <thead><tr><th>Content</th><th>Risk</th><th>Sequence Risk</th><th>Label</th></tr></thead>
            <tbody>${tableRows}</tbody>
        </table>
        <div class="review-actions">
            <button id="save-modal-reviews-btn" class="submit-button">Save</button>
        </div>
    `;

    document.getElementById('save-modal-reviews-btn').addEventListener('click', saveModalReviews);
}

async function saveModalReviews() {
    // This can reuse the logic from your existing manual review save function!
    // const choosers = document.querySelectorAll('#cluster-detail-modal .label-chooser');
    // ... the rest is the same as the saveReviews function
    // We can reuse that function by passing the selector
    const saveButton = document.getElementById('save-modal-reviews-btn');
    await saveReviews('#cluster-detail-modal .label-chooser', saveButton);
    document.getElementById('cluster-detail-modal').style.display = 'none';
    // Refresh the cluster view as counts might have changed (or cluster removed)
    fetchAndRenderClusters();
    fetchAndRenderNoiseLogs();
}


function formatSequenceRisk(score) {
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


function initLiveSparkline() {
    const ctx = document.getElementById('liveSparklineChart').getContext('2d');
    liveSparklineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sparklineData.labels,
            datasets: [
                { label: 'Normal', data: sparklineData.normal, borderColor: 'rgba(117, 183, 152, 0.8)', tension: 0.4, borderWidth: 2 },
                { label: 'Anomaly', data: sparklineData.anomaly, borderColor: 'rgba(255, 138, 138, 0.8)', tension: 0.4, borderWidth: 2 }
            ]
        },
        options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } }
    });
}

// ADD this new function to update the chart in real-time
function updateLiveSparkline(label) {
    // Shift data to the left
    sparklineData.normal.shift();
    sparklineData.anomaly.shift();

    // Add new data point
    sparklineData.normal.push(label === 'normal' ? 1 : 0);
    sparklineData.anomaly.push(label === 'anomaly' ? 1 : 0);
    
    // Update chart
    if(liveSparklineChart) liveSparklineChart.update();
}

// ADD this new function for the command palette
function setupCommandPalette() {
    const overlay = document.getElementById('command-palette-overlay');
    const input = document.getElementById('command-palette-input');
    const resultsContainer = document.getElementById('command-palette-results');
    
    const commands = [
        { name: 'Toggle Dark Mode', action: toggleDarkMode },
        { name: 'Open Review Page', action: openReviewInterface },
        { name: 'Refresh Critical Alerts', action: refreshCriticalAlerts }
    ];

    const showPalette = () => { overlay.style.display = 'flex'; input.focus(); };
    const hidePalette = () => { overlay.style.display = 'none'; input.value = ''; renderResults([]); };

    const renderResults = (results) => {
        resultsContainer.innerHTML = '';
        results.forEach(cmd => {
            const item = document.createElement('a');
            item.className = 'command-item';
            item.textContent = cmd.name;
            item.onclick = () => { cmd.action(); hidePalette(); };
            resultsContainer.appendChild(item);
        });
    };
    
    input.onkeyup = () => {
        const query = input.value.toLowerCase();
        const filtered = commands.filter(cmd => cmd.name.toLowerCase().includes(query));
        renderResults(filtered);
    };

    document.addEventListener('keydown', (e) => { if (e.key === 'k' && e.ctrlKey) { e.preventDefault(); showPalette(); } });
    document.getElementById('command-palette-btn').onclick = showPalette;
    overlay.onclick = (e) => { if (e.target === overlay) hidePalette(); };
}