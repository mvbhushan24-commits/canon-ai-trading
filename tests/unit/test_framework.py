"""Testing framework smoke tests (Sprint 0 — no business logic)."""


def test_pytest_framework_loads() -> None:
    assert True


def test_tests_package_importable() -> None:
    import tests  # noqa: F401
