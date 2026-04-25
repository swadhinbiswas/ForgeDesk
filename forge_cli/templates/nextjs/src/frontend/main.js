import { invoke } from '@forgedesk/api'

let todos = []
let currentFilter = 'all'

const todoInput = document.getElementById('todoInput')
const addBtn = document.getElementById('addBtn')
const todoList = document.getElementById('todoList')
const itemsLeft = document.getElementById('itemsLeft')
const clearCompleted = document.getElementById('clearCompleted')
const filterBtns = document.querySelectorAll('.filter')

async function loadTodos() {
    try { todos = await invoke('todo_list'); render() }
    catch (err) { console.error('Failed to load todos:', err) }
}

async function addTodo() {
    const text = todoInput.value.trim()
    if (!text) return
    try { await invoke('todo_add', { text }); todoInput.value = ''; await loadTodos() }
    catch (err) { console.error('Failed to add todo:', err) }
}

async function toggleTodo(id) {
    try { await invoke('todo_toggle', { id }); await loadTodos() }
    catch (err) { console.error('Failed to toggle todo:', err) }
}

async function deleteTodo(id) {
    try { await invoke('todo_delete', { id }); await loadTodos() }
    catch (err) { console.error('Failed to delete todo:', err) }
}

async function clearDone() {
    try { await invoke('todo_clear_completed'); await loadTodos() }
    catch (err) { console.error('Failed to clear completed:', err) }
}

function render() {
    const filtered = todos.filter(t => {
        if (currentFilter === 'active') return !t.done
        if (currentFilter === 'completed') return t.done
        return true
    })

    todoList.innerHTML = filtered.map(todo => `
        <li class="todo-item ${todo.done ? 'completed' : ''}">
            <label class="todo-check">
                <input type="checkbox" ${todo.done ? 'checked' : ''} data-id="${todo.id}">
                <span class="checkmark"></span>
            </label>
            <span class="todo-text">${escapeHtml(todo.text)}</span>
            <button class="btn-delete" data-id="${todo.id}" title="Delete">&times;</button>
        </li>
    `).join('')

    const left = todos.filter(t => !t.done).length
    itemsLeft.textContent = `${left} item${left !== 1 ? 's' : ''} left`

    todoList.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', e => toggleTodo(Number(e.target.dataset.id)))
    })
    todoList.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', e => deleteTodo(Number(e.target.dataset.id)))
    })
}

function escapeHtml(text) {
    const div = document.createElement('div')
    div.textContent = text
    return div.innerHTML
}

addBtn.addEventListener('click', addTodo)
todoInput.addEventListener('keydown', e => { if (e.key === 'Enter') addTodo() })
clearCompleted.addEventListener('click', clearDone)

filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        filterBtns.forEach(b => b.classList.remove('active'))
        btn.classList.add('active')
        currentFilter = btn.dataset.filter
        render()
    })
})

loadTodos()
