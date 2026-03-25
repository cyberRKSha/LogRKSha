import { animateCount, escapeHTML, formatRiskScore, getRiskRowClass, formatSequenceRisk, formatStatusBadge, showToast } from './utils.js';
import { initHistoricalChart, createTopNChart, updateAllChartColors, initLiveSparkline, updateLiveSparkline, createDetectionMethodChart, updateTopNChart, updateDetectionMethodChart } from './charts.js';
import * as api from './api.js';
import { initThreatMap } from './map.js';
import { connectWebSocket } from './websocket.js';
import { autoScroll, handleStatusUpdate, handleAlertUpdate, renderAlertRow, updateStatsOnScreen, renderRestoredLogs, renderLogRow, showLogContext, renderAnomalyFeedRow, updateAlertStatus, updateMonitoringStatusUI, renderRestoredAnomalies, renderSigmaMatchRow } from './ui.js';
// import { setupReviewListeners, setupKeyboardShortcuts } from './review.js';
import { applyTheme, toggleDarkMode } from './theme.js';

// --- GLOBAL STATE for the dashboard ---
let totalCount = 0;
let normalCount = 0;
let anomalyCount = 0;
let sessionCount = 0;
let liveLogsCache = [];
let anomalyFeedCache = [];
let criticalAlertsCache = {};

window.onload = () => {
    applyTheme();
    initializeMonitoringStatus();
    restoreSessionStats();
    restoreCriticalAlerts();
    setupEventListeners();
    connectWebSocket(handleWebSocketMessage);
    fetchTrainingStats();
    initHistoricalChart();
    loadInitialAnomalies();
    // setupKeyboardShortcuts();
    initLiveSparkline();

    createTopNChart('topVerdictsChart', 'verdict', 'Top Verdicts');
    createTopNChart('topAnomalousIpsChart', 'ip', 'Top IPs');
    createTopNChart('topSourcesChart', 'source', 'Top Sources');

    createDetectionMethodChart();
    setInterval(refreshAllWidgets, 30000);
    initThreatMap();

    // Phase 5: SOC Features
    loadCases();
    loadMitreHeatmap();
};

function setupEventListeners() {
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', () => {
            toggleDarkMode();
            updateAllChartColors();
        });
    }

    // --- Search & Filter Listeners ---
    document.getElementById('searchBtn')?.addEventListener('click', searchLogs);
    document.getElementById('clearFiltersBtn')?.addEventListener('click', clearSearchFilters);
    document.getElementById('exportCsvBtn')?.addEventListener('click', exportSearchResultsToCsv);
    document.getElementById('exportPdfBtn')?.addEventListener('click', handlePdfExport);
    const quickSearchContainer = document.querySelector('.quick-searches');
    if (quickSearchContainer) { quickSearchContainer.addEventListener('click', handleQuickSearch); }

    const manualSearchInputs = document.querySelectorAll('.investigation-controls input, .investigation-controls select');
    manualSearchInputs.forEach(input => {
        input.addEventListener('input', () => {
            document.querySelectorAll('.quick-search-btn.active').forEach(btn => btn.classList.remove('active'));
            document.querySelector('.investigation-controls').classList.add('manual-search-active');
        });
    });

    // Live refresh every 30 seconds
    setInterval(() => {
        loadDashboardStats();
        loadRecentLogs();
        loadAlerts();
        loadCases(); // Refresh cases list
        loadMitreHeatmap(); // Refresh heatmap
    }, 30000);

    document.getElementById('openPlaybooksBtn')?.addEventListener('click', () => {
        window.location.href = '/playbooks';
    });

    document.getElementById('openReviewPageBtn')?.addEventListener('click', () => {
        window.location.href = '/review';
    });
    document.getElementById('retrainBtn')?.addEventListener('click', handleRetrainClick);
    document.getElementById('refresh-alerts-btn')?.addEventListener('click', refreshCriticalAlerts);
    document.getElementById('monitoring-toggle-btn')?.addEventListener('click', handleMonitoringToggle);
    // document.getElementById('clusterSortBy')?.addEventListener('change', fetchAndRenderClusters);

    const modal = document.getElementById('log-context-modal');
    const closeBtn = document.getElementById('modal-close-btn');
    if (modal && closeBtn) {
        closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
        modal.addEventListener('click', (event) => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    // Modal Tab Switching
    document.querySelectorAll('.modal-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.modal-tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const tabId = tab.getAttribute('data-tab');
            document.getElementById(`tab-${tabId}`)?.classList.add('active');
        });
    });

    // Alert Side Panel Controls
    const sidePanel = document.getElementById('alert-side-panel');
    const sidePanelClose = document.getElementById('side-panel-close');
    const sidePanelOverlay = document.getElementById('side-panel-overlay');

    if (sidePanelClose) {
        sidePanelClose.addEventListener('click', () => {
            sidePanel?.classList.remove('open');
            if (sidePanelOverlay) sidePanelOverlay.style.display = 'none';
        });
    }
    if (sidePanelOverlay) {
        sidePanelOverlay.addEventListener('click', () => {
            sidePanel?.classList.remove('open');
            sidePanelOverlay.style.display = 'none';
        });
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

    // setupReviewListeners();
}

function handleWebSocketMessage(event) {
    // console.log("RAW WEBSOCKET MESSAGE RECEIVED:", event.data);
    const msg = JSON.parse(event.data);
    switch (msg.type) {
        case "session_update":
            sessionCount = msg.count;
            updateStatsOnScreen(totalCount, normalCount, anomalyCount, sessionCount);
            saveSessionState();
            break;
        case "log":
            liveLogsCache.unshift(msg.data);
            totalCount++;
            if (msg.data.label === 'anomaly') {
                anomalyCount++;
                if (msg.data.is_alert && msg.data.alert_info) {
                    anomalyFeedCache.unshift(msg.data.alert_info);
                    renderAnomalyFeedRow(msg.data.alert_info, true);
                }
            } else {
                normalCount++;
            }
            renderLogRow(msg.data, true);
            updateLiveSparkline(msg.data.label); // <-- ADD THIS LINE
            updateStatsOnScreen(totalCount, normalCount, anomalyCount, sessionCount);
            // saveSessionState();
            if (msg.data.play_sound) {
                const audio = new Audio('/static/audio/alert.wav');
                audio.play().catch(error => {
                    console.warn("Could not play alert sound, possibly due to browser restrictions.", error);
                });
            }
            break;
        // case "new_actionable_alert":
        //     // This handles adding new rows to our actionable anomaly feed
        //     if (msg.data) {
        //         anomalyFeedCache.unshift(msg.data);
        //         renderAnomalyFeedRow(msg.data, true);
        //     }
        //     break;
        case "new_alert":
            criticalAlertsCache[msg.data.id] = msg.data; // Add or update the alert
            sessionStorage.setItem('criticalAlerts', JSON.stringify(criticalAlertsCache)); // Save to session
            renderAlertRow(msg.data);
            break;
        case "alert_update":
            if (criticalAlertsCache[msg.data.id]) {
                criticalAlertsCache[msg.data.id].count = msg.data.count;
                sessionStorage.setItem('criticalAlerts', JSON.stringify(criticalAlertsCache)); // Save to session
            }
            handleAlertUpdate(msg.data);
            break;
        case "alert_status_update":
            if (criticalAlertsCache[msg.data.alert_id]) {
                criticalAlertsCache[msg.data.alert_id].status = msg.data.new_status;
                sessionStorage.setItem('criticalAlerts', JSON.stringify(criticalAlertsCache)); // Save to session
            }
            handleStatusUpdate(msg.data);
            break;
        case "monitoring_status_update":
            // THE FIX: Call the correct function to update the button's visual state
            updateMonitoringStatusUI(msg.data.is_active);
            break;
        case "sigma_match":
            renderSigmaMatchRow(msg.data);
            break;
    }
    // This call will now work correctly because of the fix in updateStatsUI.
    updateStatsOnScreen(totalCount, normalCount, anomalyCount, sessionCount);
    saveSessionState();
}

async function handleRetrainClick() {
    const retrainBtn = document.getElementById('retrainBtn');
    retrainBtn.disabled = true;

    try {
        const result = await api.postRetrainModel();

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

async function handleMonitoringToggle() {
    const button = document.getElementById('monitoring-toggle-btn');
    // Determine the new state by checking if the 'active' class is currently present
    const newStatus = !button.classList.contains('active');

    try {
        await api.postMonitoringToggle(newStatus);
        updateMonitoringStatusUI(newStatus);
        // The UI will be updated via the WebSocket broadcast for consistency
    } catch (error) {
        console.error("Failed to toggle monitoring status:", error);
        // Optionally, revert the button state on failure
    }
}

// function handleQuickSearch(event) {
//     const target = event.target;
//     if (!target.classList.contains('quick-search-btn')) return;
//     document.querySelectorAll('.quick-search-btn.active').forEach(btn => btn.classList.remove('active'));
//     document.querySelector('.investigation-controls').classList.remove('manual-search-active');
//     const keywordInput = document.getElementById('searchKeyword');
//     const startTimeInput = document.getElementById('searchStartTime');
//     const endTimeInput = document.getElementById('searchEndTime');
//     const labelInput = document.getElementById('searchLabel');
//     const sourceInput = document.getElementById('searchSource');
//     keywordInput.value = '';
//     startTimeInput.value = '';
//     endTimeInput.value = '';
//     labelInput.value = '';
//     sourceInput.value = '';
//     if (target.classList.contains('clear-btn')) {
//         document.getElementById('searchResultsBody').innerHTML = '';
//         return;
//     }
//     target.classList.add('active');
//     const keyword = target.dataset.keyword;
//     const label = target.dataset.label;
//     const hours = target.dataset.hours;
//     if (keyword) keywordInput.value = keyword;
//     if (label) labelInput.value = label;
//     if (hours) {
//         const now = new Date();
//         const startTime = new Date(now.getTime() - hours * 60 * 60 * 1000);
//         const endTime = new Date(now.getTime() + 60 * 1000);
//         const formatForInput = (date) => {
//             const tzoffset = date.getTimezoneOffset() * 60000;
//             const localISOTime = (new Date(date - tzoffset)).toISOString().slice(0, 16);
//             return localISOTime;
//         };
//         startTimeInput.value = formatForInput(startTime);
//         endTimeInput.value = formatForInput(now);
//     }
//     searchLogs();
// }

// // searchLogs remains the same
// async function searchLogs() {
//     const searchBtn = document.getElementById('searchBtn');
//     const searchBtnText = searchBtn.querySelector('.search-text');
//     const spinner = searchBtn.querySelector('.spinner');
//     searchBtnText.style.display = 'none';
//     spinner.style.display = 'block';
//     searchBtn.disabled = true;
//     const resultsBody = document.getElementById("searchResultsBody");
//     resultsBody.innerHTML = '<tr><td colspan="4">Searching...</td></tr>';
//     const searchCriteria = {
//         keyword: document.getElementById('searchKeyword').value || null,
//         start_time: document.getElementById('searchStartTime').value || null,
//         end_time: document.getElementById('searchEndTime').value || null,
//         label: document.getElementById('searchLabel').value ? parseInt(document.getElementById('searchLabel').value) : null,
//         source: document.getElementById('searchSource').value || null,
//     };
//     try {
//         const results = await api.searchLogs(searchCriteria);
//         resultsBody.innerHTML = '';
//         if (results.length === 0) {
//             resultsBody.innerHTML = '<tr><td colspan="4">No logs found matching your criteria.</td></tr>';
//             return;
//         }
//         results.forEach(log => {
//             let row = resultsBody.insertRow();
//             const riskClass = getRiskRowClass(log.risk_score);

//             row.className = 'log-row-clickable ${riskClass}';
//             row.addEventListener('click', () => {
//                 showLogContext(log.timestamp, log.content);
//             });
//             let labelText = log.final_label === 1 ? 'anomaly' : 'normal';
//             row.insertCell(0).textContent = new Date(log.timestamp).toLocaleString();
//             row.insertCell(1).innerHTML = `<div class="status-badge-cell">${formatStatusBadge(log.status)}</div>`;
//             // row.insertCell(1).innerHTML = `<div class="status-badge-cell">${formatStatusBadge(log.status)}</div>'; 
//             row.insertCell(2).innerHTML = `<span class="label-${labelText}">${labelText}</span>`;
//             row.insertCell(3).textContent = log.source;
//             row.insertCell(4).textContent = log.content;
//             row.insertCell(5).innerHTML = formatRiskScore(log.risk_score);
//             row.insertCell(6).innerHTML = formatSequenceRisk(log.sequence_risk);

//             if (log.final_label === 1 && !riskClass) {
//                 row.classList.add('risk-row-yellow');
//             }
//         });
//     } catch (error) {
//         console.error('Error fetching search results:', error);
//         resultsBody.innerHTML = '<tr><td colspan="5">An error occurred while searching.</td></tr>';
//     } finally {
//         searchBtnText.style.display = 'inline';
//         spinner.style.display = 'none';
//         searchBtn.disabled = false;
//     }
// }

async function searchLogs() {
    const searchBtn = document.getElementById('searchBtn');
    const searchBtnText = searchBtn.querySelector('.search-text');
    const spinner = searchBtn.querySelector('.spinner');
    searchBtnText.style.display = 'none';
    spinner.style.display = 'block';
    searchBtn.disabled = true;

    const resultsBody = document.getElementById("searchResultsBody");
    resultsBody.innerHTML = '<tr><td colspan="7">Searching...</td></tr>'; // Changed colspan to 7

    // 1. Gather all values from the new form
    const searchCriteria = {
        keyword: document.getElementById('searchKeyword').value || null,
        ip_address: document.getElementById('searchIpAddress').value || null,
        source: document.getElementById('searchSource').value || null,
        detection_method: document.getElementById('searchDetectionMethod').value || null,
        risk_score_min: parseFloat(document.getElementById('searchRiskScore').value) || null,
        start_time: document.getElementById('searchStartTime').value || null,
        end_time: document.getElementById('searchEndTime').value || null,
        filter_logic: document.querySelector('input[name="filter_logic"]:checked').value
    };

    // Remove null fields so we don't send empty values
    Object.keys(searchCriteria).forEach(key => {
        if (searchCriteria[key] === null || searchCriteria[key] === '') {
            delete searchCriteria[key];
        }
    });

    try {
        // 2. Send the complete searchCriteria object to the API
        const results = await api.searchLogs(searchCriteria);

        resultsBody.innerHTML = ''; // Clear "Searching..." message
        if (results.length === 0) {
            resultsBody.innerHTML = '<tr><td colspan="7">No logs found matching your criteria.</td></tr>';
            return;
        }

        // 3. Render the results (same logic as before, but now with 7 columns)
        results.forEach(log => {
            let row = resultsBody.insertRow();
            row.className = `log-row-clickable ${getRiskRowClass(log.risk_score)}`;
            row.addEventListener('click', () => {
                showLogContext(log.timestamp, log.content, log.id);
            });
            let labelText = log.final_label === 1 ? 'anomaly' : 'normal';
            row.insertCell(0).textContent = new Date(log.timestamp).toLocaleString();
            row.insertCell(1).innerHTML = `<div class="status-badge-cell">${formatStatusBadge(log.status)}</div>`;
            row.insertCell(2).innerHTML = `<span class="label-${labelText}">${labelText}</span>`;
            row.insertCell(3).textContent = log.source;
            row.insertCell(4).textContent = log.content;
            row.insertCell(5).innerHTML = formatRiskScore(log.risk_score);
            row.insertCell(6).innerHTML = formatSequenceRisk(log.sequence_risk);
        });

    } catch (error) {
        console.error('Error fetching search results:', error);
        resultsBody.innerHTML = '<tr><td colspan="7">An error occurred while searching.</td></tr>';
    } finally {
        searchBtnText.style.display = 'inline';
        spinner.style.display = 'none';
        searchBtn.disabled = false;
    }
}

function clearSearchFilters() {
    document.getElementById('searchKeyword').value = '';
    document.getElementById('searchIpAddress').value = '';
    document.getElementById('searchSource').value = '';
    document.getElementById('searchDetectionMethod').value = '';
    document.getElementById('searchRiskScore').value = '';
    document.getElementById('searchStartTime').value = '';
    document.getElementById('searchEndTime').value = '';
    document.querySelector('input[name="filter_logic"][value="and"]').checked = true;

    document.getElementById("searchResultsBody").innerHTML = '';
}

function exportSearchResultsToCsv() {
    const table = document.getElementById("searchResultsTable");
    let csv = [];
    // Header Row
    const headers = Array.from(table.querySelectorAll("thead th")).map(th => th.textContent);
    csv.push(headers.join(','));

    // Data Rows
    const rows = table.querySelectorAll("tbody tr");
    rows.forEach(row => {
        // Ensure it's a data row, not a "No results" message
        if (row.cells.length === headers.length) {
            const rowData = Array.from(row.cells).map(cell => `"${cell.textContent.replace(/"/g, '""')}"`);
            csv.push(rowData.join(','));
        }
    });

    if (csv.length <= 1) {
        showToast("No data to export.", "info");
        return;
    }

    const csvContent = "data:text/csv;charset=utf-8," + csv.join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "log_search_results.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast("Search results exported.", "success");
}

setInterval(() => {
    document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
}, 60000);

function saveSessionState() {
    sessionStorage.setItem('sessionStats', JSON.stringify({
        total: totalCount,
        normal: normalCount,
        anomaly: anomalyCount,
    }));
    sessionStorage.setItem('liveLogs', JSON.stringify(liveLogsCache));
    sessionStorage.setItem('anomalyFeed', JSON.stringify(anomalyFeedCache));
}

function restoreSessionStats() {
    // Part 1: Read data and set state
    const stats = JSON.parse(sessionStorage.getItem('sessionStats'));
    if (stats) {
        totalCount = stats.total || 0;
        normalCount = stats.normal || 0;
        anomalyCount = stats.anomaly || 0;
    }

    const logs = JSON.parse(sessionStorage.getItem('liveLogs'));
    if (logs) {
        liveLogsCache = logs;
    }

    const anomalies = JSON.parse(sessionStorage.getItem('anomalyFeed'));
    if (anomalies) {
        anomalyFeedCache = anomalies;
    }

    // Part 2: Tell the UI to render what we found
    renderRestoredLogs(liveLogsCache);
    renderRestoredAnomalies(anomalyFeedCache);
    updateStatsOnScreen(totalCount, normalCount, anomalyCount, sessionCount);
    saveSessionState();
}

async function fetchTrainingStats() {
    try {
        const stats = await api.fetchTrainingStats();
        document.getElementById('trainedTotal').textContent = stats.total;
        document.getElementById('trainedNormal').textContent = stats.normal;
        document.getElementById('trainedAnomaly').textContent = stats.anomaly;
    } catch (error) {
        console.error('Error fetching training stats:', error);
    }
}

async function loadInitialAnomalies() {
    const tableBody = document.getElementById('anomalyFeedTableBody');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="6" class="no-alerts-row">Loading alerts...</td></tr>';

    try {
        const alerts = await api.fetchInitialAnomalies();

        tableBody.innerHTML = '';

        // Render each alert using the existing renderAnomalyFeedRow function
        // which handles row creation, click handlers, and action buttons
        alerts.forEach(alert => {
            renderAnomalyFeedRow(alert, false);
        });

    } catch (error) {
        console.error("Failed to load initial anomalies:", error);
        tableBody.innerHTML = '<tr><td colspan="6" class="no-alerts-row">Failed to load alerts.</td></tr>';
    }
}

async function initializeMonitoringStatus() {
    try {
        const data = await api.fetchMonitoringStatus();
        updateMonitoringStatusUI(data.is_active);
    } catch (error) {
        console.error("Failed to get initial monitoring status:", error);
        updateMonitoringStatusUI(false);
    }
}

async function refreshCriticalAlerts() {
    const container = document.getElementById("alertsContainer");
    if (!container) return;

    try {
        const dbAlerts = await api.fetchAllAnomalies();

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

async function refreshAllWidgets() {
    console.log("Refreshing widget data...");
    await Promise.all([
        updateTopNChart('topVerdictsChart', 'verdict'),
        updateTopNChart('topAnomalousIpsChart', 'ip'),
        updateTopNChart('topSourcesChart', 'source'),
        updateDetectionMethodChart(),
        fetchTrainingStats(),
        updateStatWidgets() // Update Session Activity and Alert Breakdown widgets
    ]);
    console.log("Widget refresh complete.");
}

// Update Session Activity and Alert Breakdown stat widgets
async function updateStatWidgets() {
    try {
        // Session Activity Widget - use existing data or fetch from stats
        const sessionEl = document.getElementById('widget-active-sessions');
        const uniqueIpsEl = document.getElementById('widget-unique-ips');
        const avgRiskEl = document.getElementById('widget-avg-risk');

        if (sessionEl) sessionEl.textContent = sessionCount || 0;

        // Fetch unique IPs and avg risk from API
        const response = await fetch('/api/stats/overview');
        if (response.ok) {
            const stats = await response.json();
            if (uniqueIpsEl) uniqueIpsEl.textContent = stats.unique_ips_24h || '--';
            if (avgRiskEl) avgRiskEl.textContent = (stats.avg_risk_score || 0).toFixed(2);

            // Historical summary stats
            const histTodayEl = document.getElementById('hist-today-anomalies');
            const histPeakEl = document.getElementById('hist-peak-hour');
            const histTrendEl = document.getElementById('hist-trend');

            if (histTodayEl) histTodayEl.textContent = stats.today_anomalies || 0;
            if (histPeakEl) histPeakEl.textContent = stats.peak_hour || '--';
            if (histTrendEl) histTrendEl.textContent = stats.seven_day_trend || '--';
        }

        // Alert Breakdown Widget
        const alertsResponse = await fetch('/api/stats/alert_breakdown');
        if (alertsResponse.ok) {
            const alertStats = await alertsResponse.json();
            const newEl = document.getElementById('widget-alerts-new');
            const ackEl = document.getElementById('widget-alerts-ack');
            const closedEl = document.getElementById('widget-alerts-closed');

            if (newEl) newEl.textContent = alertStats.new || 0;
            if (ackEl) ackEl.textContent = alertStats.acknowledged || 0;
            if (closedEl) closedEl.textContent = alertStats.closed || 0;
        }
    } catch (error) {
        console.error("Error updating stat widgets:", error);
    }
}

async function handlePdfExport() {
    const pdfBtn = document.getElementById('exportPdfBtn');
    const btnText = pdfBtn.querySelector('.btn-text');
    const spinner = pdfBtn.querySelector('.spinner');

    // Show loading state
    btnText.textContent = 'Generating...';
    spinner.style.display = 'inline-block';
    pdfBtn.disabled = true;

    // 1. Gather search criteria
    const searchCriteria = {
        keyword: document.getElementById('searchKeyword').value || null,
        ip_address: document.getElementById('searchIpAddress').value || null,
        source: document.getElementById('searchSource').value || null,
        detection_method: document.getElementById('searchDetectionMethod').value || null,
        risk_score_min: parseFloat(document.getElementById('searchRiskScore').value) || null,
        start_time: document.getElementById('searchStartTime').value || null,
        end_time: document.getElementById('searchEndTime').value || null,
        filter_logic: document.querySelector('input[name="filter_logic"]:checked').value
    };

    // 2. Capture chart images as Base64 strings
    const chartImages = {};
    const chartIds = {
        "Top Anomaly Verdicts": "topVerdictsChart",
        "Top Anomalous IPs": "topAnomalousIpsChart",
        "Top Anomaly Sources": "topSourcesChart",
        "Detection Method Breakdown": "detectionMethodChart"
    };

    for (const [title, canvasId] of Object.entries(chartIds)) {
        const chartCanvas = document.getElementById(canvasId);
        if (chartCanvas && chartCanvas.offsetParent !== null) { // Check if canvas is visible
            chartImages[title] = chartCanvas.toDataURL('image/png');
        }
    }

    // 3. Add images and clean up the payload
    searchCriteria.chart_images = chartImages;
    Object.keys(searchCriteria).forEach(key => {
        if (searchCriteria[key] === null || searchCriteria[key] === '') {
            delete searchCriteria[key];
        }
    });

    try {
        // 4. Send the complete package to the backend
        const response = await fetch('/api/export/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(searchCriteria)
        });

        if (!response.ok) throw new Error('PDF generation failed on the server.');

        // 5. Handle the file download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = "dashboard_report.pdf";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

        showToast("Comprehensive report downloaded.", "success");

    } catch (error) {
        console.error("Error exporting PDF:", error);
        showToast("Failed to generate report.", "error");
    } finally {
        // Restore button state
        btnText.textContent = 'Export PDF';
        spinner.style.display = 'none';
        pdfBtn.disabled = false;
    }
}

// --- Phase 5: Cases and MITRE Functions ---

async function loadCases() {
    const container = document.getElementById('casesContainer');
    if (!container) return;

    // Status icons using folder metaphor
    const statusIcons = {
        'Open': `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2v11z"></path><path d="M2 10h20"></path></svg>`,
        'In Progress': `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>`,
        'Resolved': `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`,
        'Closed': `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>`
    };

    const priorityColors = {
        'Low': { border: '#22c55e', bg: 'rgba(34, 197, 94, 0.1)' },
        'Medium': { border: '#eab308', bg: 'rgba(234, 179, 8, 0.1)' },
        'High': { border: '#f97316', bg: 'rgba(249, 115, 22, 0.1)' },
        'Critical': { border: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' }
    };

    const statusColors = {
        'Open': '#3b82f6',
        'In Progress': '#eab308',
        'Resolved': '#22c55e',
        'Closed': '#6b7280'
    };

    try {
        const response = await fetch('/api/cases');
        const cases = await response.json();

        if (!cases || cases.length === 0) {
            container.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 60px 40px; color: var(--text-color-secondary);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity: 0.4;">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                        <line x1="12" y1="11" x2="12" y2="17"></line>
                        <line x1="9" y1="14" x2="15" y2="14"></line>
                    </svg>
                    <h4 style="margin: 16px 0 8px 0; color: var(--text-color);">No Investigation Cases</h4>
                    <p style="margin: 0; font-size: 14px;">Click "+ New Case" to create your first investigation.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = cases.map(c => {
            const priority = priorityColors[c.priority] || priorityColors['Medium'];
            const statusColor = statusColors[c.status] || statusColors['Open'];
            const statusIcon = statusIcons[c.status] || statusIcons['Open'];
            const isClosed = c.status === 'Closed' || c.status === 'Resolved';

            return `
                <div class="case-card" data-case-id="${c.id}" style="
                    background: ${priority.bg};
                    border-radius: 12px;
                    border-left: 4px solid ${priority.border};
                    padding: 0;
                    overflow: hidden;
                    transition: all 0.2s;
                    ${isClosed ? 'opacity: 0.7;' : ''}
                ">
                    <!-- Header with status icon and priority -->
                    <div style="padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--card-border);">
                        <div style="display: flex; align-items: center; gap: 8px; color: ${statusColor};">
                            ${statusIcon}
                            <span style="font-weight: 600; font-size: 12px; text-transform: uppercase;">${c.status}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <span style="background: ${priority.border}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;">${c.priority}</span>
                        </div>
                    </div>
                    
                    <!-- Body -->
                    <div style="padding: 16px;">
                        <h4 style="margin: 0 0 8px 0; color: var(--text-color); font-size: 15px; font-weight: 600;">${escapeHTML(c.title)}</h4>
                        <p style="margin: 0 0 12px 0; color: var(--text-color-secondary); font-size: 13px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                            ${escapeHTML(c.description || 'No description provided')}
                        </p>
                        
                        <!-- Stats row -->
                        <div style="display: flex; gap: 16px; margin-bottom: 12px; font-size: 12px; color: var(--text-color-secondary);">
                            <span style="display: flex; align-items: center; gap: 4px;">
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path></svg>
                                ${c.alert_count || 0} alerts
                            </span>
                            <span style="display: flex; align-items: center; gap: 4px;">
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                                ${new Date(c.created_at).toLocaleDateString()}
                            </span>
                        </div>
                    </div>
                    
                    <!-- Actions footer -->
                    <div style="padding: 12px 16px; background: var(--card-bg); border-top: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; gap: 8px;">
                            <button onclick="event.stopPropagation(); openAddAlertModal(${c.id})" class="case-action-btn" style="background: var(--button-primary); color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px;">
                                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                                Add Alert
                            </button>
                            <select onchange="updateCaseStatus(${c.id}, this.value)" onclick="event.stopPropagation()" style="background: var(--card-dark-bg); color: var(--text-color); border: 1px solid var(--card-border); padding: 6px 8px; border-radius: 6px; font-size: 11px; cursor: pointer;">
                                <option value="Open" ${c.status === 'Open' ? 'selected' : ''}>📂 Open</option>
                                <option value="In Progress" ${c.status === 'In Progress' ? 'selected' : ''}>🔄 In Progress</option>
                                <option value="Resolved" ${c.status === 'Resolved' ? 'selected' : ''}>✅ Resolved</option>
                                <option value="Closed" ${c.status === 'Closed' ? 'selected' : ''}>📁 Closed</option>
                            </select>
                        </div>
                        <button onclick="event.stopPropagation(); deleteCase(${c.id})" class="case-action-btn" style="background: transparent; color: var(--danger-color); border: 1px solid var(--danger-color); padding: 6px 10px; border-radius: 6px; font-size: 11px; cursor: pointer;" title="Delete Case">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) {
        console.error('Failed to load cases:', err);
        container.innerHTML = '<p style="color: var(--danger-color);">Failed to load cases.</p>';
    }
}


async function loadMitreHeatmap() {
    const container = document.getElementById('mitreHeatmapContainer');
    if (!container) return;

    // Tactic-specific colors based on kill chain progression
    const tacticColors = {
        'Reconnaissance': '#94a3b8',
        'Resource Development': '#a78bfa',
        'Initial Access': '#f472b6',
        'Execution': '#fb923c',
        'Persistence': '#f87171',
        'Privilege Escalation': '#ef4444',
        'Defense Evasion': '#eab308',
        'Credential Access': '#22c55e',
        'Discovery': '#06b6d4',
        'Lateral Movement': '#3b82f6',
        'Collection': '#8b5cf6',
        'Command and Control': '#ec4899',
        'Exfiltration': '#dc2626',
        'Impact': '#b91c1c',
        'Unknown': '#64748b'
    };

    // MITRE ID mapping to tactic slug for URLs
    const tacticSlugs = {
        'Reconnaissance': 'reconnaissance',
        'Resource Development': 'resource-development',
        'Initial Access': 'initial-access',
        'Execution': 'execution',
        'Persistence': 'persistence',
        'Privilege Escalation': 'privilege-escalation',
        'Defense Evasion': 'defense-evasion',
        'Credential Access': 'credential-access',
        'Discovery': 'discovery',
        'Lateral Movement': 'lateral-movement',
        'Collection': 'collection',
        'Command and Control': 'command-and-control',
        'Exfiltration': 'exfiltration',
        'Impact': 'impact'
    };

    try {
        const response = await fetch('/api/stats/mitre_heatmap');
        const data = await response.json();

        if (!data || data.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 60px 40px; color: var(--text-color-secondary);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity: 0.5;">
                        <rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect>
                    </svg>
                    <h4 style="margin: 16px 0 8px 0; color: var(--text-color);">No Techniques Detected yet</h4>
                    <p style="margin: 0; font-size: 14px;">MITRE ATT&CK techniques will appear here live when alerts are triggered.</p>
                </div>
            `;
            return;
        }

        // Group by tactic
        const tactics = {};
        let totalCount = 0;
        data.forEach(item => {
            const tactic = item.mitre_tactic || 'Unknown';
            if (!tactics[tactic]) tactics[tactic] = [];
            tactics[tactic].push(item);
            totalCount += item.count;
        });

        const maxCount = Math.max(...data.map(d => d.count));

        // Render improved heatmap
        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--card-border);">
                <div><span style="font-size: 24px; font-weight: 700; color: var(--text-color);">${data.length}</span><span style="color: var(--text-color-secondary); margin-left: 8px;">Unique Techniques</span></div>
                <div><span style="font-size: 24px; font-weight: 700; color: var(--danger-color);">${totalCount}</span><span style="color: var(--text-color-secondary); margin-left: 8px;">Total Detections</span></div>
                <div><span style="font-size: 24px; font-weight: 700; color: var(--accent-purple);">${Object.keys(tactics).length}</span><span style="color: var(--text-color-secondary); margin-left: 8px;">Tactics Covered</span></div>
            </div>
            <div class="mitre-tactics" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px;">
        `;

        for (const [tactic, techniques] of Object.entries(tactics)) {
            const tacticColor = tacticColors[tactic] || tacticColors['Unknown'];
            const tacticTotal = techniques.reduce((sum, t) => sum + t.count, 0);
            const tacticUrl = `https://attack.mitre.org/tactics/${tacticSlugs[tactic] || ''}/`;

            html += `
                <div class="mitre-tactic-card" style="background: var(--card-dark-bg); border-radius: 12px; padding: 16px; border-left: 4px solid ${tacticColor}; transition: transform 0.2s; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <a href="${tacticUrl}" target="_blank" style="text-decoration: none; display: flex; align-items: center; gap: 6px;">
                            <h4 style="margin: 0; color: var(--text-color); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">${tactic}</h4>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-color-secondary)" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                        </a>
                        <span style="background: ${tacticColor}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">${tacticTotal}</span>
                    </div>
                    <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                        ${techniques.sort((a, b) => b.count - a.count).map(t => {
                const intensity = t.count / maxCount;
                const opacity = 0.3 + intensity * 0.7;
                const techIdMatch = t.mitre_technique.match(/(T\d+(\.\d+)?)/);
                const techId = techIdMatch ? techIdMatch[0] : '';
                const techUrl = techId ? `https://attack.mitre.org/techniques/${techId.replace('.', '/')}/` : '#';

                return `
                                <a href="${techUrl}" target="_blank" class="mitre-technique" style="text-decoration: none; background: ${tacticColor}${Math.round(opacity * 255).toString(16).padStart(2, '0')}; padding: 6px 10px; border-radius: 6px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s;" title="${t.mitre_technique}: ${t.count} occurrences">
                                    <span style="color: white; text-shadow: 0 1px 2px rgba(0,0,0,0.5); font-weight: 500;">${t.mitre_technique}</span>
                                    <span style="background: rgba(0,0,0,0.4); color: white; padding: 1px 5px; border-radius: 4px; font-size: 10px; font-weight: 600;">${t.count}</span>
                                </a>
                            `;
            }).join('')}
                    </div>
                </div>
            `;
        }
        html += '</div>';

        container.innerHTML = html;
    } catch (err) {
        console.error('Failed to load MITRE heatmap:', err);
        container.innerHTML = '<p style="color: var(--danger-color); text-align: center; padding: 40px;">Failed to load MITRE data.</p>';
    }
}

// --- Phase 5: Case Modal Handlers ---
const caseModal = document.getElementById('case-modal');
const caseForm = document.getElementById('case-form');
const deleteModal = document.getElementById('delete-modal');

// Open case modal and load alerts
document.getElementById('create-case-btn')?.addEventListener('click', () => {
    if (caseModal) {
        caseModal.style.display = 'flex';
        document.getElementById('case-title')?.focus();
        loadAlertsForSelection();
    }
});

async function loadAlertsForSelection() {
    const listContainer = document.getElementById('alert-selection-list');
    const countSpan = document.getElementById('selected-alert-count');
    if (!listContainer) return;

    listContainer.innerHTML = '<div style="text-align: center; color: var(--text-color-secondary); padding: 20px;">Loading alerts...</div>';

    try {
        const response = await fetch('/api/alerts');
        const alerts = await response.json();

        if (!alerts || alerts.length === 0) {
            listContainer.innerHTML = '<div style="text-align: center; color: var(--text-color-secondary); padding: 20px;">No open alerts available to link.</div>';
            return;
        }

        listContainer.innerHTML = alerts.map(alert => `
            <div class="alert-select-item" onclick="toggleAlertSelection(this, ${alert.id})" style="padding: 10px; margin-bottom: 8px; border: 1px solid var(--card-border); border-radius: 6px; cursor: pointer; transition: all 0.2s; background: var(--card-bg);">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <span style="font-weight: 600; font-size: 13px; color: var(--text-color);">${escapeHTML(alert.rule_name)}</span>
                    <span class="badge" style="background: ${getRiskColor(alert.risk_score)}; font-size: 10px;">Risk ${alert.risk_score}</span>
                </div>
                <div style="font-size: 11px; color: var(--text-color-secondary); margin-top: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${escapeHTML(alert.content)}</div>
                <div style="font-size: 10px; color: var(--text-color-secondary); margin-top: 6px; display: flex; justify-content: space-between;">
                    <span>${new Date(alert.timestamp).toLocaleString()}</span>
                    <span>${alert.mitre_technique || 'No Technique'}</span>
                </div>
            </div>
        `).join('');

        // Reset selected count
        countSpan.textContent = '(0 selected)';
        countSpan.dataset.selectedIds = '[]';

    } catch (err) {
        console.error('Failed to load alerts for selection:', err);
        listContainer.innerHTML = '<div style="color: var(--danger-color); text-align: center; padding: 20px;">Failed to load alerts</div>';
    }
}

window.toggleAlertSelection = function (element, alertId) {
    const isSelected = element.style.borderColor === 'var(--button-primary)';

    // Toggle styles
    if (isSelected) {
        element.style.borderColor = 'var(--card-border)';
        element.style.background = 'var(--card-bg)';
    } else {
        element.style.borderColor = 'var(--button-primary)';
        element.style.background = 'rgba(59, 130, 246, 0.1)';
    }

    // Update selected IDs list
    const countSpan = document.getElementById('selected-alert-count');
    let selectedIds = JSON.parse(countSpan.dataset.selectedIds || '[]');

    if (isSelected) {
        selectedIds = selectedIds.filter(id => id !== alertId);
    } else {
        selectedIds.push(alertId);
    }

    countSpan.dataset.selectedIds = JSON.stringify(selectedIds);
    countSpan.textContent = `(${selectedIds.length} selected)`;
};

function getRiskColor(score) {
    if (score >= 80) return '#ef4444';
    if (score >= 40) return '#f97316';
    return '#22c55e';
}

// Close case modal
document.getElementById('case-modal-close')?.addEventListener('click', () => {
    if (caseModal) caseModal.style.display = 'none';
});
document.getElementById('case-cancel-btn')?.addEventListener('click', () => {
    if (caseModal) caseModal.style.display = 'none';
});

// Close on overlay click
caseModal?.addEventListener('click', (e) => {
    if (e.target === caseModal) caseModal.style.display = 'none';
});

// Handle case form submission
caseForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const submitBtn = document.getElementById('case-submit-btn');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="spinner" style="width: 16px; height: 16px; border: 2px solid white; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; display: inline-block;"></span> Creating...';
    submitBtn.disabled = true;

    const countSpan = document.getElementById('selected-alert-count');
    const selectedIds = JSON.parse(countSpan.dataset.selectedIds || '[]');

    const caseData = {
        title: document.getElementById('case-title').value,
        description: document.getElementById('case-description').value,
        priority: document.getElementById('case-priority').value
    };

    try {
        // 1. Create Case
        const response = await fetch('/api/cases', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(caseData)
        });

        if (response.ok) {
            const result = await response.json();
            const caseId = result.id;

            // 2. Link Selected Alerts (if any)
            if (selectedIds.length > 0) {
                await fetch(`/api/cases/${caseId}/alerts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ alert_ids: selectedIds })
                });
            }

            showToast('Investigation case created successfully!', 'success');
            caseModal.style.display = 'none';
            caseForm.reset();
            loadCases();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to create case', 'error');
        }
    } catch (err) {
        console.error('Failed to create case:', err);
        showToast('Failed to create case', 'error');
    } finally {
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
});

// --- Case Action Functions (exposed globally) ---

// Update case status
window.updateCaseStatus = async function (caseId, newStatus) {
    try {
        const response = await fetch(`/api/cases/${caseId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });

        if (response.ok) {
            showToast(`Case status updated to "${newStatus}"`, 'success');
            loadCases();
        } else {
            showToast('Failed to update status', 'error');
        }
    } catch (err) {
        console.error('Failed to update case status:', err);
        showToast('Failed to update status', 'error');
    }
};

// Custom Modal Delete Case
window.deleteCase = function (caseId) {
    if (!deleteModal) return;

    deleteModal.style.display = 'flex';

    // Cleanup old event listeners
    const confirmBtn = document.getElementById('delete-confirm-btn');
    const cancelBtn = document.getElementById('delete-cancel-btn');

    const newConfirm = confirmBtn.cloneNode(true);
    const newCancel = cancelBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirm, confirmBtn);
    cancelBtn.parentNode.replaceChild(newCancel, cancelBtn);

    // Add new listeners
    newCancel.addEventListener('click', () => {
        deleteModal.style.display = 'none';
    });

    // Close on overlay click
    deleteModal.onclick = (e) => {
        if (e.target === deleteModal) deleteModal.style.display = 'none';
    };

    newConfirm.addEventListener('click', async () => {
        try {
            const response = await fetch(`/api/cases/${caseId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                showToast('Case deleted successfully', 'success');
                loadCases();
            } else {
                showToast('Failed to delete case', 'error');
            }
        } catch (err) {
            console.error('Failed to delete case:', err);
            showToast('Failed to delete case', 'error');
        } finally {
            deleteModal.style.display = 'none';
        }
    });
};

// Open Add Alert modal
window.openAddAlertModal = function (caseId) {
    const alertId = prompt('Enter Alert ID to link:');
    if (!alertId || isNaN(alertId)) {
        if (alertId !== null) showToast('Please enter a valid alert ID', 'error');
        return;
    }

    linkAlertToCase(caseId, parseInt(alertId));
};

// Link alert to case
async function linkAlertToCase(caseId, alertId) {
    try {
        const response = await fetch(`/api/cases/${caseId}/alerts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ alert_ids: [alertId] })
        });

        if (response.ok) {
            showToast('Alert linked to case successfully!', 'success');
            loadCases();
        } else {
        }
    } catch (err) {
        console.error('Failed to link alert:', err);
        showToast('Failed to link alert', 'error');
    }
}