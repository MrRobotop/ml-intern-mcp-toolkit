"""Smoke tests run on every CI build to catch import-time regressions."""


def test_imports() -> None:
    """Both source packages import cleanly with no top-level side effects.

    The imports are unused on purpose; we only verify that they resolve.
    """
    import arxiv_deep  # noqa: F401
    import experiment_tracker  # noqa: F401
