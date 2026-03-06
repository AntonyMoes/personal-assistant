# personal-assistant
Jarvis, do your thing

## Backend

From the **project root** (this directory):

```bash
.venv/Scripts/python -m backend.main
```

Or: `python -m backend.main` if your venv is already activated. Do not run `python backend/main.py` — the `backend` package must be imported from the root.

## Tests

From the **project root**:

```bash
.venv/Scripts/python -m pytest
```

Run with **coverage**:

```bash
.venv/Scripts/python -m pytest --cov=backend --cov-report=term-missing
```

- `--cov=backend` measures coverage for the `backend` package.
- `--cov-report=term-missing` prints a report in the terminal and lists lines not covered.

Generate an HTML coverage report:

```bash
.venv/Scripts/python -m pytest --cov=backend --cov-report=html
```

Open `htmlcov/index.html` in a browser to see coverage by file.
