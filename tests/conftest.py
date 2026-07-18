import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-external",
        action="store_true",
        default=False,
        help="Run tests that call paid or authenticated external providers.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    run_external = config.getoption("--run-external") or os.getenv(
        "RUN_EXTERNAL_TESTS", ""
    ).strip().lower() in {"1", "true", "yes"}
    if run_external:
        return

    skip_external = pytest.mark.skip(
        reason="external integration disabled; use --run-external to enable"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_external)
