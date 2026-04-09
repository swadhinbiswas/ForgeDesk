# Forge Todo

A complete task manager example built with Forge.

## Features

- Create, edit, complete, and delete tasks
- Search tasks and filter by state or priority
- Due dates, tags, and task descriptions
- Persistent local JSON storage
- Summary dashboard with completion progress
- Demo data seeding and completed-task cleanup
- Import/export task backups with browser file pickers
- Duplicate an existing task from the detail pane
- Optional desktop notifications when tasks are completed

## Run

From this example directory:

```bash
forge dev
```

## Build validation

```bash
forge build --target web --result-format json
```

## Test validation

From the repository root:

```bash
python -m pytest -q tests/test_todo_example.py
```

## Storage

Tasks are stored in `.forge-data/tasks.json` inside this project.

## Tips

- Use **Seed demo** to populate the board with realistic example work.
- Use **Import** and **Export** for JSON task backups.
- Select a task to edit details, mark it complete, or duplicate it.
