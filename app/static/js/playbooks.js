// static/js/playbooks.js
import { applyTheme } from './theme.js';

// A simple toast notification function (can be expanded)
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideOutFadeOut 0.5s ease forwards';
        setTimeout(() => toast.remove(), 500);
    }, 5000);
}

// --- API Calls ---
async function fetchPlaybooks() {
    const response = await fetch('/api/playbooks');
    return await response.json();
}

async function savePlaybook(playbookData, id = null) {
    const url = id ? `/api/playbooks/${id}` : '/api/playbooks';
    const method = id ? 'PUT' : 'POST';
    const response = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(playbookData)
    });
    return await response.json();
}

async function deletePlaybook(id) {
    const response = await fetch(`/api/playbooks/${id}`, { method: 'DELETE' });
    return await response.json();
}

async function updatePlaybookStatus(id, playbookData) {
    const response = await fetch(`/api/playbooks/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(playbookData)
    });
    return await response.json();
}

// --- UI Rendering ---
function renderPlaybooks(playbooks) {
    const tableBody = document.getElementById('playbooks-table-body');
    tableBody.innerHTML = '';
    if (playbooks.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="3" style="text-align:center;">No playbooks found. Create one to get started!</td></tr>';
        return;
    }

    playbooks.forEach(pb => {
        const row = tableBody.insertRow();
        row.innerHTML = `
            <td>${pb.name}</td>
            <td>
                <label class="switch">
                    <input type="checkbox" class="status-toggle" data-id="${pb.id}" ${pb.is_active ? 'checked' : ''}>
                    <span class="slider round"></span>
                </label>
            </td>
            <td class="actions-cell">
                <button class="action-btn edit-btn" data-id="${pb.id}">Edit</button>
                <button class="action-btn delete-btn" data-id="${pb.id}">Delete</button>
            </td>
        `;
    });

    // Add event listeners after rendering
    document.querySelectorAll('.edit-btn').forEach(btn => btn.addEventListener('click', handleEditClick));
    document.querySelectorAll('.delete-btn').forEach(btn => btn.addEventListener('click', handleDeleteClick));
    document.querySelectorAll('.status-toggle').forEach(toggle => toggle.addEventListener('change', handleStatusToggle));
}

// --- Modal and Form Handling ---
const modal = document.getElementById('playbook-modal');
const form = document.getElementById('playbook-form');
const modalTitle = document.getElementById('modal-title');
const playbookIdInput = document.getElementById('playbook-id');

function openModal(playbook = null) {
    form.reset();
    if (playbook) {
        modalTitle.textContent = 'Edit Playbook';
        playbookIdInput.value = playbook.id;
        document.getElementById('playbook-name').value = playbook.name;
        document.getElementById('playbook-triggers').value = JSON.stringify(playbook.trigger_conditions, null, 2);
        document.getElementById('playbook-actions').value = JSON.stringify(playbook.actions, null, 2);
    } else {
        modalTitle.textContent = 'Create New Playbook';
        playbookIdInput.value = '';
    }
    modal.style.display = 'flex';
}

function closeModal() {
    modal.style.display = 'none';
}

async function handleFormSubmit(event) {
    event.preventDefault();
    const id = playbookIdInput.value;
    try {
        const playbooks = await fetchPlaybooks();
        const originalPlaybook = playbooks.find(pb => pb.id == id);
        // If we are editing, use the original status. If creating, default to true.
        const isActiveStatus = originalPlaybook ? originalPlaybook.is_active : true;
        const playbookData = {
            name: document.getElementById('playbook-name').value,
            trigger_conditions: JSON.parse(document.getElementById('playbook-triggers').value),
            actions: JSON.parse(document.getElementById('playbook-actions').value),
            is_active: isActiveStatus // Default to active, can be toggled later
        };
        await savePlaybook(playbookData, id);
        showToast(`Playbook ${id ? 'updated' : 'created'} successfully!`, 'success');
        closeModal();
        loadAndRenderPlaybooks();
    } catch (error) {
        showToast('Error saving playbook. Please check if your JSON is valid.', 'error');
        console.error('Save error:', error);
    }
}

// --- Event Handlers ---
async function handleEditClick(event) {
    const id = event.target.dataset.id;
    const playbooks = await fetchPlaybooks();
    const playbook = playbooks.find(pb => pb.id == id);
    if (playbook) {
        openModal(playbook);
    }
}

async function handleDeleteClick(event) {
    const id = event.target.dataset.id;
    if (confirm('Are you sure you want to delete this playbook?')) {
        await deletePlaybook(id);
        showToast('Playbook deleted.', 'success');
        loadAndRenderPlaybooks();
    }
}

async function handleStatusToggle(event) {
    const id = event.target.dataset.id;
    const is_active = event.target.checked;

    const playbooks = await fetchPlaybooks();
    const playbookToUpdate = playbooks.find(pb => pb.id == id);
    if (!playbookToUpdate) {
        showToast('Error: Could not find playbook to update.', 'error');
        return;
    }

    // Update only the is_active field
    playbookToUpdate.is_active = is_active;

    // Send the complete, updated object to the backend
    try {
        await updatePlaybookStatus(id, playbookToUpdate);
        showToast(`Playbook status updated.`, 'success');
    } catch (error) {
        showToast('Failed to update status.', 'error');
        // Revert the checkbox on failure
        event.target.checked = !is_active;
    }
}

async function loadAndRenderPlaybooks() {
    const playbooks = await fetchPlaybooks();
    renderPlaybooks(playbooks);
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    applyTheme();
    document.getElementById('create-playbook-btn').addEventListener('click', () => openModal());
    document.getElementById('modal-close-btn').addEventListener('click', closeModal);
    document.getElementById('back-to-dashboard-btn').addEventListener('click', () => {
        window.location.href = '/';
    });
    form.addEventListener('submit', handleFormSubmit);

    // AI Generation Handler
    document.getElementById('generate-btn')?.addEventListener('click', async () => {
        const promptInput = document.getElementById('ai-prompt');
        const generateBtn = document.getElementById('generate-btn');
        const prompt = promptInput.value.trim();

        if (!prompt) {
            showToast('Please enter a description for the playbook.', 'info');
            return;
        }

        const originalText = generateBtn.textContent;
        generateBtn.innerHTML = '<span class="spinner" style="width: 12px; height: 12px; border: 2px solid white; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; display: inline-block;"></span> Generating...';
        generateBtn.disabled = true;

        try {
            const response = await fetch('/api/playbooks/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: prompt })
            });

            if (response.ok) {
                const data = await response.json();
                document.getElementById('playbook-triggers').value = JSON.stringify(data.trigger_conditions, null, 2);
                document.getElementById('playbook-actions').value = JSON.stringify(data.actions, null, 2);
                showToast('Playbook configuration generated!', 'success');
            } else {
                const error = await response.json();
                showToast(error.detail || 'Failed to generate playbook', 'error');
            }
        } catch (err) {
            console.error('Generation error:', err);
            showToast('Failed to connect to AI service', 'error');
        } finally {
            generateBtn.innerHTML = originalText;
            generateBtn.disabled = false;
        }
    });

    loadAndRenderPlaybooks();
});