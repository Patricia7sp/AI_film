#!/usr/bin/env python3
"""Local UI for testing the AI film pipeline.

This server is intentionally local-only. It lets the owner upload a story,
launch the real LangGraph pipeline in the background, retry a failed run, and
inspect generated assets without exposing secrets.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, request, send_file

REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN3D_ROOT = Path(__file__).resolve().parent
STORY_PATH = REPO_ROOT / "data" / "historia.txt"
RUNS_ROOT = Path(os.getenv("AI_FILM_RUNS_ROOT", "/tmp/ai_film_ui_runs"))
ALLOWED_IMAGE_STYLES = {
    "cinematic_realism",
    "storybook_animation",
    "editorial_black_white",
    "watercolor_illustration",
    "anime_cinematic",
}
ALLOWED_IMAGE_QUALITY_PRESETS = {"balanced", "high"}

load_dotenv(OPEN3D_ROOT / ".env", override=True)
if os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(OPEN3D_ROOT))

app = Flask(__name__)
RUNS_ROOT.mkdir(parents=True, exist_ok=True)

RUNS: dict[str, dict[str, Any]] = {}
RUN_LOCK = threading.Lock()


INDEX_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Film Pipeline</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #090a0c;
      --panel: #121418;
      --panel-2: #191d23;
      --text: #f2eee7;
      --muted: #9d9a92;
      --line: #2b3038;
      --accent: #d9b46f;
      --ok: #6ed39a;
      --warn: #e0a85c;
      --bad: #d4675e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main { max-width: 1180px; margin: 0 auto; padding: 28px; }
    header { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 28px; }
    h1 { margin: 0; font: 600 34px/1.05 ui-serif, Georgia, serif; letter-spacing: 0; }
    .sub { color: var(--muted); margin-top: 8px; max-width: 720px; }
    .grid { display: grid; grid-template-columns: 360px 1fr; gap: 18px; align-items: start; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; }
    .panel h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .08em; margin: 0 0 14px; color: var(--muted); }
    .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    button, .file-label {
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--text);
      height: 38px;
      padding: 0 13px;
      border-radius: 7px;
      cursor: pointer;
      font-weight: 600;
    }
    button.primary { border-color: #6a5430; background: #241c10; color: #f4d38d; }
    button:disabled { opacity: .5; cursor: not-allowed; }
    input[type=file] { width: 100%; color: var(--muted); }
    label { display: block; color: var(--muted); font-size: 12px; margin: 12px 0 6px; }
    select {
      width: 100%;
      height: 38px;
      background: #0d0f12;
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 0 10px;
    }
    textarea {
      width: 100%;
      min-height: 280px;
      resize: vertical;
      background: #0d0f12;
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      font: 13px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }
    .status { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
    .metric { background: #0d0f12; border: 1px solid var(--line); border-radius: 7px; padding: 12px; min-height: 74px; }
    .metric strong { display: block; font-size: 21px; line-height: 1.1; }
    .metric span { color: var(--muted); font-size: 12px; }
    .log {
      height: 340px;
      overflow: auto;
      background: #050607;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: pre-wrap;
    }
    .assets { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
    .asset { background: #0d0f12; border: 1px solid var(--line); border-radius: 7px; overflow: hidden; min-height: 110px; }
    .asset img, .asset video { display: block; width: 100%; background: #050607; }
    .asset a { display: block; color: var(--accent); padding: 10px; text-decoration: none; overflow-wrap: anywhere; }
    .pill { display: inline-flex; align-items: center; height: 26px; padding: 0 9px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); }
    table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 12px; }
    th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; }
    td { color: var(--text); overflow-wrap: anywhere; }
    .ok { color: var(--ok); } .bad { color: var(--bad); } .warn { color: var(--warn); }
    @media (max-width: 900px) { main { padding: 18px; } .grid, .status, .assets { grid-template-columns: 1fr; } header { display: block; } }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>AI Film Pipeline</h1>
      <div class="sub">Teste local do fluxo completo: história, cenas, imagens, áudio e vídeo. A execução usa os provedores configurados no ambiente local.</div>
    </div>
    <span id="health" class="pill">verificando</span>
  </header>
  <div class="grid">
    <section class="panel">
      <h2>Entrada</h2>
      <div class="row" style="margin-bottom:12px">
        <button id="sampleBtn">Usar historia.txt</button>
        <button id="runBtn" class="primary">Executar</button>
        <button id="retryBtn" disabled>Retry</button>
      </div>
      <label for="style">Estilo das imagens</label>
      <select id="style">
        <option value="cinematic_realism">Cinematográfico realista</option>
        <option value="storybook_animation">Animação storybook</option>
        <option value="editorial_black_white">Preto e branco editorial</option>
        <option value="watercolor_illustration">Ilustração aquarela</option>
        <option value="anime_cinematic">Anime cinematográfico</option>
      </select>
      <label for="qualityPreset">Qualidade da imagem</label>
      <select id="qualityPreset">
        <option value="high">Alta</option>
        <option value="balanced">Balanceada</option>
      </select>
      <input id="file" type="file" accept=".txt,.md,text/plain" style="margin-bottom:12px">
      <textarea id="story" spellcheck="false"></textarea>
    </section>
    <section class="panel">
      <h2>Execução</h2>
      <div class="status">
        <div class="metric"><strong id="state">idle</strong><span>estado</span></div>
        <div class="metric"><strong id="scenes">0</strong><span>cenas</span></div>
        <div class="metric"><strong id="images">0</strong><span>imagens</span></div>
        <div class="metric"><strong id="audio">0</strong><span>áudios</span></div>
        <div class="metric"><strong id="quality">0</strong><span>qualidade</span></div>
        <div class="metric"><strong id="cost">$0</strong><span>custo est.</span></div>
      </div>
      <div id="log" class="log"></div>
      <div id="monitoring"></div>
      <div id="assets" class="assets"></div>
    </section>
  </div>
</main>
<script>
let currentRun = null;
let pollTimer = null;

const $ = (id) => document.getElementById(id);

function logLine(text) {
  const el = $('log');
  el.textContent += `${new Date().toLocaleTimeString()}  ${text}\n`;
  el.scrollTop = el.scrollHeight;
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function refreshHealth() {
  try {
    const data = await api('/api/health');
    $('health').textContent = `online · ${data.models.gemini_text} · imagem ${data.image_provider}:${data.models.gemini_image_quality}`;
    $('health').className = 'pill ok';
  } catch (err) {
    $('health').textContent = 'offline';
    $('health').className = 'pill bad';
  }
}

function renderRun(run) {
  $('state').textContent = run.status;
  $('state').className = run.status === 'failed' ? 'bad' : run.status === 'completed' ? 'ok' : '';
  $('scenes').textContent = run.summary?.scenes_count ?? 0;
  $('images').textContent = run.summary?.images_count ?? 0;
  $('audio').textContent = run.summary?.audio_count ?? 0;
  $('quality').textContent = run.summary?.quality_metrics?.overall_score ?? 0;
  $('cost').textContent = `$${(run.summary?.cost_estimate?.total_usd ?? 0).toFixed(4)}`;
  $('retryBtn').disabled = !currentRun || run.status === 'running';
  $('runBtn').disabled = run.status === 'running';
  $('log').textContent = (run.log || []).join('\n');

  const monitoring = $('monitoring');
  const jobs = run.summary?.runpod_jobs || [];
  const q = run.summary?.quality_metrics || {};
  const consistency = q.visual_consistency || null;
  const voices = q.voices || [];
  monitoring.innerHTML = `
    <table>
      <thead><tr><th>RunPod job</th><th>Status</th><th>Tempo</th><th>Custo</th><th>Erro</th></tr></thead>
      <tbody>${jobs.map(job => `<tr><td>${job.job_id || '-'}</td><td>${job.status || '-'}</td><td>${job.elapsed_seconds || 0}s</td><td>$${(job.estimated_cost_usd || 0).toFixed(4)}</td><td>${job.error || '-'}</td></tr>`).join('')}</tbody>
    </table>
    <table>
      <thead><tr><th>Mídia</th><th>Score</th><th>Técnico</th><th>Semântico</th><th>Detalhe</th><th>Issues</th></tr></thead>
      <tbody>
        ${(q.images || []).map(item => `<tr><td>imagem cena ${item.scene_id}</td><td>${item.quality_score || 0}</td><td>${item.technical_score ?? '-'}</td><td>${item.semantic_score ?? '-'} · ${item.semantic_accepted ? 'aceita' : 'revisar'}</td><td>${item.width || 0}x${item.height || 0} · ${item.size_bytes || 0} bytes</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
        ${consistency ? `<tr><td>coerência visual</td><td>${consistency.consistency_score || 0}</td><td>-</td><td>${consistency.accepted ? 'aceita' : 'revisar'}</td><td>${consistency.style_notes || '-'}</td><td>${(consistency.issues || []).join(', ') || '-'}</td></tr>` : ''}
        ${(q.audio || []).map(item => `<tr><td>áudio cena ${item.scene_id}</td><td>${item.quality_score || 0}</td><td>-</td><td>-</td><td>${item.duration_seconds || 0}s · ${item.bit_rate || 0}bps</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
        ${q.video ? `<tr><td>vídeo final</td><td>${q.video.quality_score || 0}</td><td>-</td><td>-</td><td>${q.video.duration_seconds || 0}s · ${q.video.bit_rate || 0}bps</td><td>${(q.video.issues || []).join(', ') || '-'}</td></tr>` : ''}
        ${voices.map(item => `<tr><td>voz cena ${item.scene_id}</td><td>${item.quality_score || 0}</td><td>-</td><td>-</td><td>${item.voice_id || '-'} · ${item.text_characters || 0} chars</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
      </tbody>
    </table>
  `;

  const assets = $('assets');
  assets.innerHTML = '';
  const summary = run.summary || {};
  for (const img of summary.scene_images || []) {
    if (img.image_path) {
      const div = document.createElement('div');
      div.className = 'asset';
      div.innerHTML = `<img src="/api/runs/${run.id}/file?path=${encodeURIComponent(img.image_path)}" alt="Cena ${img.scene_id}"><a href="/api/runs/${run.id}/file?path=${encodeURIComponent(img.image_path)}" target="_blank">Cena ${img.scene_id} · ${img.camera_motion || 'motion'}</a>`;
      assets.appendChild(div);
    }
  }
  if (summary.video_path) {
    const div = document.createElement('div');
    div.className = 'asset';
    div.innerHTML = `<video controls src="/api/runs/${run.id}/file?path=${encodeURIComponent('output/final_video.mp4')}"></video><a href="/api/runs/${run.id}/file?path=${encodeURIComponent('output/final_video.mp4')}" target="_blank">Vídeo final</a>`;
    assets.appendChild(div);
  }
}

async function poll() {
  if (!currentRun) return;
  try {
    const run = await api(`/api/runs/${currentRun}`);
    renderRun(run);
    if (run.status === 'completed' || run.status === 'failed') {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  } catch (err) {
    logLine(`erro ao consultar status: ${err.message}`);
  }
}

async function startRun(retry = false) {
  const story = $('story').value.trim();
  if (!story) {
    logLine('adicione uma história antes de executar');
    return;
  }
  $('runBtn').disabled = true;
  $('retryBtn').disabled = true;
  const data = await api('/api/runs', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      story_text: story,
      image_style: $('style').value,
      image_quality_preset: $('qualityPreset').value,
      retry_of: retry ? currentRun : null
    })
  });
  currentRun = data.id;
  logLine(`run iniciado: ${currentRun}`);
  await poll();
  clearInterval(pollTimer);
  pollTimer = setInterval(poll, 2000);
}

$('sampleBtn').onclick = async () => {
  const data = await api('/api/sample-story');
  $('story').value = data.story_text;
  logLine(`historia.txt carregado: ${data.characters} caracteres`);
};

$('runBtn').onclick = () => startRun(false).catch(err => logLine(err.message));
$('retryBtn').onclick = () => startRun(true).catch(err => logLine(err.message));
$('file').onchange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  $('story').value = await file.text();
  logLine(`arquivo carregado: ${file.name}`);
};

refreshHealth();
</script>
</body>
</html>
"""


def _append_log(run_id: str, message: str) -> None:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return
        run.setdefault("log", []).append(message)
        run["updated_at"] = datetime.utcnow().isoformat()


def _set_run(run_id: str, **updates: Any) -> None:
    with RUN_LOCK:
        RUNS[run_id].update(updates)
        RUNS[run_id]["updated_at"] = datetime.utcnow().isoformat()


def _safe_file(run: dict[str, Any], requested: str) -> Path:
    run_dir = Path(run["run_dir"]).resolve()
    path = (run_dir / requested).resolve()
    if run_dir not in path.parents and path != run_dir:
        raise ValueError("invalid path")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(requested)
    return path


def _build_summary(run_dir: Path, final_state: dict[str, Any]) -> dict[str, Any]:
    video_path = run_dir / final_state.get("video_path", "output/final_video.mp4")
    if not video_path.is_absolute():
        video_path = run_dir / video_path

    summary: dict[str, Any] = {
        "status": final_state.get("status"),
        "current_step": final_state.get("current_step"),
        "scenes_count": final_state.get("scenes_count", 0),
        "images_count": final_state.get("images_count", 0),
        "audio_count": final_state.get("audio_count", 0),
        "generation_method": final_state.get("generation_method"),
        "video_path": str(video_path),
        "video_exists": video_path.exists(),
        "video_size": video_path.stat().st_size if video_path.exists() else 0,
        "scene_images": final_state.get("scene_images", []),
        "audio_files": final_state.get("audio_files", []),
        "runpod_jobs": final_state.get("runpod_jobs", []),
        "visual_bible": final_state.get("visual_bible", {}),
        "quality_metrics": final_state.get("quality_metrics", {}),
        "cost_estimate": final_state.get("cost_estimate", {}),
    }
    if video_path.exists():
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size",
                "-of",
                "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            summary["ffprobe"] = json.loads(probe.stdout)
    return summary


def _run_pipeline(
    run_id: str,
    story_text: str,
    image_style: str,
    image_quality_preset: str,
) -> None:
    from dagster import DagsterInstance, materialize
    from orchestration.enhanced_dagster_pipeline import (
        enhanced_langgraph_workflow_asset,
        enhanced_multimodal_input_asset,
        enhanced_validation_asset,
    )

    run = RUNS[run_id]
    run_dir = Path(run["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    story_file_path = run_dir / "historia.txt"
    story_file_path.write_text(story_text, encoding="utf-8")
    output_dir = run_dir / "output"
    output_dir.mkdir(exist_ok=True)
    dagster_home = run_dir / "dagster_home"
    dagster_home.mkdir(exist_ok=True)
    (dagster_home / "dagster.yaml").write_text(
        "telemetry:\n  enabled: false\n",
        encoding="utf-8",
    )

    cwd = Path.cwd()
    previous_dagster_home = os.environ.get("DAGSTER_HOME")
    try:
        os.chdir(run_dir)
        os.environ["DAGSTER_HOME"] = str(dagster_home)
        _append_log(run_id, "materializando assets Dagster")
        assets = [
            enhanced_multimodal_input_asset,
            enhanced_langgraph_workflow_asset,
            enhanced_validation_asset,
        ]
        run_config = {
            "ops": {
                "enhanced_multimodal_input_asset": {
                    "config": {
                        "session_id": run_id,
                        "story_input": story_text,
                        "story_file_path": str(story_file_path),
                        "input_type": "ui",
                        "max_scenes": 3,
                        "image_style": image_style,
                        "image_quality_preset": image_quality_preset,
                        "quality_threshold": 0.7,
                        "enable_structured_logging": True,
                        "log_level": "INFO",
                    }
                }
            }
        }
        result = materialize(
            assets,
            run_config=run_config,
            instance=DagsterInstance.local_temp(str(dagster_home)),
            raise_on_error=True,
        )
        final_state = result.output_for_node("enhanced_langgraph_workflow_asset")
        validation = result.output_for_node("enhanced_validation_asset")
        summary = _build_summary(run_dir=run_dir, final_state=final_state)
        summary["image_style"] = image_style
        summary["image_quality_preset"] = image_quality_preset
        summary["dagster"] = {
            "success": result.success,
            "run_id": result.run_id,
            "validation": validation,
        }

        (run_dir / "pipeline_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _append_log(run_id, f"Dagster run concluído: {result.run_id}")
        _set_run(run_id, status="completed", summary=summary)
    except Exception as exc:
        _append_log(run_id, f"falha: {type(exc).__name__}: {exc}")
        _set_run(run_id, status="failed", error=str(exc), traceback=traceback.format_exc())
    finally:
        if previous_dagster_home is None:
            os.environ.pop("DAGSTER_HOME", None)
        else:
            os.environ["DAGSTER_HOME"] = previous_dagster_home
        os.chdir(cwd)


@app.get("/")
def index() -> Response:
    return Response(INDEX_HTML, mimetype="text/html")


@app.get("/api/health")
def health() -> Response:
    return jsonify(
        {
            "status": "ok",
            "runs_root": str(RUNS_ROOT),
            "models": {
                "gemini_text": os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash"),
                "gemini_image_quality": os.getenv("GEMINI_IMAGE_QUALITY_MODEL", "gemini-3-pro-image"),
                "openai_fast": os.getenv("OPENAI_FAST_MODEL", "gpt-5.4-nano"),
            },
            "image_provider": os.getenv("IMAGE_GENERATION_PROVIDER", "gemini"),
            "orchestrator": "dagster",
            "image_styles": sorted(ALLOWED_IMAGE_STYLES),
            "image_quality_presets": sorted(ALLOWED_IMAGE_QUALITY_PRESETS),
            "keys": {
                "gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "runpod": bool(os.getenv("RUNPOD_API_KEY") and os.getenv("RUNPOD_ENDPOINT_ID")),
                "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY")),
            },
        }
    )


@app.get("/api/sample-story")
def sample_story() -> Response:
    story = STORY_PATH.read_text(encoding="utf-8")
    return jsonify({"path": str(STORY_PATH), "characters": len(story), "story_text": story})


@app.post("/api/runs")
def create_run() -> Response:
    payload = request.get_json(silent=True) or {}
    story_text = str(payload.get("story_text", "")).strip()
    if not story_text:
        return jsonify({"error": "story_text is required"}), 400
    image_style = str(payload.get("image_style", "cinematic_realism")).strip()
    image_quality_preset = str(payload.get("image_quality_preset", "high")).strip()
    if image_style not in ALLOWED_IMAGE_STYLES:
        return jsonify({"error": "invalid image_style"}), 400
    if image_quality_preset not in ALLOWED_IMAGE_QUALITY_PRESETS:
        return jsonify({"error": "invalid image_quality_preset"}), 400

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    run_dir = RUNS_ROOT / run_id
    with RUN_LOCK:
        RUNS[run_id] = {
            "id": run_id,
            "status": "running",
            "run_dir": str(run_dir),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "retry_of": payload.get("retry_of"),
            "image_style": image_style,
            "image_quality_preset": image_quality_preset,
            "log": ["run recebido pela UI"],
            "summary": {},
        }

    thread = threading.Thread(
        target=_run_pipeline,
        args=(run_id, story_text, image_style, image_quality_preset),
        daemon=True,
    )
    thread.start()
    return jsonify({"id": run_id, "status": "running", "run_dir": str(run_dir)})


@app.get("/api/runs/<run_id>")
def get_run(run_id: str) -> Response:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        return jsonify(run)


@app.get("/api/runs/<run_id>/file")
def get_run_file(run_id: str):
    with RUN_LOCK:
        run = RUNS.get(run_id)
    if run is None:
        return jsonify({"error": "run not found"}), 404
    requested = request.args.get("path", "")
    try:
        return send_file(_safe_file(run, requested))
    except (FileNotFoundError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 404


@app.get("/status")
def legacy_status() -> Response:
    return redirect("/api/health")


def main() -> None:
    port = int(os.getenv("AI_FILM_UI_PORT", "8766"))
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
