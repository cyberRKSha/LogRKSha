import * as api from './api.js';

let historicalChart;
let widgetCharts = {};
let liveSparklineChart;
const sparklineData = {
    labels: Array(50).fill(''),
    normal: Array(50).fill(0),
    anomaly: Array(50).fill(0)
};
let recentLogs = [];

export async function initHistoricalChart() {
    try {
        const data = await api.fetchHistoricalTrends();

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

export async function createTopNChart(canvasId, field) {
    const widgetContainer = document.getElementById(canvasId).parentElement;
    try {
        const data = await api.fetchTopN(field);
        if (!data || data.length === 0) {
            // Optional: Show a message if no data
            widgetContainer.innerHTML = `<div class="widget-no-data">No anomalous ${field} data to display.</div>`;
            return;
        }

        const ctx = document.getElementById(canvasId).getContext('2d');

        const gradient = ctx.createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, 'rgba(90, 90, 203, 0.8)');   // --button-primary-dark, semi-transparent
        gradient.addColorStop(1, 'rgba(90, 90, 203, 0.3)');

        const chartConfig = {
            type: 'bar',
            data: {
                labels: data.map(d => d.item),
                datasets: [{
                    label: 'Count',
                    data: data.map(d => d.count),
                    backgroundColor: gradient,
                    borderColor: 'rgba(90, 90, 203, 1)',
                    borderWidth: 1,
                    borderRadius: 5
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(26, 26, 46, 0.9)', // --primary-bg-dark
                        titleColor: '#e0e0e0', // --text-color-primary-dark
                        bodyColor: '#bbb', // --text-color-secondary-dark
                        borderColor: '#3a3a5e', // --border-dark
                        borderWidth: 1,
                        padding: 10,
                        callbacks: {
                            label: function(context) {
                                return ` Count: ${context.raw}`;
                            }
                        }
                    }
                },
                scales: {
                    x: { 
                        ticks: { color: 'var(--text-color-secondary)', beginAtZero: true, precision: 0 },
                        grid: { color: 'var(--border-color)' }
                    },
                    y: { 
                        ticks: { color: 'var(--text-color-primary)' },
                        grid: { display: false }
                    }
                }
            }
        };

        widgetCharts[canvasId] = new Chart(ctx, chartConfig);

    } catch (error) {
        widgetContainer.innerHTML = `<div class="widget-no-data">Error loading chart data.</div>`;
        console.error(`Failed to load chart for ${field}:`, error);
    }
}

export function updateAllChartColors() {
    const theme = getComputedStyle(document.body);
    const textColorPrimary = theme.getPropertyValue('--text-color-primary').trim();
    const textColorSecondary = theme.getPropertyValue('--text-color-secondary').trim();
    const borderColor = theme.getPropertyValue('--border-color').trim();
    const tooltipBgColor = theme.getPropertyValue('--primary-bg-dark').trim();

    const updateChart = (chart) => {
        if (!chart) return;
        
        if (chart.options.scales && chart.options.scales.x && chart.options.scales.y) {
            chart.options.scales.x.ticks.color = textColorSecondary;
            chart.options.scales.y.ticks.color = textColorPrimary;
            chart.options.scales.x.grid.color = borderColor;
            chart.options.scales.y.grid.color = borderColor; // Also good to update the Y grid color
        }
        
        if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.display) {
            chart.options.plugins.legend.labels.color = textColorPrimary;
        }
        
        if(chart.options.plugins.tooltip) {
            chart.options.plugins.tooltip.backgroundColor = tooltipBgColor;
            chart.options.plugins.tooltip.titleColor = textColorPrimary;
            chart.options.plugins.tooltip.bodyColor = textColorSecondary;
            chart.options.plugins.tooltip.borderColor = borderColor;
        }
        chart.update();
    };

    updateChart(historicalChart);
    Object.values(widgetCharts).forEach(updateChart);
}

export function initLiveSparkline() {
    const canvas = document.getElementById('liveSparklineChart');
    if (!canvas) return; // Exit if the element isn't there
    const ctx = canvas.getContext('2d');

    // Create semi-transparent gradients for the area fill
    const normalGradient = ctx.createLinearGradient(0, 0, 0, 60);
    normalGradient.addColorStop(0, 'rgba(40, 167, 69, 0.4)');
    normalGradient.addColorStop(1, 'rgba(40, 167, 69, 0)');

    const anomalyGradient = ctx.createLinearGradient(0, 0, 0, 60);
    anomalyGradient.addColorStop(0, 'rgba(220, 53, 69, 0.4)');
    anomalyGradient.addColorStop(1, 'rgba(220, 53, 69, 0)');

    liveSparklineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: sparklineData.labels,
            datasets: [
                {
                    label: 'Normal',
                    data: sparklineData.normal,
                    borderColor: '#28a745', // Solid Green
                    backgroundColor: normalGradient,
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 0, // Hide points
                },
                {
                    label: 'Anomaly',
                    data: sparklineData.anomaly,
                    borderColor: '#dc3545', // Solid Red
                    backgroundColor: anomalyGradient,
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 0, // Hide points
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }, // We have a custom HTML legend
                tooltip: { enabled: false }, // Sparklines don't usually have tooltips
            },
            scales: {
                x: { display: false }, // Hide X-axis
                y: { display: false }  // Hide Y-axis
            }
        }
    });
}

export function updateLiveSparkline(label) {
    const now = Date.now();

    // Add new log with a timestamp
    recentLogs.push({ timestamp: now, label: label });

    // Remove logs older than 5 seconds
    recentLogs = recentLogs.filter(log => now - log.timestamp < 5000);

    // Calculate logs per second (LPS) over the last 5 seconds
    const normalLPS = (recentLogs.filter(l => l.label === 'normal').length / 5).toFixed(1);
    const anomalyLPS = (recentLogs.filter(l => l.label === 'anomaly').length / 5).toFixed(1);

    // Update the numerical displays
    const normalLpsEl = document.getElementById('normal-lps');
    const anomalyLpsEl = document.getElementById('anomaly-lps');
    if (normalLpsEl) normalLpsEl.textContent = normalLPS;
    if (anomalyLpsEl) anomalyLpsEl.textContent = anomalyLPS;

    // Shift data for the chart display
    sparklineData.normal.shift();
    sparklineData.anomaly.shift();

    // Add a smoothed value to the chart (average logs in the last second)
    const logsInLastSecond = recentLogs.filter(log => now - log.timestamp < 1000);
    const normalInLastSec = logsInLastSecond.filter(l => l.label === 'normal').length;
    const anomalyInLastSec = logsInLastSecond.filter(l => l.label === 'anomaly').length;
    
    sparklineData.normal.push(normalInLastSec);
    sparklineData.anomaly.push(anomalyInLastSec);
    
    // Update the chart itself
    if(liveSparklineChart) liveSparklineChart.update('none'); // 'none' for a smoother animation
}



export async function createDetectionMethodChart() {
    const canvasId = 'detectionMethodChart';
    const canvas = document.getElementById(canvasId);
    if (!canvas) return; // Exit if the canvas element doesn't exist

    const widgetContainer = canvas.parentElement;

    try {
        const data = await api.fetchDetectionMethodStats();

        if (Object.keys(data).length === 0) {
            widgetContainer.innerHTML = `<div class="widget-no-data">No anomaly detection data available yet.</div>`;
            return;
        }

        const ctx = canvas.getContext('2d');
        const labels = Object.keys(data);
        const counts = Object.values(data);
        
        // Define some nice colors for the chart
        const backgroundColors = [
            'rgba(90, 90, 203, 0.7)',   // A nice purple for Supervised
            'rgba(253, 126, 20, 0.7)', // Orange for Unsupervised
            'rgba(220, 53, 69, 0.7)',  // Red for Sequential
            'rgba(108, 117, 125, 0.7)' // Grey for Other
        ];

        widgetCharts[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Detection Count',
                    data: counts,
                    backgroundColor: backgroundColors,
                    borderColor: 'var(--secondary-bg)', // Use CSS variable for border
                    borderWidth: 3,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: 'var(--text-color-primary)',
                            padding: 20,
                            font: {
                                size: 14
                            }
                        }
                    }
                }
            }
        });

    } catch (error) {
        widgetContainer.innerHTML = `<div class="widget-no-data">Error loading chart data.</div>`;
        console.error("Failed to load detection method chart:", error);
    }
}

export async function updateTopNChart(canvasId, field) {
    const chart = widgetCharts[canvasId];
    if (!chart) return; // Do nothing if the chart doesn't exist

    try {
        const data = await api.fetchTopN(field);
        if (data && data.length > 0) {
            chart.data.labels = data.map(d => d.item);
            chart.data.datasets[0].data = data.map(d => d.count);
            chart.update(); // This is the magic call to refresh the chart
        }
    } catch (error) {
        console.error(`Failed to update chart for ${field}:`, error);
    }
}

export async function updateDetectionMethodChart() {
    const canvasId = 'detectionMethodChart';
    const chart = widgetCharts[canvasId];
    if (!chart) return;

    try {
        const data = await api.fetchDetectionMethodStats();
        if (Object.keys(data).length > 0) {
            chart.data.labels = Object.keys(data);
            chart.data.datasets[0].data = Object.values(data);
            chart.update();
        }
    } catch (error) {
        console.error("Failed to update detection method chart:", error);
    }
}