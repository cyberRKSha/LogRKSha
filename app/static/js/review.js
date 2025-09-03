import * as api from './api.js';
import * as utils from './utils.js';
import * as ui from './ui.js';

export function setupReviewListeners() {
    // Listener for the main button on the dashboard to open the page.
    // **Please check your HTML and use the correct ID here.**
    const openBtn = document.getElementById('openReviewPageBtn') || document.getElementById('reviewLogsBtn');
    if (openBtn) {
        openBtn.addEventListener('click', openReviewInterface);
    }
    
    // Listener for the "Back to Dashboard" button inside the review page
    const closeBtn = document.getElementById('close-review-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeReviewInterface);
    }

    // Add listeners for the tab buttons inside the review page
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => switchReviewTab(button.dataset.tab));
    });
    
    // Listener for the "Prepare" button inside the review page
    const prepareBtn = document.getElementById('prepare-clusters-btn');
    if (prepareBtn) {
        prepareBtn.addEventListener('click', prepareClusters);
    }

    document.getElementById('clusterSortBy')?.addEventListener('change', fetchAndRenderClusters);
}

function openReviewInterface() {
    document.querySelector('.dashboard-layout').style.display = 'none';
    document.getElementById('review-interface-container').style.display = 'block';
    // Automatically load the default tab's content
    fetchAndRenderClusters();
    fetchAndRenderNoiseLogs();
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

function closeReviewInterface() {
    document.getElementById('review-interface-container').style.display = 'none';
    document.querySelector('.dashboard-layout').style.display = 'block';
}

async function prepareClusters() {
    const btn = document.getElementById('prepare-clusters-btn');
    const originalText = btn.textContent;
    
    // --- ADD THIS ---
    btn.innerHTML = `<div class="spinner" style="width: 18px; height: 18px; border-width: 2px;"></div> Preparing...`;
    btn.disabled = true;

    ui.showToast('Starting log clustering process in the background...', 'info');
    try {
        const result = await api.postPrepareClusters();
        ui.showToast(result.message, 'info');
        // Start polling for the result
        pollPrepareStatus(); 
    } catch (error) {
        ui.showToast('Failed to start clustering process.', 'error');
        btn.innerHTML = 'Prepare Clusters';
        btn.disabled = false;
    } finally {
        // --- ADD THIS ---
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

function pollPrepareStatus() {
    let intervalId = setInterval(async () => {
        try {
            const status = await api.fetchPrepareStatus();

            if (status.status === 'completed' || status.status === 'failed') {
                clearInterval(intervalId); // Stop polling
                const btn = document.getElementById('prepare-clusters-btn');
                btn.innerHTML = 'Prepare Clusters';
                btn.disabled = false;

                if (status.status === 'completed') {
                    ui.showToast('Clustering complete! Refreshing view.', 'success');
                    // Refresh the view with the new clusters
                    fetchAndRenderClusters();
                    fetchAndRenderNoiseLogs();
                } else {
                    ui.showToast(status.message, 'error');
                }
            }
        } catch (error) {
            clearInterval(intervalId);
            ui.showToast('Failed to get clustering status.', 'error');
        }
    }, 2000); // Check every 2 seconds
}

async function fetchAndRenderClusters() {
    const clusterContainer = document.getElementById('cluster-container');
    clusterContainer.innerHTML = '<h4>Loading clusters...</h4>';
    const sortBy = document.getElementById('clusterSortBy').value;
    const sortOrder = (sortBy === 'confidence') ? 'asc' : 'desc';

    try {
        const clusters = await api.fetchClusters(sortBy, sortOrder);
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
                    <div class="cluster-representative-log">${utils.escapeHTML(cluster.representative_log)}</div>
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

async function openClusterDetailModal(clusterId) {
    const modal = document.getElementById('cluster-detail-modal');
    const title = document.getElementById('cluster-modal-title');
    const body = document.getElementById('cluster-modal-body');
    const closeBtn = document.getElementById('cluster-modal-close-btn');

    title.textContent = `Logs for ${clusterId}`;
    body.innerHTML = '<h4>Loading logs...</h4>';
    modal.style.display = 'flex';
    
    closeBtn.onclick = () => { modal.style.display = 'none'; };
    
    const logs = await api.fetchClusterLogs(clusterId);

    let tableRows = '';
    logs.forEach(log => {
        tableRows += `
            <tr>
                <td class="log-content">${utils.escapeHTML(log.content)}</td>
                <td>${log.risk_score.toFixed(2)}</td>
                <td>${utils.formatSequenceRisk(log.sequence_risk)}</td>
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

async function fetchAndRenderNoiseLogs() {
    const noiseContainer = document.getElementById('noise-container');
    noiseContainer.innerHTML = '<h4>Loading unclustered logs...</h4>';
    try {
        const noiseLogs = await api.fetchNoise();

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
                <div class="cluster-representative-log">${utils.escapeHTML(log.representative_log)}</div>
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

export function setupKeyboardShortcuts() {
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
            ui.showToast('Could not determine label.', 'error');
            return;
        }
    }

    button.textContent = 'Saving...';
    button.disabled = true;

    try {
        // This is the same API call as before
        const result = await api.postClusterLabel(clusterId, newLabel);
        if (result.status === 'ok') {
            ui.showToast(`Cluster ${clusterId} labeled successfully (${result.updated_count} logs).`, 'success');
            card.remove();
        } else { throw new Error(result.message); }
    } catch (error) {
        ui.showToast(`Failed to label cluster ${clusterId}.`, 'error');
        button.textContent = 'Save';
        button.disabled = false;
    }
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

async function fetchAndRenderManualLogs(sortBy, sortOrder) {
    const container = document.getElementById('manual-log-table-container');
    container.innerHTML = '<h4>Loading logs...</h4>';

    try {
        const entries = await api.fetchManualReviewLogs(sortBy, sortOrder);

        if (entries.length === 0) {
            container.innerHTML = '<h4>No pending logs to review.</h4>';
            return;
        }

        let tableRows = '';
        entries.forEach(entry => {
            const riskClass = utils.getRiskRowClass(entry.risk_score);
            tableRows += `
                <tr class="${riskClass}" data-log-id="${entry.id}">
                    <td>${new Date(entry.timestamp).toLocaleString()}</td>
                    <td>${entry.source}</td>
                    <td class="log-content">${utils.escapeHTML(entry.content)}</td>
                    <td>${entry.risk_score.toFixed(2)}</td>
                    <td>${utils.formatSequenceRisk(entry.sequence_risk)}</td>
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
        ui.showToast("No changes to save.", "info");
        return;
    }

    if (saveButtonElement) {
        saveButtonElement.textContent = 'Saving...';
        saveButtonElement.disabled = true;
    }

    try {
        const result = await api.postReviewUpdates(updates);
        if (result.status === 'ok') {
            ui.showToast(`Successfully updated ${result.updated_count} logs!`, 'success');
            
            ui.showToast('Refreshing clusters with remaining logs...', 'info');
            await prepareClusters();
            // Refresh the manual review table to show remaining logs
            loadManualReviewLogs();
        } else {
            throw new Error(result.message || "Unknown error saving reviews.");
        }
    } catch (error) {
        ui.showToast("Failed to save reviews.", "error");
        if (saveButtonElement) {
            saveButtonElement.textContent = 'Save Changes';
            saveButtonElement.disabled = false;
        }
    } finally {
        // The button will disappear on successful refresh, so no need to re-enable
    }
}