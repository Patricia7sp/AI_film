import base64
import os
import time
from pathlib import Path
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.integration


def _client() -> Any:
    runwayml = pytest.importorskip("runwayml")
    api_key = os.getenv("RUNWAY_API_KEY", "").strip()
    if not api_key:
        pytest.skip("RUNWAY_API_KEY is not configured")

    client_args: dict[str, str] = {"api_key": api_key}
    base_url = os.getenv("RUNWAY_BASE_URL", "").strip()
    if base_url:
        client_args["base_url"] = base_url
    return runwayml.RunwayML(**client_args)


def _source_image() -> Path:
    configured = os.getenv("RUNWAY_TEST_IMAGE_PATH", "").strip()
    if not configured:
        pytest.skip("RUNWAY_TEST_IMAGE_PATH is not configured")
    image_path = Path(configured).expanduser().resolve()
    if not image_path.is_file():
        pytest.fail(f"RUNWAY_TEST_IMAGE_PATH does not exist: {image_path}")
    return image_path


def _wait_for_task(client: Any, task_id: str) -> Any:
    timeout_seconds = int(os.getenv("RUNWAY_TEST_TIMEOUT_SECONDS", "900"))
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        task = client.tasks.retrieve(task_id)
        status = str(getattr(task, "status", "")).lower()
        if status in {"succeeded", "success", "completed", "complete"}:
            return task
        if status in {"failed", "failure", "cancelled", "canceled"}:
            pytest.fail(f"Runway task ended with status {status}")
        time.sleep(5)
    pytest.fail(f"Runway task did not finish within {timeout_seconds} seconds")


def test_runway_initialization() -> None:
    client = _client()
    assert client is not None


def test_generate_animation(tmp_path: Path) -> None:
    client = _client()
    image_path = _source_image()
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    is_png = image_path.suffix.lower() == ".png"
    mime_type = "image/png" if is_png else "image/jpeg"
    prompt = "Gentle cinematic motion while preserving identity " "and composition."

    task = client.image_to_video.create(
        model=os.getenv("RUNWAY_MODEL", "gen4_turbo"),
        prompt_image=f"data:{mime_type};base64,{encoded}",
        prompt_text=prompt,
        duration=5,
        ratio=os.getenv("RUNWAY_VIDEO_RATIO", "1280:720"),
    )
    completed = _wait_for_task(client, str(task.id))
    outputs = getattr(completed, "output", None) or []
    assert outputs, "Runway completed without an output URL"

    response = requests.get(str(outputs[0]), timeout=120)
    response.raise_for_status()
    output_path = tmp_path / "runway-integration.mp4"
    output_path.write_bytes(response.content)
    assert output_path.stat().st_size > 0
