"""Secure, bounded fal.ai queue client for image and video generation."""

from __future__ import annotations

import base64
import ipaddress
import math
import mimetypes
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, TypeAlias
from urllib.parse import urlparse

import requests

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]

_MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{2,180}$")
_TERMINAL_SUCCESS = {"COMPLETED", "COMPLETE", "SUCCEEDED", "SUCCESS"}
_TERMINAL_FAILURE = {"FAILED", "FAILURE", "CANCELLED", "CANCELED"}
_DEFAULT_OUTPUT_HOST_SUFFIXES = (
    "fal.media",
    "fal.run",
    "storage.googleapis.com",
)


class FalProviderError(RuntimeError):
    """Base error for fal.ai provider failures."""


class FalConfigurationError(FalProviderError):
    """Raised when required provider configuration is invalid."""


class FalAuthenticationError(FalProviderError):
    """Raised when fal.ai rejects the configured credential."""


class FalRequestError(FalProviderError):
    """Raised when fal.ai rejects or fails a queue request."""


class FalTransientRequestError(FalRequestError):
    """Raised when a fal.ai request can be retried without resubmitting the job."""


class FalTimeoutError(FalProviderError):
    """Raised when queue or execution exceeds a configured deadline."""


class FalOutputError(FalProviderError):
    """Raised when a provider response does not contain a usable artifact."""


class FalSecurityError(FalProviderError):
    """Raised when an external URL violates the provider allowlist."""


@dataclass(frozen=True)
class FalSubmission:
    request_id: str
    status_url: str
    response_url: str
    cancel_url: str | None


@dataclass(frozen=True)
class FalJobResult:
    request_id: str
    model_id: str
    data: JsonObject
    elapsed_seconds: float
    queue_seconds: float
    execution_seconds: float
    status_history: tuple[str, ...]


def _json_object(response: requests.Response) -> JsonObject:
    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as exc:
        raise FalRequestError(
            f"fal_invalid_json_response:http_{response.status_code}"
        ) from exc
    if not isinstance(payload, dict):
        raise FalRequestError("fal_response_is_not_an_object")
    return payload


def _safe_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError:
        return f"http_{response.status_code}"
    if not isinstance(payload, dict):
        return f"http_{response.status_code}"
    detail = payload.get("detail") or payload.get("error") or payload.get("message")
    return str(detail or f"http_{response.status_code}")[:500]


def _raise_for_fal_status(response: requests.Response) -> None:
    if response.status_code in {401, 403}:
        raise FalAuthenticationError(
            f"fal_authentication_failed:http_{response.status_code}:"
            f"{_safe_error_detail(response)}"
        )
    if response.status_code >= 400:
        raise FalRequestError(
            f"fal_request_failed:http_{response.status_code}:"
            f"{_safe_error_detail(response)}"
        )


def _validated_model_id(model_id: str) -> str:
    normalized = model_id.strip().strip("/")
    if not _MODEL_ID_PATTERN.fullmatch(normalized) or ".." in normalized:
        raise FalConfigurationError("invalid_fal_model_id")
    return normalized


def _allowed_host_suffixes() -> tuple[str, ...]:
    configured = os.getenv("FAL_OUTPUT_HOST_SUFFIXES", "").strip()
    if not configured:
        return _DEFAULT_OUTPUT_HOST_SUFFIXES
    suffixes = tuple(
        item.strip().lower().lstrip(".")
        for item in configured.split(",")
        if item.strip()
    )
    if not suffixes:
        raise FalConfigurationError("fal_output_host_allowlist_empty")
    return suffixes


def _host_matches_suffix(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith(f".{suffix}")


def validate_external_url(
    url: str,
    *,
    allowed_host_suffixes: Sequence[str] | None = None,
) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        raise FalSecurityError("fal_external_url_must_be_https")
    host = parsed.hostname.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    ):
        raise FalSecurityError("fal_external_url_private_address")
    suffixes = tuple(allowed_host_suffixes or _allowed_host_suffixes())
    if not any(_host_matches_suffix(host, suffix) for suffix in suffixes):
        raise FalSecurityError(f"fal_external_url_host_not_allowed:{host}")
    return url


def file_to_data_uri(
    path: str | Path,
    *,
    max_bytes: int,
    allowed_mime_types: Sequence[str],
) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        raise FalConfigurationError(f"fal_input_file_missing:{file_path.name}")
    size = file_path.stat().st_size
    if size <= 0 or size > max_bytes:
        raise FalConfigurationError(
            f"fal_input_file_size_invalid:{file_path.name}:{size}"
        )
    mime_type = mimetypes.guess_type(file_path.name)[0] or ""
    if mime_type not in set(allowed_mime_types):
        raise FalConfigurationError(
            f"fal_input_file_type_invalid:{file_path.name}:{mime_type or 'unknown'}"
        )
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def extract_image_url(payload: Mapping[str, JsonValue]) -> str:
    images = payload.get("images")
    if not isinstance(images, list) or not images:
        raise FalOutputError("fal_image_output_missing")
    first = images[0]
    if not isinstance(first, dict) or not isinstance(first.get("url"), str):
        raise FalOutputError("fal_image_url_missing")
    return validate_external_url(str(first["url"]))


def extract_video_url(payload: Mapping[str, JsonValue]) -> str:
    video = payload.get("video")
    if not isinstance(video, dict) or not isinstance(video.get("url"), str):
        raise FalOutputError("fal_video_url_missing")
    return validate_external_url(str(video["url"]))


def flux_cost_estimate_usd(width: int, height: int) -> float:
    usd_per_megapixel = float(os.getenv("FAL_FLUX_USD_PER_MEGAPIXEL", "0.003"))
    billed_megapixels = max(1, math.ceil((width * height) / 1_000_000))
    return round(billed_megapixels * max(0.0, usd_per_megapixel), 6)


def instant_character_cost_estimate_usd(width: int, height: int) -> float:
    usd_per_megapixel = float(
        os.getenv("FAL_INSTANT_CHARACTER_USD_PER_MEGAPIXEL", "0.10")
    )
    billed_megapixels = max(1, math.ceil((width * height) / 1_000_000))
    return round(billed_megapixels * max(0.0, usd_per_megapixel), 6)


def flux_pulid_cost_estimate_usd(width: int, height: int) -> float:
    usd_per_megapixel = float(os.getenv("FAL_FLUX_PULID_USD_PER_MEGAPIXEL", "0.0333"))
    billed_megapixels = max(1, math.ceil((width * height) / 1_000_000))
    return round(billed_megapixels * max(0.0, usd_per_megapixel), 6)


def nano_banana_edit_cost_estimate_usd(num_images: int = 1) -> float:
    usd_per_image = float(os.getenv("FAL_NANO_BANANA_USD_PER_IMAGE", "0.039"))
    return round(max(0, num_images) * max(0.0, usd_per_image), 6)


def kling_video_cost_estimate_usd(duration_seconds: int) -> float:
    usd_per_second = float(os.getenv("FAL_KLING_USD_PER_SECOND", "0.084"))
    return round(max(0, duration_seconds) * max(0.0, usd_per_second), 6)


def kling_lipsync_cost_estimate_usd(duration_seconds: float) -> float:
    usd_per_second = float(os.getenv("FAL_KLING_LIPSYNC_USD_PER_SECOND", "0.014"))
    billed_seconds = max(5, math.ceil(max(0.0, duration_seconds) / 5) * 5)
    return round(billed_seconds * max(0.0, usd_per_second), 6)


class FalQueueClient:
    """Minimal fal.ai REST queue client with strict time and output bounds."""

    def __init__(
        self,
        api_key: str,
        *,
        session: requests.Session | None = None,
        request_timeout_seconds: float | None = None,
    ) -> None:
        credential = api_key.strip()
        if not credential:
            raise FalConfigurationError("missing_fal_key")
        self._api_key = credential
        self._session = session or requests.Session()
        configured_timeout = request_timeout_seconds or float(
            os.getenv("FAL_HTTP_TIMEOUT_SECONDS", "30")
        )
        self._request_timeout_seconds = min(120.0, max(5.0, configured_timeout))

    @classmethod
    def from_environment(cls) -> "FalQueueClient":
        return cls(os.getenv("FAL_KEY", ""))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Key {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def submit(self, model_id: str, inputs: Mapping[str, JsonValue]) -> FalSubmission:
        validated_model = _validated_model_id(model_id)
        if not inputs:
            raise FalConfigurationError("fal_inputs_empty")
        submit_url = f"https://queue.fal.run/{validated_model}"
        try:
            response = self._session.post(
                submit_url,
                headers=self._headers(),
                json=dict(inputs),
                timeout=self._request_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise FalRequestError(
                f"fal_submit_transport_error:{type(exc).__name__}"
            ) from exc
        _raise_for_fal_status(response)
        payload = _json_object(response)
        request_id = str(payload.get("request_id") or "").strip()
        status_url = str(payload.get("status_url") or "").strip()
        response_url = str(payload.get("response_url") or "").strip()
        cancel_url_value = str(payload.get("cancel_url") or "").strip()
        if not request_id or not status_url or not response_url:
            raise FalRequestError("fal_submission_contract_invalid")
        validate_external_url(status_url, allowed_host_suffixes=("fal.run",))
        validate_external_url(response_url, allowed_host_suffixes=("fal.run",))
        if cancel_url_value:
            validate_external_url(cancel_url_value, allowed_host_suffixes=("fal.run",))
        return FalSubmission(
            request_id=request_id,
            status_url=status_url,
            response_url=response_url,
            cancel_url=cancel_url_value or None,
        )

    def _get(self, url: str) -> requests.Response:
        try:
            response = self._session.get(
                url,
                headers=self._headers(),
                timeout=self._request_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise FalTransientRequestError(
                f"fal_poll_transport_error:{type(exc).__name__}"
            ) from exc
        if response.status_code >= 500:
            raise FalTransientRequestError(
                f"fal_poll_provider_error:http_{response.status_code}:"
                f"{_safe_error_detail(response)}"
            )
        _raise_for_fal_status(response)
        return response

    def cancel(self, submission: FalSubmission) -> None:
        if not submission.cancel_url:
            return
        try:
            response = self._session.put(
                submission.cancel_url,
                headers=self._headers(),
                timeout=self._request_timeout_seconds,
            )
        except requests.RequestException:
            return
        if response.status_code in {401, 403}:
            raise FalAuthenticationError(
                f"fal_authentication_failed:http_{response.status_code}"
            )

    def run(
        self,
        model_id: str,
        inputs: Mapping[str, JsonValue],
        *,
        queue_timeout_seconds: float | None = None,
        execution_timeout_seconds: float | None = None,
        poll_interval_seconds: float | None = None,
    ) -> FalJobResult:
        validated_model = _validated_model_id(model_id)
        queue_timeout = max(
            5.0,
            queue_timeout_seconds
            or float(os.getenv("FAL_QUEUE_TIMEOUT_SECONDS", "900")),
        )
        execution_timeout = max(
            5.0,
            execution_timeout_seconds
            or float(os.getenv("FAL_EXECUTION_TIMEOUT_SECONDS", "1200")),
        )
        poll_interval = min(
            30.0,
            max(
                0.1,
                poll_interval_seconds
                or float(os.getenv("FAL_POLL_INTERVAL_SECONDS", "3")),
            ),
        )
        started_at = time.monotonic()
        execution_started_at: float | None = None
        history: list[str] = []
        submission = self.submit(validated_model, inputs)
        try:
            poll_request_attempts = int(
                os.getenv("FAL_POLL_REQUEST_RETRY_ATTEMPTS", "3")
            )
        except ValueError as exc:
            self.cancel(submission)
            raise FalConfigurationError(
                "invalid_fal_poll_request_retry_attempts"
            ) from exc
        poll_request_attempts = max(1, min(8, poll_request_attempts))

        def get_job_payload(url: str) -> JsonObject:
            for request_attempt in range(1, poll_request_attempts + 1):
                try:
                    return _json_object(self._get(url))
                except FalTransientRequestError:
                    if request_attempt >= poll_request_attempts:
                        self.cancel(submission)
                        raise
                    retry_delay = min(
                        30.0,
                        poll_interval * (2 ** (request_attempt - 1)),
                    )
                    time.sleep(retry_delay)
                except (FalAuthenticationError, FalRequestError):
                    self.cancel(submission)
                    raise
            self.cancel(submission)
            raise FalRequestError("fal_poll_retry_exhausted")

        while True:
            payload = get_job_payload(submission.status_url)
            status = str(payload.get("status") or "UNKNOWN").upper()
            if not history or history[-1] != status:
                history.append(status)
            now = time.monotonic()
            if status in _TERMINAL_SUCCESS:
                result_payload = get_job_payload(submission.response_url)
                data = result_payload.get("data")
                normalized_data = data if isinstance(data, dict) else result_payload
                queue_seconds = (
                    max(0.0, execution_started_at - started_at)
                    if execution_started_at is not None
                    else max(0.0, now - started_at)
                )
                execution_seconds = (
                    max(0.0, now - execution_started_at)
                    if execution_started_at is not None
                    else 0.0
                )
                return FalJobResult(
                    request_id=submission.request_id,
                    model_id=validated_model,
                    data=normalized_data,
                    elapsed_seconds=round(now - started_at, 3),
                    queue_seconds=round(queue_seconds, 3),
                    execution_seconds=round(execution_seconds, 3),
                    status_history=tuple(history),
                )
            if status in _TERMINAL_FAILURE:
                detail = payload.get("error") or payload.get("detail") or status
                raise FalRequestError(
                    f"fal_job_failed:{submission.request_id}:{str(detail)[:500]}"
                )
            if status == "IN_PROGRESS" and execution_started_at is None:
                execution_started_at = now
            if execution_started_at is None and now - started_at >= queue_timeout:
                self.cancel(submission)
                raise FalTimeoutError(
                    f"fal_queue_timeout:{submission.request_id}:{int(queue_timeout)}s"
                )
            if (
                execution_started_at is not None
                and now - execution_started_at >= execution_timeout
            ):
                self.cancel(submission)
                raise FalTimeoutError(
                    f"fal_execution_timeout:{submission.request_id}:"
                    f"{int(execution_timeout)}s"
                )
            time.sleep(poll_interval)

    def download(
        self,
        url: str,
        destination: str | Path,
        *,
        max_bytes: int,
        allowed_content_prefixes: Sequence[str],
    ) -> int:
        validated_url = validate_external_url(url)
        try:
            response = self._session.get(
                validated_url,
                headers={"Accept": "*/*"},
                timeout=max(120.0, self._request_timeout_seconds),
                stream=True,
            )
        except requests.RequestException as exc:
            raise FalRequestError(
                f"fal_download_transport_error:{type(exc).__name__}"
            ) from exc
        _raise_for_fal_status(response)
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if content_type and not any(
            content_type.startswith(prefix) for prefix in allowed_content_prefixes
        ):
            raise FalOutputError(f"fal_output_content_type_invalid:{content_type}")
        declared_size = int(response.headers.get("Content-Length") or 0)
        if declared_size > max_bytes:
            raise FalOutputError(f"fal_output_too_large:{declared_size}")
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = destination_path.with_suffix(f"{destination_path.suffix}.part")
        written = 0
        try:
            with temporary_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > max_bytes:
                        raise FalOutputError(f"fal_output_too_large:{written}")
                    handle.write(chunk)
            if written <= 0:
                raise FalOutputError("fal_output_empty")
            temporary_path.replace(destination_path)
        except (OSError, FalOutputError):
            temporary_path.unlink(missing_ok=True)
            raise
        return written
