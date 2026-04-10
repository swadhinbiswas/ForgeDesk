---
title: React & Next.js
description: Use ForgeDesk with React-based frontends.
---

Install the frontend bridge:

```bash
npm install @forgedesk/api
```

Use `invoke` for backend command calls:

```ts
import { invoke } from '@forgedesk/api';
const version = await invoke('app_version');
```
