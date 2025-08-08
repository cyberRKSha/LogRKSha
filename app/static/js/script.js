// let ws = new WebSocket("ws://" + window.location.host + "/ws");
// let logChart; // Donut chart
// let historicalChart; // Line chart
// let normalCount = 0;
// let anomalyCount = 0;
// let totalCount = 0;
// let sessionCount = 0;

// // Animate a number smoothly
// function animateCount(id, newCount) {
//     let el = document.getElementById(id);
//     if (!el) return;
//     let current = parseInt(el.textContent) || 0;
//     let diff = newCount - current;
//     if (diff === 0) return;
//     let step = diff / 20;
//     let i = 0;
//     let interval = setInterval(() => {
//         i++;
//         el.textContent = Math.round(current + step * i);
//         if (i >= 20) {
//             el.textContent = newCount;
//             clearInterval(interval);
//         }
//     }, 20);
// }

// // Update stats text and chart
// function updateStatsAndChart() {
//     animateCount('totalLogs', totalCount);
//     animateCount('normalCount', normalCount);
//     animateCount('anomalyCount', anomalyCount);
//     animateCount('sessionCount', sessionCount);

//     if (logChart) {
//         logChart.data.datasets[0].data = [normalCount, anomalyCount];
//         logChart.update();
//     }
//     document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
// }

// // Initialize donut chart
// function initChart() {
//     totalCount = parseInt(document.getElementById('totalLogs').textContent) || 0;
//     normalCount = parseInt(document.getElementById('normalCount').textContent) || 0;
//     anomalyCount = parseInt(document.getElementById('anomalyCount').textContent) || 0;

//     let ctx = document.getElementById('logChart').getContext('2d');
//     logChart = new Chart(ctx, {
//         type: 'doughnut',
//         data: {
//             labels: ['Normal', 'Anomaly'],
//             datasets: [{ data: [normalCount, anomalyCount], backgroundColor: ['#28a745', '#dc3545'] }]
//         },
//         options: {
//             responsive: true, maintainAspectRatio: false,
//             plugins: { legend: { position: 'bottom', labels: { color: getComputedStyle(document.body).getPropertyValue('--text-color-primary') } } }
//         }
//     });
//     updateStatsAndChart();
// }

// // Initialize historical line chart
// function initHistoricalChart() {
//     fetch('/api/historical-trends?interval=H')
//         .then(response => response.json())
//         .then(data => {
//             if (!data || data.length === 0) return;
//             const labels = data.map(d => d.timestamp);
//             const anomalyData = data.map(d => d.anomalies);
//             const ctx = document.getElementById('historicalChart').getContext('2d');
//             historicalChart = new Chart(ctx, {
//                 type: 'line',
//                 data: {
//                     labels: labels,
//                     datasets: [{ label: 'Anomalies per Hour', data: anomalyData, borderColor: '#dc3545', backgroundColor: 'rgba(220, 53, 69, 0.2)', fill: true, tension: 0.3 }]
//                 },
//                 options: {
//                     responsive: true, maintainAspectRatio: false,
//                     scales: {
//                         x: { display: false },
//                         y: {
//                             beginAtZero: true,
//                             ticks: { stepSize: 1, color: getComputedStyle(document.body).getPropertyValue('--text-color-primary') }
//                         }
//                     },
//                     plugins: { legend: { labels: { color: getComputedStyle(document.body).getPropertyValue('--text-color-primary') } } }
//                 }
//             });
//         })
//         .catch(error => console.error('Error fetching historical data:', error));
// }

// // === START: CRITICAL FIX for Dark Mode Chart Text ===
// // Toggle dark mode and update chart text colors
// function toggleDarkMode() {
//     document.body.classList.toggle('dark-mode');
//     // Get the new text color after the theme has changed
//     const newTextColor = getComputedStyle(document.body).getPropertyValue('--text-color-primary');

//     // Update donut chart colors
//     if (logChart) {
//         logChart.options.plugins.legend.labels.color = newTextColor;
//         logChart.update();
//     }
//     // Update historical chart colors
//     if (historicalChart) {
//         historicalChart.options.plugins.legend.labels.color = newTextColor;
//         historicalChart.options.scales.y.ticks.color = newTextColor;
//         historicalChart.update();
//     }
// }
// // === END: CRITICAL FIX for Dark Mode Chart Text ===

// ws.onmessage = function(event) {
//     let msg = JSON.parse(event.data);
//     if (msg.type === "session_update") { sessionCount = msg.count; }
//     else if (msg.type === "log") { addLogRow(msg.data); }
//     else if (msg.type === "alert") { addAlertRow(msg.data); }
//     updateStatsAndChart();
// };

// function addLogRow(data) {
//     let table = document.getElementById("logsTable").getElementsByTagName('tbody')[0];
//     if (!table) return;
//     let row = table.insertRow(-1);
//     row.className = 'fade-in';
//     let timestamp = data.timestamp ? new Date(data.timestamp).toLocaleString() : new Date().toLocaleString();
//     let labelText = (data.label || 'unknown').toLowerCase().trim();
//     let log = data.log || '-';
//     row.innerHTML = `<td>${timestamp}</td><td>${labelText}</td><td>${log}</td>`;
//     if (labelText === 'anomaly') { row.classList.add('log-anomaly'); anomalyCount++; }
//     else { row.classList.add('log-normal'); normalCount++; }
//     totalCount++;
//     autoScroll('logsContainer');
// }

// function addAlertRow(data) {
//     let container = document.getElementById("alertsContainer");
//     if (!container) return;
//     let div = document.createElement('div');
//     div.className = 'alert-critical fade-in';
//     let advice = data.advice || "No specific advice available.";
//     let logText = data.log || "No reference log.";
//     div.innerHTML = `<strong>Critical:</strong> ${advice}<br><small>Ref Log: ${logText}</small>`;
//     container.appendChild(div);
//     autoScroll('alertsContainer');
// }

// function autoScroll(containerId) {
//     let container = document.getElementById(containerId);
//     if (container) { // Check if container exists
//         container.scrollTop = container.scrollHeight;
//     }
// }

// function setupEventListeners() {
//     const applyBtn = document.getElementById('applyFiltersBtn');
//     if (applyBtn) { applyBtn.addEventListener('click', filterLogs); }
//     const darkModeToggle = document.getElementById('darkModeToggle');
//     if (darkModeToggle) { darkModeToggle.addEventListener('click', toggleDarkMode); }
// }

// function filterLogs() {
//     const keyword = document.getElementById('keywordSearch').value.toLowerCase();
//     const startTime = document.getElementById('startTime').value ? new Date(document.getElementById('startTime').value) : null;
//     const endTime = document.getElementById('endTime').value ? new Date(document.getElementById('endTime').value) : null;
//     const type = document.getElementById('logFilter').value;
//     const rows = document.querySelectorAll("#logsTable tbody tr");
//     rows.forEach(row => {
//         if (row.cells.length < 3) return;
//         const logTimestampStr = row.cells[0].textContent;
//         const logType = row.cells[1].textContent.toLowerCase();
//         const logContent = row.cells[2].textContent.toLowerCase();
//         const logTimestamp = new Date(logTimestampStr);
//         const keywordMatch = logContent.includes(keyword);
//         const typeMatch = (type === 'all' || logType === type);
//         const startTimeMatch = (!startTime || logTimestamp >= startTime);
//         const endTimeMatch = (!endTime || logTimestamp <= endTime);
//         if (keywordMatch && typeMatch && startTimeMatch && endTimeMatch) { row.style.display = ''; }
//         else { row.style.display = 'none'; }
//     });
// }

// setInterval(() => {
//     document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
// }, 60000);

















































































































// app/static/js/script.js (Updated for 4-Column Layout with Verdict)

let ws = new WebSocket("ws://" + window.location.host + "/ws");
let logChart; // Donut chart
let historicalChart; // Line chart
let normalCount = 0;
let anomalyCount = 0;
let totalCount = 0;
let sessionCount = 0;

// Animate a number smoothly
function animateCount(id, newCount) {
    let el = document.getElementById(id);
    if (!el) return;
    let current = parseInt(el.textContent) || 0;
    let diff = newCount - current;
    if (diff === 0) return;
    let step = diff / 20;
    let i = 0;
    let interval = setInterval(() => {
        i++;
        el.textContent = Math.round(current + step * i);
        if (i >= 20) {
            el.textContent = newCount;
            clearInterval(interval);
        }
    }, 20);
}

// Update stats text and chart
function updateStatsAndChart() {
    animateCount('totalLogs', totalCount);
    animateCount('normalCount', normalCount);
    animateCount('anomalyCount', anomalyCount);
    animateCount('sessionCount', sessionCount);

    if (logChart) {
        logChart.data.datasets[0].data = [normalCount, anomalyCount];
        logChart.update();
    }
    document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
}

// Initialize donut chart
function initChart() {
    totalCount = parseInt(document.getElementById('totalLogs').textContent) || 0;
    normalCount = parseInt(document.getElementById('normalCount').textContent) || 0;
    anomalyCount = parseInt(document.getElementById('anomalyCount').textContent) || 0;

    let ctx = document.getElementById('logChart').getContext('2d');
    logChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Normal', 'Anomaly'],
            datasets: [{ data: [normalCount, anomalyCount], backgroundColor: ['#28a745', '#dc3545'] }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { color: getComputedStyle(document.body).getPropertyValue('--text-color-primary') } } }
        }
    });
    updateStatsAndChart();
}

// Initialize historical line chart
function initHistoricalChart() {
    fetch('/api/historical-trends?interval=H')
        .then(response => response.json())
        .then(data => {
            if (!data || data.length === 0) return;
            const labels = data.map(d => d.timestamp);
            const anomalyData = data.map(d => d.anomalies);
            const ctx = document.getElementById('historicalChart').getContext('2d');
            historicalChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{ label: 'Anomalies per Hour', data: anomalyData, borderColor: '#dc3545', backgroundColor: 'rgba(220, 53, 69, 0.2)', fill: true, tension: 0.3 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: {
                        x: { display: false },
                        y: {
                            beginAtZero: true,
                            ticks: { stepSize: 1, color: getComputedStyle(document.body).getPropertyValue('--text-color-primary') }
                        }
                    },
                    plugins: { legend: { labels: { color: getComputedStyle(document.body).getPropertyValue('--text-color-primary') } } }
                }
            });
        })
        .catch(error => console.error('Error fetching historical data:', error));
}

// Toggle dark mode and update chart text colors
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const newTextColor = getComputedStyle(document.body).getPropertyValue('--text-color-primary');

    if (logChart) {
        logChart.options.plugins.legend.labels.color = newTextColor;
        logChart.update();
    }
    if (historicalChart) {
        historicalChart.options.plugins.legend.labels.color = newTextColor;
        historicalChart.options.scales.y.ticks.color = newTextColor;
        historicalChart.update();
    }
}

ws.onmessage = function(event) {
    let msg = JSON.parse(event.data);
    if (msg.type === "session_update") { sessionCount = msg.count; }
    else if (msg.type === "log") { addLogRow(msg.data); }
    else if (msg.type === "alert") { addAlertRow(msg.data); }
    updateStatsAndChart();
};

// === UPDATED FUNCTION to handle the new 'verdict' field ===
function addLogRow(data) {
    let tableBody = document.getElementById("logsTable").getElementsByTagName('tbody')[0];
    if (!tableBody) return;

    // Insert at the top for a live feed effect
    let row = tableBody.insertRow(0);
    row.className = 'fade-in';

    let timestamp = data.timestamp ? new Date(data.timestamp).toLocaleString() : new Date().toLocaleString();
    let labelText = (data.label || 'unknown').toLowerCase().trim();
    let log = data.log || '-';
    // Get the new verdict from the data, provide a default if it's not present
    let verdict = data.verdict || 'N/A';

    // Create cells for the 4 columns: Timestamp, Label, Verdict, Content
    let cellTimestamp = row.insertCell(0);
    let cellLabel = row.insertCell(1);
    let cellVerdict = row.insertCell(2);
    let cellContent = row.insertCell(3);

    // Populate the cells with data
    cellTimestamp.textContent = timestamp;
    cellLabel.innerHTML = `<span class="label-${labelText}">${labelText}</span>`; // Use a span for potential styling
    cellVerdict.textContent = verdict;
    cellContent.textContent = log;

    // Apply styling based on the label
    if (labelText === 'anomaly') {
        row.classList.add('log-anomaly');
        anomalyCount++;
    } else {
        row.classList.add('log-normal');
        normalCount++;
    }
    totalCount++;
}

function addAlertRow(data) {
    let container = document.getElementById("alertsContainer");
    if (!container) return;
    let div = document.createElement('div');
    div.className = 'alert-critical fade-in';
    let advice = data.advice || "No specific advice available.";
    let logText = data.log || "No reference log.";
    div.innerHTML = `<strong>Critical:</strong> ${advice}<br><small>Ref Log: ${logText}</small>`;
    container.appendChild(div);
    autoScroll('alertsContainer');
}

function autoScroll(containerId) {
    let container = document.getElementById(containerId);
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function setupEventListeners() {
    const applyBtn = document.getElementById('applyFiltersBtn');
    if (applyBtn) { applyBtn.addEventListener('click', filterLogs); }
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (darkModeToggle) { darkModeToggle.addEventListener('click', toggleDarkMode); }
}

// === UPDATED FUNCTION to work with the new 4-column table structure ===
function filterLogs() {
    const keyword = document.getElementById('keywordSearch').value.toLowerCase();
    const startTime = document.getElementById('startTime').value ? new Date(document.getElementById('startTime').value) : null;
    const endTime = document.getElementById('endTime').value ? new Date(document.getElementById('endTime').value) : null;
    const type = document.getElementById('logFilter').value;
    const rows = document.querySelectorAll("#logsTable tbody tr");

    rows.forEach(row => {
        // Ensure the row has the correct number of cells before processing
        if (row.cells.length < 4) return;

        const logTimestampStr = row.cells[0].textContent;
        const logType = row.cells[1].textContent.toLowerCase(); // Label is in the second cell
        // Verdict is in the third cell, content is in the fourth
        const logVerdict = row.cells[2].textContent.toLowerCase();
        const logContent = row.cells[3].textContent.toLowerCase();
        const logTimestamp = new Date(logTimestampStr);

        // Keyword can now match content OR verdict
        const keywordMatch = logContent.includes(keyword) || logVerdict.includes(keyword);
        const typeMatch = (type === 'all' || logType === type);
        const startTimeMatch = (!startTime || logTimestamp >= startTime);
        const endTimeMatch = (!endTime || logTimestamp <= endTime);

        if (keywordMatch && typeMatch && startTimeMatch && endTimeMatch) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

setInterval(() => {
    document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
}, 60000);
