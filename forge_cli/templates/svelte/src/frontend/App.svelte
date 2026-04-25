<script>
  import { onMount } from 'svelte';
  import { invoke } from '@forgedesk/api';
  import './style.css';

  let todos = [];
  let text = '';
  let filter = 'all';
  let loading = true;
  const filters = ['all', 'active', 'completed'];

  $: filtered = filter === 'active'
    ? todos.filter(t => !t.done)
    : filter === 'completed'
    ? todos.filter(t => t.done)
    : todos;

  $: left = todos.filter(t => !t.done).length;

  async function loadTodos() {
    try {
      todos = await invoke('todo_list');
    } catch (err) {
      console.error('Failed to load todos:', err);
    } finally {
      loading = false;
    }
  }

  async function addTodo() {
    if (!text.trim()) return;
    try {
      await invoke('todo_add', { text: text.trim() });
      text = '';
      await loadTodos();
    } catch (err) {
      console.error('Failed to add todo:', err);
    }
  }

  async function toggleTodo(id) {
    try {
      await invoke('todo_toggle', { id });
      await loadTodos();
    } catch (err) {
      console.error('Failed to toggle todo:', err);
    }
  }

  async function deleteTodo(id) {
    try {
      await invoke('todo_delete', { id });
      await loadTodos();
    } catch (err) {
      console.error('Failed to delete todo:', err);
    }
  }

  async function clearCompleted() {
    try {
      await invoke('todo_clear_completed');
      await loadTodos();
    } catch (err) {
      console.error('Failed to clear completed:', err);
    }
  }

  onMount(loadTodos);
</script>

<div class="app">
  <header class="app-header">
    <h1>{{PROJECT_NAME}}</h1>
    <p class="subtitle">What needs to be done?</p>
  </header>

  <main class="todo-container">
    <div class="input-wrapper">
      <input
        type="text"
        bind:value={text}
        on:keydown={e => e.key === 'Enter' && addTodo()}
        placeholder="What needs to be done?"
        autocomplete="off"
      />
      <button on:click={addTodo} class="btn-primary">Add</button>
    </div>

    <div class="filters">
      {#each filters as f}
        <button
          class="filter {filter === f ? 'active' : ''}"
          on:click={() => filter = f}
        >
          {f[0].toUpperCase() + f.slice(1)}
        </button>
      {/each}
    </div>

    {#if loading}
      <div class="loading">Loading todos...</div>
    {:else}
      <ul class="todo-list">
        {#each filtered as todo (todo.id)}
          <li class="todo-item {todo.done ? 'completed' : ''}">
            <label class="todo-check">
              <input
                type="checkbox"
                checked={todo.done}
                on:change={() => toggleTodo(todo.id)}
              />
              <span class="checkmark"></span>
            </label>
            <span class="todo-text">{todo.text}</span>
            <button class="btn-delete" on:click={() => deleteTodo(todo.id)} title="Delete">
              &times;
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    <div class="todo-footer">
      <span>{left} item{left !== 1 ? 's' : ''} left</span>
      <button class="btn-text" on:click={clearCompleted}>
        Clear completed
      </button>
    </div>
  </main>

  <footer class="app-footer">
    <p>Press <kbd>Enter</kbd> to add a todo</p>
    <p class="powered">Powered by <strong>Forge</strong> + Svelte + Python</p>
  </footer>
</div>
