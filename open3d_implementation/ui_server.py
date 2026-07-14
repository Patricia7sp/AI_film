#!/usr/bin/env python3
"""Local UI for testing the AI film pipeline.

This server is intentionally local-only. It lets the owner upload a story,
launch the real LangGraph pipeline in the background, retry a failed run, and
inspect generated assets without exposing secrets.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dagster._core.errors import DagsterError
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, request, send_file

REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN3D_ROOT = Path(__file__).resolve().parent
STORY_PATH = REPO_ROOT / "data" / "historia.txt"
RUNS_ROOT = Path(
    os.getenv("AI_FILM_RUNS_ROOT", str(Path(tempfile.gettempdir()) / "ai_film_ui_runs"))
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
    .asset-meta { padding: 0 10px 10px; color: var(--muted); font-size: 12px; }
    .asset-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; padding: 0 10px 10px; }
    .asset-actions button { height: 32px; padding: 0 8px; font-size: 12px; }
    .asset-note { width: calc(100% - 20px); min-height: 56px; margin: 0 10px 10px; font-size: 12px; }
    .badge { display: inline-flex; align-items: center; height: 22px; border: 1px solid var(--line); border-radius: 999px; padding: 0 8px; font-size: 11px; color: var(--muted); }
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
    .review-card { border: 1px solid var(--line); border-radius: 7px; background: #090a0c; overflow: hidden; }
    .review-grid { display: grid; grid-template-columns: 170px 170px 1fr; gap: 12px; padding: 12px; align-items: start; }
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
    @media (max-width: 900px) { main { padding: 18px; } .grid, .status, .assets, .review-grid, .final-gate, .attempt-compare, .compare-tools { grid-template-columns: 1fr; } header { display: block; } }
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
        <div class="metric"><strong id="quality">0</strong><span>qualidade</span></div>
        <div class="metric"><strong id="cost">$0</strong><span>custo est.</span></div>
      </div>
      <div id="curation" class="curation"></div>
      <div id="log" class="log"></div>
      <div id="monitoring"></div>
      <div id="assets" class="assets"></div>
    </section>
  </div>
</main>
<script>
let currentRun = null;
let pollTimer = null;
let comparisonSelections = {};

const $ = (id) => document.getElementById(id);

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
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function refreshHealth() {
  try {
    const data = await api('/api/health');
    const imageModel = data.image_provider === 'comfyui'
      ? data.models.comfyui_checkpoint
      : data.models.gemini_image_quality;
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
  ['image_video', 'Imagem + vídeo'],
  ['image', 'Imagem'],
  ['video', 'Vídeo'],
  ['audio', 'Áudio'],
  ['full_scene', 'Cena completa']
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
  const video = attempt.video_path ? `<video controls src="${mediaUrl(run, attempt.video_path)}"></video>` : '<div class="asset-meta">sem vídeo nesta tentativa</div>';
  const audio = attempt.audio_path ? `<audio controls src="${mediaUrl(run, attempt.audio_path)}"></audio>` : '<div class="asset-meta">sem áudio nesta tentativa</div>';
  return `${image}${video}${audio}`;
}

function renderAttemptCard(run, sceneId, review, attemptId) {
  const attempt = (review.attempts || []).find(item => item.id === attemptId) || {};
  if (!attempt.id) return `<div class="attempt-card"><div class="asset-meta">tentativa indisponível</div></div>`;
  const isActive = attempt.id === review.active_attempt_id;
  const canUse = attempt.status !== 'failed';
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
        <div>imagem: ${escapeHtml(attempt.image_quality_score ?? '-')} · semântico ${escapeHtml(attempt.image_semantic_score ?? '-')}</div>
        <div>vídeo: ${escapeHtml(attempt.video_quality_score ?? '-')}</div>
        <div>áudio: ${escapeHtml(attempt.audio_quality_score ?? '-')}</div>
        <div>escopo: ${escapeHtml(attempt.retry_scope || 'original')}</div>
        <div>providers: ${escapeHtml([attempt.image_provider, attempt.video_provider, attempt.audio_provider].filter(Boolean).join(' · ') || '-')}</div>
        <div>motivo: ${escapeHtml(attempt.reason || '-')}</div>
        ${controlledWorkflowDetail(attempt)}
        ${attemptHeroDetail(attempt)}
        ${attemptAudioDetail(attempt)}
        ${attempt.error ? `<div style="grid-column:1 / -1" class="bad">erro: ${escapeHtml(attempt.error)}</div>` : ''}
        ${attempt.note ? `<div style="grid-column:1 / -1">nota: ${escapeHtml(attempt.note)}</div>` : ''}
      </div>
      <div class="attempt-actions">
        <button onclick="activateAttempt('${sceneId}', '${attempt.id}')" ${canUse && !isActive ? '' : 'disabled'}>Tornar ativa</button>
        <button class="primary" onclick="approveAttempt('${sceneId}', '${attempt.id}')" ${canUse ? '' : 'disabled'}>Aprovar esta tentativa</button>
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
  const voice = item.voice_role || item.voice_id ? ` · voz ${item.voice_role || 'narrator'}:${item.voice_id || '-'}` : '';
  return `${item.duration_seconds || 0}s · ${item.bit_rate || 0}bps${loudness} · ${premium}${ambient}${voice}${direction}`;
}

function attemptAudioDetail(attempt) {
  const job = attempt.audio_job || {};
  const premium = job.premium_audio === true ? 'áudio premium' : job.premium_audio === false ? 'áudio não-premium' : '';
  const direction = attempt.voice_direction || job.voice_direction || {};
  const loudness = job.loudness?.input_i_lufs ? ` · ${job.loudness.input_i_lufs} LUFS alvo ${job.loudness.target_i_lufs}` : '';
  const ambient = job.ambient?.profile?.label ? ` · ambiente ${job.ambient.profile.label}` : '';
  const voice = attempt.voice_role || job.voice_role || attempt.voice_id || job.voice_id ? ` · voz ${attempt.voice_role || job.voice_role || 'narrator'}:${attempt.voice_id || job.voice_id || '-'}` : '';
  if (!premium && !direction.tone && !job.waveform?.length) return '';
  return `<div style="grid-column:1 / -1">${escapeHtml(premium || 'áudio')}${escapeHtml(loudness)}${escapeHtml(ambient)}${escapeHtml(voice)}${direction.tone ? ` · ${escapeHtml(direction.tone)}` : ''}${waveformHtml(job.waveform)}</div>`;
}

function gateTone(status) {
  if (status === 'final_approved') return 'approved';
  if (status === 'published_current') return 'approved';
  if (status === 'ready_to_publish') return 'approved';
  if (status === 'scene_review_blocked') return 'rejected';
  if (status === 'blocked' || status === 'publish_failed') return 'rejected';
  return 'pending_review';
}

function productionStatusLabel(status) {
  const labels = {
    published_current: 'publicado atual',
    published_stale: 'publicado antigo',
    ready_to_publish: 'pronto para publicar',
    needs_final_review: 'aguardando revisão final',
    missing_video: 'sem vídeo final',
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
    el.innerHTML = `
      <div class="curation-head">
        <div>
          <div class="curation-title">Sala de Curadoria</div>
          <div class="curation-sub">Aguardando geração de cenas para abrir o gate visual.</div>
        </div>
        <span class="badge pending_review">aguardando</span>
      </div>`;
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
  const q = summary.quality_metrics || {};

  const sceneCards = (summary.scene_images || []).map(img => {
    const sceneId = String(img.scene_id);
    const review = scenes[sceneId] || {status: 'pending_review', note: '', reason: '', active_attempt_id: 'attempt_1'};
    const imageMetric = findByScene(q.images, sceneId);
    const audioMetric = findByScene(q.audio, sceneId);
    const clip = findByScene(summary.scene_videos, sceneId);
    const audio = findByScene(summary.audio_files, sceneId);
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
    const defaults = comparisonSelections[sceneId] || defaultCompareSelection(review);
    const leftAttempt = attempts.find(attempt => attempt.id === defaults.left)?.id || attemptId;
    const rightAttempt = attempts.find(attempt => attempt.id === defaults.right)?.id || attempts.find(attempt => attempt.id !== leftAttempt)?.id || leftAttempt;
    comparisonSelections[sceneId] = {left: leftAttempt, right: rightAttempt};
    const attemptStrip = attempts.map(attempt => `<span class="attempt-pill ${attempt.id === attemptId ? 'active' : ''}">${escapeHtml(attempt.id)} · ${escapeHtml(attempt.status || 'draft')}</span>`).join('');
    const autoVerdict = imageMetric.semantic_accepted === false || (imageMetric.issues || []).length ? 'revisar' : 'recomendada para aprovação';
    return `
      <div class="review-card">
        <div class="review-grid">
          <div>
            <img src="/api/runs/${run.id}/file?path=${encodeURIComponent(img.image_path)}" alt="Cena ${escapeHtml(sceneId)}">
          </div>
          <div>
            ${clip.video_path ? `<video controls src="/api/runs/${run.id}/file?path=${encodeURIComponent(clip.video_path)}"></video>` : `<div class="asset-meta">clipe ainda indisponível</div>`}
            ${audio.audio_path ? `<audio controls src="/api/runs/${run.id}/file?path=${encodeURIComponent(audio.audio_path)}" style="width:100%; margin-top:8px"></audio>` : ''}
          </div>
          <div class="review-meta">
            <strong>Cena ${escapeHtml(sceneId)}</strong>
            <span class="badge ${escapeHtml(review.status || 'pending_review')}">${escapeHtml(review.status || 'pending_review')}</span>
            <div style="margin-top:8px">pré-gate: ${escapeHtml(autoVerdict)}</div>
            <div>imagem: ${escapeHtml(imageMetric.quality_score || 0)} · semântico ${escapeHtml(imageMetric.semantic_score ?? '-')}</div>
            ${controlledWorkflowDetail(imageMetric)}
            <div>vídeo: ${escapeHtml(clip.quality_score || '-')}</div>
            <div>áudio: ${escapeHtml(audioMetric.quality_score || '-')}</div>
            <div>tentativa ativa: ${escapeHtml(attemptId)}</div>
            <div class="attempt-strip">${attemptStrip}</div>
            <div class="review-controls">
              <select id="${reasonId}">${reasonOptions(review.reason || '')}</select>
              <select id="${scopeId}">${scopeOptions(review.retry_scope || 'image_video')}</select>
              <textarea id="${noteId}" placeholder="Nota obrigatória para reprovar ou pedir retry">${escapeHtml(review.note || '')}</textarea>
              <button onclick="approveAttempt('${sceneId}', '${attemptId}')">Aprovar tentativa ativa</button>
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
    <div class="curation-scenes">${sceneCards}</div>
    <div class="final-gate">
      <div>
        <div class="curation-title">Corte final</div>
        <div class="curation-sub">Publicação só libera com todas as cenas aprovadas, vídeo visualizado e corte final aprovado.</div>
        <div class="curation-sub">Status real: ${escapeHtml(productionStatusLabel(production.status))}</div>
        <div class="curation-sub">YouTube: ${escapeHtml(publication.status || 'not_started')}${publication.url ? ` · <a href="${escapeHtml(publication.url)}" target="_blank">${escapeHtml(publication.url)}</a>` : ''}${publication.error ? ` · ${escapeHtml(publication.error)}` : ''}</div>
        ${production.published_current === false && publication.status === 'published' ? `<div class="curation-sub warn">O vídeo publicado não corresponde ao corte final atual.</div>` : ''}
      </div>
      ${summary.video_path ? `<video controls onplay="markFinalVideoViewed()" src="/api/runs/${run.id}/file?path=${encodeURIComponent('output/final_video.mp4')}"></video>` : `<span class="badge pending_review">sem vídeo</span>`}
      <div class="final-actions">
        <button onclick="authenticateYoutube().catch(err => logLine(err.message))">Autenticar YouTube</button>
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
  $('quality').textContent = run.summary?.quality_metrics?.overall_score ?? 0;
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
      <tbody>${jobs.map(job => `<tr><td>${escapeHtml(job.job_id || '-')}</td><td>${escapeHtml(job.provider || '-')} · ${escapeHtml(job.model || '-')}</td><td>${escapeHtml(job.status || '-')}</td><td>${job.elapsed_seconds || 0}s</td><td>$${(job.estimated_cost_usd || 0).toFixed(4)}</td><td>${escapeHtml(job.error || '-')}</td></tr>`).join('')}</tbody>
    </table>
    <table>
      <thead><tr><th>Mídia</th><th>Score</th><th>Técnico</th><th>Semântico</th><th>Detalhe</th><th>Issues</th></tr></thead>
      <tbody>
        ${(q.images || []).map(item => `<tr><td>imagem cena ${item.scene_id}</td><td>${item.quality_score || 0}</td><td>${item.technical_score ?? '-'}</td><td>${item.semantic_score ?? '-'} · ${item.semantic_accepted ? 'aceita' : 'revisar'}</td><td>${escapeHtml(imageQualityDetail(item))}</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
        ${consistency ? `<tr><td>coerência visual</td><td>${consistency.consistency_score || 0}</td><td>-</td><td>${consistency.accepted ? 'aceita' : 'revisar'}</td><td>${consistency.style_notes || '-'}</td><td>${(consistency.issues || []).join(', ') || '-'}</td></tr>` : ''}
        ${(q.audio || []).map(item => `<tr><td>áudio cena ${item.scene_id}</td><td>${item.quality_score || 0}</td><td>-</td><td>-</td><td>${escapeHtml(audioQualityDetail(item))}${waveformHtml(item.waveform)}</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
        ${q.video ? `<tr><td>vídeo final</td><td>${q.video.quality_score || 0}</td><td>-</td><td>-</td><td>${q.video.duration_seconds || 0}s · ${q.video.bit_rate || 0}bps</td><td>${(q.video.issues || []).join(', ') || '-'}</td></tr>` : ''}
        ${voices.map(item => `<tr><td>voz cena ${item.scene_id}</td><td>${item.quality_score || 0}</td><td>-</td><td>-</td><td>${escapeHtml(`${item.voice_id || '-'} · ${item.text_characters || 0} chars · ${item.premium_audio ? 'premium' : 'revisar'}${item.voice_direction?.tone ? ` · ${item.voice_direction.tone}` : ''}`)}</td><td>${(item.issues || []).join(', ') || '-'}</td></tr>`).join('')}
      </tbody>
    </table>
  `;

  const assets = $('assets');
  assets.innerHTML = '';
  const summary = run.summary || {};
  const curation = summary.curation?.scenes || {};
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
  for (const clip of summary.scene_videos || []) {
    if (clip.video_path) {
      const div = document.createElement('div');
      div.className = 'asset';
      div.innerHTML = `<video controls src="/api/runs/${run.id}/file?path=${encodeURIComponent(clip.video_path)}"></video><a href="/api/runs/${run.id}/file?path=${encodeURIComponent(clip.video_path)}" target="_blank">Clipe cena ${escapeHtml(clip.scene_id)} · ${escapeHtml(clip.provider || 'video')}</a><div class="asset-meta">score ${escapeHtml(clip.quality_score || 0)} · ${escapeHtml(clip.duration || 0)}s</div>`;
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
    if ((run.status === 'completed' || run.status === 'failed') && !['queued', 'uploading'].includes(publicationStatus)) {
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
        "scenes": final_state.get("scenes", []),
        "scene_images": final_state.get("scene_images", []),
        "scene_videos": final_state.get("scene_videos", []),
        "audio_files": final_state.get("audio_files", []),
        "runpod_jobs": final_state.get("runpod_jobs", []),
        "visual_bible": final_state.get("visual_bible", {}),
        "quality_metrics": final_state.get("quality_metrics", {}),
        "cost_estimate": final_state.get("cost_estimate", {}),
        "curation": {"status": "pending_review", "scenes": {}},
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


def _safe_float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _video_artifact_signature(run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    video_path = Path(summary.get("video_path") or "")
    if not video_path.is_absolute():
        video_path = run_dir / video_path
    if not video_path.exists() or not video_path.is_file():
        return {"exists": False, "path": str(video_path)}
    digest = hashlib.sha256()
    with video_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = video_path.stat()
    return {
        "exists": True,
        "path": str(video_path),
        "size_bytes": stat.st_size,
        "sha256": digest.hexdigest(),
        "mtime": stat.st_mtime,
    }


def _cost_quota_summary(summary: dict[str, Any]) -> dict[str, Any]:
    cost = summary.setdefault("cost_estimate", {})
    jobs = summary.get("runpod_jobs", [])
    voices = summary.get("quality_metrics", {}).get("voices", [])
    total_usd = _safe_float_value(cost.get("total_usd"))
    warn_usd = _safe_float_value(os.getenv("AI_FILM_COST_WARN_USD", "1.00"))
    limit_usd = _safe_float_value(os.getenv("AI_FILM_COST_LIMIT_USD", "2.00"))
    runpod_limit = _safe_float_value(os.getenv("AI_FILM_RUNPOD_COST_LIMIT_USD", "0.75"))
    runway_limit = _safe_float_value(os.getenv("AI_FILM_RUNWAY_COST_LIMIT_USD", "1.50"))
    elevenlabs_character_limit = int(
        _safe_float_value(os.getenv("AI_FILM_ELEVENLABS_CHAR_LIMIT_PER_RUN", "1200"))
    )
    elevenlabs_characters = sum(
        int(_safe_float_value(item.get("text_characters")))
        for item in voices
        if item.get("premium_audio")
    )
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
            "provider": "runpod",
            "usd": round(_safe_float_value(cost.get("runpod_usd")), 6),
            "quota": "serverless",
            "usage": {
                "jobs": sum(
                    1 for job in jobs if job.get("provider") not in {"gemini", "runway"}
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
    published_artifact = publication.get("artifact") or {}
    publication_status = str(publication.get("status") or "not_started")
    published_current = (
        publication_status == "published"
        and bool(current_artifact.get("exists"))
        and current_artifact.get("sha256") == published_artifact.get("sha256")
    )
    cost_quota = _cost_quota_summary(summary)
    blockers = list(curation_blockers)
    blockers.extend(cost_quota.get("blockers", []))

    if publication_status in {"queued", "uploading"}:
        status = publication_status
    elif published_current:
        status = "published_current"
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
    elif bool(current_artifact.get("exists")):
        status = "needs_final_review"
    else:
        status = "missing_video"

    production_status = {
        "status": status,
        "published_current": published_current,
        "current_artifact": current_artifact,
        "published_artifact": published_artifact,
        "publication_status": publication_status,
        "curation_status": curation.get("status"),
        "final_review_status": final_review.get("status"),
        "cost_quota_status": cost_quota.get("status"),
        "blockers": blockers,
        "warnings": cost_quota.get("warnings", []),
    }
    summary["cost_quota"] = cost_quota
    summary["production_status"] = production_status
    return production_status


def _apply_curation_summary(
    summary: dict[str, Any],
    run_dir: Path | None = None,
) -> dict[str, Any]:
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
    scene_ids = [
        str(item.get("scene_id"))
        for item in scene_images
        if item.get("scene_id") is not None
    ]
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
                    "created_at": datetime.utcnow().isoformat(),
                    "image_path": image.get("image_path"),
                    "video_path": video.get("video_path"),
                    "audio_path": audio.get("audio_path"),
                    "image_provider": image.get("generation_method")
                    or image.get("provider"),
                    "video_provider": video.get("provider"),
                    "audio_provider": audio.get("generation_method"),
                    "image_quality_score": image_metric.get("quality_score", 0),
                    "image_semantic_score": image_metric.get("semantic_score"),
                    "image_semantic_accepted": image_metric.get("semantic_accepted"),
                    "audio_quality_score": audio_metric.get("quality_score", 0),
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
    blockers = []
    if pending:
        blockers.append(f"{pending} cena(s) pendente(s)")
    if rejected:
        blockers.append(f"{rejected} cena(s) reprovada(s)")
    if retry_requested:
        blockers.append(f"{retry_requested} retry(s) solicitado(s)")

    final_review = curation.setdefault("final_review", {})
    final_review.setdefault("status", "draft")
    final_review.setdefault("video_viewed", False)
    final_review.setdefault("approved_at", None)
    final_review.setdefault("note", "")
    video_ready = bool(summary.get("video_exists"))
    scene_gate_passed = bool(scene_ids) and approved == len(scene_ids)
    can_final_approve = (
        scene_gate_passed and video_ready and bool(final_review.get("video_viewed"))
    )

    if final_review.get("status") == "final_approved" and not scene_gate_passed:
        final_review["status"] = "scene_review_blocked"
        final_review["approved_at"] = None

    if final_review.get("status") == "final_approved":
        status = "final_approved"
    elif blockers:
        status = "scene_review_blocked"
    elif scene_ids and approved == len(scene_ids):
        status = "ready_for_final_review"
    else:
        status = "pending_review"

    if not video_ready:
        blockers.append("vídeo final ausente")
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
    run_dir = run_dir or Path(".")
    production_status = _apply_production_status(summary, run_dir, blockers)
    curation.update(
        {
            "status": status,
            "approved_count": approved,
            "rejected_count": rejected,
            "pending_count": pending,
            "retry_requested_count": retry_requested,
            "total_scenes": len(scene_ids),
            "blockers": blockers,
            "can_final_approve": can_final_approve,
            "can_publish": production_status.get("status") == "ready_to_publish",
        }
    )
    return summary


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


def _find_scene_quality_record(
    summary: dict[str, Any],
    scene_id: str,
) -> dict[str, Any]:
    for record in summary.get("quality_metrics", {}).get("images", []):
        if str(record.get("scene_id")) == scene_id:
            return dict(record)
    return {}


def _controlled_image_retry_available() -> bool:
    provider = os.getenv("IMAGE_GENERATION_PROVIDER", "comfyui").strip().lower()
    model_family = os.getenv("COMFYUI_MODEL_FAMILY", "sdxl").strip().lower()
    controlnet_model = os.getenv(
        "COMFYUI_CONTROLNET_CANNY_MODEL",
        "controlnet-canny-sdxl-1.0.safetensors",
    ).strip()
    return bool(
        provider == "comfyui"
        and model_family == "sdxl"
        and os.getenv("RUNPOD_API_KEY")
        and os.getenv("RUNPOD_ENDPOINT_ID")
        and controlnet_model
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
    if _controlled_image_retry_available():
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
        "semantic_score": attempt.get("image_semantic_score"),
        "semantic_accepted": attempt.get("image_semantic_accepted"),
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
                "voice_direction": selected.get("voice_direction")
                or audio_quality_patch.get("voice_direction"),
                "voice_id": selected.get("voice_id"),
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
            "updated_at": datetime.utcnow().isoformat(),
        }
    )
    _reset_final_gate(summary, "stale_after_attempt_change")
    run["summary"] = summary
    _recompile_final_video_from_attempts(run)
    run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
    run["updated_at"] = datetime.utcnow().isoformat()
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


def _recompile_final_video_from_attempts(run: dict[str, Any]) -> dict[str, Any]:
    from open3d_implementation.core.langgraph_adapter import (
        _audio_loudness_target_lufs,
        _probe_media_quality,
    )

    run_dir = Path(run["run_dir"])
    output_dir = run_dir / "output"
    summary = run.get("summary", {})
    scene_ids = [
        str(item.get("scene_id"))
        for item in summary.get("scene_images", [])
        if item.get("scene_id") is not None
    ]
    clip_paths: list[Path] = []
    for scene_id in scene_ids:
        attempt = _active_attempt(summary, scene_id)
        clip_path = _run_path(run, attempt.get("video_path"))
        if clip_path and clip_path.exists() and clip_path.stat().st_size > 1000:
            clip_paths.append(clip_path)
            continue
        fallback_clip = _run_path(
            run,
            next(
                (
                    item.get("video_path")
                    for item in summary.get("scene_videos", [])
                    if str(item.get("scene_id")) == scene_id
                ),
                "",
            ),
        )
        if (
            fallback_clip
            and fallback_clip.exists()
            and fallback_clip.stat().st_size > 1000
        ):
            clip_paths.append(fallback_clip)
            continue
        for candidate in (
            output_dir / f"scene_{scene_id}_runway.mp4",
            output_dir / f"scene_{scene_id}_motion.mp4",
        ):
            if candidate.exists() and candidate.stat().st_size > 1000:
                clip_paths.append(candidate)
                summary.setdefault("scene_videos", []).append(
                    {
                        "scene_id": scene_id,
                        "video_path": str(candidate),
                        "provider": (
                            "runway"
                            if candidate.name.endswith("_runway.mp4")
                            else "ffmpeg_camera_motion"
                        ),
                    }
                )
                break

    if not clip_paths:
        raise RuntimeError("no_scene_clips_available")

    output_dir.mkdir(exist_ok=True)
    video_list = output_dir / "curation_video_filelist.txt"
    temp_video = output_dir / "curation_temp_video.mp4"
    final_video = output_dir / "final_video.mp4"
    _ffmpeg_concat_file(video_list, clip_paths)
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(video_list),
            "-c:v",
            "copy",
            "-pix_fmt",
            "yuv420p",
            str(temp_video),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg_video_concat_failed:{result.stderr[:300]}")

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
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                str(final_video),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if mux_result.returncode != 0:
            raise RuntimeError(f"ffmpeg_mux_failed:{mux_result.stderr[:300]}")
    else:
        temp_video.replace(final_video)

    for temp_path in (
        video_list,
        temp_video,
        output_dir / "curation_audio_filelist.txt",
        output_dir / "curation_combined_audio.m4a",
    ):
        if temp_path.exists():
            temp_path.unlink()

    video_metric = _probe_media_quality(str(final_video), "video")
    summary["video_path"] = str(final_video)
    summary["video_exists"] = final_video.exists()
    summary["video_size"] = final_video.stat().st_size if final_video.exists() else 0
    quality_metrics = summary.setdefault("quality_metrics", {})
    quality_metrics["video"] = video_metric
    return video_metric


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
        _generate_runway_clip,
        _resolve_comfyui_checkpoint,
        _resolve_image_style,
        _resolve_quality_preset,
        _run_comfyui_image_attempt,
        _run_gemini_image_attempt,
        _safe_float,
        _scene_audio_duration,
        _scene_seed,
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
        attempt_id = _next_attempt_id(summary, scene_id)
        scene_review["status"] = "retry_requested"
        scene_review["retry_status"] = "running"
        scene_review["retry_scope"] = scope
        scene_review["note"] = note
        scene_review["reason"] = reason
        scene_review["updated_at"] = datetime.utcnow().isoformat()
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = datetime.utcnow().isoformat()
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
        image_provider = (
            os.getenv("IMAGE_GENERATION_PROVIDER", "comfyui").strip().lower()
        )
        if image_provider not in {"comfyui", "gemini"}:
            image_provider = "comfyui"
        quality_preset = _resolve_quality_preset(quality_preset_key)
        checkpoint_name = _resolve_comfyui_checkpoint(image_style)
        style_label = _resolve_image_style(image_style)["label"]
        controlled_workflow = bool(
            image_provider == "comfyui"
            and source_image_metric.get("control_workflow_required")
            and _comfyui_controlnet_available()
        )
        if (
            source_image_metric.get("control_workflow_required")
            and image_provider == "comfyui"
            and _comfyui_controlnet_available()
            and (not base_image_path or not base_image_path.exists())
        ):
            raise RuntimeError("controlled_retry_reference_image_missing")

        if scope in {"image", "image_video", "full_scene"}:
            image_path = curation_dir / f"scene_{scene_id}_{attempt_id}_image.png"
            if controlled_workflow:
                instruction = (
                    f"{instruction} Use the controlled ControlNet retry path: "
                    "make the required hero object large, sharp, natural and readable "
                    "while preserving approved character identity and global style. "
                    "Use the control image as composition guidance only; do not render "
                    "visible construction outlines, black strokes, labels or guide lines."
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
                    control_image_path=(
                        str(base_image_path) if controlled_workflow else None
                    ),
                    reference_image_path=(
                        str(base_image_path) if base_image_path else None
                    ),
                )
            else:
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
            if not image_record or not image_metric:
                raise RuntimeError(
                    f"selective_image_retry_failed:{image_job.get('error') if image_job else 'unknown'}"
                )
        elif not image_path or not image_path.exists():
            raise RuntimeError("active_image_missing_for_video_retry")

        duration = max(
            3.0,
            _scene_audio_duration(summary.get("audio_files", []), scene_id),
            float(scene.get("duration") or 5),
        )
        video_path = curation_dir / f"scene_{scene_id}_{attempt_id}_runway.mp4"
        runway_source = {
            **scene,
            "scene_id": scene_id,
            "image_path": str(image_path),
            "prompt": (image_record or active_attempt).get("prompt")
            or scene.get("prompt")
            or "",
            "base_prompt": (image_record or active_attempt).get("base_prompt")
            or scene.get("prompt")
            or "",
            "camera_motion": scene.get("camera_motion", ""),
        }
        video_job, video_ok = _generate_runway_clip(
            runway_source,
            str(video_path),
            duration,
        )
        if not video_ok:
            raise RuntimeError(f"selective_video_retry_failed:{video_job.get('error')}")

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
                    "created_at": datetime.utcnow().isoformat(),
                    "image_path": str(image_path),
                    "video_path": str(video_path),
                    "audio_path": active_attempt.get("audio_path"),
                    "image_provider": (
                        image_record.get("generation_method")
                        if image_record
                        else image_provider
                    ),
                    "controlled_workflow": controlled_workflow,
                    "controlnet_model": (image_job or {}).get("controlnet_model", ""),
                    "control_image": (image_job or {}).get("control_image", ""),
                    "video_provider": "runway",
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
                    "image_job": image_job,
                    "video_job": video_job,
                }
            )
            scene_review.update(
                {
                    "status": "pending_review",
                    "retry_status": "succeeded",
                    "active_attempt_id": attempt_id,
                    "approved_attempt_id": None,
                    "updated_at": datetime.utcnow().isoformat(),
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
            summary["scene_videos"] = [
                item
                for item in summary.get("scene_videos", [])
                if str(item.get("scene_id")) != scene_id
            ]
            summary.setdefault("scene_videos", []).append(
                {
                    "scene_id": scene_id,
                    "video_path": str(video_path),
                    "provider": "runway",
                    "job_id": video_job.get("job_id"),
                    "duration": duration,
                    "quality_score": video_job.get("quality_score", 0),
                }
            )
            jobs = summary.setdefault("runpod_jobs", [])
            if image_job:
                jobs.append(image_job)
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

        video_metric = _recompile_final_video_from_attempts(run)
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            summary = _apply_curation_summary(
                run.get("summary", {}), Path(run["run_dir"])
            )
            run["summary"] = summary
            run["updated_at"] = datetime.utcnow().isoformat()
            _persist_summary(run)
        _append_log(
            run_id,
            f"retry seletivo concluído: cena {scene_id}, tentativa {attempt_id}, vídeo score {video_metric.get('quality_score')}",
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
                    "created_at": datetime.utcnow().isoformat(),
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
            run["updated_at"] = datetime.utcnow().isoformat()
            _persist_summary(run)
        _append_log(
            run_id,
            f"retry seletivo falhou: cena {scene_id}: {type(exc).__name__}: {exc}",
        )


def _scene_narration_text(summary: dict[str, Any], scene_id: str) -> str:
    from open3d_implementation.core.langgraph_adapter import _premium_audio_narration

    scene = _summary_scene(summary, scene_id)
    return _premium_audio_narration(scene)


def _run_selective_audio_retry(
    run_id: str,
    scene_id: str,
    note: str,
    reason: str,
    scope: str,
) -> None:
    from open3d_implementation.core.langgraph_adapter import (
        _audio_quality_gate,
        _elevenlabs_remaining_characters,
        _elevenlabs_voice_id_for_scene,
        _elevenlabs_voice_settings,
        _enhance_premium_audio,
        _premium_audio_direction,
        _probe_media_quality,
        _response_error_detail,
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
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = datetime.utcnow().isoformat()
        _persist_summary(run)

    _append_log(run_id, f"retry ElevenLabs iniciado: cena {scene_id}")

    try:
        api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("elevenlabs_api_key_missing")
        scene = _summary_scene(summary, scene_id)
        voice_id, voice_role = _elevenlabs_voice_id_for_scene(scene)
        if not voice_id:
            raise RuntimeError("elevenlabs_voice_id_missing")

        run_dir = Path(run["run_dir"])
        curation_dir = run_dir / "output" / "curation"
        curation_dir.mkdir(parents=True, exist_ok=True)
        summary = run.get("summary", {})
        narration_text = _scene_narration_text(summary, scene_id)
        if not narration_text:
            raise RuntimeError("scene_narration_text_missing")
        voice_direction = _premium_audio_direction(scene)
        remaining = _elevenlabs_remaining_characters(api_key)
        if remaining is not None and len(narration_text) > remaining:
            raise RuntimeError(
                f"elevenlabs_insufficient_characters:needed={len(narration_text)},remaining={remaining}"
            )

        audio_path = curation_dir / f"scene_{scene_id}_{attempt_id}_audio.mp3"
        raw_audio_path = curation_dir / f"scene_{scene_id}_{attempt_id}_audio_raw.mp3"
        model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            },
            json={
                "text": narration_text,
                "model_id": model_id,
                "voice_settings": _elevenlabs_voice_settings(),
            },
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"elevenlabs_http_{response.status_code}:{_response_error_detail(response)}"
            )
        raw_audio_path.write_bytes(response.content)
        media_quality = _enhance_premium_audio(
            str(raw_audio_path),
            str(audio_path),
            scene,
        )
        if not bool(media_quality.get("valid")):
            raw_audio_path.replace(audio_path)
            media_quality = _probe_media_quality(str(audio_path), "audio")
        else:
            raw_audio_path.unlink(missing_ok=True)
        media_quality = _audio_quality_gate(
            media_quality,
            narration_text,
            "elevenlabs",
        )
        if not bool(media_quality.get("valid")):
            raise RuntimeError(
                "elevenlabs_invalid_audio:"
                + ",".join(str(issue) for issue in media_quality.get("issues", []))
            )

        usd_per_1k_chars = float(os.getenv("ELEVENLABS_USD_PER_1K_CHARS", "0.30"))
        estimated_cost = len(narration_text) / 1000 * usd_per_1k_chars
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
            attempts.append(
                {
                    "id": attempt_id,
                    "status": "active",
                    "created_at": datetime.utcnow().isoformat(),
                    "image_path": previous_active.get("image_path"),
                    "video_path": previous_active.get("video_path"),
                    "audio_path": str(audio_path),
                    "audio_text": narration_text,
                    "voice_direction": voice_direction,
                    "image_provider": previous_active.get("image_provider"),
                    "video_provider": previous_active.get("video_provider"),
                    "audio_provider": "elevenlabs",
                    "voice_id": voice_id,
                    "voice_role": voice_role,
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
                        "voice_id": voice_id,
                        "voice_role": voice_role,
                        "status": "succeeded",
                        "estimated_cost_usd": round(estimated_cost, 6),
                        "text_characters": len(narration_text),
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
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            summary["audio_files"] = _replace_scene_record(
                summary.get("audio_files", []),
                scene_id,
                {
                    "audio_path": str(audio_path),
                    "text": narration_text,
                    "voice_direction": voice_direction,
                    "voice_id": voice_id,
                    "voice_role": voice_role,
                    "generation_method": "elevenlabs",
                },
            )
            quality_metrics = summary.setdefault("quality_metrics", {})
            quality_metrics["audio"] = _replace_scene_record(
                quality_metrics.get("audio", []),
                scene_id,
                {
                    "generation_method": "elevenlabs",
                    "voice_direction": voice_direction,
                    **media_quality,
                },
            )
            quality_metrics["voices"] = _replace_scene_record(
                quality_metrics.get("voices", []),
                scene_id,
                {
                    "voice_id": voice_id,
                    "voice_role": voice_role,
                    "model_id": model_id,
                    "text_characters": len(narration_text),
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
            run["summary"] = summary

        video_metric = _recompile_final_video_from_attempts(run)
        with RUN_LOCK:
            run = RUNS.get(run_id)
            if run is None:
                return
            run["summary"] = _apply_curation_summary(
                run.get("summary", {}), Path(run["run_dir"])
            )
            run["updated_at"] = datetime.utcnow().isoformat()
            _persist_summary(run)
        _append_log(
            run_id,
            f"retry ElevenLabs concluído: cena {scene_id}, tentativa {attempt_id}, áudio score {media_quality.get('quality_score')}, vídeo score {video_metric.get('quality_score')}",
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
                    "created_at": datetime.utcnow().isoformat(),
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
            run["updated_at"] = datetime.utcnow().isoformat()
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
                "started_at": datetime.utcnow().isoformat(),
                "error": None,
                "failed_at": None,
                "metadata": metadata,
            }
        )
        run["summary"] = summary
        run["updated_at"] = datetime.utcnow().isoformat()
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
                    "completed_at": datetime.utcnow().isoformat(),
                    "error": None,
                    "failed_at": None,
                    "artifact": artifact,
                    **result,
                }
            )
            summary = _apply_curation_summary(summary, Path(run["run_dir"]))
            run["summary"] = summary
            run["updated_at"] = datetime.utcnow().isoformat()
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
                    "failed_at": datetime.utcnow().isoformat(),
                }
            )
            run["summary"] = summary
            run["updated_at"] = datetime.utcnow().isoformat()
            _persist_summary(run)
        _append_log(run_id, f"falha no upload YouTube: {type(exc).__name__}: {exc}")


def _start_pipeline_run(
    story_text: str,
    image_style: str,
    image_quality_preset: str,
    retry_of: str | None = None,
    target_scene_id: str | None = None,
) -> dict[str, Any]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    run_dir = RUNS_ROOT / run_id
    with RUN_LOCK:
        RUNS[run_id] = {
            "id": run_id,
            "status": "running",
            "run_dir": str(run_dir),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "retry_of": retry_of,
            "target_scene_id": target_scene_id,
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
        "updated_at": datetime.utcnow().isoformat(),
        "retry_of": None,
        "target_scene_id": None,
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

    run = _start_pipeline_run(
        story_text=story_text,
        image_style=image_style,
        image_quality_preset=image_quality_preset,
        retry_of=payload.get("retry_of"),
    )
    return jsonify({"id": run["id"], "status": "running", "run_dir": run["run_dir"]})


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
            "updated_at": datetime.utcnow().isoformat(),
        }
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = datetime.utcnow().isoformat()
        _persist_summary(run)
        return jsonify(run)


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


@app.post("/api/runs/<run_id>/final-video-viewed")
def mark_final_video_viewed(run_id: str) -> Response:
    with RUN_LOCK:
        run = RUNS.get(run_id)
        if run is None:
            return jsonify({"error": "run not found"}), 404
        summary = run.get("summary")
        if not summary:
            return jsonify({"error": "run summary is not ready"}), 409
        final_review = summary.setdefault("curation", {}).setdefault("final_review", {})
        final_review["video_viewed"] = True
        final_review["viewed_at"] = datetime.utcnow().isoformat()
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = datetime.utcnow().isoformat()
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
                "approved_at": datetime.utcnow().isoformat(),
                "note": note,
            }
        )
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = datetime.utcnow().isoformat()
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
        run["updated_at"] = datetime.utcnow().isoformat()
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
            run["updated_at"] = datetime.utcnow().isoformat()
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
                "queued_at": datetime.utcnow().isoformat(),
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
            "updated_at": datetime.utcnow().isoformat(),
        }
        run["summary"] = _apply_curation_summary(summary, Path(run["run_dir"]))
        run["updated_at"] = datetime.utcnow().isoformat()
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
