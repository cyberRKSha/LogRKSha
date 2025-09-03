// static/js/api.js

export async function fetchTrainingStats() {
    const response = await fetch('/api/training_stats');
    return await response.json();
}

export async function fetchHistoricalTrends() {
    const response = await fetch('/api/historical-trends', { cache: 'no-store' });
    return await response.json();
}

export async function fetchTopN(field) {
    const response = await fetch(`/api/stats/top_n?field=${field}`);
    return await response.json();
}

export async function searchLogs(searchCriteria) {
    const response = await fetch('/api/search_logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchCriteria)
    });
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json();
}

export async function postRetrainModel() {
    const response = await fetch('/api/model/retrain', { method: 'POST' });
    if (!response.ok) throw new Error('Failed to start model retraining');
    return await response.json();
}

export async function fetchRetrainStatus() {
    const response = await fetch(`/api/model/retrain/status`);
    return await response.json();
}

export async function fetchInitialAnomalies() {
    const response = await fetch('/api/alerts');
    return await response.json();
}

export async function postAlertStatusUpdate(alertId, newStatus) {
    const response = await fetch(`/api/alerts/${alertId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
    });
    if (!response.ok) throw new Error('Failed to update alert status')
    return await response.json();
}

export async function fetchMonitoringStatus() {
    const response = await fetch('/api/monitoring/status');
    return await response.json();
}

export async function postMonitoringToggle(newStatus) {
    const response = await fetch('/api/monitoring/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: newStatus })
    });
    if (!response.ok) throw new Error('Failed to toggle monitoring');
    return await response.json();
}

export async function fetchLogContext(timestamp) {
    const response = await fetch(`/api/logs/context?timestamp=${encodeURIComponent(timestamp)}`);
    return await response.json();
}

export async function fetchLogExplanation(logId) {
    const response = await fetch(`/api/logs/${logId}/explain`);
    if (!response.ok) throw new Error('Failed to fetch log explanation');
    return await response.json();
}

export async function fetchAllAnomalies() {
    const response = await fetch('/api/anomalies/all');
    return await response.json();
}

export async function postPrepareClusters() {
    const response = await fetch('/api/review/prepare', { method: 'POST' });
    return await response.json();
}

export async function fetchPrepareStatus() {
    const response = await fetch('/api/review/prepare/status');
    return await response.json();
}

export async function fetchClusters(sortBy, sortOrder) {
    const response = await fetch(`/api/review/clusters?sort_by=${sortBy}&sort_order=${sortOrder}`);
    return await response.json();
}

export async function fetchNoise() {
    const response = await fetch('/api/review/noise');
    return await response.json();
}

export async function fetchPendingReviewLogs(sortBy) {
    let url = '/api/review/pending';
    if (sortBy) {
        url += `?sort_by=${sortBy}`;
    }
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch pending review logs');
    return await response.json();
}

export async function postReviewUpdates(updates) {
    const response = await fetch('/api/review/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
    });
    return await response.json();
}

export async function postClusterLabel(clusterId, newLabel) {
    const response = await fetch(`/api/review/clusters/${clusterId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_label: newLabel })
    });
    return await response.json();
}

export async function fetchClusterLogs(clusterId) {
    const response = await fetch(`/api/review/clusters/${clusterId}/logs`);
    return await response.json();
}

export async function fetchManualReviewLogs(sortBy, sortOrder) {
    const response = await fetch('/api/review/manual_logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sort_by: sortBy, sort_order: sortOrder })
    });
    return await response.json();
}

export async function fetchDetectionMethodStats() {
    const response = await fetch('/api/stats/detection_methods');
    return await response.json();
}

export async function fetchAnomalousIPLocations() {
    const response = await fetch('/api/stats/anomalous_ips_locations');
    if (!response.ok) {
        console.error("Failed to fetch IP locations. Is the GeoIP database configured?");
        return [];
    }
    return await response.json();
}