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
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(16, 185, 129, 0.4);
        border-left: 4px solid #10B981;
        border-radius: 14px 14px 0 0 !important;
        padding: 16px;
        margin-bottom: 0px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2) !important;
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
        margin-top: 0px !important; 
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
    mapping = {"PAY": "特休 (PAY)", "FAC": "家庭照顧假 (FAC)", "LEV": "公假 (LEV)", "MLP": "身理假 (MLP)", "MTR": "事假 (MTR)"}
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

# ==================== 絕對最優先檢查：獨立檢視指定組員完整班表 (Inspector Mode) ====================
if st.session_state.get("inspect_emp_target") is not None:
    target_emp = st.session_state["inspect_emp_target"]
    current_unit = st.session_state.get("current_unit", "TTN")

    st.markdown(f"""
    <div class="section-header-box">
        <div class="section-title">[{current_unit}] 組員完整班表檢視: {target_emp}</div>
        <div class="section-subtitle">Inspection Mode // Full Schedule View</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("上一頁 (返回快篩結果)"):
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
        draw_bold_text(ax, 1.0 - MR, MB
