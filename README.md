# personal-assistant
Jarvis, do your thing

Coding agents: start with [`AGENTS.md`](AGENTS.md).

## Setup

```bash
cp config.example.yaml config.yaml
cp .env.example .env   # optional; set OPENAI_API_KEY for OpenAI
pip install -r requirements.txt
```

`config.example.yaml` defaults to **file** storage under `data/` and loads the persona from `prompts/system.md`.

## Backend

From the **project root** (this directory):

```bash
.venv/Scripts/python -m backend.main
```

Or: `python -m backend.main` if your venv is already activated. Do not run `python backend/main.py` — the `backend` package must be imported from the root.

## Frontend

From the **project root**:

```bash
cd frontend
npm install
npm start
```

Then open http://localhost:1234 (Parcel default). The app talks to the backend at `http://127.0.0.1:8765` by default; set `API_URL` and `WS_URL` if your backend runs elsewhere.

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
