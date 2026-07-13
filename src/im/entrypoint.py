"""Uvicorn entrypoint for the environment-configured prompted policy."""

from im.app import create_openai_app

app = create_openai_app()
