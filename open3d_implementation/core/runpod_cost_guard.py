"""Fail-closed RunPod cost admission for expensive image jobs."""

from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass
from typing import Mapping

import requests

RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"
RUNPOD_ENDPOINT_URL = "https://rest.runpod.io/v1/endpoints/{endpoint_id}"
_ACCOUNT_QUERY = """
query AccountCost {
  myself {
    clientBalance
    currentSpendPerHr
    spendLimit
  }
}
"""

_RESERVATION_LOCK = threading.Lock()
_RESERVED_USD_BY_SCOPE: dict[str, float] = {}


class RunPodCostGuardError(RuntimeError):
    """Raised before submission when a RunPod cost invariant is not satisfied."""


@dataclass(frozen=True)
class RunPodAccountCost:
    balance_usd: float
    current_spend_per_hour_usd: float
    provider_spend_limit_per_hour_usd: float

    def public_dict(self) -> dict[str, float]:
        return {
            "balance_usd": round(self.balance_usd, 6),
            "current_spend_per_hour_usd": round(
                self.current_spend_per_hour_usd,
                6,
            ),
            "provider_spend_limit_per_hour_usd": round(
                self.provider_spend_limit_per_hour_usd,
                6,
            ),
        }


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(
    name: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        value = default
    if not math.isfinite(value):
        value = default
    return max(minimum, min(value, maximum))


def runpod_cost_guard_enabled() -> bool:
    return _env_flag("AI_FILM_RUNPOD_HARD_COST_GUARD_ENABLED", False)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise RunPodCostGuardError(f"runpod_cost_guard_invalid_{label}")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunPodCostGuardError(f"runpod_cost_guard_invalid_{label}")
    number = float(value)
    if not math.isfinite(number):
        raise RunPodCostGuardError(f"runpod_cost_guard_invalid_{label}")
    return number


def fetch_runpod_account_cost(
    api_key: str,
    *,
    timeout_seconds: float = 10.0,
) -> RunPodAccountCost:
    if not api_key.strip():
        raise RunPodCostGuardError("runpod_cost_guard_api_key_missing")
    try:
        response = requests.post(
            RUNPOD_GRAPHQL_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"query": _ACCOUNT_QUERY},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RunPodCostGuardError(
            f"runpod_cost_guard_account_unreachable:{type(exc).__name__}"
        ) from exc

    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RunPodCostGuardError("runpod_cost_guard_account_invalid_json") from exc
    root = _mapping(payload, "account_payload")
    if root.get("errors"):
        raise RunPodCostGuardError("runpod_cost_guard_account_graphql_error")
    data = _mapping(root.get("data"), "account_data")
    account = _mapping(data.get("myself"), "account")
    return RunPodAccountCost(
        balance_usd=_number(account.get("clientBalance"), "balance"),
        current_spend_per_hour_usd=_number(
            account.get("currentSpendPerHr"),
            "current_spend",
        ),
        provider_spend_limit_per_hour_usd=_number(
            account.get("spendLimit"),
            "provider_spend_limit",
        ),
    )


def fetch_runpod_endpoint_workers_max(
    api_key: str,
    endpoint_id: str,
    *,
    timeout_seconds: float = 10.0,
) -> int:
    if not endpoint_id.strip():
        raise RunPodCostGuardError("runpod_cost_guard_endpoint_missing")
    try:
        response = requests.get(
            RUNPOD_ENDPOINT_URL.format(endpoint_id=endpoint_id),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RunPodCostGuardError(
            f"runpod_cost_guard_endpoint_unreachable:{type(exc).__name__}"
        ) from exc

    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RunPodCostGuardError("runpod_cost_guard_endpoint_invalid_json") from exc
    endpoint = _mapping(payload, "endpoint_payload")
    workers_max = endpoint.get("workersMax")
    if isinstance(workers_max, bool) or not isinstance(workers_max, int):
        raise RunPodCostGuardError("runpod_cost_guard_invalid_workers_max")
    return workers_max


def inspect_runpod_cost_admission(
    *,
    api_key: str,
    endpoint_ids: list[str],
) -> dict[str, object]:
    """Return a secret-free account/worker preflight without reserving budget."""
    if not runpod_cost_guard_enabled():
        return {
            "status": "disabled",
            "blockers": [],
            "warnings": [],
        }

    minimum_balance = _env_float(
        "AI_FILM_RUNPOD_MIN_BALANCE_USD",
        2.0,
        minimum=0.0,
        maximum=10_000.0,
    )
    max_workers_allowed = int(
        _env_float(
            "AI_FILM_RUNPOD_MAX_WORKERS_ALLOWED",
            1.0,
            minimum=1.0,
            maximum=8.0,
        )
    )
    account = fetch_runpod_account_cost(api_key)
    blockers: list[dict[str, object]] = []
    endpoint_rows: list[dict[str, object]] = []
    if account.balance_usd <= minimum_balance:
        blockers.append(
            {
                "code": "runpod_balance_floor",
                "message": (
                    "Saldo RunPod abaixo da reserva mínima configurada para execução"
                ),
                "blocking": True,
            }
        )
    for endpoint_id in sorted(set(endpoint_ids))[:8]:
        workers_max = fetch_runpod_endpoint_workers_max(api_key, endpoint_id)
        endpoint_rows.append(
            {
                "endpoint_suffix": endpoint_id[-6:],
                "workers_max": workers_max,
            }
        )
        if workers_max > max_workers_allowed:
            blockers.append(
                {
                    "code": "runpod_workers_over_limit",
                    "message": ("Endpoint RunPod excede o máximo de workers permitido"),
                    "blocking": True,
                    "endpoint_suffix": endpoint_id[-6:],
                    "workers_max": workers_max,
                    "workers_allowed": max_workers_allowed,
                }
            )
    return {
        "status": "blocked" if blockers else "ready",
        "blockers": blockers,
        "warnings": [],
        "account": account.public_dict(),
        "minimum_balance_usd": minimum_balance,
        "endpoints": endpoint_rows,
    }


def reserve_runpod_job_budget(
    *,
    api_key: str,
    endpoint_id: str,
    budget_scope: str,
    estimated_max_cost_usd: float,
) -> dict[str, object]:
    """Atomically reserve one job against live balance and a process run budget."""
    if not runpod_cost_guard_enabled():
        return {
            "status": "disabled",
            "reserved_usd": 0.0,
        }
    if not budget_scope.strip():
        raise RunPodCostGuardError("runpod_cost_guard_budget_scope_missing")
    if not math.isfinite(estimated_max_cost_usd) or estimated_max_cost_usd <= 0:
        raise RunPodCostGuardError("runpod_cost_guard_invalid_job_estimate")

    hard_budget = _env_float(
        "AI_FILM_RUNPOD_HARD_BUDGET_USD",
        _env_float(
            "AI_FILM_RUNPOD_COST_LIMIT_USD",
            0.75,
            minimum=0.01,
            maximum=10_000.0,
        ),
        minimum=0.01,
        maximum=10_000.0,
    )
    minimum_balance = _env_float(
        "AI_FILM_RUNPOD_MIN_BALANCE_USD",
        2.0,
        minimum=0.0,
        maximum=10_000.0,
    )
    max_workers_allowed = int(
        _env_float(
            "AI_FILM_RUNPOD_MAX_WORKERS_ALLOWED",
            1.0,
            minimum=1.0,
            maximum=8.0,
        )
    )

    with _RESERVATION_LOCK:
        account = fetch_runpod_account_cost(api_key)
        workers_max = fetch_runpod_endpoint_workers_max(api_key, endpoint_id)
        if workers_max > max_workers_allowed:
            raise RunPodCostGuardError(
                "runpod_cost_guard_workers_over_limit:"
                f"{workers_max}>{max_workers_allowed}"
            )
        if workers_max < 1:
            raise RunPodCostGuardError("runpod_cost_guard_endpoint_paused")

        already_reserved = _RESERVED_USD_BY_SCOPE.get(budget_scope, 0.0)
        proposed_total = already_reserved + estimated_max_cost_usd
        if proposed_total > hard_budget + 1e-9:
            raise RunPodCostGuardError(
                "runpod_cost_guard_run_budget_exceeded:"
                f"{proposed_total:.4f}>{hard_budget:.4f}"
            )
        if account.balance_usd - estimated_max_cost_usd < minimum_balance:
            raise RunPodCostGuardError(
                "runpod_cost_guard_balance_floor:"
                f"{account.balance_usd:.4f}-{estimated_max_cost_usd:.4f}"
                f"<{minimum_balance:.4f}"
            )

        _RESERVED_USD_BY_SCOPE[budget_scope] = proposed_total
        return {
            "status": "reserved",
            "reserved_usd": round(estimated_max_cost_usd, 6),
            "run_reserved_usd": round(proposed_total, 6),
            "run_hard_budget_usd": round(hard_budget, 6),
            "balance_before_usd": round(account.balance_usd, 6),
            "minimum_balance_usd": round(minimum_balance, 6),
            "workers_max": workers_max,
        }


def settle_runpod_job_budget(
    *,
    budget_scope: str,
    reserved_usd: float,
    actual_cost_usd: float,
) -> dict[str, object]:
    """Replace a conservative reservation with the provider execution cost."""
    if not runpod_cost_guard_enabled():
        return {
            "status": "disabled",
            "run_accounted_usd": 0.0,
        }
    if not budget_scope.strip():
        raise RunPodCostGuardError("runpod_cost_guard_budget_scope_missing")
    if (
        not math.isfinite(reserved_usd)
        or reserved_usd < 0
        or not math.isfinite(actual_cost_usd)
        or actual_cost_usd < 0
    ):
        raise RunPodCostGuardError("runpod_cost_guard_invalid_settlement")

    with _RESERVATION_LOCK:
        current = _RESERVED_USD_BY_SCOPE.get(budget_scope, 0.0)
        accounted = max(0.0, current - reserved_usd) + actual_cost_usd
        _RESERVED_USD_BY_SCOPE[budget_scope] = accounted
        return {
            "status": "settled",
            "reserved_usd": round(reserved_usd, 6),
            "actual_cost_usd": round(actual_cost_usd, 6),
            "run_accounted_usd": round(accounted, 6),
        }


def reset_runpod_cost_reservations_for_tests() -> None:
    with _RESERVATION_LOCK:
        _RESERVED_USD_BY_SCOPE.clear()
