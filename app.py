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

matplotlib.use('Agg')

st.set_page_config(page_title="TTN Shift Producer", page_icon="700st.png", layout="centered")

# --- 定義台灣時區 (GMT+8) ---
TAIWAN_TZ = timezone(timedelta(hours=8))

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    /* 調整頂部留白與整體畫面下移 */
    .block-container { padding: 4.5rem 1rem 3rem 1rem !important; }
    
    /* 呼吸燈外框動畫定義 (通用) */
    @keyframes header-pulse-glow {
        0% { 
            border-color: #1E293B; 
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), inset 0 0 0 rgba(56, 189, 248, 0); 
        }
        50% { 
            border-color: #38BDF8; 
            box-shadow: 0 4px 28px rgba(56, 189, 248, 0.25), 0 0 15px rgba(56, 189, 248, 0.15); 
        }
        100% { 
            border-color: #1E293B; 
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), inset 0 0 0 rgba(56, 189, 248, 0); 
        }
    }

    /* 登入卡片專屬精緻呼吸燈動畫 */
    @keyframes auth-card-pulse {
        0% { 
            border-color: #1E293B; 
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0px rgba(56, 189, 248, 0); 
        }
        50% { 
            border-color: #38BDF8; 
            box-shadow: 0 12px 40px rgba(56, 189, 248, 0.2), 0 0 20px rgba(56, 189, 248, 0.15); 
        }
        100% { 
            border-color: #1E293B; 
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6), 0 0 0px rgba(56, 189, 248, 0); 
        }
    }

    .auth-card-container {
        background: linear-gradient(135deg, #131C31 0%, #0F172A 100%);
        border: 1.5px solid #1E293B;
        border-radius: 16px;
        padding: 32px 28px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
        animation: auth-card-pulse 4s infinite ease-in-out;
        margin-top: 1rem;
    }

    /* 施工中紅色底線呼吸燈動畫定義 */
    @keyframes maintenance-red-line-pulse {
        0% { 
            background-color: #7F1D1D; 
            box-shadow: 0 0 4px rgba(239, 68, 68, 0.2); 
        }
        50% { 
            background-color: #EF4444; 
            box-shadow: 0 0 16px rgba(239, 68, 68, 0.8), 0 0 25px rgba(239, 68, 68, 0.4); 
        }
        100% { 
            background-color: #7F1D1D; 
            box-shadow: 0 0 4px rgba(239, 68, 68, 0.2); 
        }
    }

    /* 紅色外框呼吸燈動畫定義 */
    @keyframes missing-data-pulse {
        0% { 
            border-color: #7F1D1D; 
            box-shadow: 0 0 4px rgba(239, 68, 68, 0.2); 
        }
        50% { 
            border-color: #EF4444; 
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.8), inset 0 0 10px rgba(239, 68, 68, 0.4); 
        }
        100% { 
            border-color: #7F1D1D; 
            box-shadow: 0 0 4px rgba(239, 68, 68, 0.2); 
        }
    }

    .missing-data-card {
        background: linear-gradient(135deg, #1E1B1B 0%, #0F172A 100%) !important;
        border: 2px solid #EF4444 !important;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 16px;
        animation: missing-data-pulse 2.5s infinite ease-in-out;
    }

    /* 頂部導航總成 */
    .header-container { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        width: 100%; 
        margin-bottom: 1.5rem; 
        padding: 16px 22px;
        background: linear-gradient(135deg, #131C31 0%, #0F172A 100%);
        border: 1.5px solid #1E293B;
        border-radius: 12px;
        animation: header-pulse-glow 4s infinite ease-in-out;
    }
    .title-left-group {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .main-title { 
        color: #F8FAFC !important; 
        font-size: 20px; 
        font-weight: 800; 
        letter-spacing: 1.5px; 
        margin: 0; 
        font-family: monospace;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        background-color: #38BDF8;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px #38BDF8;
    }
    .title-subtitle {
        color: #64748B;
        font-size: 9.5px;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        font-family: monospace;
    }
    
    /* 底部低調精緻小貼紙按鈕樣式 */
    .footer-badge-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin-top: 3rem;
        margin-bottom: 1rem;
    }
    
    .footer-badge-container div.stButton > button { 
        background: #0B0F19 !important;
        border: 1px solid #1E293B !important;
        border-left: 2px solid #38BDF8 !important;
        color: #64748B !important; 
        font-size: 9px !important; 
        font-weight: 600 !important; 
        letter-spacing: 1.5px !important; 
        text-transform: uppercase !important; 
        padding: 4px 12px !important;
        border-radius: 4px !important;
        box-shadow: none !important;
        font-family: monospace !important;
        width: auto !important;
        margin: 0 auto !important;
        min-height: unset !important;
        transition: all 0.2s ease !important;
    }
    .footer-badge-container div.stButton > button:hover {
        border-color: #38BDF8 !important;
        color: #38BDF8 !important;
        background: #131C31 !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.15) !important;
        transform: translateY(-1px) !important;
    }

    /* 區塊小標題樣式 */
    .mode-selection-header {
        color: #64748B;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 10px;
        font-family: monospace;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .mode-selection-header::after {
        content: '';
        flex: 1;
        height: 1px;
        background: #1E293B;
    }

    /* 施工中卡片樣式 */
    .maintenance-card-box {
        background: linear-gradient(135deg, #271C0C 0%, #171005 100%);
        border: 1.5px solid #EAB308;
        border-left: 5px solid #EAB308;
        border-radius: 12px;
        padding: 24px 20px;
        text-align: center;
        margin-top: 2rem;
        margin-bottom: 0rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
    }
    .maintenance-red-glow-line {
        height: 3px;
        width: 100%;
        background-color: #EF4444;
        border-radius: 4px;
        margin-top: 6px;
        margin-bottom: 2rem;
        animation: maintenance-red-line-pulse 3s infinite ease-in-out;
    }
    .maintenance-title {
        color: #FEF08A;
        font-size: 20px;
        font-weight: 800;
        letter-spacing: 1.5px;
        margin-bottom: 8px;
        font-family: monospace;
    }
    .maintenance-sub {
        color: #CA8A04;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 3px;
        text-transform: uppercase;
        font-family: monospace;
    }

    .admin-bypass-banner {
        background: linear-gradient(135deg, #7F1D1D 0%, #450A0A 100%);
        border: 1px solid #EF4444;
        border-left: 5px solid #F87171;
        color: #FEE2E2;
        padding: 10px 16px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-family: monospace;
        font-size: 13px;
        font-weight: 700;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
    }

    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); position: relative; overflow: hidden; }
    .telemetry-card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: #3B82F6; }
    .telemetry-title { color: #94A3B8 !important; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .telemetry-value { color: #F8FAFC !important; font-size: 18px; font-weight: 700; font-family: monospace; }
    .telemetry-sub { margin-top: 10px; padding-top: 8px; border-top: 1px solid #334155; font-size: 13px; color: #94A3B8; }
    
    .section-header-box { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 5px solid #3B82F6; border-radius: 10px; padding: 16px 20px; margin-top: 20px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .section-title { color: #F8FAFC; font-size: 20px; font-weight: 700; letter-spacing: 0.5px; margin: 0; }
    .section-subtitle { color: #94A3B8; font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

    .date-banner { background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%); border-left: 5px solid #60A5FA; color: #FFFFFF; font-size: 15px; font-weight: 800; padding: 8px 14px; border-radius: 8px; margin-top: 24px; margin-bottom: 10px; letter-spacing: 1px; text-transform: uppercase; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }
    
    .compact-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 4px solid #3B82F6; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; color: #F8FAFC; transition: all 0.25s ease; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .compact-card:hover { border-color: #38BDF8; box-shadow: 0 0 16px rgba(56, 189, 248, 0.25), 0 6px 16px rgba(0,0,0,0.5); transform: translateY(-2px); }

    .integrated-crew-box {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-left: 4px solid #10B981;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
        transition: all 0.25s ease;
    }
    .integrated-crew-box:hover {
        border-color: #34D399;
        box-shadow: 0 0 20px rgba(52, 211, 153, 0.2), 0 6px 16px rgba(0,0,0,0.5);
    }
    .action-divider {
        height: 1px;
        background: #334155;
        margin: 12px 0 4px 0;
    }

    .time-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .compact-time { font-size: 14px; font-weight: 700; color: #60A5FA; font-family: monospace; }
    .badge-group { display: flex; gap: 4px; align-items: center; }
    
    .long-badge { background: rgba(153, 27, 27, 0.4); border: 1px solid #EF4444; color: #FCA5A5; font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; box-shadow: 0 0 8px rgba(239, 68, 68, 0.4); }
    .non-line-badge { background: rgba(76, 29, 149, 0.4); border: 1px solid #8B5CF6; color: #C4B5FD; font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; box-shadow: 0 0 8px rgba(139, 92, 246, 0.4); }
    
    .compact-name { font-size: 15px; font-weight: 600; color: #E2E8F0; }
    .compact-sub { font-size: 12px; color: #94A3B8; font-family: monospace; margin-top: 2px; }

    .stRadio > label { display: none !important; }
    .stRadio > div { background: transparent !important; display: flex; flex-direction: column; gap: 12px; }
    .stRadio label { 
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; 
        border: 1px solid #334155 !important; 
        border-left: 4px solid #3B82F6 !important; 
        border-radius: 10px !important; 
        padding: 16px 20px !important; 
        width: 100% !important; 
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.25s ease !important;
        cursor: pointer !important;
    }
    .stRadio label:hover {
        border-color: #38BDF8 !important;
        border-left-color: #38BDF8 !important;
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.25), 0 6px 16px rgba(0,0,0,0.5) !important;
        transform: translateY(-2px) !important;
    }

    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #3B82F6 0%, #60A5FA 50%, #93C5FD 100%) !important;
        box-shadow: 0 0 16px rgba(59, 130, 246, 0.9), 0 0 8px rgba(96, 165, 250, 0.7) !important;
        border-radius: 6px;
    }
    .loading-status-text {
        font-family: monospace;
        font-size: 14px;
        color: #FB923C;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
        font-weight: 700;
        text-shadow: 0 0 10px rgba(251, 146, 60, 0.5);
    }

    div.stButton > button, div.stFormSubmitButton > button { 
        font-weight: 700 !important; 
        padding: 12px 18px !important; 
        border-radius: 10px !important; 
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; 
        border: 1px solid #334155 !important;
        border-left: 4px solid #38BDF8 !important;
        color: #F8FAFC !important; 
        width: 100% !important; 
        margin-top: 6px !important;
        margin-bottom: 6px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        letter-spacing: 1.5px;
        font-family: monospace;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        border-color: #38BDF8 !important;
        border-left-color: #38BDF8 !important;
        color: #FFFFFF !important;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.4), 0 6px 16px rgba(0,0,0,0.5) !important;
        transform: translateY(-2px) !important;
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

ROLE_FILES = {
    "駕駛": "TD.xlsx",
    "列車長": "TM.xlsx",
    "服勤員": "TA.xlsx"
}

ADMIN_PASSWORD = "Lf0900"
CREW_ACCESS_PASSWORD = "0900"
LOG_FILE = "activity_log.txt"

MAINTENANCE_FLAGS = {
    "producer": "maintenance_producer.flag",
    "window_filter": "maintenance_window.flag",
    "exchange_filter": "maintenance_exchange.flag"
}

def set_module_maintenance(module_key, is_maint):
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
                    if "build" in p.lower():
                        device = f"Android ({p.split('Build')[0].strip()})"
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
        now_tw = datetime.now(TAIWAN_TZ).strftime('%Y-%m-%d %H:%M:%S')
        ua_raw = ""
        try: ua_raw = st.context.headers.get("user-agent", "")
        except: pass
        
        device_info = parse_device_info(ua_raw) if ua_raw else "未知裝置"
        current_operator = st.session_state.get("current_user_id", "未知")
        log_entry = f"{now_tw} | 操作者員編: {current_operator} | 裝置: {device_info} | 查詢: {input_str}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(log_entry)
    except: pass

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "admin_logged_in" not in st.session_state: st.session_state["admin_logged_in"] = False
if "user_input_field" not in st.session_state: st.session_state["user_input_field"] = "A"
if "show_admin_login" not in st.session_state: st.session_state["show_admin_login"] = False
if "inspect_emp_target" not in st.session_state: st.session_state["inspect_emp_target"] = None
if "nav_mode" not in st.session_state: st.session_state["nav_mode"] = "home"
if "current_user_id" not in st.session_state: st.session_state["current_user_id"] = "A"

def get_file_mtime_str(path):
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(TAIWAN_TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return "無檔案"

def get_schedule_range():
    for path in ROLE_FILES.values():
        if os.path.exists(path):
            try:
                df = pd.read_excel(path, header=3)
                cols = [str(c).strip() for c in df.columns[2:]]
                dates = [re.search(r'(\d+/\d+)', c).group(1) for c in cols if re.search(r'(\d+/\d+)', c)]
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
    if is_valid_train_code(tr_upper): return False
    if tr_upper in ["PAY", "FAC"]: return False
    if not tr or tr_upper in ["", "無", "NAN"]: return True
    keywords = ["TOWN", "STD", "TTN", "DTT", "OGT", "OGC", "FAC", "DS", "H9", "WRSL"]
    return any(kw in f"{tr_upper} {str(note).upper()}" for kw in keywords)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
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
    return dict(start=start_time, end=end_time, train=real_train if real_train else "無", hours=hours, note=" ".join(notes))

def process_file_data(input_str):
    input_clean = input_str.strip().upper()
    matched_row, emp_id, emp_name, df_found = None, "", "", None
    for role, path in ROLE_FILES.items():
        if os.path.exists(path):
            df_temp = pd.read_excel(path, header=3)
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

# --- 檢視完整班表 ---
if st.session_state.get("inspect_emp_target") is not None:
    target_emp = st.session_state["inspect_emp_target"]
    st.markdown(f"""
    <div class="section-header-box">
        <div class="section-title">組員完整班表檢視: {target_emp}</div>
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
        draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))

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
        draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // v4.19", ha="left", va="bottom", color="#0F172A", fontproperties=fp(12))
        draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str}", ha="right", va="bottom", color="#0F172A", fontproperties=fp(12))

        buf = io.BytesIO()
        plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()

        st.success(f"已成功載入 {emp_name} ({emp_id}) 之完整月班表")
        st.image(buf, use_container_width=True)
        st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"TTN班表_{emp_name}.png", mime="image/png")
    except Exception as e:
        st.error(f"載入完整班表時發生錯誤: {e}")

    st.stop()

# --- 前置授權碼門戶檢查 ---
if not st.session_state["authenticated"] and not st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <div style="font-size: 34px; font-weight: 900; letter-spacing: 1.5px; color: #F8FAFC; font-family: monospace;">CREW DUTY ENGINE</div>
        <div style="color: #64748B; font-size: 11px; font-weight: 600; letter-spacing: 2.5px; text-transform: uppercase; margin-top: 6px; font-family: monospace;">C.L.F // BUSY DOING NOTHING PRODUCTIVE // EDITION</div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        st.markdown('<div class="auth-card-container">', unsafe_allow_html=True)
        with st.form("auth_form"):
            entered_emp = st.text_input("操作者員編 (僅輸入數字)", value="A", placeholder="例如: 023300", max_chars=10)
            entered_key = st.text_input("金鑰 / 密碼", type="password", placeholder="請輸入系統授權碼...")
            btn_auth = st.form_submit_button("進入系統")

            if btn_auth:
                clean_emp = entered_emp.strip()
                if not clean_emp:
                    st.error("請輸入有效的員編")
                elif entered_key == CREW_ACCESS_PASSWORD:
                    st.session_state["authenticated"] = True
                    st.session_state["current_user_id"] = clean_emp
                    st.rerun()
                elif entered_key == ADMIN_PASSWORD:
                    st.session_state["admin_logged_in"] = True
                    st.session_state["current_user_id"] = f"ADMIN_{clean_emp}"
                    st.session_state["nav_mode"] = "admin_panel"
                    st.success("管理員驗證成功，正在載入後台...")
                    st.rerun()
                else:
                    st.error("授權碼或密碼錯誤，請重新輸入")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 頂部質感標頭 ---
st.markdown(f"""
<div class="header-container">
    <div class="title-left-group">
        <div class="main-title"><span class="status-dot"></span>CREW DUTY ENGINE</div>
        <div class="title-subtitle">C.L.F // OPERATOR: {st.session_state.get("current_user_id", "A")}</div>
    </div>
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
            with col_btn1:
                btn_submit_adm = st.form_submit_button("登入後台")
            with col_btn2:
                btn_cancel_adm = st.form_submit_button("取消")

            if btn_submit_adm:
                if adm_pwd_input == ADMIN_PASSWORD:
                    st.session_state["admin_logged_in"] = True
                    st.session_state["nav_mode"] = "admin_panel"
                    st.session_state["show_admin_login"] = False
                    st.success("驗證成功，正在進入後台...")
                    st.rerun()
                else:
                    st.error("管理員密碼錯誤")
            elif btn_cancel_adm:
                st.session_state["show_admin_login"] = False
                st.rerun()
    st.stop()

if st.session_state.get("nav_mode") == "admin_panel" and st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">管理員專用：Database 控制台</div>
        <div class="section-subtitle">Direct Administrator Dashboard</div>
    </div>
    """, unsafe_allow_html=True)

    col_ctrl1, col_ctrl2 = st.columns(2)
    with col_ctrl1:
        if st.button("← 返回一般系統首頁", key="admin_back_to_home_btn"):
            st.session_state["nav_mode"] = "home"
            st.rerun()
    with col_ctrl2:
        if st.button("🔒 登出管理員身分", key="admin_logout_btn_top"):
            st.session_state["admin_logged_in"] = False
            st.session_state["nav_mode"] = "home"
            st.rerun()

    st.success("歡迎回來，管理員 LEO（目前處於管理員在線狀態，可隨時點擊頁面最下方的版本貼紙切換回首頁）")

    st.markdown("---")
    st.subheader("查詢紀錄清單")
    col_log_1, col_log_2 = st.columns([1, 1])
    with col_log_1:
        if st.button("🔄 重新載入紀錄"): st.rerun()
    with col_log_2:
        if st.button("🗑️ 清除紀錄"):
            if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
            st.rerun()

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = f.readlines()
            for line in reversed(logs[-20:]): st.text(line.strip())
    else: st.info("尚無任何查詢紀錄")

    st.markdown("---")
    st.subheader("各系統獨立維護開關控制台")
    st.caption("您可以針對這三種系統分別設定維護狀態，不需一次關閉全部系統：")

    maint_p = is_module_maintenance("producer")
    toggle_p = st.checkbox("【系統 1】繪製個人月班表圖檔 - 進入維護模式", value=maint_p, key="toggle_producer")
    if toggle_p != maint_p:
        set_module_maintenance("producer", toggle_p)
        st.rerun()

    maint_w = is_module_maintenance("window_filter")
    toggle_w = st.checkbox("【系統 2】指定時段報到組員快篩 - 進入維護模式", value=maint_w, key="toggle_window")
    if toggle_w != maint_w:
        set_module_maintenance("window_filter", toggle_w)
        st.rerun()

    maint_e = is_module_maintenance("exchange_filter")
    toggle_e = st.checkbox("【系統 3】換假日期快篩 - 進入維護模式", value=maint_e, key="toggle_exchange")
    if toggle_e != maint_e:
        set_module_maintenance("exchange_filter", toggle_e)
        st.rerun()

    st.markdown("---")
    st.subheader("管理員檔案上傳與刪除區")
    selected_role = st.selectbox("選擇要上傳或刪除的職位類別", ["駕駛", "列車長", "服勤員"])
    
    target_path = ROLE_FILES[selected_role]

    col_up, col_del = st.columns(2)
    with col_up:
        uploaded_file = st.file_uploader(f"上傳【{selected_role}】班表檔案", type=["xlsx", "xls", "csv", "txt"])
        if uploaded_file is not None:
            with open(target_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success("上傳成功")
            st.rerun()

    with col_del:
        file_exists = os.path.exists(target_path)
        st.write("目前檔案狀態：" + ("已存在" if file_exists else "無檔案"))
        
        if file_exists:
            if st.button(f"🗑️ 刪除【{selected_role}】現有班表檔案"):
                os.remove(target_path)
                st.success(f"已成功刪除【{selected_role}】的班表檔案")
                st.rerun()
        else:
            st.button(f"🗑️ 刪除【{selected_role}】現有班表檔案", disabled=True)

    st.stop()

# --- 一般系統首頁介面 ---
# --- 檢查資料庫檔案狀態 ---
missing_files = []
for role, path in ROLE_FILES.items():
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        missing_files.append(role)

if missing_files:
    st.error("資料庫異常：請洽管理員！")

td_time = get_file_mtime_str(ROLE_FILES["駕駛"])
tm_time = get_file_mtime_str(ROLE_FILES["列車長"])
ta_time = get_file_mtime_str(ROLE_FILES["服勤員"])
sched_range = get_schedule_range()

is_db_empty = len(missing_files) == len(ROLE_FILES)
card_class = "missing-data-card" if missing_files else "telemetry-card"

st.markdown(f"""
<div class="{card_class}">
    <div class="telemetry-title">目前系統排班週期 & 伺服器資料狀態</div>
    <div class="telemetry-value" style="font-size: 22px; color: {"#EF4444" if missing_files else "#60A5FA"}; margin-bottom: 8px;">
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
    "換班｜指定時段組員快篩（Alpha測試版）",
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
        if not current_input:
            st.warning("請輸入員編或姓名")
        else:
            log_activity(current_input)
            if not any(os.path.exists(path) for path in ROLE_FILES.values()): st.error("無班表資料")
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
                    draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))
                    
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
                    draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // v4.19", ha="left", va="bottom", color="#0F172A", fontproperties=fp(12))
                    draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str}", ha="right", va="bottom", color="#0F172A", fontproperties=fp(12))
                    
                    buf = io.BytesIO()
                    plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()
                    
                    progress_bar.progress(100)
                    status_placeholder.empty()
                    progress_bar.empty()

                    st.success("個人班表圖片生成成功")
                    st.image(buf, use_container_width=True)
                    st.info("提醒：長按上方的班表圖片即可一鍵存入手機相簿")
                    st.download_button("點此下載班表影像檔", data=buf, file_name=f"TTN班表_{emp_name}.png", mime="image/png")
                except Exception as e: st.error(f"錯誤：{e}")

elif app_mode == "換班｜指定時段組員快篩（Alpha測試版）":
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

    selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2)
    target_path = ROLE_FILES[selected_role]

    if not os.path.exists(target_path):
        st.error(f"找不到【{selected_role}】的班表檔案 ({target_path})，請先至管理員後台上傳")
    else:
        df_search = pd.read_excel(target_path, header=3)
        df_search.columns = [str(c).strip() for c in df_search.columns]
        
        date_cols = []
        for col in df_search.columns[2:]:
            match_d = re.search(r'(\d+/\d+)', str(col))
            if match_d: date_cols.append(match_d.group(1))

        if not date_cols:
            st.error("表中未偵測到有效日期欄位")
        else:
            dynamic_time_set = set()
            for _, r_row in df_search.iterrows():
                for cell_val in r_row.iloc[2:]:
                    p_temp = parse_cell(cell_val)
                    if p_temp["start"] and re.match(r'^\d{1,2}:\d{2}$', p_temp["start"]):
                        dynamic_time_set.add(p_temp["start"])
            
            TIME_OPTIONS = sorted(list(dynamic_time_set))
            if not TIME_OPTIONS: TIME_OPTIONS = ["04:00", "05:00", "06:00", "07:00"]

            if selected_role == "駕駛":
                earliest_default = TIME_OPTIONS[0]
            else:
                target_default = "05:26"
                earliest_default = target_default if target_default in TIME_OPTIONS else min(TIME_OPTIONS, key=lambda x: abs(datetime.strptime(x, "%H:%M") - datetime.strptime("05:26", "%H:%M")))

            default_min_idx = TIME_OPTIONS.index(earliest_default) if earliest_default in TIME_OPTIONS else 0
            try:
                h, m = map(int, earliest_default.split(":"))
                target_mins = h * 60 + m + 120
                target_h = (target_mins // 60) % 24
                target_m = target_mins % 60
                suggested_end = f"{target_h:02d}:{target_m:02d}"
                default_max_idx = TIME_OPTIONS.index(suggested_end) if suggested_end in TIME_OPTIONS else min(range(len(TIME_OPTIONS)), key=lambda i: abs(datetime.strptime(TIME_OPTIONS[i], "%H:%M") - datetime.strptime(suggested_end, "%H:%M")))
            except:
                default_max_idx = min(default_min_idx + 4, len(TIME_OPTIONS) - 1)

            c1, c2 = st.columns(2)
            with c1: start_date = st.selectbox("起始日期", date_cols, index=0, key="win_start_date")
            start_date_idx = date_cols.index(start_date) if start_date in date_cols else 0
            with c2: end_date = st.selectbox("結束日期", date_cols, index=start_date_idx, key="win_end_date")

            c3, c4 = st.columns(2)
            with c3: min_time = st.selectbox("Sign-In Time 區間：從", options=TIME_OPTIONS, index=default_min_idx, key="min_time_selectbox")
            with c4: max_time = st.selectbox("Sign-In Time 區間：到", options=TIME_OPTIONS, index=default_max_idx, key="max_time_selectbox")

            filter_col1, filter_col2 = st.columns(2)
            with filter_col1: only_main_line = st.checkbox("僅顯示正線勤務", value=False, key="win_main_line")
            with filter_col2: only_long_shift = st.checkbox("僅顯示長班 (>8.5h)", value=False, key="win_long_shift")

            if st.button("開始區間檢索符合條件人員", key="btn_window_search"):
                log_activity(f"時段快篩 [{selected_role}] {start_date}~{end_date} {min_time}-{max_time}")
                try:
                    s_idx = date_cols.index(start_date)
                    e_idx = date_cols.index(end_date)
                    target_dates = date_cols[s_idx:e_idx+1] if s_idx <= e_idx else []
                except: target_dates = []

                if not target_dates:
                    st.warning("起始日期不可大於結束日期")
                else:
                    search_results = []
                    all_cols_list = list(df_search.columns[2:])

                    for _, row in df_search.iterrows():
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()
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
                                
                                if start_t and min_time <= start_t <= max_time:
                                    is_non_line = is_town_shift(parsed["train"], parsed["note"])
                                    is_long = is_overtime(parsed["hours"], parsed["train"], parsed["note"])
                                    
                                    if only_main_line and is_non_line: continue
                                    if only_long_shift and not is_long: continue

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
                    st.markdown(f"### 檢索結果：{start_date} 至 {end_date} ｜ 區間 {min_time} ~ {max_time}（共符合 {len(search_results)} 筆）")
                    
                    if search_results:
                        current_date_group = None
                        c_col1, c_col2 = None, None
                        col_idx = 0 
                        for r in search_results:
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
                            <div class="compact-card">
                                <div class="time-header-row">
                                    <span class="compact-time">{r['Sign-In']} -> {r['收工時間']}</span>
                                    {badges_html}
                                </div>
                                <div class="compact-name">{r['姓名']} <span style="color:#94A3B8; font-size:12px;">({r['員編']})</span></div>
                                <div class="compact-sub">班別: {r['車次']}</div>
                                <div class="compact-sub">隔日勤務時間: {r['隔日Sign-In']}</div>
                            </div>
                            """
                            if col_idx % 2 == 0:
                                with c_col1: st.markdown(card_html, unsafe_allow_html=True)
                            else:
                                with c_col2: st.markdown(card_html, unsafe_allow_html=True)
                            col_idx += 1
                    else:
                        st.info("在指定的日期與 Sign-In 區間內，沒有找到符合條件的人員")

elif app_mode == "換假｜日期快篩（Alpha測試版）":
    if st.session_state.get("last_app_mode") != "換假｜日期快篩（Alpha測試版）":
        if "ex_sub_mode" not in st.session_state:
            st.session_state["ex_sub_mode"] = "search_form"
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
    if "ex_saved_role" not in st.session_state: st.session_state["ex_saved_role"] = ""

    if st.session_state["ex_sub_mode"] == "inspect_image":
        target_emp = st.session_state["ex_selected_emp"]
        saved_role = st.session_state.get("ex_saved_role", "服勤員")
        saved_date = st.session_state.get("ex_saved_target_date", "")

        st.markdown(f"""
        <div class="section-header-box">
            <div class="section-title">換假組員完整班表檢視: {target_emp}</div>
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
            draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))

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
            draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // v4.19", ha="left", va="bottom", color="#0F172A", fontproperties=fp(12))
            draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str}", ha="right", va="bottom", color="#0F172A", fontproperties=fp(12))

            buf = io.BytesIO()
            plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()

            st.success(f"已成功載入 {emp_name} ({emp_id}) 之完整月班表")
            st.image(buf, use_container_width=True)
            st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"TTN班表_{emp_name}.png", mime="image/png")
        except Exception as e:
            st.error(f"載入完整班表時發生錯誤: {e}")

        st.stop()

    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">換假日期快篩系統</div>
        <div class="section-subtitle">Shift Exchange Date Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    ex_c1, ex_c2, ex_c3 = st.columns(3)
    with ex_c1:
        selected_role = st.selectbox("選擇職位類別", ["服勤員", "駕駛", "列車長"], index=0, key="ex_role_select")
    
    sample_path = ROLE_FILES[selected_role] if os.path.exists(ROLE_FILES[selected_role]) else list(ROLE_FILES.values())[0]
    try:
        temp_df_dates = pd.read_excel(sample_path, header=3)
        date_cols = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in temp_df_dates.columns[2:] if re.search(r'(\d+/\d+)', str(c))]
    except:
        date_cols = []

    time_filter_options = [
        "不限", 
        "05:00 以後", "06:00 以後", "07:00 以後", "08:00 以後", 
        "09:00 以後", "10:00 以後", "11:00 以後", "12:00 以後", 
        "13:00 以後", "14:00 以後", "15:00 以後", "16:00 以後"
    ]

    current_selection_key = f"{selected_role}_{st.session_state.get('ex_target_date_' + selected_role, '')}_{st.session_state.get('ex_return_date_' + selected_role, '')}"
    if "last_selection_signature" not in st.session_state:
        st.session_state["last_selection_signature"] = current_selection_key

    with ex_c2:
        if date_cols:
            target_date = st.selectbox("想休假的日期", date_cols, index=0, key=f"ex_target_date_{selected_role}")
        else:
            target_date = st.selectbox("想休假的日期", ["無可用日期"], index=0, key=f"ex_target_date_{selected_role}")

    with ex_c3:
        if date_cols:
            return_date = st.selectbox("可還假的日期(上班日)", date_cols, index=min(1, len(date_cols)-1), key=f"ex_return_date_{selected_role}")
        else:
            return_date = st.selectbox("可還假的日期(上班日)", ["無可用日期"], index=0, key=f"ex_return_date_{selected_role}")

    return_time_filter = st.selectbox(
        "還假日，可接受對方的報到時間限制（只列出 XX:XX 之後報到的班）",
        options=time_filter_options,
        index=0,
        key="ex_return_time_filter"
    )

    new_selection_key = f"{selected_role}_{target_date}_{return_date}_{return_time_filter}"
    if st.session_state["last_selection_signature"] != new_selection_key:
        st.session_state["ex_saved_candidates"] = []
        st.session_state["ex_sub_mode"] = "search_form"
        st.session_state["last_selection_signature"] = new_selection_key

    strict_limit = st.checkbox("嚴格過濾：排除前後 5 天內連續上班已達 6 天以上的人員", value=True, key="ex_strict_limit")

    is_selection_valid = True
    validation_error_msg = ""

    if date_cols and target_date != "無可用日期" and return_date != "無可用日期":
        if target_date == return_date:
            is_selection_valid = False
            validation_error_msg = "「想休假的日期」與「可還假的日期」不可選擇同一天！"
        else:
            try:
                sample_col = ""
                for c in temp_df_dates.columns[2:]:
                    if re.search(r'(\d+/\d+)', str(c)):
                        sample_col = re.search(r'(\d+/\d+)', str(c)).group(1)
                        break
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
                else:
                    first_week_sun, first_week_sat = get_sun_sat_week(date_cols[0])
                    if t_sun == first_week_sun:
                        st.info("提示：注意前一週是否連續工作 7 天喔！")
            except Exception as e:
                is_selection_valid = False
                validation_error_msg = f"日期解析發生錯誤: {e}"

    if not is_selection_valid:
        st.error(f"條件未通過：{validation_error_msg}")

    if is_selection_valid:
        btn_search_clicked = st.button("開始尋找可換假對象", key="btn_auto_search_exchange_fixed")
    else:
        st.button("修正上述日期後 開始查詢", disabled=True, key="btn_auto_search_exchange_disabled")
        btn_search_clicked = False

    if btn_search_clicked and is_selection_valid:
        log_activity(f"換假快篩 [{selected_role}] 想休:{target_date} 還假:{return_date}")
        st.session_state["ex_sub_mode"] = "results"
        try:
            target_path = ROLE_FILES[selected_role]
            df_ex = pd.read_excel(target_path, header=3)
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
                    
                    cell_target = row.iloc[target_col_idx]
                    parsed_target = parse_cell(cell_target)
                    raw_target_str = str(cell_target).upper()
                    tr_target = str(parsed_target["train"]).strip().upper()
                    
                    is_target_do = ("DO" in raw_target_str) or ("D2W" in raw_target_str)
                    is_target_leave = (tr_target in ["PAY", "FAC", "AL", "SL", "CL"]) or ("PAY" in raw_target_str) or ("FAC" in raw_target_str)
                    
                    if not (is_target_do and not is_target_leave):
                        continue

                    cell_return = row.iloc[return_col_idx]
                    parsed_return = parse_cell(cell_return)
                    raw_return_str = str(cell_return).upper()
                    tr_return = str(parsed_return["train"]).strip().upper()
                    
                    is_return_do = ("DO" in raw_return_str) or ("D2W" in raw_return_str)
                    is_return_leave = (tr_return in ["PAY", "FAC", "AL", "SL", "CL"]) or ("PAY" in raw_return_str) or ("FAC" in raw_return_str)
                    
                    if is_return_do or is_return_leave:
                        continue

                    if return_time_filter != "不限":
                        min_allowed_time = return_time_filter.split(" ")[0]
                        return_start_time = parsed_return["start"]
                        if not return_start_time or return_start_time < min_allowed_time:
                            continue

                    s_idx = max(0, actual_pos - 5)
                    e_idx = min(len(all_cols_list) - 1, actual_pos + 5)
                    
                    current_streak = 0
                    max_streak = 0
                    
                    for p_i in range(s_idx, e_idx + 1):
                        c_val = row.iloc[p_i + 2]
                        p_res = parse_cell(c_val)
                        c_raw_str = str(c_val).upper()
                        c_tr = str(p_res["train"]).strip().upper()
                        
                        is_c_rest = ("DO" in c_raw_str) or ("D2W" in c_raw_str)
                        is_c_special_leave = (c_tr in ["PAY", "FAC", "AL", "SL", "CL"]) or ("PAY" in c_raw_str) or ("FAC" in c_raw_str)
                        
                        if is_c_rest and not is_c_special_leave:
                            current_streak = 0
                        else:
                            current_streak += 1
                            if current_streak > max_streak:
                                max_streak = current_streak
                    
                    if strict_limit and max_streak >= 6:
                        continue
                        
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
                        
                        if is_c_hol and not is_c_leave:
                            shift_display = "休"
                        elif is_c_leave:
                            if "PAY" in c_raw_s or "特休" in c_raw_s:
                                shift_display = "PAY"
                            elif "FAC" in c_raw_s:
                                shift_display = "FAC"
                            else:
                                shift_display = c_tr_s if c_tr_s else "特休"
                        else:
                            main_tr_code = str(p_res["train"]).strip()
                            if main_tr_code.upper().startswith("N") and p_res["start"] and p_res["end"]:
                                shift_display = f"{p_res['start']}->{p_res['end']}"
                            else:
                                shift_display = main_tr_code if main_tr_code and main_tr_code != "無" else (p_res["note"] if p_res["note"] else "班")
                            
                        mini_schedule.append(f"{d_str}: {shift_display}")

                    candidates.append({
                        "員編": emp_id,
                        "姓名": emp_name,
                        "當天狀態": f"想休 {target_date}(DO) ｜ 還假 {return_date}({parsed_return['start']+'->'+parsed_return['end'] if parsed_return['start'] else parsed_return['train']})",
                        "前後連續上班最大天數": max_streak,
                        "鄰近天數概況": " | ".join(mini_schedule)
                    })
                st.session_state["ex_saved_candidates"] = candidates
                st.session_state["ex_saved_target_date"] = target_date
                st.session_state["ex_saved_role"] = selected_role
        except Exception as e:
            st.error(f"日期計算發生錯誤: {e}")

    if st.session_state["ex_sub_mode"] == "results" and st.session_state.get("ex_saved_candidates"):
        saved_candidates = st.session_state["ex_saved_candidates"]
        saved_date = st.session_state.get("ex_saved_target_date", target_date)
        saved_role = st.session_state.get("ex_saved_role", selected_role)

        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            border: 1px solid #334155;
            border-left: 5px solid #38BDF8;
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.4);
            display: flex;
            flex-direction: column;
            gap: 8px;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <span style="color: #F8FAFC; font-size: 18px; font-weight: 700; font-family: monospace;">
                    【{saved_role}】符合換假名單
                </span>
                <span style="background: rgba(56, 189, 248, 0.15); border: 1px solid #38BDF8; color: #38BDF8; font-size: 12px; padding: 2px 10px; border-radius: 6px; font-weight: 600; font-family: monospace;">
                    共 {len(saved_candidates)} 位符合
                </span>
            </div>
            <div style="color: #94A3B8; font-size: 13px; font-family: monospace; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <span>想休日期：<strong style="color: #34D399;">{saved_date}</strong></span>
                <span style="color: #475569;">|</span>
                <span>可還假日期：<strong style="color: #60A5FA;">{return_date}</strong></span>
                <span style="color: #475569;">|</span>
                <span>報到限制：<strong style="color: #F87171;">{return_time_filter}</strong></span>
            </div>
        </div>
        """, unsafe_allow_html=True)        
        for idx, cand in enumerate(saved_candidates):
            st.markdown(f"""
            <div class="integrated-crew-box">
                <div class="time-header-row">
                    <span class="compact-time" style="color: #34D399;">{cand['當天狀態']}</span>
                    <span class="non-line-badge" style="background: rgba(16, 185, 129, 0.2); border-color: #10B981; color: #34D399;">連續上班風險度: {cand['前後連續上班最大天數']}天</span>
                </div>
                <div class="compact-name" style="margin-top: 4px;">{cand['姓名']} <span style="color:#94A3B8; font-size:12px;">({cand['員編']})</span></div>
                <div class="compact-sub" style="margin-top: 6px; font-size: 11px; color: #CBD5E1;">前後動態: {cand['鄰近天數概況']}</div>
                <div class="action-divider"></div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"檢視完整班表：{cand['姓名']}", key=f"ex_gen_img_btn_{cand['員編']}_{idx}"):
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
            
            st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

# --- 底部版本/管理員貼紙 ---
st.markdown('<div class="footer-badge-container">', unsafe_allow_html=True)
footer_badge_label = "ADMIN PANEL // C.L.F EDITION" if st.session_state.get("admin_logged_in", False) else "C.L.F EDITION"
if st.button(footer_badge_label, key="bottom_footer_edition_badge"):
    if st.session_state.get("admin_logged_in", False):
        if st.session_state["nav_mode"] == "home":
            st.session_state["nav_mode"] = "admin_panel"
        else:
            st.session_state["nav_mode"] = "home"
    else:
        st.session_state["show_admin_login"] = True
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)
