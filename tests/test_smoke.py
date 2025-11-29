def test_smoke_imports():
    import importlib
    importlib.import_module("services.api.app.main")
    importlib.import_module("services.worker.worker.tasks")
