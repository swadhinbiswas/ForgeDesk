# The Power of the Python Backend

While Forge relies on modern web frameworks (like Astro or React) to render beautiful user interfaces, **its true unfair advantage is the Python runtime**.

When building desktop applications with Electron, you are generally trapped inside the Node.js or V8 ecosystem. If you need to perform heavy data processing, interface with machine learning models, or manipulate raw system APIs, you often have to spawn brittle child processes or write complex native node addons.

In Forge, **Python is the primary execution thread**.

### Why Python?

1. **AI and Machine Learning:**
   With Forge, importing libraries like `PyTorch`, `Transformers`, `TensorFlow`, or `llama.cpp` to run local, offline LLMs or AI assistants requires zero bridging. You simply write Python.

2. **Data Science:**
   The entire `pandas`, `numpy`, and `matplotlib` ecosystem operates natively.

3. **Secure Secrets Management:**
   By keeping external API calls in your Python backend (using libraries like `urllib` or `requests`), your API keys (like TMDB, Stripe, or OpenAI keys) are never shipped in the client-side JavaScript bundle, making your application fundamentally impenetrable to frontend scraping bots.

### API Security Example (Movie App)

In our movie example (`examples/forge_movies`), the frontend Astro application *does not* have the TMDB API Key. Instead, it asks Python:

```python
import os
import urllib.request
from forge import Forge

app = Forge()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

@app.command
def fetch_popular_movies():
    # Only the Python backend securely proxies this request
    url = f"https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())
```

And your frontend simply invokes:

```javascript
import { invoke } from '@forge/api';
const popularMovies = await invoke('fetch_popular_movies');
```

This seamless inter-process communication acts precisely like a secure microservice living natively on your machine!
