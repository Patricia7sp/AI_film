#!/usr/bin/env python3
"""Create a checksum-verified allowlist for resuming partial Cast Bible runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUN_ID_PATTERN = re.compile(r"^\d{8}_\d{6}_[0-9a-f]{8}$")
SOURCE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_-]{0,63}_character_reference_"
    r"(?:front|three_quarter|profile|full_body|expression_neutral|"
    r"expression_warm|expression_concerned)(?:_attempt_[2-9][0-9]*)?\.png$"
)
DESTINATION_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_-]{0,63}_character_reference_"
    r"(?:front|three_quarter|profile|full_body|expression_neutral|"
    r"expression_warm|expression_concerned)\.png$"
)
SCHEMA_VERSION = "1.0"
MANIFEST_NAME = "cast_reference_resume_manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_output_asset(output_dir: Path, name: str) -> Path:
    if not SOURCE_PATTERN.fullmatch(name):
        raise ValueError(f"invalid_source_name:{name}")
    path = (output_dir / name).resolve()
    if path.parent != output_dir or not path.is_file():
        raise ValueError(f"source_asset_missing:{name}")
    if not 1000 < path.stat().st_size <= 20 * 1024 * 1024:
        raise ValueError(f"source_asset_size_invalid:{name}")
    return path


def _summary_assets(summary_path: Path, output_dir: Path) -> list[dict[str, Any]]:
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"summary_invalid:{type(exc).__name__}") from exc
    characters = (
        summary.get("visual_bible", {}).get("cast_bible", {}).get("characters", [])
    )
    assets: list[dict[str, Any]] = []
    for character in characters[:64] if isinstance(characters, list) else []:
        character_id = str(character.get("id") or "")
        views = (character.get("reference") or {}).get("views", {})
        for view_id, view in (
            list(views.items())[:16] if isinstance(views, dict) else []
        ):
            if not isinstance(view, dict) or view.get("automatic_approved") is not True:
                continue
            destination_name = f"{character_id}_character_reference_{view_id}.png"
            if not DESTINATION_PATTERN.fullmatch(destination_name):
                raise ValueError(f"summary_destination_invalid:{destination_name}")
            name = Path(str(view.get("path") or "")).name
            if not SOURCE_PATTERN.fullmatch(name):
                name = destination_name
            path = _validated_output_asset(output_dir, name)
            expected = str(view.get("checksum") or "").lower()
            actual = _sha256(path)
            if not re.fullmatch(r"[0-9a-f]{64}", expected) or expected != actual:
                raise ValueError(f"summary_checksum_mismatch:{name}")
            assets.append(
                {
                    "source_name": name,
                    "destination_name": destination_name,
                    "sha256": actual,
                    "validated": True,
                    "validation_source": "automatic_gate",
                }
            )
    return assets


def create_manifest(
    run_dir: Path,
    *,
    approved_summary: Path | None,
    overrides: list[str],
) -> Path:
    run_dir = run_dir.resolve()
    if not RUN_ID_PATTERN.fullmatch(run_dir.name) or not run_dir.is_dir():
        raise ValueError("invalid_run_dir")
    output_dir = (run_dir / "output").resolve()
    if not output_dir.is_dir():
        raise ValueError("run_output_missing")

    assets = (
        _summary_assets(approved_summary.resolve(), output_dir)
        if approved_summary
        else []
    )
    by_destination = {asset["destination_name"]: asset for asset in assets}
    for override in overrides:
        source_name, separator, destination_name = override.partition("=")
        if not separator:
            raise ValueError(f"invalid_asset_override:{override}")
        if not DESTINATION_PATTERN.fullmatch(destination_name):
            raise ValueError(f"invalid_destination_name:{destination_name}")
        source = _validated_output_asset(output_dir, source_name)
        by_destination[destination_name] = {
            "source_name": source_name,
            "destination_name": destination_name,
            "sha256": _sha256(source),
            "validated": True,
            "validation_source": "local_quality_and_identity_gate",
        }
    if not by_destination:
        raise ValueError("resume_manifest_empty")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": run_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": [by_destination[name] for name in sorted(by_destination)],
    }
    manifest_path = run_dir / MANIFEST_NAME
    temp_path = manifest_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(manifest_path)
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--approved-summary", type=Path)
    parser.add_argument(
        "--asset",
        action="append",
        default=[],
        help="Validated source_name=canonical_destination_name; repeat as needed.",
    )
    args = parser.parse_args()
    manifest = create_manifest(
        args.run_dir,
        approved_summary=args.approved_summary,
        overrides=args.asset,
    )
    print(f"CAST_RESUME_MANIFEST_READY {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
