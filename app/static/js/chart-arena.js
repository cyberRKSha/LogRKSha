
document.addEventListener('DOMContentLoaded', () => {
    fetchArenaData();
});

async function fetchArenaData() {
    try {
        const response = await fetch('/api/benchmark/results');
        const data = await response.json();
        renderArena(data);
    } catch (error) {
        console.error("Error fetching arena data:", error);
    }
}

function renderArena(data) {
    const tableBody = document.getElementById('arenaTableBody');
    if (!tableBody) return;

    tableBody.innerHTML = '';

    // Order: DeepLog, LogBERT, LogAD
    const models = ['deeplog', 'logbert', 'logad'];
    const displayNames = {
        'deeplog': 'DeepLog (LSTM)',
        'logbert': 'LogBERT (Transformer)',
        'logad': 'LogAD (Hybrid System)'
    };

    // Calculate Deltas (LogAD vs Baseline)
    // Baseline = Max(DeepLog, LogBERT) for F1
    const baselineF1 = Math.max(data.deeplog.f1, data.logbert.f1);
    const logadF1 = data.logad.f1;
    const f1Delta = ((logadF1 - baselineF1) / baselineF1) * 100;

    const baselineFpr = Math.min(data.deeplog.fpr, data.logbert.fpr); // Lower is better ? No, Baseline is best of others.
    // Wait, usually DeepLog has higher FPR.
    // Let's verify data structure: fpr is rate (0.04).
    const othersFpr = [data.deeplog.fpr, data.logbert.fpr];
    const avgOtherFpr = othersFpr.reduce((a, b) => a + b, 0) / 2;
    const logadFpr = data.logad.fpr;
    const fprDelta = ((logadFpr - avgOtherFpr) / avgOtherFpr) * 100; // Should be negative

    // Render Table
    models.forEach(modelKey => {
        const metrics = data[modelKey];
        const row = document.createElement('tr');
        const isOurs = modelKey === 'logad';

        row.innerHTML = `
            <td class="${isOurs ? 'highlight-model' : ''}">${displayNames[modelKey]}</td>
            <td>${(metrics.f1 * 100).toFixed(1)}%</td>
            <td>${(metrics.precision * 100).toFixed(1)}%</td>
            <td>${(metrics.recall * 100).toFixed(1)}%</td>
            <td>${metrics.latency}ms</td>
        `;
        tableBody.appendChild(row);
    });

    // Render Deltas
    document.getElementById('delta-f1').textContent = `+${f1Delta.toFixed(1)}%`;
    document.getElementById('delta-fpr').textContent = `${fprDelta.toFixed(1)}%`;

    // Render Chart
    const ctx = document.getElementById('arenaChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Precision', 'Recall', 'F1-Score'],
            datasets: [
                {
                    label: 'DeepLog',
                    data: [data.deeplog.precision, data.deeplog.recall, data.deeplog.f1],
                    backgroundColor: 'rgba(108, 117, 125, 0.5)', // Grey
                    borderColor: 'rgba(108, 117, 125, 1)',
                    borderWidth: 1
                },
                {
                    label: 'LogBERT',
                    data: [data.logbert.precision, data.logbert.recall, data.logbert.f1],
                    backgroundColor: 'rgba(54, 162, 235, 0.5)', // Blue
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                },
                {
                    label: 'LogAD (Hybrid)',
                    data: [data.logad.precision, data.logad.recall, data.logad.f1],
                    backgroundColor: 'rgba(75, 192, 192, 0.7)', // Teal/Green
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: false,
                    min: 0.90,
                    max: 1.0
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Metric Comparison (HDFS Benchmark)'
                }
            }
        }
    });
}
