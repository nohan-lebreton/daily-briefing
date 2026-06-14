#!/usr/bin/env python3
"""
Daily Briefing — App menubar macOS
Réveil intelligent : Spotify + résumé Google Agenda parlé

Modes d'exécution :
  python3 daily_briefing_app.py            → lance l'app dans la menubar
  python3 daily_briefing_app.py --settings → ouvre la fenêtre de paramètres
  python3 daily_briefing_app.py --alarm    → déclenche l'alarme (appelé par launchd)
"""

import sys
import json
import os
import subprocess
import threading
import datetime
from pathlib import Path

# ─── Chemins ──────────────────────────────────────────────────────────────────

APP_SCRIPT   = Path(__file__).resolve()
CONFIG_DIR   = Path.home() / ".daily-briefing"

# Icône soleil monochrome encodée en base64 (PNG 22x22 template-compatible)
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABYAAAAWCAAAAADh3zPnAAAATklEQVR4nIVRQQoAMAjq"
    "/592MIqybPOwSJxYmSVgCoDkBw2iwTIuhehWQ1Hd8+EgIiHAvDdJ3+IdAmGm1Zv3K4nO"
    "rafUO1k3SP/7Mf5HO+mlkm7CGMvNAAAAAElFTkSuQmCC"
)

def _get_icon_path() -> str:
    icon_path = CONFIG_DIR / "icon.png"
    if not icon_path.exists():
        import base64
        CONFIG_DIR.mkdir(exist_ok=True)
        icon_path.write_bytes(base64.b64decode(_ICON_B64))
    return str(icon_path)
CONFIG_FILE  = CONFIG_DIR / "config.json"
SUMMARY_FILE = Path.home() / "daily-briefing-summary.txt"
PLIST_PATH   = Path.home() / "Library" / "LaunchAgents" / "com.fairforge.daily-briefing.plist"

# ─── Config par défaut ────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "days": [0, 1, 2, 3, 4],          # 0=Lun … 6=Dim
    "hour": 9,
    "minute": 0,
    "spotify_uri": "spotify:playlist:37i9dQZF1DX4sWSpwq3LiO",
    "music_delay": 10,                 # secondes de musique avant le brief
    "alarm_volume": 80,                # volume Spotify pendant le réveil (0-100)
    "voice": "Thomas",
    "voice_volume": 80                 # volume de la voix TTS (0-100)
}

# launchd : 0=Dim, 1=Lun … 6=Sam  →  notre index 0=Lun, donc décalage
_LAUNCHD_WEEKDAY = [1, 2, 3, 4, 5, 6, 0]   # index app → weekday launchd


# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    CONFIG_DIR.mkdir(exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    _install_launchd(cfg)


# ─── launchd ──────────────────────────────────────────────────────────────────

def _install_launchd(cfg: dict):
    python = sys.executable

    intervals_xml = ""
    for day_idx in cfg.get("days", []):
        wd = _LAUNCHD_WEEKDAY[day_idx]
        intervals_xml += (
            f"        <dict>\n"
            f"            <key>Weekday</key><integer>{wd}</integer>\n"
            f"            <key>Hour</key><integer>{cfg['hour']}</integer>\n"
            f"            <key>Minute</key><integer>{cfg['minute']}</integer>\n"
            f"        </dict>\n"
        )

    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.fairforge.daily-briefing</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{APP_SCRIPT}</string>
        <string>--alarm</string>
    </array>

    <key>StartCalendarInterval</key>
    <array>
{intervals_xml}    </array>

    <key>StandardOutPath</key>
    <string>/tmp/daily-briefing.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/daily-briefing-error.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>"""

    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist)
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True)


# ─── Logique alarme ───────────────────────────────────────────────────────────

def run_alarm(cfg: dict, test_mode: bool = False):
    import time

    spotify_uri  = cfg.get("spotify_uri", "")
    music_delay  = int(cfg.get("music_delay", 10))
    alarm_volume = int(cfg.get("alarm_volume", 80))
    brief_volume = max(10, alarm_volume // 4)   # ~25% du volume réveil pendant le brief
    voice        = cfg.get("voice", "Thomas")
    voice_volume = int(cfg.get("voice_volume", 80))

    def set_spotify_volume(vol):
        subprocess.run(
            ["osascript", "-e", f'tell application "Spotify" to set sound volume to {vol}'],
            capture_output=True
        )

    # 1. Ouvrir Spotify au volume de réveil
    if spotify_uri:
        subprocess.Popen(["open", spotify_uri])
        time.sleep(3)
        set_spotify_volume(alarm_volume)

    # 2. Attendre (pleine musique)
    delay = 5 if test_mode else music_delay
    time.sleep(delay)

    # 3. Attendre le fichier résumé (écrit par Cowork, max 5 min)
    if not test_mode:
        waited = 0
        today  = datetime.date.today()
        while waited < 300:
            if SUMMARY_FILE.exists():
                mtime = datetime.datetime.fromtimestamp(SUMMARY_FILE.stat().st_mtime).date()
                if mtime == today:
                    break
            time.sleep(5)
            waited += 5

    # 4. Baisser le volume pendant le brief
    set_spotify_volume(brief_volume)

    # 5. Lire le résumé (en test on lit aussi le vrai fichier si disponible)
    if SUMMARY_FILE.exists():
        summary = SUMMARY_FILE.read_text().strip() or "Aucun résumé disponible."
    elif test_mode:
        summary = "Bonjour ! Aucun résumé trouvé. Lance d'abord la tâche Cowork daily briefing pour générer le fichier."
    else:
        summary = "Je n'ai pas pu récupérer le résumé de la journée."

    # Sauvegarder le volume système, mettre le volume voix, lire, restaurer
    try:
        sys_vol = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {voice_volume}"],
            capture_output=True
        )
    except Exception:
        sys_vol = None

    subprocess.run(["say", "-v", voice, summary])

    if sys_vol is not None:
        try:
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {sys_vol}"],
                capture_output=True
            )
        except Exception:
            pass

    # 6. Reprendre la musique au volume de réveil
    time.sleep(0.5)
    set_spotify_volume(alarm_volume)


# ─── Fenêtre Paramètres (pywebview — design Apple HIG) ───────────────────────

def _build_settings_html() -> str:
    """Génère le HTML de la fenêtre de paramètres façon macOS System Settings."""
    return r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Briefing</title>
<style>
  :root {
    --bg:      #f5f5f7;
    --card:    #ffffff;
    --accent:  #0071e3;
    --accent-h:#0077ed;
    --t1:      #1d1d1f;
    --t2:      #6e6e73;
    --t3:      #86868b;
    --sep:     #d2d2d7;
    --green:   #34c759;
    --r:       10px;
    --pad:     20px;
  }
  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
                 "Helvetica Neue", system-ui, sans-serif;
    background: var(--bg);
    color: var(--t1);
    font-size: 13px;
    line-height: 1.45;
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
    padding-bottom: 80px;
  }

  /* Toolbar */
  .toolbar {
    position: sticky; top: 0; z-index: 100;
    display: flex; align-items: center; justify-content: space-between;
    padding: 18px var(--pad) 12px;
    background: rgba(245,245,247,.92);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 1px solid rgba(0,0,0,.06);
  }
  .tb-left { display:flex; align-items:center; gap:12px; }
  .tb-icon {
    width:40px; height:40px; border-radius:10px;
    background: linear-gradient(145deg,#f9d423,#f7931e);
    display:flex; align-items:center; justify-content:center;
    font-size:22px; flex-shrink:0;
    box-shadow: 0 2px 8px rgba(247,147,30,.3);
  }
  .tb-title { font-size:17px; font-weight:600; letter-spacing:-.3px; }
  .tb-sub   { font-size:11px; color:var(--t3); margin-top:1px; }
  .btn-update {
    display:flex; align-items:center; gap:6px;
    padding:6px 14px;
    border: 1px solid var(--sep); border-radius:20px;
    background: var(--card);
    font:500 12px/1 inherit; color:var(--t1);
    cursor:pointer; transition:background .12s; white-space:nowrap;
  }
  .btn-update:hover  { background:#e8e8ed; }
  .btn-update:active { transform:scale(.97); }

  /* Content */
  .content { padding: 20px var(--pad) 0; }

  /* Section */
  .section { margin-bottom:22px; }
  .section-label {
    font-size:11px; font-weight:600; color:var(--t2);
    text-transform:uppercase; letter-spacing:.07em;
    margin-bottom:6px; padding-left:4px;
  }

  /* Card */
  .card {
    background: var(--card); border-radius:var(--r); overflow:hidden;
    box-shadow: 0 1px 0 rgba(0,0,0,.07), 0 0 0 .5px rgba(0,0,0,.06);
  }
  .row {
    display:flex; align-items:center;
    padding:0 16px; min-height:44px;
    border-bottom:1px solid var(--sep); gap:12px;
  }
  .row:last-child { border-bottom:none; }
  .row-label { flex:1; font-size:13px; }
  .row-sub   { font-size:11px; color:var(--t3); margin-top:2px; }

  /* Days */
  .days-row {
    display:flex; justify-content:space-between; align-items:center;
    padding:14px 16px; gap:6px;
  }
  .day-toggle input[type=checkbox] { display:none; }
  .day-toggle label {
    display:flex; flex-direction:column; align-items:center;
    gap:5px; cursor:pointer;
  }
  .day-name { font-size:10px; font-weight:600; color:var(--t2); letter-spacing:.03em; }
  .day-pill {
    width:36px; height:36px; border-radius:50%;
    background:#e8e8ed;
    display:flex; align-items:center; justify-content:center;
    font-size:13px; font-weight:600; color:var(--t2);
    transition:background .18s, color .18s; user-select:none;
  }
  .day-toggle input:checked + label .day-pill { background:var(--accent); color:#fff; }

  /* Time */
  .time-wrap { display:flex; align-items:center; gap:4px; padding:8px 0; }
  .time-inp {
    width:56px; padding:8px 6px;
    border:1.5px solid var(--sep); border-radius:8px;
    font-size:24px; font-weight:200; font-family:inherit;
    color:var(--t1); text-align:center; background:#fff;
    outline:none; -moz-appearance:textfield;
    transition:border-color .15s;
  }
  .time-inp:focus { border-color:var(--accent); }
  .time-inp::-webkit-inner-spin-button,
  .time-inp::-webkit-outer-spin-button { -webkit-appearance:none; }
  .time-sep { font-size:28px; font-weight:200; color:var(--t2); line-height:1; }

  /* Text input */
  .text-inp {
    flex:1; border:none; outline:none;
    font:12px/1 'SF Mono','Menlo','Courier New',monospace;
    color:var(--t1); background:transparent;
  }
  .text-inp::placeholder { color:var(--t3); }

  /* Slider */
  .slider-wrap { display:flex; align-items:center; gap:10px; flex:1; }
  input[type=range] {
    flex:1; -webkit-appearance:none; height:4px; border-radius:2px; outline:none;
    background:linear-gradient(to right, var(--accent) 0%, var(--accent) var(--pct,50%), #d2d2d7 var(--pct,50%));
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance:none; width:20px; height:20px; border-radius:50%;
    background:#fff; cursor:pointer;
    box-shadow:0 1px 4px rgba(0,0,0,.25),0 0 0 .5px rgba(0,0,0,.1);
    transition:transform .1s;
  }
  input[type=range]::-webkit-slider-thumb:active { transform:scale(1.12); }
  .slider-val { min-width:44px; text-align:right; font-size:13px; font-weight:500; color:var(--accent); }

  /* Select */
  .select-wrap { display:flex; align-items:center; gap:4px; }
  select {
    border:none; background:transparent;
    font:13px/1 inherit; color:var(--t1);
    outline:none; cursor:pointer;
    -webkit-appearance:none; appearance:none;
  }
  .select-caret { font-size:10px; color:var(--t3); pointer-events:none; }

  /* Brief */
  .brief-header {
    display:flex; align-items:center; justify-content:space-between;
    padding:10px 16px 0;
  }
  .brief-date { font-size:11px; color:var(--t3); }
  .btn-refresh { background:none; border:none; color:var(--accent); font:12px/1 inherit; cursor:pointer; padding:0; }
  .brief-body { padding:10px 16px 14px; font-size:13px; line-height:1.55; white-space:pre-wrap; min-height:80px; }
  .placeholder { color:var(--t3); font-style:italic; }

  /* Bottom bar */
  .bottom-bar {
    position:fixed; bottom:0; left:0; right:0;
    display:flex; align-items:center; gap:8px; padding:12px var(--pad);
    background:rgba(245,245,247,.88);
    -webkit-backdrop-filter:saturate(180%) blur(20px);
    backdrop-filter:saturate(180%) blur(20px);
    border-top:1px solid rgba(0,0,0,.07);
  }
  .confirm { flex:1; font-size:12px; font-weight:500; color:var(--green); opacity:0; transition:opacity .3s; }
  .confirm.show { opacity:1; }
  .btn {
    padding:7px 18px; border-radius:20px; border:none;
    font:500 13px/1 inherit; cursor:pointer; transition:all .13s; white-space:nowrap;
  }
  .btn:active { transform:scale(.96); }
  .btn-ghost   { background:rgba(0,0,0,.06); color:var(--t1); }
  .btn-ghost:hover  { background:rgba(0,0,0,.1); }
  .btn-outline { background:none; border:1px solid var(--sep); color:var(--t2); }
  .btn-outline:hover { background:rgba(0,0,0,.04); }
  .btn-primary { background:var(--accent); color:#fff; font-weight:600; }
  .btn-primary:hover { background:var(--accent-h); }
  .btn-primary:disabled { background:#d2d2d7; color:#fff; cursor:default; transform:none; }
  .btn-danger  { background:#ff3b30; color:#fff; }
  .btn-danger:hover  { background:#ff2d20; }
  .modal-bd { position:fixed;inset:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:900; }
  .modal-box { background:#fff;border-radius:14px;padding:24px 24px 18px;width:280px;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,.2); }
  .modal-title { font-size:15px;font-weight:600;margin-bottom:6px; }
  .modal-msg { font-size:13px;color:var(--t2);line-height:1.5;margin-bottom:20px; }
  .modal-actions { display:flex;gap:8px;justify-content:center; }
</style>
</head>
<body>

<div class="toolbar">
  <div class="tb-left">
    <div class="tb-icon">☀️</div>
    <div>
      <div class="tb-title">Daily Briefing</div>
      <div class="tb-sub">Réveil intelligent</div>
    </div>
  </div>
  <button class="btn-update" onclick="updateApp()">
    <svg width="11" height="11" viewBox="0 0 11 11" fill="none"
         stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <line x1="5.5" y1="9" x2="5.5" y2="1"/>
      <polyline points="2,4 5.5,1 9,4"/>
    </svg>
    Mettre à jour
  </button>
</div>

<div class="content">

  <div class="section">
    <div class="section-label">Jours actifs</div>
    <div class="card"><div class="days-row" id="days-row"></div></div>
  </div>

  <div class="section">
    <div class="section-label">Heure de déclenchement</div>
    <div class="card">
      <div class="row">
        <span class="row-label">Réveil à</span>
        <div class="time-wrap">
          <input type="number" class="time-inp" id="hour"   min="0" max="23" value="9"  oninput="clamp(this,0,23)">
          <span class="time-sep">:</span>
          <input type="number" class="time-inp" id="minute" min="0" max="59" value="0"  oninput="clamp(this,0,59)">
        </div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">Musique de réveil</div>
    <div class="card">
      <div class="row" style="flex-direction:column;align-items:flex-start;padding-top:10px;padding-bottom:8px;gap:3px;">
        <span class="row-label" style="font-weight:500">URI Spotify</span>
        <span class="row-sub">Clic droit sur un titre ou playlist → Partager → Copier l'URI</span>
      </div>
      <div class="row">
        <input type="text" class="text-inp" id="spotify-uri" placeholder="spotify:playlist:…">
      </div>
      <div class="row">
        <span class="row-label">Durée avant le brief</span>
        <div class="slider-wrap">
          <input type="range" id="delay" min="5" max="60" value="10"
                 oninput="syncSlider(this,'delay-val',v=>v+' s')">
          <span class="slider-val" id="delay-val">10 s</span>
        </div>
      </div>
      <div class="row">
        <span class="row-label">Volume</span>
        <div class="slider-wrap">
          <input type="range" id="volume" min="10" max="100" value="80"
                 oninput="syncSlider(this,'vol-val',v=>v+' %')">
          <span class="slider-val" id="vol-val">80 %</span>
        </div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">Brief vocal</div>
    <div class="card">
      <div class="row">
        <span class="row-label">Voix</span>
        <div class="select-wrap">
          <select id="voice">
            <option value="Thomas">Thomas</option>
            <option value="Amélie">Amélie</option>
            <option value="Nathalie">Nathalie</option>
          </select>
          <span class="select-caret">▾</span>
        </div>
      </div>
      <div class="row">
        <span class="row-label">Volume de la voix</span>
        <div class="slider-wrap">
          <input type="range" id="voice-volume" min="10" max="100" value="80"
                 oninput="syncSlider(this,'voice-vol-val',v=>v+' %')">
          <span class="slider-val" id="voice-vol-val">80 %</span>
        </div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-label">Brief du jour</div>
    <div class="card">
      <div class="brief-header">
        <span class="brief-date" id="brief-date">Chargement…</span>
        <button class="btn-refresh" onclick="loadSummary()">↺ Actualiser</button>
      </div>
      <div class="brief-body" id="brief-text">—</div>
    </div>
  </div>

</div>

<div class="bottom-bar">
  <button class="btn btn-danger"  onclick="uninstallApp()">Désinstaller</button>
  <span class="confirm" id="confirm">✓ Paramètres sauvegardés</span>
  <button class="btn btn-ghost"   onclick="testAlarm()">🔊 Tester</button>
  <button class="btn btn-primary" id="btn-save" onclick="saveSettings()" disabled>Sauvegarder</button>
  <button class="btn btn-outline" onclick="callApi('close',null)">Fermer</button>
</div>

<script>
const DAY_ABR  = ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim'];
const DAY_INIT = ['L','M','M','J','V','S','D'];

// ── Bridge JS → Python via webkit.messageHandlers ───────────────────────────
const _pending = {};
window.__pyResp = (result, id) => { if (_pending[id]) { _pending[id](result); delete _pending[id]; } };
function callApi(action, data) {
  return new Promise(resolve => {
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2);
    _pending[id] = resolve;
    window.webkit.messageHandlers.api.postMessage({ action, data: data ?? null, id });
  });
}

let _savedSnapshot = null;  // JSON snapshot de la dernière config sauvegardée

function configSnapshot() { return JSON.stringify(getConfig()); }

function checkDirty() {
  const dirty = _savedSnapshot !== null && configSnapshot() !== _savedSnapshot;
  document.getElementById('btn-save').disabled = !dirty;
}

function watchInputs() {
  document.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('input',  checkDirty);
    el.addEventListener('change', checkDirty);
  });
}

function buildDays(active) {
  document.getElementById('days-row').innerHTML = DAY_ABR.map((d,i) => `
    <div class="day-toggle">
      <input type="checkbox" id="d${i}" ${active.includes(i)?'checked':''}>
      <label for="d${i}">
        <span class="day-name">${d}</span>
        <span class="day-pill">${DAY_INIT[i]}</span>
      </label>
    </div>`).join('');
  // Réattacher les écouteurs sur les nouvelles checkboxes
  document.querySelectorAll('.day-toggle input').forEach(el => {
    el.addEventListener('change', checkDirty);
  });
}

function syncSlider(el, labelId, fmt) {
  const v = parseInt(el.value);
  const pct = ((v - +el.min) / (+el.max - +el.min) * 100).toFixed(1) + '%';
  el.style.setProperty('--pct', pct);
  document.getElementById(labelId).textContent = fmt(v);
}

function clamp(el, min, max) {
  let v = parseInt(el.value);
  if (isNaN(v)) v = min;
  el.value = Math.min(max, Math.max(min, v));
}

function getConfig() {
  return {
    days:         [...document.querySelectorAll('.day-toggle input:checked')].map(e=>+e.id.slice(1)),
    hour:         parseInt(document.getElementById('hour').value)||0,
    minute:       parseInt(document.getElementById('minute').value)||0,
    spotify_uri:  document.getElementById('spotify-uri').value.trim(),
    music_delay:  parseInt(document.getElementById('delay').value),
    alarm_volume: parseInt(document.getElementById('volume').value),
    voice:        document.getElementById('voice').value,
    voice_volume: parseInt(document.getElementById('voice-volume').value),
  };
}

function populate(cfg) {
  buildDays(cfg.days || [0,1,2,3,4]);
  document.getElementById('hour').value        = String(cfg.hour||9).padStart(2,'0');
  document.getElementById('minute').value      = String(cfg.minute||0).padStart(2,'0');
  document.getElementById('spotify-uri').value = cfg.spotify_uri || '';
  document.getElementById('delay').value       = cfg.music_delay || 10;
  document.getElementById('volume').value      = cfg.alarm_volume || 80;
  document.getElementById('voice').value        = cfg.voice || 'Thomas';
  document.getElementById('voice-volume').value = cfg.voice_volume || 80;
  syncSlider(document.getElementById('delay'),        'delay-val',     v=>v+' s');
  syncSlider(document.getElementById('volume'),       'vol-val',       v=>v+' %');
  syncSlider(document.getElementById('voice-volume'), 'voice-vol-val', v=>v+' %');
  // Fixer le snapshot de référence et verrouiller le bouton
  _savedSnapshot = configSnapshot();
  document.getElementById('btn-save').disabled = true;
  watchInputs();
}

async function loadSummary() {
  document.getElementById('brief-date').textContent = 'Chargement…';
  const r = await callApi('get_summary', null);
  if (r && r.text) {
    document.getElementById('brief-date').textContent = 'Généré le ' + r.date;
    document.getElementById('brief-text').textContent = r.text;
  } else {
    document.getElementById('brief-date').textContent = '';
    document.getElementById('brief-text').innerHTML =
      '<span class="placeholder">Aucun brief disponible.\nLance la tâche Cowork "daily-breifing" pour en générer un.</span>';
  }
}

async function saveSettings() {
  const cfg = getConfig();
  await callApi('save_settings', cfg);
  _savedSnapshot = configSnapshot();
  document.getElementById('btn-save').disabled = true;
  const el = document.getElementById('confirm');
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2500);
}

async function testAlarm() {
  await callApi('run_test', getConfig());
}

function showModal(title, msg, buttons) {
  return new Promise(resolve => {
    const bd = document.createElement('div');
    bd.className = 'modal-bd';
    bd.innerHTML = `<div class="modal-box">
      <div class="modal-title">${title}</div>
      ${msg ? `<div class="modal-msg">${msg}</div>` : ''}
      <div class="modal-actions">
        ${buttons.map((b,i)=>`<button class="btn ${b.cls}" data-i="${i}">${b.label}</button>`).join('')}
      </div></div>`;
    document.body.appendChild(bd);
    bd.querySelectorAll('button').forEach(btn => {
      btn.onclick = () => { document.body.removeChild(bd); resolve(+btn.dataset.i); };
    });
  });
}

async function uninstallApp() {
  const r = await showModal(
    'Désinstaller Daily Briefing ?',
    "L'alarme sera supprimée et l'application quittera.",
    [{label:'Annuler', cls:'btn-outline'}, {label:'Désinstaller', cls:'btn-danger'}]
  );
  if (r !== 1) return;
  callApi('uninstall', null);
}

async function updateApp() {
  const btn = document.querySelector('.btn-update');
  btn.disabled = true;
  btn.textContent = 'Mise à jour…';
  const result = await callApi('update_from_repo', null);
  if (result === 'ok') {
    await showModal('Mise à jour réussie', "L'app redémarre automatiquement.", [{label:'OK', cls:'btn-primary'}]);
    callApi('close', null);
  } else {
    await showModal('Erreur', String(result), [{label:'OK', cls:'btn-outline'}]);
    btn.disabled = false;
    btn.innerHTML = '<svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="5.5" y1="9" x2="5.5" y2="1"/><polyline points="2,4 5.5,1 9,4"/></svg> Mettre à jour';
  }
}

// Init après chargement — setTimeout garantit que le bridge webkit est prêt
window.addEventListener('load', () => setTimeout(async () => {
  const cfg = await callApi('get_config', null);
  populate(cfg);
  loadSummary();
}, 50));
</script>
</body>
</html>"""


# Références globales pour garder les objets ObjC en vie
_settings_refs = {"win": None, "wv": None, "handler": None, "delegate": None}


def open_settings_window():
    """Ouvre les paramètres via WKWebView natif dans le process principal (pas de Dock icon)."""
    # Si déjà ouverte, ramener au premier plan
    if _settings_refs["win"] is not None:
        try:
            _settings_refs["win"].makeKeyAndOrderFront_(None)
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            return
        except Exception:
            _settings_refs["win"] = None

    try:
        from AppKit import (
            NSWindow, NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
            NSWindowStyleMaskResizable, NSWindowStyleMaskMiniaturizable,
            NSBackingStoreBuffered, NSApplication,
        )
        from WebKit import WKWebView, WKWebViewConfiguration, WKUserContentController
        from Foundation import NSObject
        import objc
    except ImportError:
        # PyObjC absent (ne devrait pas arriver — installé avec rumps)
        return

    # ── Handler JS → Python ───────────────────────────────────────────────────

    class _Handler(NSObject):

        def userContentController_didReceiveScriptMessage_(self, ucc, msg):
            body = msg.body()
            # Convertir NSDictionary → dict Python si nécessaire
            try:
                body = {str(k): v for k, v in body.items()}
            except Exception:
                return
            action = str(body.get("action", ""))
            data   = body.get("data") or {}
            if not isinstance(data, dict):
                data = {}
            rid    = str(body.get("id", ""))
            result = None

            if action == "get_config":
                result = load_config()

            elif action == "save_settings":
                save_config(dict(data))
                result = "ok"

            elif action == "run_test":
                merged = {**load_config(), **dict(data)}
                threading.Thread(target=run_alarm, args=(merged, True), daemon=True).start()
                result = "ok"

            elif action == "get_summary":
                if SUMMARY_FILE.exists():
                    mtime = datetime.datetime.fromtimestamp(SUMMARY_FILE.stat().st_mtime)
                    result = {
                        "date": mtime.strftime("%d/%m à %H:%M"),
                        "text": SUMMARY_FILE.read_text().strip() or "(vide)",
                    }
                else:
                    result = {"date": None, "text": None}

            elif action == "uninstall":
                launch_agents = Path.home() / "Library" / "LaunchAgents"
                for plist in launch_agents.glob("com.fairforge.daily-briefing*.plist"):
                    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
                    plist.unlink(missing_ok=True)
                NSApplication.sharedApplication().terminate_(None)
                return

            elif action == "update_from_repo":
                import urllib.request
                RAW_URL = (
                    "https://raw.githubusercontent.com/"
                    "nohan-lebreton/daily-briefing/main/daily_briefing_app.py"
                )
                try:
                    with urllib.request.urlopen(RAW_URL, timeout=15) as r:
                        new_code = r.read()
                    APP_SCRIPT.write_bytes(new_code)
                    subprocess.Popen(
                        [sys.executable, str(APP_SCRIPT)],
                        start_new_session=True,
                    )
                    result = "ok"
                except Exception as e:
                    result = f"error:{e}"

            elif action == "close":
                wv = _settings_refs.get("wv")
                if wv:
                    try:
                        wv.configuration().userContentController().removeScriptMessageHandlerForName_("api")
                    except Exception:
                        pass
                win = _settings_refs.get("win")
                # Clear refs before close() so windowWillClose_ (called
                # synchronously inside close()) finds them already None.
                _settings_refs["win"]      = None
                _settings_refs["wv"]       = None
                _settings_refs["handler"]  = None
                _settings_refs["delegate"] = None
                if win:
                    win.close()
                return

            # Envoyer la réponse au JS — utiliser wv directement (pas win.contentView())
            js = f"window.__pyResp({json.dumps(result)}, '{rid}');"
            wv = _settings_refs["wv"]
            if wv:
                wv.evaluateJavaScript_completionHandler_(js, None)

    _Handler.userContentController_didReceiveScriptMessage_ = objc.selector(
        _Handler.userContentController_didReceiveScriptMessage_,
        signature=b"v@:@@",
    )

    # ── Delegate fenêtre (nettoyage à la fermeture) ───────────────────────────

    class _Delegate(NSObject):
        def windowWillClose_(self, _notif):
            # Remove message handler early; defer win/wv/delegate cleanup to
            # windowDidClose_ to avoid releasing the NSWindow while [close]
            # is still executing on self.
            wv = _settings_refs.get("wv")
            if wv:
                try:
                    wv.configuration().userContentController().removeScriptMessageHandlerForName_("api")
                except Exception:
                    pass
            _settings_refs["handler"] = None

        def windowDidClose_(self, _notif):
            _settings_refs["win"]      = None
            _settings_refs["wv"]       = None
            _settings_refs["delegate"] = None

    _Delegate.windowWillClose_ = objc.selector(
        _Delegate.windowWillClose_, signature=b"v@:@"
    )
    _Delegate.windowDidClose_ = objc.selector(
        _Delegate.windowDidClose_, signature=b"v@:@"
    )

    handler  = _Handler.alloc().init()
    delegate = _Delegate.alloc().init()
    _settings_refs["handler"]  = handler
    _settings_refs["delegate"] = delegate

    ucc = WKUserContentController.alloc().init()
    ucc.addScriptMessageHandler_name_(handler, "api")

    config = WKWebViewConfiguration.alloc().init()
    config.setUserContentController_(ucc)

    # ── Fenêtre ───────────────────────────────────────────────────────────────

    style = (
        NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
        NSWindowStyleMaskResizable | NSWindowStyleMaskMiniaturizable
    )
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        ((0, 0), (520, 720)), style, NSBackingStoreBuffered, False
    )
    win.setTitle_("Daily Briefing — Paramètres")
    win.setMinSize_((480, 600))
    win.setDelegate_(delegate)
    win.center()

    wv = WKWebView.alloc().initWithFrame_configuration_(
        ((0, 0), (520, 720)), config
    )
    win.setContentView_(wv)

    # Stocker wv AVANT de charger le HTML (le handler en a besoin dès le premier message)
    _settings_refs["win"] = win
    _settings_refs["wv"]  = wv

    wv.loadHTMLString_baseURL_(_build_settings_html(), None)

    win.makeKeyAndOrderFront_(None)
    NSApplication.sharedApplication().activateIgnoringOtherApps_(True)


# ─── App menubar ──────────────────────────────────────────────────────────────

def run_menubar_app():
    import rumps

    class DailyBriefingApp(rumps.App):
        def __init__(self):
            super().__init__("", icon=_get_icon_path(), template=True, quit_button=None)
            self.menu = [
                rumps.MenuItem("Paramètres…"),
                rumps.MenuItem("Tester maintenant"),
                None,
                rumps.MenuItem("Quitter", callback=rumps.quit_application),
            ]

        @rumps.clicked("Paramètres…")
        def open_settings(self, _):
            open_settings_window()

        @rumps.clicked("Tester maintenant")
        def test_now(self, _):
            cfg = load_config()
            threading.Thread(target=run_alarm, args=(cfg, True), daemon=True).start()

    DailyBriefingApp().run()


# ─── Point d'entrée ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--alarm" in sys.argv:
        run_alarm(load_config())
    else:
        run_menubar_app()
