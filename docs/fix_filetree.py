with open("src/content/docs/getting-started.mdx") as f:
    content = f.read()

content = content.replace("<FileTree>\n- my-app/", "<FileTree>\n\n- my-app/")
content = content.replace("        - main.tsx\n- src-forge/", "        - main.tsx\n  - src-forge/")
content = content.replace(
    "        - main.tsx\n    - src-forge/", "        - main.tsx\n  - src-forge/"
)
content = content.replace(
    "  - src-forge/          # Auto-generated native assets\n</FileTree>",
    "  - src-forge/          # Auto-generated native assets\n\n</FileTree>",
)
with open("src/content/docs/getting-started.mdx", "w") as f:
    f.write(content)
