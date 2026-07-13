#!/usr/bin/env python3
"""Control RunPod Serverless endpoint scale without exposing secrets."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "open3d_implementation" / ".env"
GRAPHQL_URL = "https://api.runpod.io/graphql"
HEALTH_URL_TEMPLATE = "https://api.runpod.ai/v2/{endpoint_id}/health"
CANCEL_URL_TEMPLATE = "https://api.runpod.ai/v2/{endpoint_id}/cancel/{job_id}"


def load_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def request_json(
    url: str,
    *,
    api_key: str,
    payload: Dict[str, Any] | None = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ai-film-runpod-control/1.0",
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error: {exc.reason}") from exc
    return json.loads(body or "{}")


def save_endpoint(
    *,
    api_key: str,
    endpoint_id: str,
    endpoint_name: str,
    workers_min: int,
    workers_max: int,
    locations: str,
) -> Dict[str, Any]:
    query = """
    mutation($input: EndpointInput!) {
      saveEndpoint(input: $input) {
        id
        name
        workersMin
        workersMax
        idleTimeout
        locations
        executionTimeoutMs
        gpuIds
        networkVolumeId
        scalerType
        scalerValue
      }
    }
    """
    payload = {
        "query": query,
        "variables": {
            "input": {
                "id": endpoint_id,
                "name": endpoint_name,
                "workersMin": workers_min,
                "workersMax": workers_max,
                "locations": locations,
            }
        },
    }
    result = request_json(GRAPHQL_URL, api_key=api_key, payload=payload)
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False)[:1000])
    endpoint = result.get("data", {}).get("saveEndpoint")
    if not endpoint:
        raise RuntimeError("RunPod did not return endpoint data")
    return endpoint


def endpoint_health(*, api_key: str, endpoint_id: str) -> Dict[str, Any]:
    return request_json(
        HEALTH_URL_TEMPLATE.format(endpoint_id=endpoint_id),
        api_key=api_key,
    )


def cancel_job(*, api_key: str, endpoint_id: str, job_id: str) -> Dict[str, Any]:
    return request_json(
        CANCEL_URL_TEMPLATE.format(endpoint_id=endpoint_id, job_id=job_id),
        api_key=api_key,
        payload={},
    )


def print_json(data: Dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Control RunPod Serverless endpoint workers safely."
    )
    parser.add_argument(
        "command",
        choices=("health", "stop", "test-capacity", "set-workers", "cancel-job"),
        help=(
            "health prints queue/worker state; stop sets min/max to 0; "
            "test-capacity sets min 0/max 1; set-workers uses explicit values; "
            "cancel-job cancels a specific RunPod job id."
        ),
    )
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--workers-min", type=int, default=None)
    parser.add_argument("--workers-max", type=int, default=None)
    parser.add_argument("--name", default="ai-film-comfyui")
    parser.add_argument(
        "--locations",
        default=None,
        help="RunPod data center string. Defaults to RUNPOD_NETWORK_VOLUME_DATACENTER.",
    )
    parser.add_argument(
        "--wait", type=int, default=0, help="Poll health for N seconds."
    )
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    api_key = env.get("RUNPOD_API_KEY", "")
    endpoint_id = env.get("RUNPOD_ENDPOINT_ID", "")
    if not api_key or not endpoint_id:
        print("RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID are required.", file=sys.stderr)
        return 2

    if args.command == "health":
        print_json(endpoint_health(api_key=api_key, endpoint_id=endpoint_id))
        return 0

    if args.command == "cancel-job":
        if not args.job_id:
            print("cancel-job requires --job-id.", file=sys.stderr)
            return 2
        print_json(
            {
                "cancel": cancel_job(
                    api_key=api_key,
                    endpoint_id=endpoint_id,
                    job_id=args.job_id,
                )
            }
        )
        return 0

    if args.command == "stop":
        workers_min, workers_max = 0, 0
    elif args.command == "test-capacity":
        workers_min, workers_max = 0, 1
    else:
        if args.workers_min is None or args.workers_max is None:
            print(
                "set-workers requires --workers-min and --workers-max.",
                file=sys.stderr,
            )
            return 2
        workers_min, workers_max = args.workers_min, args.workers_max

    endpoint = save_endpoint(
        api_key=api_key,
        endpoint_id=endpoint_id,
        endpoint_name=args.name,
        workers_min=workers_min,
        workers_max=workers_max,
        locations=args.locations
        or env.get("RUNPOD_NETWORK_VOLUME_DATACENTER", "EUR-IS-1"),
    )
    print_json({"endpoint": endpoint})

    deadline = time.monotonic() + max(args.wait, 0)
    while time.monotonic() < deadline:
        time.sleep(min(10, max(1, int(deadline - time.monotonic()))))
        print_json(
            {"health": endpoint_health(api_key=api_key, endpoint_id=endpoint_id)}
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
