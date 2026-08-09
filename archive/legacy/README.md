# Legacy archive

This directory preserves retired project surfaces for historical reference only.
Nothing below this directory may be imported, installed, linted, packaged, or
deployed by the active AI Film pipeline.

## Archived

- `tooling/agent-framework/`: the former `.agent` prompt, workflow, and helper
  bundle. No active runtime, CI, or deployment entrypoint references it.

## Not archived yet

Blender remains coupled to historical entrypoints in `app/main.py`, the
`blender` optional dependency, README instructions, and local deployment files.
It must be retired as one vertical slice after those entrypoints are replaced;
moving individual Blender files now would create a broken half-migration.

The ignored `.venv_blender_mcp` directory is a local generated environment. It
is not source code and is not transferred by Git. Remove it only through an
explicit local cleanup operation.
