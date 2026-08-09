#!/usr/bin/env python3
"""Local UI for testing the AI film pipeline.

This server is intentionally local-only. It lets the owner upload a story,
launch the real LangGraph pipeline in the background, retry a failed run, and
inspect generated assets without exposing secrets.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

import requests
from dagster._core.errors import DagsterError
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN3D_ROOT = Path(__file__).resolve().parent
load_dotenv(OPEN3D_ROOT / ".env", override=True)

STORY_PATH = REPO_ROOT / "data" / "historia.txt"
RUNS_ROOT = (
    Path(os.getenv("AI_FILM_RUNS_ROOT", str(REPO_ROOT / "data" / "runs")))
    .expanduser()
    .resolve()
)
ALLOWED_IMAGE_STYLES = {
    "comic_storybook",
    "cinematic_realism",
    "storybook_animation",
    "editorial_black_white",
    "watercolor_illustration",
    "anime_cinematic",
}
ALLOWED_IMAGE_QUALITY_PRESETS = {"balanced", "high", "turbo"}
RUN_ID_PATTERN = re.compile(r"^\d{8}_\d{6}_[0-9a-f]{8}$")
CAST_REFERENCE_RESUME_MANIFEST = "cast_reference_resume_manifest.json"
CAST_REFERENCE_RESUME_SCHEMA_VERSION = "1.0"
CAST_REFERENCE_RESUME_TRUST_FILE = ".validated_cast_reference_resume.json"
CAST_REFERENCE_VIEW_IDS = (
    "front",
    "three_quarter",
    "profile",
    "full_body",
    "expression_neutral",
    "expression_warm",
    "expression_concerned",
)
CAST_REFERENCE_RESUME_SOURCE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_-]{0,63}_character_reference_"
    r"(?:front|three_quarter|profile|full_body|expression_neutral|"
    r"expression_warm|expression_concerned)(?:_attempt_[2-9][0-9]*)?\.png$"
)
CAST_REFERENCE_RESUME_DESTINATION_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_-]{0,63}_character_reference_"
    r"(?:front|three_quarter|profile|full_body|expression_neutral|"
    r"expression_warm|expression_concerned)\.png$"
)
NARRATIVE_IMAGE_RESUME_PATTERN = re.compile(
    r"^scene_(?:[1-9]|1[0-9]|2[0-4])_" r"(?:(?:fal|gemini)_attempt_[1-9]|image)\.png$"
)
SCENE_RESUME_MANIFEST = "scene_resume_manifest.json"
SCENE_RESUME_SCHEMA_VERSION = "1.0"
MAX_CAST_REFERENCE_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_CAST_REFERENCE_UPLOAD_PIXELS = 24_000_000
ALLOWED_CURATION_STATUSES = {
    "approved",
    "rejected",
    "pending_review",
    "retry_requested",
    "superseded",
}
CURATION_REASONS = {
    "personagem incorreto",
    "estilo inconsistente",
    "cena não fiel ao texto",
    "artefatos/texto",
    "rosto/anatomia ruim",
    "movimento ruim",
    "áudio/voz ruim",
    "ritmo/transição ruim",
}
RETRY_SCOPES = {"image", "video", "audio", "image_video", "full_scene"}
YOUTUBE_PRIVACY_STATUSES = {"private", "unlisted", "public"}

if os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(OPEN3D_ROOT))

from open3d_implementation.core.runpod_cost_guard import (  # noqa: E402
    RunPodCostGuardError,
    inspect_runpod_cost_admission,
    runpod_cost_guard_enabled,
)

app = Flask(__name__)
RUNS_ROOT.mkdir(parents=True, exist_ok=True)

RUNS: dict[str, dict[str, Any]] = {}
RUN_LOCK = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


INDEX_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Film Pipeline</title>
  <link rel="icon" href="data:,">
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
    .asset audio { display: block; width: calc(100% - 20px); height: 38px; margin: 10px; }
    .asset a { display: block; color: var(--accent); padding: 10px; text-decoration: none; overflow-wrap: anywhere; }
    .asset-meta { padding: 0 10px 10px; color: var(--muted); font-size: 12px; }
    .asset-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; padding: 0 10px 10px; }
    .asset-actions button { height: 32px; padding: 0 8px; font-size: 12px; }
    .asset-note { width: calc(100% - 20px); min-height: 56px; margin: 0 10px 10px; font-size: 12px; }
    .badge { display: inline-flex; align-items: center; height: 22px; border: 1px solid var(--line); border-radius: 999px; padding: 0 8px; font-size: 11px; color: var(--muted); white-space: nowrap; }
    .badge.approved { color: var(--ok); border-color: rgba(110, 211, 154, .35); }
    .badge.rejected { color: var(--bad); border-color: rgba(212, 103, 94, .35); }
    .badge.pending_review, .badge.retry_requested { color: var(--warn); border-color: rgba(224, 168, 92, .35); }
    .badge.controlled { color: var(--warn); border-color: rgba(224, 168, 92, .55); background: rgba(224, 168, 92, .08); }
    .curation { margin: 14px 0; border: 1px solid var(--line); border-radius: 8px; background: #0d0f12; overflow: hidden; }
    .curation-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px; border-bottom: 1px solid var(--line); }
    .curation-title { font: 600 18px/1.2 ui-serif, Georgia, serif; }
    .curation-sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .progress { height: 6px; background: #050607; border-radius: 999px; overflow: hidden; margin-top: 10px; }
    .progress > span { display: block; height: 100%; background: var(--accent); width: 0; }
    .blockers { color: var(--warn); font-size: 12px; padding: 0 14px 12px; }
    .curation-scenes { display: grid; grid-template-columns: 1fr; gap: 10px; padding: 14px; }
    .workspace-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); margin: 14px 0 0; }
    .workspace-tab { border: 0; border-bottom: 2px solid transparent; border-radius: 0; background: transparent; color: var(--muted); }
    .workspace-tab.active { color: var(--text); border-bottom-color: var(--accent); }
    .workspace-pane[hidden] { display: none; }
    .gate-matrix { display: grid; grid-template-columns: repeat(6, minmax(82px, 1fr)); gap: 6px; margin-top: 10px; }
    .gate-cell { border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: #0d0f12; min-height: 58px; }
    .gate-cell strong { display: block; color: var(--text); font-size: 12px; }
    .gate-cell span { color: var(--muted); font-size: 11px; }
    .gate-cell.pass { border-color: rgba(110, 211, 154, .38); }
    .gate-cell.fail { border-color: rgba(212, 103, 94, .5); }
    .cast-character { padding: 14px; border-bottom: 1px solid var(--line); }
    .cast-character-head { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
    .cast-character-head > div:first-child { min-width: 0; flex: 1; }
    .cast-character-status { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; flex: 0 0 auto; }
    .cast-views { display: grid; grid-template-columns: repeat(7, minmax(86px, 1fr)); gap: 6px; margin-top: 10px; }
    .cast-anchor-upload { display: grid; grid-template-columns: minmax(220px, 1fr) auto; gap: 10px; align-items: end; margin-top: 12px; }
    .cast-anchor-upload label { margin: 0; }
    .cast-view { border: 1px solid var(--line); border-radius: 6px; overflow: hidden; background: #050607; }
    .cast-view.pass { border-color: rgba(110, 211, 154, .38); }
    .cast-view.fail { border-color: rgba(212, 103, 94, .5); }
    .cast-view img { display: block; width: 100%; aspect-ratio: 3 / 4; object-fit: cover; }
    .cast-view span { display: block; padding: 6px; color: var(--muted); font-size: 10px; overflow-wrap: anywhere; }
    .review-card { border: 1px solid var(--line); border-radius: 7px; background: #090a0c; overflow: hidden; }
    .review-grid { display: grid; grid-template-columns: 220px 1fr; gap: 12px; padding: 12px; align-items: start; }
    .review-card img, .review-card video { width: 100%; background: #050607; border-radius: 6px; display: block; }
    .review-meta { color: var(--muted); font-size: 12px; }
    .review-meta strong { color: var(--text); font-size: 14px; display: block; margin-bottom: 6px; }
    .review-controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
    .review-controls select, .review-controls textarea { min-height: 38px; margin: 0; width: 100%; }
    .review-controls textarea { grid-column: 1 / -1; min-height: 64px; }
    .attempt-strip { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
    .attempt-pill { border: 1px solid var(--line); border-radius: 999px; padding: 4px 8px; color: var(--muted); font-size: 11px; }
    .attempt-pill.active { color: var(--accent); border-color: rgba(217, 180, 111, .5); }
    .compare-tools { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
    .attempt-compare { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 10px; }
    .attempt-card { border: 1px solid var(--line); border-radius: 7px; background: #050607; overflow: hidden; }
    .attempt-card-head { display: flex; justify-content: space-between; gap: 8px; padding: 10px; border-bottom: 1px solid var(--line); }
    .attempt-card-title { font-weight: 700; }
    .attempt-media { display: grid; gap: 8px; padding: 10px; }
    .attempt-media img, .attempt-media video { width: 100%; border-radius: 6px; background: #090a0c; }
    .attempt-media audio { width: 100%; height: 38px; display: block; }
    .attempt-card audio { width: 100%; }
    .attempt-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; padding: 0 10px 10px; color: var(--muted); font-size: 12px; }
    .attempt-facts div { overflow-wrap: anywhere; }
    .waveform { display: flex; align-items: center; gap: 2px; height: 34px; width: 100%; margin-top: 6px; }
    .waveform span { flex: 1; min-width: 2px; border-radius: 999px; background: linear-gradient(180deg, #f0d392, #8d6a2f); opacity: .88; }
    .attempt-actions { display: flex; gap: 6px; flex-wrap: wrap; padding: 0 10px 10px; }
    .attempt-actions button { height: 32px; padding: 0 9px; font-size: 12px; }
    .final-gate { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 10px; align-items: center; padding: 14px; border-top: 1px solid var(--line); background: #0b0c0e; }
    .final-gate video { width: 220px; max-width: 100%; border-radius: 6px; background: #050607; }
    .final-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .pill { display: inline-flex; align-items: center; height: 26px; padding: 0 9px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); }
    table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 12px; }
    th, td { border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; }
    td { color: var(--text); overflow-wrap: anywhere; }
    .ok { color: var(--ok); } .bad { color: var(--bad); } .warn { color: var(--warn); }
    @media (max-width: 900px) { main { padding: 18px; } .grid, .status, .assets, .review-grid, .final-gate, .attempt-compare, .compare-tools, .gate-matrix, .cast-views, .cast-anchor-upload { grid-template-columns: 1fr; } header { display: block; } }
    @media (max-width: 640px) { .cast-character-head { flex-direction: column; } .cast-character-status { justify-content: flex-start; } }
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
        <option value="comic_storybook">História em quadrinhos premium</option>
        <option value="cinematic_realism">Cinematográfico realista</option>
        <option value="storybook_animation">Animação storybook</option>
        <option value="editorial_black_white">Preto e branco editorial</option>
        <option value="watercolor_illustration">Ilustração aquarela</option>
        <option value="anime_cinematic">Anime cinematográfico</option>
      </select>
      <label for="qualityPreset">Qualidade da imagem</label>
      <select id="qualityPreset">
        <option value="high">Alta</option>
        <option value="turbo">Turbo SDXL</option>
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
        <div class="metric"><strong id="quality">-</strong><span>gates visuais</span></div>
        <div class="metric"><strong id="cost">$0</strong><span>custo est.</span></div>
      </div>
      <div class="workspace-tabs" role="tablist" aria-label="Áreas do pipeline">
        <button id="tab-curation" class="workspace-tab active" onclick="setWorkspaceTab('curation')">Curadoria</button>
        <button id="tab-operation" class="workspace-tab" onclick="setWorkspaceTab('operation')">Operação</button>
        <button id="tab-media" class="workspace-tab" onclick="setWorkspaceTab('media')">Mídia</button>
      </div>
      <section id="pane-curation" class="workspace-pane"><div id="curation" class="curation"></div></section>
      <section id="pane-operation" class="workspace-pane" hidden><div id="log" class="log"></div><div id="monitoring"></div></section>
      <section id="pane-media" class="workspace-pane" hidden><div id="assets" class="assets"></div></section>
    </section>
  </div>
</main>
<script>
let currentRun = null;
let pollTimer = null;
let comparisonSelections = {};
let workspaceTab = 'curation';

const $ = (id) => document.getElementById(id);

function setWorkspaceTab(tab) {
  workspaceTab = ['curation', 'operation', 'media'].includes(tab) ? tab : 'curation';
  for (const name of ['curation', 'operation', 'media']) {
    $(`pane-${name}`).hidden = name !== workspaceTab;
    $(`tab-${name}`).classList.toggle('active', name === workspaceTab);
  }
}

function logLine(text) {
  const el = $('log');
  el.textContent += `${new Date().toLocaleTimeString()}  ${text}\n`;
  el.scrollTop = el.scrollHeight;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  }[char]));
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const text = await res.text();
    try {
      const payload = JSON.parse(text);
      throw new Error(payload.error || text);
    } catch (err) {
      if (err instanceof SyntaxError) throw new Error(text);
      throw err;
    }
  }
  return res.json();
}

async function refreshHealth() {
  try {
    const data = await api('/api/health');
    const imageModel = data.image_provider === 'comfyui'
      ? data.models.comfyui_checkpoint
      : (data.image_provider === 'fal'
          ? data.models.fal_flux
          : data.models.gemini_image_quality);
    $('health').textContent = `online · ${data.models.gemini_text} · imagem ${data.image_provider}:${imageModel}`;
    $('health').className = 'pill ok';
  } catch (err) {
    $('health').textContent = 'offline';
    $('health').className = 'pill bad';
  }
}

const CURATION_REASONS = [
  'personagem incorreto',
  'estilo inconsistente',
  'cena não fiel ao texto',
  'artefatos/texto',
  'rosto/anatomia ruim',
  'movimento ruim',
  'áudio/voz ruim',
  'ritmo/transição ruim'
];

const RETRY_SCOPES = [
  ['image_video', 'Imagem; vídeo após aprovação'],
  ['image', 'Imagem'],
  ['video', 'Vídeo'],
  ['audio', 'Áudio'],
  ['full_scene', 'Cena completa; vídeo após aprovação']
];

function reasonOptions(selected = '') {
  return `<option value="">Motivo</option>${CURATION_REASONS.map(reason => `<option value="${escapeHtml(reason)}" ${reason === selected ? 'selected' : ''}>${escapeHtml(reason)}</option>`).join('')}`;
}

function scopeOptions(selected = 'image_video') {
  return RETRY_SCOPES.map(([value, label]) => `<option value="${value}" ${value === selected ? 'selected' : ''}>${label}</option>`).join('');
}

function findByScene(items, sceneId) {
  return (items || []).find(item => String(item.scene_id) === String(sceneId)) || {};
}

function mediaUrl(run, path) {
  return `/api/runs/${run.id}/file?path=${encodeURIComponent(path)}`;
}

function dialogueMediaCurrent(summary = {}) {
  return summary.video_current === true && summary.quality_metrics?.dialogue?.passed === true;
}

function activeAttempt(review) {
  const attempts = review.attempts || [];
  return attempts.find(attempt => attempt.id === review.active_attempt_id) || attempts[attempts.length - 1] || {};
}

function defaultCompareSelection(review) {
  const attempts = review.attempts || [];
  const active = review.active_attempt_id || attempts[attempts.length - 1]?.id || 'attempt_1';
  const previous = attempts.slice().reverse().find(attempt => attempt.id !== active)?.id || active;
  return {left: active, right: previous};
}

function attemptOptions(attempts, selected) {
  return (attempts || []).map(attempt => `<option value="${escapeHtml(attempt.id)}" ${attempt.id === selected ? 'selected' : ''}>${escapeHtml(attempt.id)} · ${escapeHtml(attempt.status || 'draft')}</option>`).join('');
}

function attemptMedia(run, attempt) {
  const image = attempt.image_path ? `<img src="${mediaUrl(run, attempt.image_path)}" alt="${escapeHtml(attempt.id)} imagem">` : '<div class="asset-meta">sem imagem nesta tentativa</div>';
  const audio = attempt.audio_path
    ? `<audio controls preload="metadata" src="${mediaUrl(run, attempt.audio_path)}" aria-label="Áudio ${escapeHtml(attempt.id)}"></audio>`
    : '';
  return `${image}${audio}`;
}

const GATE_LABELS = {
  technical: 'Técnico',
  semantic: 'Semântico',
  identity: 'Identidade',
  style: 'Estilo',
  objects: 'Objetos',
  reference_version: 'Referência'
};

function renderGateMatrix(automaticGate = {}) {
  const gates = automaticGate.gates || {};
  return `<div class="gate-matrix">${Object.entries(GATE_LABELS).map(([key, label]) => {
    const gate = gates[key] || {};
    const passed = gate.passed === true;
    const score = gate.score === null || gate.score === undefined ? (passed ? 'OK' : '-') : gate.score;
    const verdict = gate.human_review_required === true ? 'REVIEW' : (passed ? 'PASS' : 'BLOCK');
    return `<div class="gate-cell ${passed ? 'pass' : 'fail'}"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(score)} · ${verdict}</span></div>`;
  }).join('')}</div>`;
}

function renderAttemptCard(run, sceneId, review, attemptId) {
  const attempt = (review.attempts || []).find(item => item.id === attemptId) || {};
  if (!attempt.id) return `<div class="attempt-card"><div class="asset-meta">tentativa indisponível</div></div>`;
  const isActive = attempt.id === review.active_attempt_id;
  const automaticGate = attempt.automatic_gate || {};
  const canUse = attempt.status !== 'failed';
  const canApprove = canUse && automaticGate.passed === true;
  return `
    <div class="attempt-card">
      <div class="attempt-card-head">
        <div>
          <div class="attempt-card-title">${escapeHtml(attempt.id)}</div>
          <div class="curation-sub">${escapeHtml(attempt.created_at || '')}</div>
        </div>
        <span class="badge ${escapeHtml(attempt.status || 'pending_review')}">${escapeHtml(isActive ? `${attempt.status || 'active'} · ativa` : attempt.status || 'draft')}</span>
      </div>
      <div class="attempt-media">${attemptMedia(run, attempt)}</div>
      <div class="attempt-facts">
        <div>agregado informativo: ${escapeHtml(attempt.image_quality_score ?? '-')}</div>
        <div>semântico: ${escapeHtml(attempt.image_semantic_score ?? '-')}</div>
        <div>escopo: ${escapeHtml(attempt.retry_scope || 'original')}</div>
        <div>motivo: ${escapeHtml(attempt.reason || '-')}</div>
        <div style="grid-column:1 / -1">${renderGateMatrix(automaticGate)}</div>
        ${controlledWorkflowDetail(attempt)}
        ${attemptHeroDetail(attempt)}
        ${attemptAudioDetail(attempt)}
        ${attempt.error ? `<div style="grid-column:1 / -1" class="bad">erro: ${escapeHtml(attempt.error)}</div>` : ''}
        ${attempt.note ? `<div style="grid-column:1 / -1">nota: ${escapeHtml(attempt.note)}</div>` : ''}
      </div>
      <div class="attempt-actions">
        <button onclick="activateAttempt('${sceneId}', '${attempt.id}')" ${canUse && !isActive ? '' : 'disabled'}>Tornar ativa</button>
        <button class="primary" onclick="approveAttempt('${sceneId}', '${attempt.id}')" ${canApprove ? '' : 'disabled'}>Aprovar esta tentativa</button>
      </div>
    </div>`;
}

function updateAttemptComparison(sceneId) {
  if (!currentRun || !window.lastRenderedRun) return;
  const left = document.getElementById(`compare-left-${sceneId}`)?.value;
  const right = document.getElementById(`compare-right-${sceneId}`)?.value;
  comparisonSelections[sceneId] = {left, right};
  const run = window.lastRenderedRun;
  const review = run.summary?.curation?.scenes?.[String(sceneId)] || {};
  const target = document.getElementById(`attempt-compare-${sceneId}`);
  if (target) {
    target.innerHTML = `${renderAttemptCard(run, sceneId, review, left)}${renderAttemptCard(run, sceneId, review, right)}`;
  }
}

function imageQualityDetail(item) {
  const heroObjects = (item.hero_objects || []).map(obj => obj.name).filter(Boolean).join(', ');
  const heroState = item.hero_object_legibility === true ? 'hero legível' : item.hero_object_legibility === false ? 'hero ilegível' : '';
  const heroNotes = item.hero_object_notes ? ` · ${item.hero_object_notes}` : '';
  const hero = heroObjects ? ` · ${heroState || 'hero n/a'}: ${heroObjects}${heroNotes}` : '';
  const controlled = item.control_workflow_required ? ` · requer ${item.recommended_generation_strategy || 'workflow controlado'}` : '';
  const used = item.controlled_workflow ? ` · ControlNet: ${item.controlnet_model || 'ativo'}` : '';
  return `${item.width || 0}x${item.height || 0} · ${item.size_bytes || 0} bytes${hero}${controlled}${used}`;
}

function controlledWorkflowDetail(record) {
  if (record?.controlled_workflow) {
    const reference = record.control_image ? ` · ref ${escapeHtml(record.control_image)}` : '';
    return `<div style="grid-column:1 / -1"><span class="badge controlled">ControlNet</span> retry controlado usado${record.controlnet_model ? ` · ${escapeHtml(record.controlnet_model)}` : ''}${reference}</div>`;
  }
  if (!record?.control_workflow_required) return '';
  const strategy = record.recommended_generation_strategy || 'controlled_inpaint';
  const action = record.operator_next_action || 'Usar inpaint/ControlNet antes de novo retry.';
  return `<div style="grid-column:1 / -1"><span class="badge controlled">${escapeHtml(strategy)}</span> ${escapeHtml(action)}</div>`;
}

function attemptHeroDetail(attempt) {
  const job = attempt.image_job || {};
  const heroObjects = (attempt.hero_objects || job.hero_objects || []).map(obj => obj.name).filter(Boolean).join(', ');
  if (!heroObjects) return '';
  const legible = attempt.hero_object_legibility ?? job.hero_object_legibility;
  const state = legible === true ? 'hero legível' : legible === false ? 'hero ilegível' : 'hero n/a';
  const notes = attempt.hero_object_notes || job.hero_object_notes || '';
  return `<div style="grid-column:1 / -1">${escapeHtml(state)}: ${escapeHtml(heroObjects)}${notes ? ` · ${escapeHtml(notes)}` : ''}</div>`;
}

function waveformHtml(samples = []) {
  if (!Array.isArray(samples) || !samples.length) return '';
  const bars = samples.slice(0, 48).map(value => {
    const height = Math.max(3, Math.round(Number(value || 0) * 32));
    return `<span style="height:${height}px"></span>`;
  }).join('');
  return `<div class="waveform" aria-label="waveform">${bars}</div>`;
}

function audioQualityDetail(item) {
  const premium = item.premium_audio === true ? 'premium' : item.premium_audio === false ? 'não-premium' : 'n/a';
  const direction = item.voice_direction?.tone ? ` · ${item.voice_direction.tone}` : '';
  const loudness = item.loudness?.input_i_lufs ? ` · ${item.loudness.input_i_lufs} LUFS alvo ${item.loudness.target_i_lufs}` : '';
  const ambient = item.ambient?.profile?.label ? ` · ambiente ${item.ambient.profile.label}` : '';
  const roleList = (item.voice_roles || []).join(', ');
  const idList = (item.voice_ids || []).join(', ');
  const voice = roleList || idList || item.voice_role || item.voice_id ? ` · vozes ${roleList || item.voice_role || 'personagens'}:${idList || item.voice_id || '-'}` : '';
  const legacyNarrator = `${roleList} ${item.voice_role || ''}`.toLowerCase().includes('narrat') ? ' · legado bloqueado' : '';
  const turns = Array.isArray(item.dialogue_turns) ? ` · ${item.dialogue_turns.length} falas` : '';
  return `${item.duration_seconds || 0}s · ${item.bit_rate || 0}bps${loudness} · ${premium}${ambient}${voice}${legacyNarrator}${turns}${direction}`;
}

function renderDialoguePlan(summary) {
  const scenes = summary.scenes || [];
  const gate = summary.quality_metrics?.dialogue || summary.quality_metrics?.dialogue_contract || {};
  if (!scenes.length) return '';
  const sceneRows = scenes.map(scene => {
    const turns = scene.dialogue || [];
    const sceneGate = (gate.scenes || []).find(item => String(item.scene_id) === String(scene.scene_id)) || {};
    const turnRows = turns.map(turn => {
      const mode = turn.mode === 'internal_thought' ? 'pensamento' : 'fala';
      const sync = turn.lip_sync_required ? 'lip sync' : 'boca fechada';
      return `<div class="curation-sub"><strong>${escapeHtml(turn.speaker_name || turn.speaker_id || 'personagem')}</strong> · ${escapeHtml(mode)} · ${escapeHtml(sync)} · ${escapeHtml(turn.emotion || '-')}<br>“${escapeHtml(turn.text_pt_br || '')}”<br><span>${escapeHtml(turn.action || '')}</span></div>`;
    }).join('');
    const blockers = sceneGate.blockers || [];
    return `<div class="cast-character">
      <div class="cast-character-head"><strong>Cena ${escapeHtml(scene.scene_id)}</strong><span class="badge ${sceneGate.passed === false ? 'rejected' : 'approved'}">${sceneGate.passed === false ? 'BLOCK' : 'pt-BR'}</span></div>
      <div class="curation-sub">${escapeHtml(scene.location || '-')} · ${escapeHtml(scene.main_action || '-')} · ${escapeHtml(scene.dominant_emotion || '-')}</div>
      ${turnRows}
      ${blockers.length ? `<div class="blockers">${blockers.map(escapeHtml).join(' · ')}</div>` : ''}
    </div>`;
  }).join('');
  return `<div class="curation-head"><div><div class="curation-title">Roteiro falado</div><div class="curation-sub">Sem narrador · português brasileiro · uma boca ativa por fala</div></div><span class="badge ${gate.passed === false ? 'rejected' : 'approved'}">${gate.passed === false ? 'BLOCK' : 'PASS'}</span></div>${sceneRows}`;
}

function renderCastBible(summary, run) {
  const cast = summary.visual_bible?.cast_bible;
  if (!cast) return `<div class="curation-head"><div><div class="curation-title">Cast Bible</div><div class="curation-sub">Contrato de personagens ausente. Aprovação visual bloqueada.</div></div><span class="badge rejected">BLOCK</span></div>`;
  if (!cast.characters?.length) return `<div class="curation-head"><div><div class="curation-title">Cast Bible</div><div class="curation-sub">${escapeHtml(cast.revision || '')} · nenhum personagem recorrente detectado</div></div><span class="badge approved">N/A</span></div>`;
  const required = new Set(cast.required_for_production || cast.required_for_scenes || []);
  const characters = cast.characters
    .filter(character => required.size === 0 || required.has(character.id))
    .map(character => {
      const reference = character.reference || {};
      const lora = character.lora || {};
      const views = reference.views || {};
      const viewCards = (reference.required_views || []).map(viewId => {
        const view = views[viewId] || {};
        const image = view.path ? `<img src="${mediaUrl(run, view.path)}" alt="${escapeHtml(character.name || character.id)} ${escapeHtml(viewId)}">` : '';
        const viewState = view.human_approved
          ? 'HUMANO PASS'
          : view.automatic_approved
            ? 'AUTO PASS'
            : view.status === 'rejected' || view.status === 'blocked_by_anchor'
              ? 'AUTO BLOCK'
              : 'PENDENTE';
        return `<div class="cast-view ${view.human_approved ? 'pass' : 'fail'}">${image}<span>${escapeHtml(viewId)} · ${viewState}</span></div>`;
      }).join('');
      const referenceActions = reference.automatic_approved === true
        ? `<div class="row" style="margin-top:12px">
            <button ${reference.human_approved ? 'disabled' : ''} onclick="setCastReferenceApproval('${escapeHtml(character.id)}', true)">Aprovar referência</button>
            <button class="danger" onclick="setCastReferenceApproval('${escapeHtml(character.id)}', false)">Reprovar referência</button>
          </div>`
        : '';
      const uploadCandidate = reference.upload_candidate || {};
      const uploadCandidatePreview = uploadCandidate.path
        ? `<div class="curation-sub warn">Último upload bloqueado · técnico ${escapeHtml(uploadCandidate.quality_score ?? '-')} · semântico ${escapeHtml(uploadCandidate.semantic_score ?? '-')} · ${escapeHtml((uploadCandidate.issues || []).join(', ') || 'gate reprovado')}</div>`
        : '';
      const anchorUpload = character.kind === 'human'
        ? `<div class="cast-anchor-upload">
            <label>Frente canônica
              <input id="cast-front-upload-${escapeHtml(character.id)}" type="file" accept="image/png,image/jpeg,image/webp" aria-label="Frente canônica de ${escapeHtml(character.name || character.id)}">
            </label>
            <button onclick="uploadCastFront('${escapeHtml(character.id)}')">Substituir frente</button>
          </div>
          ${uploadCandidatePreview}`
        : '';
      return `<div class="cast-character">
        <div class="cast-character-head">
          <div><strong>${escapeHtml(character.name || character.id)}</strong><div class="curation-sub">${escapeHtml(character.role || '-')} · ${escapeHtml(character.identity_prompt || '-')}</div></div>
          <div class="cast-character-status"><span class="badge ${reference.approved ? 'approved' : 'rejected'}">ref v${escapeHtml(reference.version || 1)} · ${escapeHtml(reference.status || 'pending')}</span><span class="badge ${lora.status === 'configured' ? 'approved' : 'rejected'}">LoRA ${escapeHtml(lora.status || 'unconfigured')}</span></div>
        </div>
        <div class="curation-sub">checksum ${escapeHtml((reference.checksum || '-').slice(0, 16))} · ${escapeHtml(lora.name || lora.expected_name || '-')}</div>
        <div class="cast-views">${viewCards}</div>
        ${anchorUpload}
        ${referenceActions}
      </div>`;
    }).join('');
  const stage = summary.status || summary.current_step || '';
  const stageActions = cast.status === 'approved'
    ? `<div class="row" style="margin:12px 0 16px">
        <button onclick="exportCastLoraPacks()">Exportar packs LoRA</button>
        <button ${stage !== 'ready_to_generate_scenes' ? 'disabled' : ''} onclick="continueAfterCast()">Continuar geração</button>
      </div>`
    : '';
  return `
    <div class="curation-head"><div><div class="curation-title">Cast Bible</div><div class="curation-sub">${escapeHtml(cast.revision || '')} · referências multipose bloqueantes</div></div><span class="badge ${cast.status === 'approved' ? 'approved' : 'rejected'}">${escapeHtml(cast.status || 'pending')}</span></div>
    ${stageActions}${characters}`;
}

function characterIdentityDetail(item) {
  const identities = item.character_identity || [];
  if (!identities.length) return '';
  const labels = {face: 'rosto', age_kind: 'idade', hair: 'cabelo', wardrobe: 'roupa', silhouette: 'silhueta', unique: 'unicidade'};
  return identities.map(identity => {
    const dimensions = Object.entries(identity.dimensions || {})
      .map(([key, score]) => `${labels[key] || key} ${score}`)
      .join(' · ');
    const verdict = identity.human_review_required === true
      ? 'revisão humana obrigatória'
      : (identity.accepted ? 'aprovado automático' : 'reprovado');
    return `${identity.character_name || identity.character_id}: ${identity.score ?? 0} ${verdict}${dimensions ? ` · ${dimensions}` : ''}`;
  }).join(' | ');
}

function attemptAudioDetail(attempt) {
  const job = attempt.audio_job || {};
  const provider = attempt.audio_provider || job.provider || '';
  const providerLabel = provider.includes('elevenlabs') ? 'ElevenLabs' : provider || 'áudio';
  const premium = job.premium_audio === true
    ? `${providerLabel} · gate premium aprovado`
    : job.premium_audio === false
      ? `${providerLabel} · revisão de qualidade necessária`
      : providerLabel;
  const direction = attempt.voice_direction || job.voice_direction || {};
  const loudness = job.loudness?.input_i_lufs ? ` · ${job.loudness.input_i_lufs} LUFS alvo ${job.loudness.target_i_lufs}` : '';
  const ambient = job.ambient?.profile?.label ? ` · ambiente ${job.ambient.profile.label}` : '';
  const roleList = (attempt.voice_roles || job.voice_roles || []).join(', ');
  const idList = (attempt.voice_ids || job.voice_ids || []).join(', ');
  const voice = roleList || idList || attempt.voice_role || job.voice_role || attempt.voice_id || job.voice_id ? ` · vozes ${roleList || attempt.voice_role || job.voice_role || 'personagens'}:${idList || attempt.voice_id || job.voice_id || '-'}` : '';
  const legacyNarrator = `${roleList} ${attempt.voice_role || job.voice_role || ''}`.toLowerCase().includes('narrat') ? ' · legado bloqueado' : '';
  if (!premium && !direction.tone && !job.waveform?.length) return '';
  return `<div style="grid-column:1 / -1">${escapeHtml(premium)}${escapeHtml(loudness)}${escapeHtml(ambient)}${escapeHtml(voice)}${escapeHtml(legacyNarrator)}${direction.tone ? ` · ${escapeHtml(direction.tone)}` : ''}${waveformHtml(job.waveform)}</div>`;
}

function gateTone(status) {
  if (status === 'final_approved') return 'approved';
  if (status === 'published_current') return 'approved';
  if (status === 'ready_to_publish') return 'approved';
  if (status === 'scene_review_blocked' || status === 'quality_review_blocked' || status === 'video_review_blocked') return 'rejected';
  if (status === 'blocked' || status === 'publish_failed' || status === 'invalid_video') return 'rejected';
  return 'pending_review';
}

function productionStatusLabel(status) {
  const labels = {
    published_current: 'publicado atual',
    published_stale: 'publicado antigo',
    ready_to_publish: 'pronto para publicar',
    needs_final_review: 'aguardando revisão final',
    missing_video: 'sem vídeo final',
    invalid_video: 'vídeo final inválido',
    publish_failed: 'publicação falhou',
    uploading: 'publicando',
    queued: 'publicação na fila',
    blocked: 'bloqueado'
  };
  return labels[status] || status || 'indefinido';
}

function renderCostQuota(summary) {
  const cq = summary.cost_quota || {};
  const providers = cq.providers || [];
  if (!providers.length) return '';
  return `
    <table>
      <thead><tr><th>Provider</th><th>Custo</th><th>Quota</th><th>Uso</th></tr></thead>
      <tbody>
        ${providers.map(item => `<tr><td>${escapeHtml(item.provider)}</td><td>$${Number(item.usd || 0).toFixed(4)}</td><td>${escapeHtml(item.quota || '-')}</td><td>${escapeHtml(JSON.stringify(item.usage || {}))}</td></tr>`).join('')}
      </tbody>
    </table>
    ${(cq.warnings || []).length ? `<div class="blockers">${(cq.warnings || []).map(escapeHtml).join(' · ')}</div>` : ''}
    ${(cq.blockers || []).length ? `<div class="blockers">${(cq.blockers || []).map(escapeHtml).join(' · ')}</div>` : ''}`;
}

function renderCuration(run) {
  const el = $('curation');
  const summary = run.summary || {};
  if (!summary.scene_images?.length) {
    const waitingStep = summary.current_step || summary.status || 'aguardando';
    const runBlockers = summary.runpod_preflight?.blockers || [];
    el.innerHTML = `
      <div class="curation-head">
        <div>
          <div class="curation-title">Sala de Curadoria</div>
          <div class="curation-sub">${escapeHtml(waitingStep)} · cenas narrativas permanecem bloqueadas até as referências e LoRAs vigentes serem aprovadas.</div>
        </div>
        <span class="badge ${runBlockers.length ? 'rejected' : 'pending_review'}">${runBlockers.length ? 'BLOCK' : 'aguardando'}</span>
      </div>
      ${runBlockers.length ? `<div class="blockers">${runBlockers.map(item => escapeHtml(item.message || item.code || 'RunPod indisponível')).join(' · ')}</div>` : ''}
      ${renderCastBible(summary, run)}
      ${renderDialoguePlan(summary)}`;
    return;
  }

  const curation = summary.curation || {};
  const scenes = curation.scenes || {};
  const approved = curation.approved_count || 0;
  const total = curation.total_scenes || summary.scene_images.length || 0;
  const progress = total ? Math.round((approved / total) * 100) : 0;
  const blockers = curation.blockers || [];
  const finalReview = curation.final_review || {};
  const publication = summary.publication || {};
  const production = summary.production_status || {};
  const videoGeneration = curation.video_generation || {};
  const q = summary.quality_metrics || {};

  const sceneCards = (summary.scene_images || []).map(img => {
    const sceneId = String(img.scene_id);
    const review = scenes[sceneId] || {status: 'pending_review', note: '', reason: '', active_attempt_id: 'attempt_1'};
    const imageMetric = findByScene(q.images, sceneId);
    const noteId = `curation-note-${sceneId}`;
    const reasonId = `curation-reason-${sceneId}`;
    const scopeId = `curation-scope-${sceneId}`;
    const attemptId = review.active_attempt_id || 'attempt_1';
    const attempts = review.attempts?.length ? review.attempts : [{
      id: attemptId,
      status: 'active',
      image_path: img.image_path,
      video_path: clip.video_path,
      audio_path: audio.audio_path,
      image_quality_score: imageMetric.quality_score,
      image_semantic_score: imageMetric.semantic_score,
      image_semantic_accepted: imageMetric.semantic_accepted,
      hero_objects: imageMetric.hero_objects || [],
      hero_object_legibility: imageMetric.hero_object_legibility,
      hero_object_notes: imageMetric.hero_object_notes || '',
      control_workflow_required: imageMetric.control_workflow_required || false,
      recommended_generation_strategy: imageMetric.recommended_generation_strategy || 'txt2img_retry',
      operator_next_action: imageMetric.operator_next_action || ''
    }];
    review.attempts = attempts;
    const activeAttempt = attempts.find(attempt => attempt.id === attemptId) || attempts[attempts.length - 1] || {};
    const automaticGate = review.automatic_gate || activeAttempt.automatic_gate || {};
    const defaults = comparisonSelections[sceneId] || defaultCompareSelection(review);
    const leftAttempt = attempts.find(attempt => attempt.id === defaults.left)?.id || attemptId;
    const rightAttempt = attempts.find(attempt => attempt.id === defaults.right)?.id || attempts.find(attempt => attempt.id !== leftAttempt)?.id || leftAttempt;
    comparisonSelections[sceneId] = {left: leftAttempt, right: rightAttempt};
    const attemptStrip = attempts.map(attempt => `<span class="attempt-pill ${attempt.id === attemptId ? 'active' : ''}">${escapeHtml(attempt.id)} · ${escapeHtml(attempt.status || 'draft')}</span>`).join('');
    const autoVerdict = automaticGate.passed === true ? 'PASS automático' : `BLOCK · ${(automaticGate.blockers || []).join(', ') || 'gates incompletos'}`;
    return `
      <div class="review-card">
        <div class="review-grid">
          <div>
            <img src="/api/runs/${run.id}/file?path=${encodeURIComponent(img.image_path)}" alt="Cena ${escapeHtml(sceneId)}">
          </div>
          <div class="review-meta">
            <strong>Cena ${escapeHtml(sceneId)}</strong>
            <span class="badge ${escapeHtml(review.status || 'pending_review')}">${escapeHtml(review.status || 'pending_review')}</span>
            <div style="margin-top:8px">gate automático: ${escapeHtml(autoVerdict)}</div>
            ${renderGateMatrix(automaticGate)}
            <div>agregado informativo: ${escapeHtml(imageMetric.quality_score || 0)}</div>
            ${controlledWorkflowDetail(imageMetric)}
            <div>tentativa ativa: ${escapeHtml(attemptId)}</div>
            <div class="attempt-strip">${attemptStrip}</div>
            <div class="review-controls">
              <select id="${reasonId}">${reasonOptions(review.reason || '')}</select>
              <select id="${scopeId}">${scopeOptions(review.retry_scope || 'image_video')}</select>
              <textarea id="${noteId}" placeholder="Nota obrigatória para reprovar ou pedir retry">${escapeHtml(review.note || '')}</textarea>
              <button onclick="approveAttempt('${sceneId}', '${attemptId}')" ${automaticGate.passed === true ? '' : 'disabled'}>Aprovar tentativa ativa</button>
              <button onclick="setCuration('${sceneId}', 'rejected')">Reprovar</button>
              <button onclick="requestSceneRetry('${sceneId}')">Retry escopo</button>
            </div>
            <div class="compare-tools">
              <select id="compare-left-${sceneId}" onchange="updateAttemptComparison('${sceneId}')">${attemptOptions(attempts, leftAttempt)}</select>
              <select id="compare-right-${sceneId}" onchange="updateAttemptComparison('${sceneId}')">${attemptOptions(attempts, rightAttempt)}</select>
            </div>
            <div id="attempt-compare-${sceneId}" class="attempt-compare">
              ${renderAttemptCard(run, sceneId, review, leftAttempt)}
              ${renderAttemptCard(run, sceneId, review, rightAttempt)}
            </div>
          </div>
        </div>
      </div>`;
  }).join('');

  el.innerHTML = `
    <div class="curation-head">
      <div>
        <div class="curation-title">Sala de Curadoria</div>
        <div class="curation-sub">${approved}/${total} cenas aprovadas · corte final: ${escapeHtml(finalReview.status || 'draft')} · produção: ${escapeHtml(productionStatusLabel(production.status))}</div>
        <div class="progress"><span style="width:${progress}%"></span></div>
      </div>
      <span class="badge ${gateTone(production.status || curation.status)}">${escapeHtml(production.status || curation.status || 'pending_review')}</span>
    </div>
    ${blockers.length ? `<div class="blockers">${blockers.map(escapeHtml).join(' · ')}</div>` : ''}
    ${(production.blockers || []).length ? `<div class="blockers">${production.blockers.map(escapeHtml).join(' · ')}</div>` : ''}
    ${(production.warnings || []).length ? `<div class="blockers">${production.warnings.map(escapeHtml).join(' · ')}</div>` : ''}
    ${renderCastBible(summary, run)}
    ${renderDialoguePlan(summary)}
    <div class="curation-scenes">${sceneCards}</div>
    <div class="final-gate">
      <div>
        <div class="curation-title">Corte final</div>
        <div class="curation-sub">Publicação só libera com todas as cenas aprovadas, vídeo visualizado e corte final aprovado.</div>
        <div class="curation-sub">Status real: ${escapeHtml(productionStatusLabel(production.status))}</div>
        <div class="curation-sub">Animação: ${escapeHtml(videoGeneration.status || 'not_started')}${videoGeneration.error ? ` · ${escapeHtml(videoGeneration.error)}` : ''}</div>
        <div class="curation-sub">YouTube: ${escapeHtml(publication.status || 'not_started')}${publication.url ? ` · <a href="${escapeHtml(publication.url)}" target="_blank">${escapeHtml(publication.url)}</a>` : ''}${publication.error ? ` · ${escapeHtml(publication.error)}` : ''}</div>
        ${production.published_current === false && publication.status === 'published' ? `<div class="curation-sub warn">O vídeo publicado não corresponde ao corte final atual.</div>` : ''}
      </div>
      ${dialogueMediaCurrent(summary) ? `<video controls onplay="markFinalVideoViewed()" src="/api/runs/${run.id}/file?path=${encodeURIComponent('output/final_video.mp4')}"></video>` : `<span class="badge rejected">${summary.legacy_video_artifact ? 'vídeo legado ocultado' : summary.video_exists ? 'vídeo inválido' : 'sem vídeo'}</span>`}
      <div class="final-actions">
        <button onclick="authenticateYoutube().catch(err => logLine(err.message))">Autenticar YouTube</button>
        <button onclick="generateApprovedVideos()" ${curation.can_generate_video ? '' : 'disabled'}>Gerar animação real</button>
        <button onclick="approveFinalCut()" ${curation.can_final_approve ? '' : 'disabled'}>Aprovar corte final</button>
        <button class="primary" onclick="publishGate()" ${curation.can_publish ? '' : 'disabled'}>Publicar</button>
      </div>
    </div>`;
}

function renderRun(run) {
  window.lastRenderedRun = run;
  const production = run.summary?.production_status || {};
  $('state').textContent = production.status ? productionStatusLabel(production.status) : run.status;
  $('state').className = ['blocked', 'publish_failed'].includes(production.status) || run.status === 'failed' ? 'bad' : ['published_current', 'ready_to_publish'].includes(production.status) || run.status === 'completed' ? 'ok' : '';
  $('scenes').textContent = run.summary?.scenes_count ?? 0;
  $('images').textContent = run.summary?.images_count ?? 0;
  $('audio').textContent = run.summary?.audio_count ?? 0;
  const visualGate = run.summary?.quality_metrics?.gate_status || run.summary?.curation?.quality_gate_status;
  $('quality').textContent = visualGate === 'passed' ? 'PASS' : visualGate === 'blocked' ? 'BLOCK' : '-';
  $('quality').className = visualGate === 'passed' ? 'ok' : visualGate === 'blocked' ? 'bad' : '';
  $('cost').textContent = `$${(run.summary?.cost_estimate?.total_usd ?? 0).toFixed(4)}`;
  $('retryBtn').disabled = !currentRun || run.status === 'running';
  $('runBtn').disabled = run.status === 'running';
  $('log').textContent = (run.log || []).join('\n');
  renderCuration(run);

  const monitoring = $('monitoring');
  const jobs = run.summary?.runpod_jobs || [];
  const q = run.summary?.quality_metrics || {};
  const consistency = q.visual_consistency || null;
  const voices = q.voices || [];
  monitoring.innerHTML = `
    ${renderCostQuota(run.summary || {})}
    <table>
      <thead><tr><th>Provider job</th><th>Provider</th><th>Status</th><th>Tempo</th><th>Custo</th><th>Erro</th></tr></thead>
      <tbody>${jobs.map(job => {
        const cost = Number.isFinite(Number(job.estimated_cost_usd)) && job.estimated_cost_usd !== null
          ? `$${Number(job.estimated_cost_usd).toFixed(4)}`
          : 'n/d';
        const execution = job.execution_seconds === null || job.execution_seconds === undefined
          ? 'GPU n/d'
          : `GPU ${job.execution_seconds}s`;
        return `<tr><td>${escapeHtml(job.job_id || '-')}</td><td>${escapeHtml(job.provider || '-')} · ${escapeHtml(job.model || '-')}</td><td>${escapeHtml(job.status || '-')}</td><td>${job.elapsed_seconds || 0}s · fila ${job.queue_seconds || 0}s · ${execution}</td><td>${cost}</td><td>${escapeHtml(job.error || '-')}</td></tr>`;
      }).join('')}</tbody>
    </table>
    <table>
      <thead><tr><th>Mídia</th><th>Técnico</th><th>Semântico</th><th>Identidade</th><th>Estilo</th><th>Objetos</th><th>Issues</th></tr></thead>
      <tbody>
        ${(q.images || []).map(item => `<tr><td>imagem cena ${item.scene_id}</td><td>${item.technical_score ?? '-'}</td><td>${item.semantic_score ?? '-'}</td><td>${item.identity_score ?? '-'}<br>${escapeHtml(characterIdentityDetail(item) || '-')}</td><td>${item.style_score ?? '-'}</td><td>${item.objects_score ?? '-'}</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
        ${consistency ? `<tr><td>coerência visual</td><td>-</td><td>-</td><td>-</td><td>${consistency.consistency_score || 0} · ${consistency.accepted ? 'PASS' : 'BLOCK'}</td><td>-</td><td>${(consistency.issues || []).join(', ') || '-'}</td></tr>` : ''}
      </tbody>
    </table>
    <table>
      <thead><tr><th>Mídia derivada</th><th>Qualidade</th><th>Detalhe</th><th>Issues</th></tr></thead>
      <tbody>
        ${(q.audio || []).map(item => `<tr><td>áudio cena ${item.scene_id}</td><td>${item.quality_score || 0}</td><td>${escapeHtml(audioQualityDetail(item))}${waveformHtml(item.waveform)}</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
        ${q.video ? `<tr><td>vídeo final</td><td>${q.video.quality_score || 0}</td><td>${q.video.duration_seconds || 0}s · ${q.video.bit_rate || 0}bps</td><td>${(q.video.issues || []).join(', ') || '-'}</td></tr>` : ''}
        ${voices.map(item => `<tr><td>voz cena ${item.scene_id}${item.turn_id ? ` · ${escapeHtml(item.turn_id)}` : ''}</td><td>${item.quality_score || 0}</td><td>${escapeHtml(`${item.voice_role || item.speaker_id || (item.voice_roles || []).join(', ') || '-'} · ${item.voice_id || (item.voice_ids || []).join(', ') || '-'} · ${item.text_characters || 0} chars · ${item.premium_audio ? 'premium' : 'revisar'}${item.voice_direction?.tone ? ` · ${item.voice_direction.tone}` : ''}`)}</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
      </tbody>
    </table>
  `;

  const assets = $('assets');
  assets.innerHTML = '';
  const summary = run.summary || {};
  const curation = summary.curation?.scenes || {};
  const castCharacters = summary.visual_bible?.cast_bible?.characters || [];
  for (const character of castCharacters) {
    for (const viewId of character.reference?.required_views || []) {
      const view = character.reference?.views?.[viewId] || {};
      if (!view.path || view.approved !== true) continue;
      const div = document.createElement('div');
      div.className = 'asset';
      div.innerHTML = `
        <img src="/api/runs/${run.id}/file?path=${encodeURIComponent(view.path)}" alt="Referência ${escapeHtml(character.name || character.id)} ${escapeHtml(viewId)}">
        <a href="/api/runs/${run.id}/file?path=${encodeURIComponent(view.path)}" target="_blank">${escapeHtml(character.name || character.id)} · ${escapeHtml(viewId)}</a>
        <div class="asset-meta">ref v${escapeHtml(character.reference?.version || 1)} · ${escapeHtml((view.checksum || '').slice(0, 12))}</div>`;
      assets.appendChild(div);
    }
  }
  for (const img of summary.scene_images || []) {
    if (img.image_path) {
      const div = document.createElement('div');
      div.className = 'asset';
      const sceneId = String(img.scene_id);
      const review = curation[sceneId] || {status: 'pending_review', note: ''};
      div.innerHTML = `
        <img src="/api/runs/${run.id}/file?path=${encodeURIComponent(img.image_path)}" alt="Cena ${escapeHtml(sceneId)}">
        <a href="/api/runs/${run.id}/file?path=${encodeURIComponent(img.image_path)}" target="_blank">Cena ${escapeHtml(sceneId)} · ${escapeHtml(img.camera_motion || 'motion')}</a>
        <div class="asset-meta"><span class="badge ${escapeHtml(review.status)}">${escapeHtml(review.status)}</span></div>`;
      assets.appendChild(div);
    }
  }
  for (const audio of summary.audio_files || []) {
    if (!audio.audio_path) continue;
    const div = document.createElement('div');
    div.className = 'asset';
    const roles = (audio.voice_roles || []).join(', ') || 'personagens';
    div.innerHTML = `
      <audio controls preload="metadata" src="${mediaUrl(run, audio.audio_path)}" aria-label="Áudio cena ${escapeHtml(audio.scene_id)}"></audio>
      <a href="${mediaUrl(run, audio.audio_path)}" target="_blank">Áudio cena ${escapeHtml(audio.scene_id)} · ${escapeHtml(roles)}</a>
      <div class="asset-meta">${escapeHtml(audio.generation_method || 'áudio')} · ${escapeHtml(audio.language || '-')} · ${escapeHtml((audio.dialogue_turns || []).length)} fala(s)</div>`;
    assets.appendChild(div);
  }
  const currentDialogueMedia = dialogueMediaCurrent(summary);
  for (const clip of summary.scene_videos || []) {
    if (clip.video_path && currentDialogueMedia) {
      const div = document.createElement('div');
      div.className = 'asset';
      div.innerHTML = `<video controls src="/api/runs/${run.id}/file?path=${encodeURIComponent(clip.video_path)}"></video><a href="/api/runs/${run.id}/file?path=${encodeURIComponent(clip.video_path)}" target="_blank">Clipe cena ${escapeHtml(clip.scene_id)} · ${escapeHtml(clip.provider || 'video')}</a><div class="asset-meta">score ${escapeHtml(clip.quality_score || 0)} · ${escapeHtml(clip.duration || 0)}s</div>`;
      assets.appendChild(div);
    }
  }
  if ((summary.scene_videos || []).some(clip => clip.video_path) && !currentDialogueMedia) {
    const div = document.createElement('div');
    div.className = 'asset';
    div.innerHTML = `<div class="asset-meta"><span class="badge rejected">mídia legada</span><br>Clipes anteriores preservados para auditoria, sem carregamento no player.</div>`;
    assets.appendChild(div);
  }
  if (currentDialogueMedia) {
    const div = document.createElement('div');
    div.className = 'asset';
    div.innerHTML = `<video controls src="/api/runs/${run.id}/file?path=${encodeURIComponent('output/final_video.mp4')}"></video><a href="/api/runs/${run.id}/file?path=${encodeURIComponent('output/final_video.mp4')}" target="_blank">Vídeo final</a>`;
    assets.appendChild(div);
  } else if (summary.legacy_video_artifact) {
    const div = document.createElement('div');
    div.className = 'asset';
    div.innerHTML = `<div class="asset-meta"><span class="badge rejected">vídeo legado ocultado</span><br>O MP4 anterior foi preservado para auditoria, mas não atende ao contrato atual de diálogo.</div>`;
    assets.appendChild(div);
  }
}

async function setCuration(sceneId, status) {
  if (!currentRun) return;
  const note = document.getElementById(`curation-note-${sceneId}`)?.value || '';
  const reason = document.getElementById(`curation-reason-${sceneId}`)?.value || '';
  if ((status === 'rejected' || status === 'retry_requested') && !note.trim() && !reason) {
    logLine(`informe um motivo ou nota para cena ${sceneId}`);
    return;
  }
  const active = window.lastRenderedRun?.summary?.curation?.scenes?.[String(sceneId)]?.active_attempt_id || 'attempt_1';
  const run = await api(`/api/runs/${currentRun}/curation`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({scene_id: sceneId, status, note, reason, attempt_id: active})
  });
  renderRun(run);
  logLine(`curadoria cena ${sceneId}: ${status}`);
}

async function setCastReferenceApproval(characterId, approved) {
  if (!currentRun) return;
  try {
    const run = await api(`/api/runs/${currentRun}/cast-reference-approval`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({character_id: characterId, approved})
    });
    renderRun(run);
    logLine(`Cast Bible ${characterId}: ${approved ? 'aprovada' : 'reprovada'}`);
  } catch (err) {
    logLine(`aprovação da Cast Bible bloqueada: ${err.message}`);
  }
}

async function uploadCastFront(characterId) {
  if (!currentRun) return;
  const input = document.getElementById(`cast-front-upload-${characterId}`);
  const file = input?.files?.[0];
  if (!file) {
    logLine(`selecione uma frente canônica para ${characterId}`);
    return;
  }
  const body = new FormData();
  body.append('character_id', characterId);
  body.append('reference', file);
  try {
    const response = await fetch(`/api/runs/${currentRun}/cast-front-reference`, {
      method: 'POST',
      body
    });
    const payload = await response.json();
    if (payload.run) renderRun(payload.run);
    if (!response.ok) throw new Error(payload.error || 'upload bloqueado');
    renderRun(payload);
    logLine(`frente canônica ${characterId}: aceita; vistas derivadas invalidadas`);
  } catch (err) {
    logLine(`frente canônica ${characterId}: ${err.message}`);
  }
}

async function exportCastLoraPacks() {
  if (!currentRun) return;
  try {
    const result = await api(`/api/runs/${currentRun}/cast-lora-export`, {method: 'POST'});
    if (result.run) renderRun(result.run);
    logLine(`packs LoRA exportados: ${(result.packs || []).length}`);
  } catch (err) {
    logLine(`export LoRA bloqueado: ${err.message}`);
  }
}

async function continueAfterCast() {
  if (!currentRun) return;
  try {
    const run = await api(`/api/runs/${currentRun}/continue-after-cast`, {method: 'POST'});
    currentRun = run.id;
    renderRun(run);
    logLine(`geração de cenas retomada: ${run.id}`);
    clearInterval(pollTimer);
    pollTimer = setInterval(poll, 2000);
  } catch (err) {
    logLine(`continuação bloqueada: ${err.message}`);
  }
}

async function activateAttempt(sceneId, attemptId) {
  if (!currentRun) return;
  const run = await api(`/api/runs/${currentRun}/attempt-active`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({scene_id: sceneId, attempt_id: attemptId})
  });
  renderRun(run);
  logLine(`tentativa ativa alterada: cena ${sceneId} · ${attemptId}`);
}

async function approveAttempt(sceneId, attemptId) {
  if (!currentRun) return;
  const run = await api(`/api/runs/${currentRun}/attempt-approval`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({scene_id: sceneId, attempt_id: attemptId})
  });
  renderRun(run);
  logLine(`tentativa aprovada: cena ${sceneId} · ${attemptId}`);
}

async function requestSceneRetry(sceneId) {
  if (!currentRun) return;
  const note = document.getElementById(`curation-note-${sceneId}`)?.value || '';
  const reason = document.getElementById(`curation-reason-${sceneId}`)?.value || '';
  const scope = document.getElementById(`curation-scope-${sceneId}`)?.value || 'image_video';
  if (!note.trim() && !reason) {
    logLine(`informe um motivo ou nota para retry da cena ${sceneId}`);
    return;
  }
  await setCuration(sceneId, 'retry_requested');
  let data;
  try {
    data = await api(`/api/runs/${currentRun}/retry-scene`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scene_id: sceneId, note, reason, scope})
    });
  } catch (err) {
    logLine(`retry bloqueado para cena ${sceneId}: ${err.message}`);
    await poll();
    return;
  }
  currentRun = data.id;
  logLine(`retry ${scope} iniciado para cena ${sceneId}: ${currentRun}`);
  await poll();
  clearInterval(pollTimer);
  pollTimer = setInterval(poll, 2000);
}

async function markFinalVideoViewed() {
  if (!currentRun) return;
  const run = await api(`/api/runs/${currentRun}/final-video-viewed`, {method: 'POST'});
  renderRun(run);
  logLine('vídeo final marcado como visualizado');
}

async function generateApprovedVideos() {
  if (!currentRun) return;
  const result = await api(`/api/runs/${currentRun}/generate-approved-videos`, {method: 'POST'});
  logLine(`animação real: ${result.status}`);
  clearInterval(pollTimer);
  pollTimer = setInterval(poll, 3000);
}

async function approveFinalCut() {
  if (!currentRun) return;
  const run = await api(`/api/runs/${currentRun}/final-approval`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({note: 'Aprovado na Sala de Curadoria'})
  });
  renderRun(run);
  logLine('corte final aprovado');
}

async function publishGate() {
  if (!currentRun) return;
  const result = await api(`/api/runs/${currentRun}/publish-gate`, {method: 'POST'});
  if (result.blocked) {
    logLine(`publicação bloqueada: ${(result.blockers || []).join(', ')}`);
  } else if (result.status === 'published') {
    logLine(`YouTube já publicado: ${result.url || result.video_id}`);
  } else if (result.status === 'queued' || result.status === 'uploading') {
    if (result.run) renderRun(result.run);
    logLine('upload YouTube iniciado');
    clearInterval(pollTimer);
    pollTimer = setInterval(poll, 3000);
  } else {
    logLine(`publicação: ${result.status || 'ok'}`);
  }
}

async function authenticateYoutube() {
  logLine('iniciando autenticação YouTube');
  const result = await api('/api/youtube/auth', {method: 'POST'});
  logLine(`YouTube: ${result.status}`);
  await refreshHealth();
}

async function poll() {
  if (!currentRun) return;
  try {
    const run = await api(`/api/runs/${currentRun}`);
    renderRun(run);
    const publicationStatus = run.summary?.publication?.status || '';
    const videoGenerationStatus = run.summary?.curation?.video_generation?.status || '';
    if ((run.status === 'completed' || run.status === 'failed') && !['queued', 'uploading'].includes(publicationStatus) && !['queued', 'running'].includes(videoGenerationStatus)) {
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
  try {
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
  } catch (err) {
    logLine(`execução bloqueada: ${err.message}`);
    $('runBtn').disabled = false;
    $('retryBtn').disabled = !currentRun;
  }
}

async function loadLatestRun() {
  try {
    const run = await api('/api/runs/latest');
    currentRun = run.id;
    renderRun(run);
    logLine(`último run carregado: ${currentRun}`);
  } catch (err) {
    logLine('nenhum run anterior carregado');
  }
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
loadLatestRun();
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
        run["updated_at"] = _utc_now_iso()


def _set_run(run_id: str, **updates: Any) -> None:
    with RUN_LOCK:
        RUNS[run_id].update(updates)
        RUNS[run_id]["updated_at"] = _utc_now_iso()


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

    video_artifact = _probe_video_artifact(video_path)
    summary: dict[str, Any] = {
        "status": final_state.get("status"),
        "current_step": final_state.get("current_step"),
        "scenes_count": final_state.get("scenes_count", 0),
        "images_count": final_state.get("images_count", 0),
        "audio_count": final_state.get("audio_count", 0),
        "generation_method": final_state.get("generation_method"),
        "video_path": str(video_path),
        "video_exists": video_artifact["exists"],
        "video_valid": video_artifact["valid"],
        "video_size": video_artifact["size_bytes"],
        "video_artifact": video_artifact,
        "scenes": final_state.get("scenes", []),
        "scene_images": final_state.get("scene_images", []),
        "scene_videos": final_state.get("scene_videos", []),
        "audio_files": final_state.get("audio_files", []),
        "runpod_jobs": final_state.get("runpod_jobs", []),
        "visual_bible": final_state.get("visual_bible", {}),
        "quality_metrics": final_state.get("quality_metrics", {}),
        "cost_estimate": final_state.get("cost_estimate", {}),
        "cast_resume_local_only": bool(
            final_state.get("cast_resume_local_only", False)
        ),
        "curation": {"status": "pending_review", "scenes": {}},
    }
    if video_artifact.get("ffprobe"):
        summary["ffprobe"] = video_artifact["ffprobe"]
    return summary


def _safe_float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_video_path(run_dir: Path, summary: dict[str, Any]) -> Path:
    video_path = Path(summary.get("video_path") or "output/final_video.mp4")
    return video_path if video_path.is_absolute() else run_dir / video_path


def _probe_video_artifact(video_path: Path) -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "probe_contract_version": 2,
        "exists": video_path.is_file(),
        "valid": False,
        "path": str(video_path),
        "size_bytes": video_path.stat().st_size if video_path.is_file() else 0,
        "mtime": video_path.stat().st_mtime if video_path.is_file() else None,
        "duration_seconds": 0.0,
        "frame_count": 0,
        "codec": None,
        "width": 0,
        "height": 0,
        "first_frame_decoded": False,
        "stream_decoded": False,
        "issues": [],
    }
    if not artifact["exists"]:
        artifact["issues"].append("missing_file")
        return artifact
    if artifact["size_bytes"] <= 0:
        artifact["issues"].append("empty_file")
        return artifact

    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=codec_name,width,height,nb_frames,nb_read_frames:format=duration,size,bit_rate",
                "-of",
                "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        artifact["issues"].append(f"ffprobe_unavailable:{type(exc).__name__}")
        return artifact
    if probe.returncode != 0:
        artifact["issues"].append("ffprobe_failed")
        artifact["probe_error"] = probe.stderr.strip()[:500]
        return artifact

    try:
        payload = json.loads(probe.stdout)
    except json.JSONDecodeError:
        artifact["issues"].append("ffprobe_invalid_json")
        return artifact
    artifact["ffprobe"] = payload
    streams = payload.get("streams") or []
    if not streams or not isinstance(streams[0], dict):
        artifact["issues"].append("missing_video_stream")
        return artifact

    stream = streams[0]
    fmt = payload.get("format") or {}
    duration = _safe_float_value(fmt.get("duration"))
    width = _safe_int_value(stream.get("width"))
    height = _safe_int_value(stream.get("height"))
    frame_count = max(
        _safe_int_value(stream.get("nb_read_frames")),
        _safe_int_value(stream.get("nb_frames")),
    )
    artifact.update(
        {
            "duration_seconds": round(duration, 3),
            "frame_count": frame_count,
            "codec": stream.get("codec_name"),
            "width": width,
            "height": height,
        }
    )
    if duration <= 0:
        artifact["issues"].append("zero_duration")
    if width <= 0 or height <= 0:
        artifact["issues"].append("invalid_video_dimensions")
    if frame_count <= 0:
        artifact["issues"].append("no_decodable_frames_reported")
    if artifact["issues"]:
        return artifact

    try:
        decode = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(video_path),
                "-map",
                "0:v:0",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        artifact["issues"].append(f"ffmpeg_unavailable:{type(exc).__name__}")
        return artifact
    if decode.returncode != 0:
        artifact["issues"].append("video_stream_decode_failed")
        artifact["decode_error"] = decode.stderr.strip()[:500]
        return artifact

    artifact["first_frame_decoded"] = True
    artifact["stream_decoded"] = True
    artifact["valid"] = True
    return artifact


def _validated_video_artifact(run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    video_path = _resolve_video_path(run_dir, summary)
    cached = summary.get("video_artifact")
    if video_path.is_file() and isinstance(cached, dict):
        stat = video_path.stat()
        if (
            cached.get("path") == str(video_path)
            and _safe_int_value(cached.get("size_bytes")) == stat.st_size
            and _safe_float_value(cached.get("mtime")) == stat.st_mtime
            and cached.get("probe_contract_version") == 2
            and cached.get("stream_decoded") is True
            and "valid" in cached
        ):
            return cached

    artifact = _probe_video_artifact(video_path)
    summary["video_artifact"] = artifact
    summary["video_exists"] = artifact["exists"]
    summary["video_valid"] = artifact["valid"]
    summary["video_size"] = artifact["size_bytes"]
    if artifact.get("ffprobe"):
        summary["ffprobe"] = artifact["ffprobe"]
    else:
        summary.pop("ffprobe", None)
    return artifact


def _video_artifact_signature(run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    artifact = dict(_validated_video_artifact(run_dir, summary))
    video_path = Path(artifact["path"])
    if not artifact["exists"]:
        return artifact
    digest = hashlib.sha256()
    with video_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    artifact["sha256"] = digest.hexdigest()
    return artifact


def _cost_quota_summary(summary: dict[str, Any]) -> dict[str, Any]:
    cost = summary.setdefault("cost_estimate", {})
    jobs = summary.get("runpod_jobs", [])
    voices = summary.get("quality_metrics", {}).get("voices", [])
    stored_total_usd = _safe_float_value(cost.get("total_usd"))
    stored_fal_usd = _safe_float_value(cost.get("fal_usd"))
    warn_usd = _safe_float_value(os.getenv("AI_FILM_COST_WARN_USD", "1.00"))
    limit_usd = _safe_float_value(os.getenv("AI_FILM_COST_LIMIT_USD", "2.00"))
    runpod_limit = _safe_float_value(os.getenv("AI_FILM_RUNPOD_COST_LIMIT_USD", "0.75"))
    runway_limit = _safe_float_value(os.getenv("AI_FILM_RUNWAY_COST_LIMIT_USD", "1.50"))
    fal_limit = _safe_float_value(os.getenv("AI_FILM_FAL_COST_LIMIT_USD", "2.00"))
    elevenlabs_character_limit = int(
        _safe_float_value(os.getenv("AI_FILM_ELEVENLABS_CHAR_LIMIT_PER_RUN", "1200"))
    )
    elevenlabs_characters = sum(
        int(_safe_float_value(item.get("text_characters")))
        for item in voices
        if item.get("premium_audio")
    )
    fal_jobs = [job for job in jobs if job.get("provider") == "fal"]
    fal_usd = round(
        (
            sum(_safe_float_value(job.get("estimated_cost_usd")) for job in fal_jobs)
            if fal_jobs
            else stored_fal_usd
        ),
        6,
    )
    cost["fal_usd"] = fal_usd
    component_total_usd = round(
        _safe_float_value(cost.get("llm_usd"))
        + _safe_float_value(cost.get("runpod_usd"))
        + _safe_float_value(cost.get("gemini_image_usd"))
        + _safe_float_value(cost.get("elevenlabs_usd"))
        + _safe_float_value(cost.get("runway_usd"))
        + fal_usd,
        6,
    )
    total_usd = round(
        max(
            component_total_usd,
            max(0.0, stored_total_usd - stored_fal_usd) + fal_usd,
        ),
        6,
    )
    cost["total_usd"] = total_usd
    provider_rows = [
        {
            "provider": "llm",
            "usd": round(_safe_float_value(cost.get("llm_usd")), 6),
            "quota": "tokens",
            "usage": {
                "input_tokens": cost.get("llm_input_tokens", 0),
                "output_tokens": cost.get("llm_output_tokens", 0),
            },
        },
        {
            "provider": "gemini_image",
            "usd": round(_safe_float_value(cost.get("gemini_image_usd")), 6),
            "quota": "images",
            "usage": {
                "jobs": sum(1 for job in jobs if job.get("provider") == "gemini"),
            },
        },
        {
            "provider": "elevenlabs",
            "usd": round(_safe_float_value(cost.get("elevenlabs_usd")), 6),
            "quota": "characters",
            "usage": {
                "characters": elevenlabs_characters,
                "limit_per_run": elevenlabs_character_limit,
                "remaining_per_run": max(
                    0,
                    elevenlabs_character_limit - elevenlabs_characters,
                ),
                "remaining_start": cost.get("elevenlabs_characters_remaining_start"),
                "remaining_end": cost.get("elevenlabs_characters_remaining_end"),
            },
        },
        {
            "provider": "runway",
            "usd": round(_safe_float_value(cost.get("runway_usd")), 6),
            "quota": "jobs",
            "usage": {
                "jobs": sum(1 for job in jobs if job.get("provider") == "runway"),
                "limit_usd": runway_limit,
            },
        },
        {
            "provider": "fal",
            "usd": fal_usd,
            "quota": "jobs",
            "usage": {
                "jobs": sum(1 for job in jobs if job.get("provider") == "fal"),
                "limit_usd": fal_limit,
            },
        },
        {
            "provider": "runpod",
            "usd": round(_safe_float_value(cost.get("runpod_usd")), 6),
            "quota": "serverless",
            "usage": {
                "jobs": sum(
                    1
                    for job in jobs
                    if job.get("provider") not in {"gemini", "runway", "fal"}
                ),
                "limit_usd": runpod_limit,
            },
        },
    ]
    warnings: list[str] = []
    blockers: list[str] = []
    if warn_usd and total_usd >= warn_usd:
        warnings.append(f"custo estimado acima do alerta: ${total_usd:.4f}")
    if limit_usd and total_usd > limit_usd:
        blockers.append(f"custo estimado excede limite por run: ${total_usd:.4f}")
    if runpod_limit and _safe_float_value(cost.get("runpod_usd")) > runpod_limit:
        warnings.append("RunPod acima do limite configurado")
    if runway_limit and _safe_float_value(cost.get("runway_usd")) > runway_limit:
        warnings.append("Runway acima do limite configurado")
    if fal_limit and fal_usd > fal_limit:
        blockers.append("fal.ai acima do limite configurado por run")
    if (
        elevenlabs_character_limit
        and elevenlabs_characters > elevenlabs_character_limit
    ):
        blockers.append("ElevenLabs acima do limite de caracteres por run")
    status = "blocked" if blockers else "warning" if warnings else "ok"
    return {
        "status": status,
        "total_usd": round(total_usd, 6),
        "warn_usd": warn_usd,
        "limit_usd": limit_usd,
        "providers": provider_rows,
        "warnings": warnings,
        "blockers": blockers,
    }


def _apply_production_status(
    summary: dict[str, Any],
    run_dir: Path,
    curation_blockers: list[str],
) -> dict[str, Any]:
    publication = summary.setdefault("publication", {})
    curation = summary.setdefault("curation", {})
    final_review = curation.setdefault("final_review", {})
    current_artifact = _video_artifact_signature(run_dir, summary)
    video_current = bool(
        current_artifact.get("valid")
        and summary.get("video_current", current_artifact.get("valid"))
    )
    current_artifact["dialogue_compliant"] = summary.get("video_dialogue_compliant")
    current_artifact["release_ready"] = video_current
    published_artifact = publication.get("artifact") or {}
    publication_status = str(publication.get("status") or "not_started")
    published_current = (
        publication_status == "published"
        and video_current
        and current_artifact.get("sha256") == published_artifact.get("sha256")
    )
    cost_quota = _cost_quota_summary(summary)
    blockers = list(curation_blockers)
    blockers.extend(cost_quota.get("blockers", []))
    publication_retry_available = bool(
        publication_status == "failed"
        and not blockers
        and final_review.get("status") == "final_approved"
    )

    if publication_status in {"queued", "uploading"}:
        status = publication_status
    elif published_current:
        status = "published_current"
    elif publication_retry_available:
        status = "ready_to_publish"
    elif publication_status == "failed":
        status = "publish_failed"
    elif (
        publication_status == "published"
        and final_review.get("status") != "final_approved"
    ):
        status = "published_stale"
    elif blockers:
        status = "blocked"
    elif final_review.get("status") == "final_approved":
        status = "ready_to_publish"
    elif publication_status == "published":
        status = "published_stale"
    elif video_current:
        status = "needs_final_review"
    elif bool(current_artifact.get("valid")):
        status = "legacy_video"
    elif bool(current_artifact.get("exists")):
        status = "invalid_video"
    else:
        status = "missing_video"

    production_status = {
        "status": status,
        "published_current": published_current,
        "current_artifact": current_artifact,
        "published_artifact": published_artifact,
        "publication_status": publication_status,
        "publication_retry_available": publication_retry_available,
        "curation_status": curation.get("status"),
        "final_review_status": final_review.get("status"),
        "cost_quota_status": cost_quota.get("status"),
        "blockers": blockers,
        "warnings": cost_quota.get("warnings", []),
    }
    summary["cost_quota"] = cost_quota
    summary["production_status"] = production_status
    return production_status


def _planned_scene_ids(summary: dict[str, Any]) -> list[str]:
    planned: list[str] = []
    for scene in summary.get("scenes", []):
        scene_id = scene.get("scene_id")
        if scene_id is not None and str(scene_id) not in planned:
            planned.append(str(scene_id))
    if not planned:
        scenes_count = int(_safe_float_value(summary.get("scenes_count")))
        planned.extend(str(index) for index in range(1, scenes_count + 1))
    if not planned:
        for image in summary.get("scene_images", []):
            scene_id = image.get("scene_id")
            if scene_id is not None and str(scene_id) not in planned:
                planned.append(str(scene_id))
    return planned


def _quality_gate_min_score() -> float:
    return max(
        0.0,
        min(100.0, _safe_float_value(os.getenv("IMAGE_SEMANTIC_MIN_SCORE"), 88.0)),
    )


def _scene_expected_cast_ids(summary: dict[str, Any], scene_id: str) -> list[str]:
    for scene in summary.get("scenes", []):
        if str(scene.get("scene_id")) != scene_id:
            continue
        return [
            str(character_id)
            for character_id in scene.get("cast_character_ids", [])
            if character_id
        ]
    return []


def _current_cast_reference_versions(
    summary: dict[str, Any], character_ids: list[str]
) -> dict[str, dict[str, Any]]:
    characters = {
        str(character.get("id")): character
        for character in summary.get("visual_bible", {})
        .get("cast_bible", {})
        .get("characters", [])
        if character.get("id")
    }
    return {
        character_id: {
            "version": _safe_int_value(
                (characters.get(character_id, {}).get("reference") or {}).get(
                    "version"
                ),
                1,
            ),
            "checksum": str(
                (characters.get(character_id, {}).get("reference") or {}).get(
                    "checksum"
                )
                or ""
            ),
        }
        for character_id in character_ids
    }


def _cast_reference_versions_match(
    generated: dict[str, Any],
    current: dict[str, Any],
) -> bool:
    return all(
        _safe_int_value((generated.get(character_id) or {}).get("version"), 0)
        == _safe_int_value(reference.get("version"), 0)
        and bool(reference.get("checksum"))
        and str((generated.get(character_id) or {}).get("checksum") or "")
        == str(reference.get("checksum") or "")
        for character_id, reference in current.items()
    )


def _attempt_automatic_gate(
    summary: dict[str, Any], scene_id: str, attempt: dict[str, Any]
) -> dict[str, Any]:
    image_job = attempt.get("image_job") or {}
    minimum = _quality_gate_min_score()
    expected_cast_ids = _scene_expected_cast_ids(summary, scene_id)
    identities = {
        str(item.get("character_id")): item
        for item in image_job.get("character_identity", [])
        if item.get("character_id")
    }
    identity_scores = [
        _safe_float_value(identities.get(character_id, {}).get("score"))
        for character_id in expected_cast_ids
    ]
    identity_accepted = all(
        identities.get(character_id, {}).get("accepted") is True
        or identities.get(character_id, {}).get("human_review_required") is True
        for character_id in expected_cast_ids
    )
    human_identity_review_ids = [
        character_id
        for character_id in expected_cast_ids
        if identities.get(character_id, {}).get("human_review_required") is True
    ]
    generated_versions = image_job.get("cast_reference_versions") or {}
    current_versions = _current_cast_reference_versions(summary, expected_cast_ids)
    reference_versions_current = _cast_reference_versions_match(
        generated_versions,
        current_versions,
    )
    hero_objects = list(image_job.get("hero_objects", []))
    gates = {
        "technical": {
            "score": _safe_float_value(image_job.get("technical_score")),
            "passed": image_job.get("technical_accepted") is True
            and _safe_float_value(image_job.get("technical_score")) >= minimum,
        },
        "semantic": {
            "score": _safe_float_value(image_job.get("semantic_score")),
            "passed": image_job.get("semantic_accepted") is True
            and _safe_float_value(image_job.get("semantic_score")) >= minimum,
            **(
                {"human_review_required": True}
                if image_job.get("animal_human_review_required") is True
                else {}
            ),
        },
        "identity": {
            "score": (
                round(sum(identity_scores) / len(identity_scores), 1)
                if identity_scores
                else None
            ),
            "passed": identity_accepted if expected_cast_ids else True,
            "required_character_ids": expected_cast_ids,
            "human_review_required": bool(human_identity_review_ids),
            "human_review_required_character_ids": human_identity_review_ids,
        },
        "style": {
            "score": _safe_float_value(image_job.get("style_score")),
            "passed": (
                image_job.get("style_accepted") is True
                and _safe_float_value(image_job.get("style_score")) >= minimum
            )
            or image_job.get("style_human_review_required") is True,
            "human_review_required": (
                image_job.get("style_human_review_required") is True
            ),
        },
        "objects": {
            "score": (
                100.0
                if image_job.get("hero_object_legibility") is True
                else 0.0 if hero_objects else None
            ),
            "passed": (
                image_job.get("hero_object_legibility") is True
                if hero_objects
                else True
            ),
        },
        "reference_version": {
            "score": None,
            "passed": reference_versions_current if expected_cast_ids else True,
        },
    }
    blockers = [name for name, gate in gates.items() if gate["passed"] is not True]
    return {
        "status": "passed" if not blockers else "blocked",
        "passed": not blockers,
        "minimum_score": minimum,
        "gates": gates,
        "blockers": blockers,
    }


def _visual_quality_blockers(
    summary: dict[str, Any], run_dir: Path, scene_ids: list[str]
) -> list[str]:
    images = summary.get("scene_images", [])
    metrics = summary.get("quality_metrics", {}).get("images", [])
    blockers: list[str] = []
    cast_bible = summary.get("visual_bible", {}).get("cast_bible", {})
    if scene_ids and not cast_bible:
        blockers.append("Cast Bible ausente")
    required_character_ids = {
        str(character_id)
        for character_id in cast_bible.get("required_for_scenes", [])
        if character_id
    }
    characters = {
        str(character.get("id")): character
        for character in cast_bible.get("characters", [])
        if character.get("id")
    }
    missing_character_references: list[str] = []
    missing_character_loras: list[str] = []
    image_providers = {
        str(item.get("generation_method") or item.get("provider") or "").lower()
        for item in images
    }
    lora_required = any("comfyui" in provider for provider in image_providers)
    for character_id in sorted(required_character_ids):
        character = characters.get(character_id, {})
        reference = character.get("reference", {})
        reference_path = _run_path({"run_dir": str(run_dir)}, reference.get("path"))
        required_views = reference.get("required_views") or []
        reference_views = reference.get("views") or {}
        views_valid = bool(required_views) and all(
            reference_views.get(view_id, {}).get("approved") is True
            and reference_views.get(view_id, {}).get("checksum")
            and (
                view_path := _run_path(
                    {"run_dir": str(run_dir)},
                    reference_views.get(view_id, {}).get("path"),
                )
            )
            and view_path.is_file()
            and view_path.stat().st_size > 1000
            for view_id in required_views
        )
        if (
            reference.get("approved") is not True
            or not reference.get("checksum")
            or not views_valid
            or not reference_path
            or not reference_path.is_file()
            or reference_path.stat().st_size <= 1000
        ):
            missing_character_references.append(
                str(character.get("name") or character_id)
            )
        if (
            lora_required
            and (character.get("lora") or {}).get("status") != "configured"
        ):
            missing_character_loras.append(str(character.get("name") or character_id))
    if missing_character_references:
        blockers.append(
            "Cast Bible sem referência aprovada: "
            + ", ".join(missing_character_references)
        )
    if missing_character_loras:
        blockers.append(
            "Cast Bible sem LoRA individual vigente: "
            + ", ".join(missing_character_loras)
        )
    lora_gate = summary.get("visual_bible", {}).get("lora_gate") or {}
    if lora_required and lora_gate.get("status") == "blocked":
        blockers.append(
            "Gate LoRA bloqueado: " + ", ".join(lora_gate.get("blockers", []))
        )

    for scene_id in scene_ids:
        image = next(
            (item for item in images if str(item.get("scene_id")) == scene_id),
            {},
        )
        metric = next(
            (item for item in metrics if str(item.get("scene_id")) == scene_id),
            {},
        )
        image_path = _run_path({"run_dir": str(run_dir)}, image.get("image_path"))
        if not image_path or not image_path.is_file():
            blockers.append(f"cena {scene_id} sem imagem final válida")
        provider = str(
            image.get("generation_method") or image.get("provider") or ""
        ).lower()
        if provider == "mock":
            blockers.append(f"cena {scene_id} usa imagem mock")
        if not metric:
            blockers.append(f"cena {scene_id} sem métricas de qualidade")
            continue
        issues = {str(issue) for issue in metric.get("issues", []) if issue}
        minimum = _quality_gate_min_score()
        if (
            metric.get("semantic_accepted") is not True
            or _safe_float_value(metric.get("semantic_score")) < minimum
        ):
            blockers.append(f"cena {scene_id} reprovada pelo gate semântico")
        if (
            metric.get("technical_accepted") is not True
            or _safe_float_value(metric.get("technical_score")) < minimum
        ):
            blockers.append(f"cena {scene_id} reprovada pelo gate técnico")
        if (
            not (
                metric.get("style_accepted") is True
                and _safe_float_value(metric.get("style_score")) >= minimum
            )
            and metric.get("style_human_review_required") is not True
        ):
            blockers.append(f"cena {scene_id} reprovada pelo gate de estilo")
        expected_cast_ids = _scene_expected_cast_ids(summary, scene_id)
        identity_by_id = {
            str(item.get("character_id")): item
            for item in metric.get("character_identity", [])
            if item.get("character_id")
        }
        if any(
            identity_by_id.get(character_id, {}).get("accepted") is not True
            and identity_by_id.get(character_id, {}).get("human_review_required")
            is not True
            for character_id in expected_cast_ids
        ):
            blockers.append(f"cena {scene_id} reprovada pelo gate de identidade")
        if (
            metric.get("hero_objects")
            and metric.get("hero_object_legibility") is not True
        ):
            blockers.append(f"cena {scene_id} reprovada pelo gate de objetos")
        generated_versions = metric.get("cast_reference_versions") or {}
        current_versions = _current_cast_reference_versions(summary, expected_cast_ids)
        if expected_cast_ids and not _cast_reference_versions_match(
            generated_versions,
            current_versions,
        ):
            blockers.append(
                f"cena {scene_id} usa versão antiga ou desconhecida do Cast Bible"
            )
        if "semantic_gate_blocked" in issues:
            blockers.append(f"cena {scene_id} bloqueada após retries semânticos")

    expected_count = int(_safe_float_value(summary.get("scenes_count")))
    if expected_count and len(scene_ids) != expected_count:
        blockers.append(
            f"quantidade de cenas inconsistente: {len(scene_ids)}/{expected_count}"
        )
    generation_method = str(summary.get("generation_method") or "").lower()
    if generation_method == "mock":
        blockers.append("vídeo final usa fallback mock")
    return list(dict.fromkeys(blockers))


def _apply_curation_summary(
    summary: dict[str, Any],
    run_dir: Path | None = None,
) -> dict[str, Any]:
    from open3d_implementation.core.dialogue_contract import enrich_scene_performance

    summary["scenes"] = [
        enrich_scene_performance(scene)
        for scene in summary.get("scenes", [])
        if isinstance(scene, dict)
    ]
    curation = summary.setdefault("curation", {})
    scenes = curation.setdefault("scenes", {})
    if not isinstance(scenes, dict):
        scenes = {}
        curation["scenes"] = scenes

    scene_images = summary.get("scene_images", [])
    scene_videos = summary.get("scene_videos", [])
    audio_files = summary.get("audio_files", [])
    quality_metrics = summary.setdefault("quality_metrics", {})
    image_metrics = quality_metrics.get("images", [])
    audio_metrics = quality_metrics.get("audio", [])
    scene_ids = _planned_scene_ids(summary)
    for scene_id in scene_ids:
        image = next(
            (item for item in scene_images if str(item.get("scene_id")) == scene_id),
            {},
        )
        video = next(
            (item for item in scene_videos if str(item.get("scene_id")) == scene_id),
            {},
        )
        audio = next(
            (item for item in audio_files if str(item.get("scene_id")) == scene_id),
            {},
        )
        image_metric = next(
            (item for item in image_metrics if str(item.get("scene_id")) == scene_id),
            {},
        )
        audio_metric = next(
            (item for item in audio_metrics if str(item.get("scene_id")) == scene_id),
            {},
        )
        attempt_id = "attempt_1"
        scenes.setdefault(
            scene_id,
            {
                "status": "pending_review",
                "note": "",
                "reason": "",
                "active_attempt_id": attempt_id,
                "approved_attempt_id": None,
                "attempts": [],
                "updated_at": None,
            },
        )
        scene_review = scenes[scene_id]
        attempts = scene_review.setdefault("attempts", [])
        if not attempts:
            attempts.append(
                {
                    "id": attempt_id,
                    "status": "active",
                    "created_at": _utc_now_iso(),
                    "image_path": image.get("image_path"),
                    "video_path": video.get("video_path"),
                    "audio_path": audio.get("audio_path"),
                    "audio_text": audio.get("text"),
                    "dialogue_turns": audio.get("dialogue_turns", []),
                    "voice_ids": audio.get("voice_ids", []),
                    "voice_roles": audio.get("voice_roles", []),
                    "image_provider": image.get("generation_method")
                    or image.get("provider"),
                    "video_provider": video.get("provider"),
                    "audio_provider": audio.get("generation_method"),
                    "image_quality_score": image_metric.get("quality_score", 0),
                    "image_semantic_score": image_metric.get("semantic_score"),
                    "image_semantic_accepted": image_metric.get("semantic_accepted"),
                    "image_job": dict(image_metric),
                    "audio_quality_score": audio_metric.get("quality_score", 0),
                    "audio_job": dict(audio_metric),
                    "prompt": image.get("prompt") or image.get("base_prompt"),
                }
            )
        scene_review.setdefault("active_attempt_id", attempt_id)
        active_attempt = next(
            (
                attempt
                for attempt in attempts
                if attempt.get("id") == scene_review.get("active_attempt_id")
            ),
            {},
        )
        if (
            active_attempt
            and active_attempt.get("image_path")
            and not active_attempt.get("image_job")
        ):
            repaired_attempt = _inherited_audio_retry_attempt(
                attempts,
                active_attempt,
            )
            if repaired_attempt.get("image_job"):
                active_attempt.clear()
                active_attempt.update(repaired_attempt)
        if active_attempt:
            automatic_gate = _attempt_automatic_gate(
                summary,
                scene_id,
                active_attempt,
            )
            active_attempt["automatic_gate"] = automatic_gate
            scene_review["automatic_gate"] = automatic_gate
            if (
                scene_review.get("status") == "approved"
                and not automatic_gate["passed"]
            ):
                scene_review.update(
                    {
                        "status": "automatic_gate_blocked",
                        "approved_attempt_id": None,
                        "updated_at": _utc_now_iso(),
                    }
                )
                if active_attempt.get("status") == "approved":
                    active_attempt["status"] = "active"
        if active_attempt and active_attempt.get("image_path"):
            quality_metrics["images"] = _replace_scene_record(
                quality_metrics.get("images", []),
                scene_id,
                {
                    "path": active_attempt.get("image_path"),
                    "generation_method": active_attempt.get("image_provider")
                    or "curation",
                    **_attempt_image_quality_patch(active_attempt),
                },
            )
            image_metrics = quality_metrics.get("images", [])
        if scene_review.get("status") == "approved":
            scene_review.setdefault(
                "approved_attempt_id", scene_review["active_attempt_id"]
            )

    approved = sum(
        1
        for scene_id in scene_ids
        if scenes.get(scene_id, {}).get("status") == "approved"
    )
    rejected = sum(
        1
        for scene_id in scene_ids
        if scenes.get(scene_id, {}).get("status") == "rejected"
    )
    retry_requested = sum(
        1
        for scene_id in scene_ids
        if scenes.get(scene_id, {}).get("status") == "retry_requested"
    )
    pending = sum(
        1
        for scene_id in scene_ids
        if scenes.get(scene_id, {}).get("status") == "pending_review"
    )
    automatic_blocked = sum(
        1
        for scene_id in scene_ids
        if scenes.get(scene_id, {}).get("status") == "automatic_gate_blocked"
    )
    run_dir = run_dir or Path(".")
    visual_quality_blockers = _visual_quality_blockers(summary, run_dir, scene_ids)
    from open3d_implementation.core.dialogue_contract import production_dialogue_gate

    video_generation = curation.setdefault(
        "video_generation",
        {
            "status": "not_started",
            "started_at": None,
            "completed_at": None,
            "error": None,
        },
    )
    dialogue_pre_video_gate = production_dialogue_gate(
        summary.get("scenes", []),
        audio_files,
        [],
    )
    quality_metrics["dialogue_pre_video"] = dialogue_pre_video_gate
    generation_dialogue_blockers = [
        f"diálogo: {item}" for item in dialogue_pre_video_gate.get("blockers", [])
    ]
    quality_blockers = [
        *visual_quality_blockers,
        *generation_dialogue_blockers,
    ]
    current_scene_videos = (
        scene_videos if video_generation.get("status") == "completed" else []
    )
    dialogue_gate = production_dialogue_gate(
        summary.get("scenes", []),
        audio_files,
        current_scene_videos,
    )
    if video_generation.get("status") != "completed":
        dialogue_gate = {
            **dialogue_gate,
            "passed": False,
            "blockers": [
                *dialogue_gate.get("blockers", []),
                "video_generation_not_current",
            ],
        }
    quality_metrics["dialogue"] = dialogue_gate
    dialogue_blockers = [
        f"diálogo: {item}" for item in dialogue_gate.get("blockers", [])
    ]
    blockers = list(quality_blockers)
    if pending:
        blockers.append(f"{pending} cena(s) pendente(s)")
    if rejected:
        blockers.append(f"{rejected} cena(s) reprovada(s)")
    if retry_requested:
        blockers.append(f"{retry_requested} retry(s) solicitado(s)")
    if automatic_blocked:
        blockers.append(f"{automatic_blocked} cena(s) bloqueada(s) pelo pré-gate")

    final_review = curation.setdefault("final_review", {})
    final_review.setdefault("status", "draft")
    final_review.setdefault("video_viewed", False)
    final_review.setdefault("approved_at", None)
    final_review.setdefault("note", "")
    video_artifact = _validated_video_artifact(run_dir, summary)
    technical_video_valid = bool(video_artifact.get("valid"))
    dialogue_video_compliant = dialogue_gate.get("passed") is True
    video_ready = technical_video_valid and dialogue_video_compliant
    summary["video_technically_valid"] = technical_video_valid
    summary["video_dialogue_compliant"] = dialogue_video_compliant
    summary["video_current"] = video_ready
    summary["video_valid"] = video_ready
    if not video_ready:
        final_review["video_viewed"] = False
        final_review.pop("viewed_at", None)
    if technical_video_valid and not dialogue_video_compliant:
        summary["legacy_video_artifact"] = {
            "path": video_artifact.get("path"),
            "size_bytes": video_artifact.get("size_bytes", 0),
            "technically_valid": True,
            "reason": "dialogue_contract_blocked",
            "blockers": dialogue_gate.get("blockers", []),
        }
    elif not summary.get("legacy_video_artifact", {}).get("archived"):
        summary.pop("legacy_video_artifact", None)
    scene_gate_passed = (
        bool(scene_ids) and approved == len(scene_ids) and not quality_blockers
    )
    can_final_approve = (
        scene_gate_passed and video_ready and bool(final_review.get("video_viewed"))
    )

    if technical_video_valid and not dialogue_video_compliant:
        blockers.append(
            "vídeo legado ocultado: regenere o corte com vozes por personagem e segmentos por fala"
        )
    elif not video_ready and scene_gate_passed:
        if video_artifact.get("exists"):
            issues = ", ".join(video_artifact.get("issues", [])) or "mídia inválida"
            blockers.append(f"vídeo final inválido ou corrompido: {issues}")
        else:
            blockers.append("vídeo final ausente")
    elif not scene_gate_passed:
        blockers.append("vídeo aguarda aprovação de 100% das cenas")

    if final_review.get("status") == "final_approved" and (
        not scene_gate_passed or not video_ready
    ):
        if not scene_gate_passed:
            final_review["status"] = (
                "quality_review_blocked" if quality_blockers else "scene_review_blocked"
            )
        else:
            final_review["status"] = "video_review_blocked"
        final_review["approved_at"] = None

    if final_review.get("status") == "final_approved":
        status = "final_approved"
    elif quality_blockers:
        status = "quality_review_blocked"
    elif not scene_gate_passed:
        status = "scene_review_blocked"
    elif not video_ready:
        status = "video_review_blocked"
    elif blockers:
        status = "scene_review_blocked"
    elif scene_ids and approved == len(scene_ids):
        status = "ready_for_final_review"
    else:
        status = "pending_review"

    if scene_gate_passed and video_ready and not final_review.get("video_viewed"):
        blockers.append("vídeo final ainda não visualizado")
    if (
        scene_gate_passed
        and video_ready
        and final_review.get("video_viewed")
        and final_review.get("status") != "final_approved"
    ):
        blockers.append("corte final ainda não aprovado")

    curation["status"] = status
    production_status = _apply_production_status(summary, run_dir, blockers)
    # Artifact probing remains technical; the public compatibility flag is release-ready.
    summary["video_valid"] = video_ready
    summary["video_current"] = video_ready
    curation.update(
        {
            "status": status,
            "approved_count": approved,
            "rejected_count": rejected,
            "pending_count": pending,
            "retry_requested_count": retry_requested,
            "automatic_blocked_count": automatic_blocked,
            "total_scenes": len(scene_ids),
            "blockers": blockers,
            "can_final_approve": can_final_approve,
            "can_generate_video": bool(
                scene_gate_passed
                and not video_ready
                and video_generation.get("status") not in {"queued", "running"}
            ),
            "can_publish": production_status.get("status") == "ready_to_publish",
            "quality_gate_status": "blocked" if quality_blockers else "passed",
            "quality_blockers": quality_blockers,
            "generation_dialogue_gate_status": (
                "passed" if dialogue_pre_video_gate.get("passed") else "blocked"
            ),
            "generation_dialogue_blockers": generation_dialogue_blockers,
            "dialogue_gate_status": (
                "passed" if dialogue_gate.get("passed") else "blocked"
            ),
            "dialogue_blockers": dialogue_blockers,
        }
    )
    return summary


def _approved_video_worker_gate(curation: Mapping[str, Any]) -> bool:
    if curation.get("can_generate_video") is True:
        return True
    generation_status = str(
        (curation.get("video_generation") or {}).get("status") or ""
    )
    total_scenes = _safe_int_value(curation.get("total_scenes"), 0)
    return bool(
        generation_status in {"queued", "running"}
        and curation.get("quality_gate_status") == "passed"
        and total_scenes > 0
        and _safe_int_value(curation.get("approved_count"), 0) == total_scenes
        and _safe_int_value(curation.get("pending_count"), 0) == 0
        and _safe_int_value(curation.get("rejected_count"), 0) == 0
        and _safe_int_value(curation.get("retry_requested_count"), 0) == 0
        and _safe_int_value(curation.get("automatic_blocked_count"), 0) == 0
    )


def _persist_summary(run: dict[str, Any]) -> None:
    summary = run.get("summary", {})
    if not summary:
        return
    summary_path = Path(run["run_dir"]) / "pipeline_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = summary_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(summary_path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _persist_cast_bible_registry(summary: dict[str, Any], run_dir: Path) -> Path:
    cast_bible = summary.get("visual_bible", {}).get("cast_bible") or {}
    schema_version = str(cast_bible.get("schema_version") or "")
    style_key = str(cast_bible.get("style_key") or summary.get("image_style") or "")
    if schema_version != "2.0" or not style_key:
        raise ValueError("cast_bible_v2_registry_required")

    resolved_run_dir = run_dir.resolve()
    approved_characters: list[dict[str, Any]] = []
    for source_character in cast_bible.get("characters", []):
        character = copy.deepcopy(source_character)
        reference = character.get("reference") or {}
        if reference.get("human_approved") is not True:
            continue
        required_views = list(reference.get("required_views") or [])
        views = reference.get("views") or {}
        if not required_views:
            raise ValueError(f"cast_reference_views_missing:{character.get('id')}")
        for view_id in required_views:
            view = views.get(view_id) or {}
            raw_path = str(view.get("path") or "")
            path = Path(raw_path)
            resolved = (
                path.expanduser().resolve()
                if path.is_absolute()
                else (resolved_run_dir / path).resolve()
            )
            if resolved_run_dir not in resolved.parents:
                raise ValueError(f"cast_reference_path_outside_run:{view_id}")
            if (
                view.get("human_approved") is not True
                or not resolved.is_file()
                or resolved.stat().st_size <= 1000
                or _file_sha256(resolved) != view.get("checksum")
            ):
                raise ValueError(f"cast_reference_view_invalid:{view_id}")
            view["path"] = str(resolved)
        primary_view = views.get("three_quarter") or {}
        if not primary_view.get("path"):
            raise ValueError("cast_reference_primary_view_missing")
        reference["path"] = str(primary_view["path"])
        approved_characters.append(character)

    configured = os.getenv("AI_FILM_CAST_BIBLE_REGISTRY", "").strip()
    registry_path = (
        Path(configured).expanduser().resolve()
        if configured
        else (REPO_ROOT / "data" / "cast_bible_registry.json").resolve()
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": schema_version,
        "revision": cast_bible.get("revision"),
        "style_key": style_key,
        "updated_at": _utc_now_iso(),
        "characters": approved_characters,
    }
    temp_path = registry_path.with_suffix(f"{registry_path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(registry_path)
    return registry_path


def _invalidate_assets_for_cast_change(summary: dict[str, Any]) -> None:
    curation = summary.setdefault("curation", {})
    for review in curation.setdefault("scenes", {}).values():
        review.update(
            {
                "status": "pending_review",
                "approved_attempt_id": None,
                "updated_at": _utc_now_iso(),
            }
        )
        for attempt in review.get("attempts", []):
            if attempt.get("status") == "approved":
                attempt["status"] = "active"
    curation["video_generation"] = {
        "status": "not_started",
        "started_at": None,
        "completed_at": None,
        "error": None,
    }
    curation["final_review"] = {
        "status": "draft",
        "video_viewed": False,
        "approved_at": None,
        "note": "",
    }
    summary.update(
        {
            "scene_videos": [],
            "video_path": "",
            "video_exists": False,
            "video_valid": False,
            "video_artifact": {},
            "generation_method": "awaiting_approved_stills",
        }
    )


def _refresh_cast_stage(
    summary: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> str:
    from open3d_implementation.core.langgraph_adapter import (
        _cast_reference_waiting_stage,
        _flux2_lora_gate,
        _image_generation_provider,
        _refresh_cast_bible_status,
        _required_production_cast,
    )

    load_dotenv(OPEN3D_ROOT / ".env", override=True)
    visual_bible = summary.get("visual_bible") or {}
    scenes = list(summary.get("scenes") or [])
    required_characters = _required_production_cast(scenes, visual_bible)
    cast_status = _refresh_cast_bible_status(
        visual_bible,
        required_characters,
        base_dir=base_dir,
    )
    if cast_status.get("status") == "blocked":
        stage = _cast_reference_waiting_stage(required_characters)
        lora_gate = {"status": "blocked", "blockers": ["cast_reference_pending"]}
    else:
        image_provider = _image_generation_provider()
        lora_gate = (
            _flux2_lora_gate(scenes, visual_bible)
            if image_provider == "comfyui"
            else {
                "status": "approved",
                "blockers": [],
                "reason": f"not_required_for_{image_provider}",
            }
        )
        stage = (
            "ready_to_generate_scenes"
            if lora_gate.get("status") == "approved"
            else "awaiting_character_lora_training"
        )
    visual_bible["lora_gate"] = lora_gate
    summary["visual_bible"] = visual_bible
    summary["status"] = stage
    summary["current_step"] = stage
    summary.setdefault("quality_metrics", {})["cast_reference_status"] = (
        "pending_human_review"
        if stage == "awaiting_cast_reference_approval"
        else (
            "regeneration_required"
            if stage == "awaiting_cast_reference_regeneration"
            else cast_status.get("status")
        )
    )
    summary["quality_metrics"]["lora_gate"] = lora_gate
    return stage


def _decode_cast_reference_upload(raw: bytes) -> Image.Image:
    if len(raw) <= 1000:
        raise ValueError("cast_reference_upload_too_small")
    if len(raw) > MAX_CAST_REFERENCE_UPLOAD_BYTES:
        raise ValueError("cast_reference_upload_too_large")
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("cast_reference_upload_format_not_allowed")
            if int(getattr(source, "n_frames", 1)) != 1:
                raise ValueError("cast_reference_upload_must_be_single_frame")
            width, height = source.size
            if width * height > MAX_CAST_REFERENCE_UPLOAD_PIXELS:
                raise ValueError("cast_reference_upload_pixel_limit")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
    ) as exc:
        raise ValueError("cast_reference_upload_invalid_image") from exc
    width, height = image.size
    if width < 512 or height < 512:
        raise ValueError("cast_reference_upload_dimensions_too_small")
    aspect_ratio = width / max(1, height)
    if not 0.55 <= aspect_ratio <= 1.20:
        raise ValueError("cast_reference_upload_requires_portrait")
    return image


def _run_path(run: dict[str, Any], media_path: str | None) -> Path | None:
    if not media_path:
        return None
    path = Path(media_path)
    if not path.is_absolute():
        path = Path(run["run_dir"]) / path
    return path


def _summary_scene(summary: dict[str, Any], scene_id: str) -> dict[str, Any]:
    for scene in summary.get("scenes", []):
        if str(scene.get("scene_id")) == scene_id:
            return dict(scene)
    for image in summary.get("scene_images", []):
        if str(image.get("scene_id")) == scene_id:
            base_prompt = image.get("base_prompt") or ""
            description = image.get("description") or ""
            must_include: list[str] = []
            if scene_id == "1":
                description = (
                    "Alice está no jardim da universidade, junto às raízes de uma "
                    "faia antiga, observando um pequeno formigueiro."
                )
                must_include = ["small anthill in the grass"]
            elif scene_id == "2":
                description = (
                    "Na sala de jantar vitoriana, Ludovico revela o truque do "
                    "açucareiro: um pequeno ratinho branco surge do açucareiro "
                    "sobre a mesa de chá."
                )
                must_include = ["small white mouse emerging from the sugar bowl"]
            elif scene_id == "3":
                description = (
                    "Alice encontra uma toca funda no barranco do jardim e percebe "
                    "o chamado visual para a aventura."
                )
                must_include = ["dark rabbit hole in a grassy embankment"]
            return {
                "scene_id": image.get("scene_id"),
                "prompt": base_prompt,
                "description": description or base_prompt,
                "duration": image.get("duration", 6),
                "camera_motion": image.get("camera_motion", ""),
                "must_include": must_include,
            }
    return {"scene_id": scene_id, "prompt": "", "description": "", "duration": 6}


def _active_attempt(summary: dict[str, Any], scene_id: str) -> dict[str, Any]:
    scene_review = summary.get("curation", {}).get("scenes", {}).get(scene_id, {})
    active_attempt_id = scene_review.get("active_attempt_id")
    attempts = scene_review.get("attempts", [])
    for attempt in attempts:
        if attempt.get("id") == active_attempt_id:
            return dict(attempt)
    return dict(attempts[-1]) if attempts else {}


def _next_attempt_id(summary: dict[str, Any], scene_id: str) -> str:
    attempts = (
        summary.get("curation", {})
        .get("scenes", {})
        .get(scene_id, {})
        .get("attempts", [])
    )
    return f"attempt_{len(attempts) + 1}"


def _find_attempt(
    summary: dict[str, Any], scene_id: str, attempt_id: str
) -> dict[str, Any]:
    attempts = (
        summary.get("curation", {})
        .get("scenes", {})
        .get(scene_id, {})
        .get("attempts", [])
    )
    for attempt in attempts:
        if attempt.get("id") == attempt_id:
            return attempt
    return {}


def _replace_scene_record(
    records: list[dict[str, Any]],
    scene_id: str,
    patch: dict[str, Any],
) -> list[dict[str, Any]]:
    replaced = False
    updated: list[dict[str, Any]] = []
    for record in records:
        if str(record.get("scene_id")) == scene_id:
            updated.append(
                {**record, **patch, "scene_id": record.get("scene_id", scene_id)}
            )
            replaced = True
        else:
            updated.append(record)
    if not replaced:
        updated.append({"scene_id": scene_id, **patch})
    return updated


def _persist_generated_video_items(
    summary: dict[str, Any],
    generated: list[dict[str, Any]],
    *,
    require_current_approval: bool,
) -> int:
    persisted = 0
    for item in generated:
        scene_id = str(item["scene_id"])
        attempt_id = str(item["attempt_id"])
        review = summary.get("curation", {}).get("scenes", {}).get(scene_id, {})
        if review.get("approved_attempt_id") != attempt_id:
            if require_current_approval:
                raise RuntimeError(f"approved_attempt_changed:{scene_id}")
            continue
        attempt = _find_attempt(summary, scene_id, attempt_id)
        if not attempt:
            if require_current_approval:
                raise RuntimeError(f"approved_attempt_missing:{scene_id}")
            continue
        previous_video_path = str(attempt.get("video_path") or "")
        next_video_path = str(item.get("video_path") or "")
        if previous_video_path and previous_video_path != next_video_path:
            history = attempt.setdefault("video_attempts", [])
            if not any(
                str(record.get("video_path") or "") == previous_video_path
                for record in history
                if isinstance(record, dict)
            ):
                history.append(
                    {
                        "video_path": previous_video_path,
                        "video_provider": attempt.get("video_provider"),
                        "video_quality_score": attempt.get("video_quality_score"),
                        "video_job": copy.deepcopy(attempt.get("video_job") or {}),
                        "temporal_identity": copy.deepcopy(
                            attempt.get("temporal_identity") or {}
                        ),
                        "dialogue_segments": copy.deepcopy(
                            attempt.get("dialogue_segments") or []
                        ),
                        "duration": attempt.get("duration"),
                        "superseded_at": _utc_now_iso(),
                    }
                )
        attempt.update(item)
        summary["scene_videos"] = _replace_scene_record(
            summary.get("scene_videos", []),
            scene_id,
            {
                "video_path": item["video_path"],
                "provider": item["video_provider"],
                "quality_score": item["video_quality_score"],
                "duration": item["duration"],
                "temporal_identity": item["temporal_identity"],
                "dialogue_segments": copy.deepcopy(item.get("dialogue_segments") or []),
                "language": item.get("language", "pt-BR"),
                "narration_absent": item.get("narration_absent", True),
            },
        )
        persisted += 1
    return persisted


def _find_scene_quality_record(
    summary: dict[str, Any],
    scene_id: str,
) -> dict[str, Any]:
    for record in summary.get("quality_metrics", {}).get("images", []):
        if str(record.get("scene_id")) == scene_id:
            return dict(record)
    return {}


def _controlled_image_retry_available(strategy: str = "controlled_inpaint") -> bool:
    provider = os.getenv("IMAGE_GENERATION_PROVIDER", "comfyui").strip().lower()
    controlnet_model = os.getenv(
        "COMFYUI_CONTROLNET_CANNY_MODEL",
        "controlnet-canny-sdxl-1.0.safetensors",
    ).strip()
    return bool(
        provider == "comfyui"
        and os.getenv("RUNPOD_API_KEY")
        and os.getenv("RUNPOD_ENDPOINT_ID")
        and (strategy == "masked_inpaint" or bool(controlnet_model))
    )


def _controlled_retry_blocker(
    summary: dict[str, Any],
    scene_id: str,
    scope: str,
) -> dict[str, Any] | None:
    if scope not in {"image", "image_video", "full_scene"}:
        return None
    image_metric = _find_scene_quality_record(summary, scene_id)
    if not bool(image_metric.get("control_workflow_required")):
        return None
    strategy = str(
        image_metric.get("recommended_generation_strategy", "controlled_inpaint")
    )
    if _controlled_image_retry_available(strategy):
        return None
    return {
        "error": "controlled_workflow_unavailable",
        "scene_id": scene_id,
        "scope": scope,
        "recommended_generation_strategy": image_metric.get(
            "recommended_generation_strategy", "controlled_inpaint"
        ),
        "operator_next_action": image_metric.get("operator_next_action")
        or "Prepare ControlNet/inpaint before retrying this visual scene.",
        "issues": image_metric.get("issues", []),
    }


def _attempt_image_quality_patch(attempt: dict[str, Any]) -> dict[str, Any]:
    image_job = attempt.get("image_job") or {}
    return {
        "quality_score": attempt.get("image_quality_score", 0),
        "technical_score": image_job.get("technical_score"),
        "technical_accepted": image_job.get("technical_accepted"),
        "semantic_score": attempt.get("image_semantic_score"),
        "semantic_accepted": attempt.get("image_semantic_accepted"),
        "style_score": image_job.get("style_score"),
        "style_accepted": image_job.get("style_accepted"),
        "style_human_review_required": image_job.get(
            "style_human_review_required",
            False,
        ),
        "animal_human_review_required": image_job.get(
            "animal_human_review_required",
            False,
        ),
        "identity_score": image_job.get("identity_score"),
        "identity_accepted": image_job.get("identity_accepted"),
        "character_identity": image_job.get("character_identity", []),
        "objects_score": image_job.get("objects_score"),
        "objects_accepted": image_job.get("objects_accepted"),
        "cast_reference_versions": image_job.get("cast_reference_versions", {}),
        "semantic_critical_failures": image_job.get("semantic_critical_failures", []),
        "semantic_retry_prompt": image_job.get("semantic_retry_prompt", ""),
        "semantic_qa_model": image_job.get("semantic_qa_model"),
        "hero_objects": attempt.get("hero_objects")
        or image_job.get("hero_objects", []),
        "hero_object_legibility": (
            attempt.get("hero_object_legibility")
            if "hero_object_legibility" in attempt
            else image_job.get("hero_object_legibility")
        ),
        "hero_object_notes": attempt.get("hero_object_notes")
        or image_job.get("hero_object_notes", ""),
        "control_workflow_required": attempt.get("control_workflow_required")
        or image_job.get("control_workflow_required", False),
        "recommended_generation_strategy": attempt.get(
            "recommended_generation_strategy"
        )
        or image_job.get("recommended_generation_strategy", "txt2img_retry"),
        "operator_next_action": attempt.get("operator_next_action")
        or image_job.get("operator_next_action", ""),
        "controlled_workflow": attempt.get("controlled_workflow")
        or image_job.get("controlled_workflow", False),
        "controlnet_model": attempt.get("controlnet_model")
        or image_job.get("controlnet_model", ""),
        "control_image": attempt.get("control_image")
        or image_job.get("control_image", ""),
    }


def _attempt_audio_quality_patch(attempt: dict[str, Any]) -> dict[str, Any]:
    audio_job = attempt.get("audio_job") or {}
    return {
        "quality_score": attempt.get("audio_quality_score", 0),
        "premium_audio": audio_job.get("premium_audio"),
        "enhanced": audio_job.get("enhanced"),
        "ambient": audio_job.get("ambient"),
        "loudness": audio_job.get("loudness"),
        "waveform": audio_job.get("waveform", []),
        "voice_direction": attempt.get("voice_direction")
        or audio_job.get("voice_direction", {}),
        "voice_id": attempt.get("voice_id") or audio_job.get("voice_id"),
        "voice_role": attempt.get("voice_role") or audio_job.get("voice_role"),
        "voice_ids": attempt.get("voice_ids") or audio_job.get("voice_ids", []),
        "voice_roles": attempt.get("voice_roles") or audio_job.get("voice_roles", []),
        "dialogue_turns": attempt.get("dialogue_turns")
        or audio_job.get("dialogue_turns", []),
        "model_id": attempt.get("model_id") or audio_job.get("model"),
        "text_characters": audio_job.get("text_characters"),
        "issues": audio_job.get("issues", []),
    }


def _reset_final_gate(summary: dict[str, Any], status: str) -> None:
    final_review = summary.setdefault("curation", {}).setdefault("final_review", {})
    final_review.update(
        {
            "status": "draft",
            "video_viewed": False,
            "approved_at": None,
            "note": "",
        }
    )
    summary.setdefault("publication", {}).update({"status": status})


def _archive_legacy_final_video(
    summary: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any] | None:
    archive_dir = run_dir / "output" / "archive" / "legacy"
    manifest_path = archive_dir / "legacy_media_manifest.json"
    manifest = {"schema_version": "1.0", "assets": []}
    if manifest_path.is_file():
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            manifest = parsed

    def recover_from_manifest() -> dict[str, Any] | None:
        for asset in reversed(manifest.get("assets", [])):
            if not isinstance(asset, dict) or asset.get("archived") is not True:
                continue
            archived_path = _run_path(
                {"run_dir": str(run_dir)},
                str(asset.get("path") or ""),
            )
            if archived_path and archived_path.is_file():
                summary["legacy_video_artifact"] = dict(asset)
                return summary["legacy_video_artifact"]
        return None

    legacy = summary.get("legacy_video_artifact")
    if (
        not isinstance(legacy, dict)
        or legacy.get("reason") != "dialogue_contract_blocked"
    ):
        return recover_from_manifest()
    if legacy.get("archived"):
        archived_path = _run_path(
            {"run_dir": str(run_dir)},
            str(legacy.get("path") or ""),
        )
        return legacy if archived_path and archived_path.is_file() else None

    source = _resolve_video_path(run_dir, summary)
    if not source.is_file():
        return recover_from_manifest()

    archive_dir.mkdir(parents=True, exist_ok=True)
    digest = _file_sha256(source)
    destination = archive_dir / f"narrated_final_video_{digest[:12]}.mp4"
    if destination.exists() and _file_sha256(destination) != digest:
        raise RuntimeError("legacy_video_archive_checksum_conflict")
    if not destination.exists():
        shutil.move(str(source), str(destination))

    relative_destination = str(destination.relative_to(run_dir))
    archived = {
        **legacy,
        "path": relative_destination,
        "original_path": str(source.relative_to(run_dir)),
        "sha256": digest,
        "archived": True,
        "archived_at": _utc_now_iso(),
    }
    assets = [
        item
        for item in manifest.get("assets", [])
        if isinstance(item, dict) and item.get("sha256") != digest
    ]
    assets.append(archived)
    manifest.update({"schema_version": "1.0", "assets": assets})
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary["legacy_video_artifact"] = archived
    summary.pop("video_artifact", None)
    summary["video_exists"] = False
    summary["video_technically_valid"] = False
    summary["video_current"] = False
    summary["video_valid"] = False
    return archived


def _apply_attempt_to_summary(
    run: dict[str, Any],
    scene_id: str,
    attempt_id: str,
    approve: bool,
) -> dict[str, Any]:
    summary = run.get("summary", {})
    scene_review = (
        summary.setdefault("curation", {})
        .setdefault("scenes", {})
        .setdefault(scene_id, {"status": "pending_review", "attempts": []})
    )
    attempts = scene_review.setdefault("attempts", [])
    selected = _find_attempt(summary, scene_id, attempt_id)
    if not selected:
        raise ValueError("attempt not found")
    if selected.get("status") == "failed":
        raise ValueError("failed attempt cannot be activated")
    if approve:
        automatic_gate = _attempt_automatic_gate(summary, scene_id, selected)
        selected["automatic_gate"] = automatic_gate
        if not automatic_gate["passed"]:
            raise ValueError(
                "automatic_gate_blocked:" + ",".join(automatic_gate["blockers"])
            )

    for attempt in attempts:
        if attempt.get("id") == attempt_id:
            attempt["status"] = "approved" if approve else "active"
        elif attempt.get("status") != "failed":
            attempt["status"] = "superseded"

    if selected.get("image_path"):
        image_quality_patch = _attempt_image_quality_patch(selected)
        summary["scene_images"] = _replace_scene_record(
            summary.get("scene_images", []),
            scene_id,
            {
                "image_path": selected.get("image_path"),
                "generation_method": selected.get("image_provider") or "curation",
                "prompt": selected.get("prompt"),
            },
        )
        quality_metrics = summary.setdefault("quality_metrics", {})
        quality_metrics["images"] = _replace_scene_record(
            quality_metrics.get("images", []),
            scene_id,
            {
                "path": selected.get("image_path"),
                "generation_method": selected.get("image_provider") or "curation",
                **image_quality_patch,
            },
        )
    if selected.get("video_path"):
        summary["scene_videos"] = _replace_scene_record(
            summary.get("scene_videos", []),
            scene_id,
            {
                "video_path": selected.get("video_path"),
                "provider": selected.get("video_provider") or "curation",
                "quality_score": selected.get("video_quality_score", 0),
            },
        )
    if selected.get("audio_path"):
        audio_quality_patch = _attempt_audio_quality_patch(selected)
        summary["audio_files"] = _replace_scene_record(
            summary.get("audio_files", []),
            scene_id,
            {
                "audio_path": selected.get("audio_path"),
                "text": selected.get("audio_text"),
                "dialogue_turns": selected.get("dialogue_turns", []),
                "voice_direction": selected.get("voice_direction")
                or audio_quality_patch.get("voice_direction"),
                "voice_id": selected.get("voice_id"),
                "voice_ids": selected.get("voice_ids", []),
                "voice_roles": selected.get("voice_roles", []),
                "generation_method": selected.get("audio_provider") or "curation",
            },
        )
        quality_metrics = summary.setdefault("quality_metrics", {})
        quality_metrics["audio"] = _replace_scene_record(
            quality_metrics.get("audio", []),
            scene_id,
            {
                "path": selected.get("audio_path"),
                "generation_method": selected.get("audio_provider") or "curation",
                **audio_quality_patch,
            },
        )
        quality_metrics["voices"] = _replace_scene_record(
            quality_metrics.get("voices", []),
            scene_id,
            audio_quality_patch,
        )

    scene_review.update(
        {
            "status": "approved" if approve else "pending_review",
            "active_attempt_id": attempt_id,
            "approved_attempt_id": attempt_id if approve else None,
            "retry_status": None,
            "updated_at": _utc_now_iso(),
        }
    )
    _reset_final_gate(summary, "stale_after_attempt_change")
    summary.setdefault("curation", {}).setdefault("video_generation", {}).update(
        {
            "status": "stale_after_attempt_change",
            "completed_at": None,
            "error": None,
        }
    )
    run["summary"] = summary
    run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
    run["updated_at"] = _utc_now_iso()
    _persist_summary(run)
    return run


def _retry_instruction(reason: str, note: str, scope: str) -> str:
    correction = f"{reason}. {note}".strip(". ")
    extras = {
        "artefatos/texto": "Remove all visible text, captions, watermarks, logos, malformed borders and typography.",
        "personagem incorreto": "Preserve the correct protagonist identity and required characters exactly; remove wrong or duplicate characters.",
        "estilo inconsistente": "Match the global visual bible, color palette, lens language, wardrobe, era and finish of the approved scenes.",
        "cena não fiel ao texto": "Obey the story excerpt and required objects literally; do not invent unrelated action or props.",
        "rosto/anatomia ruim": "Fix face, eyes, hands, proportions and anatomy while preserving the character identity.",
        "movimento ruim": "Keep the image faithful; the video retry must use subtle coherent cinematic motion only.",
    }
    return (
        "Director curation correction. "
        f"Retry scope: {scope}. "
        f"Requested correction: {correction or 'Improve fidelity and remove visual defects'}. "
        f"{extras.get(reason, '')} "
        "Preserve continuity with approved scenes. Correct only the issue pointed out by the director."
    ).strip()


def _ffmpeg_concat_file(filelist_path: Path, paths: list[Path]) -> None:
    filelist_path.write_text(
        "".join(f"file '{path.resolve()}'\n" for path in paths),
        encoding="utf-8",
    )


def _normalize_and_concat_video_clips(
    clip_paths: list[Path],
    output_path: Path,
) -> None:
    if not clip_paths:
        raise ValueError("video_clip_paths_required")

    artifacts = [_probe_video_artifact(path) for path in clip_paths]
    invalid_paths = [
        str(path)
        for path, artifact in zip(clip_paths, artifacts, strict=True)
        if not artifact.get("valid")
    ]
    if invalid_paths:
        raise RuntimeError(
            "video_clip_normalization_source_invalid:" + ",".join(invalid_paths)
        )

    target_width = max(_safe_int_value(item.get("width"), 0) for item in artifacts)
    target_height = max(_safe_int_value(item.get("height"), 0) for item in artifacts)
    target_width += target_width % 2
    target_height += target_height % 2
    if target_width <= 0 or target_height <= 0:
        raise RuntimeError("video_clip_normalization_dimensions_invalid")

    command = ["ffmpeg", "-nostdin", "-y"]
    for clip_path in clip_paths:
        command.extend(["-i", str(clip_path)])

    filters: list[str] = []
    for index in range(len(clip_paths)):
        filters.append(
            f"[{index}:v]"
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,fps=24,settb=AVTB,setpts=PTS-STARTPTS"
            f"[v{index}]"
        )
    inputs = "".join(f"[v{index}]" for index in range(len(clip_paths)))
    filters.append(f"{inputs}concat=n={len(clip_paths)}:v=1:a=0[outv]")
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg_video_normalization_failed:{result.stderr[:300]}")


def _approved_stills_manifest(
    summary: dict[str, Any], run_dir: Path
) -> list[dict[str, str]]:
    manifest: list[dict[str, str]] = []
    for scene_id in _planned_scene_ids(summary):
        review = summary.get("curation", {}).get("scenes", {}).get(scene_id, {})
        attempt_id = str(review.get("approved_attempt_id") or "")
        if review.get("status") != "approved" or not attempt_id:
            raise RuntimeError(f"scene_not_human_approved:{scene_id}")
        attempt = _find_attempt(summary, scene_id, attempt_id)
        gate = _attempt_automatic_gate(summary, scene_id, attempt)
        if not gate["passed"]:
            raise RuntimeError(
                f"scene_automatic_gate_blocked:{scene_id}:{','.join(gate['blockers'])}"
            )
        image_path = _run_path({"run_dir": str(run_dir)}, attempt.get("image_path"))
        if (
            not image_path
            or not image_path.is_file()
            or image_path.stat().st_size <= 1000
        ):
            raise RuntimeError(f"approved_still_missing:{scene_id}")
        digest = hashlib.sha256()
        with image_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest.append(
            {
                "scene_id": scene_id,
                "attempt_id": attempt_id,
                "image_sha256": digest.hexdigest(),
            }
        )
    return manifest


def _recompile_final_video_from_attempts(run: dict[str, Any]) -> dict[str, Any]:
    from open3d_implementation.core.langgraph_adapter import (
        _audio_loudness_target_lufs,
        _probe_media_quality,
    )

    run_dir = Path(run["run_dir"])
    output_dir = run_dir / "output"
    summary = run.get("summary", {})
    scene_ids = _planned_scene_ids(summary)
    source_manifest = _approved_stills_manifest(summary, run_dir)
    clip_paths: list[Path] = []
    for scene_id in scene_ids:
        scene_review = summary.get("curation", {}).get("scenes", {}).get(scene_id, {})
        attempt = _find_attempt(
            summary,
            scene_id,
            str(scene_review.get("approved_attempt_id") or ""),
        )
        if attempt.get("status") != "approved":
            raise RuntimeError(f"approved_attempt_not_selected:{scene_id}")
        if attempt.get("video_provider") not in {"runway", "fal_kling"}:
            raise RuntimeError(f"real_video_provider_required:{scene_id}")
        temporal_identity = attempt.get("temporal_identity") or {}
        if temporal_identity.get("accepted") is not True:
            raise RuntimeError(f"temporal_identity_gate_blocked:{scene_id}")
        clip_path = _run_path(run, attempt.get("video_path"))
        if not clip_path:
            raise RuntimeError(f"approved_scene_clip_missing:{scene_id}")
        clip_artifact = _probe_video_artifact(clip_path)
        if not clip_artifact["valid"]:
            raise RuntimeError(f"approved_scene_clip_invalid:{scene_id}")
        clip_paths.append(clip_path)

    if not scene_ids or len(clip_paths) != len(scene_ids):
        raise RuntimeError("approved_scene_clip_count_mismatch")

    from open3d_implementation.core.dialogue_contract import production_dialogue_gate

    dialogue_gate = production_dialogue_gate(
        summary.get("scenes", []),
        summary.get("audio_files", []),
        summary.get("scene_videos", []),
    )
    if not dialogue_gate.get("passed"):
        raise RuntimeError(
            "dialogue_video_gate_blocked:"
            + ",".join(str(item) for item in dialogue_gate.get("blockers", []))
        )

    output_dir.mkdir(exist_ok=True)
    temp_video = output_dir / "curation_temp_video.mp4"
    pending_final_video = output_dir / "final_video.next.mp4"
    final_video = output_dir / "final_video.mp4"
    _normalize_and_concat_video_clips(clip_paths, temp_video)

    audio_paths = []
    for scene_id in scene_ids:
        attempt = _active_attempt(summary, scene_id)
        audio_path = _run_path(run, attempt.get("audio_path"))
        if audio_path and audio_path.exists() and audio_path.stat().st_size > 1000:
            audio_paths.append(audio_path)
            continue
        fallback_audio = _run_path(
            run,
            next(
                (
                    item.get("audio_path")
                    for item in summary.get("audio_files", [])
                    if str(item.get("scene_id")) == scene_id
                ),
                "",
            ),
        )
        if (
            fallback_audio
            and fallback_audio.exists()
            and fallback_audio.stat().st_size > 1000
        ):
            audio_paths.append(fallback_audio)
    audio_paths = [
        path
        for path in audio_paths
        if path and path.exists() and path.stat().st_size > 1000
    ]
    if audio_paths:
        audio_list = output_dir / "curation_audio_filelist.txt"
        combined_audio = output_dir / "curation_combined_audio.m4a"
        _ffmpeg_concat_file(audio_list, audio_paths)
        audio_result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(audio_list),
                "-af",
                f"loudnorm=I={_audio_loudness_target_lufs():.1f}:TP=-1.5:LRA=11",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                str(combined_audio),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if audio_result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg_audio_concat_failed:{audio_result.stderr[:300]}"
            )
        mux_result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(temp_video),
                "-i",
                str(combined_audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(pending_final_video),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if mux_result.returncode != 0:
            raise RuntimeError(f"ffmpeg_mux_failed:{mux_result.stderr[:300]}")
    else:
        temp_video.replace(pending_final_video)

    pending_artifact = _probe_video_artifact(pending_final_video)
    if not pending_artifact["valid"]:
        issues = ", ".join(pending_artifact.get("issues", [])) or "invalid_video"
        raise RuntimeError(f"final_video_validation_failed:{issues}")
    pending_final_video.replace(final_video)

    for temp_path in (
        temp_video,
        output_dir / "curation_audio_filelist.txt",
        output_dir / "curation_combined_audio.m4a",
    ):
        if temp_path.exists():
            temp_path.unlink()

    video_metric = _probe_media_quality(str(final_video), "video")
    summary["video_path"] = str(final_video)
    summary["video_source_manifest"] = source_manifest
    approved_video_providers = {
        str(_active_attempt(summary, scene_id).get("video_provider") or "")
        for scene_id in scene_ids
    }
    if len(approved_video_providers) != 1:
        raise RuntimeError("mixed_video_providers_not_supported")
    summary["generation_method"] = f"{approved_video_providers.pop()}_approved_stills"
    video_artifact = _probe_video_artifact(final_video)
    summary["video_artifact"] = video_artifact
    summary["video_exists"] = video_artifact["exists"]
    summary["video_valid"] = video_artifact["valid"]
    summary["video_size"] = video_artifact["size_bytes"]
    quality_metrics = summary.setdefault("quality_metrics", {})
    quality_metrics["video"] = video_metric
    return video_metric


def _extract_temporal_validation_frames(
    clip_path: Path,
    output_dir: Path,
) -> tuple[list[Path], dict[str, Any]]:
    artifact = _probe_video_artifact(clip_path)
    if not artifact["valid"]:
        issues = ",".join(artifact.get("issues", [])) or "invalid_video"
        raise RuntimeError(f"temporal_source_invalid:{issues}")
    duration = _safe_float_value(artifact.get("duration_seconds"))
    positions = (0.0, duration / 2.0, max(0.0, duration - 0.1))
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    for index, position in enumerate(positions, start=1):
        frame_path = output_dir / f"frame_{index}.jpg"
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{position:.3f}",
                "-i",
                str(clip_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(frame_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if (
            result.returncode != 0
            or not frame_path.is_file()
            or frame_path.stat().st_size <= 1000
        ):
            raise RuntimeError(f"temporal_frame_decode_failed:{index}")
        frames.append(frame_path)
    return frames, artifact


def _temporal_identity_min_score() -> float:
    return max(
        0.0,
        min(100.0, _safe_float_value(os.getenv("TEMPORAL_IDENTITY_MIN_SCORE"), 75.0)),
    )


def _temporal_identity_frame_floor() -> float:
    return max(
        0.0,
        min(
            _temporal_identity_min_score(),
            _safe_float_value(os.getenv("TEMPORAL_IDENTITY_FRAME_FLOOR"), 70.0),
        ),
    )


def _temporal_identity_frame_accepted(
    score: float,
    model_accepted: bool,
) -> bool:
    return model_accepted or score >= _temporal_identity_frame_floor()


def _temporal_identity_character_gate(
    frame_results: list[dict[str, Any]],
) -> dict[str, Any]:
    required_passing_frames = max(
        1,
        math.ceil(len(frame_results) * 2 / 3),
    )
    strongest_frames = sorted(
        frame_results,
        key=lambda item: float(item["score"]),
        reverse=True,
    )[:required_passing_frames]
    character_score = round(
        sum(float(item["score"]) for item in strongest_frames) / len(strongest_frames),
        1,
    )
    frame_floor = _temporal_identity_frame_floor()
    passing_frames = sum(
        1
        for item in frame_results
        if item["accepted"] and float(item["score"]) >= frame_floor
    )
    return {
        "score": character_score,
        "accepted": (
            character_score >= _temporal_identity_min_score()
            and passing_frames >= required_passing_frames
        ),
        "passing_frames": passing_frames,
        "required_passing_frames": required_passing_frames,
    }


def _temporal_tracking_boxes(
    anchor_box: tuple[int, int, int, int],
    source_size: tuple[int, int],
    frame_size: tuple[int, int],
) -> list[tuple[int, int, int, int]]:
    source_width, source_height = source_size
    frame_width, frame_height = frame_size
    if min(source_width, source_height, frame_width, frame_height) <= 0:
        return []
    scale_x = frame_width / source_width
    scale_y = frame_height / source_height
    left, top, right, bottom = anchor_box
    scaled_width = max(24, round((right - left) * scale_x))
    scaled_height = max(24, round((bottom - top) * scale_y))
    center_x = ((left + right) / 2) * scale_x
    center_y = ((top + bottom) / 2) * scale_y
    boxes: list[tuple[int, int, int, int]] = []
    for vertical_offset in (-1.5, -0.75, 0.0, 0.75, 1.5):
        for horizontal_offset in (-1.5, -0.75, 0.0, 0.75, 1.5):
            candidate_center_x = center_x + horizontal_offset * scaled_width
            candidate_center_y = center_y + vertical_offset * scaled_height
            candidate = (
                max(0, round(candidate_center_x - scaled_width / 2)),
                max(0, round(candidate_center_y - scaled_height / 2)),
                min(frame_width, round(candidate_center_x + scaled_width / 2)),
                min(frame_height, round(candidate_center_y + scaled_height / 2)),
            )
            if candidate[2] - candidate[0] >= 24 and candidate[3] - candidate[1] >= 24:
                boxes.append(candidate)
    return boxes


def _evaluate_temporal_identity(
    *,
    clip_path: Path,
    scene_id: str,
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    from open3d_implementation.core.local_visual_qa import (
        LocalVisualQAError,
        detect_local_face_boxes,
        evaluate_local_narrative_identity,
    )

    try:
        frames, artifact = _extract_temporal_validation_frames(clip_path, output_dir)
        expected_ids = _scene_expected_cast_ids(summary, scene_id)
        if not expected_ids:
            return {
                "accepted": True,
                "score": 100.0,
                "frames": [str(frame) for frame in frames],
                "characters": [],
                "video_artifact": artifact,
                "issues": [],
            }
        characters = {
            str(character.get("id")): character
            for character in summary.get("visual_bible", {})
            .get("cast_bible", {})
            .get("characters", [])
            if character.get("id")
        }
        scene_review = summary.get("curation", {}).get("scenes", {}).get(scene_id, {})
        approved_attempt = _find_attempt(
            summary,
            scene_id,
            str(scene_review.get("approved_attempt_id") or ""),
        )
        approved_still = _run_path(
            {"run_dir": str(output_dir.parents[2])},
            approved_attempt.get("image_path"),
        )
        if not approved_still or not approved_still.is_file():
            raise RuntimeError(f"temporal_approved_still_missing:{scene_id}")

        def reference_paths(character: dict[str, Any]) -> list[Path]:
            reference = character.get("reference") or {}
            views = reference.get("views") or {}
            paths: list[Path] = []
            for view_id in (
                "front",
                "expression_neutral",
                "expression_concerned",
                "three_quarter",
            ):
                resolved = _run_path(
                    {"run_dir": str(output_dir.parents[2])},
                    (views.get(view_id) or {}).get("path"),
                )
                if resolved and resolved.is_file() and resolved not in paths:
                    paths.append(resolved)
            return paths[:3]

        with Image.open(approved_still) as source_image:
            source_size = source_image.size
            detected_anchor_boxes = list(detect_local_face_boxes(source_image))

        anchor_assessments: dict[str, Any] = {}
        if len(expected_ids) > 1 and len(detected_anchor_boxes) >= len(expected_ids):
            from itertools import permutations

            candidate_boxes = detected_anchor_boxes[: max(4, len(expected_ids) * 2)]
            assessment_matrix: dict[str, list[Any]] = {}
            for character_id in expected_ids:
                identity_references = reference_paths(characters.get(character_id, {}))
                if not identity_references:
                    raise RuntimeError(f"temporal_reference_missing:{character_id}")
                negative_references = [
                    path
                    for other_id, other_character in characters.items()
                    if other_id != character_id
                    for path in reference_paths(other_character)
                ][:12]
                assessment_matrix[character_id] = [
                    evaluate_local_narrative_identity(
                        reference_paths=identity_references,
                        candidate_path=approved_still,
                        character_id=character_id,
                        negative_reference_paths=negative_references,
                        candidate_boxes_override=[candidate_box],
                        restrict_candidate_boxes=True,
                    )
                    for candidate_box in candidate_boxes
                ]
            assignments = permutations(
                range(len(candidate_boxes)),
                len(expected_ids),
            )
            best_assignment = max(
                assignments,
                key=lambda assignment: (
                    sum(
                        assessment_matrix[character_id][box_index].accepted
                        for character_id, box_index in zip(
                            expected_ids,
                            assignment,
                            strict=True,
                        )
                    ),
                    sum(
                        assessment_matrix[character_id][box_index].score
                        for character_id, box_index in zip(
                            expected_ids,
                            assignment,
                            strict=True,
                        )
                    ),
                    sum(
                        assessment_matrix[character_id][box_index].face_similarity
                        for character_id, box_index in zip(
                            expected_ids,
                            assignment,
                            strict=True,
                        )
                    ),
                ),
            )
            anchor_assessments = {
                character_id: assessment_matrix[character_id][box_index]
                for character_id, box_index in zip(
                    expected_ids,
                    best_assignment,
                    strict=True,
                )
            }

        minimum = _temporal_identity_min_score()
        frame_floor = _temporal_identity_frame_floor()
        character_results: list[dict[str, Any]] = []
        character_scores: list[float] = []
        for character_id in expected_ids:
            character = characters.get(character_id, {})
            identity_references = reference_paths(character)
            if not identity_references:
                raise RuntimeError(f"temporal_reference_missing:{character_id}")
            negative_references = [
                path
                for other_id, other_character in characters.items()
                if other_id != character_id
                for path in reference_paths(other_character)
            ][:12]
            anchor_assessment = anchor_assessments.get(character_id)
            if anchor_assessment is None:
                anchor_assessment = evaluate_local_narrative_identity(
                    reference_paths=identity_references,
                    candidate_path=approved_still,
                    character_id=character_id,
                    negative_reference_paths=negative_references,
                )
            frame_results: list[dict[str, Any]] = []
            for frame in frames:
                with Image.open(frame) as frame_image:
                    tracking_boxes = _temporal_tracking_boxes(
                        anchor_assessment.candidate_box,
                        source_size,
                        frame_image.size,
                    )
                canonical_assessment = evaluate_local_narrative_identity(
                    reference_paths=identity_references,
                    candidate_path=frame,
                    character_id=character_id,
                    negative_reference_paths=negative_references,
                    candidate_boxes_override=tracking_boxes,
                )
                assessments = [("cast_bible", canonical_assessment)]
                shot_assessment = evaluate_local_narrative_identity(
                    reference_paths=[approved_still],
                    candidate_path=frame,
                    character_id=character_id,
                    reference_boxes_override=[anchor_assessment.candidate_box],
                    candidate_boxes_override=tracking_boxes,
                )
                assessments.append(("approved_still", shot_assessment))
                assessment_source, assessment = max(
                    assessments,
                    key=lambda item: (
                        item[1].accepted,
                        item[1].score,
                        item[1].face_similarity,
                    ),
                )
                dimensions = {
                    "face": assessment.score,
                    "face_similarity": round(
                        assessment.face_similarity * 100,
                        1,
                    ),
                    "contrastive_margin": (
                        round(max(0.0, assessment.similarity_margin) * 100, 1)
                        if assessment.similarity_margin is not None
                        else 100.0
                    ),
                }
                frame_accepted = _temporal_identity_frame_accepted(
                    float(assessment.score),
                    bool(assessment.accepted),
                )
                frame_results.append(
                    {
                        "frame_path": str(frame),
                        "score": assessment.score,
                        "accepted": frame_accepted,
                        "model_accepted": assessment.accepted,
                        "dimensions": dimensions,
                        "checks": [
                            {
                                "code": "identity_face_embedding",
                                "matched": frame_accepted,
                                "model_matched": assessment.accepted,
                                "reference_source": assessment_source,
                                "face_similarity": assessment.face_similarity,
                                "face_threshold": assessment.face_threshold,
                                "closest_negative_similarity": (
                                    assessment.closest_negative_similarity
                                ),
                                "similarity_margin": assessment.similarity_margin,
                                "margin_threshold": assessment.margin_threshold,
                                "candidate_box": list(assessment.candidate_box),
                                "issues": list(assessment.issues),
                            }
                        ],
                    }
                )
            character_gate = _temporal_identity_character_gate(frame_results)
            character_score = float(character_gate["score"])
            character_scores.append(character_score)
            character_results.append(
                {
                    "character_id": character_id,
                    "character_name": character.get("name") or character_id,
                    "score": character_score,
                    "accepted": character_gate["accepted"],
                    "passing_frames": character_gate["passing_frames"],
                    "required_passing_frames": character_gate[
                        "required_passing_frames"
                    ],
                    "frames": frame_results,
                }
            )
        overall = (
            round(sum(character_scores) / len(character_scores), 1)
            if character_scores
            else 0.0
        )
        accepted = overall >= minimum and all(
            character["accepted"] for character in character_results
        )
        return {
            "accepted": accepted,
            "score": overall,
            "minimum_score": minimum,
            "frame_floor": frame_floor,
            "frames": [str(frame) for frame in frames],
            "characters": character_results,
            "video_artifact": artifact,
            "issues": [] if accepted else ["temporal_identity_drift"],
        }
    except (
        LocalVisualQAError,
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        return {
            "accepted": False,
            "score": 0.0,
            "frames": [],
            "characters": [],
            "issues": [f"temporal_identity_qa_failed:{type(exc).__name__}:{exc}"],
        }


def _run_approved_video_generation(run_id: str) -> None:
    from open3d_implementation.core.dialogue_contract import (
        build_speaker_motion_prompt,
        dialogue_turns,
    )
    from open3d_implementation.core.langgraph_adapter import (
        _generate_real_video_clip,
        _video_generation_provider,
    )

    generated: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    video_provider = _video_generation_provider()
    try:
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = _apply_curation_summary(
                run.get("summary", {}), Path(run["run_dir"])
            )
            if not _approved_video_worker_gate(summary.get("curation", {})):
                raise RuntimeError("approved_stills_gate_blocked")
            summary["curation"]["video_generation"] = {
                "status": "running",
                "started_at": _utc_now_iso(),
                "completed_at": None,
                "error": None,
            }
            run["summary"] = summary
            _persist_summary(run)
            snapshot = copy.deepcopy(run)

        snapshot_summary = snapshot["summary"]
        run_dir = Path(snapshot["run_dir"])
        curation_dir = run_dir / "output" / "curation"
        curation_dir.mkdir(parents=True, exist_ok=True)
        for scene_id in _planned_scene_ids(snapshot_summary):
            review = snapshot_summary["curation"]["scenes"][scene_id]
            attempt_id = str(review.get("approved_attempt_id") or "")
            attempt = _find_attempt(snapshot_summary, scene_id, attempt_id)
            if attempt.get("status") != "approved":
                raise RuntimeError(f"approved_attempt_missing:{scene_id}")
            image_path = _run_path(snapshot, attempt.get("image_path"))
            if not image_path or not image_path.is_file():
                raise RuntimeError(f"approved_still_missing:{scene_id}")
            scene = _summary_scene(snapshot_summary, scene_id)
            expected_turns = dialogue_turns(scene)
            audio_record = next(
                (
                    item
                    for item in snapshot_summary.get("audio_files", [])
                    if str(item.get("scene_id")) == scene_id
                ),
                {},
            )
            rendered_turns = audio_record.get("dialogue_turns", [])
            if len(rendered_turns) != len(expected_turns):
                raise RuntimeError(f"dialogue_audio_turn_count_mismatch:{scene_id}")
            if not rendered_turns:
                raise RuntimeError(f"dialogue_audio_missing:{scene_id}")

            clip_path = (
                curation_dir / f"scene_{scene_id}_{attempt_id}_{video_provider}.mp4"
            )
            segment_paths: list[Path] = []
            dialogue_segments: list[dict[str, Any]] = []
            segment_jobs: list[dict[str, Any]] = []
            for turn_index, turn in enumerate(rendered_turns, 1):
                lip_sync_required = bool(turn.get("lip_sync_required"))
                turn_duration = max(
                    3.0,
                    _safe_float_value(turn.get("duration_seconds")),
                )
                segment_path = curation_dir / (
                    f"scene_{scene_id}_{attempt_id}_turn_{turn_index}_"
                    f"{video_provider}.mp4"
                )
                recovered_artifact = _probe_video_artifact(segment_path)
                if recovered_artifact.get("valid"):
                    segment_job = {
                        "provider": "fal",
                        "service": "kling_dialogue_segment",
                        "scene_id": scene_id,
                        "turn_id": turn.get("turn_id") or f"turn_{turn_index}",
                        "status": "COMPLETED",
                        "output_path": str(segment_path),
                        "quality_score": 100,
                        "estimated_cost_usd": 0.0,
                        "recovered_from_disk": True,
                        "video_artifact": recovered_artifact,
                    }
                else:
                    turn_audio_path = _run_path(snapshot, turn.get("audio_path"))
                    if lip_sync_required and not turn_audio_path:
                        raise RuntimeError(
                            f"dialogue_turn_audio_missing:{scene_id}:{turn_index}"
                        )
                    source = {
                        **scene,
                        "scene_id": scene_id,
                        "image_path": str(image_path),
                        "dialogue_turn": turn,
                        "prompt": build_speaker_motion_prompt(scene, turn),
                        "base_prompt": build_speaker_motion_prompt(scene, turn),
                    }
                    segment_job, ok = _generate_real_video_clip(
                        source,
                        str(segment_path),
                        turn_duration,
                        audio_path=(
                            str(turn_audio_path)
                            if lip_sync_required and turn_audio_path
                            else None
                        ),
                        visual_bible=snapshot_summary.get("visual_bible"),
                        enable_lipsync=lip_sync_required,
                    )
                    if not ok:
                        raise RuntimeError(
                            f"{video_provider}_dialogue_turn_failed:"
                            f"{scene_id}:{turn_index}:{segment_job.get('error')}"
                        )
                segment_job.update(
                    {
                        "scene_id": scene_id,
                        "turn_id": turn.get("turn_id") or f"turn_{turn_index}",
                        "speaker_id": turn.get("speaker_id"),
                        "lip_sync_required": lip_sync_required,
                        "mouth_motion_policy": (
                            "active_speaker_only"
                            if lip_sync_required
                            else "all_mouths_closed"
                        ),
                    }
                )
                jobs.append(segment_job)
                segment_jobs.append(segment_job)
                segment_paths.append(segment_path)
                dialogue_segments.append(
                    {
                        "turn_id": turn.get("turn_id") or f"turn_{turn_index}",
                        "speaker_id": turn.get("speaker_id"),
                        "speaker_name": turn.get("speaker_name"),
                        "mode": turn.get("mode"),
                        "lip_sync_required": lip_sync_required,
                        "lipsync_status": segment_job.get("lipsync_status"),
                        "video_path": str(segment_path),
                        "job_id": segment_job.get("job_id"),
                        "duration": turn_duration,
                    }
                )

            segment_filelist = curation_dir / (
                f"scene_{scene_id}_{attempt_id}_dialogue_segments.txt"
            )
            _ffmpeg_concat_file(segment_filelist, segment_paths)
            concat_result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(segment_filelist),
                    "-c:v",
                    "copy",
                    "-an",
                    str(clip_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            segment_filelist.unlink(missing_ok=True)
            if concat_result.returncode != 0:
                raise RuntimeError(
                    f"dialogue_scene_concat_failed:{scene_id}:"
                    f"{concat_result.stderr[:300]}"
                )
            duration = sum(
                _safe_float_value(item.get("duration")) for item in dialogue_segments
            )
            job = {
                "provider": "fal",
                "service": "kling_dialogue_scene",
                "scene_id": scene_id,
                "status": "COMPLETED",
                "output_path": str(clip_path),
                "quality_score": min(
                    (
                        _safe_float_value(item.get("quality_score"))
                        for item in segment_jobs
                    ),
                    default=0.0,
                ),
                "estimated_cost_usd": round(
                    sum(
                        _safe_float_value(item.get("estimated_cost_usd"))
                        for item in segment_jobs
                    ),
                    6,
                ),
                "dialogue_segments": dialogue_segments,
            }
            temporal = _evaluate_temporal_identity(
                clip_path=clip_path,
                scene_id=scene_id,
                summary=snapshot_summary,
                output_dir=curation_dir / f"{clip_path.stem}_temporal",
            )
            generated.append(
                {
                    "scene_id": scene_id,
                    "attempt_id": attempt_id,
                    "video_path": str(clip_path),
                    "video_provider": video_provider,
                    "video_quality_score": job.get("quality_score", 0),
                    "video_job": job,
                    "temporal_identity": temporal,
                    "duration": duration,
                    "dialogue_segments": dialogue_segments,
                    "language": "pt-BR",
                    "narration_absent": True,
                }
            )
            if temporal.get("accepted") is not True:
                issues = ",".join(temporal.get("issues", []))
                raise RuntimeError(
                    f"temporal_identity_gate_blocked:{scene_id}:{issues}"
                )
            _append_log(run_id, f"animação real validada para cena {scene_id}")

        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = run.get("summary", {})
            _persist_generated_video_items(
                summary,
                generated,
                require_current_approval=True,
            )
            summary.setdefault("runpod_jobs", []).extend(jobs)
            run["summary"] = summary
            _recompile_final_video_from_attempts(run)
            _reset_final_gate(summary, "stale_after_video_regeneration")
            summary["curation"]["video_generation"].update(
                {
                    "status": "completed",
                    "completed_at": _utc_now_iso(),
                    "error": None,
                }
            )
            run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        _append_log(run_id, "animações aprovadas compiladas e validadas")
    except (
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = run.get("summary", {})
            persisted_count = _persist_generated_video_items(
                summary,
                generated,
                require_current_approval=False,
            )
            summary.setdefault("runpod_jobs", []).extend(jobs)
            summary.setdefault("curation", {}).setdefault(
                "video_generation", {}
            ).update(
                {
                    "status": "failed",
                    "completed_at": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        if persisted_count:
            _append_log(
                run_id,
                f"{persisted_count} animação(ões) concluída(s) preservada(s) para retry",
            )
        _append_log(run_id, f"falha na animação aprovada: {type(exc).__name__}: {exc}")


def _run_selective_visual_retry(
    run_id: str,
    scene_id: str,
    note: str,
    reason: str,
    scope: str,
) -> None:
    from open3d_implementation.core.langgraph_adapter import (
        _build_image_prompt,
        _comfyui_controlnet_available,
        _generate_real_video_clip,
        _image_generation_provider,
        _resolve_comfyui_checkpoint,
        _resolve_image_style,
        _resolve_quality_preset,
        _run_comfyui_image_attempt,
        _run_fal_flux_image_attempt,
        _run_gemini_image_attempt,
        _safe_float,
        _scene_audio_duration,
        _scene_seed,
        _video_generation_provider,
    )

    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return
        summary = run.get("summary", {})
        previous_summary = json.loads(json.dumps(summary))
        scene_review = (
            summary.setdefault("curation", {})
            .setdefault("scenes", {})
            .setdefault(
                scene_id,
                {"status": "pending_review", "attempts": []},
            )
        )
        previous_active_attempt_id = scene_review.get("active_attempt_id")
        previous_approved_attempt_id = scene_review.get("approved_attempt_id")
        attempt_id = _next_attempt_id(summary, scene_id)
        scene_review["status"] = "retry_requested"
        scene_review["retry_status"] = "running"
        scene_review["retry_scope"] = scope
        scene_review["note"] = note
        scene_review["reason"] = reason
        scene_review["updated_at"] = _utc_now_iso()
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)

    _append_log(
        run_id, f"retry seletivo real iniciado: cena {scene_id}, escopo {scope}"
    )

    try:
        run_dir = Path(run["run_dir"])
        curation_dir = run_dir / "output" / "curation"
        curation_dir.mkdir(parents=True, exist_ok=True)
        summary = run.get("summary", {})
        scene = _summary_scene(summary, scene_id)
        image_style = str(
            run.get("image_style") or summary.get("image_style") or "comic_storybook"
        )
        quality_preset_key = str(
            run.get("image_quality_preset")
            or summary.get("image_quality_preset")
            or "high"
        )
        visual_bible = summary.get("visual_bible", {})
        instruction = _retry_instruction(reason, note, scope)
        active_attempt = _active_attempt(summary, scene_id)
        source_image_metric = _find_scene_quality_record(summary, scene_id)
        base_image_path = _run_path(run, active_attempt.get("image_path"))
        image_path = base_image_path
        image_record = None
        image_metric = None
        image_job = None
        image_provider = _image_generation_provider()
        quality_preset = _resolve_quality_preset(quality_preset_key)
        checkpoint_name = _resolve_comfyui_checkpoint(image_style)
        style_label = _resolve_image_style(image_style)["label"]
        control_strategy = str(
            source_image_metric.get(
                "recommended_generation_strategy", "controlled_inpaint"
            )
        )
        control_backend_available = bool(
            control_strategy == "masked_inpaint" or _comfyui_controlnet_available()
        )
        controlled_workflow = bool(
            image_provider == "comfyui"
            and source_image_metric.get("control_workflow_required")
            and control_backend_available
        )
        if (
            source_image_metric.get("control_workflow_required")
            and image_provider == "comfyui"
            and control_backend_available
            and (not base_image_path or not base_image_path.exists())
        ):
            raise RuntimeError("controlled_retry_reference_image_missing")

        if scope in {"image", "image_video", "full_scene"}:
            image_path = curation_dir / f"scene_{scene_id}_{attempt_id}_image.png"
            if controlled_workflow:
                if control_strategy == "masked_inpaint":
                    instruction = (
                        f"{instruction} Use masked inpainting without ControlNet. "
                        "Rebuild only the hero-prop region at believable physical scale; "
                        "preserve everything outside the mask."
                    ).strip()
                else:
                    instruction = (
                        f"{instruction} Use the controlled ControlNet retry path: "
                        "make the required hero object sharp, natural and readable while "
                        "preserving approved character identity and global style."
                    ).strip()
            directed_prompt = _build_image_prompt(
                scene,
                image_style,
                visual_bible,
                instruction,
            )
            seed = _scene_seed(run_id, image_style, f"{scene_id}:{attempt_id}:curation")
            if image_provider == "comfyui":
                runpod_api_key = os.getenv("RUNPOD_API_KEY", "")
                runpod_endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "")
                if not (runpod_api_key and runpod_endpoint_id):
                    raise RuntimeError("comfyui_retry_missing_runpod_credentials")
                image_job, image_record, image_metric = _run_comfyui_image_attempt(
                    scene=scene,
                    image_path=str(image_path),
                    directed_prompt=directed_prompt,
                    image_style=image_style,
                    style_label=style_label,
                    quality_preset_key=quality_preset_key,
                    quality_preset=quality_preset,
                    checkpoint_name=checkpoint_name,
                    scene_seed=seed,
                    visual_bible=visual_bible,
                    runpod_endpoint_id=runpod_endpoint_id,
                    runpod_api_key=runpod_api_key,
                    runpod_gpu_usd_per_second=_safe_float(
                        os.getenv("RUNPOD_GPU_USD_PER_SECOND", "0.00044")
                    ),
                    attempt=int(attempt_id.split("_")[-1]),
                    controlled_workflow=controlled_workflow,
                    control_strategy=control_strategy,
                    control_image_path=(
                        str(base_image_path) if controlled_workflow else None
                    ),
                    reference_image_path=(
                        str(base_image_path)
                        if base_image_path and control_strategy != "masked_inpaint"
                        else None
                    ),
                )
            elif image_provider == "gemini":
                image_job, image_record, image_metric = _run_gemini_image_attempt(
                    scene=scene,
                    image_path=str(image_path),
                    directed_prompt=directed_prompt,
                    image_style=image_style,
                    style_label=style_label,
                    quality_preset_key=quality_preset_key,
                    scene_seed=seed,
                    visual_bible=visual_bible,
                    attempt=int(attempt_id.split("_")[-1]),
                    reference_image_path=(
                        str(base_image_path) if base_image_path else None
                    ),
                )
            else:
                image_job, image_record, image_metric = _run_fal_flux_image_attempt(
                    scene=scene,
                    image_path=str(image_path),
                    directed_prompt=directed_prompt,
                    image_style=image_style,
                    style_label=style_label,
                    quality_preset_key=quality_preset_key,
                    quality_preset=quality_preset,
                    scene_seed=seed,
                    visual_bible=visual_bible,
                    attempt=int(attempt_id.split("_")[-1]),
                    reference_image_path=(
                        str(base_image_path) if base_image_path else None
                    ),
                )
            if not image_record or not image_metric:
                raise RuntimeError(
                    f"selective_image_retry_failed:{image_job.get('error') if image_job else 'unknown'}"
                )
        elif not image_path or not image_path.exists():
            raise RuntimeError("active_image_missing_for_video_retry")

        video_path: Path | None = None
        video_job: dict[str, Any] = {}
        temporal_identity: dict[str, Any] = {}
        if scope == "video":
            video_provider = _video_generation_provider()
            source_gate = _attempt_automatic_gate(summary, scene_id, active_attempt)
            if (
                previous_approved_attempt_id != previous_active_attempt_id
                or not source_gate["passed"]
            ):
                raise RuntimeError("video_retry_requires_approved_still")
            duration = max(
                3.0,
                _scene_audio_duration(summary.get("audio_files", []), scene_id),
                float(scene.get("duration") or 5),
            )
            video_path = (
                curation_dir / f"scene_{scene_id}_{attempt_id}_{video_provider}.mp4"
            )
            video_source = {
                **scene,
                "scene_id": scene_id,
                "image_path": str(image_path),
                "prompt": active_attempt.get("prompt") or scene.get("prompt") or "",
                "base_prompt": active_attempt.get("base_prompt")
                or scene.get("prompt")
                or "",
                "camera_motion": scene.get("camera_motion", ""),
            }
            audio_path = _run_path(run, active_attempt.get("audio_path"))
            if not audio_path:
                audio_path = _run_path(
                    run,
                    next(
                        (
                            item.get("audio_path")
                            for item in summary.get("audio_files", [])
                            if str(item.get("scene_id")) == scene_id
                        ),
                        "",
                    ),
                )
            video_job, video_ok = _generate_real_video_clip(
                video_source,
                str(video_path),
                duration,
                audio_path=str(audio_path) if audio_path else None,
                visual_bible=visual_bible,
            )
            if not video_ok:
                raise RuntimeError(
                    f"selective_video_retry_failed:{video_job.get('error')}"
                )
            temporal_identity = _evaluate_temporal_identity(
                clip_path=video_path,
                scene_id=scene_id,
                summary=summary,
                output_dir=curation_dir / f"scene_{scene_id}_{attempt_id}_temporal",
            )
            if temporal_identity.get("accepted") is not True:
                raise RuntimeError("selective_video_temporal_identity_failed")

        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = run.get("summary", {})
            scene_review = (
                summary.setdefault("curation", {})
                .setdefault("scenes", {})
                .setdefault(scene_id, {})
            )
            attempts = scene_review.setdefault("attempts", [])
            if previous_active_attempt_id:
                for attempt in attempts:
                    if attempt.get("id") == previous_active_attempt_id:
                        attempt["status"] = "superseded"
            attempts.append(
                {
                    "id": attempt_id,
                    "status": "active",
                    "created_at": _utc_now_iso(),
                    "image_path": str(image_path),
                    "video_path": str(video_path) if video_path else None,
                    "audio_path": active_attempt.get("audio_path"),
                    "image_provider": (
                        image_record.get("generation_method")
                        if image_record
                        else image_provider
                    ),
                    "controlled_workflow": controlled_workflow,
                    "controlnet_model": (image_job or {}).get("controlnet_model", ""),
                    "control_image": (image_job or {}).get("control_image", ""),
                    "video_provider": (video_provider if video_path else None),
                    "retry_scope": scope,
                    "reason": reason,
                    "note": note,
                    "image_quality_score": (image_metric or {}).get("quality_score", 0),
                    "image_semantic_score": (image_metric or {}).get("semantic_score"),
                    "image_semantic_accepted": (image_metric or {}).get(
                        "semantic_accepted"
                    ),
                    "hero_objects": (image_metric or {}).get("hero_objects", []),
                    "hero_object_legibility": (image_metric or {}).get(
                        "hero_object_legibility"
                    ),
                    "hero_object_notes": (image_metric or {}).get(
                        "hero_object_notes", ""
                    ),
                    "control_workflow_required": (image_metric or {}).get(
                        "control_workflow_required", False
                    ),
                    "recommended_generation_strategy": (image_metric or {}).get(
                        "recommended_generation_strategy", "txt2img_retry"
                    ),
                    "operator_next_action": (image_metric or {}).get(
                        "operator_next_action", ""
                    ),
                    "video_quality_score": video_job.get("quality_score", 0),
                    "image_job": image_metric or source_image_metric,
                    "image_provider_job": image_job,
                    "video_job": video_job,
                    "temporal_identity": temporal_identity,
                }
            )
            scene_review.update(
                {
                    "status": "pending_review",
                    "retry_status": "succeeded",
                    "active_attempt_id": attempt_id,
                    "approved_attempt_id": None,
                    "updated_at": _utc_now_iso(),
                }
            )
            if image_record:
                image_quality_patch = _attempt_image_quality_patch(attempts[-1])
                summary["scene_images"] = [
                    (
                        {
                            **item,
                            "image_path": str(image_path),
                            "generation_method": image_record.get(
                                "generation_method", image_provider
                            ),
                            "controlled_workflow": image_record.get(
                                "controlled_workflow", False
                            ),
                            "controlnet_model": image_record.get(
                                "controlnet_model", ""
                            ),
                            "control_image": image_record.get("control_image", ""),
                        }
                        if str(item.get("scene_id")) == scene_id
                        else item
                    )
                    for item in summary.get("scene_images", [])
                ]
                quality_metrics = summary.setdefault("quality_metrics", {})
                quality_metrics["images"] = _replace_scene_record(
                    quality_metrics.get("images", []),
                    scene_id,
                    {
                        "path": str(image_path),
                        "generation_method": image_record.get(
                            "generation_method", image_provider
                        ),
                        **image_quality_patch,
                    },
                )
            if video_path:
                summary["scene_videos"] = _replace_scene_record(
                    summary.get("scene_videos", []),
                    scene_id,
                    {
                        "video_path": str(video_path),
                        "provider": video_provider,
                        "job_id": video_job.get("job_id"),
                        "duration": duration,
                        "quality_score": video_job.get("quality_score", 0),
                        "temporal_identity": temporal_identity,
                    },
                )
            elif image_record:
                summary["scene_videos"] = [
                    item
                    for item in summary.get("scene_videos", [])
                    if str(item.get("scene_id")) != scene_id
                ]
            jobs = summary.setdefault("runpod_jobs", [])
            if image_job:
                jobs.append(image_job)
            if video_job:
                jobs.append(video_job)
            final_review = summary.setdefault("curation", {}).setdefault(
                "final_review", {}
            )
            final_review.update(
                {
                    "status": "draft",
                    "video_viewed": False,
                    "approved_at": None,
                    "note": "",
                }
            )
            publication = summary.setdefault("publication", {})
            publication.update({"status": "stale_after_retry"})
            run["summary"] = summary

        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = _apply_curation_summary(
                run.get("summary", {}), Path(run["run_dir"])
            )
            run["summary"] = summary
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        _append_log(
            run_id,
            f"retry seletivo concluído: cena {scene_id}, tentativa {attempt_id}; nova aprovação obrigatória",
        )
    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            run["summary"] = previous_summary
            scene_review = (
                run["summary"]
                .setdefault("curation", {})
                .setdefault("scenes", {})
                .setdefault(scene_id, {})
            )
            attempts = scene_review.setdefault("attempts", [])
            attempts.append(
                {
                    "id": attempt_id,
                    "status": "failed",
                    "created_at": _utc_now_iso(),
                    "retry_scope": scope,
                    "reason": reason,
                    "note": note,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            scene_review["retry_status"] = "failed"
            scene_review["status"] = "retry_requested"
            run["summary"] = _apply_curation_summary(
                run["summary"], Path(run["run_dir"])
            )
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        _append_log(
            run_id,
            f"retry seletivo falhou: cena {scene_id}: {type(exc).__name__}: {exc}",
        )


def _scene_dialogue_text(summary: dict[str, Any], scene_id: str) -> str:
    from open3d_implementation.core.dialogue_contract import dialogue_turns

    scene = _summary_scene(summary, scene_id)
    return " ".join(
        str(turn.get("text_pt_br") or "").strip()
        for turn in dialogue_turns(scene)
        if str(turn.get("text_pt_br") or "").strip()
    )


def _inherited_audio_retry_attempt(
    attempts: list[dict[str, Any]],
    previous_active: dict[str, Any],
) -> dict[str, Any]:
    visual_attempt = next(
        (
            attempt
            for attempt in reversed(attempts)
            if attempt.get("image_job") and attempt.get("image_path")
        ),
        previous_active,
    )
    return {
        **copy.deepcopy(visual_attempt),
        **copy.deepcopy(previous_active),
    }


def _run_selective_audio_retry(
    run_id: str,
    scene_id: str,
    note: str,
    reason: str,
    scope: str,
) -> None:
    from open3d_implementation.core.dialogue_contract import enrich_scene_performance
    from open3d_implementation.core.langgraph_adapter import (
        _elevenlabs_remaining_characters,
        _generate_scene_dialogue_audio,
    )

    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return
        summary = run.get("summary", {})
        previous_summary = json.loads(json.dumps(summary))
        scene_review = (
            summary.setdefault("curation", {})
            .setdefault("scenes", {})
            .setdefault(scene_id, {"status": "pending_review", "attempts": []})
        )
        previous_active = _active_attempt(summary, scene_id)
        attempt_id = _next_attempt_id(summary, scene_id)
        scene_review.update(
            {
                "status": "retry_requested",
                "retry_status": "running",
                "retry_scope": scope,
                "note": note,
                "reason": reason,
                "updated_at": _utc_now_iso(),
            }
        )
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)

    _append_log(run_id, f"retry ElevenLabs iniciado: cena {scene_id}")

    try:
        api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("elevenlabs_api_key_missing")
        scene = enrich_scene_performance(_summary_scene(summary, scene_id))

        run_dir = Path(run["run_dir"])
        curation_dir = run_dir / "output" / "curation"
        curation_dir.mkdir(parents=True, exist_ok=True)
        summary = run.get("summary", {})
        dialogue_text = _scene_dialogue_text(summary, scene_id)
        if not dialogue_text:
            raise RuntimeError("scene_dialogue_text_missing")
        remaining = _elevenlabs_remaining_characters(api_key)
        if remaining is not None and len(dialogue_text) > remaining:
            raise RuntimeError(
                f"elevenlabs_insufficient_characters:needed={len(dialogue_text)},remaining={remaining}"
            )
        (
            audio_record,
            media_quality,
            scene_voice_metrics,
            estimated_cost,
            _remaining,
        ) = _generate_scene_dialogue_audio(
            scene,
            api_key,
            remaining,
            output_dir=curation_dir,
            file_prefix=f"scene_{scene_id}_{attempt_id}",
        )
        audio_path = Path(str(audio_record["audio_path"]))
        dialogue_turn_records = audio_record.get("dialogue_turns", [])
        model_id = str(
            scene_voice_metrics[0].get("model_id") if scene_voice_metrics else ""
        )
        voice_roles = [
            str(item.get("voice_role") or item.get("speaker_id") or "")
            for item in dialogue_turn_records
        ]
        voice_ids = [str(item.get("voice_id") or "") for item in dialogue_turn_records]
        voice_direction = {
            "tone": scene.get("dominant_emotion"),
            "delivery": "diálogo de personagens em português brasileiro",
        }
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = run.get("summary", {})
            scene_review = (
                summary.setdefault("curation", {})
                .setdefault("scenes", {})
                .setdefault(scene_id, {})
            )
            attempts = scene_review.setdefault("attempts", [])
            active_id = scene_review.get("active_attempt_id")
            for attempt in attempts:
                if attempt.get("id") == active_id:
                    attempt["status"] = "superseded"
            inherited_attempt = _inherited_audio_retry_attempt(
                attempts,
                previous_active,
            )
            attempts.append(
                {
                    **inherited_attempt,
                    "id": attempt_id,
                    "status": "active",
                    "created_at": _utc_now_iso(),
                    "image_path": previous_active.get("image_path"),
                    "video_path": previous_active.get("video_path"),
                    "audio_path": str(audio_path),
                    "audio_text": dialogue_text,
                    "dialogue_turns": dialogue_turn_records,
                    "voice_direction": voice_direction,
                    "image_provider": previous_active.get("image_provider"),
                    "video_provider": previous_active.get("video_provider"),
                    "audio_provider": "elevenlabs",
                    "voice_ids": voice_ids,
                    "voice_roles": voice_roles,
                    "voice_role": "multiple_characters",
                    "model_id": model_id,
                    "retry_scope": scope,
                    "reason": reason,
                    "note": note,
                    "image_quality_score": previous_active.get(
                        "image_quality_score",
                        0,
                    ),
                    "image_semantic_score": previous_active.get("image_semantic_score"),
                    "image_semantic_accepted": previous_active.get(
                        "image_semantic_accepted"
                    ),
                    "video_quality_score": previous_active.get(
                        "video_quality_score",
                        0,
                    ),
                    "audio_quality_score": media_quality.get("quality_score", 0),
                    "audio_job": {
                        "provider": "elevenlabs",
                        "model": model_id,
                        "voice_ids": voice_ids,
                        "voice_roles": voice_roles,
                        "dialogue_turns": dialogue_turn_records,
                        "status": "succeeded",
                        "estimated_cost_usd": round(estimated_cost, 6),
                        "text_characters": len(dialogue_text),
                        "voice_direction": voice_direction,
                        "premium_audio": media_quality.get("premium_audio", False),
                        "issues": media_quality.get("issues", []),
                        "enhanced": media_quality.get("enhanced"),
                        "ambient": media_quality.get("ambient"),
                        "loudness": media_quality.get("loudness"),
                        "waveform": media_quality.get("waveform", []),
                    },
                }
            )
            scene_review.update(
                {
                    "status": "pending_review",
                    "retry_status": "succeeded",
                    "active_attempt_id": attempt_id,
                    "approved_attempt_id": None,
                    "updated_at": _utc_now_iso(),
                }
            )
            summary["audio_files"] = _replace_scene_record(
                summary.get("audio_files", []),
                scene_id,
                {
                    "audio_path": str(audio_path),
                    "text": dialogue_text,
                    "dialogue_turns": dialogue_turn_records,
                    "voice_direction": voice_direction,
                    "voice_ids": voice_ids,
                    "voice_roles": voice_roles,
                    "generation_method": "elevenlabs_dialogue",
                    "language": "pt-BR",
                    "narration_absent": True,
                },
            )
            quality_metrics = summary.setdefault("quality_metrics", {})
            quality_metrics["audio"] = _replace_scene_record(
                quality_metrics.get("audio", []),
                scene_id,
                {
                    "generation_method": "elevenlabs_dialogue",
                    "voice_direction": voice_direction,
                    **media_quality,
                },
            )
            quality_metrics["voices"] = _replace_scene_record(
                quality_metrics.get("voices", []),
                scene_id,
                {
                    "voice_ids": voice_ids,
                    "voice_roles": voice_roles,
                    "dialogue_turns": dialogue_turn_records,
                    "model_id": model_id,
                    "text_characters": len(dialogue_text),
                    "voice_direction": voice_direction,
                    "premium_audio": media_quality.get("premium_audio", False),
                    "quality_score": media_quality.get("quality_score", 0),
                    "issues": media_quality.get("issues", []),
                    "retry_note": note,
                },
            )
            cost_estimate = summary.setdefault("cost_estimate", {})
            cost_estimate["elevenlabs_usd"] = round(
                float(cost_estimate.get("elevenlabs_usd") or 0) + estimated_cost,
                6,
            )
            cost_estimate["total_usd"] = round(
                float(cost_estimate.get("total_usd") or 0) + estimated_cost,
                6,
            )
            _reset_final_gate(summary, "stale_after_audio_retry")
            _archive_legacy_final_video(summary, run_dir)
            run["summary"] = summary

        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            run["summary"] = _apply_curation_summary(
                run.get("summary", {}), Path(run["run_dir"])
            )
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        _append_log(
            run_id,
            f"retry ElevenLabs concluído: cena {scene_id}, tentativa {attempt_id}, "
            f"áudio score {media_quality.get('quality_score')}; "
            "corte final aguarda aprovação humana",
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        requests.RequestException,
        subprocess.SubprocessError,
    ) as exc:
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            run["summary"] = previous_summary
            scene_review = (
                run["summary"]
                .setdefault("curation", {})
                .setdefault("scenes", {})
                .setdefault(scene_id, {})
            )
            attempts = scene_review.setdefault("attempts", [])
            attempts.append(
                {
                    "id": attempt_id,
                    "status": "failed",
                    "created_at": _utc_now_iso(),
                    "retry_scope": scope,
                    "reason": reason,
                    "note": note,
                    "audio_provider": "elevenlabs",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            scene_review["retry_status"] = "failed"
            scene_review["status"] = "retry_requested"
            run["summary"] = _apply_curation_summary(
                run["summary"], Path(run["run_dir"])
            )
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        _append_log(
            run_id,
            f"retry ElevenLabs falhou: cena {scene_id}: {type(exc).__name__}: {exc}",
        )


def _first_existing_path(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _youtube_token_path() -> Path:
    configured = os.getenv("YOUTUBE_TOKEN_FILE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (REPO_ROOT.parent / "token.json").resolve()


def _youtube_client_secrets_path() -> Path | None:
    configured = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "").strip()
    if configured:
        path = Path(configured).expanduser().resolve()
        return path if path.exists() else None
    return _first_existing_path(
        [
            OPEN3D_ROOT / "GOOGLE_APPLICATION_CREDENTIALS_OAUTH.json",
            REPO_ROOT / "script" / "client_secrets.json",
            REPO_ROOT.parent / "client_secrets.json",
            REPO_ROOT.parent.parent / "client_secrets.json",
        ]
    )


def _youtube_auth_status() -> dict[str, Any]:
    token_path = _youtube_token_path()
    client_secrets_path = _youtube_client_secrets_path()
    status = {
        "token_exists": token_path.exists(),
        "client_secrets_exists": bool(
            client_secrets_path and client_secrets_path.exists()
        ),
        "token_valid": False,
        "token_expired": False,
        "has_refresh_token": False,
    }
    if token_path.exists():
        try:
            from google.oauth2.credentials import Credentials

            credentials = Credentials.from_authorized_user_file(
                str(token_path),
                ["https://www.googleapis.com/auth/youtube.upload"],
            )
            status.update(
                {
                    "token_valid": bool(credentials.valid),
                    "token_expired": bool(credentials.expired),
                    "has_refresh_token": bool(credentials.refresh_token),
                }
            )
        except ImportError:
            status["google_auth_dependency_missing"] = True
        except (OSError, ValueError):
            status["token_invalid"] = True
    return status


def _build_youtube_service() -> Any:
    try:
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("youtube_google_client_missing") from exc

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    token_path = _youtube_token_path()
    client_secrets_path = _youtube_client_secrets_path()
    credentials = None

    if token_path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
        except (OSError, ValueError) as exc:
            raise RuntimeError("youtube_token_invalid") from exc

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(GoogleAuthRequest())
        except RefreshError as exc:
            if os.getenv("YOUTUBE_ALLOW_OAUTH_FLOW", "false").lower() != "true":
                raise RuntimeError("youtube_token_refresh_failed") from exc
            credentials = None
        else:
            token_path.write_text(credentials.to_json(), encoding="utf-8")

    if not credentials or not credentials.valid:
        if not client_secrets_path:
            raise RuntimeError("youtube_client_secrets_missing")
        if os.getenv("YOUTUBE_ALLOW_OAUTH_FLOW", "false").lower() != "true":
            raise RuntimeError("youtube_oauth_required")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path),
                scopes,
            )
            credentials = flow.run_local_server(port=0)
        except (OSError, ValueError) as exc:
            raise RuntimeError("youtube_oauth_flow_failed") from exc
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")

    try:
        return build("youtube", "v3", credentials=credentials)
    except (OSError, ValueError) as exc:
        raise RuntimeError("youtube_service_build_failed") from exc


def _youtube_metadata(run: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(run["run_dir"])
    story_path = run_dir / "historia.txt"
    story_text = story_path.read_text(encoding="utf-8") if story_path.exists() else ""
    first_line = next(
        (line.strip() for line in story_text.splitlines() if line.strip()),
        "AI Film",
    )
    title = os.getenv("YOUTUBE_UPLOAD_TITLE", first_line[:95]).strip() or "AI Film"
    description = os.getenv("YOUTUBE_UPLOAD_DESCRIPTION", "").strip()
    if not description:
        description = (
            f"{first_line}\n\n"
            "Vídeo criado com o pipeline AI Film: cenas, imagens, vozes e animação geradas com IA."
        )
    tags_raw = os.getenv(
        "YOUTUBE_UPLOAD_TAGS",
        "AI Film,animação,filme com IA,história animada",
    )
    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
    privacy = os.getenv("YOUTUBE_UPLOAD_PRIVACY", "private").strip().lower()
    if privacy not in YOUTUBE_PRIVACY_STATUSES:
        privacy = "private"
    return {
        "title": title[:100],
        "description": description[:5000],
        "tags": tags[:30],
        "categoryId": os.getenv("YOUTUBE_UPLOAD_CATEGORY_ID", "1"),
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": os.getenv(
            "YOUTUBE_SELF_DECLARED_MADE_FOR_KIDS",
            "false",
        ).lower()
        == "true",
    }


def _upload_video_to_youtube(
    video_path: Path, metadata: dict[str, Any]
) -> dict[str, Any]:
    try:
        import httplib2
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError("youtube_google_client_missing") from exc

    service = _build_youtube_service()
    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": metadata["categoryId"],
        },
        "status": {
            "privacyStatus": metadata["privacyStatus"],
            "selfDeclaredMadeForKids": metadata["selfDeclaredMadeForKids"],
        },
    }
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )
    request_upload = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )
    response = None
    retries = 0
    while response is None:
        try:
            _, response = request_upload.next_chunk()
        except HttpError as exc:
            if exc.resp.status not in {500, 502, 503, 504} or retries >= 5:
                raise RuntimeError(f"youtube_upload_http_{exc.resp.status}") from exc
            retries += 1
            threading.Event().wait(2**retries)
        except (httplib2.HttpLib2Error, OSError) as exc:
            if retries >= 5:
                raise RuntimeError("youtube_upload_network_failed") from exc
            retries += 1
            threading.Event().wait(2**retries)
    video_id = str(response.get("id", ""))
    if not video_id:
        raise RuntimeError("youtube_upload_missing_video_id")
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "privacyStatus": metadata["privacyStatus"],
    }


def _run_youtube_upload(run_id: str) -> None:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return
        summary = run.get("summary", {})
        video_path = Path(summary.get("video_path") or "")
        if not video_path.is_absolute():
            video_path = Path(run["run_dir"]) / video_path
        metadata = _youtube_metadata(run)
        summary.setdefault("publication", {}).update(
            {
                "status": "uploading",
                "started_at": _utc_now_iso(),
                "error": None,
                "failed_at": None,
                "metadata": metadata,
            }
        )
        run["summary"] = summary
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)
    _append_log(run_id, "upload real para YouTube iniciado")

    try:
        if not video_path.exists() or not video_path.is_file():
            raise FileNotFoundError(str(video_path))
        result = _upload_video_to_youtube(video_path, metadata)
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = run.get("summary", {})
            artifact = _video_artifact_signature(Path(run["run_dir"]), summary)
            summary.setdefault("publication", {}).update(
                {
                    "status": "published",
                    "completed_at": _utc_now_iso(),
                    "error": None,
                    "failed_at": None,
                    "artifact": artifact,
                    **result,
                }
            )
            summary = _apply_curation_summary(summary, Path(run["run_dir"]))
            run["summary"] = summary
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        _append_log(run_id, f"YouTube publicado: {result['url']}")
    except (
        FileNotFoundError,
        RuntimeError,
        OSError,
        ValueError,
    ) as exc:
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = run.get("summary", {})
            summary.setdefault("publication", {}).update(
                {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "failed_at": _utc_now_iso(),
                }
            )
            run["summary"] = summary
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        _append_log(run_id, f"falha no upload YouTube: {type(exc).__name__}: {exc}")


def _validated_retry_run_id(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("invalid_retry_run_id")
    run_dir = (RUNS_ROOT / value).resolve()
    if run_dir.parent != RUNS_ROOT or not run_dir.is_dir():
        raise ValueError("retry_run_not_found")
    return value


def _probe_runpod_endpoint(
    label: str,
    endpoint_id: str,
    api_key: str,
) -> dict[str, Any]:
    try:
        response = requests.get(
            f"https://api.runpod.ai/v2/{endpoint_id}/health",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=8,
        )
    except requests.RequestException as exc:
        return {
            "endpoint": label,
            "status": "inconclusive",
            "blocking": False,
            "code": "health_unreachable",
            "message": f"RunPod {label}: health inconclusivo ({type(exc).__name__})",
        }

    if response.status_code == 402:
        return {
            "endpoint": label,
            "status": "blocked",
            "blocking": True,
            "http_status": 402,
            "code": "payment_required",
            "message": (
                f"RunPod {label} sem saldo; adicione créditos e use Retry para "
                "retomar as referências já geradas"
            ),
        }
    if response.status_code in {401, 403}:
        return {
            "endpoint": label,
            "status": "blocked",
            "blocking": True,
            "http_status": response.status_code,
            "code": "authorization_failed",
            "message": f"RunPod {label}: credencial sem autorização",
        }
    if response.status_code >= 500:
        return {
            "endpoint": label,
            "status": "inconclusive",
            "blocking": False,
            "http_status": response.status_code,
            "code": "provider_unavailable",
            "message": f"RunPod {label}: health temporariamente indisponível",
        }
    if not 200 <= response.status_code < 300:
        return {
            "endpoint": label,
            "status": "blocked",
            "blocking": True,
            "http_status": response.status_code,
            "code": "endpoint_unavailable",
            "message": (
                f"RunPod {label}: endpoint indisponível "
                f"(HTTP {response.status_code})"
            ),
        }
    return {
        "endpoint": label,
        "status": "ready",
        "blocking": False,
        "http_status": response.status_code,
        "code": "ready",
        "message": f"RunPod {label}: disponível",
    }


def _runpod_preflight() -> dict[str, Any]:
    if os.getenv("IMAGE_GENERATION_PROVIDER", "comfyui").strip() != "comfyui":
        return {"status": "skipped", "blockers": [], "warnings": [], "probes": []}

    api_key = os.getenv("RUNPOD_API_KEY", "").strip()
    endpoint_pairs = [
        ("principal", os.getenv("RUNPOD_ENDPOINT_ID", "").strip()),
        ("Qwen Cast Bible", os.getenv("COMFYUI_QWEN_EDIT_ENDPOINT_ID", "").strip()),
    ]
    endpoints = [(label, endpoint) for label, endpoint in endpoint_pairs if endpoint]
    if not api_key or not endpoints:
        blocker = {
            "endpoint": "configuração",
            "status": "blocked",
            "blocking": True,
            "code": "runpod_not_configured",
            "message": "RunPod não configurado para o provider ComfyUI",
        }
        return {
            "status": "blocked",
            "http_status": 424,
            "blockers": [blocker],
            "warnings": [],
            "probes": [blocker],
        }

    with ThreadPoolExecutor(max_workers=min(2, len(endpoints))) as executor:
        futures = [
            executor.submit(_probe_runpod_endpoint, label, endpoint, api_key)
            for label, endpoint in endpoints
        ]
        probes = [future.result() for future in futures]

    blockers = [probe for probe in probes if probe.get("blocking") is True]
    warnings = [probe for probe in probes if probe.get("status") == "inconclusive"]
    cost_admission: dict[str, object] = {
        "status": "skipped",
        "blockers": [],
        "warnings": [],
    }
    if not blockers and runpod_cost_guard_enabled():
        try:
            cost_admission = inspect_runpod_cost_admission(
                api_key=api_key,
                endpoint_ids=[endpoint for _label, endpoint in endpoints],
            )
        except RunPodCostGuardError as exc:
            cost_admission = {
                "status": "blocked",
                "blockers": [
                    {
                        "code": "runpod_cost_guard_unavailable",
                        "message": (
                            "Não foi possível validar saldo e concorrência do RunPod"
                        ),
                        "blocking": True,
                        "reason": str(exc),
                    }
                ],
                "warnings": [],
            }
        blockers.extend(list(cost_admission.get("blockers") or []))
        warnings.extend(list(cost_admission.get("warnings") or []))
    status = "blocked" if blockers else "warning" if warnings else "ready"
    http_status = (
        402
        if any(blocker.get("code") == "payment_required" for blocker in blockers)
        else 424
    )
    return {
        "status": status,
        "http_status": http_status,
        "blockers": blockers,
        "warnings": warnings,
        "probes": probes,
        "cost_admission": cost_admission,
    }


def _cast_reference_resume_manifest_assets(
    validated_retry_of: str,
    source_output: Path,
) -> list[tuple[Path, str, str]]:
    manifest_path = source_output.parent / CAST_REFERENCE_RESUME_MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError,
    ):
        return []
    assets = manifest.get("assets", []) if isinstance(manifest, dict) else []
    if (
        manifest.get("schema_version") != CAST_REFERENCE_RESUME_SCHEMA_VERSION
        or manifest.get("source_run_id") != validated_retry_of
        or not isinstance(assets, list)
        or not 0 < len(assets) <= 128
    ):
        return []
    parsed_assets: list[tuple[Path, str, str]] = []
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("validated") is not True:
            return []
        source_name = str(asset.get("source_name") or "")
        destination_name = str(asset.get("destination_name") or "")
        checksum = str(asset.get("sha256") or "").lower()
        if (
            not CAST_REFERENCE_RESUME_SOURCE_PATTERN.fullmatch(source_name)
            or not CAST_REFERENCE_RESUME_DESTINATION_PATTERN.fullmatch(destination_name)
            or not re.fullmatch(r"[0-9a-f]{64}", checksum)
        ):
            return []
        parsed_assets.append((source_output / source_name, destination_name, checksum))
    return parsed_assets


def _validated_cast_reference_resume_assets(
    validated_retry_of: str,
    source_output: Path,
) -> list[tuple[Path, str, bool]]:
    source_summary: dict[str, Any] = {}
    summary_path = source_output.parent / "pipeline_summary.json"
    if summary_path.is_file():
        try:
            loaded_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(loaded_summary, dict):
                source_summary = loaded_summary
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            source_summary = {}
    cast_bible = source_summary.get("visual_bible", {}).get("cast_bible", {})
    characters = (
        cast_bible.get("characters", []) if isinstance(cast_bible, dict) else []
    )
    human_rejected_ids = {
        str(character.get("id") or "")
        for character in characters
        if isinstance(character, dict)
        and (
            (character.get("reference") or {}).get("status") == "rejected_by_human"
            or (
                bool((character.get("reference") or {}).get("human_reviewed_at"))
                and (character.get("reference") or {}).get("human_approved") is False
            )
        )
    }
    rejected_draft_ids = {
        str(character.get("id") or "")
        for character in characters
        if isinstance(character, dict)
        and (
            str((character.get("reference") or {}).get("status") or "")
            in {"rejected", "rejected_by_human", "blocked"}
            or (
                ((character.get("reference") or {}).get("views") or {})
                .get("front", {})
                .get("automatic_approved")
                is False
            )
        )
    }
    manifest_path = source_output.parent / CAST_REFERENCE_RESUME_MANIFEST
    manifest_assets = (
        _cast_reference_resume_manifest_assets(
            validated_retry_of,
            source_output,
        )
        if manifest_path.is_file()
        else []
    )
    resume_by_destination: dict[str, tuple[Path, str, str, bool]] = {}
    if manifest_path.is_file():
        if not manifest_assets:
            return []
        for manifest_asset in manifest_assets:
            if any(
                manifest_asset[1].startswith(f"{character_id}_character_reference_")
                for character_id in human_rejected_ids
            ):
                continue
            resume_by_destination[manifest_asset[1]] = (*manifest_asset, True)
    else:
        if isinstance(characters, list):
            for character in characters[:64]:
                if not isinstance(character, dict):
                    continue
                character_id = str(character.get("id") or "")
                if character_id in human_rejected_ids:
                    continue
                views = (character.get("reference") or {}).get("views", {})
                if not isinstance(views, dict):
                    continue
                for view_id, view in list(views.items())[:16]:
                    if not isinstance(view, dict):
                        continue
                    raw_path = str(view.get("path") or "")
                    checksum = str(view.get("checksum") or "").lower()
                    source_name = Path(raw_path).name
                    destination_name = (
                        f"{character_id}_character_reference_{view_id}.png"
                    )
                    if (
                        view.get("automatic_approved") is True
                        and CAST_REFERENCE_RESUME_SOURCE_PATTERN.fullmatch(source_name)
                        and CAST_REFERENCE_RESUME_DESTINATION_PATTERN.fullmatch(
                            destination_name
                        )
                        and re.fullmatch(r"[0-9a-f]{64}", checksum)
                    ):
                        resume_by_destination[destination_name] = (
                            source_output / source_name,
                            destination_name,
                            checksum,
                            True,
                        )

        trust_path = source_output / CAST_REFERENCE_RESUME_TRUST_FILE
        if trust_path.is_file():
            try:
                trust_payload = json.loads(trust_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                trust_payload = {}
            if (
                isinstance(trust_payload, dict)
                and trust_payload.get("schema_version")
                == CAST_REFERENCE_RESUME_SCHEMA_VERSION
                and isinstance(trust_payload.get("source_run_id"), str)
                and RUN_ID_PATTERN.fullmatch(str(trust_payload.get("source_run_id")))
            ):
                trust_assets = trust_payload.get("assets", [])
                if isinstance(trust_assets, list):
                    for asset in trust_assets[:128]:
                        if not isinstance(asset, dict):
                            continue
                        destination_name = str(asset.get("name") or "")
                        checksum = str(asset.get("sha256") or "").lower()
                        if CAST_REFERENCE_RESUME_DESTINATION_PATTERN.fullmatch(
                            destination_name
                        ) and re.fullmatch(r"[0-9a-f]{64}", checksum):
                            resume_by_destination[destination_name] = (
                                source_output / destination_name,
                                destination_name,
                                checksum,
                                True,
                            )

    manifest_draft_allowlist = {
        destination_name for _source, destination_name, _checksum in manifest_assets
    }
    for character_id in sorted(rejected_draft_ids):
        for view_id in CAST_REFERENCE_VIEW_IDS:
            draft_name = f"{character_id}_character_reference_{view_id}.png"
            if not CAST_REFERENCE_RESUME_DESTINATION_PATTERN.fullmatch(draft_name):
                continue
            if manifest_path.is_file() and draft_name not in manifest_draft_allowlist:
                continue
            draft_source = source_output / draft_name
            if draft_source.is_file():
                resume_by_destination[draft_name] = (
                    draft_source,
                    draft_name,
                    _file_sha256(draft_source),
                    False,
                )

    validated_assets: list[tuple[Path, str, bool]] = []
    for source, destination_name, expected_checksum, trusted in sorted(
        resume_by_destination.values(),
        key=lambda asset: asset[1],
    ):
        resolved_source = source.resolve()
        if resolved_source.parent != source_output:
            continue
        if not resolved_source.is_file():
            continue
        size = resolved_source.stat().st_size
        if size <= 1000 or size > 20 * 1024 * 1024:
            continue
        if _file_sha256(resolved_source) != expected_checksum:
            continue
        validated_assets.append((resolved_source, destination_name, trusted))
    return validated_assets


def _copy_cast_reference_resume_assets(
    retry_of: str | None,
    output_dir: Path,
) -> list[str]:
    validated_retry_of = _validated_retry_run_id(retry_of)
    if validated_retry_of is None:
        return []
    source_output = (RUNS_ROOT / validated_retry_of / "output").resolve()
    if not source_output.is_dir():
        return []

    copied: list[str] = []
    trusted_assets: list[dict[str, str]] = []
    for (
        resolved_source,
        destination_name,
        trusted,
    ) in _validated_cast_reference_resume_assets(validated_retry_of, source_output):
        destination = output_dir / destination_name
        shutil.copy2(resolved_source, destination)
        copied.append(destination_name)
        if trusted:
            trusted_assets.append(
                {
                    "name": destination_name,
                    "sha256": _file_sha256(destination),
                }
            )
    if trusted_assets:
        trust_path = output_dir / CAST_REFERENCE_RESUME_TRUST_FILE
        trust_temp_path = trust_path.with_suffix(".json.tmp")
        trust_temp_path.write_text(
            json.dumps(
                {
                    "schema_version": CAST_REFERENCE_RESUME_SCHEMA_VERSION,
                    "source_run_id": validated_retry_of,
                    "assets": trusted_assets,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        trust_temp_path.replace(trust_path)
    return copied


def _copy_narrative_image_resume_assets(
    retry_of: str | None,
    output_dir: Path,
) -> list[str]:
    validated_retry_of = _validated_retry_run_id(retry_of)
    if validated_retry_of is None:
        return []
    source_output = (RUNS_ROOT / validated_retry_of / "output").resolve()
    if not source_output.is_dir():
        return []

    copied: list[str] = []
    for source in sorted(source_output.iterdir()):
        if not NARRATIVE_IMAGE_RESUME_PATTERN.fullmatch(source.name):
            continue
        resolved_source = source.resolve()
        if resolved_source.parent != source_output or not resolved_source.is_file():
            continue
        size = resolved_source.stat().st_size
        if size <= 1000 or size > 40 * 1024 * 1024:
            continue
        try:
            with Image.open(resolved_source) as image:
                image.verify()
                width, height = image.size
                if (
                    width < 512
                    or height < 512
                    or width * height > MAX_CAST_REFERENCE_UPLOAD_PIXELS
                ):
                    continue
        except (OSError, ValueError, UnidentifiedImageError):
            continue
        destination = output_dir / source.name
        shutil.copy2(resolved_source, destination)
        copied.append(source.name)
    return copied


def _scene_resume_payload_from_lineage(
    retry_of: str | None,
    *,
    story_text: str,
    image_style: str,
    max_scenes: int,
) -> dict[str, Any] | None:
    from open3d_implementation.core.langgraph_adapter import (
        _validate_structured_scenes,
    )

    current_run_id = _validated_retry_run_id(retry_of)
    if current_run_id is None:
        return None
    story_sha256 = hashlib.sha256(story_text.encode("utf-8")).hexdigest()
    visited: list[str] = []
    for _depth in range(24):
        if current_run_id in visited:
            raise ValueError("scene_resume_lineage_cycle")
        visited.append(current_run_id)
        run_dir = (RUNS_ROOT / current_run_id).resolve()
        if run_dir.parent != RUNS_ROOT or not run_dir.is_dir():
            raise ValueError("scene_resume_lineage_run_missing")
        story_path = run_dir / "historia.txt"
        summary_path = run_dir / "pipeline_summary.json"
        if story_path.is_file() and summary_path.is_file():
            try:
                source_story = story_path.read_text(encoding="utf-8")
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("scene_resume_lineage_invalid_summary") from exc
            source_story_sha256 = hashlib.sha256(
                source_story.encode("utf-8")
            ).hexdigest()
            if (
                source_story_sha256 == story_sha256
                and summary.get("image_style") == image_style
            ):
                scenes = _validate_structured_scenes(
                    summary.get("scenes"),
                    max_scenes,
                )
                return {
                    "schema_version": SCENE_RESUME_SCHEMA_VERSION,
                    "source_run_id": str(retry_of),
                    "canonical_run_id": current_run_id,
                    "lineage": visited,
                    "story_sha256": story_sha256,
                    "image_style": image_style,
                    "max_scenes": max_scenes,
                    "scenes": scenes,
                }
        trust_path = run_dir / "output" / CAST_REFERENCE_RESUME_TRUST_FILE
        if not trust_path.is_file():
            return None
        try:
            trust_payload = json.loads(trust_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("scene_resume_lineage_invalid_trust") from exc
        next_run_id = str(trust_payload.get("source_run_id") or "").strip()
        if not RUN_ID_PATTERN.fullmatch(next_run_id):
            raise ValueError("scene_resume_lineage_invalid_source")
        current_run_id = next_run_id
    raise ValueError("scene_resume_lineage_too_deep")


def _copy_scene_resume_manifest(
    retry_of: str | None,
    run_dir: Path,
    *,
    story_text: str,
    image_style: str,
    max_scenes: int,
) -> Path | None:
    payload = _scene_resume_payload_from_lineage(
        retry_of,
        story_text=story_text,
        image_style=image_style,
        max_scenes=max_scenes,
    )
    if payload is None:
        return None
    destination = run_dir / SCENE_RESUME_MANIFEST
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def _can_resume_cast_references_locally(
    retry_of: str | None,
    runpod_preflight: Mapping[str, Any],
) -> bool:
    validated_retry_of = _validated_retry_run_id(retry_of)
    if validated_retry_of is None:
        return False
    blockers = list(runpod_preflight.get("blockers") or [])
    if not blockers or any(
        blocker.get("code") != "payment_required" for blocker in blockers
    ):
        return False
    source_output = (RUNS_ROOT / validated_retry_of / "output").resolve()
    if not source_output.is_dir():
        return False
    return any(
        trusted
        for _source, _destination, trusted in _validated_cast_reference_resume_assets(
            validated_retry_of, source_output
        )
    )


def _start_pipeline_run(
    story_text: str,
    image_style: str,
    image_quality_preset: str,
    retry_of: str | None = None,
    target_scene_id: str | None = None,
    cast_resume_local_only: bool = False,
) -> dict[str, Any]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    run_dir = RUNS_ROOT / run_id
    with RUN_LOCK:
        RUNS[run_id] = {
            "id": run_id,
            "status": "running",
            "run_dir": str(run_dir),
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            "retry_of": retry_of,
            "target_scene_id": target_scene_id,
            "cast_resume_local_only": cast_resume_local_only,
            "image_style": image_style,
            "image_quality_preset": image_quality_preset,
            "log": ["run recebido pela UI"],
            "summary": {},
        }

    thread = threading.Thread(
        target=_run_pipeline,
        args=(
            run_id,
            story_text,
            image_style,
            image_quality_preset,
            retry_of,
            cast_resume_local_only,
        ),
        daemon=True,
    )
    thread.start()
    return RUNS[run_id]


def _hydrate_run_from_summary(summary_path: Path) -> dict[str, Any]:
    run_dir = summary_path.parent
    run_id = run_dir.name
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = _apply_curation_summary(summary, run_dir)
    story_path = run_dir / "historia.txt"
    run = {
        "id": run_id,
        "status": summary.get("status") or "completed",
        "run_dir": str(run_dir),
        "created_at": datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat(),
        "updated_at": _utc_now_iso(),
        "retry_of": None,
        "target_scene_id": None,
        "cast_resume_local_only": bool(summary.get("cast_resume_local_only", False)),
        "image_style": summary.get("image_style", "comic_storybook"),
        "image_quality_preset": summary.get("image_quality_preset", "high"),
        "log": ["run carregado de pipeline_summary.json"],
        "summary": summary,
        "summary_mtime": summary_path.stat().st_mtime,
    }
    if story_path.exists():
        run["story_characters"] = len(story_path.read_text(encoding="utf-8"))
    with RUN_LOCK:
        RUNS[run_id] = run
    return run


def _summary_path_for_run(run_id: str) -> Path:
    return RUNS_ROOT / run_id / "pipeline_summary.json"


def _refresh_completed_run_from_disk(run: dict[str, Any]) -> dict[str, Any]:
    if run.get("status") == "running":
        return run
    summary_path = _summary_path_for_run(str(run.get("id", "")))
    if not summary_path.exists():
        return run
    current_mtime = float(run.get("summary_mtime") or 0)
    if summary_path.stat().st_mtime <= current_mtime:
        return run
    refreshed = _hydrate_run_from_summary(summary_path)
    refreshed_log = [*run.get("log", []), "summary recarregado do disco"]
    refreshed["log"] = refreshed_log[-200:]
    with RUN_LOCK:
        RUNS[refreshed["id"]] = refreshed
    return refreshed


def _run_pipeline(
    run_id: str,
    story_text: str,
    image_style: str,
    image_quality_preset: str,
    retry_of: str | None = None,
    cast_resume_local_only: bool = False,
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
    resumed_cast_assets = _copy_cast_reference_resume_assets(retry_of, output_dir)
    if resumed_cast_assets:
        _append_log(
            run_id,
            f"retomando {len(resumed_cast_assets)} referências da Cast Bible de {retry_of}",
        )
    resumed_scene_assets = _copy_narrative_image_resume_assets(retry_of, output_dir)
    if resumed_scene_assets:
        _append_log(
            run_id,
            f"retomando {len(resumed_scene_assets)} imagens narrativas de {retry_of}",
        )
    max_scenes = max(
        1,
        min(
            24,
            _safe_int_value(os.getenv("AI_FILM_MAX_SCENES", "8"), 8),
        ),
    )
    scene_resume_manifest_path = _copy_scene_resume_manifest(
        retry_of,
        run_dir,
        story_text=story_text,
        image_style=image_style,
        max_scenes=max_scenes,
    )
    if resumed_scene_assets and scene_resume_manifest_path is None:
        raise RuntimeError("scene_resume_manifest_unavailable_for_resumed_images")
    if scene_resume_manifest_path is not None:
        _append_log(
            run_id,
            "retomando contrato canônico de cenas com hash validado",
        )
    if cast_resume_local_only:
        _append_log(
            run_id,
            "retomada local ativada; novas gerações RunPod estão desabilitadas",
        )
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
                        "max_scenes": max_scenes,
                        "image_style": image_style,
                        "image_quality_preset": image_quality_preset,
                        "cast_resume_local_only": cast_resume_local_only,
                        "scene_resume_manifest_path": (
                            str(scene_resume_manifest_path)
                            if scene_resume_manifest_path is not None
                            else ""
                        ),
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
        summary = _apply_curation_summary(summary, run_dir)
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
    except (
        DagsterError,
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as exc:
        _append_log(run_id, f"falha: {type(exc).__name__}: {exc}")
        _set_run(
            run_id, status="failed", error=str(exc), traceback=traceback.format_exc()
        )
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
                "gemini_image_quality": os.getenv(
                    "GEMINI_IMAGE_QUALITY_MODEL", "gemini-3-pro-image"
                ),
                "comfyui_checkpoint": os.getenv(
                    "COMFYUI_DEFAULT_CHECKPOINT",
                    "ai-film-comic-storybook-xl.safetensors",
                ),
                "fal_flux": os.getenv(
                    "FAL_FLUX_MODEL_ID",
                    "fal-ai/flux/schnell",
                ),
                "fal_reference_edit": os.getenv(
                    "FAL_REFERENCE_EDIT_MODEL_ID",
                    "fal-ai/nano-banana/edit",
                ),
                "fal_identity_human": os.getenv(
                    "FAL_FLUX_PULID_MODEL_ID",
                    "fal-ai/flux-pulid",
                ),
                "fal_identity_nonhuman": os.getenv(
                    "FAL_INSTANT_CHARACTER_MODEL_ID",
                    "fal-ai/instant-character",
                ),
                "fal_kling": os.getenv(
                    "FAL_KLING_MODEL_ID",
                    "fal-ai/kling-video/v3/standard/image-to-video",
                ),
                "fal_kling_lipsync": os.getenv(
                    "FAL_KLING_LIPSYNC_MODEL_ID",
                    "fal-ai/kling-video/lipsync/audio-to-video",
                ),
                "openai_fast": os.getenv("OPENAI_FAST_MODEL", "gpt-5.4-nano"),
            },
            "image_provider": os.getenv("IMAGE_GENERATION_PROVIDER", "comfyui"),
            "video_provider": os.getenv("VIDEO_GENERATION_PROVIDER", "runway"),
            "orchestrator": "dagster",
            "image_styles": sorted(ALLOWED_IMAGE_STYLES),
            "image_quality_presets": sorted(ALLOWED_IMAGE_QUALITY_PRESETS),
            "youtube": _youtube_auth_status(),
            "keys": {
                "gemini": bool(
                    os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                ),
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "runpod": bool(
                    os.getenv("RUNPOD_API_KEY") and os.getenv("RUNPOD_ENDPOINT_ID")
                ),
                "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY")),
                "runway": bool(os.getenv("RUNWAY_API_KEY")),
                "fal": bool(os.getenv("FAL_KEY")),
            },
        }
    )


@app.get("/api/sample-story")
def sample_story() -> Response:
    story = STORY_PATH.read_text(encoding="utf-8")
    return jsonify(
        {"path": str(STORY_PATH), "characters": len(story), "story_text": story}
    )


@app.post("/api/youtube/auth")
def youtube_auth() -> Response:
    previous = os.environ.get("YOUTUBE_ALLOW_OAUTH_FLOW")
    os.environ["YOUTUBE_ALLOW_OAUTH_FLOW"] = "true"
    try:
        _build_youtube_service()
    except RuntimeError as exc:
        return jsonify({"status": "failed", "error": str(exc)}), 409
    finally:
        if previous is None:
            os.environ.pop("YOUTUBE_ALLOW_OAUTH_FLOW", None)
        else:
            os.environ["YOUTUBE_ALLOW_OAUTH_FLOW"] = previous
    return jsonify({"status": "authenticated", "youtube": _youtube_auth_status()})


@app.post("/api/runs")
def create_run() -> Response:
    from open3d_implementation.core.langgraph_adapter import (
        _image_generation_provider,
    )

    payload = request.get_json(silent=True) or {}
    story_text = str(payload.get("story_text", "")).strip()
    if not story_text:
        return jsonify({"error": "story_text is required"}), 400
    image_style = str(payload.get("image_style", "comic_storybook")).strip()
    image_quality_preset = str(payload.get("image_quality_preset", "high")).strip()
    if image_style not in ALLOWED_IMAGE_STYLES:
        return jsonify({"error": "invalid image_style"}), 400
    if image_quality_preset not in ALLOWED_IMAGE_QUALITY_PRESETS:
        return jsonify({"error": "invalid image_quality_preset"}), 400
    try:
        retry_of = _validated_retry_run_id(payload.get("retry_of"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    cast_resume_local_only = False
    if _image_generation_provider() == "comfyui":
        runpod_preflight = _runpod_preflight()
        if runpod_preflight["status"] == "blocked":
            cast_resume_local_only = _can_resume_cast_references_locally(
                retry_of,
                runpod_preflight,
            )
            if not cast_resume_local_only:
                blockers = runpod_preflight.get("blockers") or []
                message = str(
                    blockers[0].get("message")
                    if blockers
                    else "RunPod bloqueado antes da execução"
                )
                return (
                    jsonify(
                        {
                            "error": message,
                            "retry_of": retry_of,
                            "runpod_preflight": runpod_preflight,
                        }
                    ),
                    int(runpod_preflight.get("http_status") or 424),
                )

    run = _start_pipeline_run(
        story_text=story_text,
        image_style=image_style,
        image_quality_preset=image_quality_preset,
        retry_of=retry_of,
        cast_resume_local_only=cast_resume_local_only,
    )
    return jsonify(
        {
            "id": run["id"],
            "status": "running",
            "run_dir": run["run_dir"],
            "cast_resume_local_only": cast_resume_local_only,
        }
    )


@app.post("/api/runs/<run_id>/curation")
def set_run_curation(run_id: str) -> Response:
    payload = request.get_json(silent=True) or {}
    scene_id = str(payload.get("scene_id", "")).strip()
    status = str(payload.get("status", "")).strip()
    note = str(payload.get("note", "")).strip()[:2000]
    reason = str(payload.get("reason", "")).strip()
    attempt_id = str(payload.get("attempt_id", "")).strip() or "attempt_1"
    if not scene_id:
        return jsonify({"error": "scene_id is required"}), 400
    if status not in ALLOWED_CURATION_STATUSES:
        return jsonify({"error": "invalid curation status"}), 400
    if status in {"rejected", "retry_requested"} and not (note or reason):
        return jsonify({"error": "reason or note is required"}), 400
    if reason and reason not in CURATION_REASONS:
        return jsonify({"error": "invalid curation reason"}), 400

    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary")
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        curation = summary.setdefault("curation", {})
        scenes = curation.setdefault("scenes", {})
        existing = scenes.get(scene_id, {})
        attempts = existing.get("attempts", [])
        if status == "approved":
            approved_attempt_id = attempt_id
            selected_attempt = next(
                (
                    attempt
                    for attempt in attempts
                    if attempt.get("id") == approved_attempt_id
                ),
                None,
            )
            if selected_attempt is None:
                return jsonify({"error": "attempt not found"}), 400
            automatic_gate = _attempt_automatic_gate(
                summary,
                scene_id,
                selected_attempt,
            )
            selected_attempt["automatic_gate"] = automatic_gate
            if not automatic_gate["passed"]:
                return (
                    jsonify(
                        {
                            "error": "automatic gate blocked",
                            "blockers": automatic_gate["blockers"],
                            "gates": automatic_gate["gates"],
                        }
                    ),
                    409,
                )
            for attempt in attempts:
                if attempt.get("id") != approved_attempt_id:
                    attempt["status"] = "superseded"
                else:
                    attempt["status"] = "approved"
        else:
            approved_attempt_id = existing.get("approved_attempt_id")
        scenes[scene_id] = {
            **existing,
            "status": status,
            "note": note,
            "reason": reason,
            "active_attempt_id": attempt_id,
            "approved_attempt_id": approved_attempt_id,
            "attempts": attempts,
            "updated_at": _utc_now_iso(),
        }
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)
        return jsonify(run)


@app.post("/api/runs/<run_id>/cast-reference-approval")
def set_cast_reference_approval(run_id: str) -> Response:
    from open3d_implementation.core.langgraph_adapter import (
        _set_cast_reference_human_approval,
    )

    payload = request.get_json(silent=True) or {}
    character_id = str(payload.get("character_id") or "").strip()
    approved = payload.get("approved")
    if not character_id:
        return jsonify({"error": "character_id is required"}), 400
    if not isinstance(approved, bool):
        return jsonify({"error": "approved must be boolean"}), 400

    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = copy.deepcopy(run.get("summary") or {})
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        cast_bible = summary.get("visual_bible", {}).get("cast_bible") or {}
        character = next(
            (
                item
                for item in cast_bible.get("characters", [])
                if str(item.get("id")) == character_id
            ),
            None,
        )
        if character is None:
            return jsonify({"error": "cast character not found"}), 404
        try:
            _set_cast_reference_human_approval(
                character,
                approved,
                base_dir=Path(run["run_dir"]),
            )
            _invalidate_assets_for_cast_change(summary)
            stage = _refresh_cast_stage(
                summary,
                base_dir=Path(run["run_dir"]),
            )
            registry_path = _persist_cast_bible_registry(
                summary,
                Path(run["run_dir"]),
            )
            summary = _apply_curation_summary(summary, Path(run["run_dir"]))
        except (OSError, ValueError) as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 409
        run["summary"] = summary
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)
        run.setdefault("log", []).append(
            f"Cast Bible {character_id} {'aprovada' if approved else 'reprovada'}; estágio {stage}; registro {registry_path}"
        )
        return jsonify(run)


@app.post("/api/runs/<run_id>/cast-front-reference")
def upload_cast_front_reference(run_id: str) -> Response:
    from open3d_implementation.core.langgraph_adapter import (
        _begin_cast_reference_revision,
        _build_character_reference_scene,
        _build_image_prompt,
        _character_reference_accepted,
        _combine_image_quality,
        _evaluate_image_semantics,
        _probe_image_quality,
        _reconcile_cast_reference_semantic_false_negatives,
        _update_cast_reference,
    )

    if (
        request.content_length is not None
        and request.content_length > MAX_CAST_REFERENCE_UPLOAD_BYTES + 1024 * 1024
    ):
        return jsonify({"error": "cast_reference_upload_too_large"}), 413
    character_id = str(request.form.get("character_id") or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", character_id):
        return jsonify({"error": "invalid_character_id"}), 400
    uploaded = request.files.get("reference")
    if uploaded is None:
        return jsonify({"error": "reference file is required"}), 400
    raw = uploaded.stream.read(MAX_CAST_REFERENCE_UPLOAD_BYTES + 1)
    try:
        image = _decode_cast_reference_upload(raw)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with RUN_LOCK:
        current_run = RUNS.get(run_id)
        if current_run is None:
            return jsonify({"error": "run not found"}), 404
        if current_run.get("status") == "running":
            return jsonify({"error": "run is still running"}), 409
        summary = copy.deepcopy(current_run.get("summary") or {})
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        run_updated_at = str(current_run.get("updated_at") or "")
        run_dir = Path(current_run["run_dir"]).resolve()

    cast_bible = summary.get("visual_bible", {}).get("cast_bible") or {}
    character = next(
        (
            item
            for item in cast_bible.get("characters", [])
            if str(item.get("id")) == character_id
        ),
        None,
    )
    if character is None:
        return jsonify({"error": "cast character not found"}), 404
    if str(character.get("kind") or "").lower() != "human":
        return jsonify({"error": "manual front upload supports human cast only"}), 409

    output_dir = (run_dir / "output").resolve()
    if output_dir.parent != run_dir:
        return jsonify({"error": "invalid run output directory"}), 409
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = output_dir / (
        f"{character_id}_character_reference_front_upload_candidate.png"
    )
    try:
        image.save(candidate_path, format="PNG", optimize=True)
    except OSError as exc:
        return jsonify({"error": f"cast_reference_upload_save_failed:{exc}"}), 409

    visual_bible = summary["visual_bible"]
    reference_scene = _build_character_reference_scene(
        visual_bible,
        character_id,
        "front",
    )
    style_key = str(
        summary.get("image_style") or visual_bible.get("style_key") or "comic_storybook"
    )
    reference_prompt = _build_image_prompt(
        reference_scene,
        style_key,
        visual_bible,
    )
    technical_metrics = _probe_image_quality(
        str(candidate_path),
        scene=reference_scene,
    )
    semantic_metrics = _evaluate_image_semantics(
        str(candidate_path),
        reference_scene,
        reference_prompt,
        style_key,
        visual_bible,
    )
    image_metric = {
        "scene_id": reference_scene["scene_id"],
        "path": str(candidate_path),
        "generation_method": "human_uploaded_cast_anchor",
        "attempt": 0,
        "style": style_key,
        **_combine_image_quality(technical_metrics, semantic_metrics),
    }
    _reconcile_cast_reference_semantic_false_negatives(
        image_metric=image_metric,
        candidate_path=str(candidate_path),
        view_id="front",
        identity_accepted=True,
        composition_similarity=0.0,
    )
    accepted = _character_reference_accepted(image_metric)
    upload_audit = {
        "character_id": character_id,
        "view_id": "front",
        "accepted": accepted,
        "quality_score": image_metric.get("quality_score"),
        "semantic_score": image_metric.get("semantic_score"),
        "issues": list(image_metric.get("issues", []))[:20],
        "checksum": _file_sha256(candidate_path),
        "uploaded_at": _utc_now_iso(),
    }
    quality_metrics = summary.setdefault("quality_metrics", {})
    upload_history = list(quality_metrics.get("cast_reference_uploads") or [])
    quality_metrics["cast_reference_uploads"] = [*upload_history[-19:], upload_audit]

    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            candidate_path.unlink(missing_ok=True)
            return jsonify({"error": "run not found"}), 404
        if str(run.get("updated_at") or "") != run_updated_at:
            candidate_path.unlink(missing_ok=True)
            return jsonify({"error": "run changed during upload validation"}), 409

        if not accepted:
            reference = character.setdefault("reference", {})
            reference["upload_candidate"] = {
                **upload_audit,
                "path": str(candidate_path),
            }
            run["summary"] = summary
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
            run.setdefault("log", []).append(
                f"Frente canônica {character_id} bloqueada pelo gate automático"
            )
            return (
                jsonify(
                    {
                        "error": "uploaded_cast_reference_failed_quality_gate",
                        "metrics": upload_audit,
                        "run": run,
                    }
                ),
                422,
            )

        canonical_path = output_dir / f"{character_id}_character_reference_front.png"
        backup_path = output_dir / (
            f".{character_id}_character_reference_front_{uuid.uuid4().hex}.bak"
        )
        had_canonical = canonical_path.is_file()
        try:
            if had_canonical:
                shutil.copy2(canonical_path, backup_path)
            candidate_path.replace(canonical_path)
            _begin_cast_reference_revision(character)
            _update_cast_reference(
                character,
                str(canonical_path),
                {**image_metric, "path": str(canonical_path)},
                view_id="front",
                human_approved=True,
            )
            reference = character["reference"]
            reference.pop("upload_candidate", None)
            reference["anchor_source"] = "human_upload"
            reference["anchor_uploaded_at"] = upload_audit["uploaded_at"]
            reference["views"]["front"]["source"] = "human_upload"
            _invalidate_assets_for_cast_change(summary)
            stage = _refresh_cast_stage(summary, base_dir=run_dir)
            summary = _apply_curation_summary(summary, run_dir)
            run["summary"] = summary
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
        except (OSError, ValueError) as exc:
            if backup_path.is_file():
                backup_path.replace(canonical_path)
            elif not had_canonical:
                canonical_path.unlink(missing_ok=True)
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 409
        finally:
            backup_path.unlink(missing_ok=True)
        run.setdefault("log", []).append(
            f"Frente canônica {character_id} aceita; vistas derivadas invalidadas; estágio {stage}"
        )
        return jsonify(run)


@app.post("/api/runs/<run_id>/cast-lora-export")
def export_cast_lora_packs(run_id: str) -> Response:
    from scripts.export_cast_bible_lora_manifest import export_training_packs

    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary") or {}
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        _refresh_cast_stage(
            summary,
            base_dir=Path(run["run_dir"]),
        )
        cast_status = (
            summary.get("visual_bible", {}).get("cast_bible", {}).get("status")
        )
        if cast_status != "approved":
            return jsonify({"error": "cast references are not approved"}), 409
        _persist_summary(run)
        summary_path = Path(run["run_dir"]) / "pipeline_summary.json"
        output_dir = Path(run["run_dir"]) / "output" / "lora_training_packs"
        try:
            packs = export_training_packs(summary_path, output_dir)
        except (OSError, ValueError) as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 409
        export_state = {
            "status": "ready",
            "exported_at": _utc_now_iso(),
            "packs": [str(pack.relative_to(Path(run["run_dir"]))) for pack in packs],
        }
        summary.setdefault("visual_bible", {})["lora_training_export"] = export_state
        run["summary"] = summary
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)
        run.setdefault("log", []).append(
            f"{len(packs)} pacote(s) LoRA exportado(s) com checksum"
        )
        return jsonify({"run": run, **export_state})


@app.post("/api/runs/<run_id>/continue-after-cast")
def continue_after_cast(run_id: str) -> Response:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary") or {}
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        try:
            stage = _refresh_cast_stage(
                summary,
                base_dir=Path(run["run_dir"]),
            )
            if stage != "ready_to_generate_scenes":
                blockers = (
                    summary.get("visual_bible", {})
                    .get("lora_gate", {})
                    .get("blockers", [])
                )
                return (
                    jsonify(
                        {
                            "error": "cast or LoRA gate blocked",
                            "stage": stage,
                            "blockers": blockers,
                        }
                    ),
                    409,
                )
            _persist_cast_bible_registry(summary, Path(run["run_dir"]))
        except (OSError, ValueError) as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 409
        story_path = Path(run["run_dir"]) / "historia.txt"
        if not story_path.is_file():
            return jsonify({"error": "story file not found"}), 409
        story_text = story_path.read_text(encoding="utf-8").strip()
        image_style = str(run.get("image_style") or "comic_storybook")
        quality_preset = str(run.get("image_quality_preset") or "high")

    next_run = _start_pipeline_run(
        story_text=story_text,
        image_style=image_style,
        image_quality_preset=quality_preset,
        retry_of=run_id,
    )
    return jsonify(next_run), 202


@app.post("/api/runs/<run_id>/attempt-active")
def activate_attempt(run_id: str) -> Response:
    payload = request.get_json(silent=True) or {}
    scene_id = str(payload.get("scene_id", "")).strip()
    attempt_id = str(payload.get("attempt_id", "")).strip()
    if not scene_id:
        return jsonify({"error": "scene_id is required"}), 400
    if not attempt_id:
        return jsonify({"error": "attempt_id is required"}), 400
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        if not run.get("summary"):
            return jsonify({"error": "run summary is not ready"}), 409
        try:
            updated = _apply_attempt_to_summary(run, scene_id, attempt_id, False)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500
        return jsonify(updated)


@app.post("/api/runs/<run_id>/attempt-approval")
def approve_attempt(run_id: str) -> Response:
    payload = request.get_json(silent=True) or {}
    scene_id = str(payload.get("scene_id", "")).strip()
    attempt_id = str(payload.get("attempt_id", "")).strip()
    if not scene_id:
        return jsonify({"error": "scene_id is required"}), 400
    if not attempt_id:
        return jsonify({"error": "attempt_id is required"}), 400
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        if not run.get("summary"):
            return jsonify({"error": "run summary is not ready"}), 409
        try:
            updated = _apply_attempt_to_summary(run, scene_id, attempt_id, True)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500
        return jsonify(updated)


@app.post("/api/runs/<run_id>/generate-approved-videos")
def generate_approved_videos(run_id: str) -> Response:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary")
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        summary = _apply_curation_summary(summary, Path(run["run_dir"]))
        _archive_legacy_final_video(summary, Path(run["run_dir"]))
        curation = summary.setdefault("curation", {})
        run["summary"] = summary
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)
        if not curation.get("can_generate_video"):
            return (
                jsonify(
                    {
                        "error": "approved stills gate blocked",
                        "blockers": curation.get("blockers", []),
                    }
                ),
                409,
            )
        curation.setdefault("video_generation", {}).update(
            {
                "status": "queued",
                "started_at": None,
                "completed_at": None,
                "error": None,
            }
        )
        run["summary"] = summary
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)

    thread = threading.Thread(
        target=_run_approved_video_generation,
        args=(run_id,),
        daemon=True,
    )
    thread.start()
    _append_log(run_id, "geração image-to-video aprovada enfileirada")
    return jsonify({"id": run_id, "status": "queued"}), 202


@app.post("/api/runs/<run_id>/final-video-viewed")
def mark_final_video_viewed(run_id: str) -> Response:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary")
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        summary = _apply_curation_summary(summary, Path(run["run_dir"]))
        video_artifact = summary.get("video_artifact", {})
        if summary.get("video_current") is not True:
            return (
                jsonify(
                    {
                        "error": "final video is not current and dialogue-compliant",
                        "issues": video_artifact.get("issues", []),
                        "dialogue_blockers": summary.get("curation", {}).get(
                            "dialogue_blockers", []
                        ),
                    }
                ),
                409,
            )
        final_review = summary.setdefault("curation", {}).setdefault("final_review", {})
        final_review["video_viewed"] = True
        final_review["viewed_at"] = _utc_now_iso()
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)
        return jsonify(run)


@app.post("/api/runs/<run_id>/final-approval")
def approve_final_cut(run_id: str) -> Response:
    payload = request.get_json(silent=True) or {}
    note = str(payload.get("note", "")).strip()[:2000]
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary")
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        summary = _apply_curation_summary(summary, Path(run["run_dir"]))
        curation = summary.setdefault("curation", {})
        if not curation.get("can_final_approve"):
            return (
                jsonify(
                    {
                        "error": "final approval blocked",
                        "blockers": curation.get("blockers", []),
                    }
                ),
                409,
            )
        final_review = curation.setdefault("final_review", {})
        final_review.update(
            {
                "status": "final_approved",
                "approved_at": _utc_now_iso(),
                "note": note,
            }
        )
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)
        return jsonify(run)


@app.post("/api/runs/<run_id>/publish-gate")
def publish_gate(run_id: str) -> Response:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary")
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        summary = _apply_curation_summary(summary, Path(run["run_dir"]))
        curation = summary.get("curation", {})
        publication = summary.setdefault("publication", {})
        production = summary.get("production_status", {})
        run["summary"] = summary
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)
        if not curation.get("can_publish"):
            return jsonify(
                {
                    "blocked": True,
                    "status": curation.get("status"),
                    "blockers": curation.get("blockers", []),
                }
            )
        if publication.get("status") == "uploading":
            return jsonify(
                {
                    "blocked": False,
                    "status": "uploading",
                    "message": "youtube upload already running",
                }
            )
        if production.get("status") == "published_current":
            publication.update({"error": None, "failed_at": None})
            run["summary"] = summary
            run["updated_at"] = _utc_now_iso()
            _persist_summary(run)
            return jsonify(
                {
                    "blocked": False,
                    "status": "published",
                    "url": publication.get("url"),
                    "video_id": publication.get("video_id"),
                }
            )
        publication.update(
            {
                "status": "queued",
                "queued_at": _utc_now_iso(),
                "error": None,
                "failed_at": None,
            }
        )
        run["summary"] = summary
        _persist_summary(run)
    thread = threading.Thread(
        target=_run_youtube_upload,
        args=(run_id,),
        daemon=True,
    )
    thread.start()
    _append_log(run_id, "upload YouTube enfileirado")
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is not None:
            return jsonify(
                {
                    "blocked": False,
                    "status": "queued",
                    "message": "youtube upload queued",
                    "run": run,
                }
            )
        return (
            jsonify(
                {
                    "blocked": True,
                    "status": "run_missing_after_queue",
                    "blockers": ["run not found after queue"],
                }
            ),
            404,
        )


@app.post("/api/runs/<run_id>/retry-scene")
def retry_scene(run_id: str) -> Response:
    payload = request.get_json(silent=True) or {}
    scene_id = str(payload.get("scene_id", "")).strip()
    note = str(payload.get("note", "")).strip()[:2000]
    reason = str(payload.get("reason", "")).strip()
    scope = str(payload.get("scope", "image_video")).strip()
    if not scene_id:
        return jsonify({"error": "scene_id is required"}), 400
    if scope not in RETRY_SCOPES:
        return jsonify({"error": "invalid retry scope"}), 400
    if not (note or reason):
        return jsonify({"error": "reason or note is required"}), 400
    if reason and reason not in CURATION_REASONS:
        return jsonify({"error": "invalid curation reason"}), 400
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary") or {}
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        controlled_blocker = _controlled_retry_blocker(summary, scene_id, scope)
        if controlled_blocker:
            return jsonify(controlled_blocker), 409
        curation = summary.setdefault("curation", {})
        scenes = curation.setdefault("scenes", {})
        existing = scenes.get(scene_id, {})
        scenes[scene_id] = {
            **existing,
            "status": "retry_requested",
            "retry_status": "queued",
            "note": note,
            "reason": reason,
            "retry_scope": scope,
            "updated_at": _utc_now_iso(),
        }
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = _utc_now_iso()
        _persist_summary(run)

    retry_target = (
        _run_selective_audio_retry if scope == "audio" else _run_selective_visual_retry
    )
    thread = threading.Thread(
        target=retry_target,
        args=(run_id, scene_id, note, reason, scope),
        daemon=True,
    )
    thread.start()
    _append_log(run_id, f"retry seletivo enfileirado para cena {scene_id}: {scope}")
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        return jsonify(
            {
                "id": run["id"],
                "status": run["status"],
                "run_dir": run["run_dir"],
                "summary": run.get("summary", {}),
            }
        )


@app.get("/api/runs/latest")
def get_latest_run() -> Response:
    with RUN_LOCK:
        latest_memory_run = (
            max(RUNS.values(), key=lambda item: item.get("updated_at", ""))
            if RUNS
            else None
        )
    if latest_memory_run and latest_memory_run.get("status") == "running":
        return jsonify(latest_memory_run)

    summary_files = sorted(
        RUNS_ROOT.glob("*/pipeline_summary.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if latest_memory_run:
        if not summary_files:
            return jsonify(latest_memory_run)
        latest_summary = summary_files[0]
        if latest_summary.parent.name == latest_memory_run.get("id"):
            try:
                return jsonify(_refresh_completed_run_from_disk(latest_memory_run))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                return jsonify({"error": str(exc)}), 500

    if not summary_files:
        return jsonify({"error": "run not found"}), 404
    try:
        return jsonify(_hydrate_run_from_summary(summary_files[0]))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/api/runs/<run_id>")
def get_run(run_id: str) -> Response:
    with RUN_LOCK:
        run = RUNS.get(run_id)
    if run is None:
        summary_path = _summary_path_for_run(run_id)
        if not summary_path.exists():
            return jsonify({"error": "run not found"}), 404
        try:
            return jsonify(_hydrate_run_from_summary(summary_path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return jsonify({"error": str(exc)}), 500
    try:
        run = _refresh_completed_run_from_disk(run)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 500
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
