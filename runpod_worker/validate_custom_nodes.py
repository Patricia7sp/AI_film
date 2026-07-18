#!/usr/bin/env python3
"""Fail the worker image build when required ComfyUI custom nodes cannot load."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Mapping

COMFYUI_ROOT = Path("/comfyui")
IPADAPTER_ROOT = COMFYUI_ROOT / "custom_nodes" / "comfyui-ipadapter"
REQUIRED_IPADAPTER_NODES = frozenset(
    {
        "IPAdapterUnifiedLoader",
        "IPAdapterAdvanced",
    }
)


def load_ipadapter_module(
    *,
    comfyui_root: Path = COMFYUI_ROOT,
    ipadapter_root: Path = IPADAPTER_ROOT,
) -> ModuleType:
    init_path = ipadapter_root / "__init__.py"
    if not init_path.is_file():
        raise RuntimeError(f"IP-Adapter package missing: {init_path}")
    sys.path.insert(0, str(comfyui_root))
    module_name = "ai_film_ipadapter_build_validation"
    spec = importlib.util.spec_from_file_location(
        module_name,
        init_path,
        submodule_search_locations=[str(ipadapter_root)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to create the IP-Adapter import specification.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def validate_ipadapter_nodes(module: ModuleType) -> None:
    mappings = getattr(module, "NODE_CLASS_MAPPINGS", None)
    if not isinstance(mappings, Mapping):
        raise RuntimeError("IP-Adapter did not export NODE_CLASS_MAPPINGS.")
    missing = sorted(REQUIRED_IPADAPTER_NODES.difference(mappings))
    if missing:
        raise RuntimeError("Required IP-Adapter nodes missing: " + ", ".join(missing))


def main() -> int:
    module = load_ipadapter_module()
    validate_ipadapter_nodes(module)
    print("AI_FILM_CUSTOM_NODES_OK=" + ",".join(sorted(REQUIRED_IPADAPTER_NODES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
