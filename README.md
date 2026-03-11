# Council Orchestrator

Standalone Python CLI for a hybrid planning council and code execution loop.

## Layout

- `config.yml` for model, chairman, and executor settings
- `council_orchestrator/` for the Python package
- `data/` for runtime plans and run logs

## Run

```bash
python -m council_orchestrator.main run "Add a hello world function" --project-path path/to/repo
```
