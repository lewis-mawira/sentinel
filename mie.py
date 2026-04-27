import streamlit as st
import json
import requests
from bs4 import BeautifulSoup
from groq import Groq
import time
import xml.etree.ElementTree as ET
from datetime import datetime, date
import re
import base64
from pathlib import Path
import io

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Minet Kenya | Project Sentinel",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
#  THEME STATE & PERSISTENT SESSION KEYS
# ─────────────────────────────────────────────
# ── Theme toggle must be processed FIRST — before dark/colours are derived ──
# The toolbar iframe clicks a hidden st.button which sets this flag, then reruns.
if "pending_theme_toggle" not in st.session_state:
    st.session_state.pending_theme_toggle = False
if st.session_state.pending_theme_toggle:
    st.session_state.dark_mode = not st.session_state.get("dark_mode", True)
    st.session_state.pending_theme_toggle = False
    st.rerun()

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "relationship_graph" not in st.session_state:
    st.session_state.relationship_graph = {}
if "client_risk_scores" not in st.session_state:
    st.session_state.client_risk_scores = {}
if "closed_loop_tracker" not in st.session_state:
    st.session_state.closed_loop_tracker = []
if "renewal_calendar" not in st.session_state:
    st.session_state.renewal_calendar = []
if "feedback_log" not in st.session_state:
    st.session_state.feedback_log = []
# Persist last scan output so theme toggle rerun doesn't clear results
if "last_report_body" not in st.session_state:
    st.session_state.last_report_body = None
if "last_report_stats" not in st.session_state:
    st.session_state.last_report_stats = {}
if "last_signals" not in st.session_state:
    st.session_state.last_signals = []
if "last_scan_mode" not in st.session_state:
    st.session_state.last_scan_mode = None
if "last_competition_report" not in st.session_state:
    st.session_state.last_competition_report = None
if "last_sources_active" not in st.session_state:
    st.session_state.last_sources_active = 0
if "signal_archive" not in st.session_state:
    st.session_state.signal_archive = []  # list of saved scan result dicts

dark = st.session_state.dark_mode

# ─────────────────────────────────────────────
#  THEME COLOURS
# ─────────────────────────────────────────────
if dark:
    BG          = "#0D0F14"
    BG2         = "#111318"
    BORDER      = "#1E2330"
    BORDER2     = "#252B3B"
    TEXT        = "#E2E8F0"
    TEXT2       = "#9BA3B8"
    TEXT3       = "#6B7280"
    TEXT4       = "#4B5563"
    TEXT5       = "#2D3340"
    ACCENT      = "#0066FF"
    ACCENT2     = "#0052CC"
    TH_BG       = "#1A1E2A"
    TR_HOVER    = "#141720"
    SIDEBAR_BG  = "#111318"
    SIDEBAR_BORDER = "#1E2330"
else:
    BG          = "#F8FAFC"
    BG2         = "#FFFFFF"
    BORDER      = "#E2E8F0"
    BORDER2     = "#CBD5E1"
    TEXT        = "#0F172A"
    TEXT2       = "#334155"
    TEXT3       = "#64748B"
    TEXT4       = "#94A3B8"
    TEXT5       = "#CBD5E1"
    ACCENT      = "#0066FF"
    ACCENT2     = "#0052CC"
    TH_BG       = "#F1F5F9"
    TR_HOVER    = "#F8FAFC"
    SIDEBAR_BG  = "#FFFFFF"
    SIDEBAR_BORDER = "#E2E8F0"


def get_logo_b64():
    try:
        logo_path = Path("logo.png")
        if not logo_path.exists():
            logo_path = Path("/mnt/user-data/uploads/logo.png")
        if logo_path.exists():
            with open(logo_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except Exception:
        pass
    return None


def inject_styles():
    logo_b64 = get_logo_b64()
    logo_src = f"data:image/png;base64,{logo_b64}" if logo_b64 else ""

    # ── Signal tag light-mode fix: when light mode, use dark text on colored border
    signal_tag_light = "" if dark else """
    .signal-tag.active { background: #EFF6FF !important; color: #1D4ED8 !important; border-color: #3B82F6 !important; }
    """

    sidebar_text_explicit = f"""
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown div,
    section[data-testid="stSidebar"] .stMarkdown span,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stSlider label,
    section[data-testid="stSidebar"] .stCheckbox label,
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] p {{ color: {TEXT2} !important; }}
    section[data-testid="stSidebar"] .stSelectbox > div > div {{
        background: {BG2} !important; color: {TEXT} !important; border-color: {BORDER} !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox svg {{ fill: {TEXT2} !important; }}
    section[data-testid="stSidebar"] .stCheckbox span {{ color: {TEXT2} !important; }}
    """

    # Signal tags — in light mode override the dark colors per-signal using inline style,
    # this CSS just ensures the base tag is readable
    signal_tag_css = f"""
    .signal-tag {{
        display: inline-block;
        background: {BG2};
        border: 1px solid {BORDER2};
        color: {'#334155' if not dark else TEXT2};
        font-size: 10px;
        padding: 3px 8px;
        border-radius: 2px;
        margin: 2px;
        font-family: 'IBM Plex Mono', monospace;
        letter-spacing: 0.5px;
    }}
    .signal-tag.active {{
        background: {'#EFF6FF' if not dark else '#0D2A5E'};
        border-color: {'#3B82F6' if not dark else ACCENT};
        color: {'#1E40AF' if not dark else '#60A5FA'};
    }}
    """

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: 'IBM Plex Sans', sans-serif;
        background-color: {BG} !important;
        color: {TEXT} !important;
    }}
    .main {{ background-color: {BG}; color: {TEXT}; }}
    .stApp {{ background-color: {BG}; }}

    header[data-testid="stHeader"] {{
        background: transparent !important; height: 0px !important; display: none !important;
    }}

    /* ── Toolbar iframe fixed positioning handled by JS (sidebar-aware) ── */

    /* ── Always show Streamlit's native sidebar collapse/expand button ── */
    button[data-testid="stSidebarCollapsedControl"],
    button[data-testid="stBaseButton-headerNoPadding"] {{
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        position: fixed !important;
        top: 14px !important;
        left: 14px !important;
        z-index: 1100 !important;
        background: {BG2} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 4px !important;
        width: 32px !important;
        height: 32px !important;
        padding: 4px !important;
        cursor: pointer !important;
    }}
    button[data-testid="stSidebarCollapsedControl"] svg,
    button[data-testid="stBaseButton-headerNoPadding"] svg {{
        fill: {TEXT2} !important;
        width: 18px !important;
        height: 18px !important;
    }}

    section[data-testid="stSidebar"] {{
        background-color: {SIDEBAR_BG};
        border-right: 1px solid {SIDEBAR_BORDER};
    }}
    {sidebar_text_explicit}

    div[data-testid="stMetric"] {{
        background: {BG2}; border: 1px solid {BORDER};
        border-left: 3px solid {ACCENT}; padding: 16px 20px; border-radius: 4px;
    }}
    div[data-testid="stMetricLabel"] {{ font-size: 11px !important; letter-spacing: 1.5px; text-transform: uppercase; color: {TEXT3} !important; }}
    div[data-testid="stMetricValue"] {{ font-family: 'IBM Plex Mono', monospace !important; font-size: 26px !important; color: {TEXT} !important; }}

    /* All buttons default */
    .stButton > button {{
        background: {ACCENT}; color: #FFFFFF; border: none; border-radius: 3px;
        font-family: 'IBM Plex Mono', monospace; font-size: 12px; letter-spacing: 1px;
        text-transform: uppercase; height: 44px; width: 100%; transition: background 0.2s;
    }}
    .stButton > button:hover {{ background: {ACCENT2}; }}

    /* ENGINE START button — special car ignition style */
    .stButton [data-testid="baseButton-secondary"].engine-btn,
    button[kind="secondary"].engine-btn {{
        background: radial-gradient(circle at 40% 35%, #1a2a1a, #050a05) !important;
        border: 2px solid #22C55E !important;
        border-radius: 50% !important;
        width: 100px !important; height: 100px !important;
        box-shadow: 0 0 18px #22C55E55, inset 0 0 12px #22C55E22 !important;
        font-size: 10px !important; letter-spacing: 2px !important;
        color: #22C55E !important; font-family: IBM Plex Mono, monospace !important;
        transition: all 0.3s !important;
    }}

    h1 {{ font-size: 22px !important; font-weight: 600 !important; color: {TEXT} !important; letter-spacing: -0.5px; }}
    h2 {{ font-size: 14px !important; font-weight: 500 !important; color: {TEXT2} !important; letter-spacing: 1.5px; text-transform: uppercase; }}
    h3 {{ font-size: 13px !important; font-weight: 600 !important; color: {TEXT2} !important; }}

    details {{ background: {BG2} !important; border: 1px solid {BORDER} !important; border-radius: 4px; }}
    summary {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: {TEXT3} !important; }}

    .stMarkdown {{ color: {TEXT2} !important; }}
    .stMarkdown table {{ border-collapse: collapse; width: 100%; font-size: 12.5px; border: 1px solid {BORDER}; border-radius: 4px; overflow: hidden; }}
    .stMarkdown table th {{ background: {TH_BG}; color: {TEXT2}; font-weight: 600; letter-spacing: 0.8px; font-size: 10.5px; text-transform: uppercase; padding: 10px 12px; border-bottom: 2px solid {BORDER}; white-space: nowrap; }}
    .stMarkdown table td {{ padding: 9px 12px; border-bottom: 1px solid {BORDER}; color: {TEXT2}; vertical-align: top; line-height: 1.55; border-right: 1px solid {BORDER}; }}
    .stMarkdown table td:last-child {{ border-right: none; }}
    .stMarkdown table th:last-child {{ border-right: none; }}
    .stMarkdown table tr:last-child td {{ border-bottom: none; }}
    .stMarkdown table tr:hover td {{ background: {TR_HOVER}; }}
    .stMarkdown table tr:nth-child(even) td {{ background: {'#0F1218' if dark else '#F8FAFC'}; }}
    .stMarkdown table tr:nth-child(even):hover td {{ background: {TR_HOVER}; }}
    /* Source link in tables */
    .stMarkdown table td a {{ color: {ACCENT} !important; text-decoration: none; font-family: IBM Plex Mono, monospace; font-size: 11px; }}
    .stMarkdown table td a:hover {{ text-decoration: underline; }}

    .stAlert {{ background: {BG2} !important; border: 1px solid {BORDER} !important; color: {TEXT2} !important; border-radius: 4px; }}
    .stStatus {{ background: {BG2} !important; }}

    .stDownloadButton > button {{
        background: transparent !important; border: 1px solid {BORDER} !important;
        color: {TEXT2} !important; font-size: 12px !important;
        font-family: 'IBM Plex Mono', monospace !important; letter-spacing: 1px;
    }}
    .stDownloadButton > button:hover {{ border-color: {ACCENT} !important; color: {TEXT} !important; }}

    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }}
    }}
    .pulse-dot {{
        display: inline-block; width: 8px; height: 8px;
        background: #22C55E; border-radius: 50%;
        animation: pulse 2s infinite; margin-right: 6px;
    }}

    .urgency-high {{ color: #F87171 !important; font-weight: 600; }}
    .urgency-medium {{ color: #FBBF24 !important; }}
    .urgency-low {{ color: #34D399 !important; }}

    {signal_tag_css}

    .sentinel-toolbar {{
        background: {'#0A0C11' if dark else '#FFFFFF'};
        border-bottom: 1px solid {BORDER};
        padding: 0 24px; height: 80px;
        display: flex; align-items: center; justify-content: space-between;
        box-shadow: {'0 2px 20px #00000070' if dark else '0 1px 12px #0000001A'};
    }}
    .toolbar-left {{ display: flex; align-items: center; gap: 14px; }}
    .toolbar-right {{ display: flex; align-items: center; gap: 18px; }}
    .toolbar-divider {{ width: 1px; height: 24px; background: {BORDER}; }}
    .toolbar-brand {{ font-family: 'IBM Plex Mono', monospace; font-size: 10px; letter-spacing: 2px; color: {TEXT4}; text-transform: uppercase; }}
    .toolbar-live {{ font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #22C55E; letter-spacing: 1.5px; display: flex; align-items: center; }}
    .toolbar-clock-el {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: {TEXT2}; letter-spacing: 1px; white-space: nowrap; }}

    .intel-card {{
        background: {BG2}; border: 1px solid {BORDER};
        border-left: 3px solid {ACCENT}; padding: 14px 16px;
        border-radius: 4px; margin-bottom: 12px;
    }}
    .why-matters-card {{
        background: {'#0D1F0E' if dark else '#F0FDF4'};
        border: 1px solid {'#1A3A1C' if dark else '#BBF7D0'};
        border-left: 3px solid #22C55E; padding: 12px 16px;
        border-radius: 4px; margin-top: 8px;
    }}
    .competition-card {{
        background: {'#1A0D1A' if dark else '#FDF4FF'};
        border: 1px solid {'#3A103A' if dark else '#E9D5FF'};
        border-left: 3px solid #A78BFA; padding: 12px 16px;
        border-radius: 4px; margin-bottom: 8px;
    }}
    .sector-layer {{
        background: {BG2}; border: 1px solid {BORDER};
        padding: 8px 14px; border-radius: 3px; margin: 16px 0 8px 0;
        font-family: 'IBM Plex Mono', monospace; font-size: 11px;
        letter-spacing: 2px; color: {TEXT3}; text-transform: uppercase;
    }}
    .risk-badge-high {{ background: #7F1D1D; color: #FCA5A5; padding: 2px 8px; border-radius: 2px; font-size: 11px; font-family: IBM Plex Mono, monospace; }}
    .risk-badge-med  {{ background: #78350F; color: #FDE68A; padding: 2px 8px; border-radius: 2px; font-size: 11px; font-family: IBM Plex Mono, monospace; }}
    .risk-badge-low  {{ background: #064E3B; color: #6EE7B7; padding: 2px 8px; border-radius: 2px; font-size: 11px; font-family: IBM Plex Mono, monospace; }}
    .rel-table {{ width: 100%; border-collapse: collapse; font-size: 12px; font-family: IBM Plex Mono, monospace; }}
    .rel-table th {{ background: {TH_BG}; color: {TEXT3}; padding: 6px 10px; border-bottom: 1px solid {BORDER}; font-size: 10px; letter-spacing: 1px; }}
    .rel-table td {{ padding: 6px 10px; border-bottom: 1px solid {BORDER}; color: {TEXT2}; }}
    .stTextInput > div > div > input, .stSelectbox > div > div, .stTextArea > div > div > textarea {{
        background: {BG2} !important; border-color: {BORDER} !important; color: {TEXT} !important;
    }}
    .cl-open   {{ border-left: 3px solid #F59E0B; }}
    .cl-closed {{ border-left: 3px solid #22C55E; }}
    .cl-card   {{ background: {BG2}; border: 1px solid {BORDER}; padding: 10px 14px; border-radius: 3px; margin-bottom: 6px; }}
    </style>
    """, unsafe_allow_html=True)

    # ── Toolbar rendered via st.components so SVG/JS executes properly ──
    import streamlit.components.v1 as components
    logo_img_html = (f"<img src='{logo_src}' style='height:46px;object-fit:contain;display:block;' />"
                     if logo_src else
                     "<span style='font-size:20px;font-weight:700;color:#CC0000;font-family:IBM Plex Mono,monospace;'>MINET</span>")
    theme_icon    = "☀" if dark else "🌙"
    theme_tooltip = "Switch to Light Mode" if dark else "Switch to Dark Mode"
    toolbar_bg    = "#0A0C11" if dark else "#FFFFFF"
    border_c      = BORDER
    text2_c       = TEXT2
    text3_c       = TEXT3
    text4_c       = TEXT4
    accent_c      = ACCENT

    toolbar_component = f"""<!DOCTYPE html>
<html><head>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=IBM+Plex+Mono:wght@400;600&family=Space+Grotesk:wght@400;600&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:{toolbar_bg}; overflow:hidden; }}
  .bar {{
    background:{toolbar_bg}; border-bottom:1px solid {border_c};
    height:78px; display:flex; align-items:center;
    justify-content:space-between; padding:0 28px;
    box-shadow:{'0 2px 20px #00000070' if dark else '0 1px 12px #0000001A'};
  }}
  .left {{ display:flex; align-items:center; gap:20px; flex:1; }}
  .center {{ display:flex; flex-direction:column; align-items:center;
             justify-content:center; flex:1; gap:3px; }}
  .right {{ display:flex; align-items:center; gap:18px; flex:1; justify-content:flex-end; }}
  .divider {{ width:1px; height:32px; background:{border_c}; opacity:0.6; }}
  .brand-title {{
    font-family:'Space Grotesk',sans-serif; font-size:12px; font-weight:600;
    letter-spacing:3px; color:{text2_c}; text-transform:uppercase; white-space:nowrap;
  }}
  .brand-sub {{
    font-family:'IBM Plex Mono',monospace; font-size:8.5px;
    letter-spacing:2.5px; color:{text4_c}; text-transform:uppercase;
  }}
  .live {{ font-family:'IBM Plex Mono',monospace; font-size:10px; color:#22C55E;
           letter-spacing:2px; display:flex; align-items:center; gap:7px; }}
  .dot {{ width:7px; height:7px; background:#22C55E; border-radius:50%;
          animation:blink 2s infinite; display:inline-block; }}
  @keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:0.2}} }}
  .clock-wrap {{ display:flex; flex-direction:column; align-items:flex-end; gap:2px; }}
  .clock-date {{
    font-family:'Orbitron',monospace; font-size:10px; font-weight:500;
    color:{text3_c}; letter-spacing:2px; white-space:nowrap;
  }}
  .clock-time {{
    font-family:'Orbitron',monospace; font-size:16px; font-weight:700;
    color:{text2_c}; letter-spacing:3px; white-space:nowrap;
  }}
  .clock-eat {{
    font-family:'IBM Plex Mono',monospace; font-size:8px;
    color:{accent_c}; letter-spacing:2px;
  }}
  .toggle {{
    width:34px; height:34px; border-radius:50%;
    border:1px solid {border_c}; background:transparent;
    cursor:pointer; font-size:17px; display:flex; align-items:center;
    justify-content:center; transition:border-color 0.2s, background 0.2s;
    color:{text2_c}; flex-shrink:0;
  }}
  .toggle:hover {{ border-color:{accent_c}; background:{'#0D1A2E' if dark else '#EFF6FF'}; }}
</style>
</head><body>
<div class="bar">
  <div class="left">
    {logo_img_html}
    <div class="divider"></div>
  </div>
  <div class="center">
    <div class="brand-title">PROJECT SENTINEL &nbsp;·&nbsp; CREATED BY CIA MINET</div>
    <div class="brand-sub">CORPORATE INTELLIGENCE ANALYTICS &nbsp;·&nbsp; MINET KENYA</div>
  </div>
  <div class="right">
    <div class="divider"></div>
    <div class="live"><div class="dot"></div>LIVE</div>
    <div class="clock-wrap">
      <div class="clock-date" id="clk-date">--- -- --- ----</div>
      <div class="clock-time" id="clk-time">--:--:--</div>
      <div class="clock-eat">EAT · UTC+3</div>
    </div>
    <div class="toggle" id="thm" title="{theme_tooltip}">{theme_icon}</div>
  </div>
</div>
<script>
function tick() {{
  var now = new Date();
  var eat = new Date(now.getTime() + 3*3600*1000);
  var days  = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  var months= ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  var p = function(n){{ return String(n).padStart(2,'0'); }};
  document.getElementById('clk-date').textContent =
    days[eat.getUTCDay()] + '  ' + p(eat.getUTCDate()) + '  ' + months[eat.getUTCMonth()] + '  ' + eat.getUTCFullYear();
  document.getElementById('clk-time').textContent =
    p(eat.getUTCHours()) + ':' + p(eat.getUTCMinutes()) + ':' + p(eat.getUTCSeconds());
}}
tick();
setInterval(tick, 1000);

document.getElementById('thm').addEventListener('click', function() {{
  var btns = window.parent.document.querySelectorAll('button');
  for (var i = 0; i < btns.length; i++) {{
    if (btns[i].textContent.trim() === '\u25d1 THEME') {{
      btns[i].click();
      break;
    }}
  }}
}});
</script>
</body></html>"""

    components.html(toolbar_component, height=80, scrolling=False)


inject_styles()

# ── Hidden theme-toggle button — visually buried via JS, clicked by toolbar iframe ──
# Render button first so Streamlit registers it, then JS buries its container off-screen.
if st.button("\u25d1 THEME", key="theme_toggle_hidden"):
    st.session_state.pending_theme_toggle = True
    st.rerun()
import streamlit.components.v1 as components
components.html("""<script>
(function() {
  // ── Hide the theme button ──
  function hideThemeBtn() {
    var btns = window.parent.document.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].textContent.trim() === '\u25d1 THEME') {
        var el = btns[i];
        el.style.cssText = 'position:fixed!important;top:-9999px!important;width:0!important;height:0!important;opacity:0!important;pointer-events:none!important;';
        var p = el.parentElement;
        while (p && p.getAttribute('data-testid') !== 'element-container') { p = p.parentElement; }
        if (p) p.style.cssText = 'position:fixed!important;top:-9999px!important;width:0!important;height:0!important;overflow:hidden!important;';
        return;
      }
    }
    setTimeout(hideThemeBtn, 60);
  }
  hideThemeBtn();

  // ── Pin the toolbar iframe to top of viewport, respecting sidebar ──
  function pinToolbar() {
    var doc = window.parent.document;
    var iframes = doc.querySelectorAll('iframe');
    for (var i = 0; i < iframes.length; i++) {
      var f = iframes[i];
      if (f.offsetHeight > 40 && f.offsetHeight < 90 && f.getBoundingClientRect().top < 120) {
        function applyPin() {
          var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
          var sidebarW = (sidebar && sidebar.offsetWidth > 0) ? sidebar.offsetWidth : 0;
          f.style.cssText =
            'position:fixed!important;top:0!important;' +
            'left:' + sidebarW + 'px!important;' +
            'width:calc(100vw - ' + sidebarW + 'px)!important;' +
            'height:82px!important;' +
            'z-index:1050!important;border:none!important;';
          var bc = doc.querySelector('.block-container');
          if (bc && parseInt(getComputedStyle(bc).paddingTop) < 80) {
            bc.style.paddingTop = '88px';
          }
        }
        applyPin();
        // Re-apply when sidebar resizes (collapse/expand)
        var ro = new ResizeObserver(applyPin);
        var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
        if (sidebar) ro.observe(sidebar);
        // Also poll briefly to catch late sidebar renders
        var polls = 0;
        var poller = setInterval(function() {
          applyPin();
          if (++polls > 10) clearInterval(poller);
        }, 300);
        return;
      }
    }
    setTimeout(pinToolbar, 100);
  }
  pinToolbar();

  // ── Ensure sidebar toggle button is always visible ──
  // Streamlit hides it when the custom header is hidden; we re-surface it.
  function ensureSidebarToggle() {
    var doc = window.parent.document;
    // Try to find the native collapsed-control button (shows when sidebar is hidden)
    var native = doc.querySelector('button[data-testid="stSidebarCollapsedControl"]');
    if (native) {
      native.style.cssText = 'display:flex!important;visibility:visible!important;opacity:1!important;' +
        'position:fixed!important;top:14px!important;left:14px!important;z-index:1100!important;' +
        'width:32px!important;height:32px!important;cursor:pointer!important;';
      return; // found and fixed — no need for custom button
    }
    // If no custom toggle yet, inject one
    if (!doc.getElementById('sentinel-sidebar-toggle')) {
      var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
      var btn = doc.createElement('button');
      btn.id = 'sentinel-sidebar-toggle';
      btn.title = 'Toggle sidebar';
      btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>';
      btn.style.cssText =
        'position:fixed;top:14px;left:14px;z-index:1100;' +
        'width:32px;height:32px;border-radius:4px;border:1px solid #1E2330;' +
        'background:#111318;color:#9BA3B8;cursor:pointer;display:flex;' +
        'align-items:center;justify-content:center;padding:4px;';
      btn.onmouseenter = function(){ this.style.borderColor='#0066FF'; };
      btn.onmouseleave = function(){ this.style.borderColor='#1E2330'; };
      btn.onclick = function() {
        // Click Streamlit's own sidebar toggle (the expand button inside sidebar header)
        var sidebarBtn = doc.querySelector('button[data-testid="stBaseButton-headerNoPadding"]');
        if (!sidebarBtn) sidebarBtn = doc.querySelector('[data-testid="stSidebar"] button');
        if (sidebarBtn) { sidebarBtn.click(); return; }
        // Last resort: toggle sidebar visibility directly
        if (sidebar) {
          var hidden = sidebar.style.display === 'none' || getComputedStyle(sidebar).display === 'none';
          sidebar.style.display = hidden ? '' : 'none';
        }
      };
      doc.body.appendChild(btn);
    }
    setTimeout(ensureSidebarToggle, 800);
  }
  setTimeout(ensureSidebarToggle, 400);
})();
</script>""", height=0, scrolling=False)

# ─────────────────────────────────────────────
#  SIGNAL TAXONOMY — EXPANDED
# ─────────────────────────────────────────────

SIGNAL_TYPES = {
    # ── GROWTH ──
    "EXPANSION":                {"color": "#34D399", "icon": "↗", "urgency": "HIGH",   "sector": "GROWTH"},
    "HIRING_SURGE":             {"color": "#2DD4BF", "icon": "↑", "urgency": "MEDIUM", "sector": "GROWTH"},
    "NEW_PRODUCT":              {"color": "#818CF8", "icon": "★", "urgency": "MEDIUM", "sector": "GROWTH"},
    "NEW_MARKET_ENTRY":         {"color": "#6EE7B7", "icon": "⊛", "urgency": "HIGH",   "sector": "GROWTH"},
    "CAPITAL_RAISE":            {"color": "#4ADE80", "icon": "⬆", "urgency": "HIGH",   "sector": "GROWTH"},
    # ── CORPORATE ACTION ──
    "ACQUISITION":              {"color": "#60A5FA", "icon": "⊕", "urgency": "HIGH",   "sector": "CORPORATE ACTION"},
    "MERGER":                   {"color": "#38BDF8", "icon": "⊗", "urgency": "HIGH",   "sector": "CORPORATE ACTION"},
    "RESTRUCTURING":            {"color": "#FBBF24", "icon": "⟳", "urgency": "MEDIUM", "sector": "CORPORATE ACTION"},
    "SUBSIDIARY":               {"color": "#F472B6", "icon": "◈", "urgency": "LOW",    "sector": "CORPORATE ACTION"},
    "DIVESTITURE":              {"color": "#FDA4AF", "icon": "⊖", "urgency": "MEDIUM", "sector": "CORPORATE ACTION"},
    "IPO_LISTING":              {"color": "#7DD3FC", "icon": "⬡", "urgency": "HIGH",   "sector": "CORPORATE ACTION"},
    "SPIN_OFF":                 {"color": "#C4B5FD", "icon": "⊘", "urgency": "MEDIUM", "sector": "CORPORATE ACTION"},
    # ── WORKFORCE ──
    "LAYOFFS":                  {"color": "#F87171", "icon": "↓", "urgency": "HIGH",   "sector": "WORKFORCE"},
    "LABOR_LIABILITY":          {"color": "#FCA5A5", "icon": "⚖", "urgency": "HIGH",   "sector": "WORKFORCE"},
    "STRIKE_INDUSTRIAL_ACTION": {"color": "#FB7185", "icon": "✕", "urgency": "HIGH",   "sector": "WORKFORCE"},
    "MASS_CASUALTY_ACCIDENT":   {"color": "#FF6B6B", "icon": "⚠", "urgency": "HIGH",   "sector": "WORKFORCE"},
    # ── GOVERNANCE ──
    "LEADERSHIP_CHANGE":        {"color": "#A78BFA", "icon": "⊘", "urgency": "MEDIUM", "sector": "GOVERNANCE"},
    "BOARD_CHANGE":             {"color": "#C4B5FD", "icon": "◉", "urgency": "MEDIUM", "sector": "GOVERNANCE"},
    "FRAUD_SCANDAL":            {"color": "#F43F5E", "icon": "⚑", "urgency": "HIGH",   "sector": "GOVERNANCE"},
    "OWNERSHIP_CHANGE":         {"color": "#E879F9", "icon": "⇄", "urgency": "HIGH",   "sector": "GOVERNANCE"},
    # ── FINANCIAL ──
    "FINANCIAL_DISTRESS":       {"color": "#FB923C", "icon": "⚑", "urgency": "HIGH",   "sector": "FINANCIAL"},
    "CREDIT_DOWNGRADE":         {"color": "#F97316", "icon": "↘", "urgency": "HIGH",   "sector": "FINANCIAL"},
    "DEBT_RESTRUCTURING":       {"color": "#FDBA74", "icon": "⟳", "urgency": "HIGH",   "sector": "FINANCIAL"},
    "PROFIT_WARNING":           {"color": "#FCD34D", "icon": "⚠", "urgency": "HIGH",   "sector": "FINANCIAL"},
    "RECEIVERSHIP_LIQUIDATION": {"color": "#FF4500", "icon": "✕", "urgency": "HIGH",   "sector": "FINANCIAL"},
    # ── ECOSYSTEM ──
    "PARTNERSHIP":              {"color": "#4ADE80", "icon": "⇔", "urgency": "MEDIUM", "sector": "ECOSYSTEM"},
    "JOINT_VENTURE":            {"color": "#86EFAC", "icon": "⊞", "urgency": "MEDIUM", "sector": "ECOSYSTEM"},
    "SUPPLY_CHAIN_DISRUPTION":  {"color": "#FDE68A", "icon": "⚡", "urgency": "HIGH",   "sector": "ECOSYSTEM"},
    "FRANCHISE_DISTRIBUTION":   {"color": "#BBF7D0", "icon": "⊟", "urgency": "LOW",    "sector": "ECOSYSTEM"},
    # ── REGULATORY ──
    "REGULATORY_NON_COMPLIANCE":{"color": "#EF4444", "icon": "⊗", "urgency": "HIGH",   "sector": "REGULATORY"},
    "REGULATORY_APPROVAL":      {"color": "#34D399", "icon": "✓", "urgency": "MEDIUM", "sector": "REGULATORY"},
    "COURT_JUDGMENT":           {"color": "#F87171", "icon": "⚖", "urgency": "HIGH",   "sector": "REGULATORY"},
    "LICENCE_REVOCATION":       {"color": "#DC2626", "icon": "✕", "urgency": "HIGH",   "sector": "REGULATORY"},
    # ── ESG ──
    "CLIMATE_ESG":              {"color": "#86EFAC", "icon": "♻", "urgency": "MEDIUM", "sector": "ESG"},
    "ENVIRONMENTAL_INCIDENT":   {"color": "#4ADE80", "icon": "⚠", "urgency": "HIGH",   "sector": "ESG"},
    "SUSTAINABILITY_COMMITMENT":{"color": "#BBF7D0", "icon": "♻", "urgency": "LOW",    "sector": "ESG"},
    "SOCIAL_IMPACT_PROGRAMME":  {"color": "#6EE7B7", "icon": "⊛", "urgency": "LOW",    "sector": "ESG"},
    # ── PROCUREMENT ──
    "TENDER_AWARD":             {"color": "#FCD34D", "icon": "🏆","urgency": "MEDIUM", "sector": "PROCUREMENT"},
    "GOVERNMENT_CONTRACT":      {"color": "#FDE68A", "icon": "◈", "urgency": "HIGH",   "sector": "PROCUREMENT"},
    "INFRASTRUCTURE_PROJECT":   {"color": "#F59E0B", "icon": "⊞", "urgency": "HIGH",   "sector": "PROCUREMENT"},
    # ── ASSET & PROPERTY ──
    "PROPERTY_ACQUISITION":     {"color": "#67E8F9", "icon": "⌂", "urgency": "HIGH",   "sector": "ASSET"},
    "FLEET_EXPANSION":          {"color": "#22D3EE", "icon": "⊛", "urgency": "MEDIUM", "sector": "ASSET"},
    "CONSTRUCTION_PROJECT":     {"color": "#06B6D4", "icon": "⊞", "urgency": "HIGH",   "sector": "ASSET"},
    "ASSET_DISPOSAL":           {"color": "#A5F3FC", "icon": "⊖", "urgency": "MEDIUM", "sector": "ASSET"},
    # ── TECHNOLOGY ──
    "DIGITAL_TRANSFORMATION":   {"color": "#818CF8", "icon": "⊛", "urgency": "MEDIUM", "sector": "TECHNOLOGY"},
    "CYBER_INCIDENT":           {"color": "#6366F1", "icon": "⚡", "urgency": "HIGH",   "sector": "TECHNOLOGY"},
    "TECH_INVESTMENT":          {"color": "#A5B4FC", "icon": "★", "urgency": "MEDIUM", "sector": "TECHNOLOGY"},
}

SECTOR_LAYERS = {
    "GROWTH":           [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "GROWTH"],
    "CORPORATE ACTION": [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "CORPORATE ACTION"],
    "WORKFORCE":        [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "WORKFORCE"],
    "GOVERNANCE":       [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "GOVERNANCE"],
    "FINANCIAL":        [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "FINANCIAL"],
    "ECOSYSTEM":        [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "ECOSYSTEM"],
    "REGULATORY":       [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "REGULATORY"],
    "ESG":              [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "ESG"],
    "PROCUREMENT":      [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "PROCUREMENT"],
    "ASSET":            [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "ASSET"],
    "TECHNOLOGY":       [s for s, m in SIGNAL_TYPES.items() if m["sector"] == "TECHNOLOGY"],
}


# ─────────────────────────────────────────────
#  RSS FEED REGISTRY — EXPANDED WITH NEW SOURCES
# ─────────────────────────────────────────────

RSS_FEEDS = [
    # Kenya — Tier 1
    {"url": "https://www.businessdailyafrica.com/rss/bd/corporate-news/539550", "region": "KE", "tier": 1, "type": "news"},
    {"url": "https://kenyanwallstreet.com/feed/",                               "region": "KE", "tier": 1, "type": "news"},
    {"url": "https://www.capitalfm.co.ke/business/feed/",                       "region": "KE", "tier": 1, "type": "news"},
    {"url": "https://www.standardmedia.co.ke/rss/business.php",                "region": "KE", "tier": 1, "type": "news"},
    # Kenya — Tier 2
    {"url": "https://www.the-star.co.ke/rss/business/",                        "region": "KE", "tier": 2, "type": "news"},
    {"url": "https://www.kbc.co.ke/category/business/feed/",                   "region": "KE", "tier": 2, "type": "news"},
    {"url": "https://www.pd.co.ke/category/business/feed/",                    "region": "KE", "tier": 2, "type": "news"},
    # East Africa
    {"url": "https://www.theeastafrican.co.ke/service/rss/view/teafric/2522/rss.xml", "region": "EA", "tier": 1, "type": "news"},
    {"url": "https://www.monitor.co.ug/rss/business",                          "region": "EA", "tier": 2, "type": "news"},
    {"url": "https://www.thecitizen.co.tz/rss/business",                       "region": "EA", "tier": 2, "type": "news"},
    # Africa-wide
    {"url": "https://www.cnbcafrica.com/feed/",                                "region": "AF", "tier": 1, "type": "news"},
    {"url": "https://www.businessinsider.co.za/rss/",                          "region": "AF", "tier": 2, "type": "news"},
    # International — Tier 1 (Africa/EM focused)
    {"url": "https://www.reuters.com/rssFeed/businessNews",                    "region": "AF", "tier": 1, "type": "news"},
    {"url": "https://feeds.bloomberg.com/markets/news.rss",                    "region": "AF", "tier": 1, "type": "news"},
    # Regulatory / Official Sources
    {"url": "https://www.ira.go.ke/index.php/news/press-releases?format=feed&type=rss", "region": "KE", "tier": 1, "type": "regulator"},
    {"url": "https://www.cma.or.ke/index.php/news-and-events/press-releases?format=feed&type=rss", "region": "KE", "tier": 1, "type": "regulator"},
    # NSE Company Announcements
    {"url": "https://www.nse.co.ke/news-and-resources/market-announcements/?format=feed", "region": "KE", "tier": 1, "type": "announcement"},
]

# ── Keywords that indicate a signal is relevant to insurance / risk / corporate events ──
RELEVANCE_KEYWORDS = [
    # ── Corporate actions
    "expand", "expansion", "acqui", "merger", "takeover", "restructur", "layoff", "retrench",
    "redundan", "leadership", "appoint", "resign", "ceo", "cfo", "coo", "cto", "director",
    "board", "chairman", "subsidiay", "subsidiary", "joint venture", "partnership", "contract",
    "tender", "award", "bid", "procure", "spin-off", "spinoff", "divestiture", "divest",
    "carve-out", "merger", "demerger", "amalgamat", "consolidat", "absorbed", "taken over",
    "bought out", "management buyout", "mbo", "private equity", "ipo", "initial public offer",
    "listing", "delisting", "rights issue", "share buyback", "recapitalis",
    # ── Financial signals
    "profit", "loss", "revenue", "turnover", "debt", "loan", "fund", "invest", "capital",
    "listed", "nse", "bond", "rating", "downgrad", "upgrad", "bankrupt", "receivership",
    "liquidat", "distress", "default", "credit facilit", "overdraft", "non-performing",
    "npl", "bad debt", "write-off", "impairment", "rights issue", "equity raise",
    "vc funding", "series a", "series b", "seed funding", "grant", "subsidy",
    "profit warning", "earnings", "dividend", "interim results", "annual results",
    "quarterly results", "auditor", "audit", "financial statement",
    # ── Workforce & people
    "hire", "hiring", "recruit", "staff", "employee", "workforce", "headcount", "job",
    "talent", "retrench", "redundan", "severance", "pension", "gratuity", "benefits",
    "medical scheme", "group life", "retirement", "strike", "industrial action",
    "work stoppage", "go-slow", "union", "collective bargain", "occupational",
    "workplace injur", "fatality", "accident at work", "compensation",
    # ── Regulatory, legal & compliance
    "regulat", "compliance", "penalt", "fine", "court", "lawsuit", "litigation",
    "arbitration", "tribunal", "criminal charge", "investigated", "prosecut",
    "ira", "cma", "kra", "nema", "rba", "ppra", "eac", "competition authority",
    "sanction", "licence", "revok", "suspend", "deregist", "tax evasion", "anti-money",
    "aml", "kyc", "data breach", "data protection", "gdpr", "odpc",
    # ── ESG & environment
    "esg", "environment", "climate", "emission", "sustainab", "carbon", "net zero",
    "renewable", "solar", "wind energy", "green", "waste management", "pollution",
    "environmental impact", "biodiversity", "social impact", "community",
    "corporate social responsibility", "csr", "human rights",
    # ── Insurance, risk & financial services
    "insurance", "insurer", "underwrite", "reinsur", "broker", "risk", "cover",
    "policy", "claim", "liabilit", "property", "asset", "fleet", "cargo", "marine",
    "aviation", "medical", "health", "life cover", "indemnit", "premium",
    "actuar", "loss ratio", "combined ratio", "retention", "facultative", "treaty",
    "professional indemnit", "directors liability", "cyber", "fidelit",
    "trade credit", "political risk", "product liabilit", "public liabilit",
    "employers liabilit", "workmen compensation", "group medical", "group life",
    # ── Growth & physical assets
    "new office", "new branch", "open", "launch", "plant", "factory", "project",
    "infrastr", "construction", "development", "real estate", "warehouse", "depot",
    "port", "terminal", "pipeline", "power plant", "dam", "road", "railway",
    "hospital", "clinic", "school", "university", "hotel", "mall", "retail",
    "data centre", "fibre", "tower", "mast", "facility",
    # ── Sector-specific Kenya/EA triggers
    "safaricom", "mpesa", "nse", "nssf", "nhif", "kplc", "kengen", "kebs",
    "nema", "kaa", "kpa", "sgr", "lapsset", "vision 2030", "big four",
    "affordable housing", "food security", "universal health", "manufacturing",
    "agribusiness", "horticulture", "floriculture", "tea", "coffee", "soya",
    "fertiliser", "agrichemical", "mining", "oil", "gas", "geothermal",
    "fintech", "mobile money", "digital lending", "saccos", "microfinance",
    "ngo", "multilateral", "development bank", "world bank", "ifc", "afdb",
]

SOURCE_TYPE_LABELS = {
    "news":         ("📰", "#60A5FA"),
    "regulator":    ("⚖️", "#F87171"),
    "announcement": ("📢", "#FBBF24"),
}


def is_relevant_signal(title: str, content: str) -> bool:
    """Return True if article contains at least one insurance/corporate relevance keyword."""
    text = (title + " " + content[:600]).lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


# ─────────────────────────────────────────────
#  DATA LOADING
# ─────────────────────────────────────────────

def _normalize_client_name(n):
    """Normalize client name to consistent title-case, preserving short acronyms."""
    import re as _re
    ACRONYMS = {
        'LTD','LIMITED','PLC','CO','LLC','INC','KE','EA','IMB','SACCO',
        'NSE','CBK','KPC','GIZ','FHI','TNC','ACT','SGS','IHL','CHRM',
        'KVM','PASS','MESPT','AGRA','NSSF','CIC','USD','CRBC','CEEC',
        'SMEC','DR','US','UK','CIA','ESG','ALP','BOC','SGA','SNDBX',
        'BM','ALH','WOW','QED','JHPIEGO','IOM','UNON','RUIRU',
    }
    words = n.split()
    result = []
    for w in words:
        clean = _re.sub(r'[().,&\-]', '', w)
        if clean.upper() in ACRONYMS or (len(clean) <= 4 and clean.isupper() and clean.isalpha()):
            result.append(clean.upper())
        else:
            result.append(w.title())
    return ' '.join(result)


def load_clients():
    try:
        with open('minet_clients.json', 'r') as f:
            data = json.load(f)
            names = [_normalize_client_name(c['name']) for c in data['clients']
                     if c['name'].lower() not in ['various', '']]
            return sorted(set(names))
    except Exception:
        st.sidebar.warning("minet_clients.json not found — using demo list.", icon="⚠")
        return [
            "Safaricom", "KCB Group", "Equity Bank", "EABL",
            "Bamburi Cement", "Kenya Airways", "Central Bank of Kenya",
            "Nation Media Group", "Unga Limited", "BAT Kenya",
            "Law Society of Kenya", "Quickmart", "Trademark Africa",
            "Wananchi Group Kenya", "Bolt Support Kenya Ltd"
        ]


# ─────────────────────────────────────────────
#  INGESTION ENGINE
# ─────────────────────────────────────────────

def harvest_signals(tier_filter=None, max_per_feed=3, source_types=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*'
    }
    signals = []
    feeds_attempted = 0
    feeds_successful = 0

    feeds_to_use = RSS_FEEDS
    if tier_filter:
        feeds_to_use = [f for f in feeds_to_use if f["tier"] <= tier_filter]
    if source_types:
        feeds_to_use = [f for f in feeds_to_use if f.get("type", "news") in source_types]

    for feed in feeds_to_use:
        feeds_attempted += 1
        try:
            response = requests.get(feed["url"], headers=headers, timeout=8)
            response.raise_for_status()
            content = response.content.decode('utf-8', errors='ignore')
            root = ET.fromstring(content)
            items = root.findall('.//item')
            feed_success = False

            for item in items[:max_per_feed]:
                try:
                    title_el   = item.find('title')
                    link_el    = item.find('link')
                    pubdate_el = item.find('pubDate')
                    if title_el is None or link_el is None:
                        continue
                    title    = title_el.text or ""
                    link     = link_el.text or ""
                    pub_date = pubdate_el.text if pubdate_el is not None else "Unknown"
                    try:
                        art_res  = requests.get(link, headers=headers, timeout=7)
                        art_soup = BeautifulSoup(art_res.text, 'html.parser')
                        for tag in art_soup(["script", "style", "nav", "footer", "aside", "form"]):
                            tag.decompose()
                        paragraphs = art_soup.find_all('p')
                        body_text  = " ".join([
                            p.get_text(strip=True) for p in paragraphs
                            if len(p.get_text(strip=True)) > 50
                        ])
                        if len(body_text) < 100:
                            continue
                        # ── Relevance pre-filter — drop noise before LLM ──
                        if not is_relevant_signal(title, body_text):
                            continue
                        signals.append({
                            "title":    title.strip(),
                            "content":  body_text[:2000],
                            "url":      link,
                            "pub_date": pub_date,
                            "source":   feed["url"].split('/')[2],
                            "source_url": link,
                            "region":   feed["region"],
                            "tier":     feed["tier"],
                            "source_type": feed.get("type", "news"),
                        })
                        feed_success = True
                        time.sleep(0.25)
                    except Exception:
                        signals.append({
                            "title":    title.strip(),
                            "content":  title.strip(),
                            "url":      link,
                            "pub_date": pub_date,
                            "source":   feed["url"].split('/')[2],
                            "source_url": link,
                            "region":   feed["region"],
                            "tier":     feed["tier"],
                            "source_type": feed.get("type", "news"),
                        })
                        feed_success = True
                except Exception:
                    continue
            if feed_success:
                feeds_successful += 1
        except Exception:
            continue

    return signals, feeds_attempted, feeds_successful


# ─────────────────────────────────────────────
#  REGEX TABLE EXTRACTOR
# ─────────────────────────────────────────────

def extract_table_rows(markdown_text):
    """Extract rows from a markdown table using regex."""
    rows = []
    pattern = re.compile(r'^\|(.+)\|$', re.MULTILINE)
    for match in pattern.finditer(markdown_text):
        cells = [c.strip() for c in match.group(1).split('|')]
        # Skip separator rows like |:---|:---|
        if all(re.match(r'^:?-+:?$', c) for c in cells if c):
            continue
        rows.append(cells)
    return rows


# ─────────────────────────────────────────────
#  RELATIONSHIP GRAPH
# ─────────────────────────────────────────────

def update_relationship_graph(entity_a, entity_b, rel_type, opportunity):
    """Store detected entity relationships in session state.
    entity_a = Minet client (existing)
    entity_b = prospect / third-party doing business with entity_a
    """
    key = (entity_a.strip(), entity_b.strip())  # ordered: client first, prospect second
    if key not in st.session_state.relationship_graph:
        st.session_state.relationship_graph[key] = {
            "minet_client": entity_a.strip(),
            "prospect":     entity_b.strip(),
            "rel_type":     rel_type,
            "opportunity":  opportunity,
            "first_seen":   datetime.now().strftime("%d %b %Y"),
            "last_seen":    datetime.now().strftime("%d %b %Y"),
            "count": 1
        }
    else:
        st.session_state.relationship_graph[key]["last_seen"] = datetime.now().strftime("%d %b %Y")
        st.session_state.relationship_graph[key]["count"] += 1


def extract_relationships_from_table(rows, headers):
    """
    Parse LLM table rows and extract entity relationships for the graph.
    
    Acquisition Mode:  MINET CLIENT col → client,  NEW PROSPECT col → prospect
    Full Intelligence: CLIENT LINK col → client (if not 'NEW PROSPECT'), ENTITY col → prospect
    Retention Mode:    CLIENT col → client only (no prospect to extract)
    """
    try:
        h_upper = [h.upper() for h in headers]

        # ── Acquisition Mode columns ──
        minet_client_col = next((i for i, h in enumerate(h_upper) if h == "MINET CLIENT"), None)
        new_prospect_col = next((i for i, h in enumerate(h_upper) if h == "NEW PROSPECT"), None)
        rel_col          = next((i for i, h in enumerate(h_upper)
                                 if "RELATIONSHIP" in h or "LINK TYPE" in h or "REL" in h), None)
        opport_col       = next((i for i, h in enumerate(h_upper)
                                 if "PITCH" in h or "ANGLE" in h or "OPPORTUNITY" in h), None)

        # ── Full Intelligence Mode columns ──
        entity_col      = next((i for i, h in enumerate(h_upper) if h == "ENTITY"), None)
        client_link_col = next((i for i, h in enumerate(h_upper) if "CLIENT" in h and "LINK" in h), None)

        for row in rows[1:]:  # skip header
            if not any(c.strip() for c in row):
                continue

            client   = ""
            prospect = ""
            rel      = "ASSOCIATED"
            opport   = ""

            if minet_client_col is not None and new_prospect_col is not None:
                # ── Acquisition Mode: crystal clear columns ──
                client   = row[minet_client_col].strip() if minet_client_col < len(row) else ""
                prospect = row[new_prospect_col].strip() if new_prospect_col < len(row) else ""

            elif entity_col is not None and client_link_col is not None:
                # ── Full Intelligence Mode ──
                # CLIENT LINK = existing client name or "NEW PROSPECT"
                # ENTITY = the company the signal is about
                client_link = row[client_link_col].strip() if client_link_col < len(row) else ""
                entity_val  = row[entity_col].strip()      if entity_col      < len(row) else ""

                if client_link and client_link.upper() not in ["NEW PROSPECT", "—", "", "N/A"]:
                    # Entity is linked to an existing client — entity IS the client, 
                    # but we don't have a separate prospect here unless the signal reveals one
                    client   = client_link
                    prospect = ""  # No clear prospect in this row — skip graph update
                else:
                    # Entity is a NEW PROSPECT — no Minet client in this row either
                    client   = ""
                    prospect = ""

            # Get relationship type and opportunity text
            if rel_col is not None and rel_col < len(row):
                rel = row[rel_col].strip() or "ASSOCIATED"
            if opport_col is not None and opport_col < len(row):
                opport = row[opport_col].strip()

            # Only store when we have BOTH a real client AND a real prospect
            if (client and prospect
                    and client.upper()   not in ["NEW PROSPECT", "—", "", "N/A", "MINET CLIENT"]
                    and prospect.upper() not in ["NEW PROSPECT", "—", "", "N/A"]):
                update_relationship_graph(client, prospect, rel, opport)

    except Exception:
        pass


# ─────────────────────────────────────────────
#  CLIENT RISK SCORING
# ─────────────────────────────────────────────

def update_prospect_risk_score(prospect_name, signal_type, urgency,
                               minet_client="", relationship="", minet_angle="",
                               article_url="", article_summary="", scan_mode_used=""):
    """Risk score tracks PROSPECTS — how urgently we should pursue them."""
    urgency_weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    score_delta    = urgency_weight.get(urgency.upper(), 1)
    now_str        = datetime.now().strftime("%d %b %Y %H:%M")

    if prospect_name not in st.session_state.client_risk_scores:
        st.session_state.client_risk_scores[prospect_name] = {
            "score":          0,
            "signals":        [],
            "minet_clients":  [],   # which Minet clients connected them
            "relationships":  [],   # how they connect
            "minet_angles":   [],   # Minet service opportunity (risk, reinsurance, people)
            "article_urls":   [],   # source articles
            "summaries":      [],   # article summaries
            "first_seen":     now_str,
            "last_updated":   now_str,
            "scan_modes":     [],
        }

    rec = st.session_state.client_risk_scores[prospect_name]
    rec["score"]       += score_delta
    rec["last_updated"] = now_str

    if signal_type and signal_type not in rec["signals"]:
        rec["signals"].append(signal_type)
    if minet_client and minet_client not in rec["minet_clients"]:
        rec["minet_clients"].append(minet_client)
    if relationship and relationship not in rec["relationships"]:
        rec["relationships"].append(relationship)
    if minet_angle and minet_angle not in rec["minet_angles"]:
        rec["minet_angles"].append(minet_angle[:120])
    if article_url and article_url.startswith("http") and article_url not in rec["article_urls"]:
        rec["article_urls"].append(article_url)
    if article_summary and article_summary not in rec["summaries"]:
        rec["summaries"].append(article_summary[:150])
    if scan_mode_used and scan_mode_used not in rec["scan_modes"]:
        rec["scan_modes"].append(scan_mode_used)


def get_risk_badge(score):
    if score >= 6:
        return "<span class='risk-badge-high'>HIGH RISK</span>"
    elif score >= 3:
        return "<span class='risk-badge-med'>MED RISK</span>"
    else:
        return "<span class='risk-badge-low'>LOW RISK</span>"


# ─────────────────────────────────────────────
#  PDF EXPORT
# ─────────────────────────────────────────────

def build_pdf_bytes(report_text, mode, stats):
    """Build a simple HTML→bytes report for download (no external PDF lib needed)."""
    now = datetime.now().strftime("%d %b %Y · %H:%M EAT")
    html = f"""<!DOCTYPE html>
<html><head>
<meta charset='utf-8'>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; font-size: 13px; color: #1a1a1a; }}
h1 {{ font-size: 20px; color: #003399; border-bottom: 2px solid #003399; padding-bottom: 8px; }}
h2 {{ font-size: 14px; color: #555; text-transform: uppercase; letter-spacing: 1px; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 12px; }}
th {{ background: #003399; color: white; padding: 8px 10px; text-align: left; font-size: 11px; }}
td {{ padding: 7px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
tr:nth-child(even) td {{ background: #f8fafc; }}
.header-block {{ background: #f1f5f9; border-left: 4px solid #003399; padding: 12px 16px; margin-bottom: 24px; border-radius: 3px; }}
.footer {{ margin-top: 40px; font-size: 11px; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 10px; }}
</style>
</head><body>
<h1>🛡 MINET KENYA — PROJECT SENTINEL</h1>
<div class='header-block'>
<b>Intelligence Brief</b> · {now}<br>
Mode: {mode} &nbsp;|&nbsp; Intel Items: {stats.get('total_signals', 'N/A')} &nbsp;|&nbsp;
High Urgency: {stats.get('high_urgency', 'N/A')} &nbsp;|&nbsp;
New Prospects: {stats.get('new_prospects', 'N/A')}
</div>
{report_text.replace(chr(10), '<br>').replace('| :--- |', '').replace('**', '')}
<div class='footer'>Generated by Project Sentinel · Minet Kenya · Confidential Internal Brief</div>
</body></html>"""
    return html.encode('utf-8')


# ─────────────────────────────────────────────
#  LLM PROMPT BUILDER
# ─────────────────────────────────────────────

def build_prompt(scan_mode, signal_type_list, articles_text, client_names):
    known_rels = ""
    if st.session_state.relationship_graph:
        rels_list = list(st.session_state.relationship_graph.values())[:10]
        known_rels = "\nKNOWN ENTITY RELATIONSHIPS:\n" + "\n".join([
            "- " + r.get("minet_client","?") + " ↔ " + r.get("prospect","?") + " (" + r.get("rel_type","?") + ")"
            for r in rels_list
        ]) + "\n"

    strict_rules = """STRICT OUTPUT RULES:
1. OUTPUT ONLY THE MARKDOWN TABLE. No preamble, no explanation, no footnotes.
2. RELEVANCE GATE: Only include articles with DIRECT corporate/commercial relevance to insurance, risk, or people/benefits
   (expansion, acquisition, layoffs, financial distress, regulatory breach, leadership change,
   partnership, tender, ESG issue, restructuring, new product, workforce event).
   SKIP: politics, sports, entertainment, opinion, personal profiles, macroeconomic commentary
   without a named company, weather unless a named company is directly affected.
3. KENYA/EAST AFRICA GATE: ONLY include a signal if the entity has confirmed operations, employees,
   assets, contracts, or registered presence IN Kenya or East Africa. A global company headquartered
   elsewhere with NO Kenya/EA footprint must be SKIPPED. Minet Kenya's mandate is Kenya and East Africa only.
4. SOURCE: Copy the FULL article URL verbatim from [URL: ...] in the article block.
   NEVER use a homepage domain only (e.g. businessdailyafrica.com, reuters.com — these are WRONG).
   The URL must contain a path/slug beyond the domain, e.g. https://www.businessdailyafrica.com/bd/corporate/...
   NEVER truncate. NEVER leave blank. A SOURCE cell that is just a domain name is a CRITICAL ERROR.
5. DEDUPLICATION: Same event in 2+ articles = ONE merged row using the most informative URL.
6. ENTITY: Full registered company name. No vague references.
7. All cells filled. Use — only when genuinely not applicable.
8. ARTICLE SUMMARY: minimum 3 sentences. Include: (a) what happened, (b) the scale — exact KES/USD amounts, headcounts, dates, percentages, (c) named parties, locations, and timeline.
9. INSURANCE ANGLE: minimum 2 sentences. Name the exact Minet product line, the specific risk exposure triggered, estimated insurable value or headcount if inferable, and the urgency driver.
10. MINET ADVISORY ANGLE: minimum 2 sentences. Name the advisory service, what gap it fills for this entity, and a concrete first step Minet's team should take.
"""

    if scan_mode == "FULL INTELLIGENCE":
        return f"""You are the Chief Intelligence Analyst at Minet Kenya — East Africa's leading risk advisory and insurance brokerage firm.
Minet operates across three pillars — it acts BOTH as a direct insurer/broker AND as a risk/people advisor:
  1. RISK (Insurer/Broker) — Property & Casualty, Marine Cargo, Aviation, Motor Fleet, Construction All Risk,
     Professional Indemnity, D&O, Cyber Insurance, Public/Employers Liability, Workers Comp, Trade Credit,
     Political Risk, Fidelity; plus Risk Consulting, Risk Audits, Claims Advocacy, Risk Transfer
  2. REINSURANCE — Reinsurance Brokerage & Placement, Capital Management, Facultative & Treaty Reinsurance,
     Claims Advocacy for re/insurers
  3. PEOPLE (Benefits Broker/Consultant) — Employee Benefits, Group Medical / Managed Care, Group Life &
     Last Expense, Pension & Retirement Administration, Wellness Programs, HR & Actuarial Consulting

Mandate: scan corporate signals across East Africa — Kenya-linked entities only (see gate below).
Flag existing clients for retention/upsell. Flag every other Kenya/EA-present company as a prospect.

MINET CLIENT PORTFOLIO (for CLIENT LINK column only):
{client_names}

SIGNAL TAXONOMY (use EXACT names only):
{signal_type_list}
{known_rels}
ARTICLES:
{articles_text}

{strict_rules}

COLUMNS:
SIGNAL TYPE: Exact taxonomy name
URGENCY: HIGH / MEDIUM / LOW
ENTITY: Full company name (must have confirmed Kenya/EA presence)
CLIENT LINK: Exact portfolio name if entity matches, else NEW PROSPECT
ARTICLE SUMMARY: 2 sentences — what happened, when, scale (numbers/dates if present)
INSURANCE ANGLE: The direct insurance placement opportunity — exact Minet product line (e.g. Property All Risk, Group Medical, Marine Cargo, D&O, Motor Fleet, Cyber, Workers Comp) + the specific exposure/trigger with values or headcounts
MINET ADVISORY ANGLE: The broader advisory opportunity beyond direct cover — Risk Consulting, Reinsurance Placement, Claims Advocacy, Pension Admin, Wellness Programme, Risk Audit, HR Consulting etc.
STRATEGIC ACTION: Named action + Minet team/division responsible + timeframe. Specific and executable.
WHY IT MATTERS: One sentence — consequence to Minet Kenya of missing this signal
WHEN TO ACT: IMMEDIATE / THIS MONTH / NEXT QUARTER / MONITOR
SOURCE: Full article URL with path (not just domain)

OUTPUT — table only, no preamble:
| SIGNAL TYPE | URGENCY | ENTITY | CLIENT LINK | ARTICLE SUMMARY | INSURANCE ANGLE | MINET ADVISORY ANGLE | STRATEGIC ACTION | WHY IT MATTERS | WHEN TO ACT | SOURCE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

    elif scan_mode == "ACQUISITION MODE":
        return f"""You are the Lead Acquisition Strategist at Minet Kenya — a pan-African risk advisory and insurance brokerage firm.
Minet acts BOTH as a direct insurer/broker AND as a risk/people advisor:
  RISK (Insurer/Broker): Property & Casualty, Marine, Aviation, Motor Fleet, Construction, Professional Indemnity,
    D&O, Cyber, Liability, Workers Comp, Trade Credit, Political Risk, Fidelity; Risk Consulting, Claims Advocacy
  REINSURANCE: Reinsurance Placement, Capital Management, Facultative & Treaty
  PEOPLE (Benefits Broker): Group Medical/Managed Care, Group Life & Last Expense, Pension & Retirement Admin,
    Wellness, HR & Actuarial Consulting

MISSION: Find articles where an EXISTING MINET CLIENT and a NON-CLIENT third party appear together.
That third party is a warm acquisition prospect reachable via the client relationship.
KENYA/EA GATE: Both the client AND the prospect must have confirmed Kenya or East Africa presence.

LOGIC PER ARTICLE:
1. Does this article name a company from the Minet portfolio? That is the MINET CLIENT.
2. Is there a SECOND company in the same article transacting WITH that client?
   (supplier, buyer, contractor, JV partner, lender, tenant, franchisee, distributor, co-investor)
3. Is the second company NOT in the Minet portfolio AND confirmed Kenya/EA presence? That is the NEW PROSPECT.
4. If both conditions met: create one row. Otherwise: SKIP the article entirely.
5. NEVER create rows for articles mentioning only clients, only non-clients, or only individuals.
6. NEVER fabricate relationships not explicitly stated in the article.

MINET CLIENT PORTFOLIO:
{client_names}
{known_rels}
ARTICLES:
{articles_text}

{strict_rules}

COLUMNS:
MINET CLIENT: Existing client exact name
NEW PROSPECT: Third-party non-client exact name (Kenya/EA presence confirmed)
RELATIONSHIP TYPE: How they connect (supplier/JV/buyer/contractor/lender/co-investor etc.)
ARTICLE SUMMARY: 2 sentences, what the article says, amounts/dates if present
INSURANCE ANGLE: Direct insurance placement opportunity — exact Minet product line the prospect needs and why (e.g. Property All Risk, Motor Fleet, Group Medical, D&O, Marine Cargo, Construction All Risk)
MINET ADVISORY ANGLE: Broader Minet advisory opportunity — Risk Audit, Reinsurance Placement, Pension Consulting, Wellness Programme, Claims Advocacy, Risk Management Consulting etc.
WARM PITCH: One sentence leveraging the existing client relationship to open the door at the prospect
WHY IT MATTERS: Revenue/relationship risk to Minet Kenya of ignoring this
WHEN TO ACT: IMMEDIATE/THIS MONTH/NEXT QUARTER/MONITOR
SOURCE: Full article URL with path (not just domain)

OUTPUT table only:
| MINET CLIENT | NEW PROSPECT | RELATIONSHIP TYPE | ARTICLE SUMMARY | INSURANCE ANGLE | MINET ADVISORY ANGLE | WARM PITCH | WHY IT MATTERS | WHEN TO ACT | SOURCE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

    elif scan_mode == "RETENTION MODE":
        return f"""You are the Client Retention Intelligence Analyst at Minet Kenya — a pan-African risk advisory and insurance brokerage firm.
Minet acts BOTH as a direct insurer/broker AND as a risk/people advisor:
  RISK (Insurer/Broker): Property & Casualty, Marine, Aviation, Motor Fleet, Construction, Professional Indemnity,
    D&O, Cyber, Liability, Workers Comp, Trade Credit, Political Risk, Fidelity; Risk Consulting, Claims Advocacy
  REINSURANCE: Reinsurance Placement, Capital Management, Facultative & Treaty
  PEOPLE (Benefits Broker): Group Medical/Managed Care, Group Life & Last Expense, Pension & Retirement Admin,
    Wellness, HR & Actuarial Consulting

MISSION: Find signals about EXISTING MINET CLIENTS indicating:
CHURN RISK: client may switch broker, reduce cover, or lapse
UPSELL OPPORTUNITY: new activity requiring additional Minet insurance or advisory services
RENEWAL ALERT: corporate event coincides with renewal timing
RELATIONSHIP DEEPENING: moment to strengthen the Minet partnership

MINET CLIENT PORTFOLIO:
{client_names}
{known_rels}
ARTICLES:
{articles_text}

{strict_rules}

RULE: Only rows for companies IN the Minet portfolio with Kenya/EA operations. Analyse impact on their EXISTING Minet programme.

COLUMNS:
CLIENT: Exact Minet client name (must be in portfolio)
RETENTION SIGNAL: CHURN RISK/UPSELL OPPORTUNITY/RENEWAL ALERT/RELATIONSHIP DEEPENING
URGENCY: HIGH/MEDIUM/LOW
ARTICLE SUMMARY: 2 sentences, what happened, scale, dates
INSURANCE ANGLE: Which existing Minet insurance product/cover is affected and exactly how — name the specific policy type and the new exposure triggered (e.g. expanded Motor Fleet policy needed, new Property All Risk for new facility, Group Medical head-count increase)
MINET ADVISORY ANGLE: Beyond direct cover — Risk Consulting update, Reinsurance structure review, Pension gap, Wellness gap, Claims Advocacy opportunity, Risk Audit needed etc.
RETENTION ACTION: Named action + Minet division responsible (Risk / Reinsurance / People team) + timeframe
WHY IT MATTERS: Revenue/relationship risk of ignoring this
WHEN TO ACT: IMMEDIATE/THIS MONTH/NEXT QUARTER/MONITOR
SOURCE: Full article URL with path (not just domain)

OUTPUT table only:
| CLIENT | RETENTION SIGNAL | URGENCY | ARTICLE SUMMARY | INSURANCE ANGLE | MINET ADVISORY ANGLE | RETENTION ACTION | WHY IT MATTERS | WHEN TO ACT | SOURCE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |


"""
def build_competition_prompt(articles_text, client_names):
    return f"""
You are the Competitive Intelligence Analyst at Minet Kenya — a pan-African risk advisory and insurance brokerage firm (Risk · Reinsurance · People).
Mission: Detect signals in East African business news that relate to ANY of Minet's competitors across all three divisions:

BROKER/ADVISOR COMPETITORS: AON Kenya, Willis Towers Watson, Marsh, Alexander Forbes Kenya, Zamara, Momentum
GENERAL INSURANCE COMPETITORS: Jubilee Insurance, Britam, CIC Insurance, GA Insurance, APA Insurance, UAP Old Mutual, Heritage Insurance, Pioneer Insurance, Pacis Insurance, Cannon Assurance, Mayfair Insurance, Kenindia Assurance, Resolution Insurance, Saham Insurance, Takaful Insurance, First Assurance, Geminia Insurance, Occidental Insurance, Trident Insurance, AAR Insurance
REINSURANCE COMPETITORS: Africa Re, ZEP-RE, Continental Reinsurance, East Africa Reinsurance, PTA Reinsurance, Swiss Re (EA), Munich Re (EA), SCOR (EA)
LIFE/MEDICAL/BENEFITS COMPETITORS: Sanlam Kenya, Old Mutual Kenya, Prudential Kenya, Madison Insurance, CIC Life, Jubilee Life, AAR Health, Resolution Health, Bupa Africa, Cigna Kenya, MUA Insurance

MINET CLIENT PORTFOLIO:
{client_names}

ARTICLES:
{articles_text}

Identify:
1. Any competitor wins, losses, new products, or partnerships in Kenya/East Africa
2. Competitor pricing or product moves affecting Minet's Risk, Reinsurance, or People divisions
3. Any Minet client mentioned alongside a competitor — indicates churn risk
4. Regulatory actions against competitors that create opportunity for Minet

OUTPUT — ONLY this Markdown table:
| COMPETITOR | DIVISION AT RISK | SIGNAL | ENTITY INVOLVED | MINET CLIENT AT RISK | INTELLIGENCE SUMMARY | MINET COUNTER-ACTION |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""


# ─────────────────────────────────────────────
#  INTELLIGENCE ANALYSIS ENGINE
# ─────────────────────────────────────────────

def run_intelligence_analysis(signals, client_names, groq_client, scan_mode):
    if not signals:
        return "⚠ No signals harvested. Check feed connectivity.", {}

    signal_type_list = "\n".join([f"- {k}: {v['urgency']} urgency, sector: {v['sector']}" for k, v in SIGNAL_TYPES.items()])

    articles_text = "\n\n".join([
        f"[ARTICLE {i+1}]\nTITLE: {a['title']}\nSOURCE: {a['source']} ({a['region']}) | TYPE: {a.get('source_type','news').upper()}\nURL: {a['url']}\nDATE: {a.get('pub_date','')[:25]}\nCONTENT: {a['content'][:1200]}"
        for i, a in enumerate(signals[:24])
    ])

    prompt = build_prompt(scan_mode, signal_type_list, articles_text, client_names)

    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.05,
            max_tokens=4000
        )
        result = response.choices[0].message.content

        # Parse stats
        rows = extract_table_rows(result)
        data_rows = rows[1:] if rows else []  # skip header

        stats = {
            "total_signals": len(data_rows),
            "high_urgency":  sum(1 for r in data_rows if any("HIGH" in c.upper() for c in r)),
            "new_prospects": sum(1 for r in data_rows if any("NEW PROSPECT" in c.upper() for c in r)),
        }

        # Extract and store relationships
        if rows:
            extract_relationships_from_table(rows, rows[0] if rows else [])

        # ── Update prospect risk scores with rich detail ──
        if rows and len(rows) > 1:
            hdrs = rows[0]

            def hcol(name):
                return next((i for i, h in enumerate(hdrs) if name.lower() in h.lower()), None)

            # Column indices for data extraction
            c_entity    = hcol("entity")
            c_client    = hcol("minet client") or hcol("client link") or hcol("client")
            c_prospect  = hcol("new prospect")
            c_urgency   = hcol("urgency")
            c_signal    = hcol("signal type") or hcol("signal") or hcol("retention signal")
            c_rel       = hcol("relationship type") or hcol("link type")
            c_ins_angle = hcol("insurance angle")
            c_adv_angle = hcol("minet advisory angle") or hcol("minet angle")
            c_summary   = hcol("article summary")
            c_source    = hcol("source")

            for row in data_rows:
                def cell(idx):
                    return row[idx].strip() if idx is not None and idx < len(row) else ""

                urgency_val  = cell(c_urgency)  or "MEDIUM"
                sig_val      = cell(c_signal)   or "UNKNOWN"
                # Combine both angles for prospect scoring storage
                ins_angle_val = cell(c_ins_angle)
                adv_angle_val = cell(c_adv_angle)
                angle_val    = " | ".join(filter(None, [ins_angle_val, adv_angle_val]))
                summary_val  = cell(c_summary)
                source_val   = cell(c_source)
                rel_val      = cell(c_rel)
                client_val   = cell(c_client)
                prospect_val = cell(c_prospect)
                entity_val   = cell(c_entity)

                # ── Acquisition Mode: prospect is explicitly in NEW PROSPECT column ──
                if scan_mode == "ACQUISITION MODE" and prospect_val:
                    name = prospect_val
                    if name.upper() not in ["—", "", "NEW PROSPECT"]:
                        update_prospect_risk_score(
                            name, sig_val, urgency_val,
                            minet_client=client_val,
                            relationship=rel_val,
                            minet_angle=angle_val,
                            article_url=source_val,
                            article_summary=summary_val,
                            scan_mode_used=scan_mode
                        )

                # ── Full Intelligence Mode: NEW PROSPECT in CLIENT LINK column ──
                elif scan_mode == "FULL INTELLIGENCE":
                    cl = client_val.upper()
                    if "NEW PROSPECT" in cl and entity_val:
                        name = entity_val
                        if name.upper() not in ["—", ""]:
                            update_prospect_risk_score(
                                name, sig_val, urgency_val,
                                minet_client="",
                                relationship="",
                                minet_angle=angle_val,
                                article_url=source_val,
                                article_summary=summary_val,
                                scan_mode_used=scan_mode
                            )

        return result, stats

    except Exception as e:
        err_str = str(e).lower()
        # Detect common Groq/LLM quota and rate-limit errors
        if any(x in err_str for x in ["rate_limit", "rate limit", "quota", "tokens", "429",
                                        "exceeded", "too many", "capacity", "overloaded"]):
            friendly = (
                "⚠️ **Groq API Limit Reached**\n\n"
                "The Llama 3.3-70B model has returned a rate-limit or token-quota error. "
                "This usually means:\n"
                "- You have exhausted your free-tier token quota for this minute/day\n"
                "- The model is temporarily overloaded\n\n"
                "**What to do:**\n"
                "1. Wait 60 seconds and try again\n"
                "2. Reduce **Articles per feed** to 1-2 in the sidebar\n"
                "3. Switch to **Tier 1 Only** feed coverage\n"
                "4. Check your Groq console at console.groq.com for quota status\n\n"
                f"*Raw error: `{e}`*"
            )
        else:
            friendly = f"⚠️ **Analysis engine error:** {e}"
        return friendly, {"total_signals": 0, "high_urgency": 0, "new_prospects": 0}


def run_competition_analysis(signals, client_names, groq_client):
    articles_text = "\n\n".join([
        f"[ARTICLE {i+1}]\nTITLE: {a['title']}\nSOURCE: {a['source']}\nURL: {a['url']}\nCONTENT: {a['content'][:800]}"
        for i, a in enumerate(signals[:18])
    ])
    prompt = build_competition_prompt(articles_text, client_names)
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.05,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        err_str = str(e).lower()
        if any(x in err_str for x in ["rate_limit", "rate limit", "quota", "tokens", "429", "exceeded", "too many"]):
            return "⚠️ **Competition scan skipped** — API rate limit reached. Try again in 60 seconds."
        return f"⚠️ Competition analysis error: {e}"


# ─────────────────────────────────────────────
#  REPORT HEADER
# ─────────────────────────────────────────────

def build_report_header(scan_mode, num_signals, sources_active, stats):
    now = datetime.now().strftime("%d %b %Y · %H:%M EAT")
    return f"""# MINET KENYA — PROJECT SENTINEL
**Classification:** Internal Intelligence Brief  
**Generated:** {now}  
**Scan Mode:** {scan_mode}  
**Sources Active:** {sources_active}  
**Raw Signals Ingested:** {num_signals}  
**Actionable Intelligence Items:** {stats.get('total_signals', 'N/A')}  
**High-Urgency Flags:** {stats.get('high_urgency', 'N/A')}  
**New Prospects Identified:** {stats.get('new_prospects', 'N/A')}  

---

"""


# ─────────────────────────────────────────────
#  RENDER ENHANCED INTEL TABLE WITH EXTRA LAYERS
# ─────────────────────────────────────────────

def render_intel_output(report_body, scan_mode, signals):
    """Render intelligence output — TABLE view (original preference) + sector grouping headers."""
    rows = extract_table_rows(report_body)
    if not rows or len(rows) < 2:
        st.markdown(report_body)
        return

    headers = rows[0]
    data_rows = rows[1:]

    # Remove any EST. PREMIUM column if LLM still sneaks it in
    headers, data_rows = _strip_column(headers, data_rows, "premium")

    # Group by sector if Full Intelligence mode
    if scan_mode == "FULL INTELLIGENCE":
        signal_col = next((i for i, h in enumerate(headers) if "SIGNAL" in h.upper()), 0)
        sectors_found = {}
        for row in data_rows:
            sig = row[signal_col].strip().upper().replace(" ", "_") if signal_col < len(row) else "OTHER"
            sector = SIGNAL_TYPES.get(sig, {}).get("sector", "OTHER")
            sectors_found.setdefault(sector, []).append(row)

        global_row_idx = [0]  # mutable counter shared across sectors
        for sector, sector_rows in sectors_found.items():
            st.markdown(f"""
            <div class='sector-layer'>
                ▸ SECTOR INTELLIGENCE LAYER &nbsp;·&nbsp; {sector} &nbsp;·&nbsp; {len(sector_rows)} SIGNAL{'S' if len(sector_rows) > 1 else ''}
            </div>""", unsafe_allow_html=True)
            _render_table_with_actions(headers, sector_rows, scan_mode, signals, global_row_idx)
    else:
        _render_table_with_actions(headers, data_rows, scan_mode, signals, [0])


def _strip_column(headers, data_rows, keyword):
    """Remove a column by keyword match from headers + all rows."""
    idx = next((i for i, h in enumerate(headers) if keyword.lower() in h.lower()), None)
    if idx is None:
        return headers, data_rows
    new_headers = [h for i, h in enumerate(headers) if i != idx]
    new_rows = [[c for i, c in enumerate(row) if i != idx] for row in data_rows]
    return new_headers, new_rows


def _render_table_with_actions(headers, rows, scan_mode, signals, row_counter):
    """
    Render intelligence as the original styled Markdown table PLUS
    Why-This-Matters banners and per-row action buttons below the table.
    """
    if not rows:
        return

    def col(name):
        return next((i for i, h in enumerate(headers) if name.lower() in h.lower()), None)

    why_i    = col("why")
    when_i   = col("when")
    source_i = col("source")
    # Entity detection — order matters: most specific first
    entity_i = col("entity")
    if entity_i is None:
        entity_i = col("new prospect")   # acquisition mode prospect column
    if entity_i is None:
        entity_i = col("client")         # retention mode / acquisition minet client
    if entity_i is None:
        entity_i = 0                     # fallback to first column

    sig_i    = col("signal") or col("retention") or 0
    urg_i    = col("urgency")
    action_i = col("action") or col("retention action") or col("strategic action") or col("warm pitch")

    # ── Render the full markdown table (original preferred look) ──
    # Build source-enriched rows: swap raw URL cell for clickable markdown link
    enriched_rows = []
    for row in rows:
        enriched = list(row)
        # Inject source link into SOURCE column if present
        if source_i is not None and source_i < len(enriched):
            url = enriched[source_i].strip()
            if not url.startswith("http"):
                # Try to match from harvested signals
                entity = enriched[entity_i].strip() if entity_i is not None and entity_i < len(enriched) else ""
                matched = next((s for s in signals if entity.lower() in s['title'].lower() or
                               entity.lower() in s['content'].lower()[:200]), None)
                url = matched['url'] if matched else ""
            enriched[source_i] = f"[↗ Source]({url})" if url.startswith("http") else "—"
        enriched_rows.append(enriched)

    # Build markdown table string
    header_line = "| " + " | ".join(headers) + " |"
    sep_line    = "| " + " | ".join([":---"] * len(headers)) + " |"
    body_lines  = ["| " + " | ".join(r + [""] * max(0, len(headers) - len(r))) + " |" for r in enriched_rows]
    table_md    = "\n".join([header_line, sep_line] + body_lines)
    st.markdown(table_md)

    # ── Below-table: Why This Matters banners + action buttons ──
    st.markdown(f"<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    for row in rows:
        row_counter[0] += 1
        ridx = row_counter[0]

        entity   = row[entity_i].strip()  if entity_i  is not None and entity_i  < len(row) else f"row_{ridx}"
        sig_type = row[sig_i].strip()     if sig_i     is not None and sig_i     < len(row) else "SIGNAL"
        urgency  = row[urg_i].strip()     if urg_i     is not None and urg_i     < len(row) else "MEDIUM"
        action   = row[action_i].strip()  if action_i  is not None and action_i  < len(row) else "—"
        why      = row[why_i].strip()     if why_i     is not None and why_i     < len(row) else ""
        when     = row[when_i].strip()    if when_i    is not None and when_i    < len(row) else ""

        when_color = {"IMMEDIATE": "#F87171", "THIS MONTH": "#FBBF24",
                      "NEXT QUARTER": "#60A5FA", "MONITOR": "#6B7280"}.get(when.upper(), TEXT3)

        # Safe unique key: use row index (never collides even if entity/sig are identical)
        key_base = f"r{ridx}"

        if why:
            st.markdown(f"""
            <div class='why-matters-card' style='margin-bottom:4px;'>
                <span style='font-size:10px; letter-spacing:1px; color:#4ADE80; font-family:IBM Plex Mono,monospace; text-transform:uppercase;'>
                    ▸ {entity} &nbsp;·&nbsp; WHY THIS MATTERS
                </span>
                <span style='font-family:IBM Plex Mono,monospace; font-size:10px; color:{when_color}; float:right;'>⏱ {when}</span><br>
                <span style='font-size:13px; color:{TEXT2};'>{why}</span>
            </div>""", unsafe_allow_html=True)

        # Action buttons — toast only, NO st.rerun()
        col_fb1, col_fb2, col_fb3, _ = st.columns([1, 1, 1.2, 3])
        with col_fb1:
            if st.button("👍 Relevant", key=f"fb_yes_{key_base}"):
                st.session_state.feedback_log.append({
                    "entity": entity, "signal": sig_type, "rating": "relevant",
                    "ts": datetime.now().strftime("%d %b %Y %H:%M")
                })
                st.toast("Feedback recorded ✓", icon="✅")
        with col_fb2:
            if st.button("👎 Not useful", key=f"fb_no_{key_base}"):
                st.session_state.feedback_log.append({
                    "entity": entity, "signal": sig_type, "rating": "not_useful",
                    "ts": datetime.now().strftime("%d %b %Y %H:%M")
                })
                st.toast("Feedback recorded ✓", icon="✅")
        with col_fb3:
            if st.button("📌 Add to Tracker", key=f"track_{key_base}"):
                # Find source URL for this row
                source_url = ""
                if source_i is not None and source_i < len(row):
                    source_url = row[source_i].strip()
                if not source_url.startswith("http"):
                    matched = next((s for s in signals if entity.lower() in s['title'].lower() or
                                   entity.lower() in s['content'].lower()[:200]), None)
                    source_url = matched['url'] if matched else ""
                st.session_state.closed_loop_tracker.append({
                    "entity": entity, "signal": sig_type, "action": action,
                    "status": "OPEN", "urgency": urgency,
                    "opened": datetime.now().strftime("%d %b %Y %H:%M"),
                    "source_url": source_url,
                    "closed": None
                })
                st.toast(f"📌 {entity} added to tracker", icon="📌")

        st.markdown(f"<hr style='border-color:{BORDER}; margin:6px 0 14px 0;'>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  MAIN UI
# ─────────────────────────────────────────────

def main():
    # ── Sidebar ──────────────────────────────
    with st.sidebar:
        st.markdown(f"""
        <div style='padding: 16px 0 8px 0;'>
            <div style='font-family: IBM Plex Mono, monospace; font-size: 11px; letter-spacing: 2px; color: {TEXT4}; margin-bottom: 4px;'>MINET KENYA</div>
            <div style='font-size: 18px; font-weight: 600; color: {TEXT};'>PROJECT SENTINEL</div>
            <div style='font-size: 11px; color: {TEXT4}; margin-top: 2px;'>Intelligence Operations Platform</div>
        </div>
        <hr style='border-color: {BORDER}; margin: 12px 0;'>
        """, unsafe_allow_html=True)

        st.markdown(f"<div style='font-size:11px;letter-spacing:1px;color:{TEXT4};text-transform:uppercase;margin-bottom:8px;'>Scan Configuration</div>", unsafe_allow_html=True)

        scan_mode = st.selectbox(
            "Intelligence Mode",
            ["FULL INTELLIGENCE", "ACQUISITION MODE", "RETENTION MODE"],
            help="Full Intelligence: all signals. Acquisition: ecosystem prospect mapping. Retention: client retention signals."
        )

        feed_tier = st.select_slider(
            "Feed Coverage",
            options=["Tier 1 Only (Fastest)", "Tier 1 + 2 (Balanced)", "All Feeds (Maximum)"],
            value="Tier 1 + 2 (Balanced)"
        )
        tier_map = {"Tier 1 Only (Fastest)": 1, "Tier 1 + 2 (Balanced)": 2, "All Feeds (Maximum)": 3}
        selected_tier = tier_map[feed_tier]

        articles_per_feed = st.slider("Articles per feed", min_value=1, max_value=5, value=3)

        st.markdown(f"<hr style='border-color: {BORDER}; margin: 12px 0;'>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:11px;letter-spacing:1px;color:{TEXT4};text-transform:uppercase;margin-bottom:8px;'>Source Types</div>", unsafe_allow_html=True)
        src_news  = st.checkbox("📰 News Media", value=True)
        src_reg   = st.checkbox("⚖️ Regulators (IRA, CMA)", value=True)
        src_annc  = st.checkbox("📢 Company Announcements (NSE)", value=True)
        active_source_types = []
        if src_news: active_source_types.append("news")
        if src_reg:  active_source_types.append("regulator")
        if src_annc: active_source_types.append("announcement")

        run_competition = st.checkbox("🔍 Competition Counter-Intelligence", value=False)

        st.markdown(f"<hr style='border-color: {BORDER}; margin: 12px 0;'>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:11px;letter-spacing:1px;color:{TEXT4};text-transform:uppercase;margin-bottom:8px;'>Signal Taxonomy</div>", unsafe_allow_html=True)

        for sector, sigs in SECTOR_LAYERS.items():
            st.markdown(f"<div style='font-size:9px;letter-spacing:1px;color:{TEXT4};text-transform:uppercase;margin:6px 0 3px 0;'>{sector}</div>", unsafe_allow_html=True)
            tags_html = ""
            for sig in sigs:
                meta = SIGNAL_TYPES[sig]
                sig_color = meta['color']
                # In light mode, darken the color for readability on white background
                if not dark:
                    tag_bg     = "#F0F9FF"
                    tag_color  = "#1E3A5F"
                    tag_border = "#93C5FD"
                else:
                    tag_bg     = "#0D1F3A"
                    tag_color  = sig_color
                    tag_border = sig_color
                tags_html += (f"<span style='display:inline-block;background:{tag_bg};border:1px solid {tag_border};"
                              f"color:{tag_color};font-size:10px;padding:3px 8px;border-radius:2px;margin:2px;"
                              f"font-family:IBM Plex Mono,monospace;letter-spacing:0.5px;'>"
                              f"{meta['icon']} {sig.replace('_',' ')}</span>")
            st.markdown(tags_html, unsafe_allow_html=True)

        st.markdown(f"<hr style='border-color: {BORDER}; margin: 16px 0;'>", unsafe_allow_html=True)

        groq_api_key = st.text_input("GROQ API Key", value="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", type="password")

        st.markdown(f"<hr style='border-color: {BORDER}; margin: 16px 0;'>", unsafe_allow_html=True)

        # ── Engine Start button — ignition-style component triggers hidden st.button ──

        # Render the real Streamlit button first so it registers with Streamlit's state engine.
        # Then bury it off-screen via a zero-height components.html script (runs in iframe, accesses parent DOM).
        execute = st.button("▶ SCAN", key="sentinel_scan_btn", help="Execute Sentinel Scan", use_container_width=False)

        import streamlit.components.v1 as components
        components.html("""<script>
(function() {
  function hideScanBtn() {
    var btns = window.parent.document.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].textContent.trim() === '\u25b6 SCAN') {
        var el = btns[i];
        el.style.cssText = 'position:fixed!important;top:-9999px!important;width:0!important;height:0!important;opacity:0!important;pointer-events:none!important;';
        var p = el.parentElement;
        while (p && p.getAttribute('data-testid') !== 'element-container') { p = p.parentElement; }
        if (p) p.style.cssText = 'position:fixed!important;top:-9999px!important;width:0!important;height:0!important;overflow:hidden!important;';
        return;
      }
    }
    setTimeout(hideScanBtn, 60);
  }
  hideScanBtn();
})();
</script>""", height=0, scrolling=False)

        btn_bg = '#0A0C11' if dark else '#FFFFFF'
        btn_html = f"""<!DOCTYPE html><html><head>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:{btn_bg};display:flex;justify-content:center;align-items:center;height:140px;}}
.eng{{
  width:115px;height:115px;border-radius:50%;
  background:radial-gradient(circle at 38% 32%, #1a0505 0%, #050005 70%);
  border:3px solid #CC0000;cursor:pointer;
  box-shadow:0 0 22px #CC000055,0 0 8px #CC000033,inset 0 0 16px #CC000022;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;
  transition:all 0.25s;user-select:none;font-family:'IBM Plex Mono',monospace;
  animation:glow 2.5s ease-in-out infinite;
}}
.eng:hover{{box-shadow:0 0 35px #CC000099,0 0 14px #CC000066,inset 0 0 22px #CC000044;border-color:#FF2222;transform:scale(1.05);}}
.eng:active{{transform:scale(0.96);box-shadow:0 0 10px #CC000055;}}
.icon{{font-size:28px;color:#CC0000;text-shadow:0 0 12px #FF000099;line-height:1;}}
.lbl{{font-size:8px;letter-spacing:2.5px;color:#FFFFFF;text-transform:uppercase;text-align:center;line-height:1.4;font-weight:600;}}
@keyframes glow{{
  0%,100%{{box-shadow:0 0 22px #CC000055,0 0 8px #CC000033,inset 0 0 16px #CC000022;}}
  50%{{box-shadow:0 0 38px #CC000088,0 0 16px #CC000055,inset 0 0 26px #CC000038;}}
}}
</style></head><body>
<div class="eng" onclick="
  var btns=window.parent.document.querySelectorAll('button');
  for(var i=0;i<btns.length;i++){{
    if(btns[i].textContent.trim()==='\u25b6 SCAN'){{btns[i].click();break;}}
  }}
">
  <div class="icon">⬡</div>
  <div class="lbl">EXECUTE<br>SENTINEL</div>
</div>
</body></html>"""
        components.html(btn_html, height=148, scrolling=False)

        st.markdown(f"<hr style='border-color: {BORDER}; margin: 8px 0 16px 0;'>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:11px;color:{TEXT5};text-align:center;'>Minet Kenya · Project Sentinel v5.0<br>Powered by Llama 3.3 · 70B</div>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────
    tab_intel, tab_calendar, tab_graph, tab_tracker, tab_risk, tab_archive, tab_feedback = st.tabs([
        "🛡 Intelligence", "📅 Renewal Calendar", "🔗 Relationship Graph",
        "📌 Closed-Loop Tracker", "📊 Prospect Scores", "🗄 Signal Archive", "💬 Feedback"
    ])

    # ══════════════════════════════════════════
    #  TAB 1 — INTELLIGENCE
    # ══════════════════════════════════════════
    with tab_intel:
        col_title, col_status = st.columns([3, 1])
        with col_title:
            st.markdown("<h1>Intelligence Dashboard</h1>", unsafe_allow_html=True)
            st.markdown(f"<h2>East Africa · Corporate Signal Detection · {len(RSS_FEEDS)} Active Feeds</h2>", unsafe_allow_html=True)
        with col_status:
            st.markdown(f"""
            <div style='text-align:right; padding-top: 8px;'>
                <span class='pulse-dot'></span>
                <span style='font-size:12px; font-family: IBM Plex Mono, monospace; color: #22C55E; letter-spacing:1px;'>SYSTEM READY</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"<hr style='border-color: {BORDER}; margin: 8px 0 24px 0;'>", unsafe_allow_html=True)

        # ── Determine whether to run a fresh scan or restore previous results ──
        run_fresh = execute
        has_cached = st.session_state.last_report_body is not None

        if run_fresh:
            groq_client = Groq(api_key=groq_api_key)
            clients = load_clients()

            # ── Scan initiation banner — rendered via components so SVG/animation works ──
            import streamlit.components.v1 as components
            banner_bg   = "#0D1F0E" if dark else "#EFF6EC"
            banner_bdr  = "#1A3A1C" if dark else "#BBF7D0"
            txt_color   = "#4ADE80" if dark else "#15803D"
            components.html(f"""<!DOCTYPE html><html><head>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:{banner_bg};font-family:'IBM Plex Mono',monospace;overflow:hidden;}}
  .banner{{
    display:flex;align-items:center;gap:20px;
    padding:14px 20px;
    border:1px solid {banner_bdr};border-left:4px solid #22C55E;
    border-radius:6px;
  }}
  .txt-main{{font-size:14px;color:#4ADE80;letter-spacing:2px;font-weight:600;margin-bottom:4px;}}
  .txt-sub{{font-size:11px;color:{txt_color};letter-spacing:1px;opacity:0.85;}}
  /* Bike wheel spinner */
  svg.wheel{{flex-shrink:0;}}
</style>
</head><body>
<div class="banner">
  <svg class="wheel" viewBox="0 0 80 80" width="80" height="80">
    <!-- Hub -->
    <circle cx="40" cy="40" r="6" fill="#22C55E"/>
    <circle cx="40" cy="40" r="3" fill="#0D1F0E"/>
    <!-- Rim -->
    <circle cx="40" cy="40" r="34" fill="none" stroke="#22C55E" stroke-width="3"/>
    <!-- Tyre (outer) -->
    <circle cx="40" cy="40" r="37" fill="none" stroke="#4ADE80" stroke-width="2" opacity="0.4"/>
    <!-- 8 Spokes — rotated as a group -->
    <g id="spokes">
      <line x1="40" y1="34" x2="40" y2="6"  stroke="#22C55E" stroke-width="1.8" stroke-linecap="round"/>
      <line x1="40" y1="34" x2="40" y2="6"  stroke="#22C55E" stroke-width="1.8" stroke-linecap="round" transform="rotate(45 40 40)"/>
      <line x1="40" y1="34" x2="40" y2="6"  stroke="#22C55E" stroke-width="1.8" stroke-linecap="round" transform="rotate(90 40 40)"/>
      <line x1="40" y1="34" x2="40" y2="6"  stroke="#22C55E" stroke-width="1.8" stroke-linecap="round" transform="rotate(135 40 40)"/>
      <line x1="40" y1="34" x2="40" y2="6"  stroke="#22C55E" stroke-width="1.8" stroke-linecap="round" transform="rotate(180 40 40)"/>
      <line x1="40" y1="34" x2="40" y2="6"  stroke="#22C55E" stroke-width="1.8" stroke-linecap="round" transform="rotate(225 40 40)"/>
      <line x1="40" y1="34" x2="40" y2="6"  stroke="#22C55E" stroke-width="1.8" stroke-linecap="round" transform="rotate(270 40 40)"/>
      <line x1="40" y1="34" x2="40" y2="6"  stroke="#22C55E" stroke-width="1.8" stroke-linecap="round" transform="rotate(315 40 40)"/>
      <animateTransform attributeName="transform" type="rotate"
        from="0 40 40" to="360 40 40" dur="1.1s" repeatCount="indefinite"/>
    </g>
    <!-- Moving highlight dot on rim -->
    <circle cx="40" cy="6" r="3.5" fill="#FFFFFF" opacity="0.9">
      <animateTransform attributeName="transform" type="rotate"
        from="0 40 40" to="360 40 40" dur="1.1s" repeatCount="indefinite"/>
    </circle>
    <!-- Inner pulsing ring -->
    <circle cx="40" cy="40" r="18" fill="none" stroke="#22C55E" stroke-width="1" opacity="0.3">
      <animate attributeName="r" values="16;20;16" dur="1.8s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0.5;0.1;0.5" dur="1.8s" repeatCount="indefinite"/>
    </circle>
  </svg>
  <div>
    <div class="txt-main">SENTINEL ENGINE ACTIVE</div>
    <div class="txt-sub">
      MODE:&nbsp;<b>{scan_mode}</b>&nbsp;&nbsp;·&nbsp;&nbsp;
      TIER:&nbsp;<b>{feed_tier}</b>&nbsp;&nbsp;·&nbsp;&nbsp;
      {datetime.now().strftime('%H:%M:%S')}&nbsp;EAT
    </div>
  </div>
</div>
</body></html>""", height=110, scrolling=False)

            with st.status("⬡ Intelligence harvest in progress...", expanded=True) as status:
                active_feed_count = len([f for f in RSS_FEEDS if f['tier'] <= selected_tier and f.get('type','news') in active_source_types])
                st.write(f"⬡ Establishing connections to {active_feed_count} intelligence sources across East Africa...")
                st.write(f"⬡ Feed tiers selected: {feed_tier} · Articles per feed: {articles_per_feed}")

                signals, attempted, successful = harvest_signals(
                    tier_filter=selected_tier,
                    max_per_feed=articles_per_feed,
                    source_types=active_source_types if active_source_types else None
                )
                st.write(f"✓ Harvest complete → {successful}/{attempted} feeds responded · {len(signals)} raw signals ingested")

                if len(signals) == 0:
                    status.update(label="⚠ No signals harvested — check feed connectivity or widen tier selection.", state="error")
                    st.stop()

                st.write(f"⬡ Routing {len(signals)} signals into {scan_mode} analysis pipeline...")
                st.write("⬡ Deduplicating and merging overlapping event signals...")
                st.write("⬡ Querying Llama 3.3-70B intelligence engine · this takes ~15-30 seconds...")
                report_body, stats = run_intelligence_analysis(signals, clients, groq_client, scan_mode)
                st.write(f"✓ LLM analysis complete → {stats.get('total_signals', 0)} intelligence items extracted")

                competition_report = None
                if run_competition:
                    st.write("⬡ Initiating competition counter-intelligence sweep...")
                    competition_report = run_competition_analysis(signals, clients, groq_client)
                    st.write("✓ Competition layer complete")

                status.update(
                    label=f"✓ SENTINEL SCAN COMPLETE · {stats.get('total_signals', 0)} intel items · "
                          f"{stats.get('high_urgency', 0)} high urgency · {stats.get('new_prospects', 0)} prospects",
                    state="complete", expanded=False
                )

            # ── Persist results so theme-toggle rerun doesn't wipe them ──
            st.session_state.last_report_body       = report_body
            st.session_state.last_report_stats      = stats
            st.session_state.last_signals           = signals
            st.session_state.last_scan_mode         = scan_mode
            st.session_state.last_competition_report= competition_report
            st.session_state.last_sources_active    = successful

        elif has_cached:
            # Restore from previous scan after theme toggle rerun
            report_body       = st.session_state.last_report_body
            stats             = st.session_state.last_report_stats
            signals           = st.session_state.last_signals
            scan_mode         = st.session_state.last_scan_mode
            competition_report= st.session_state.last_competition_report
            successful        = st.session_state.last_sources_active

            st.markdown(f"""
            <div style='background:{"#0D1515" if dark else "#F0FDF4"}; border:1px solid {"#1A3030" if dark else "#BBF7D0"};
                 border-left:3px solid #22C55E; padding:10px 16px; border-radius:4px; margin-bottom:16px;'>
                <span style='font-family:IBM Plex Mono,monospace; font-size:11px; color:#4ADE80; letter-spacing:1px;'>
                    ↺ RESTORED PREVIOUS SCAN · {scan_mode} · {len(signals)} signals · Theme updated
                </span>
            </div>""", unsafe_allow_html=True)

        if run_fresh or has_cached:
            st.markdown("<br>", unsafe_allow_html=True)
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Signals Harvested", f"{len(signals)}")
            k2.metric("Sources Active",    f"{successful}")
            k3.metric("Intel Items",       f"{stats.get('total_signals', 0)}")
            k4.metric("High Urgency",      f"{stats.get('high_urgency', 0)}")
            k5.metric("New Prospects",     f"{stats.get('new_prospects', 0)}")

            st.markdown(f"<hr style='border-color: {BORDER}; margin: 24px 0 16px 0;'>", unsafe_allow_html=True)

            # Mode badge + bulletin header
            mode_colors = {
                "FULL INTELLIGENCE": "#60A5FA",
                "ACQUISITION MODE":  "#34D399",
                "RETENTION MODE":    "#FBBF24"
            }
            st.markdown(f"""
            <div style='font-family: IBM Plex Mono, monospace; font-size: 11px; letter-spacing: 1.5px; color: {TEXT4}; margin-bottom: 16px;'>
                INTELLIGENCE BULLETIN &nbsp;·&nbsp;
                <span style='color:{mode_colors.get(scan_mode, ACCENT)};'>{scan_mode}</span>
                &nbsp;·&nbsp; {datetime.now().strftime('%d %b %Y')}
            </div>
            """, unsafe_allow_html=True)

            # Render enhanced cards
            render_intel_output(report_body, scan_mode, signals)

            # Competition layer
            if competition_report:
                st.markdown(f"<hr style='border-color:{BORDER}; margin:32px 0 16px 0;'>", unsafe_allow_html=True)
                st.markdown(f"""
                <div style='font-family: IBM Plex Mono, monospace; font-size: 11px; letter-spacing: 1.5px; color:{TEXT4}; margin-bottom:12px;'>
                    🔍 COMPETITION COUNTER-INTELLIGENCE LAYER
                </div>""", unsafe_allow_html=True)
                comp_rows = extract_table_rows(competition_report)
                if comp_rows and len(comp_rows) > 1:
                    for row in comp_rows[1:]:
                        if not any(row):
                            continue
                        st.markdown(f"""
                        <div class='competition-card'>
                            <div style='font-family:IBM Plex Mono,monospace; font-size:11px; color:#A78BFA; letter-spacing:1px; margin-bottom:6px;'>
                                ⊡ COMPETITOR SIGNAL
                            </div>
                            <div style='font-size:13px; color:{TEXT2}; line-height:1.6;'>
                                {'&nbsp;&nbsp;|&nbsp;&nbsp;'.join(row)}
                            </div>
                        </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(competition_report)

            # Downloads
            st.markdown(f"<hr style='border-color: {BORDER}; margin: 24px 0 16px 0;'>", unsafe_allow_html=True)
            full_report = build_report_header(scan_mode, len(signals), successful, stats) + report_body

            col_dl1, col_dl2, col_dl3, _ = st.columns([1, 1, 1, 1])
            with col_dl1:
                st.download_button(
                    "↓ Download Brief (.md)",
                    full_report,
                    f"Minet_Sentinel_{scan_mode.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                    mime="text/markdown"
                )
            with col_dl2:
                st.download_button(
                    "↓ Download Raw Signals (.json)",
                    json.dumps(signals, indent=2),
                    f"Minet_RawSignals_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json"
                )
            with col_dl3:
                pdf_bytes = build_pdf_bytes(report_body, scan_mode, stats)
                st.download_button(
                    "↓ Download PDF Brief (.html)",
                    pdf_bytes,
                    f"Minet_Sentinel_{scan_mode.replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                    mime="text/html"
                )

            # Raw signals expander
            with st.expander(f"▸ View raw signals ({len(signals)} articles ingested)"):
                for i, art in enumerate(signals):
                    src_icon, src_color = SOURCE_TYPE_LABELS.get(art.get("source_type","news"), ("📰", ACCENT))
                    col_a, col_b = st.columns([2, 5])
                    with col_a:
                        st.markdown(f"""
                        <div style='font-family: IBM Plex Mono, monospace; font-size: 10px; color: {TEXT4};'>
                            <span style='color:{src_color};'>{src_icon}</span> [{art['region']}] T{art['tier']}<br>
                            {art['source']}<br>
                            {art.get('pub_date','')[:16]}
                        </div>
                        """, unsafe_allow_html=True)
                    with col_b:
                        st.markdown(f"**{art['title']}**")
                        st.markdown(f"<a href='{art['url']}' target='_blank' style='color:{ACCENT};font-size:11px;font-family:IBM Plex Mono,monospace;'>↗ {art['url'][:80]}...</a>", unsafe_allow_html=True)
                        st.markdown(f"<span style='font-size:12px;color:{TEXT4};'>{art['content'][:200]}...</span>", unsafe_allow_html=True)
                    st.markdown(f"<hr style='border-color:{BORDER}; margin: 8px 0;'>", unsafe_allow_html=True)

        elif not has_cached:
            # Idle state — no previous scan to show
            _idle_logo_b64 = get_logo_b64()
            _idle_logo_html = (
                f"<img src='data:image/png;base64,{_idle_logo_b64}' style='height:54px;object-fit:contain;display:block;margin:0 auto 18px auto;' />"
                if _idle_logo_b64 else
                "<div style='font-family:IBM Plex Mono,monospace;font-size:22px;font-weight:700;color:#CC0000;margin-bottom:18px;'>MINET</div>"
            )
            st.markdown(f"""
            <div style='background:{BG2};border:1px solid {BORDER};border-radius:8px;padding:48px 32px;text-align:center;margin-top:24px;
                        box-shadow:{"0 0 40px #00000030" if dark else "0 2px 20px #0000000A"};'>
                {{_idle_logo_html}}
                <div style='font-family:IBM Plex Mono,monospace;font-size:10px;letter-spacing:3px;
                            color:{ACCENT};text-transform:uppercase;margin-bottom:6px;'>
                    PROJECT SENTINEL · CREATED BY CIA MINET
                </div>
                <div style='font-family:IBM Plex Mono,monospace;font-size:11px;letter-spacing:2px;
                            color:{TEXT3};margin-bottom:24px;'>
                    CORPORATE INTELLIGENCE ANALYTICS · MINET KENYA
                </div>
                <div style='width:64px;height:1px;background:{BORDER};margin:0 auto 24px auto;'></div>
                <div style='font-size:14px;color:{TEXT4};margin-bottom:6px;font-weight:500;'>
                    Configure scan parameters in the sidebar, then press the ignition button
                </div>
                <div style='font-family:IBM Plex Mono,monospace;font-size:11px;color:{TEXT5};letter-spacing:1.5px;'>
                    AWAITING EXECUTION · PROJECT SENTINEL v5.0
                </div>
                <div style='margin-top:28px;display:flex;justify-content:center;gap:28px;flex-wrap:wrap;'>
                    <div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:1.5px;color:{TEXT4};'>
                        <span style='color:#CC0000;font-size:14px;'>⬡</span><br>RISK
                    </div>
                    <div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:1.5px;color:{TEXT4};'>
                        <span style='color:#0066FF;font-size:14px;'>⬡</span><br>REINSURANCE
                    </div>
                    <div style='font-family:IBM Plex Mono,monospace;font-size:9px;letter-spacing:1.5px;color:{TEXT4};'>
                        <span style='color:#22C55E;font-size:14px;'>⬡</span><br>PEOPLE
                    </div>
                </div>
            </div>
            """.format(_idle_logo_html=_idle_logo_html), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("## Signal Detection Taxonomy")

            for sector, sigs in SECTOR_LAYERS.items():
                st.markdown(f"<div class='sector-layer'>▸ {sector}</div>", unsafe_allow_html=True)
                cols = st.columns(min(len(sigs), 3))
                for i, sig_type in enumerate(sigs):
                    meta = SIGNAL_TYPES[sig_type]
                    # Ensure text is visible in both themes
                    card_color = meta["color"] if dark else "#1E3A5F"
                    with cols[i % len(cols)]:
                        st.markdown(f"""
                        <div style='background:{BG2}; border:1px solid {BORDER}; border-left: 2px solid {meta["color"]};
                             padding: 10px 12px; border-radius: 3px; margin-bottom: 6px;'>
                            <div style='font-size:11px; font-family: IBM Plex Mono, monospace; color: {card_color}; letter-spacing:1px;'>
                                {meta["icon"]} {sig_type.replace("_", " ")}
                            </div>
                            <div style='font-size:10px; color: {TEXT3}; margin-top: 4px;'>{meta["urgency"]} PRIORITY</div>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("## Active Intelligence Sources")
            for region in ["KE", "EA", "AF"]:
                region_name = {"KE": "Kenya", "EA": "East Africa", "AF": "Pan-Africa"}[region]
                feeds = [f for f in RSS_FEEDS if f["region"] == region]
                st.markdown(f"<div style='font-family:IBM Plex Mono,monospace; font-size:10px; letter-spacing:1px; color:{TEXT4}; text-transform:uppercase; margin:12px 0 6px 0;'>{region_name} · {len(feeds)} feeds</div>", unsafe_allow_html=True)
                for feed in feeds:
                    domain = feed['url'].split('/')[2]
                    src_icon, src_color = SOURCE_TYPE_LABELS.get(feed.get("type","news"), ("📰", ACCENT))
                    st.markdown(f"""
                    <div style='font-size: 12px; color: {TEXT4}; padding: 4px 0;
                         border-bottom: 1px solid {BORDER}; font-family: IBM Plex Mono, monospace;'>
                        <span style='color:{src_color}; margin-right: 8px;'>{src_icon}</span>{domain}
                        <span style='float:right; color:{TEXT5}; font-size:10px;'>TIER {feed["tier"]}</span>
                    </div>
                    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════
    #  TAB 2 — RENEWAL CALENDAR
    # ══════════════════════════════════════════
    with tab_calendar:
        st.markdown("<h1>Renewal Calendar</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2>Policy renewals & key dates</h2>", unsafe_allow_html=True)
        st.markdown(f"<hr style='border-color:{BORDER}; margin: 8px 0 20px 0;'>", unsafe_allow_html=True)

        with st.expander("➕ Add Renewal Entry", expanded=False):
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                cal_client   = st.text_input("Client Name", key="cal_client")
                cal_policy   = st.text_input("Policy Type", key="cal_policy")
            with rc2:
                cal_renewal  = st.date_input("Renewal Date", key="cal_renewal")
                cal_premium  = st.text_input("Current Premium (KES)", key="cal_premium")
            with rc3:
                cal_contact  = st.text_input("Contact Person", key="cal_contact")
                cal_notes    = st.text_area("Notes", key="cal_notes", height=68)
            if st.button("Add to Calendar", key="add_cal"):
                if cal_client and cal_policy:
                    st.session_state.renewal_calendar.append({
                        "client": cal_client, "policy": cal_policy,
                        "renewal_date": str(cal_renewal), "premium": cal_premium,
                        "contact": cal_contact, "notes": cal_notes,
                        "added": datetime.now().strftime("%d %b %Y")
                    })
                    st.success("✓ Renewal entry added.")

        if st.session_state.renewal_calendar:
            today = date.today()
            sorted_entries = sorted(st.session_state.renewal_calendar, key=lambda x: x["renewal_date"])
            
            upcoming = [e for e in sorted_entries if e["renewal_date"] >= str(today)]
            overdue  = [e for e in sorted_entries if e["renewal_date"] < str(today)]

            if upcoming:
                st.markdown(f"<div class='sector-layer'>▸ UPCOMING RENEWALS · {len(upcoming)} ENTRIES</div>", unsafe_allow_html=True)
                for e in upcoming:
                    days_to = (date.fromisoformat(e["renewal_date"]) - today).days
                    urgency_color = "#F87171" if days_to <= 30 else "#FBBF24" if days_to <= 60 else "#34D399"
                    st.markdown(f"""
                    <div class='intel-card' style='margin-bottom:8px;'>
                        <div style='display:flex; justify-content:space-between;'>
                            <div>
                                <span style='font-size:15px; font-weight:600; color:{TEXT};'>{e['client']}</span>
                                <span style='font-family:IBM Plex Mono,monospace; font-size:11px; color:{TEXT3}; margin-left:12px;'>{e['policy']}</span>
                            </div>
                            <div style='text-align:right;'>
                                <span style='font-family:IBM Plex Mono,monospace; font-size:12px; color:{urgency_color};'>{e['renewal_date']}</span>
                                <span style='font-family:IBM Plex Mono,monospace; font-size:10px; color:{TEXT4}; margin-left:8px;'>in {days_to}d</span>
                            </div>
                        </div>
                        <div style='font-size:12px; color:{TEXT4}; margin-top:6px;'>
                            Premium: <b style='color:{TEXT2};'>{e.get('premium','—')} KES</b> &nbsp;·&nbsp;
                            Contact: <b style='color:{TEXT2};'>{e.get('contact','—')}</b>
                            {'&nbsp;·&nbsp;' + e.get('notes','') if e.get('notes') else ''}
                        </div>
                    </div>""", unsafe_allow_html=True)

            if overdue:
                st.markdown(f"<div class='sector-layer' style='border-color:#F87171; color:#F87171;'>▸ OVERDUE · {len(overdue)} ENTRIES</div>", unsafe_allow_html=True)
                for e in overdue:
                    st.markdown(f"""
                    <div class='intel-card' style='border-left-color:#F87171; margin-bottom:8px;'>
                        <span style='font-weight:600; color:{TEXT};'>{e['client']}</span>
                        <span style='font-family:IBM Plex Mono,monospace; font-size:11px; color:{TEXT3}; margin-left:10px;'>{e['policy']}</span>
                        <span style='float:right; font-family:IBM Plex Mono,monospace; font-size:12px; color:#F87171;'>OVERDUE · {e['renewal_date']}</span>
                    </div>""", unsafe_allow_html=True)
        else:
            st.info("No renewal entries yet. Add entries using the form above.")

    # ══════════════════════════════════════════
    #  TAB 3 — RELATIONSHIP GRAPH
    # ══════════════════════════════════════════
    with tab_graph:
        st.markdown("<h1>Relationship Intelligence Graph</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2>Detected entity relationships · auto-populated from scans</h2>", unsafe_allow_html=True)
        st.markdown(f"<hr style='border-color:{BORDER}; margin: 8px 0 20px 0;'>", unsafe_allow_html=True)

        with st.expander("➕ Manually Add Relationship", expanded=False):
            rg1, rg2, rg3 = st.columns(3)
            with rg1:
                rg_a = st.text_input("Minet Client (Entity A)", key="rg_a")
                rg_b = st.text_input("Prospect / Third Party (Entity B)", key="rg_b")
            with rg2:
                rg_type = st.selectbox("Link Type", [
                    "CLIENT", "PARTNER", "SUPPLIER", "INVESTOR", "JV", "SUBSIDIARY",
                    "COMPETITOR", "REGULATOR", "BUYER", "LENDER", "OTHER"
                ], key="rg_type")
            with rg3:
                rg_ev = st.text_area("Acquisition Opportunity / Notes", key="rg_ev", height=68)
            if st.button("Add Relationship", key="add_rel"):
                if rg_a and rg_b:
                    update_relationship_graph(rg_a, rg_b, rg_type, rg_ev)
                    st.success("✓ Relationship stored.")

        if st.session_state.relationship_graph:
            rels = list(st.session_state.relationship_graph.values())
            st.markdown(f"<div style='font-family:IBM Plex Mono,monospace; font-size:11px; color:{TEXT4}; margin-bottom:12px;'>{len(rels)} RELATIONSHIP{'S' if len(rels)>1 else ''} DETECTED &nbsp;·&nbsp; Entity A = Minet Client &nbsp;·&nbsp; Entity B = Acquisition Prospect</div>", unsafe_allow_html=True)

            table_rows = ""
            for r in sorted(rels, key=lambda x: x.get("count", 1), reverse=True):
                # Badge for relationship type
                table_rows += f"""<tr>
                    <td style='color:#34D399;font-weight:600;'>{r.get('minet_client', r.get('entity_a','—'))}</td>
                    <td style='color:{ACCENT};text-align:center;font-family:IBM Plex Mono,monospace;font-size:11px;'>{r.get('rel_type','—')}</td>
                    <td style='color:#FBBF24;font-weight:600;'>{r.get('prospect', r.get('entity_b','—'))}</td>
                    <td style='color:{TEXT2}; font-size:12px;'>{r.get('opportunity', r.get('evidence',''))[:120]}{'...' if len(r.get('opportunity', r.get('evidence','')))>120 else ''}</td>
                    <td style='color:{TEXT4};font-family:IBM Plex Mono,monospace;font-size:11px;'>{r.get('first_seen','—')}</td>
                    <td style='color:{TEXT3};font-family:IBM Plex Mono,monospace;font-size:11px;text-align:center;'>{r.get('count',1)}</td>
                </tr>"""

            st.markdown(f"""
            <table class='rel-table'>
                <tr>
                    <th>MINET CLIENT (A)</th>
                    <th>LINK TYPE</th>
                    <th>PROSPECT (B)</th>
                    <th>ACQUISITION OPPORTUNITY</th>
                    <th>FIRST SEEN</th>
                    <th>HITS</th>
                </tr>
                {table_rows}
            </table>""", unsafe_allow_html=True)

            st.download_button(
                "↓ Export Relationships (.json)",
                json.dumps(list(st.session_state.relationship_graph.values()), indent=2),
                "Minet_Relationships.json", mime="application/json"
            )
        else:
            st.info("No relationships detected yet. Run a scan to auto-populate this graph, or add manually above.")

    # ══════════════════════════════════════════
    #  TAB 4 — CLOSED LOOP TRACKER
    # ══════════════════════════════════════════
    with tab_tracker:
        st.markdown("<h1>Closed-Loop Action Tracker</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2>Track signal actions from detection to resolution</h2>", unsafe_allow_html=True)
        st.markdown(f"<hr style='border-color:{BORDER}; margin: 8px 0 20px 0;'>", unsafe_allow_html=True)

        if st.session_state.closed_loop_tracker:
            open_items   = [i for i in st.session_state.closed_loop_tracker if i["status"] == "OPEN"]
            closed_items = [i for i in st.session_state.closed_loop_tracker if i["status"] == "CLOSED"]

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Actions", len(st.session_state.closed_loop_tracker))
            c2.metric("Open", len(open_items))
            c3.metric("Closed", len(closed_items))

            st.markdown(f"<div class='sector-layer'>▸ OPEN ACTIONS · {len(open_items)}</div>", unsafe_allow_html=True)
            for idx, item in enumerate(open_items):
                urg_color = {"HIGH": "#F87171", "MEDIUM": "#FBBF24", "LOW": "#34D399"}.get(item.get("urgency","").upper(), TEXT3)
                sig_meta  = SIGNAL_TYPES.get(item.get("signal","").upper().replace(" ","_"), {})
                sig_color = sig_meta.get("color", ACCENT)
                src_url   = item.get("source_url", "")
                src_html  = (f"<a href='{src_url}' target='_blank' style='color:{ACCENT};font-family:IBM Plex Mono,monospace;"
                             f"font-size:10px;text-decoration:none;'>↗ VIEW ARTICLE</a>") if src_url.startswith("http") else ""

                col_info, col_btn = st.columns([5, 1])
                with col_info:
                    st.markdown(f"""
                    <div class='cl-card cl-open'>
                        <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;'>
                            <div style='display:flex;align-items:center;gap:8px;'>
                                <span style='font-size:15px;font-weight:600;color:{TEXT};'>{item['entity']}</span>
                                <span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:{urg_color};
                                      background:{"#2D0808" if item.get("urgency","")=="HIGH" else "#2D2000"};
                                      padding:2px 6px;border-radius:2px;'>{item.get('urgency','—')}</span>
                            </div>
                            <span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:{sig_color};
                                  border:1px solid {sig_color};padding:2px 6px;border-radius:2px;'>
                                {item.get('signal','—').replace('_',' ')}
                            </span>
                        </div>
                        <div style='font-size:12px;color:{TEXT2};line-height:1.5;margin-bottom:8px;'>{item.get('action','—')}</div>
                        <div style='display:flex;justify-content:space-between;align-items:center;'>
                            <span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:{TEXT4};'>
                                📅 Opened: <b>{item['opened']}</b>
                            </span>
                            {src_html}
                        </div>
                    </div>""", unsafe_allow_html=True)
                with col_btn:
                    if st.button("✓ Close", key=f"close_{idx}_{item['entity']}"):
                        item["status"] = "CLOSED"
                        item["closed"] = datetime.now().strftime("%d %b %Y %H:%M")
                        st.rerun()

            if closed_items:
                with st.expander(f"▸ Closed Actions ({len(closed_items)})"):
                    for item in closed_items:
                        src_url  = item.get("source_url","")
                        src_html = (f"<a href='{src_url}' target='_blank' style='color:{ACCENT};font-size:10px;"
                                    f"font-family:IBM Plex Mono,monospace;text-decoration:none;'>↗ ARTICLE</a>") if src_url.startswith("http") else ""
                        st.markdown(f"""
                        <div class='cl-card cl-closed' style='opacity:0.8;'>
                            <div style='display:flex;justify-content:space-between;align-items:center;'>
                                <span style='font-weight:600;color:{TEXT};'>{item['entity']}</span>
                                <span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:#34D399;'>✓ CLOSED</span>
                            </div>
                            <div style='font-size:10px;color:{TEXT3};font-family:IBM Plex Mono,monospace;margin-top:4px;'>
                                {item.get('signal','—').replace('_',' ')}
                            </div>
                            <div style='font-size:11px;color:{TEXT4};margin-top:6px;font-family:IBM Plex Mono,monospace;
                                  display:flex;justify-content:space-between;'>
                                <span>📅 Opened: {item['opened']} &nbsp;·&nbsp; Closed: {item.get('closed','—')}</span>
                                {src_html}
                            </div>
                        </div>""", unsafe_allow_html=True)
        else:
            st.info("No tracked actions yet. Click '✓ Add to Tracker' on any intelligence card after running a scan.")

    # ══════════════════════════════════════════
    #  TAB 5 — CLIENT RISK SCORES
    # ══════════════════════════════════════════
    with tab_risk:
        st.markdown("<h1>Prospect Risk & Opportunity Scores</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2>Acquisition priority intelligence · auto-enriched on each scan</h2>", unsafe_allow_html=True)
        st.markdown(f"<hr style='border-color:{BORDER}; margin: 8px 0 20px 0;'>", unsafe_allow_html=True)

        if st.session_state.client_risk_scores:
            sorted_prospects = sorted(
                st.session_state.client_risk_scores.items(),
                key=lambda x: x[1]["score"], reverse=True
            )

            # KPI strip
            total     = len(sorted_prospects)
            high_p    = sum(1 for _, d in sorted_prospects if d["score"] >= 6)
            med_p     = sum(1 for _, d in sorted_prospects if 3 <= d["score"] < 6)
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Prospects", total)
            k2.metric("Pursue Now 🔴", high_p)
            k3.metric("Schedule Call 🟡", med_p)
            st.markdown(f"<hr style='border-color:{BORDER}; margin:16px 0;'>", unsafe_allow_html=True)

            for prospect, data in sorted_prospects:
                badge         = get_risk_badge(data["score"])
                priority_lbl  = ("🔴 PURSUE NOW"    if data["score"] >= 6
                                  else "🟡 SCHEDULE CALL" if data["score"] >= 3
                                  else "🟢 MONITOR")

                clients   = ", ".join(data.get("minet_clients", [])) or "—"
                rels      = ", ".join(data.get("relationships", [])) or "—"
                signals_l = list(set(data.get("signals", [])))
                angles    = data.get("minet_angles", data.get("insurance_angles", []))  # backwards compat
                summaries = data.get("summaries", [])
                urls      = data.get("article_urls", [])
                modes     = ", ".join(data.get("scan_modes", [])) or "—"
                first_s   = data.get("first_seen", "—")
                last_u    = data.get("last_updated", "—")

                # Build signal badges safely
                sig_html = ""
                for s in signals_l:
                    meta = SIGNAL_TYPES.get(s.upper().replace(" ", "_"), {})
                    sc   = meta.get("color", ACCENT) if dark else "#1E3A5F"
                    bg   = "#0D1F3A" if dark else "#EFF6FF"
                    sig_html += ("<span style='background:" + bg + ";border:1px solid " + sc +
                                 ";color:" + sc + ";font-size:9px;padding:2px 6px;border-radius:2px;"
                                 "margin:2px;font-family:IBM Plex Mono,monospace;'>"
                                 + s.replace("_", " ") + "</span>")

                # Build article links safely
                links_html = ""
                for i2, url in enumerate(urls[:3]):
                    dom = url.split('/')[2] if url.count('/') >= 2 else url
                    links_html += ("<a href='" + url + "' target='_blank' style='color:" + ACCENT +
                                   ";font-family:IBM Plex Mono,monospace;font-size:10px;"
                                   "text-decoration:none;margin-right:12px;'>↗ " + dom + "</a>")

                latest_summary = summaries[-1] if summaries else ""
                best_angle     = angles[-1]    if angles    else ""

                # ── Build the card HTML using concatenation (safe, no nested f-string quotes) ──
                card  = "<div class='intel-card' style='margin-bottom:16px;'>"

                # Header
                card += ("<div style='display:flex;justify-content:space-between;"
                         "align-items:flex-start;margin-bottom:12px;'>"
                         "<div><div style='font-size:17px;font-weight:700;color:" + TEXT + ";margin-bottom:4px;'>"
                         + prospect + "</div>"
                         "<div style='display:flex;align-items:center;gap:8px;'>"
                         + badge +
                         "<span style='font-family:IBM Plex Mono,monospace;font-size:12px;color:" + TEXT3 + ";'>"
                         "Score: <b style='color:" + TEXT + ";'>" + str(data["score"]) + "</b></span>"
                         "<span style='font-size:12px;'>" + priority_lbl + "</span>"
                         "</div></div>"
                         "<div style='text-align:right;font-family:IBM Plex Mono,monospace;font-size:10px;color:" + TEXT4 + ";'>"
                         "<div>First seen: " + first_s + "</div>"
                         "<div>Last updated: " + last_u + "</div>"
                         "<div style='margin-top:4px;color:" + TEXT3 + ";'>Detected via: " + modes + "</div>"
                         "</div></div>")

                # Signal badges row
                if sig_html:
                    card += "<div style='margin-bottom:8px;'>" + sig_html + "</div>"

                # Two-column info row
                bg_green  = "#0A1A0A" if dark else "#F0FDF4"
                bdr_green = "#1A3A1C" if dark else "#BBF7D0"
                bg_blue   = "#0A0A1A" if dark else "#EFF6FF"
                bdr_blue  = "#1A1A3A" if dark else "#BFDBFE"
                card += ("<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px;'>"
                         "<div style='background:" + bg_green + ";border:1px solid " + bdr_green + ";"
                         "border-left:3px solid #22C55E;padding:10px 12px;border-radius:3px;'>"
                         "<div style='font-size:9px;letter-spacing:1.5px;color:#22C55E;"
                         "font-family:IBM Plex Mono,monospace;text-transform:uppercase;margin-bottom:4px;'>Connected via Minet Client</div>"
                         "<div style='font-size:13px;font-weight:600;color:" + TEXT + ";'>" + clients + "</div>"
                         "<div style='font-size:11px;color:" + TEXT3 + ";margin-top:2px;'>" + rels + "</div>"
                         "</div>"
                         "<div style='background:" + bg_blue + ";border:1px solid " + bdr_blue + ";"
                         "border-left:3px solid " + ACCENT + ";padding:10px 12px;border-radius:3px;'>"
                         "<div style='font-size:9px;letter-spacing:1.5px;color:" + ACCENT + ";"
                         "font-family:IBM Plex Mono,monospace;text-transform:uppercase;margin-bottom:4px;'>Signals Detected</div>"
                         "<div style='font-size:12px;color:" + TEXT2 + ";'>" + (", ".join(signals_l) or "—") + "</div>"
                         "</div></div>")

                # Summary
                if latest_summary:
                    card += ("<div style='margin-bottom:10px;'>"
                             "<div style='font-size:9px;letter-spacing:1.5px;color:" + TEXT4 + ";"
                             "font-family:IBM Plex Mono,monospace;text-transform:uppercase;margin-bottom:4px;'>Latest Signal Context</div>"
                             "<div style='font-size:12px;color:" + TEXT2 + ";line-height:1.5;'>" + latest_summary + "</div>"
                             "</div>")

                # Minet angle
                if best_angle:
                    bg_ang  = "#0D1F0E" if dark else "#F0FDF4"
                    bdr_ang = "#1A3A1C" if dark else "#BBF7D0"
                    card += ("<div style='background:" + bg_ang + ";border:1px solid " + bdr_ang + ";"
                             "border-left:3px solid #22C55E;padding:8px 12px;border-radius:3px;margin-bottom:10px;'>"
                             "<div style='font-size:9px;letter-spacing:1.5px;color:#4ADE80;"
                             "font-family:IBM Plex Mono,monospace;text-transform:uppercase;margin-bottom:3px;'>Minet Advisory Angle</div>"
                             "<div style='font-size:12px;color:" + TEXT2 + ";'>" + best_angle + "</div>"
                             "</div>")

                # Article links
                if links_html:
                    card += "<div style='margin-top:6px;'>" + links_html + "</div>"

                card += "</div>"
                st.markdown(card, unsafe_allow_html=True)

            col_reset, _ = st.columns([1, 3])
            with col_reset:
                if st.button("🗑 Reset Prospect Scores"):
                    st.session_state.client_risk_scores = {}
                    st.rerun()
        else:
            st.info("No prospect scores yet. Prospect scores populate automatically during Acquisition Mode and Full Intelligence scans.")

    # ══════════════════════════════════════════
    #  TAB 6 — SIGNAL ARCHIVE
    # ══════════════════════════════════════════
    with tab_archive:
        st.markdown("<h1>Signal Archive</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2>Saved intelligence scans · filter by date · {len(st.session_state.signal_archive)} scans stored</h2>", unsafe_allow_html=True)
        st.markdown(f"<hr style='border-color:{BORDER}; margin: 8px 0 20px 0;'>", unsafe_allow_html=True)

        if not st.session_state.signal_archive:
            st.info("No scans archived yet. Run a Sentinel scan and results will be automatically saved here.")
        else:
            archive = list(reversed(st.session_state.signal_archive))  # newest first

            # ── Filter controls ──
            all_dates  = sorted(set(e["date_label"] for e in archive), reverse=True)
            all_modes  = sorted(set(e["scan_mode"]  for e in archive))

            fc1, fc2, fc3 = st.columns([2, 2, 1])
            with fc1:
                sel_dates = st.multiselect("Filter by Date", options=all_dates, default=[], key="arch_dates")
            with fc2:
                sel_modes = st.multiselect("Filter by Mode", options=all_modes, default=[], key="arch_modes")
            with fc3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑 Clear Archive", key="clear_archive"):
                    st.session_state.signal_archive = []
                    st.rerun()

            filtered = archive
            if sel_dates:
                filtered = [e for e in filtered if e["date_label"] in sel_dates]
            if sel_modes:
                filtered = [e for e in filtered if e["scan_mode"] in sel_modes]

            st.markdown(f"<div style='font-family:IBM Plex Mono,monospace;font-size:10px;color:{TEXT4};letter-spacing:1px;margin:12px 0 8px 0;'>{len(filtered)} SCANS SHOWN</div>", unsafe_allow_html=True)

            for entry in filtered:
                mode_color = {"FULL INTELLIGENCE": ACCENT, "ACQUISITION MODE": "#22C55E", "RETENTION MODE": "#F59E0B"}.get(entry["scan_mode"], TEXT3)
                stats = entry.get("stats", {})

                with st.expander(
                    f"📅 {entry['date_label']} · {entry['time_label']}  ·  {entry['scan_mode']}  ·  "
                    f"{stats.get('total_signals',0)} signals · {stats.get('high_urgency',0)} high urgency · {stats.get('new_prospects',0)} prospects"
                ):
                    # Meta strip
                    st.markdown(f"""
                    <div style='display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;'>
                        <span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:{mode_color};
                              border:1px solid {mode_color};padding:2px 8px;border-radius:2px;'>{entry['scan_mode']}</span>
                        <span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:{TEXT4};'>
                            📡 {entry.get('sources_active',0)} sources active
                        </span>
                        <span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:{TEXT4};'>
                            🕐 {entry['ts']}
                        </span>
                    </div>""", unsafe_allow_html=True)

                    # Stats row
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.metric("Intelligence Items", stats.get('total_signals', 0))
                    sc2.metric("High Urgency", stats.get('high_urgency', 0))
                    sc3.metric("New Prospects", stats.get('new_prospects', 0))

                    st.markdown(f"<hr style='border-color:{BORDER};margin:12px 0;'>", unsafe_allow_html=True)

                    # Full report body
                    if entry.get("report_body"):
                        st.markdown(entry["report_body"])

                    # Download button for this archived scan
                    st.download_button(
                        "↓ Download this scan (.md)",
                        entry.get("report_body",""),
                        f"Minet_Archive_{entry['ts'].replace(':','-').replace(' ','_')}_{entry['scan_mode'].replace(' ','_')}.md",
                        mime="text/markdown",
                        key=f"dl_arch_{entry['ts']}"
                    )

    # ══════════════════════════════════════════
    #  TAB 7 — FEEDBACK
    # ══════════════════════════════════════════
    with tab_feedback:
        st.markdown("<h1>Intelligence Feedback Loop</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2>Signal quality ratings · helps refine future analysis</h2>", unsafe_allow_html=True)
        st.markdown(f"<hr style='border-color:{BORDER}; margin: 8px 0 20px 0;'>", unsafe_allow_html=True)

        if st.session_state.feedback_log:
            relevant   = [f for f in st.session_state.feedback_log if f["rating"] == "relevant"]
            not_useful = [f for f in st.session_state.feedback_log if f["rating"] == "not_useful"]

            f1, f2, f3 = st.columns(3)
            f1.metric("Total Ratings", len(st.session_state.feedback_log))
            f2.metric("Relevant", len(relevant))
            f3.metric("Not Useful", len(not_useful))

            precision = round(len(relevant) / len(st.session_state.feedback_log) * 100, 1) if st.session_state.feedback_log else 0
            st.markdown(f"""
            <div class='intel-card' style='margin: 16px 0;'>
                <div style='font-family:IBM Plex Mono,monospace; font-size:11px; color:{TEXT4}; margin-bottom:6px;'>INTELLIGENCE PRECISION SCORE</div>
                <div style='font-size:28px; font-weight:600; color:{"#34D399" if precision >= 70 else "#FBBF24" if precision >= 50 else "#F87171"};'>{precision}%</div>
            </div>""", unsafe_allow_html=True)

            with st.expander("▸ Feedback Log"):
                for fb in reversed(st.session_state.feedback_log):
                    color = "#34D399" if fb["rating"] == "relevant" else "#F87171"
                    icon  = "👍" if fb["rating"] == "relevant" else "👎"
                    st.markdown(f"""
                    <div style='font-size:12px; color:{TEXT3}; padding:4px 0; border-bottom:1px solid {BORDER};
                         font-family:IBM Plex Mono,monospace;'>
                        {icon} <span style='color:{TEXT};'>{fb['entity']}</span> · {fb['signal']} ·
                        <span style='color:{color};'>{fb['rating'].replace('_',' ').upper()}</span> · {fb['ts']}
                    </div>""", unsafe_allow_html=True)

            if st.button("🗑 Clear Feedback Log"):
                st.session_state.feedback_log = []
                st.rerun()
        else:
            st.info("No feedback yet. Use 👍/👎 buttons on intelligence cards to rate signal quality.")

    # ── Footer ──────────────────────────────────────────────────────────────────
    _footer_logo_b64 = get_logo_b64()
    _footer_logo_html = (
        f"<img src='data:image/png;base64,{_footer_logo_b64}' style='height:36px;object-fit:contain;display:block;margin:0 auto 12px auto;opacity:0.7;' />"
        if _footer_logo_b64 else ""
    )
    st.markdown(f"""
    <div style='
        margin-top: 60px;
        border-top: 1px solid {BORDER};
        padding: 28px 0 20px 0;
        text-align: center;
    '>
        {_footer_logo_html}
        <div style='
            font-family: IBM Plex Mono, monospace;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 4px;
            text-transform: uppercase;
            color: {"#CC0000" if dark else "#CC0000"};
            margin-bottom: 6px;
        '>
            ⬡ &nbsp; CIA SENTINEL ENGINE &nbsp; ⬡
        </div>
        <div style='
            font-family: IBM Plex Mono, monospace;
            font-size: 10px;
            letter-spacing: 2px;
            color: {TEXT4};
            margin-bottom: 4px;
        '>
            MINET KENYA INTELLIGENCE OPERATIONS
        </div>
        <div style='
            font-family: IBM Plex Mono, monospace;
            font-size: 10px;
            letter-spacing: 1px;
            color: {TEXT5};
        '>
            Created by &nbsp;<span style='color:{ACCENT};font-weight:600;'>LEWIS</span>
            &nbsp;·&nbsp; Powered by Llama 3.3-70B &nbsp;·&nbsp; Project Sentinel v5.0
        </div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()