import re

with open("index.mdx") as f:
    content = f.read()

replacement = """<Tabs>
  <TabItem label="uv" icon="seti:python">
    ```bash
    uv pip install forgedesk
    forge create
    ```
  </TabItem>
  <TabItem label="pip" icon="seti:python">
    ```bash
    pip install forgedesk
    forge create
    ```
  </TabItem>
  <TabItem label="npm" icon="seti:npm">
    ```bash
    npm create @forgedesk/forge-app@latest
    ```
  </TabItem>
  <TabItem label="pnpm" icon="pnpm">
    ```bash
    pnpm create @forgedesk/forge-app
    ```
  </TabItem>
  <TabItem label="yarn" icon="seti:yarn">
    ```bash
    yarn create @forgedesk/forge-app
    ```
  </TabItem>
  <TabItem label="bun" icon="bun">
    ```bash
    bun create @forgedesk/forge-app
    ```
  </TabItem>
</Tabs>"""

content = re.sub(r"<Tabs>.*?</Tabs>", replacement, content, flags=re.DOTALL)

with open("index.mdx", "w") as f:
    f.write(content)
