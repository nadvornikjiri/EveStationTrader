from importlib import import_module

from fastapi import FastAPI


def test_backend_main_entrypoint_exports_fastapi_app() -> None:
    entrypoint_module = import_module("main")
    app_module = import_module("app.main")

    assert hasattr(entrypoint_module, "app")
    assert isinstance(entrypoint_module.app, FastAPI)
    assert entrypoint_module.app is app_module.app
