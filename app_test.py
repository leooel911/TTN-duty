import streamlit as str_module
import streamlit as st
import os
import re
import io
import pandas as pd
from datetime import date, timedelta, datetime, timezone
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch
import time
import hashlib
import base64

matplotlib.use('Agg')

st.set_page_config(page_title="TTN Shift Producer", page_icon="700st.png", layout="centered")

TAIWAN_TZ = timezone(timedelta(hours=8))

DATA_DIR = os.path.join(os.getcwd(), "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

UNITS = {
    "TTN": {
        "駕駛": os.path.join(DATA_DIR, "TTN_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTN_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTN_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTN_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTN_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTN_shift_mapping_TA.xlsx")
        }
    },
    "TTC": {
        "駕駛": os.path.join(DATA_DIR, "TTC_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTC_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTC_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTC_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTC_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTC_shift_mapping_TA.xlsx")
        }
    },
    "TTS": {
        "駕駛": os.path.join(DATA_DIR, "TTS_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTS_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTS_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTS_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTS_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTS_shift_mapping_TA.xlsx")
        }
    }
}

LOG_FILE = os.path.join(DATA_DIR, "activity_log.txt")

MAINTENANCE_FLAGS = {
    "producer": os.path.join(DATA_DIR, "maintenance_producer.flag"),
    "window_filter": os.path.join(DATA_DIR, "maintenance_window.flag"),
    "exchange_filter": os.path.join(DATA_DIR, "maintenance_exchange.flag")
}

# --- 升級版毛玻璃視覺設計 (Glassmorphism & Advanced UI Styling) ---
st.markdown("""
<style>
    .stApp { 
        background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f172a 50%, #020617 100%) !important; 
        color: #F8FAFC !important; 
        background-attachment: fixed !important;
    }
    .block-container { padding: 4.5rem 1rem 3rem 1rem !important; max-width: 750px !important; }

    @keyframes online-green-pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.7); }
        70% { transform: scale(1.05); box-shadow: 0 0 0 8px rgba(74, 222, 128, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
    }

    .online-dot {
        width: 8px; height: 8px; background-color: #4ADE80; border-radius: 50%;
        display: inline-block; animation: online-green-pulse 2s infinite ease-in-out;
        box-shadow: 0 0 10px #4ADE80; margin: 0 8px; vertical-align: middle;
    }

    @keyframes test-env-breathe {
        0% { border-color: rgba(245, 158, 11, 0.5); box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37), inset 0 0 10px rgba(245, 158, 11, 0.1); background: rgba(39, 28, 12, 0.45); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
        50% { border-color: rgba(245, 158, 11, 0.9); box-shadow: 0 8px 32px 0 rgba(245, 158, 11, 0.2), inset 0 0 16px rgba(245, 158, 11, 0.3); background: rgba(59, 39, 12, 0.55); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); }
        100% { border-color: rgba(245, 158, 11, 0.5); box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37), inset 0 0 10px rgba(245, 158, 11, 0.1); background: rgba(39, 28, 12, 0.45); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
    }

    .test-env-banner {
        border: 1px solid rgba(245, 158, 11, 0.5); border-radius: 16px; padding: 12px 18px; margin-bottom: 1.5rem;
        text-align: center; animation: test-env-breathe 3s infinite ease-in-out; font-family: monospace;
    }
    .test-env-title { color: #FDE68A; font-size: 13px; font-weight: 800; letter-spacing: 1.5px; margin-bottom: 2px; text-transform: uppercase; text-shadow: 0 2px 8px rgba(245,158,11,0.4); }
    .test-env-sub { color: #FCD34D; font-size: 10px; font-weight: 600; letter-spacing: 1px; opacity: 0.9; }

    @keyframes maintenance-red-line-pulse {
        0% { background-color: #7F1D1D; box-shadow: 0 0 4px rgba(239, 68, 68, 0.2); }
        50% { background-color: #EF4444; box-shadow: 0 0 16px rgba(239, 68, 68, 0.8), 0 0 25px rgba(239, 68, 68, 0.4); }
        100% { background-color: #7F1D1D; box-shadow: 0 0 4px rgba(239, 68, 68, 0.2); }
    }

    @keyframes missing-data-pulse {
        0% { border-color: rgba(239, 68, 68, 0.5); box-shadow: 0 8px 32px 0 rgba(239, 68, 68, 0.2); background: rgba(30, 27, 27, 0.5); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
        50% { border-color: rgba(239, 68, 68, 0.9); box-shadow: 0 8px 32px 0 rgba(239, 68, 68, 0.4), inset 0 0 12px rgba(239, 68, 68, 0.3); background: rgba(45, 20, 20, 0.6); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); }
        100% { border-color: rgba(239, 68, 68, 0.5); box-shadow: 0 8px 32px 0 rgba(239, 68, 68, 0.2); background: rgba(30, 27, 27, 0.5); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
    }

    @keyframes blue-glow-pulse {
        0% { border-color: rgba(56, 189, 248, 0.3); box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37), inset 0 0 10px rgba(56, 189, 248, 0.1); background: rgba(15, 23, 42, 0.45); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
        50% { border-color: rgba(56, 189, 248, 0.7); box-shadow: 0 8px 32px 0 rgba(56, 189, 248, 0.25), inset 0 0 16px rgba(56, 189, 248, 0.2); background: rgba(30, 41, 59, 0.55); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); }
        100% { border-color: rgba(56, 189, 248, 0.3); box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37), inset 0 0 10px rgba(56, 189, 248, 0.1); background: rgba(15, 23, 42, 0.45); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); }
    }

    .missing-data-card {
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(239, 68, 68, 0.6) !important; border-radius: 16px;
        padding: 16px 20px; margin-bottom: 16px; animation: missing-data-pulse 2.5s infinite ease-in-out;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }

    .header-container { 
        display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;
        width: 100%; margin-bottom: 1.2rem; padding: 24px 20px;
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 20px; animation: blue-glow-pulse 2.5s infinite ease-in-out;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    .title-left-group { display: flex; flex-direction: column; align-items: center; gap: 6px; width: 100%; }
    .main-title { color: #F8FAFC !important; font-size: 22px; font-weight: 800; letter-spacing: 2px; margin: 0; font-family: monospace; display: flex; align-items: center; justify-content: center; text-shadow: 0 2px 12px rgba(56,189,248,0.4); }
    .title-subtitle { color: #FFFFFF; font-size: 12px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; font-family: monospace; margin-top: 4px; display: flex; align-items: center; justify-content: center; }

    .footer-badge-container { display: flex; justify-content: center; align-items: center; width: 100%; margin-top: 3rem; margin-bottom: 1rem; }
    .footer-badge-container div.stButton > button { 
        background: rgba(15, 23, 42, 0.4) !important; backdrop-filter: blur(12px) !important; -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(51, 65, 85, 0.5) !important; border-left: 2px solid #38BDF8 !important;
        color: #94A3B8 !important; font-size: 9px !important; font-weight: 600 !important; letter-spacing: 1.5px !important; 
        text-transform: uppercase !important; padding: 6px 14px !important; border-radius: 6px !important; box-shadow: 0 4px 16px rgba(0,0,0,0.2) !important;
        font-family: monospace !important; width: auto !important; margin: 0 auto !important; min-height: unset !important; transition: all 0.25s ease !important;
    }
    .footer-badge-container div.stButton > button:hover {
        border-color: #38BDF8 !important; color: #38BDF8 !important; background: rgba(30, 41, 59, 0.6) !important;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.25) !important; transform: translateY(-1px) !important;
    }

    .mode-selection-header { color: #F8FAFC; font-size: 12px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 12px; font-family: monospace; display: flex; align-items: center; gap: 8px; }
    .mode-selection-header::after { content: ''; flex: 1; height: 1px; background: rgba(255, 255, 255, 0.1); }

    .maintenance-card-box {
        background: rgba(39, 28, 12, 0.5);
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(234, 179, 8, 0.5); border-left: 4px solid #EAB308; border-radius: 16px;
        padding: 24px 20px; text-align: center; margin-top: 2rem; margin-bottom: 0rem; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    .maintenance-red-glow-line { height: 3px; width: 100%; background-color: #EF4444; border-radius: 4px; margin-top: 6px; margin-bottom: 2rem; animation: maintenance-red-line-pulse 3s infinite ease-in-out; }
    .maintenance-title { color: #FEF08A; font-size: 18px; font-weight: 800; letter-spacing: 1.5px; margin-bottom: 8px; font-family: monospace; text-shadow: 0 2px 8px rgba(234,179,8,0.3); }
    .maintenance-sub { color: #CA8A04; font-size: 10px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; font-family: monospace; opacity: 0.9; }

    .admin-bypass-banner {
        background: rgba(127, 29, 29, 0.45);
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(239, 68, 68, 0.5); border-left: 4px solid #F87171;
        color: #FEE2E2; padding: 10px 16px; border-radius: 12px; margin-bottom: 20px; font-family: monospace; font-size: 12px; font-weight: 700;
        display: flex; justify-content: space-between; align-items: center; box-shadow: 0 8px 32px 0 rgba(239, 68, 68, 0.15);
    }

    .admin-card-container {
        background: rgba(30, 41, 59, 0.45);
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #38BDF8; border-radius: 16px;
        padding: 20px; margin-bottom: 20px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }

    .telemetry-card { 
        background: rgba(30, 41, 59, 0.45) !important; 
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08) !important; border-left: 4px solid #3B82F6 !important; border-radius: 16px; padding: 16px 20px; margin-bottom: 16px; 
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); position: relative; overflow: hidden; 
    }
    .telemetry-title { color: #94A3B8 !important; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 1px; }
    .telemetry-value { color: #F8FAFC !important; font-size: 16px; font-weight: 700; font-family: monospace; }
    .telemetry-sub { margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.06); font-size: 12px; color: #94A3B8; font-family: monospace; line-height: 1.5; }

    .section-header-box { 
        background: rgba(30, 41, 59, 0.45); 
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #3B82F6; border-radius: 16px; padding: 18px 20px; margin-top: 20px; margin-bottom: 20px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); 
    }
    .section-title { color: #F8FAFC; font-size: 18px; font-weight: 700; letter-spacing: 0.5px; margin: 0; }
    .section-subtitle { color: #94A3B8; font-size: 11px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; font-family: monospace; }

    .date-banner { 
        background: rgba(30, 64, 175, 0.45); 
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(96, 165, 250, 0.3); border-left: 4px solid #60A5FA; color: #FFFFFF; font-size: 13px; font-weight: 800; padding: 10px 16px; border-radius: 12px; margin-top: 24px; margin-bottom: 12px; letter-spacing: 1px; text-transform: uppercase; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); 
        font-family: monospace;
    }

    .compact-card { 
        background: rgba(30, 41, 59, 0.45); 
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #3B82F6; border-radius: 14px; padding: 14px 18px; margin-bottom: 12px; color: #F8FAFC; transition: all 0.25s ease; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); 
    }
    .compact-card:hover { border-color: rgba(56, 189, 248, 0.5); box-shadow: 0 0 24px rgba(56, 189, 248, 0.2), 0 8px 32px rgba(0,0,0,0.5); transform: translateY(-2px); }

    .integrated-crew-box {
        background: rgba(30, 41, 59, 0.5);
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #10B981; border-radius: 14px 14px 0 0 !important;
        padding: 16px; margin-bottom: 0px !important; box-shadow: none !important;
    }

    .time-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .compact-time { font-size: 13px; font-weight: 700; color: #60A5FA; font-family: monospace; }
    .badge-group { display: flex; gap: 6px; align-items: center; }

    .long-badge { background: rgba(153, 27, 27, 0.3); border: 1px solid rgba(239, 68, 68, 0.5); color: #FCA5A5; font-size: 10px; padding: 2px 8px; border-radius: 6px; font-weight: 600; box-shadow: 0 0 10px rgba(239, 68, 68, 0.2); }
    .non-line-badge { background: rgba(76, 29, 149, 0.3); border: 1px solid rgba(139, 92, 246, 0.5); color: #C4B5FD; font-size: 10px; padding: 2px 8px; border-radius: 6px; font-weight: 600; box-shadow: 0 0 10px rgba(139, 92, 246, 0.2); }

    .compact-name { font-size: 15px; font-weight: 600; color: #E2E8F0; }
    .compact-sub { font-size: 11px; color: #94A3B8; font-family: monospace; margin-top: 3px; }

    .stRadio > label { display: none !important; }
    .stRadio > div { background: transparent !important; display: flex; flex-direction: column; gap: 10px; }
    .stRadio label { 
        background: rgba(30, 41, 59, 0.45) !important; 
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08) !important; 
        border-left: 4px solid #3B82F6 !important; border-radius: 14px !important; padding: 14px 18px !important; width: 100% !important; 
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important; transition: all 0.25s ease !important; cursor: pointer !important;
    }
    .stRadio label:hover {
        border-color: rgba(56, 189, 248, 0.5) !important; border-left-color: #38BDF8 !important;
        box-shadow: 0 0 24px rgba(56, 189, 248, 0.2), 0 8px 32px rgba(0,0,0,0.5) !important; transform: translateY(-2px) !important;
    }

    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #3B82F6 0%, #60A5FA 50%, #93C5FD 100%) !important;
        box-shadow: 0 0 16px rgba(59, 130, 246, 0.7), 0 0 8px rgba(96, 165, 250, 0.5) !important; border-radius: 6px;
    }
    .loading-status-text { font-family: monospace; font-size: 13px; color: #FB923C; letter-spacing: 0.5px; margin-bottom: 6px; font-weight: 700; text-shadow: 0 0 10px rgba(251, 146, 60, 0.4); }

    div.stButton > button, div.stFormSubmitButton > button { 
        font-weight: 700 !important; padding: 0.5rem 1rem !important; border-radius: 0.5rem !important; 
        background: rgba(30, 41, 59, 0.55) !important; 
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: #38BDF8 !important; width: 100% !important; 
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important; letter-spacing: 1px; font-family: monospace;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        border-color: rgba(56, 189, 248, 0.6) !important; color: #FFFFFF !important;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.85) 0%, rgba(29, 78, 216, 0.85) 100%) !important;
        box-shadow: 0 0 24px rgba(56, 189, 248, 0.4), 0 8px 32px rgba(0,0,0,0.5) !important; transform: translateY(-1px) !important;
    }

    div.stButton > button[kind="secondary"] { 
        border-radius: 0 0 14px 14px !important; 
        border-top: none !important;
        border-left: 4px solid #10B981 !important; 
        margin-top: -14px !important; 
        margin-bottom: 16px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2) !important;
    }
</style>
""", unsafe_allow_html=True)

NATIONAL_HOLIDAYS = {
    "1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", 
    "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節",
    "6/19": "端午節", "9/25": "中秋節", "9/28": "教師節", "10/10": "國慶日",
    "10/25": "台灣光復節", "12/25": "行憲紀念日"
}

TRANSPORT_PERIODS = {"9/24-9/29": "中秋疏運"}
TITLE = "TRAIN CREW DUTY CALENDAR"

ADMIN_PASSWORD = "Lf090000"
CREW_ACCESS_PASSWORD = "0096"

def set_module_maintenance(module_key, is_maint):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    flag_path = MAINTENANCE_FLAGS.get(module_key)
    if not flag_path: return
    if is_maint:
        with open(flag_path, "w") as f: f.write("ON")
    else:
        if os.path.exists(flag_path): os.remove(flag_path)

def is_module_maintenance(module_key):
    flag_path = MAINTENANCE_FLAGS.get(module_key)
    return os.path.exists(flag_path) if flag_path else False

def parse_device_info(ua_string):
    ua = ua_string.lower()
    if "iphone" in ua: device = "iPhone"
    elif "ipad" in ua: device = "iPad"
    elif "android" in ua:
        device = "Android Phone"
        if "build" in ua:
            try:
                parts = ua_string.split(";")
                for p in parts:
                    if "build" in p.lower(): device = f"Android ({p.split('Build')[0].strip()})"
            except: pass
    elif "macintosh" in ua or "mac os" in ua: device = "Mac"
    elif "windows" in ua: device = "Windows PC"
    else: device = "Desktop / Other"

    if "safari" in ua and "chrome" not in ua and "crios" not in ua: browser = "Safari"
    elif "chrome" in ua or "crios" in ua: browser = "Chrome"
    elif "line" in ua: browser = "LINE App"
    elif "edg" in ua: browser = "Edge"
    else: browser = "Browser"

    return f"{device} [{browser}]"

def log_activity(input_str):
    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        now_tw = datetime.now(TAIWAN_TZ).strftime('%Y-%m-%d %H:%M:%S')
        ua_raw = ""
        try: ua_raw = st.context.headers.get("user-agent", "")
        except: pass

        device_info = parse_device_info(ua_raw) if ua_raw else "未知裝置"
        current_operator = st.session_state.get("current_user_id", "未知")
        current_unit = st.session_state.get("current_unit", "TTN")
        log_entry = f"{now_tw} | 單位: {current_unit} | 操作者員編: {current_operator} | 裝置: {device_info} | 動作: {input_str}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(log_entry)
    except: pass

def render_zoomable_image(image_buf, caption=""):
    st.image(image_buf, use_container_width=True)

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "admin_logged_in" not in st.session_state: st.session_state["admin_logged_in"] = False
if "user_input_field" not in st.session_state: st.session_state["user_input_field"] = "A"
if "show_admin_login" not in st.session_state: st.session_state["show_admin_login"] = False
if "inspect_emp_target" not in st.session_state: st.session_state["inspect_emp_target"] = None
if "nav_mode" not in st.session_state: st.session_state["nav_mode"] = "home"
if "current_user_id" not in st.session_state: st.session_state["current_user_id"] = "A"
if "current_unit" not in st.session_state: st.session_state["current_unit"] = "TTN"

def get_current_role_files():
    unit = st.session_state.get("current_unit", "TTN")
    return UNITS.get(unit, UNITS["TTN"])

@st.cache_data(show_spinner=False)
def safe_read_excel_cached(file_path_or_bytes, header=None, file_mtime=None):
    try:
        if isinstance(file_path_or_bytes, str):
            if file_path_or_bytes.endswith('.xls'):
                return pd.read_excel(file_path_or_bytes, header=header, engine='xlrd')
            else:
                try:
                    return pd.read_excel(file_path_or_bytes, header=header, engine='openpyxl')
                except:
                    return pd.read_excel(file_path_or_bytes, header=header, engine='xlrd')
        else:
            file_bytes = file_path_or_bytes
            try:
                return pd.read_excel(io.BytesIO(file_bytes), header=header, engine='openpyxl')
            except:
                return pd.read_excel(io.BytesIO(file_bytes), header=header, engine='xlrd')
    except Exception as e:
        raise ValueError(f"無法解析 Excel 檔案格式 (錯誤: {e})")

def safe_read_excel(file_source, header=None):
    if isinstance(file_source, str) and os.path.exists(file_source):
        mtime = os.path.getmtime(file_source)
        return safe_read_excel_cached(file_source, header=header, file_mtime=mtime)
    elif hasattr(file_source, "getvalue"):
        return safe_read_excel_cached(file_source.getvalue(), header=header)
    else:
        return safe_read_excel_cached(file_source, header=header)

@st.cache_data(show_spinner=False)
def get_unit_member_set(unit_key, file_mtimes_tuple):
    unit_files = UNITS.get(unit_key, UNITS["TTN"])
    members = set()
    for role in ["駕駛", "列車長", "服勤員"]:
        path = unit_files[role]
        if os.path.exists(path):
            try:
                df = safe_read_excel(path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    emp_id = str(row.iloc[0]).strip().upper()
                    emp_name = str(row.iloc[1]).strip().upper()
                    if emp_id and emp_id != "NAN": members.add(emp_id)
                    if emp_name and emp_name != "NAN": members.add(emp_name)
            except: pass
    return members

def verify_crew_membership(unit_key, emp_input):
    unit_files = UNITS.get(unit_key, UNITS["TTN"])
    mtimes = []
    for role in ["駕駛", "列車長", "服勤員"]:
        p = unit_files[role]
        mtimes.append(os.path.getmtime(p) if os.path.exists(p) else 0)
    member_set = get_unit_member_set(unit_key, tuple(mtimes))
    clean_input = emp_input.strip().upper()
    return clean_input in member_set

def get_file_mtime_str(path):
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(TAIWAN_TZ)
        size_kb = os.path.getsize(path) / 1024
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({size_kb:.1f} KB)"
    return "尚無檔案"

def get_file_info_text(path, label_prefix="目前檔案"):
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(TAIWAN_TZ)
        size_kb = os.path.getsize(path) / 1024
        return f"📁 {label_prefix}：{os.path.basename(path)} | 大小：{size_kb:.1f} KB | 更新時間：{dt.strftime('%Y-%m-%d %H:%M:%S')}"
    return f"📁 {label_prefix}：尚無上傳檔案"

def get_schedule_range():
    active_files = get_current_role_files()
    for role in ["駕駛", "列車長", "服勤員"]:
        path = active_files[role]
        if os.path.exists(path):
            try:
                df = safe_read_excel(path, header=None)
                for r_idx in range(min(6, len(df))):
                    row_vals = [str(val).strip() for val in df.iloc[r_idx].values]
                    date_count = sum(1 for val in row_vals if re.search(r'\d{1,2}/\d{1,2}', val))
                    if date_count >= 3:
                        dates = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in df.iloc[r_idx].values if re.search(r'(\d+/\d+)', str(c))]
                        if dates: return f"{dates[0]} 至 {dates[-1]}"
            except: pass
    return "尚無資料"

def pad_time(t_str):
    if not t_str or ":" not in t_str: return t_str
    parts = str(t_str).split(":")
    return f"{int(parts[0]):02d}:{parts[1]}" if len(parts) == 2 else str(t_str)

def calculate_hours(start_str, end_str):
    if not start_str or not end_str or ":" not in start_str or ":" not in end_str: return ""
    try:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        start_mins = sh * 60 + sm
        end_mins = eh * 60 + em
        if end_mins <= start_mins: end_mins += 24 * 60
        diff_mins = end_mins - start_mins
        return f"{diff_mins // 60}h{diff_mins % 60:02d}m"
    except: return ""

def is_valid_train_code(tr):
    if not tr: return False
    tr_clean = str(tr).strip().upper()
    leave_codes = ["PAY", "FAC", "DO", "D2W", "AL", "SL", "CL", "ML"]
    if tr_clean in leave_codes or "OGC" in tr_clean: return False
    return bool(re.match(r'^[A-Z]+\d+', tr_clean))

def is_overtime(h, tr, note):
    if not is_valid_train_code(tr): return False
    if not h: return False
    try:
        p = str(h).replace("h", ":").replace("m", "").split(":")
        return (int(p[0]) * 60 + int(p[1])) > 510
    except: return False

def translate_train_code(tr):
    if not tr: return "無"
    tr_upper = str(tr).strip().upper()
    mapping = {"PAY": "特休 (PAY)", "FAC": "家庭照顧假 (FAC)", "AL": "年假 (AL)", "SL": "病假 (SL)", "CL": "事假 (CL)"}
    return mapping.get(tr_upper, tr)

def is_town_shift(tr, note):
    tr_upper = str(tr).strip().upper()
    note_upper = str(note).strip().upper()
    combined_text = f"{tr_upper} {note_upper}"
    
    if not tr or tr_upper in ["", "無", "NAN"]: 
        return True
    if tr_upper in ["PAY", "FAC"]: 
        return False
        
    keywords = ["TOWN", "STD", "TTN", "DTT", "OGT", "OGC", "FAC", "DS", "H9", "WRSL"]
    for kw in keywords:
        pattern = rf"\b{kw}\d*"
        if re.search(pattern, combined_text):
            return True
            
    if is_valid_train_code(tr_upper): 
        return False
        
    return True

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()

    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    lines = [l for l in lines if l != "."]

    if not lines: return dict(start="", train="", end="", hours="", note="")
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): return dict(start="", train=lines[0], end="", hours="", note="")

    start_time = pad_time(times[0]) if times else ""
    end_time = pad_time(times[1]) if len(times) > 1 else ""
    hours = calculate_hours(start_time, end_time)

    do_str = next((l for l in lines if "DO" in l or "D2W" in l or "PAY" in l or "FAC" in l), "")
    real_train = next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and l != do_str and "h" not in l and "m" not in l), "")
    if not real_train:
        non_time_lines = [l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and "h" not in l and "m" not in l]
        if non_time_lines: real_train = non_time_lines[0]

    notes = [l for l in lines if l not in times and l != real_train]

    clean_real_train = re.sub(r'[#%]', '', real_train).strip() if real_train else "無"

    return dict(start=start_time, end=end_time, train=clean_real_train if clean_real_train else "無", hours=hours, note=" ".join(notes))

def load_shift_mapping_dict(role_key="服勤員"):
    active_files = get_current_role_files()
    mapping_file = active_files["mapping"].get(role_key, active_files["mapping"]["服勤員"])
    mapping_dict = {}
    if os.path.exists(mapping_file):
        try:
            df = safe_read_excel(mapping_file)
            for _, row in df.iterrows():
                code = str(row.iloc[0]).strip().upper()
                start_t = str(row.iloc[1]).strip()
                end_t = str(row.iloc[2]).strip()
                hrs = str(row.iloc[3]).strip() if len(row) > 3 and not pd.isna(row.iloc[3]) else calculate_hours(start_t, end_t)
                if code and code != "NAN":
                    mapping_dict[code] = {
                        "start": pad_time(start_t),
                        "end": pad_time(end_t),
                        "hours": hrs
                    }
        except Exception as e:
            print(f"載入 {role_key} 班別對照表發生錯誤: {e}")
    return mapping_dict

def process_file_data(input_str):
    input_clean = input_str.strip().upper()
    matched_row, emp_id, emp_name, df_found = None, "", "", None
    active_files = get_current_role_files()

    for role in ["駕駛", "列車長", "服勤員"]:
        path = active_files[role]
        if os.path.exists(path):
            df_temp = safe_read_excel(path, header=3)
            df_temp.columns = [str(c).strip() for c in df_temp.columns]
            for idx, row in df_temp.iterrows():
                if str(row.iloc[0]).strip().upper() == input_clean or str(row.iloc[1]).strip().upper() == input_clean:
                    matched_row, emp_id, emp_name, df_found = row, str(row.iloc[0]).strip(), str(row.iloc[1]).strip(), df_temp
                    break
        if matched_row is not None: break
    if matched_row is None: raise ValueError(f"找不到員編或姓名為「{input_str}」的資料。")
    col_names = df_found.columns[2:]
    dates = []
    start_dt = date(2026, 2, 1)
    for i, col in enumerate(col_names):
        col_str = str(col).strip()
        match_d = re.search(r'(\d+/\d+)', col_str)
        if match_d:
            dates.append(match_d.group(1))
            if i == 0: m, d = map(int, match_d.group(1).split("/")); start_dt = date(2026, m, d)
        else: dates.append(col_str)
    return start_dt, dates, emp_id, emp_name, matched_row.iloc[2:].values

def draw_bold_text(ax, x, y, text, **kwargs):
    ax.text(x, y, text, **kwargs)
    offset = 0.0002
    ax.text(x + offset, y, text, **kwargs); ax.text(x, y + offset, text, **kwargs); ax.text(x - offset, y, text, **kwargs); ax.text(x, y - offset, text, **kwargs)

def parse_transport_periods(raw_periods, year=2026):
    expanded = {}
    for k, v in raw_periods.items():
        if "-" in k:
            parts = k.split("-")
            s_m, s_d = map(int, parts[0].strip().split("/")); e_m, e_d = map(int, parts[1].strip().split("/"))
            cur = date(year, s_m, s_d); end_dt = date(year, e_m, e_d)
            while cur <= end_dt: expanded[f"{cur.month}/{cur.day}"] = v; cur += timedelta(days=1)
        else: expanded[k.strip()] = v
    return expanded

def build_weeks(start_dt, dates, cells):
    first_wd = (start_dt.weekday() + 1) % 7
    weeks, week = [], [None] * first_wd
    for dt, raw in zip(dates, cells):
        week.append((dt, parse_cell(raw), str(raw) if not pd.isna(raw) else ""))
        if len(week) == 7: weeks.append(week); week = []
    if week:
        while len(week) < 7: week.append(None)
        weeks.append(week)
    return weeks

def setup_font():
    font_path = "NotoSansTC.ttf"
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        return fm.FontProperties(fname=font_path)
    return None

C_HDR, C_BORDER, C_EMPTY = "#0F172A", "#475569", "#F1F5F9"
C_WORK_BG, C_WEEKEND_BG = "#FFFFFF", "#F8FAFC"
C_DO_BG, C_PAY_BG, C_TOWN_BG = "#FFE4E6", "#FFEDD5", "#CBD5E1"
C_DO_TXT, C_PAY_TXT, C_HOLI_TXT, C_OT_TXT, C_NOTE_TXT = "#881337", "#9A3412", "#7C2D12", "#991B1B", "#4C1D95"
C_TOWN_TXT = "#000000"

# ==================== 最優先檢查：獨立檢視指定組員完整班表 (Inspector Mode) ====================
if st.session_state.get("inspect_emp_target") is not None:
    target_emp = st.session_state["inspect_emp_target"]
    current_unit = st.session_state.get("current_unit", "TTN")
    st.markdown(f"""
    <div class="section-header-box">
        <div class="section-title">[{current_unit}] 組員完整班表檢視: {target_emp}</div>
        <div class="section-subtitle">Inspection Mode // Full Schedule View</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("上一頁 (返回換假列表)"):
        st.session_state["inspect_emp_target"] = None
        st.rerun()

    try:
        start_dt, dates, emp_id, emp_name, cells = process_file_data(target_emp)
        active_transport = parse_transport_periods(TRANSPORT_PERIODS)
        font_prop = setup_font()
        def fp(size=9): return fm.FontProperties(fname=font_prop.get_file(), size=size) if font_prop else fm.FontProperties(size=size)

        weeks = build_weeks(start_dt, dates, cells)
        fig, ax = plt.subplots(figsize=(16, 11), dpi=300)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        fig.patch.set_facecolor("white")
        ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
        TW, CW = 1.0 - ML - MR, (1.0 - ML - MR) / 7
        RH = (1.0 - MT - MB - TH - DH) / len(weeks)
        ty = 1.0 - MT - TH
        ax.add_patch(FancyBboxPatch((ML, ty), TW, TH, boxstyle="square,pad=0", linewidth=0, facecolor=C_HDR))

        draw_bold_text(ax, ML + 0.008, ty + TH * 0.58, TITLE, ha="left", va="center", color="#FFFFFF", fontproperties=fp(16))
        draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"UNIT // {current_unit}    CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))

        badge_w = CW * 0.90
        badge_x = (1.0 - MR) - CW + (CW - badge_w) / 2
        badge_y = ty + TH * 0.42
        badge_h = 0.035

        ax.add_patch(FancyBboxPatch((badge_x, badge_y), badge_w, badge_h, boxstyle="round,pad=0.002,rounding_size=0.01", linewidth=1.0, edgecolor="#334155", facecolor="#1E293B"))
        draw_bold_text(ax, badge_x + badge_w / 2, badge_y + badge_h / 2, "Inspector | C.L.F", ha="center", va="center", color="#38BDF8", fontproperties=fp(10.5))

        dy = ty - DH
        for c in range(7):
            x = ML + c * CW
            ax.add_patch(FancyBboxPatch((x, dy), CW, DH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#475569", facecolor="#94A3B8"))
            draw_bold_text(ax, x + CW / 2, dy + DH / 2, ["SUN 星期日", "MON 星期一", "TUE 星期二", "WED 星期三", "THU 星期四", "FRI 星期五", "SAT 星期六"][c], ha="center", va="center", color="#000000", fontproperties=fp(11))

        has_emp_do, has_emp_pay, has_emp_ot, has_emp_town = False, False, False, False
        for week in weeks:
            for item in week:
                if item is not None:
                    dt, d, raw_cell_str = item
                    tr, note, hours = d["train"], d.get("note", ""), d.get("hours", "")
                    is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d["start"]
                    if is_pure_hol or tr.startswith("DO"): has_emp_do = True
                    elif tr in ["PAY", "FAC"] or "PAY" in raw_cell_str or "FAC" in raw_cell_str: has_emp_pay = True
                    elif is_town_shift(tr, note): has_emp_town = True
                    if is_overtime(hours, tr, note): has_emp_ot = True

        for ri, week in enumerate(weeks):
            ry = dy - (ri + 1) * RH
            for ci, item in enumerate(week):
                x = ML + ci * CW
                if item is None: 
                    ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=C_EMPTY))
                    continue
                dt, d, raw_cell_str = item
                tr, note = d["train"], d.get("note", "")

                is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d["start"]
                is_pay_shift = (tr in ["PAY", "FAC"]) or ("PAY" in raw_cell_str) or ("FAC" in raw_cell_str)

                bg = C_DO_BG if is_pure_hol else (C_PAY_BG if is_pay_shift else (C_TOWN_BG if is_town_shift(tr, note) else (C_WEEKEND_BG if ci in [0,6] else C_WORK_BG)))
                ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=bg))

                if dt in NATIONAL_HOLIDAYS:
                    full_date_str = f"{dt} ({NATIONAL_HOLIDAYS[dt]})"
                    draw_bold_text(ax, x + 0.005, ry + RH - 0.004, full_date_str, ha="left", va="top", color=C_HOLI_TXT, fontproperties=fp(9.5))
                else:
                    draw_bold_text(ax, x + 0.005, ry + RH - 0.004, dt, ha="left", va="top", color="#000000", fontproperties=fp(10))

                if dt in active_transport:
                    draw_bold_text(ax, x + CW - 0.004, ry + RH - 0.004, active_transport[dt], ha="right", va="top", color="#7C3AED", fontproperties=fp(8.5))

                if d.get("hours"): 
                    draw_bold_text(ax, x + CW - 0.004, ry + 0.003, f"({d['hours']})", ha="right", va="bottom", color=C_OT_TXT if is_overtime(d["hours"], tr, note) else "#000000", fontproperties=fp(11.5))
                    do_match = next((l for l in raw_cell_str.split('\n') if "DO" in l or "D2W" in l or "PAY" in l or "FAC" in l or "OGC" in l), "")
                    if do_match:
                        draw_bold_text(ax, x + CW - 0.004, ry + 0.026, do_match, ha="right", va="bottom", color=C_DO_TXT, fontproperties=fp(10.5))

                cx = x + CW / 2
                if is_pure_hol: 
                    do_code = next((l for l in raw_cell_str.split('\n') if "DO" in l or "D2W" in l), "DO")
                    draw_bold_text(ax, cx, ry + RH * 0.48, do_code, ha="center", va="center", color=C_DO_TXT, fontproperties=fp(14))
                elif is_pay_shift and not d["start"]: 
                    draw_bold_text(ax, cx, ry + RH * 0.48, tr, ha="center", va="center", color=C_PAY_TXT, fontproperties=fp(14))
                else:
                    draw_bold_text(ax, cx, ry + RH * 0.65, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                    draw_bold_text(ax, cx, ry + RH * 0.40, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                    draw_bold_text(ax, cx, ry + RH * 0.15, tr, ha="center", va="center", color=C_PAY_TXT if is_pay_shift else "#000000", fontproperties=fp(12))

        legend_y = MB * 0.45
        badge_w_leg, badge_h_leg = CW * 0.90, 0.022
        has_active_transport = any(d in active_transport for d in dates)
        has_active_holiday = any(d in NATIONAL_HOLIDAYS for d in dates)

        pill_legends = [
            (0, "#F1F5F9", "#475569", C_NOTE_TXT, "備註"),
            (1, C_DO_BG if has_emp_do else C_WORK_BG, "#E11D48" if has_emp_do else "#64748B", C_DO_TXT if has_emp_do else "#64748B", "休假日"),
            (2, C_PAY_BG if has_emp_pay else C_WORK_BG, "#EA580C" if has_emp_pay else "#64748B", C_PAY_TXT if has_emp_pay else "#64748B", "特休"),
            (3, C_WORK_BG, "#DC2626" if has_emp_ot else "#64748B", C_OT_TXT if has_emp_ot else "#64748B", "工時 > 8.5h"),
            (4, C_WORK_BG, "#C2410C" if has_active_holiday else "#64748B", C_HOLI_TXT if has_active_holiday else "#64748B", "國定假日"),
            (5, "#F3E8FF" if has_active_transport else C_WORK_BG, "#7C3AED" if has_active_transport else "#64748B", C_NOTE_TXT if has_active_transport else "#64748B", "疏運"),
            (6, C_TOWN_BG if has_emp_town else C_WORK_BG, "#334155" if has_emp_town else "#64748B", C_TOWN_TXT if has_emp_town else "#64748B", "非正線勤務"),
        ]

        for col_idx, bg_clr, border_clr, txt_clr, label in pill_legends:
            col_x = ML + col_idx * CW
            lx = col_x + (CW - badge_w_leg) / 2
            badge = FancyBboxPatch((lx, legend_y), badge_w_leg, badge_h_leg, boxstyle="round,pad=0.002,rounding_size=0.008", linewidth=1.2, edgecolor=border_clr, facecolor=bg_clr)
            ax.add_patch(badge)
            draw_bold_text(ax, lx + badge_w_leg / 2, legend_y + badge_h_leg / 2, label, ha="center", va="center", color=txt_clr, fontproperties=fp(9))

        now_str = datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M")
        draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // v4.20", ha="left", va="bottom", color="#0F172A", fontproperties=fp(12))
        draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str}", ha="right", va="bottom", color="#0F172A", fontproperties=fp(12))

        buf = io.BytesIO()
        plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()

        st.success(f"已成功載入 {emp_name} ({emp_id}) 之完整月班表")
        render_zoomable_image(buf)
        st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"TTN班表_{emp_name}.png", mime="image/png")
    except Exception as e:
        st.error(f"載入完整班表時發生錯誤: {e}")

    st.stop()

# --- 前置授權碼門戶檢查 ---
if not st.session_state["authenticated"] and not st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <div style="font-size: 32px; font-weight: 900; letter-spacing: 1.5px; color: #F8FAFC; font-family: monospace; text-shadow: 0 2px 16px rgba(56,189,248,0.4);">CREW DUTY ENGINE</div>
        <div style="color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-top: 8px; font-family: monospace; background: transparent !important;">
            BUSY DOING NOTHING PRODUCTIVE<br>
            C.L.F EDITION
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2.4, 1])
    with col2:
        with st.form("auth_form"):
            selected_unit = st.selectbox("選擇所屬單位", ["TTN", "TTC", "TTS"])
            entered_emp = st.text_input("使用者員編", value="A", placeholder="例如: 023300", max_chars=10)
            entered_key = st.text_input("系統授權碼", type="password", placeholder="請輸入系統授權碼...")
            btn_auth = st.form_submit_button("進入系統")

            if btn_auth:
                clean_emp = entered_emp.strip().upper()
                if not clean_emp: 
                    st.error("請輸入有效的員編")

                elif entered_key == "0900": 
                    st.session_state["authenticated"] = True
                    st.session_state["admin_logged_in"] = False 
                    st.session_state["current_unit"] = selected_unit
                    st.session_state["current_user_id"] = f"VIP_USER ({clean_emp if clean_emp != 'A' else '全域通行'})"
                    log_activity("VIP 身分登入系統")
                    st.rerun()

                elif entered_key == ADMIN_PASSWORD:
                    st.session_state["admin_logged_in"] = True
                    st.session_state["current_unit"] = selected_unit
                    st.session_state["current_user_id"] = f"ADMIN_{clean_emp}"
                    st.session_state["nav_mode"] = "admin_panel"
                    log_activity("管理員登入後台")
                    st.success("管理員驗證成功，正在載入後台...")
                    st.rerun()
                elif entered_key == CREW_ACCESS_PASSWORD:
                    is_member = verify_crew_membership(selected_unit, clean_emp)
                    if is_member:
                        st.session_state["authenticated"] = True
                        st.session_state["admin_logged_in"] = False
                        st.session_state["current_unit"] = selected_unit
                        st.session_state["current_user_id"] = clean_emp
                        log_activity("使用者登入系統")
                        st.rerun()
                    else:
                        st.error("非所屬單位組員，或輸入不存在的編號，請確認員編。")
                else: 
                    st.error("授權碼或密碼錯誤，請重新輸入")
    st.stop()

# --- 頂部質感標頭 ---
current_unit_label = st.session_state.get("current_unit", "TTN")
current_operator_id = st.session_state.get("current_user_id", "A")

st.markdown(f"""
<div class="header-container">
    <div class="title-left-group">
        <div class="main-title">CREW DUTY ENGINE</div>
        <div style="color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; font-family: monospace; margin-top: 6px; line-height: 1.6;">
            BUSY DOING NOTHING PRODUCTIVE<br>
            C.L.F EDITION
        </div>
        <div class="title-subtitle">
            <span class="online-dot"></span>HELLO WELCOME: {current_unit_label} | {current_operator_id}<span class="online-dot"></span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 測試環境呼吸燈警示橫幅 ---
st.markdown("""
<div class="test-env-banner">
    <div class="test-env-title">測試環境運行中（TEST ENVIRONMENT）</div>
    <div class="test-env-sub">目前為內部測試階段|(所屬運轉單位組員查詢使用)</div>
</div>
""", unsafe_allow_html=True)

if st.session_state.get("show_admin_login", False) and not st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">管理員身分驗證</div>
        <div class="section-subtitle">Administrator Security Verification</div>
    </div>
    """, unsafe_allow_html=True)

    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("admin_login_form"):
            adm_pwd_input = st.text_input("管理員密碼", type="password", placeholder="請輸入管理員解鎖密碼...", key="badge_admin_pwd_box")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1: btn_submit_adm = st.form_submit_button("登入後台")
            with col_btn2: btn_cancel_adm = st.form_submit_button("取消")

            if btn_submit_adm:
                if adm_pwd_input == ADMIN_PASSWORD:
                    st.session_state["admin_logged_in"] = True
                    st.session_state["nav_mode"] = "admin_panel"
                    st.session_state["show_admin_login"] = False
                    log_activity("管理員登入後台")
                    st.success("驗證成功，正在進入後台...")
                    st.rerun()
                else: st.error("管理員密碼錯誤")
            elif btn_cancel_adm:
                st.session_state["show_admin_login"] = False
                st.rerun()
    st.stop()

# ==================== 管理員專用：支援三單位的升級版 UI 控制台 ====================
if st.session_state.get("nav_mode") == "admin_panel" and st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">管理員專用：Database 智慧控制台</div>
        <div class="section-subtitle">Advanced Crew Duty Management & Data Maintenance Center</div>
    </div>
    """, unsafe_allow_html=True)

    admin_target_unit = st.selectbox("選擇要維護的營運單位", ["TTN", "TTC", "TTS"], index=["TTN", "TTC", "TTS"].index(st.session_state.get("current_unit", "TTN")), key="admin_target_unit_sel")
    st.session_state["current_unit"] = admin_target_unit
    current_unit_files = UNITS[admin_target_unit]

    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        if st.button("← 返回一般系統首頁", key="admin_back_to_home_btn"):
            st.session_state["nav_mode"] = "home"
            st.rerun()
    with col_ctrl2:
        if st.button("🔒 登出管理員身分", key="admin_logout_btn_top"):
            log_activity("管理員登出後台")
            st.session_state["admin_logged_in"] = False
            st.session_state["nav_mode"] = "home"
            st.rerun()

    st.markdown("---")

    st.subheader("各大系統模組維護開關控制")
    st.markdown("<p style='color:#94A3B8; font-size:12px;'>在此可獨立切換三大系統模組的維護狀態（開啟後一般組員端會顯示維護中畫面）。</p>", unsafe_allow_html=True)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        m_prod = st.checkbox("【個人月班表圖檔】維護中", value=is_module_maintenance("producer"), key="m_prod_chk")
        if m_prod != is_module_maintenance("producer"):
            set_module_maintenance("producer", m_prod)
            log_activity(f"切換個人月班表系統維護狀態: {m_prod}")
            st.rerun()
    with col_m2:
        m_win = st.checkbox("【換班時段快篩】維護中", value=is_module_maintenance("window_filter"), key="m_win_chk")
        if m_win != is_module_maintenance("window_filter"):
            set_module_maintenance("window_filter", m_win)
            log_activity(f"切換換班時段快篩系統維護狀態: {m_win}")
            st.rerun()
    with col_m3:
        m_ex = st.checkbox("【換假日期快篩】維護中", value=is_module_maintenance("exchange_filter"), key="m_ex_chk")
        if m_ex != is_module_maintenance("exchange_filter"):
            set_module_maintenance("exchange_filter", m_ex)
            log_activity(f"切換換假日期快篩系統維護狀態: {m_ex}")
            st.rerun()

    st.markdown("---")
    st.subheader(f"【{admin_target_unit}】伺服器即時處理動態與檔案健康狀態")

    col_stat1, col_stat2, col_stat3 = st.columns(3)

    with col_stat1:
        is_td_ready = os.path.exists(current_unit_files["駕駛"])
        td_status = "已就緒" if is_td_ready else "缺檔案"
        td_card_class = "telemetry-card" if is_td_ready else "missing-data-card"
        td_dot = '<span class="online-dot"></span>' if is_td_ready else '<span style="width: 8px; height: 8px; background-color: #EF4444; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #EF4444; margin: 0 8px; vertical-align: middle;"></span>'
        st.markdown(f"""
        <div class="{td_card_class}">
            <div class="telemetry-title">駕駛大表 (TD)</div>
            <div class="telemetry-value" style="font-size:13px;">{td_dot}{td_status}</div>
            <div class="telemetry-sub">{get_file_mtime_str(current_unit_files["駕駛"])}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_stat2:
        is_tm_ready = os.path.exists(current_unit_files["列車長"])
        tm_status = "已就緒" if is_tm_ready else "缺檔案"
        tm_card_class = "telemetry-card" if is_tm_ready else "missing-data-card"
        tm_dot = '<span class="online-dot"></span>' if is_tm_ready else '<span style="width: 8px; height: 8px; background-color: #EF4444; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #EF4444; margin: 0 8px; vertical-align: middle;"></span>'
        st.markdown(f"""
        <div class="{tm_card_class}">
            <div class="telemetry-title">列車長大表 (TM)</div>
            <div class="telemetry-value" style="font-size:13px;">{tm_dot}{tm_status}</div>
            <div class="telemetry-sub">{get_file_mtime_str(current_unit_files["列車長"])}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_stat3:
        is_ta_ready = os.path.exists(current_unit_files["服勤員"])
        ta_status = "已就緒" if is_ta_ready else "缺檔案"
        ta_card_class = "telemetry-card" if is_ta_ready else "missing-data-card"
        ta_dot = '<span class="online-dot"></span>' if is_ta_ready else '<span style="width: 8px; height: 8px; background-color: #EF4444; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px #EF4444; margin: 0 8px; vertical-align: middle;"></span>'
        st.markdown(f"""
        <div class="{ta_card_class}">
            <div class="telemetry-title">服勤員大表 (TA)</div>
            <div class="telemetry-value" style="font-size:13px;">{ta_dot}{ta_status}</div>
            <div class="telemetry-sub">{get_file_mtime_str(current_unit_files["服勤員"])}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(f"【{admin_target_unit}】班表維護控制台（黃金二窗口架構）")
    selected_role = st.selectbox("選擇目前要維護的職位類別", ["駕駛", "列車長", "服勤員"], index=2, key="admin_role_select_box")
    target_path = current_unit_files[selected_role]

    st.markdown("""
    <div style="display: flex; flex-direction: column; gap: 20px; margin-top: 15px;">
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown(f"""
        <div class="admin-card-container" style="border-left-color: #EAB308;">
            <h4 style="color: #FEF08A; margin-top: 0; font-size: 15px;">1. 每月 20 號基準大表（原始月班表底稿）</h4>
            <p style="color: #94A3B8; font-size: 12px; margin-bottom:0;">上傳每月初或 20 號發出的基準大表，作為系統的基礎排班框架。</p>
        </div>
        """, unsafe_allow_html=True)

        st.info(get_file_info_text(target_path, label_prefix="目前伺服器基準大表狀態"))

        uploaded_file_master = st.file_uploader(f"上傳【{admin_target_unit} - {selected_role}】基準大表 (.xlsx / .xls)", type=["xlsx", "xls", "csv"], key=f"master_up_{admin_target_unit}_{selected_role}")
        if uploaded_file_master is not None:
            file_bytes_m = uploaded_file_master.getvalue()
            current_hash_m = hashlib.md5(file_bytes_m).hexdigest()
            hash_key_m = f"master_hash_{admin_target_unit}_{selected_role}"

            if st.session_state.get(hash_key_m) != current_hash_m:
                try:
                    if not os.path.exists(DATA_DIR):
                        os.makedirs(DATA_DIR, exist_ok=True)
                    with open(target_path, "wb") as f: f.write(file_bytes_m)
                    st.session_state[hash_key_m] = current_hash_m
                    log_activity(f"上傳【{admin_target_unit} - {selected_role}】每月基準大表")
                    st.success(f"【{admin_target_unit} - {selected_role}】基準大表已成功更新！")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e: st.error(f"基準大表儲存失敗: {e}")

    with st.container():
        st.markdown(f"""
        <div class="admin-card-container" style="border-left-color: #10B981;">
            <h4 style="color: #34D399; margin-top: 0; font-size: 15px;">2. 本機運算完畢的「最新完整大表」更新（每日異動窗口）</h4>
            <p style="color: #94A3B8; font-size: 12px; margin-bottom:0;">當您在電腦端執行 Python 腳本完成多檔合併與時間對照後，直接將產出的**最終完整更新檔**上傳至此，即可直接覆蓋線上資料庫！</p>
        </div>
        """, unsafe_allow_html=True)

        st.info(get_file_info_text(target_path, label_prefix="目前正式資料庫狀態"))

        uploaded_file_update = st.file_uploader(f"上傳【{admin_target_unit} - {selected_role}】本機運算完畢的完整更新大表 (.xlsx)", type=["xlsx", "xls", "csv"], key=f"local_compiled_up_{admin_target_unit}_{selected_role}")

        if uploaded_file_update is not None:
            file_bytes_u = uploaded_file_update.getvalue()
            current_hash_u = hashlib.md5(file_bytes_u).hexdigest()
            hash_key_u = f"update_hash_{admin_target_unit}_{selected_role}"

            if st.session_state.get(hash_key_u) != current_hash_u:
                try:
                    if not os.path.exists(DATA_DIR):
                        os.makedirs(DATA_DIR, exist_ok=True)
                    with open(target_path, "wb") as f: f.write(file_bytes_u)
                    st.session_state[hash_key_u] = current_hash_u
                    log_activity(f"上傳本機運算完畢的【{admin_target_unit} - {selected_role}】完整更新大表")
                    st.success(f"【{admin_target_unit} - {selected_role}】資料庫已成功以本機運算檔更新完成！")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e: st.error(f"更新檔寫入失敗: {e}")

        col_rb_btn1, col_rb_btn2 = st.columns(2)
        with col_rb_btn1:
            if os.path.exists(target_path):
                with open(target_path, "rb") as f:
                    excel_bytes = f.read()
                st.download_button(
                    label=f"下載【{admin_target_unit} - {selected_role}】現行資料庫 (.xlsx)",
                    data=excel_bytes,
                    file_name=f"{admin_target_unit}_{selected_role}_database_{datetime.now(TAIWAN_TZ).strftime('%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_db_{admin_target_unit}_{selected_role}"
                )
        with col_rb_btn2:
            if os.path.exists(target_path):
                if st.button(f"清除【{admin_target_unit} - {selected_role}】的資料庫檔案", key=f"del_db_{admin_target_unit}_{selected_role}"):
                    os.remove(target_path)
                    log_activity(f"清除資料庫 [{admin_target_unit} - {selected_role}]")
                    st.success(f"已成功清除【{admin_target_unit} - {selected_role}】的資料庫檔案！")
                    time.sleep(0.5)
                    st.rerun()

    st.markdown("---")

    st.subheader("📋 系統操作活動紀錄日誌 (Activity Log)")

    col_log_1, col_log_2, col_log_3 = st.columns([1, 1, 2])
    with col_log_1:
        if st.button("🔄 重新載入日誌"): st.rerun()
    with col_log_2:
        if st.button("🗑️ 清空歷史日誌"):
            if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
            st.rerun()

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = f.readlines()

        st.caption(f"目前日誌總筆數：{len(logs)} 筆（下方顯示最新 30 筆）")

        parsed_logs = []
        for line in reversed(logs[-30:]):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5:
                parsed_logs.append({
                    "時間": parts[0],
                    "單位": parts[1].replace("單位: ", ""),
                    "操作者": parts[2].replace("操作者員編: ", ""),
                    "裝置": parts[3].replace("裝置: ", ""),
                    "動作/查詢": " | ".join(parts[4:]).replace("動作: ", "")
                })
            else:
                parsed_logs.append({
                    "時間": "格式化日誌",
                    "單位": "-",
                    "操作者": "-",
                    "裝置": "-",
                    "動作/查詢": line.strip()
                })

        if parsed_logs:
            df_log_display = pd.DataFrame(parsed_logs)
            st.dataframe(df_log_display, use_container_width=True, hide_index=True)
    else:
        st.info("尚無任何登入與操作紀錄")

    st.stop()

# ==================== 一般系統首頁介面 ====================
active_files = get_current_role_files()
missing_files = []
for role in ["駕駛", "列車長", "服勤員"]:
    path = active_files[role]
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        missing_files.append(role)

if missing_files:
    st.error(f"【{current_unit_label}】資料庫異常或尚無檔案：請洽管理員上傳！")

td_time = get_file_mtime_str(active_files["駕駛"])
tm_time = get_file_mtime_str(active_files["列車長"])
ta_time = get_file_mtime_str(active_files["服勤員"])
sched_range = get_schedule_range()

is_db_empty = len(missing_files) == 3
card_class = "missing-data-card" if missing_files else "telemetry-card"

st.markdown(f"""
<div class="{card_class}">
    <div class="telemetry-title">[{current_unit_label}] 目前系統排班週期 & 伺服器資料狀態</div>
    <div class="telemetry-value" style="font-size: 20px; color: {"#EF4444" if missing_files else "#60A5FA"}; margin-bottom: 6px;">
        {sched_range if not is_db_empty else "資料庫異常：請洽管理員！"}
    </div>
    <div class="telemetry-sub">
        - 駕駛更新：{td_time}<br>
        - 列車長更新：{tm_time}<br>
        - 服勤員更新：{ta_time}
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="mode-selection-header">Select Operation Mode // 請選擇系統模式</div>', unsafe_allow_html=True)
app_mode = st.radio("系統操作模式選擇", [
    "繪製個人月班表圖檔", 
    "換班｜指定時段組員名單快篩（Alpha測試版）",
    "換假｜日期快篩（Alpha測試版）"
], horizontal=False, label_visibility="collapsed")

if app_mode != "換假｜日期快篩（Alpha測試版）":
    st.session_state["ex_sub_mode"] = "search_form"
    st.session_state["last_app_mode"] = ""

st.markdown("---")

if app_mode == "繪製個人月班表圖檔":
    if is_module_maintenance("producer") and not st.session_state.get("admin_logged_in", False):
        st.markdown("""
        <div class="maintenance-card-box">
            <div class="maintenance-title">[ 系統維護中 ] 繪製個人月班表圖檔系統</div>
            <div class="maintenance-sub">C.L.F // MAINTENANCE MODE &bull; SYSTEM UPGRADING</div>
        </div>
        <div class="maintenance-red-glow-line"></div>
        """, unsafe_allow_html=True)
        st.stop()

    if st.session_state.get("admin_logged_in", False) and is_module_maintenance("producer"):
        st.markdown("""
        <div class="admin-bypass-banner">
            <span>[!] ADMIN BYPASS // 「個人班表」目前處於維護中，您正以管理員身分預覽</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">個人班表圖檔生成</div>
        <div class="section-subtitle">Personal Shift Schedule Image Generator</div>
    </div>
    """, unsafe_allow_html=True)

    target_input = st.text_input("輸入 員編 或 姓名 (例如: A023300 or 波莉)", value="A", key="user_input_field")

    if st.button("立即生成個人班表圖片檔"):
        current_input = st.session_state.get("user_input_field", "").strip()
        if not current_input: st.warning("請輸入員編或姓名")
        else:
            log_activity(f"生成個人班表圖檔查詢: {current_input}")
            if not any(os.path.exists(path) for path in active_files.values() if isinstance(path, str)): st.error("無班表資料")
            else:
                try:
                    _, _, _, temp_emp_name, _ = process_file_data(current_input)
                    first_name = temp_emp_name[1:] if len(temp_emp_name) > 1 else temp_emp_name

                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)

                    status_placeholder.markdown(f'<div class="loading-status-text">「{first_name}」的班表繪製中，請稍後...</div>', unsafe_allow_html=True)
                    progress_bar.progress(30)
                    time.sleep(0.4)

                    start_dt, dates, emp_id, emp_name, cells = process_file_data(current_input)
                    progress_bar.progress(70)
                    time.sleep(0.4)

                    active_transport = parse_transport_periods(TRANSPORT_PERIODS)
                    font_prop = setup_font()
                    def fp(size=9): return fm.FontProperties(fname=font_prop.get_file(), size=size) if font_prop else fm.FontProperties(size=size)

                    progress_bar.progress(90)
                    weeks = build_weeks(start_dt, dates, cells)
                    fig, ax = plt.subplots(figsize=(16, 11), dpi=300)
                    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
                    fig.patch.set_facecolor("white")
                    ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
                    TW, CW = 1.0 - ML - MR, (1.0 - ML - MR) / 7
                    RH = (1.0 - MT - MB - TH - DH) / len(weeks)
                    ty = 1.0 - MT - TH
                    ax.add_patch(FancyBboxPatch((ML, ty), TW, TH, boxstyle="square,pad=0", linewidth=0, facecolor=C_HDR))

                    draw_bold_text(ax, ML + 0.008, ty + TH * 0.58, TITLE, ha="left", va="center", color="#FFFFFF", fontproperties=fp(16))
                    draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"UNIT // {current_unit_label}    CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))

                    badge_w = CW * 0.90
                    badge_x = (1.0 - MR) - CW + (CW - badge_w) / 2
                    badge_y = ty + TH * 0.42
                    badge_h = 0.035

                    ax.add_patch(FancyBboxPatch((badge_x, badge_y), badge_w, badge_h, boxstyle="round,pad=0.002,rounding_size=0.01", linewidth=1.0, edgecolor="#334155", facecolor="#1E293B"))
                    draw_bold_text(ax, badge_x + badge_w / 2, badge_y + badge_h / 2, "Producer | C.L.F", ha="center", va="center", color="#38BDF8", fontproperties=fp(10.5))

                    dy = ty - DH
                    for c in range(7):
                        x = ML + c * CW
                        ax.add_patch(FancyBboxPatch((x, dy), CW, DH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#475569", facecolor="#94A3B8"))
                        draw_bold_text(ax, x + CW / 2, dy + DH / 2, ["SUN 星期日", "MON 星期一", "TUE 星期二", "WED 星期三", "THU 星期四", "FRI 星期五", "SAT 星期六"][c], ha="center", va="center", color="#000000", fontproperties=fp(11))

                    has_emp_do, has_emp_pay, has_emp_ot, has_emp_town = False, False, False, False
                    for week in weeks:
                        for item in week:
                            if item is not None:
                                dt, d, raw_cell_str = item
                                tr, note, hours = d["train"], d.get("note", ""), d.get("hours", "")
                                is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d["start"]

                                if is_pure_hol or tr.startswith("DO"): has_emp_do = True
                                elif tr in ["PAY", "FAC"] or "PAY" in raw_cell_str or "FAC" in raw_cell_str: has_emp_pay = True
                                elif is_town_shift(tr, note): has_emp_town = True
                                if is_overtime(hours, tr, note): has_emp_ot = True

                    for ri, week in enumerate(weeks):
                        ry = dy - (ri + 1) * RH
                        for ci, item in enumerate(week):
                            x = ML + ci * CW
                            if item is None: 
                                ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=C_EMPTY))
                                continue
                            dt, d, raw_cell_str = item
                            tr, note = d["train"], d.get("note", "")

                            is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d["start"]
                            is_pay_shift = (tr in ["PAY", "FAC"]) or ("PAY" in raw_cell_str) or ("FAC" in raw_cell_str)

                            bg = C_DO_BG if is_pure_hol else (C_PAY_BG if is_pay_shift else (C_TOWN_BG if is_town_shift(tr, note) else (C_WEEKEND_BG if ci in [0,6] else C_WORK_BG)))
                            ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=bg))

                            if dt in NATIONAL_HOLIDAYS:
                                full_date_str = f"{dt} ({NATIONAL_HOLIDAYS[dt]})"
                                draw_bold_text(ax, x + 0.005, ry + RH - 0.004, full_date_str, ha="left", va="top", color=C_HOLI_TXT, fontproperties=fp(9.5))
                            else:
                                draw_bold_text(ax, x + 0.005, ry + RH - 0.004, dt, ha="left", va="top", color="#000000", fontproperties=fp(10))

                            if dt in active_transport:
                                draw_bold_text(ax, x + CW - 0.004, ry + RH - 0.004, active_transport[dt], ha="right", va="top", color="#7C3AED", fontproperties=fp(8.5))

                            if d.get("hours"): 
                                draw_bold_text(ax, x + CW - 0.004, ry + 0.003, f"({d['hours']})", ha="right", va="bottom", color=C_OT_TXT if is_overtime(d["hours"], tr, note) else "#000000", fontproperties=fp(11.5))
                                do_match = next((l for l in raw_cell_str.split('\n') if "DO" in l or "D2W" in l or "PAY" in l or "FAC" in l or "OGC" in l), "")
                                if do_match:
                                    draw_bold_text(ax, x + CW - 0.004, ry + 0.026, do_match, ha="right", va="bottom", color=C_DO_TXT, fontproperties=fp(10.5))

                            cx = x + CW / 2
                            if is_pure_hol: 
                                do_code = next((l for l in raw_cell_str.split('\n') if "DO" in l or "D2W" in l), "DO")
                                draw_bold_text(ax, cx, ry + RH * 0.48, do_code, ha="center", va="center", color=C_DO_TXT, fontproperties=fp(14))
                            elif is_pay_shift and not d["start"]: 
                                draw_bold_text(ax, cx, ry + RH * 0.48, tr, ha="center", va="center", color=C_PAY_TXT, fontproperties=fp(14))
                            else:
                                draw_bold_text(ax, cx, ry + RH * 0.65, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                                draw_bold_text(ax, cx, ry + RH * 0.40, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                                draw_bold_text(ax, cx, ry + RH * 0.15, tr, ha="center", va="center", color=C_PAY_TXT if is_pay_shift else "#000000", fontproperties=fp(12))

                    legend_y = MB * 0.45
                    badge_w_leg, badge_h_leg = CW * 0.90, 0.022
                    has_active_transport = any(d in active_transport for d in dates)
                    has_active_holiday = any(d in NATIONAL_HOLIDAYS for d in dates)

                    pill_legends = [
                        (0, "#F1F5F9", "#475569", C_NOTE_TXT, "備註"),
                        (1, C_DO_BG if has_emp_do else C_WORK_BG, "#E11D48" if has_emp_do else "#64748B", C_DO_TXT if has_emp_do else "#64748B", "休假日"),
                        (2, C_PAY_BG if has_emp_pay else C_WORK_BG, "#EA580C" if has_emp_pay else "#64748B", C_PAY_TXT if has_emp_pay else "#64748B", "特休"),
                        (3, C_WORK_BG, "#DC2626" if has_emp_ot else "#64748B", C_OT_TXT if has_emp_ot else "#64748B", "工時 > 8.5h"),
                        (4, C_WORK_BG, "#C2410C" if has_active_holiday else "#64748B", C_HOLI_TXT if has_active_holiday else "#64748B", "國定假日"),
                        (5, "#F3E8FF" if has_active_transport else C_WORK_BG, "#7C3AED" if has_active_transport else "#64748B", C_NOTE_TXT if has_active_transport else "#64748B", "疏運"),
                        (6, C_TOWN_BG if has_emp_town else C_WORK_BG, "#334155" if has_emp_town else "#64748B", C_TOWN_TXT if has_emp_town else "#64748B", "非正線勤務"),
                    ]

                    for col_idx, bg_clr, border_clr, txt_clr, label in pill_legends:
                        col_x = ML + col_idx * CW
                        lx = col_x + (CW - badge_w_leg) / 2
                        badge = FancyBboxPatch((lx, legend_y), badge_w_leg, badge_h_leg, boxstyle="round,pad=0.002,rounding_size=0.008", linewidth=1.2, edgecolor=border_clr, facecolor=bg_clr)
                        ax.add_patch(badge)
                        draw_bold_text(ax, lx + badge_w_leg / 2, legend_y + badge_h_leg / 2, label, ha="center", va="center", color=txt_clr, fontproperties=fp(9))

                    now_str = datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M")
                    draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // v4.20", ha="left", va="bottom", color="#0F172A", fontproperties=fp(12))
                    draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str}", ha="right", va="bottom", color="#0F172A", fontproperties=fp(12))

                    buf = io.BytesIO()
                    plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()

                    progress_bar.progress(100)
                    status_placeholder.empty()
                    progress_bar.empty()

                    st.success("個人班表圖片生成成功")
                    render_zoomable_image(buf)
                    st.download_button("點此下載班表影像檔", data=buf, file_name=f"{current_unit_label}_班表_{emp_name}.png", mime="image/png")
                except Exception as e: st.error(f"錯誤：{e}")

elif app_mode == "換班｜指定時段組員名單快篩（Alpha測試版）":
    if is_module_maintenance("window_filter") and not st.session_state.get("admin_logged_in", False):
        st.markdown("""
        <div class="maintenance-card-box">
            <div class="maintenance-title">[ 系統維護中 ] 指定時段報到組員快篩系統</div>
            <div class="maintenance-sub">C.L.F // MAINTENANCE MODE &bull; SYSTEM UPGRADING</div>
        </div>
        <div class="maintenance-red-glow-line"></div>
        """, unsafe_allow_html=True)
        st.stop()

    if st.session_state.get("admin_logged_in", False) and is_module_maintenance("window_filter"):
        st.markdown("""
        <div class="admin-bypass-banner">
            <span>[!] ADMIN BYPASS // 「時段快篩」目前處於維護中，您正以管理員身分預覽</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">指定 Sign-In 時段組員名單快篩</div>
        <div class="section-subtitle">Duty Time Window & Sign-In Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2, key="win_selected_role")
    target_path = active_files[selected_role]

    if not os.path.exists(target_path):
        st.error(f"找不到【{current_unit_label} - {selected_role}】的班表檔案 ({target_path})，請先至管理員後台上傳")
    else:
        raw_df_preview = safe_read_excel(target_path, header=None)
        header_row_idx = 3
        for r_idx in range(min(6, len(raw_df_preview))):
            row_vals = [str(val).strip() for val in raw_df_preview.iloc[r_idx].values]
            date_count = sum(1 for val in row_vals if re.search(r'\d{1,2}/\d{1,2}', val))
            if date_count >= 3:
                header_row_idx = r_idx
                break

        df_search = safe_read_excel(target_path, header=header_row_idx)
        df_search.columns = [str(c).strip() for c in df_search.columns]

        date_cols = []
        for col in df_search.columns[2:]:
            match_d = re.search(r'(\d+/\d+)', str(col))
            if match_d: date_cols.append(match_d.group(1))

        if not date_cols: st.error("表中未偵測到有效日期欄位")
        else:
            TIME_OPTIONS = [f"{h:02d}:00" for h in range(19)]

            target_default = "03:00" if selected_role == "駕駛" else "05:00"
            earliest_default = target_default if target_default in TIME_OPTIONS else TIME_OPTIONS[0]
            default_min_idx = TIME_OPTIONS.index(earliest_default)

            role_selectbox_key = f"min_time_selectbox_{selected_role}"

            if "win_start_date" not in st.session_state:
                st.session_state["win_start_date"] = date_cols[0]
            if "win_end_date" not in st.session_state:
                st.session_state["win_end_date"] = date_cols[0]

            c1, c2 = st.columns(2)
            with c1: 
                start_date = st.selectbox("起始日期", date_cols, key="win_start_date")

            if st.session_state["win_end_date"] not in date_cols or date_cols.index(st.session_state["win_end_date"]) < date_cols.index(start_date):
                st.session_state["win_end_date"] = start_date

            with c2: 
                end_date = st.selectbox("結束日期", date_cols, key="win_end_date")

            c3, c4 = st.columns(2)
            with c3: 
                min_time = st.selectbox("Sign-In Time 區間：從", options=TIME_OPTIONS, index=default_min_idx, key=role_selectbox_key)

            to_time_options = ["-- (僅查單一時間點)"] + TIME_OPTIONS
            default_max_idx = 1 
            try:
                h_part = int(min_time.split(":")[0])
                target_next_h = h_part + 1
                if target_next_h <= 18:
                    target_next_str = f"{target_next_h:02d}:00"
                    if target_next_str in to_time_options:
                        default_max_idx = to_time_options.index(target_next_str)
                else:
                    default_max_idx = to_time_options.index("18:00")
            except:
                pass

            max_selectbox_key = f"max_time_selectbox_{selected_role}_{min_time}"

            with c4: 
                max_time_sel = st.selectbox("Sign-In Time 區間：到", options=to_time_options, index=default_max_idx, key=max_selectbox_key)

            filter_col1, filter_col2 = st.columns(2)
            with filter_col1: only_main_line = st.checkbox("僅顯示正線勤務", value=False, key="win_main_line")
            with filter_col2: only_long_shift = st.checkbox("僅顯示長班 (>8.5h)", value=False, key="win_long_shift")

            if st.button("開始區間檢索符合條件人員", key="btn_window_search"):
                log_activity(f"時段快篩 [{current_unit_label} - {selected_role}] {start_date}~{end_date} 從:{min_time} 到:{max_time_sel}")
                try:
                    s_idx = date_cols.index(start_date)
                    e_idx = date_cols.index(end_date)
                    target_dates = date_cols[s_idx:e_idx+1] if s_idx <= e_idx else []
                except: target_dates = []

                if not target_dates: st.warning("起始日期不可大於結束日期")
                else:
                    search_results = []
                    all_cols_list = list(df_search.columns[2:])

                    for _, row in df_search.iterrows():
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()
                        if not emp_id or emp_id.upper() == "NAN": continue

                        for d_str in target_dates:
                            target_col_idx = -1
                            actual_col_pos = -1
                            for idx, col in enumerate(all_cols_list):
                                if d_str in str(col):
                                    target_col_idx = idx + 2
                                    actual_col_pos = idx
                                    break

                            if target_col_idx != -1:
                                cell_raw = row.iloc[target_col_idx]
                                parsed = parse_cell(cell_raw)
                                start_t = parsed["start"]

                                if start_t:
                                    matched_time_cond = False
                                    if max_time_sel.startswith("--"):
                                        matched_time_cond = (start_t == min_time)
                                    else:
                                        matched_time_cond = (min_time <= start_t <= max_time_sel)

                                    if matched_time_cond:
                                        tr_upper = str(parsed["train"]).strip().upper()
                                        raw_cell_upper = str(cell_raw).upper()

                                        is_leave = (
                                            "PAY" in raw_cell_upper or 
                                            "FAC" in raw_cell_upper or 
                                            "AL" in raw_cell_upper or 
                                            "SL" in raw_cell_upper or 
                                            "CL" in raw_cell_upper or 
                                            tr_upper in ["PAY", "FAC", "AL", "SL", "CL", "DO", "D2W"]
                                        )

                                        is_non_line = is_town_shift(parsed["train"], parsed["note"])
                                        is_long = is_overtime(parsed["hours"], parsed["train"], parsed["note"])

                                        if only_main_line and is_non_line:
                                            continue
                                        if only_main_line and is_leave:
                                            continue
                                        if only_long_shift and not is_long:
                                            continue

                                        next_day_sign_in = "無記錄"
                                        if actual_col_pos + 1 < len(all_cols_list):
                                            next_cell_raw = row.iloc[target_col_idx + 1]
                                            next_parsed = parse_cell(next_cell_raw)
                                            if next_parsed["start"]: next_day_sign_in = next_parsed["start"]
                                            elif next_parsed["train"]: next_day_sign_in = next_parsed["train"]

                                        search_results.append({
                                            "日期": d_str, "員編": emp_id, "姓名": emp_name,
                                            "Sign-In": start_t, "收工時間": parsed["end"],
                                            "車次": translate_train_code(parsed["train"]),
                                            "隔日Sign-In": next_day_sign_in, "長班": is_long, "非正線": is_non_line
                                        })

                    search_results = sorted(search_results, key=lambda x: (date_cols.index(x["日期"]) if x["日期"] in date_cols else 999, str(x["Sign-In"]), str(x["收工時間"]), str(x["員編"])))
                    range_label_str = f"{start_date} 至 {end_date}" if start_date != end_date else start_date
                    time_label_str = f"時間 {min_time}" if max_time_sel.startswith("--") else f"區間 {min_time} ~ {max_time_sel}"

                    st.markdown(f"### 檢索結果：{range_label_str} ｜ {time_label_str}（共符合 {len(search_results)} 筆）")

                    if search_results:
                        current_date_group = None
                        c_col1, c_col2 = None, None
                        col_idx = 0 
                        for idx, r in enumerate(search_results):
                            if r["日期"] != current_date_group:
                                current_date_group = r["日期"]
                                st.markdown(f'<div class="date-banner">SERVICE DATE : {current_date_group}</div>', unsafe_allow_html=True)
                                c_col1, c_col2 = st.columns(2)
                                col_idx = 0 

                            badges_html = '<div class="badge-group">'
                            if r['長班']: badges_html += '<span class="long-badge">長班</span>'
                            if r['非正線']: badges_html += '<span class="non-line-badge">非正線</span>'
                            badges_html += '</div>'

                            card_html = f"""
                            <div class="integrated-crew-box" style="margin-bottom: 0px !important;">
                                <div class="time-header-row">
                                    <span class="compact-time">{r['Sign-In']} -> {r['收工時間']}</span>
                                    {badges_html}
                                </div>
                                <div class="compact-name" style="margin-top: 4px;">{r['姓名']} <span style="color:#94A3B8; font-size:12px;">({r['員編']})</span></div>
                                <div class="compact-sub" style="margin-top: 3px;">班別: {r['車次']}</div>
                                <div class="compact-sub" style="margin-top: 3px;">隔日勤務時間: {r['隔日Sign-In']}</div>
                            </div>
                            """

                            target_stream_col = c_col1 if (col_idx % 2 == 0) else c_col2
                            with target_stream_col:
                                st.markdown(card_html, unsafe_allow_html=True)
                                if st.button(f"查看 {r['姓名']} 完整班表", key=f"win_inspect_{r['員編']}_{r['日期']}_{idx}", use_container_width=True, type="secondary"):
                                    st.session_state["inspect_emp_target"] = r['員編']
                                    st.rerun()
                                    
                            col_idx += 1
                    else: st.info("在指定的日期與 Sign-In 區間內，沒有找到符合條件的人員")

elif app_mode == "換假｜日期快篩（Alpha測試版）":
    if st.session_state.get("last_app_mode") != "換假｜日期快篩（Alpha測試版）":
        if "ex_sub_mode" not in st.session_state: st.session_state["ex_sub_mode"] = "search_form"
        st.session_state["last_app_mode"] = "換假｜日期快篩（Alpha測試版）"

    if is_module_maintenance("exchange_filter") and not st.session_state.get("admin_logged_in", False):
        st.markdown("""
        <div class="maintenance-card-box">
            <div class="maintenance-title">[ 系統維護中 ] 換假日期快篩系統</div>
            <div class="maintenance-sub">C.L.F // MAINTENANCE MODE &bull; SYSTEM UPGRADING</div>
        </div>
        <div class="maintenance-red-glow-line"></div>
        """, unsafe_allow_html=True)
        st.stop()

    if st.session_state.get("admin_logged_in", False) and is_module_maintenance("exchange_filter"):
        st.markdown("""
        <div class="admin-bypass-banner">
            <span>[!] ADMIN BYPASS // 「換假快篩」目前處於維護中，您正以管理員身分預覽</span>
        </div>
        """, unsafe_allow_html=True)

    if "ex_sub_mode" not in st.session_state: st.session_state["ex_sub_mode"] = "search_form"
    if "ex_selected_emp" not in st.session_state: st.session_state["ex_selected_emp"] = None
    if "ex_saved_candidates" not in st.session_state: st.session_state["ex_saved_candidates"] = []
    if "ex_saved_target_date" not in st.session_state: st.session_state["ex_saved_target_date"] = ""
    if "ex_saved_return_date" not in st.session_state: st.session_state["ex_saved_return_date"] = ""
    if "ex_saved_role" not in st.session_state: st.session_state["ex_saved_role"] = ""
    if "ex_saved_time_filter" not in st.session_state: st.session_state["ex_saved_time_filter"] = "不限"

    if st.session_state["ex_sub_mode"] == "inspect_image":
        target_emp = st.session_state["ex_selected_emp"]
        saved_role = st.session_state.get("ex_saved_role", "服勤員")
        saved_date = st.session_state.get("ex_saved_target_date", "")

        st.markdown(f"""
        <div class="section-header-box">
            <div class="section-title">[{current_unit_label}] 換假組員完整班表檢視: {target_emp}</div>
            <div class="section-subtitle">Exchange Inspector Mode // [{saved_role}] 欲休假日期: {saved_date}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("← 返回上一頁"):
            st.session_state["ex_sub_mode"] = "results"
            st.rerun()

        st.markdown("---")
        try:
            current_input = target_emp
            log_activity(f"換假檢視完整班表: {current_input}")

            start_dt, dates, emp_id, emp_name, cells = process_file_data(current_input)
            active_transport = parse_transport_periods(TRANSPORT_PERIODS)
            font_prop = setup_font()
            def fp(size=9): return fm.FontProperties(fname=font_prop.get_file(), size=size) if font_prop else fm.FontProperties(size=size)

            weeks = build_weeks(start_dt, dates, cells)
            fig, ax = plt.subplots(figsize=(16, 11), dpi=300)
            ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
            fig.patch.set_facecolor("white")
            ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
            TW, CW = 1.0 - ML - MR, (1.0 - ML - MR) / 7
            RH = (1.0 - MT - MB - TH - DH) / len(weeks)
            ty = 1.0 - MT - TH
            ax.add_patch(FancyBboxPatch((ML, ty), TW, TH, boxstyle="square,pad=0", linewidth=0, facecolor=C_HDR))

            draw_bold_text(ax, ML + 0.008, ty + TH * 0.58, TITLE, ha="left", va="center", color="#FFFFFF", fontproperties=fp(16))
            draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"UNIT // {current_unit_label}    CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))

            badge_w = CW * 0.90
            badge_x = (1.0 - MR) - CW + (CW - badge_w) / 2
            badge_y = ty + TH * 0.42
            badge_h = 0.035

            ax.add_patch(FancyBboxPatch((badge_x, badge_y), badge_w, badge_h, boxstyle="round,pad=0.002,rounding_size=0.01", linewidth=1.0, edgecolor="#334155", facecolor="#1E293B"))
            draw_bold_text(ax, badge_x + badge_w / 2, badge_y + badge_h / 2, "Exchange | C.L.F", ha="center", va="center", color="#38BDF8", fontproperties=fp(10.5))

            dy = ty - DH
            for c in range(7):
                x = ML + c * CW
                ax.add_patch(FancyBboxPatch((x, dy), CW, DH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#475569", facecolor="#94A3B8"))
                draw_bold_text(ax, x + CW / 2, dy + DH / 2, ["SUN 星期日", "MON 星期一", "TUE 星期二", "WED 星期三", "THU 星期四", "FRI 星期五", "SAT 星期六"][c], ha="center", va="center", color="#000000", fontproperties=fp(11))

            has_emp_do, has_emp_pay, has_emp_ot, has_emp_town = False, False, False, False
            for week in weeks:
                for item in week:
                    if item is not None:
                        dt, d, raw_cell_str = item
                        tr, note, hours = d["train"], d.get("note", ""), d.get("hours", "")
                        is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d["start"]
                        if is_pure_hol or tr.startswith("DO"): has_emp_do = True
                        elif tr in ["PAY", "FAC"] or "PAY" in raw_cell_str or "FAC" in raw_cell_str: has_emp_pay = True
                        elif is_town_shift(tr, note): has_emp_town = True
                        if is_overtime(hours, tr, note): has_emp_ot = True

            for ri, week in enumerate(weeks):
                ry = dy - (ri + 1) * RH
                for ci, item in enumerate(week):
                    x = ML + ci * CW
                    if item is None: 
                        ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=C_EMPTY))
                        continue
                    dt, d, raw_cell_str = item
                    tr, note = d["train"], d.get("note", "")

                    is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d["start"]
                    is_pay_shift = (tr in ["PAY", "FAC"]) or ("PAY" in raw_cell_str) or ("FAC" in raw_cell_str)

                    bg = C_DO_BG if is_pure_hol else (C_PAY_BG if is_pay_shift else (C_TOWN_BG if is_town_shift(tr, note) else (C_WEEKEND_BG if ci in [0,6] else C_WORK_BG)))
                    ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=bg))

                    if dt in NATIONAL_HOLIDAYS:
                        full_date_str = f"{dt} ({NATIONAL_HOLIDAYS[dt]})"
                        draw_bold_text(ax, x + 0.005, ry + RH - 0.004, full_date_str, ha="left", va="top", color=C_HOLI_TXT, fontproperties=fp(9.5))
                    else:
                        draw_bold_text(ax, x + 0.005, ry + RH - 0.004, dt, ha="left", va="top", color="#000000", fontproperties=fp(10))

                    if dt in active_transport:
                        draw_bold_text(ax, x + CW - 0.004, ry + RH - 0.004, active_transport[dt], ha="right", va="top", color="#7C3AED", fontproperties=fp(8.5))

                    if d.get("hours"): 
                        draw_bold_text(ax, x + CW - 0.004, ry + 0.003, f"({d['hours']})", ha="right", va="bottom", color=C_OT_TXT if is_overtime(d["hours"], tr, note) else "#000000", fontproperties=fp(11.5))
                        do_match = next((l for l in raw_cell_str.split('\n') if "DO" in l or "D2W" in l or "PAY" in l or "FAC" in l or "OGC" in l), "")
                        if do_match:
                            draw_bold_text(ax, x + CW - 0.004, ry + 0.026, do_match, ha="right", va="bottom", color=C_DO_TXT, fontproperties=fp(10.5))

                    cx = x + CW / 2
                    if is_pure_hol: 
                        do_code = next((l for l in raw_cell_str.split('\n') if "DO" in l or "D2W" in l), "DO")
                        draw_bold_text(ax, cx, ry + RH * 0.48, do_code, ha="center", va="center", color=C_DO_TXT, fontproperties=fp(14))
                    elif is_pay_shift and not d["start"]: 
                        draw_bold_text(ax, cx, ry + RH * 0.48, tr, ha="center", va="center", color=C_PAY_TXT, fontproperties=fp(14))
                    else:
                        draw_bold_text(ax, cx, ry + RH * 0.65, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                        draw_bold_text(ax, cx, ry + RH * 0.40, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                        draw_bold_text(ax, cx, ry + RH * 0.15, tr, ha="center", va="center", color=C_PAY_TXT if is_pay_shift else "#000000", fontproperties=fp(12))

            legend_y = MB * 0.45
            badge_w_leg, badge_h_leg = CW * 0.90, 0.022
            has_active_transport = any(d in active_transport for d in dates)
            has_active_holiday = any(d in NATIONAL_HOLIDAYS for d in dates)

            pill_legends = [
                (0, "#F1F5F9", "#475569", C_NOTE_TXT, "備註"),
                (1, C_DO_BG if has_emp_do else C_WORK_BG, "#E11D48" if has_emp_do else "#64748B", C_DO_TXT if has_emp_do else "#64748B", "休假日"),
                (2, C_PAY_BG if has_emp_pay else C_WORK_BG, "#EA580C" if has_emp_pay else "#64748B", C_PAY_TXT if has_emp_pay else "#64748B", "特休"),
                (3, C_WORK_BG, "#DC2626" if has_emp_ot else "#64748B", C_OT_TXT if has_emp_ot else "#64748B", "工時 > 8.5h"),
                (4, C_WORK_BG, "#C2410C" if has_active_holiday else "#64748B", C_HOLI_TXT if has_active_holiday else "#64748B", "國定假日"),
                (5, "#F3E8FF" if has_active_transport else C_WORK_BG, "#7C3AED" if has_active_transport else "#64748B", C_NOTE_TXT if has_active_transport else "#64748B", "疏運"),
                (6, C_TOWN_BG if has_emp_town else C_WORK_BG, "#334155" if has_emp_town else "#64748B", C_TOWN_TXT if has_emp_town else "#64748B", "非正線勤務"),
            ]

            for col_idx, bg_clr, border_clr, txt_clr, label in pill_legends:
                col_x = ML + col_idx * CW
                lx = col_x + (CW - badge_w_leg) / 2
                badge = FancyBboxPatch((lx, legend_y), badge_w_leg, badge_h_leg, boxstyle="round,pad=0.002,rounding_size=0.008", linewidth=1.2, edgecolor=border_clr, facecolor=bg_clr)
                ax.add_patch(badge)
                draw_bold_text(ax, lx + badge_w_leg / 2, legend_y + badge_h_leg / 2, label, ha="center", va="center", color=txt_clr, fontproperties=fp(9))

            now_str = datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M")
            draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // v4.20", ha="left", va="bottom", color="#0F172A", fontproperties=fp(12))
            draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str}", ha="right", va="bottom", color="#0F172A", fontproperties=fp(12))

            buf = io.BytesIO()
            plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()

            st.success(f"已成功載入 {emp_name} ({emp_id}) 之完整月班表")
            render_zoomable_image(buf)
            st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"{current_unit_label}_班表_{emp_name}.png", mime="image/png")
        except Exception as e: st.error(f"載入完整班表時發生錯誤: {e}")
        st.stop()

    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">換假日期快篩系統</div>
        <div class="section-subtitle">Shift Exchange Date Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    ex_c1, ex_c2, ex_c3 = st.columns(3)
    with ex_c1:
        roles_list = ["服勤員", "駕駛", "列車長"]
        saved_role_val = st.session_state.get("ex_saved_role", "服勤員")
        default_role_idx = roles_list.index(saved_role_val) if saved_role_val in roles_list else 0
        selected_role = st.selectbox("選擇職位類別", roles_list, index=default_role_idx, key="ex_role_select")

    sample_path = active_files[selected_role] if os.path.exists(active_files[selected_role]) else list(active_files.values())[0]
    try:
        temp_df_dates = safe_read_excel(sample_path, header=3)
        date_cols = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in temp_df_dates.columns[2:] if re.search(r'(\d+/\d+)', str(c))]
    except: date_cols = []

    time_filter_options = [
        "不限", "05:00 以後", "06:00 以後", "07:00 以後", "08:00 以後", 
        "09:00 以後", "10:00 以後", "11:00 以後", "12:00 以後", 
        "13:00 以後", "14:00 以後", "15:00 以後", "16:00 以後"
    ]

    with ex_c2:
        if date_cols:
            saved_t_date = st.session_state.get("ex_saved_target_date", "")
            default_t_idx = date_cols.index(saved_t_date) if saved_t_date in date_cols else 0
            target_date = st.selectbox("想休假的日期", date_cols, index=default_t_idx, key=f"ex_target_date_{selected_role}")
        else: target_date = st.selectbox("想休假的日期", ["無可用日期"], index=0, key=f"ex_target_date_{selected_role}")

    with ex_c3:
        if date_cols:
            saved_r_date = st.session_state.get("ex_saved_return_date", "")
            default_r_idx = date_cols.index(saved_r_date) if saved_r_date in date_cols else min(1, len(date_cols)-1)
            return_date = st.selectbox("可還假的日期(上班日)", date_cols, index=default_r_idx, key=f"ex_return_date_{selected_role}")
        else: return_date = st.selectbox("可還假的日期(上班日)", ["無可用日期"], index=0, key=f"ex_return_date_{selected_role}")

    saved_time_f = st.session_state.get("ex_saved_time_filter", "不限")
    default_time_idx = time_filter_options.index(saved_time_f) if saved_time_f in time_filter_options else 0
    return_time_filter = st.selectbox(
        "還假日，可接受對方的報到時間限制（只列出 XX:XX 之後報到的班）",
        options=time_filter_options, index=default_time_idx, key="ex_return_time_filter"
    )

    new_selection_key = f"{selected_role}_{target_date}_{return_date}_{return_time_filter}"
    if "last_selection_signature" not in st.session_state: st.session_state["last_selection_signature"] = new_selection_key

    if st.session_state["ex_sub_mode"] != "results":
        if st.session_state["last_selection_signature"] != new_selection_key:
            st.session_state["ex_saved_candidates"] = []
            st.session_state["last_selection_signature"] = new_selection_key
    else: st.session_state["last_selection_signature"] = new_selection_key

    strict_limit = st.checkbox("嚴格過濾：排除前後 5 天內連續上班已達 6 天以上的人員", value=True, key="ex_strict_limit")

    is_selection_valid = True
    validation_error_msg = ""

    if date_cols and target_date != "無可用日期" and return_date != "無可用日期":
        if target_date == return_date:
            is_selection_valid = False
            validation_error_msg = "「想休假的日期」與「可還假的日期」不可選擇同一天！"
        else:
            try:
                year_val = 2026
                def get_sun_sat_week(d_str):
                    m, d = map(int, d_str.split("/"))
                    dt_obj = date(year_val, m, d)
                    w_day = (dt_obj.weekday() + 1) % 7
                    sun_date = dt_obj - timedelta(days=w_day)
                    sat_date = sun_date + timedelta(days=6)
                    return sun_date, sat_date

                t_sun, t_sat = get_sun_sat_week(target_date)
                r_sun, r_sat = get_sun_sat_week(return_date)

                if t_sun != r_sun:
                    is_selection_valid = False
                    validation_error_msg = "注意！『想休假日』與『可還假日』必須選擇在同一週內"
            except Exception as e:
                is_selection_valid = False
                validation_error_msg = f"日期解析發生錯誤: {e}"

    if not is_selection_valid: st.error(f"條件未通過：{validation_error_msg}")

    if is_selection_valid:
        if st.button("開始尋找可換假對象", key="btn_auto_search_exchange_fixed"):
            log_activity(f"換假快篩 [{current_unit_label} - {selected_role}] 想休:{target_date} 還假:{return_date}")
            st.session_state["ex_sub_mode"] = "results"
            try:
                target_path = active_files[selected_role]
                df_ex = safe_read_excel(target_path, header=3)
                df_ex.columns = [str(c).strip() for c in df_ex.columns]

                target_col_idx = -1
                return_col_idx = -1
                actual_pos = -1
                all_cols_list = list(df_ex.columns[2:])

                for idx, col in enumerate(all_cols_list):
                    c_str = str(col)
                    if target_date in c_str:
                        target_col_idx = idx + 2
                        actual_pos = idx
                    if return_date in c_str:
                        return_col_idx = idx + 2

                if target_col_idx == -1 or return_col_idx == -1:
                    st.warning("找不到指定日期的欄位資料")
                    st.session_state["ex_saved_candidates"] = []
                else:
                    candidates = []
                    for _, row in df_ex.iterrows():
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()

                        has_external_support = False
                        s_wk_idx = max(0, actual_pos - 3)
                        e_wk_idx = min(len(all_cols_list) - 1, actual_pos + 3)
                        for w_i in range(s_wk_idx, e_wk_idx + 1):
                            cell_check = str(row.iloc[w_i + 2]).strip().upper()
                            for line_item in cell_check.split('\n'):
                                line_trimmed = line_item.strip()
                                if re.match(r'^[IE]\d+[A-Z0-9]*$', line_trimmed):
                                    has_external_support = True
                                    break
                            if has_external_support: break
                        if has_external_support: continue

                        cell_target = row.iloc[target_col_idx]
                        parsed_target = parse_cell(cell_target)
                        raw_target_str = str(cell_target).upper()
                        tr_target = str(parsed_target["train"]).strip().upper()

                        is_target_do = ("DO" in raw_target_str) or ("D2W" in raw_target_str)
                        is_target_leave = (tr_target in ["PAY", "FAC", "AL", "SL", "CL"]) or ("PAY" in raw_target_str) or ("FAC" in raw_target_str)
                        if not (is_target_do and not is_target_leave): continue

                        cell_return = row.iloc[return_col_idx]
                        parsed_return = parse_cell(cell_return)
                        raw_return_str = str(cell_return).upper()
                        tr_return = str(parsed_return["train"]).strip().upper()

                        is_return_do = ("DO" in raw_return_str) or ("D2W" in raw_return_str)
                        is_return_leave = (tr_return in ["PAY", "FAC", "AL", "SL", "CL"]) or ("PAY" in raw_return_str) or ("FAC" in raw_return_str)
                        if is_return_do or is_return_leave: continue

                        if return_time_filter != "不限":
                            min_allowed_time = return_time_filter.split(" ")[0]
                            return_start_time = parsed_return["start"]
                            if not return_start_time or return_start_time < min_allowed_time: continue

                        s_idx = max(0, actual_pos - 5)
                        e_idx = min(len(all_cols_list) - 1, actual_pos + 5)
                        current_streak, max_streak = 0, 0

                        for p_i in range(s_idx, e_idx + 1):
                            c_val = row.iloc[p_i + 2]
                            p_res = parse_cell(c_val)
                            c_raw_str = str(c_val).upper()
                            c_tr = str(p_res["train"]).strip().upper()
                            is_c_rest = ("DO" in c_raw_str) or ("D2W" in c_raw_str)
                            is_c_special_leave = (c_tr in ["PAY", "FAC", "AL", "SL", "CL"]) or ("PAY" in c_raw_str) or ("FAC" in c_raw_str)

                            if is_c_rest and not is_c_special_leave: current_streak = 0
                            else:
                                current_streak += 1
                                if current_streak > max_streak: max_streak = current_streak

                        if strict_limit and max_streak >= 6: continue

                        disp_s = max(0, actual_pos - 7)
                        disp_e = min(len(all_cols_list) - 1, actual_pos + 7)
                        mini_schedule = []
                        for p_i in range(disp_s, disp_e + 1):
                            d_str = date_cols[p_i] if p_i < len(date_cols) else all_cols_list[p_i]
                            c_val = row.iloc[p_i + 2]
                            p_res = parse_cell(c_val)
                            c_raw_s = str(c_val).upper()
                            c_tr_s = str(p_res["train"]).strip().upper()
                            is_c_hol = ("DO" in c_raw_s) or ("D2W" in c_raw_s)
                            is_c_leave = (c_tr_s in ["PAY", "FAC", "AL", "SL", "CL"]) or ("PAY" in c_raw_s) or ("FAC" in c_raw_s) or ("特休" in c_raw_s)

                            if is_c_hol and not is_c_leave: shift_display = "休"
                            elif is_c_leave:
                                if "PAY" in c_raw_s or "特休" in c_raw_s: shift_display = "PAY"
                                elif "FAC" in c_raw_s: shift_display = "FAC"
                                else: shift_display = c_tr_s if c_tr_s else "特休"
                            else:
                                main_tr_code = str(p_res["train"]).strip()
                                if main_tr_code.upper().startswith("N") and p_res["start"] and p_res["end"]:
                                    shift_display = f"{p_res['start']}->{p_res['end']}"
                                else: shift_display = main_tr_code if main_tr_code and main_tr_code != "無" else (p_res["note"] if p_res["note"] else "班")
                            mini_schedule.append(f"{d_str}: {shift_display}")

                        candidates.append({
                            "員編": emp_id, "姓名": emp_name,
                            "當天狀態": f"想休 {target_date}(DO) ｜ 還假 {return_date}({parsed_return['start']+'->'+parsed_return['end'] if parsed_return['start'] else parsed_return['train']})",
                            "前後連續上班最大天數": max_streak,
                            "鄰近天數概況": " | ".join(mini_schedule)
                        })
                    st.session_state["ex_saved_candidates"] = candidates
                    st.session_state["ex_saved_target_date"] = target_date
                    st.session_state["ex_saved_return_date"] = return_date
                    st.session_state["ex_saved_role"] = selected_role
                    st.session_state["ex_saved_time_filter"] = return_time_filter
            except Exception as e: st.error(f"日期計算發生錯誤: {e}")
            st.rerun()
    else: st.button("修正上述日期後 開始查詢", disabled=True, key="btn_auto_search_exchange_disabled")

    if st.session_state["ex_sub_mode"] == "results" and st.session_state.get("ex_saved_candidates"):
        saved_candidates = st.session_state["ex_saved_candidates"]
        saved_date = st.session_state.get("ex_saved_target_date", target_date)
        saved_return_date = st.session_state.get("ex_saved_return_date", return_date)
        saved_role = st.session_state.get("ex_saved_role", selected_role)
        saved_time_f = st.session_state.get("ex_saved_time_filter", return_time_filter)

        st.markdown(f"""
        <div style="background: rgba(30, 41, 59, 0.45); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #38BDF8; border-radius: 16px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 8px 32px 0 rgba(0,0,0,0.37); display: flex; flex-direction: column; gap: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <span style="color: #F8FAFC; font-size: 16px; font-weight: 700; font-family: monospace;">【{current_unit_label} - {saved_role}】符合換假名單</span>
                <span style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38BDF8; font-size: 11px; padding: 2px 10px; border-radius: 6px; font-weight: 600; font-family: monospace;">共 {len(saved_candidates)} 位符合</span>
            </div>
            <div style="color: #94A3B8; font-size: 12px; font-family: monospace; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <span>想休日期：<strong style="color: #34D399;">{saved_date}</strong></span>
                <span style="color: #475569;">|</span>
                <span>可還假日期：<strong style="color: #60A5FA;">{saved_return_date}</strong></span>
                <span style="color: #475569;">|</span>
                <span>報到限制：<strong style="color: #F87171;">{saved_time_f}</strong></span>
            </div>
        </div>
        """, unsafe_allow_html=True)        

        for idx, cand in enumerate(saved_candidates):
            card_container = st.container()
            with card_container:
                st.markdown(f"""
                <div class="integrated-crew-box">
                    <div class="time-header-row">
                        <span class="compact-time" style="color: #34D399;">{cand['當天狀態']}</span>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <span class="non-line-badge" style="background: rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.4); color: #34D399;">連續上班風險度: {cand['前後連續上班最大天數']}天</span>
                        </div>
                    </div>
                    <div class="compact-name" style="margin-top: 4px;">{cand['姓名']} <span style="color:#94A3B8; font-size:12px;">({cand['員編']})</span></div>
                    <div class="compact-sub" style="margin-top: 6px; font-size: 11px; color: #CBD5E1;">前後動態: {cand['鄰近天數概況']}</div>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"查看 {cand['姓名']} ({cand['員編']}) 完整班表", key=f"ex_gen_img_btn_{cand['員編']}_{idx}", use_container_width=True, type="secondary"):
                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)
                    first_name = cand['姓名'][1:] if len(cand['姓名']) > 1 else cand['姓名']
                    status_placeholder.markdown(f'<div class="loading-status-text">「{first_name}」的班表繪製中，請稍後...</div>', unsafe_allow_html=True)
                    progress_bar.progress(40)
                    time.sleep(0.4)
                    progress_bar.progress(80)
                    time.sleep(0.3)
                    st.session_state["ex_selected_emp"] = cand['員編']
                    st.session_state["ex_sub_mode"] = "inspect_image"
                    progress_bar.progress(100)
                    time.sleep(0.2)
                    status_placeholder.empty()
                    progress_bar.empty()
                    st.rerun()

# --- 底部版本/管理員貼紙 ---
st.markdown('<div class="footer-badge-container">', unsafe_allow_html=True)
footer_badge_label = f"ADMIN PANEL [{current_unit_label}] // C.L.F EDITION" if st.session_state.get("admin_logged_in", False) else f"C.L.F EDITION [{current_unit_label}]"
if st.button(footer_badge_label, key="bottom_footer_edition_badge"):
    if st.session_state.get("admin_logged_in", False):
        if st.session_state["nav_mode"] == "home": st.session_state["nav_mode"] = "admin_panel"
        else: st.session_state["nav_mode"] = "home"
    else: st.session_state["show_admin_login"] = True
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)
