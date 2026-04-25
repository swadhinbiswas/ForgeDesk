import { useState, useEffect, useCallback } from 'react'
import { invoke } from '@forgedesk/api'
import './App.css'

function App() {
  const [todos, setTodos] = useState([])
  const [text, setText] = useState('')
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)

  const loadTodos = useCallback(async () => {
    try {
      const data = await invoke('todo_list')
      setTodos(data)
    } catch (err) {
      console.error('Failed to load todos:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadTodos() }, [loadTodos])

  const addTodo = async () => {
    if (!text.trim()) return
    try {
      await invoke('todo_add', { text: text.trim() })
      setText('')
      await loadTodos()
    } catch (err) {
      console.error('Failed to add todo:', err)
    }
  }

  const toggleTodo = async (id) => {
    try {
      await invoke('todo_toggle', { id })
      await loadTodos()
    } catch (err) {
      console.error('Failed to toggle todo:', err)
    }
  }

  const deleteTodo = async (id) => {
    try {
      await invoke('todo_delete', { id })
      await loadTodos()
    } catch (err) {
      console.error('Failed to delete todo:', err)
    }
  }

  const clearCompleted = async () => {
    try {
      await invoke('todo_clear_completed')
      await loadTodos()
    } catch (err) {
      console.error('Failed to clear completed:', err)
    }
  }

  const filtered = todos.filter(t => {
    if (filter === 'active') return !t.done
    if (filter === 'completed') return t.done
    return true
  })

  const left = todos.filter(t => !t.done).length

  return (
    <div className="app">
      <header className="app-header">
        <h1>{{PROJECT_NAME}}</h1>
        <p className="subtitle">What needs to be done?</p>
        <p className="architecture-note">
          Complex template — Modular architecture with handlers/ + services/
        </p>
      </header>

      <main className="todo-container">
        <div className="input-wrapper">
          <input
            type="text"
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addTodo()}
            placeholder="What needs to be done?"
            autoComplete="off"
          />
          <button onClick={addTodo} className="btn-primary">Add</button>
        </div>

        <div className="filters">
          {['all', 'active', 'completed'].map(f => (
            <button
              key={f}
              className={`filter ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f[0].toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="loading">Loading todos...</div>
        ) : (
          <ul className="todo-list">
            {filtered.map(todo => (
              <li key={todo.id} className={`todo-item ${todo.done ? 'completed' : ''}`}>
                <label className="todo-check">
                  <input
                    type="checkbox"
                    checked={todo.done}
                    onChange={() => toggleTodo(todo.id)}
                  />
                  <span className="checkmark"></span>
                </label>
                <span className="todo-text">{todo.text}</span>
                <button
                  className="btn-delete"
                  onClick={() => deleteTodo(todo.id)}
                  title="Delete"
                >
                  &times;
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="todo-footer">
          <span>{left} item{left !== 1 ? 's' : ''} left</span>
          <button className="btn-text" onClick={clearCompleted}>
            Clear completed
          </button>
        </div>
      </main>

      <footer className="app-footer">
        <p>Press <kbd>Enter</kbd> to add a todo</p>
        <p className="powered">
          Powered by <strong>Forge</strong> + React + Python
          <br />
          <em>handlers/ + services/ architecture</em>
        </p>
      </footer>
    </div>
  )
}

export default App
