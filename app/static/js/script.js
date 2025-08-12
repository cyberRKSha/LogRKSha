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
        case "alert":
            // This part was correct.
            renderAlertRow(msg.data, true); // Pass 'isNew' flag
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
    row.className = 'fade-in';
    const labelText = (data.label || 'unknown').toLowerCase().trim();
    
    row.insertCell(0).textContent = new Date(data.timestamp).toLocaleString();
    row.insertCell(1).innerHTML = `<span class="label-${labelText}">${labelText}</span>`;
    row.insertCell(2).textContent = data.verdict || 'N/A';
    row.insertCell(3).textContent = data.log || '-';

    if (labelText === 'anomaly') {
        row.classList.add('log-anomaly');
        anomalyCount++;
        renderAnomalyFeedRow(data);
    } else {
        normalCount++;
    }
    totalCount++;
}

function renderAnomalyFeedRow(data, isNew) {
    const tableBody = document.getElementById("anomalyFeedTableBody");
    if (!tableBody) return;
    const row = tableBody.insertRow(0);
    if (isNew) row.className = 'fade-in';
    row.classList.add('log-anomaly');
    row.insertCell(0).textContent = new Date(data.timestamp).toLocaleString();
    row.insertCell(1).textContent = data.verdict || 'N/A';
    row.insertCell(2).textContent = data.log || '-';
}

function renderAlertRow(data, isNew) {
    const container = document.getElementById("alertsContainer");
    if (!container) return;
    const div = document.createElement('div');
    div.className = isNew ? 'alert-critical fade-in' : 'alert-critical';
    div.innerHTML = `<strong>Critical:</strong> ${data.advice || "No advice."}<br><small>Ref Log: ${data.log || "N/A"}</small>`;
    container.appendChild(div);
    if (isNew) autoScroll(container);
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
            let labelText = log.final_label === 1 ? 'anomaly' : 'normal';
            row.insertCell(0).textContent = new Date(log.timestamp).toLocaleString();
            row.insertCell(1).innerHTML = `<span class="label-${labelText}">${labelText}</span>`;
            row.insertCell(2).textContent = log.source;
            row.insertCell(3).textContent = log.content;
            if (log.final_label === 1) row.classList.add('log-anomaly');
        });
    } catch (error) {
        console.error('Error fetching search results:', error);
        resultsBody.innerHTML = '<tr><td colspan="4">An error occurred while searching.</td></tr>';
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

    // Hide the main dashboard and show the review container
    mainDashboard.style.display = 'none';
    reviewContainer.style.display = 'block';
    reviewContainer.innerHTML = '<h2>Loading logs for review...</h2>';

    try {
        let url = '/api/review/pending';
        if (sortBy !== null) { // Only add the sort_by parameter if it's not null
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

        if (entries.length === 0) {
            reviewContainer.innerHTML = `
                <div class="review-header"><h1>Log Review</h1><button id="close-review-btn" class="control-button">Back to Dashboard</button></div>
                ${sortButtonsHTML}
                <p class="review-no-logs">No pending logs to review. Great job!</p>
            `;
            document.getElementById('close-review-btn').addEventListener('click', closeReviewInterface);
            return;
        }

        let tableRows = '';
        entries.forEach(entry => {
            tableRows += `
                <tr>
                    <td>${new Date(entry.timestamp).toLocaleString()}</td>
                    <td>${entry.source}</td>
                    <td class="log-content">${entry.content}</td>
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

        reviewContainer.innerHTML = `
            <div class="review-header"><h1>Pending Logs for Review</h1><button id="close-review-btn" class="control-button">Back to Dashboard</button></div>
            ${sortButtonsHTML}
            <table class="review-table">
                <thead><tr><th>Timestamp</th><th>Source</th><th>Content</th><th>Correct Label?</th></tr></thead>
                <tbody>${tableRows}</tbody>
            </table>
            <div class="review-actions"><button id="save-reviews-btn" class="submit-button">Save</button></div>
        `;

        document.getElementById('close-review-btn').addEventListener('click', closeReviewInterface);
        document.getElementById('save-reviews-btn').addEventListener('click', saveReviews);

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