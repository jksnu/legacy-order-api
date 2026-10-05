# Legacy Order Management API

A deliberately imperfect Flask REST API used for an AI-assisted re-engineering exercise.

## Purpose

This repository represents a small inherited application. It intentionally contains a mixture of realistic legacy design problems and a small number of seeded security weaknesses. **Do not treat this code as production-safe.**

The application supports users, customers, products, orders, payments and sales reporting.

## Technology

- Python 3.11+
- Flask
- Flask-SQLAlchemy
- SQLite
- JWT authentication
- pytest

## Run locally

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

The API starts on `http://127.0.0.1:5000`.

## Run tests

```bash
pytest -q
```

## Seeded accounts

The development seed creates:

- `admin@example.com` / `admin123`
- `alice@example.com` / `alice123`
- `bob@example.com` / `bob123`

These credentials are intentionally simple because this is a training repository.

## Important exercise rule

The repository is a **legacy baseline**. Before re-engineering, use GitHub Copilot Agent to reverse-engineer and assess it. Do not manually fix the seeded issues before the baseline analysis.
