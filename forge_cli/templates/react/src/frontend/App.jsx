import { useState } from 'react'
import forge, { invoke } from '@forge/api'
import './App.css'

function App() {
  const [name, setName] = useState('Developer')
  const [greeting, setGreeting] = useState('')
  const [systemInfo, setSystemInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Call Python greet command
  const handleGreet = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await invoke('greet', { name })
      setGreeting(result)
      
      // Copy to clipboard
      await forge.clipboard.write(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Call Python get_system_info command
  const handleGetInfo = async () => {
    setLoading(true)
    setError(null)
    try {
      const info = await invoke('get_system_info')
      setSystemInfo(info)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>⚡ {{PROJECT_NAME}}</h1>
        <p className="tagline">Built with Forge + React</p>
      </header>

      <main className="main">
        <section className="card">
          <h2>Greeting</h2>
          <div className="input-group">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter your name"
            />
            <button onClick={handleGreet} disabled={loading}>
              {loading ? '...' : 'Greet'}
            </button>
          </div>
          {greeting && <p className="result success">{greeting}</p>}
        </section>

        <section className="card">
          <h2>System Info</h2>
          <button onClick={handleGetInfo} disabled={loading}>
            {loading ? 'Loading...' : 'Get Info'}
          </button>
          {systemInfo && (
            <pre className="result">{JSON.stringify(systemInfo, null, 2)}</pre>
          )}
        </section>

        {error && (
          <section className="card error">
            <h2>Error</h2>
            <p className="result error">{error}</p>
          </section>
        )}
      </main>

      <footer className="footer">
        <p>Forge Framework v1.0.0</p>
      </footer>
    </div>
  )
}

export default App
