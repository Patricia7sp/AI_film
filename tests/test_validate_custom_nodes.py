from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_validator() -> ModuleType:
    validator_path = (
        Path(__file__).resolve().parents[1]
        / "runpod_worker"
        / "validate_custom_nodes.py"
    )
    spec = importlib.util.spec_from_file_location(
        "ai_film_validate_custom_nodes_test",
        validator_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the custom-node validator for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()
load_ipadapter_module = VALIDATOR.load_ipadapter_module
validate_ipadapter_nodes = VALIDATOR.validate_ipadapter_nodes


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ipadapter_validation_imports_comfyui_in_cpu_mode(
    tmp_path: Path,
) -> None:
    comfyui_root = tmp_path / "comfyui"
    ipadapter_root = comfyui_root / "custom_nodes" / "comfyui-ipadapter"
    _write(comfyui_root / "comfy" / "__init__.py", "")
    _write(
        comfyui_root / "comfy" / "options.py",
        "args_parsing = False\n"
        "def enable_args_parsing(enable=True):\n"
        "    global args_parsing\n"
        "    args_parsing = enable\n",
    )
    _write(
        comfyui_root / "comfy" / "cli_args.py",
        "import sys\n"
        "from . import options\n"
        "if not options.args_parsing or sys.argv[1:] != ['--cpu']:\n"
        "    raise RuntimeError('cpu_mode_not_enabled')\n"
        "class Args:\n"
        "    cpu = True\n"
        "args = Args()\n",
    )
    _write(
        ipadapter_root / "__init__.py",
        "from comfy.cli_args import args\n"
        "if not args.cpu:\n"
        "    raise RuntimeError('gpu_import_attempted')\n"
        "NODE_CLASS_MAPPINGS = {\n"
        "    'IPAdapterUnifiedLoader': object,\n"
        "    'IPAdapterAdvanced': object,\n"
        "}\n",
    )

    original_argv = list(sys.argv)
    original_modules = set(sys.modules)
    try:
        module = load_ipadapter_module(
            comfyui_root=comfyui_root,
            ipadapter_root=ipadapter_root,
        )
        validate_ipadapter_nodes(module)
        assert sys.argv == original_argv
    finally:
        for module_name in set(sys.modules).difference(original_modules):
            if module_name == "comfy" or module_name.startswith("comfy."):
                sys.modules.pop(module_name, None)
            if module_name.startswith("ai_film_ipadapter_build_validation"):
                sys.modules.pop(module_name, None)
