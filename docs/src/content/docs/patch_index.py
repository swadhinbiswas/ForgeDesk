with open("index.mdx") as f:
    content = f.read()

replacement = """import { Card, CardGrid, Tabs, TabItem } from '@astrojs/starlight/components';

## Quick Start

<Tabs>
  <TabItem label="npm" icon="seti:npm">
    ```bash
    npm create forge-app@latest
    ```
  </TabItem>
  <TabItem label="pnpm" icon="pnpm">
    ```bash
    pnpm create forge-app
    ```
  </TabItem>
  <TabItem label="yarn" icon="seti:yarn">
    ```bash
    yarn create forge-app
    ```
  </TabItem>
</Tabs>

## Create small, fast, secure desktop applications"""

content = content.replace(
    "import { Card, CardGrid } from '@astrojs/starlight/components';\n\n## Create small, fast, secure desktop applications",  # noqa: E501
    replacement,
)

with open("index.mdx", "w") as f:
    f.write(content)
