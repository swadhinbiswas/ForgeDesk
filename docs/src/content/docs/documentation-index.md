---
title: "Documentation Index"
description: "Complete guide to ForgeDesk documentation"
---

## Welcome to ForgeDesk Documentation

ForgeDesk is a **next-generation desktop application framework** combining the power of Rust with Python and modern web technologies. This documentation covers everything you need to build production-grade desktop applications.

## Getting Started

Start with these guides if you're new to Forge:

1. **[Framework Overview](./framework-overview/)** - Understand Forge's philosophy, architecture, and capabilities
   - Framework design principles
   - 4-layer architecture diagram
   - Comparison with alternatives (Tauri, Electron, PyQt)
   - Key features overview

2. **[Building Apps](/building-apps/)** - Step-by-step guide to creating your first ForgeDesk app
   - Project structure and setup
   - fork.toml configuration
   - Backend setup with Python
   - Frontend setup with React/Vue/Svelte
   - Best practices and patterns

## Core Concepts

Understand how Forge works under the hood:

3. **[IPC Communication](./ipc-communication/)** - How frontend and backend communicate
   - Command registration
   - Event streaming
   - Type hints and validation
   - Error handling
   - Real-world examples

4. **[State Management](./state-management/)** - Store and manage application data
   - Global app state
   - SQLite persistence
   - Caching strategies
   - Session management
   - Authentication patterns

## Frontend Development

Build user interfaces with your favorite framework:

5. **[Frontend Integration](.//frontend-integration/)** - Framework integration guides
   - React hooks and patterns
   - Vue composables
   - Svelte stores
   - TypeScript support
   - Context and state patterns

## Advanced Topics

Master production deployment and optimization:

6. **[Deployment & Security](.//deployment-security/)** - Deploy securely to production
   - Production build process
   - Input validation
   - Authentication and encryption
   - Rate limiting
   - Performance optimization
   - Troubleshooting guide

7. **[API Reference](.//api-complete-reference/)** - Complete API documentation
   - ForgeApp API
   - Window management
   - Built-in APIs (FileSystem, Dialogs, etc.)
   - Frontend API
   - Type hints guide

8. **[Best Practices](./best-practices/)** - Real-world patterns and recipes
   - Project structure templates
   - Code organization
   - Error handling patterns
   - Frontend patterns
   - Testing strategies
   - Performance tips

## By Use Case

### I want to build a simple app
→ Start with [Building Apps](/building-apps/), then reference [Best Practices](/best-practices/)

### I need to fetch data from the backend
→ Read [IPC Communication](./ipc-communication/) and [Frontend Integration](.//frontend-integration/)

### I need to store and persist data
→ Follow [State Management](./state-management/)

### I'm ready to deploy
→ Reference [Deployment & Security](.//deployment-security/)

### I need to do something specific
→ Check [API Reference](.//api-complete-reference/)

## Documentation Structure

```
docs/
├── framework-overview.md          # Philosophy & architecture
├── building-apps.md               # Project setup & structure
├── ipc-communication.md           # Frontend-backend communication
├── state-management.md            # Data persistence & caching
├── /frontend-integration/        # React/Vue/Svelte integration
├── /deployment-security/         # Production & security
├── /api-complete-reference/      # Full API reference
├── best-practices.md              # Patterns & recipes
└── index.md (this file)          # Navigation guide
```

## Quick Reference

### Creating a Command

```python
@app.command("get_data")
def get_data(query: str) -> dict:
    """Get data with type hints"""
    return {"result": query}
```

### Invoking from Frontend

```javascript
const result = await invoke("get_data", { query: "search term" })
```

### Listening for Events

```python
# Backend
app.emit("data_updated", {"value": 42})

# Frontend
on("data_updated", (data) => {
  console.log(data.value)
})
```

### React Integration

```jsx
function MyComponent() {
  const [data, setData] = useState(null)
  
  const { execute } = useForgeCommand("get_data")
  
  useEffect(() => {
    execute({ query: "data" }).then(setData)
  }, [])
  
  return <div>{data?.result}</div>
}
```

## Common Patterns

### Request-Response
Backend sends data back to frontend command [→ See Example](./ipc-communication.md#request-response-pattern)

### Event Streaming
Backend continuously emits events to frontend [→ See Example](./ipc-communication.md#event-streaming-pattern)

### State Persistence
Save/load data using SQLite [→ See Example](./state-management.md#database-persistence)

### Authentication
Secure user login flow [→ See Example](./state-management.md#authentication-flow)

### Error Handling
Consistent error responses [→ See Example](./best-practices.md#error-handling-patterns)

## Code Examples

Most documentation includes **copy-paste ready code examples**:

- ✅ Complete working code
- ✅ Real-world patterns
- ✅ Error handling
- ✅ Type hints
- ✅ Best practices

You can copy these directly into your projects and adapt them to your needs.

## Platform Support

Forge supports:
- **Windows** - Native Windows API
- **macOS** - Native Cocoa framework
- **Linux** - XDG desktop standards + Qt

See [Building Apps](/building-apps/) for platform-specific patterns.

## Performance Benchmarks

- **App startup**: ~200-300ms
- **Command latency**: <10ms
- **Event streaming**: 1000s of events/second
- **Memory usage**: 30-50MB base + app data

See [Deployment & Security](.//deployment-security/#performance-profiling) for optimization strategies.

## Troubleshooting

Common issues and solutions in [Deployment & Security](.//deployment-security/#troubleshooting-guide).

## Examples

Check out complete example applications in the `examples/` directory:
- `forge_todo/` - Todo application with React
- `crypto_analyzer/` - Real-time data streaming
- `api_explorer/` - API testing tool
- `hello_forge/` - Minimal starter app

## Contributing

Found an issue in the docs? Want to contribute improvements?

1. Fork the repository
2. Create a branch: `git checkout -b docs/fix-something`
3. Make your changes
4. Submit a pull request

## Support

- **Questions?** Check the FAQ section in [Framework Overview](/framework-overview/)
- **Issues?** See [Troubleshooting](.//deployment-security/#troubleshooting-guide)
- **Community?** Join us on GitHub Discussions

## License

Forge documentation and examples are licensed under MIT License.

---

**Next Step:** Start with [Framework Overview](./framework-overview/) to understand Forge's architecture and philosophy.

