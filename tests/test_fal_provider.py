from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from open3d_implementation.core import fal_provider  # noqa: E402
from open3d_implementation.core.fal_provider import (  # noqa: E402
    FalAuthenticationError,
    FalJobResult,
    FalOutputError,
    FalQueueClient,
    FalSecurityError,
    FalTimeoutError,
    extract_image_url,
    file_to_data_uri,
    validate_external_url,
)


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, object],
        *,
        status_code: int = 200,
        content: bytes = b"",
        content_type: str = "application/json",
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
        }

    def json(self) -> dict[str, object]:
        return self._payload

    def iter_content(self, chunk_size: int) -> list[bytes]:
        del chunk_size
        return [self.content]


class FakeSession:
    def __init__(self) -> None:
        self.posts: list[dict[str, object]] = []
        self.puts: list[str] = []
        self.statuses = [
            FakeResponse({"status": "IN_QUEUE"}),
            FakeResponse({"status": "IN_PROGRESS"}),
            FakeResponse({"status": "COMPLETED"}),
        ]

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        self.posts.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            {
                "request_id": "request-123",
                "status_url": (
                    "https://queue.fal.run/fal-ai/flux/dev/"
                    "requests/request-123/status"
                ),
                "response_url": (
                    "https://queue.fal.run/fal-ai/flux/dev/" "requests/request-123"
                ),
                "cancel_url": (
                    "https://queue.fal.run/fal-ai/flux/dev/"
                    "requests/request-123/cancel"
                ),
            }
        )

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        stream: bool = False,
    ) -> FakeResponse:
        del headers, timeout, stream
        if url.endswith("/status"):
            return self.statuses.pop(0)
        return FakeResponse(
            {
                "images": [
                    {
                        "url": "https://fal.media/files/test/image.png",
                        "width": 768,
                        "height": 1024,
                    }
                ]
            }
        )

    def put(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        del headers, timeout
        self.puts.append(url)
        return FakeResponse({"status": "CANCELLED"})


def test_authentication_error_preserves_safe_provider_detail():
    response = FakeResponse(
        {"detail": "Exhausted balance"},
        status_code=403,
    )

    with pytest.raises(
        FalAuthenticationError,
        match="fal_authentication_failed:http_403:Exhausted balance",
    ):
        fal_provider._raise_for_fal_status(response)


def test_queue_client_uses_key_header_and_bounded_polling(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(fal_provider.time, "sleep", lambda _seconds: None)
    client = FalQueueClient(
        "secret-value",
        session=session,
        request_timeout_seconds=5,
    )

    result = client.run(
        "fal-ai/flux/dev",
        {"prompt": "storybook frame"},
        poll_interval_seconds=0.1,
    )

    assert result.request_id == "request-123"
    assert result.status_history == ("IN_QUEUE", "IN_PROGRESS", "COMPLETED")
    assert session.posts[0]["headers"]["Authorization"] == "Key secret-value"
    assert "secret-value" not in repr(result)


def test_queue_timeout_cancels_request(monkeypatch):
    session = FakeSession()
    session.statuses = [FakeResponse({"status": "IN_QUEUE"})]
    monotonic_values = iter([0.0, 6.0])
    monkeypatch.setattr(
        fal_provider.time,
        "monotonic",
        lambda: next(monotonic_values),
    )
    client = FalQueueClient("secret-value", session=session)

    with pytest.raises(FalTimeoutError, match="fal_queue_timeout"):
        client.run(
            "fal-ai/flux/dev",
            {"prompt": "storybook frame"},
            queue_timeout_seconds=5,
            poll_interval_seconds=0.1,
        )

    assert session.puts


def test_transient_poll_failure_retries_without_resubmitting(monkeypatch):
    session = FakeSession()
    original_get = session.get
    poll_attempts = 0

    def flaky_get(*args, **kwargs):
        nonlocal poll_attempts
        if str(args[0]).endswith("/status") and poll_attempts == 0:
            poll_attempts += 1
            raise fal_provider.requests.Timeout("temporary timeout")
        return original_get(*args, **kwargs)

    session.get = flaky_get  # type: ignore[method-assign]
    monkeypatch.setattr(fal_provider.time, "sleep", lambda _seconds: None)
    client = FalQueueClient("secret-value", session=session)

    result = client.run(
        "fal-ai/flux/dev",
        {"prompt": "storybook frame"},
        poll_interval_seconds=0.1,
    )

    assert result.request_id == "request-123"
    assert len(session.posts) == 1
    assert session.puts == []


def test_exhausted_poll_retries_cancel_submitted_job(monkeypatch):
    session = FakeSession()

    def failed_get(*_args, **_kwargs):
        raise fal_provider.requests.ConnectionError("connection reset")

    session.get = failed_get  # type: ignore[method-assign]
    monkeypatch.setenv("FAL_POLL_REQUEST_RETRY_ATTEMPTS", "2")
    monkeypatch.setattr(fal_provider.time, "sleep", lambda _seconds: None)
    client = FalQueueClient("secret-value", session=session)

    with pytest.raises(
        fal_provider.FalTransientRequestError,
        match="fal_poll_transport_error",
    ):
        client.run(
            "fal-ai/flux/dev",
            {"prompt": "storybook frame"},
            poll_interval_seconds=0.1,
        )

    assert len(session.posts) == 1
    assert session.puts


@pytest.mark.parametrize(
    "url",
    [
        "http://fal.media/file.png",
        "https://127.0.0.1/file.png",
        "https://example.com/file.png",
        "https://user@fal.media/file.png",
    ],
)
def test_external_url_validation_blocks_untrusted_locations(url):
    with pytest.raises(FalSecurityError):
        validate_external_url(url)


def test_output_contract_requires_image_url():
    with pytest.raises(FalOutputError, match="fal_image_output_missing"):
        extract_image_url({"images": []})


def test_file_data_uri_is_bounded_and_typed(tmp_path: Path):
    image = tmp_path / "reference.png"
    image.write_bytes(b"png-data")

    uri = file_to_data_uri(
        image,
        max_bytes=1024,
        allowed_mime_types=("image/png",),
    )

    assert uri.startswith("data:image/png;base64,")
    with pytest.raises(fal_provider.FalConfigurationError):
        file_to_data_uri(
            image,
            max_bytes=2,
            allowed_mime_types=("image/png",),
        )


def test_download_rejects_oversized_output(tmp_path: Path):
    session = FakeSession()
    client = FalQueueClient("secret-value", session=session)
    session.get = lambda *args, **kwargs: FakeResponse(  # type: ignore[method-assign]
        {},
        content=b"x" * 32,
        content_type="image/png",
    )

    with pytest.raises(FalOutputError, match="fal_output_too_large"):
        client.download(
            "https://fal.media/files/test/image.png",
            tmp_path / "image.png",
            max_bytes=16,
            allowed_content_prefixes=("image/",),
        )


def test_result_dataclass_does_not_contain_credentials():
    result = FalJobResult(
        request_id="request-1",
        model_id="fal-ai/flux/dev",
        data={"images": []},
        elapsed_seconds=1.0,
        queue_seconds=0.2,
        execution_seconds=0.8,
        status_history=("COMPLETED",),
    )

    assert "Authorization" not in repr(result)


def test_schnell_default_cost_is_billed_per_megapixel(monkeypatch):
    monkeypatch.delenv("FAL_FLUX_USD_PER_MEGAPIXEL", raising=False)

    assert fal_provider.flux_cost_estimate_usd(768, 1024) == 0.003
    assert fal_provider.flux_cost_estimate_usd(1024, 1024) == 0.006


def test_instant_character_default_cost_is_billed_per_megapixel(monkeypatch):
    monkeypatch.delenv("FAL_INSTANT_CHARACTER_USD_PER_MEGAPIXEL", raising=False)

    assert fal_provider.instant_character_cost_estimate_usd(768, 1024) == 0.1
    assert fal_provider.instant_character_cost_estimate_usd(1024, 1024) == 0.2


def test_flux_pulid_default_cost_is_billed_per_megapixel(monkeypatch):
    monkeypatch.delenv("FAL_FLUX_PULID_USD_PER_MEGAPIXEL", raising=False)

    assert fal_provider.flux_pulid_cost_estimate_usd(768, 1024) == 0.0333
    assert fal_provider.flux_pulid_cost_estimate_usd(1024, 1024) == 0.0666


def test_nano_banana_default_cost_is_billed_per_image(monkeypatch):
    monkeypatch.delenv("FAL_NANO_BANANA_USD_PER_IMAGE", raising=False)

    assert fal_provider.nano_banana_edit_cost_estimate_usd() == 0.039
    assert fal_provider.nano_banana_edit_cost_estimate_usd(2) == 0.078
