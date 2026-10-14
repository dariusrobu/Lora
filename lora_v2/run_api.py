"""ASGI entrypoint for the isolated Mini App API."""

from lora_v2.api import create_app

app = create_app()
