#!/usr/bin/env python3
"""Export checksum-verified Cast Bible packs for one LoRA per character."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved_reference_path(run_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (run_dir / candidate).resolve()
    )
    if resolved != run_dir and run_dir not in resolved.parents:
        raise ValueError(f"reference_path_outside_run:{raw_path}")
    if not resolved.is_file() or resolved.stat().st_size <= 1000:
        raise ValueError(f"reference_file_invalid:{raw_path}")
    return resolved


def export_training_packs(summary_path: Path, output_dir: Path) -> list[Path]:
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"summary_invalid:{type(exc).__name__}") from exc
    cast_bible = summary.get("visual_bible", {}).get("cast_bible") or {}
    if cast_bible.get("schema_version") != "2.0":
        raise ValueError("cast_bible_v2_required")
    required_ids = {
        str(character_id)
        for character_id in cast_bible.get("required_for_scenes", [])
        if character_id
    }
    characters = [
        character
        for character in cast_bible.get("characters", [])
        if not required_ids or str(character.get("id")) in required_ids
    ]
    if not characters or len(characters) > 24:
        raise ValueError("cast_bible_character_count_invalid")

    run_dir = summary_path.parent.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    for character in characters:
        character_id = str(character.get("id") or "").strip()
        reference = character.get("reference") or {}
        if not character_id or reference.get("approved") is not True:
            raise ValueError(
                f"character_reference_not_approved:{character_id or 'unknown'}"
            )
        version = int(reference.get("version") or 0)
        if version < 1 or not reference.get("checksum"):
            raise ValueError(f"character_reference_version_invalid:{character_id}")
        required_views = list(reference.get("required_views") or [])
        views = reference.get("views") or {}
        if not required_views:
            raise ValueError(f"character_reference_views_missing:{character_id}")

        expected_adapter = f"char_{character_id}_v{version}.safetensors"
        trigger = f"char_{character_id}_v{version}"
        character_dir = output_dir / f"char_{character_id}_v{version}"
        images_dir = character_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        manifest_rows: list[dict[str, Any]] = []
        for view_id in required_views:
            view = views.get(view_id) or {}
            if view.get("approved") is not True or not view.get("checksum"):
                raise ValueError(
                    f"character_reference_view_not_approved:{character_id}:{view_id}"
                )
            source = _resolved_reference_path(run_dir, str(view.get("path") or ""))
            actual_checksum = _sha256(source)
            if actual_checksum != view["checksum"]:
                raise ValueError(
                    f"character_reference_checksum_mismatch:{character_id}:{view_id}"
                )
            destination = images_dir / f"{view_id}{source.suffix.lower()}"
            shutil.copy2(source, destination)
            caption = (
                f"{trigger}, {character.get('name') or character_id}, {view_id}, "
                f"{character.get('identity_prompt') or ''}"
            ).strip()
            destination.with_suffix(".txt").write_text(caption, encoding="utf-8")
            manifest_rows.append(
                {
                    "view_id": view_id,
                    "image": str(destination.relative_to(character_dir)),
                    "caption": caption,
                    "sha256": actual_checksum,
                }
            )

        manifest_path = character_dir / "manifest.jsonl"
        manifest_path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False) + "\n" for row in manifest_rows
            ),
            encoding="utf-8",
        )
        (character_dir / "training_spec.json").write_text(
            json.dumps(
                {
                    "cast_revision": cast_bible.get("revision"),
                    "character_id": character_id,
                    "character_name": character.get("name"),
                    "reference_version": version,
                    "reference_checksum": reference["checksum"],
                    "adapter_filename": expected_adapter,
                    "trigger_token": trigger,
                    "training_images": len(manifest_rows),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        exported.append(character_dir)
    return exported


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    packs = export_training_packs(args.summary.resolve(), args.output.resolve())
    for pack in packs:
        print(f"CAST_LORA_PACK_READY {pack}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
