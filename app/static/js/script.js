// let ws = new WebSocket("ws://" + window.location.host + "/ws");
// let chart;
// let normalCount = 0;
// let anomalyCount = 0;
// // let totalCount = 0;
// let sessionCount = 0;

// // Initialize chart
// function initChart(initialNormal, initialAnomaly) {
//     normalCount = initialNormal || 0;
//     anomalyCount = initialAnomaly || 0;
//     totalCount = normalCount + anomalyCount;

//     let ctx = document.getElementById('logChart').getContext('2d');
//     chart = new Chart(ctx, {
//         type: 'doughnut',
//         data: {
//             labels: ['Normal', 'Anomaly'],
//             datasets: [{
//                 data: [normalCount, anomalyCount],
//                 backgroundColor: ['green', 'red']
//             }]
//         },
//         options: { responsive: true }
//     });

//     updateStatsAndChart();
// }

// // Update stats text and chart
// function updateStatsAndChart() {
//     animateCount('normalCount', normalCount);
//     animateCount('anomalyCount', anomalyCount);
//     animateCount('totalLogs', totalCount);
//     animateCount('sessionCount', sessionCount);

//     if (chart) {
//         chart.data.datasets[0].data = [normalCount, anomalyCount];
//         chart.update();
//     }

//     document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
// }

// // Animate a number smoothly
// function animateCount(id, newCount) {
//     let el = document.getElementById(id);
//     let current = parseInt(el.textContent) || 0;
//     let diff = newCount - current;
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

// // WebSocket handling
// ws.onopen = () => {
//     sessionCount++;
//     updateStatsAndChart();
// };

// ws.onclose = () => {
//     sessionCount = Math.max(0, sessionCount - 1);
//     updateStatsAndChart();
// };

// ws.onmessage = function(event) {
//     let msg = JSON.parse(event.data);
//     if (msg.type === "session_update") {
//         sessionCount = msg.count;
//     } else if (msg.type === "log") {
//         addLogRow(msg.data);
//     } else if (msg.type === "alert") {
//         addAlertRow(msg.data);
//     }
//     updateStatsAndChart();
// };

// function addLogRow(data) {

//     let table = document.getElementById("logsTable");
//     let row = table.insertRow(-1);  // append at bottom
//     row.className = 'fade-in';

//     let timestamp = data.timestamp || '-';
//     let rawLabel = data.label;  // could be '1' or '0' or true/false etc.
//     let log = data.log || '-';

//     // Map numeric/boolean label to string
//     let labelText = (data.label || '').toLowerCase().trim();

//     row.innerHTML = `<td>${timestamp}</td><td>${labelText}</td><td>${log}</td>`;

//     if (labelText === 'anomaly') {
//         row.classList.add('log-anomaly');
//         anomalyCount++;
//     } else if (labelText === 'normal') {
//         row.classList.add('log-normal');
//         normalCount++;
//     }

//     totalCount++;
//     updateStatsAndChart();
//     autoScroll('logsContainer');
// }

// // Add alert row
// function addAlertRow(data) {
//     let container = document.getElementById("alertsContainer");
//     let div = document.createElement('div');
//     div.className = 'alert-critical fade-in';
//     div.innerHTML = `${data.advice}<br><small>Ref Log: ${data.log}</small>`;
//     // container.prepend(div);
//     container.appendChild(div);
//     autoScroll('alertsContainer');
// }

// // Auto-scroll
// function autoScroll(containerId) {
//     let container = document.getElementById(containerId);
//     container.scrollTop = container.scrollHeight;
// }

// // Toggle dark mode
// function toggleDarkMode() {
//     document.body.classList.toggle('dark-mode');
// }

// // Filter logs
// function filterLogs(type) {
//     let rows = document.querySelectorAll("#logsTable tr");
//     rows.forEach(row => {
//         if (type === 'all' || row.cells[1].textContent === type) {
//             row.style.display = '';
//         } else {
//             row.style.display = 'none';
//         }
//     });
// }

// // Periodic timestamp update
// setInterval(() => {
//     document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
// }, 60000);










let ws = new WebSocket("ws://" + window.location.host + "/ws");
let chart;
let normalCount = 0;
let anomalyCount = 0;
let totalCount = 0;
let sessionCount = 0;

// Initialize chart
function initChart(initialNormal, initialAnomaly) {
    normalCount = initialNormal || 0;
    anomalyCount = initialAnomaly || 0;
    totalCount = normalCount + anomalyCount;

    let ctx = document.getElementById('logChart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Normal', 'Anomaly'],
            datasets: [{
                data: [normalCount, anomalyCount],
                backgroundColor: ['#28a745', '#dc3545'] // Use defined colors
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // Allow chart to fill container
            plugins: {
                legend: {
                    position: 'bottom', // Move legend to bottom
                    labels: {
                        color: 'var(--text-color-primary)' // Dynamic text color
                    }
                }
            }
        }
    });

    updateStatsAndChart();
}

// Update stats text and chart
function updateStatsAndChart() {
    animateCount('totalLogs', totalCount);
    animateCount('normalCount', normalCount);
    animateCount('anomalyCount', anomalyCount);
    animateCount('sessionCount', sessionCount);

    if (chart) {
        chart.data.datasets[0].data = [normalCount, anomalyCount];
        chart.update();
    }

    document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
}

// Animate a number smoothly
function animateCount(id, newCount) {
    let el = document.getElementById(id);
    if (!el) return; // Add null check
    let current = parseInt(el.textContent) || 0;
    let diff = newCount - current;
    if (diff === 0) { // No animation if count is same
        el.textContent = newCount;
        return;
    }
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

// WebSocket handling
ws.onopen = () => {
    // sessionCount++; // sessionCount is updated by server message
    updateStatsAndChart();
};

ws.onclose = () => {
    // sessionCount = Math.max(0, sessionCount - 1); // sessionCount is updated by server message
    updateStatsAndChart();
};

ws.onmessage = function(event) {
    let msg = JSON.parse(event.data);
    if (msg.type === "session_update") {
        sessionCount = msg.count;
    } else if (msg.type === "log") {
        addLogRow(msg.data);
    } else if (msg.type === "alert") {
        addAlertRow(msg.data);
    }
    updateStatsAndChart(); // Update chart and stats after every message
};

function addLogRow(data) {
    let table = document.getElementById("logsTable");
    let row = table.insertRow(-1);  // append at bottom
    row.className = 'fade-in';

    let timestamp = data.timestamp || '-';
    let labelText = (data.label || '').toLowerCase().trim(); // Use pre-processed label
    let log = data.log || '-';

    row.innerHTML = `<td>${timestamp}</td><td>${labelText}</td><td>${log}</td>`;

    if (labelText === 'anomaly') {
        row.classList.add('log-anomaly');
        anomalyCount++;
    } else if (labelText === 'normal') {
        row.classList.add('log-normal');
        normalCount++;
    }

    totalCount++;
    // updateStatsAndChart(); // Called by ws.onmessage
    autoScroll('logsContainer');
}

// Add alert row
function addAlertRow(data) {
    let container = document.getElementById("alertsContainer");
    let div = document.createElement('div');
    div.className = 'alert-critical fade-in';
    div.innerHTML = `<strong>Critical:</strong> ${data.advice}<br><small>Ref Log: ${data.log}</small>`;
    container.appendChild(div);
    autoScroll('alertsContainer');
}

// Auto-scroll
function autoScroll(containerId) {
    let container = document.getElementById(containerId);
    if (container) { // Check if container exists
        container.scrollTop = container.scrollHeight;
    }
}

// Toggle dark mode
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    // Update chart legend color immediately on toggle
    if (chart) {
        const root = document.documentElement;
        const currentTextColor = getComputedStyle(root).getPropertyValue('--text-color-primary');
        chart.options.plugins.legend.labels.color = currentTextColor;
        chart.update();
    }
}

// Filter logs
function filterLogs(type) {
    let rows = document.querySelectorAll("#logsTable tr");
    rows.forEach(row => {
        // Ensure row.cells[1] exists before accessing textContent
        if (row.cells.length > 1) {
            if (type === 'all' || row.cells[1].textContent === type) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        }
    });
}

// Periodic timestamp update
setInterval(() => {
    document.getElementById("lastUpdated").textContent = new Date().toLocaleString();
}, 60000);