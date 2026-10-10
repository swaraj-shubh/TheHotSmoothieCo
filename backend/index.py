"""Vercel entrypoint (serverless). Everywhere else run `uvicorn app.main:app`."""

from app.main import app  # noqa: F401
