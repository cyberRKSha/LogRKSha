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