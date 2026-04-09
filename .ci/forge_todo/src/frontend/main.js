const state = {
    tasks: [],
    stats: null,
    filter: 'all',
    search: '',
    selectedTaskId: null,
};

const elements = {};

document.addEventListener('DOMContentLoaded', async () => {
    cacheElements();
    bindEvents();
    syncFilterButtons();
    await refreshAll();
});

function cacheElements() {
    Object.assign(elements, {
        taskList: document.getElementById('taskList'),
        emptyState: document.getElementById('emptyState'),
        detailsEmpty: document.getElementById('detailsEmpty'),
        detailsForm: document.getElementById('detailsForm'),
        taskId: document.getElementById('taskId'),
        searchInput: document.getElementById('searchInput'),
        taskListTitle: document.getElementById('taskListTitle'),
        taskCountBadge: document.getElementById('taskCountBadge'),
        toast: document.getElementById('toast'),
        totalCount: document.getElementById('totalCount'),
        activeCount: document.getElementById('activeCount'),
        doneCount: document.getElementById('doneCount'),
        overdueCount: document.getElementById('overdueCount'),
        completionRate: document.getElementById('completionRate'),
        progressFill: document.getElementById('progressFill'),
        highCount: document.getElementById('highCount'),
        mediumCount: document.getElementById('mediumCount'),
        lowCount: document.getElementById('lowCount'),
        filterGroup: document.getElementById('filterGroup'),
        newTaskTitle: document.getElementById('newTaskTitle'),
        newTaskPriority: document.getElementById('newTaskPriority'),
        newTaskDueDate: document.getElementById('newTaskDueDate'),
        newTaskTags: document.getElementById('newTaskTags'),
        editTitle: document.getElementById('editTitle'),
        editDescription: document.getElementById('editDescription'),
        editPriority: document.getElementById('editPriority'),
        editDueDate: document.getElementById('editDueDate'),
        editTags: document.getElementById('editTags'),
        editCompleted: document.getElementById('editCompleted'),
        importBtn: document.getElementById('importBtn'),
        exportBtn: document.getElementById('exportBtn'),
        duplicateTaskBtn: document.getElementById('duplicateTaskBtn'),
        storagePath: document.getElementById('storagePath'),
        storageTaskCount: document.getElementById('storageTaskCount'),
    });
}

function bindEvents() {
    document.getElementById('addTaskBtn').addEventListener('click', createTask);
    document.getElementById('newTaskBtn').addEventListener('click', () => elements.newTaskTitle.focus());
    document.getElementById('importBtn').addEventListener('click', importTasks);
    document.getElementById('exportBtn').addEventListener('click', exportTasks);
    document.getElementById('seedDemoBtn').addEventListener('click', seedDemoTasks);
    document.getElementById('clearCompletedBtn').addEventListener('click', clearCompletedTasks);
    document.getElementById('deleteTaskBtn').addEventListener('click', deleteSelectedTask);
    document.getElementById('duplicateTaskBtn').addEventListener('click', duplicateSelectedTask);
    elements.searchInput.addEventListener('input', debounce(async (event) => {
        state.search = event.target.value.trim();
        await loadTasks();
    }, 180));
    elements.filterGroup.addEventListener('click', async (event) => {
        const button = event.target.closest('[data-filter]');
        if (!button) return;
        state.filter = button.dataset.filter;
        syncFilterButtons();
        await loadTasks();
    });
    elements.detailsForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        await saveSelectedTask();
    });
    elements.taskList.addEventListener('click', async (event) => {
        const action = event.target.dataset.action;
        const taskId = event.target.closest('[data-task-id]')?.dataset.taskId;
        if (!taskId) return;
        if (action === 'toggle') {
            const task = state.tasks.find((item) => item.id === taskId);
            if (task) {
                await setTaskCompleted(taskId, !task.completed);
            }
            return;
        }
        if (action === 'delete') {
            await deleteTask(taskId);
            return;
        }
        selectTask(taskId);
    });
    elements.newTaskTitle.addEventListener('keydown', async (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            await createTask();
        }
    });
}

async function refreshAll() {
    await Promise.all([loadTasks(), loadStats()]);
    await loadStorageInfo();
}

async function invoke(command, payload = {}) {
    return window.__forge__.invoke(command, payload);
}

function currentQuery() {
    return state.filter === 'high'
        ? { status: 'all', priority: 'high', search: state.search }
        : { status: state.filter, priority: 'all', search: state.search };
}

async function loadTasks() {
    try {
        state.tasks = await invoke('list_tasks', currentQuery());
        if (state.selectedTaskId && !state.tasks.some((task) => task.id === state.selectedTaskId)) {
            state.selectedTaskId = null;
        }
        renderTasks();
        renderDetails();
    } catch (error) {
        showToast(`Failed to load tasks: ${error.message}`, 'error');
    }
}

async function loadStats() {
    try {
        state.stats = await invoke('get_task_stats');
        renderStats();
    } catch (error) {
        showToast(`Failed to load stats: ${error.message}`, 'error');
    }
}

async function loadStorageInfo() {
    try {
        const info = await invoke('get_storage_info');
        elements.storageTaskCount.textContent = `${info.task_count} task${info.task_count === 1 ? '' : 's'} persisted`;
        elements.storagePath.textContent = info.path;
        elements.storagePath.title = info.path;
    } catch (error) {
        elements.storageTaskCount.textContent = 'Storage unavailable';
        elements.storagePath.textContent = 'Unable to load storage details';
    }
}

function renderTasks() {
    const filterTitles = {
        all: 'All tasks',
        active: 'Active tasks',
        completed: 'Completed tasks',
        high: 'High priority tasks',
    };
    elements.taskListTitle.textContent = filterTitles[state.filter] || 'Tasks';
    elements.taskCountBadge.textContent = `${state.tasks.length} item${state.tasks.length === 1 ? '' : 's'}`;

    if (!state.tasks.length) {
        elements.taskList.innerHTML = '';
        elements.emptyState.classList.remove('hidden');
        return;
    }

    elements.emptyState.classList.add('hidden');
    elements.taskList.innerHTML = state.tasks.map((task) => `
        <article class="task-card ${task.completed ? 'completed' : ''} ${state.selectedTaskId === task.id ? 'selected' : ''}" data-task-id="${task.id}">
            <button class="check-btn ${task.completed ? 'done' : ''}" data-action="toggle" aria-label="Toggle task">
                ${task.completed ? '✓' : ''}
            </button>
            <div class="task-body">
                <div class="task-topline">
                    <h4>${escapeHtml(task.title)}</h4>
                    <span class="priority-pill ${task.priority}">${task.priority}</span>
                </div>
                <p class="task-desc">${escapeHtml(task.description || 'No description yet.')}</p>
                <div class="task-meta">
                    ${task.due_date ? `<span>Due ${task.due_date}</span>` : '<span>No due date</span>'}
                    <span>Updated ${formatDateTime(task.updated_at)}</span>
                </div>
                <div class="tag-row">
                    ${(task.tags || []).map((tag) => `<span class="tag">#${escapeHtml(tag)}</span>`).join('')}
                </div>
            </div>
            <button class="icon-delete" data-action="delete" aria-label="Delete task">✕</button>
        </article>
    `).join('');
}

function renderDetails() {
    const selected = state.tasks.find((task) => task.id === state.selectedTaskId);
    if (!selected) {
        elements.detailsEmpty.classList.remove('hidden');
        elements.detailsForm.classList.add('hidden');
        return;
    }
    elements.detailsEmpty.classList.add('hidden');
    elements.detailsForm.classList.remove('hidden');
    elements.taskId.value = selected.id;
    elements.editTitle.value = selected.title;
    elements.editDescription.value = selected.description || '';
    elements.editPriority.value = selected.priority;
    elements.editDueDate.value = selected.due_date || '';
    elements.editTags.value = (selected.tags || []).join(', ');
    elements.editCompleted.checked = Boolean(selected.completed);
}

function renderStats() {
    if (!state.stats) return;
    elements.totalCount.textContent = state.stats.total;
    elements.activeCount.textContent = state.stats.active;
    elements.doneCount.textContent = state.stats.completed;
    elements.overdueCount.textContent = state.stats.overdue;
    elements.completionRate.textContent = `${state.stats.completion_rate}%`;
    elements.progressFill.style.width = `${state.stats.completion_rate}%`;
    elements.highCount.textContent = state.stats.priorities.high;
    elements.mediumCount.textContent = state.stats.priorities.medium;
    elements.lowCount.textContent = state.stats.priorities.low;
}

function selectTask(taskId) {
    state.selectedTaskId = taskId;
    renderTasks();
    renderDetails();
}

async function createTask() {
    const title = elements.newTaskTitle.value.trim();
    if (!title) {
        showToast('Enter a task title first.', 'warning');
        elements.newTaskTitle.focus();
        return;
    }
    try {
        const task = await invoke('create_task', {
            title,
            priority: elements.newTaskPriority.value,
            due_date: elements.newTaskDueDate.value || null,
            tags: parseTags(elements.newTaskTags.value),
        });
        elements.newTaskTitle.value = '';
        elements.newTaskDueDate.value = '';
        elements.newTaskTags.value = '';
        state.selectedTaskId = task.id;
        await refreshAll();
        renderDetails();
        showToast('Task created.', 'success');
    } catch (error) {
        showToast(`Failed to create task: ${error.message}`, 'error');
    }
}

async function saveSelectedTask() {
    const taskId = elements.taskId.value;
    if (!taskId) return;
    try {
        await invoke('update_task', {
            task_id: taskId,
            title: elements.editTitle.value.trim(),
            description: elements.editDescription.value,
            priority: elements.editPriority.value,
            due_date: elements.editDueDate.value || null,
            tags: parseTags(elements.editTags.value),
        });
        await invoke('set_task_completed', {
            task_id: taskId,
            completed: elements.editCompleted.checked,
        });
        await refreshAll();
        state.selectedTaskId = taskId;
        renderDetails();
        showToast('Task updated.', 'success');
    } catch (error) {
        showToast(`Failed to save task: ${error.message}`, 'error');
    }
}

async function setTaskCompleted(taskId, completed) {
    try {
        await invoke('set_task_completed', { task_id: taskId, completed });
        await refreshAll();
        state.selectedTaskId = taskId;
        renderDetails();
        if (completed) {
            notify('Task completed', 'Nice work — the task was marked as done.');
        }
    } catch (error) {
        showToast(`Failed to update task: ${error.message}`, 'error');
    }
}

async function deleteSelectedTask() {
    const taskId = elements.taskId.value;
    if (!taskId) return;
    await deleteTask(taskId);
}

async function duplicateSelectedTask() {
    const taskId = elements.taskId.value;
    if (!taskId) {
        showToast('Select a task first.', 'warning');
        return;
    }
    try {
        const task = await invoke('duplicate_task', { task_id: taskId });
        state.selectedTaskId = task.id;
        await refreshAll();
        renderDetails();
        showToast('Task duplicated.', 'success');
    } catch (error) {
        showToast(`Failed to duplicate task: ${error.message}`, 'error');
    }
}

async function deleteTask(taskId) {
    try {
        await invoke('delete_task', { task_id: taskId });
        if (state.selectedTaskId === taskId) {
            state.selectedTaskId = null;
        }
        await refreshAll();
        showToast('Task deleted.', 'success');
    } catch (error) {
        showToast(`Failed to delete task: ${error.message}`, 'error');
    }
}

async function clearCompletedTasks() {
    try {
        const removed = await invoke('clear_completed_tasks');
        if (removed > 0) {
            state.selectedTaskId = null;
            await refreshAll();
            showToast(`Cleared ${removed} completed task${removed === 1 ? '' : 's'}.`, 'success');
        } else {
            showToast('No completed tasks to clear.', 'warning');
        }
    } catch (error) {
        showToast(`Failed to clear tasks: ${error.message}`, 'error');
    }
}

async function seedDemoTasks() {
    try {
        const result = await invoke('seed_demo_tasks');
        await refreshAll();
        showToast(result.skipped ? 'Demo tasks already exist.' : `Added ${result.created} demo tasks.`, 'success');
    } catch (error) {
        showToast(`Failed to seed demo tasks: ${error.message}`, 'error');
    }
}

async function exportTasks() {
    try {
        const payload = await invoke('export_tasks_payload');
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'forge-tasks.json';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        showToast(`Exported ${(payload.tasks || []).length} tasks.`, 'success');
    } catch (error) {
        showToast(`Failed to export tasks: ${error.message}`, 'error');
    }
}

async function importTasks() {
    try {
        const result = await pickJsonFile();
        if (!result) {
            showToast('Import cancelled.', 'warning');
            return;
        }
        const payload = JSON.parse(result);
        const tasks = Array.isArray(payload) ? payload : (payload.tasks || []);
        const importResult = await invoke('import_tasks_payload', { tasks, merge: true });
        await refreshAll();
        showToast(`Imported ${importResult.imported} task${importResult.imported === 1 ? '' : 's'}.`, 'success');
    } catch (error) {
        showToast(`Failed to import tasks: ${error.message}`, 'error');
    }
}

function pickJsonFile() {
    return new Promise((resolve) => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'application/json,.json';
        input.onchange = () => {
            const file = input.files && input.files[0];
            if (!file) {
                resolve(null);
                return;
            }
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ''));
            reader.onerror = () => resolve(null);
            reader.readAsText(file);
        };
        input.click();
    });
}

function parseTags(value) {
    return value
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean);
}

function syncFilterButtons() {
    elements.filterGroup.querySelectorAll('[data-filter]').forEach((button) => {
        button.classList.toggle('active', button.dataset.filter === state.filter);
    });
}

function showToast(message, type = 'info') {
    elements.toast.textContent = message;
    elements.toast.className = `toast show ${type}`;
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
        elements.toast.className = 'toast';
    }, 2800);
}

function notify(title, body) {
    if (window.__forge__?.notifications?.notify) {
        window.__forge__.notifications.notify(title, body, { timeout: 4 }).catch(() => {
            showToast(body, 'success');
        });
        return;
    }
    showToast(body, 'success');
}

function formatDateTime(value) {
    if (!value) return 'just now';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function debounce(callback, wait) {
    let timeoutId = null;
    return (...args) => {
        window.clearTimeout(timeoutId);
        timeoutId = window.setTimeout(() => callback(...args), wait);
    };
}
