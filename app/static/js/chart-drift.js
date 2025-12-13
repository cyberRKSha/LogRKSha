// app/static/js/chart-drift.js
async function initDriftChart() {
    const ctx = document.getElementById('modelPerformanceChart');
    if (!ctx) return;

    try {
        const response = await fetch('/api/stats/model_drift');
        const data = await response.json();

        if (!data || data.length === 0) {
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['No Data'],
                    datasets: [{ label: 'Accuracy', data: [0] }]
                },
                options: { plugins: { title: { display: true, text: 'No model updates yet' } } }
            });
            // Reset metrics
            ['acc', 'prec', 'rec', 'f1'].forEach(k => document.getElementById(`metric-${k}`).textContent = '--');
            return;
        }

        // --- Populate Metrics Stats (Latest) ---
        const latest = data[data.length - 1]; // Get last entry
        document.getElementById('modelLastUpdated').textContent = `Use: ${latest.timestamp}`;

        const fmt = val => (val * 100).toFixed(1) + '%';

        document.getElementById('metric-acc').textContent = fmt(latest.accuracy);
        document.getElementById('metric-prec').textContent = fmt(latest.precision);
        document.getElementById('metric-rec').textContent = fmt(latest.recall);
        document.getElementById('metric-f1').textContent = fmt(latest.f1_score);

        // --- Render Chart ---
        const labels = data.map(d => d.timestamp);

        const accuracy = data.map(d => d.accuracy);
        const precision = data.map(d => d.precision);
        const recall = data.map(d => d.recall);
        const f1 = data.map(d => d.f1_score);

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Accuracy',
                        data: accuracy,
                        borderColor: '#10b981', // green-500
                        backgroundColor: 'rgba(16, 185, 129, 0.05)',
                        tension: 0.3, borderWidth: 2, pointRadius: 3
                    },
                    {
                        label: 'Precision',
                        data: precision,
                        borderColor: '#3b82f6', // blue-500
                        backgroundColor: 'rgba(59, 130, 246, 0.05)',
                        tension: 0.3, borderWidth: 2, pointRadius: 3,
                        hidden: true // Hide by default to reduce clutter, clickable to show
                    },
                    {
                        label: 'Recall',
                        data: recall,
                        borderColor: '#8b5cf6', // violet-500
                        backgroundColor: 'rgba(139, 92, 246, 0.05)',
                        tension: 0.3, borderWidth: 2, pointRadius: 3,
                        hidden: true
                    },
                    {
                        label: 'F1 Score',
                        data: f1,
                        borderColor: '#f59e0b', // amber-500
                        backgroundColor: 'rgba(245, 158, 11, 0.05)',
                        tension: 0.3, borderWidth: 2, pointRadius: 3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 3, // Width to height ratio (3:1) - prevents stretching
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                layout: {
                    padding: {
                        top: 20,
                        bottom: 10,
                        left: 10,
                        right: 10
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        align: 'center',
                        labels: {
                            color: '#9ca3af',
                            usePointStyle: true,
                            pointStyle: 'circle', // Dot style for legend
                            boxWidth: 8,
                            boxHeight: 8,
                            padding: 20,
                            font: {
                                size: 12,
                                weight: 500
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(17, 24, 39, 0.95)',
                        titleColor: '#f9fafb',
                        bodyColor: '#d1d5db',
                        borderColor: 'rgba(99, 102, 241, 0.3)',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: true,
                        boxWidth: 10,
                        boxHeight: 10,
                        usePointStyle: true,
                        callbacks: {
                            label: context => `${context.dataset.label}: ${(context.raw * 100).toFixed(1)}%`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1.05,
                        grid: { color: 'rgba(75, 85, 99, 0.15)' },
                        ticks: {
                            color: '#9ca3af',
                            padding: 10,
                            callback: value => (value * 100).toFixed(0) + '%'
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#9ca3af',
                            maxTicksLimit: 8,
                            padding: 8
                        }
                    }
                }
            }
        });

    } catch (error) {
        console.error("Error loading drift chart:", error);
    }
}

document.addEventListener('DOMContentLoaded', initDriftChart);
