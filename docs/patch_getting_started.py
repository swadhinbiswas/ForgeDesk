with open("src/content/docs/getting-started.mdx") as f:
    content = f.read()

content = content.replace(
    "---\n\nBuild cross-platform",
    "---\n\nimport { FileTree } from '@astrojs/starlight/components';\n\nBuild cross-platform",
)

old_tree = """```text
my-app/
├── forge.toml          # Rust/Python App capabilities and configuration
├── src/
│   ├── main.py         # Python backend entrypoint
│   └── frontend/       # Vite-powered React/TypeScript frontend
│       ├── index.html
│       ├── package.json
│       ├── src/
│       │   ├── App.tsx
│       │   └── main.tsx
└── src-forge/          # Auto-generated native assets
```"""

new_tree = """<FileTree>
- my-app/
  - forge.toml          # Rust/Python App capabilities and configuration
  - src/
    - main.py         # Python backend entrypoint
    - frontend/       # Vite-powered React/TypeScript frontend
      - index.html
      - package.json
      - src/
        - App.tsx
        - main.tsx
  - src-forge/          # Auto-generated native assets
</FileTree>"""

content = content.replace(old_tree, new_tree)

with open("src/content/docs/getting-started.mdx", "w") as f:
    f.write(content)
