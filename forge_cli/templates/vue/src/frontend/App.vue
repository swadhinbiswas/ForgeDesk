<template>
  <div class="app">
    <header class="header">
      <h1>⚡ {{PROJECT_NAME}}</h1>
      <p class="tagline">Built with Forge + Vue</p>
    </header>

    <main class="main">
      <section class="card">
        <h2>Greeting</h2>
        <div class="input-group">
          <input
            v-model="name"
            type="text"
            placeholder="Enter your name"
          />
          <button @click="handleGreet" :disabled="loading">
            {{ loading ? '...' : 'Greet' }}
          </button>
        </div>
        <p v-if="greeting" class="result success">{{ greeting }}</p>
      </section>

      <section class="card">
        <h2>System Info</h2>
        <button @click="handleGetInfo" :disabled="loading">
          {{ loading ? 'Loading...' : 'Get Info' }}
        </button>
        <pre v-if="systemInfo" class="result">{{ JSON.stringify(systemInfo, null, 2) }}</pre>
      </section>

      <section v-if="error" class="card error">
        <h2>Error</h2>
        <p class="result error">{{ error }}</p>
      </section>
    </main>

    <footer class="footer">
      <p>Forge Framework v1.0.0</p>
    </footer>
  </div>
</template>

<script>
import forge, { invoke } from '@forge/api'

export default {
  name: 'App',
  data() {
    return {
      name: 'Developer',
      greeting: '',
      systemInfo: null,
      loading: false,
      error: null
    }
  },
  methods: {
    async handleGreet() {
      this.loading = true
      this.error = null
      try {
        const result = await invoke('greet', { name: this.name })
        this.greeting = result
        
        // Copy to clipboard
        await forge.clipboard.write(result)
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    async handleGetInfo() {
      this.loading = true
      this.error = null
      try {
        const info = await invoke('get_system_info')
        this.systemInfo = info
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.app {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
}

.header {
  text-align: center;
  margin-bottom: 3rem;
  padding: 2rem 0;
}

.header h1 {
  font-size: 2.5rem;
  font-weight: 700;
  background: linear-gradient(135deg, #00d4ff, #7b2fff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 0.5rem;
}

.tagline {
  color: #a0a0b0;
  font-size: 1.1rem;
}

.main {
  display: grid;
  gap: 1.5rem;
}

.card {
  background: #1a1a25;
  border: 1px solid #2a2a3a;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.card h2 {
  font-size: 1.25rem;
  margin-bottom: 1rem;
  color: #00d4ff;
}

.input-group {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

input[type="text"] {
  flex: 1;
  padding: 0.75rem 1rem;
  background: #12121a;
  border: 1px solid #2a2a3a;
  border-radius: 8px;
  color: #ffffff;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
}

input:focus {
  border-color: #00d4ff;
}

button {
  padding: 0.75rem 1.5rem;
  background: #00d4ff;
  color: #0a0a0f;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

button:hover:not(:disabled) {
  background: #00b8e6;
  transform: translateY(-1px);
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.result {
  background: #12121a;
  border: 1px solid #2a2a3a;
  border-radius: 8px;
  padding: 1rem;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 0.9rem;
  margin-top: 1rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.result.success {
  color: #00ff88;
}

.result.error {
  color: #ff4757;
  border-color: #ff4757;
}

.footer {
  text-align: center;
  margin-top: 3rem;
  padding: 2rem 0;
  color: #a0a0b0;
  font-size: 0.9rem;
}

@media (max-width: 600px) {
  .app {
    padding: 1rem;
  }

  .header h1 {
    font-size: 1.75rem;
  }

  .input-group {
    flex-direction: column;
  }

  button {
    width: 100%;
  }
}
</style>
