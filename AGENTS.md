# Repository Guidelines

## Project Structure & Modules
- `bot.py`: Main voice bot entrypoint. Prefer extending here or add features in `modules/`.
- `simple_avatar.py`, `avatar_test.html`, `custom_client/`: Optional example UIs/clients for local testing.
- `assets/`: Local models and media; large files are Git-ignored backups in `assets.backup/`.
- `Dockerfile`, `pcc-deploy.toml`: Cloud deployment config for Pipecat Cloud.
- `pyproject.toml`, `requirements.txt`: Dependency and tooling definitions.

## Build, Test, and Dev Commands
- Setup env: `uv sync` (installs deps) or `python -m venv venv && pip install -r requirements.txt`.
- Run locally (uv): `uv run bot.py` or `uv run bot.py --transport webrtc`.
- Run locally (python): `python bot.py --transport webrtc`.
- Lint/import sort: `uv run ruff check --fix`.
- Cloud auth: `uv run pcc auth login`.
- Build & push: `uv run pcc docker build-push`.
- Deploy: `uv run pcc deploy`.

## Coding Style & Naming
- Python 3.10+; 4-space indent; max line length 100 (see `pyproject.toml`).
- Names: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`.
- Imports: sorted by Ruff (rule `I`). Keep stdlib/third-party/local groups clean.
- Keep bot logic modular (pure helpers in `modules/`), avoid hard-coding secrets.

## Testing Guidelines
- No formal suite yet. If adding tests, use `pytest` in `tests/` with files named `test_*.py`.
- Aim for fast, unit-level tests around helpers; mock network/audio I/O.
- Run (if added): `uv run pytest -q`.

## Commit & Pull Requests
- Commits: imperative, concise subject (≤72 chars). Example: `Add Moonshine STT pipeline`.
- Reference issues/PRs when relevant: `Fix TTS glitch (#123)`.
- PRs: include summary, rationale, testing steps, and screenshots for UI changes (`custom_client/`, HTML).
- Keep diffs focused; update docs (`README.md`, `QUICKSTART.md`) when behavior changes.

## Security & Config Tips
- Never commit secrets. Use `.env` locally (`DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `CARTESIA_API_KEY`).
- For Cloud, upload with: `uv run pcc secrets set quickstart-secrets --file .env`.
- Large model files belong in `assets/`; avoid committing heavyweight binaries.
