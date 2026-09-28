# Student Rewards Platform

A classroom rewards and assessment platform with balances, transfers, and role-based workflows.

## Features

- Student and administrator accounts
- Assessments and reward transactions
- Transfer rules and audit history
- FastAPI application with Alembic migrations

## Run locally

```bash
python -m venv .venv
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```
