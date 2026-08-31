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

# --- 單位獨立維護開關的核心檔案處理邏輯 ---
def get_maintenance_flag_path(unit, module_key):
    return os.path.join(DATA_DIR, f"maintenance_{unit}_{module_key}.flag")

def set_module_maintenance(unit, module_key, is_maint):
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR, exist_ok=True)
    flag_path = get_maintenance_flag_path(unit, module_key)
    if is_maint:
        with open(flag_path, "w") as f: f.write("ON")
    else:
        if os.path.exists(flag_path): os.remove(flag_path)

def is_module_maintenance(unit, module_key):
    flag_path = get_maintenance_flag_path(unit, module_key)
    return os.path.exists(flag_path)

# --- 事件驅動型維護狀態變更 Callback ---
def toggle_maintenance_callback(unit, module_key):
    key = f"maint_sw_{unit}_{module_key}"
    new_state = st.session_state.get(key, False)
    set_module_maintenance(unit, module_key, new_state)
    log_activity(f"設定 [{unit}] {module_key} 維護開關狀態: {'開啟維護' if new_state else '解除維護'}")

# --- 升級版毛玻璃與響應式視覺設計 (Glassmorphism & Integrated UI) ---
st.markdown("""
<style>
    .stApp { 
        background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f172a 50%, #020617 100%) !important; 
        color: #F8FAFC !important; 
        background-attachment: fixed !important;
    }
    
    /* 桌面端與行動端寬度適配 */
    @media (min-width: 1024px) {
        .block-container { padding: 3.5rem 1.5rem 3rem 1.5rem !important; max-width: 1050px !important; }
    }
    @media (max-width: 1023px) {
        .block-container { padding: 2.5rem 0.8rem 2rem 0.8rem !important; max-width: 100% !important; }
    }

    /* 強制所有 Streamlit 按鈕容器具備 100% 滿寬能力 */
    div[data-testid="stButton"], div.stButton {
        width: 100% !important;
    }
    div[data-testid="stButton"] > button, div.stButton > button {
        width: 100% !important;
    }

    /* 三大系統按鈕選項方格化卡片設計 */
    div[role="radiogroup"] {
        display: flex;
        flex-direction: column;
        gap: 12px;
        width: 100%;
        margin-top: 10px;
        margin-bottom: 15px;
    }
    div[role="radiogroup"] > label {
        background: rgba(30, 41, 59, 0.65) !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-left: 5px solid #38BDF8 !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        margin: 0 !important;
        cursor: pointer !important;
        transition: all 0.2s ease-in-out !important;
        width: 100% !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    div[role="radiogroup"] > label:hover {
        background: rgba(30, 58, 138, 0.5) !important;
        border-color: #38BDF8 !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(56, 189, 248, 0.2);
    }
    div[role="radiogroup"] > label[data-checked="true"], div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(30, 64, 175, 0.65) !important;
        border-color: #60A5FA !important;
        border-left-color: #60A5FA !important;
        box-shadow: 0 0 14px rgba(96, 165, 250, 0.3);
    }
    div[role="radiogroup"] > label p {
        font-size: 15px !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
    }

    @keyframes online-green-pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.6); }
        70% { transform: scale(1.05); box-shadow: 0 0 0 6px rgba(74, 222, 128, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
    }

    .online-dot {
        width: 8px; height: 8px; background-color: #4ADE80; border-radius: 50%;
        display: inline-block; animation: online-green-pulse 2.5s infinite ease-in-out;
        box-shadow: 0 0 8px #4ADE80; margin: 0 8px; vertical-align: middle;
    }

    .test-env-banner {
        border: 1px solid rgba(245, 158, 11, 0.5); border-radius: 16px; padding: 10px 18px; margin-bottom: 1.2rem;
        text-align: center; background: rgba(39, 28, 12, 0.55); backdrop-filter: blur(12px); font-family: monospace;
    }
    .test-env-title { color: #FDE68A; font-size: 13px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; }
    .test-env-sub { color: #FCD34D; font-size: 10px; font-weight: 600; letter-spacing: 1px; opacity: 0.9; }

    .header-container { 
        display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;
        width: 100%; margin-bottom: 1.2rem; padding: 20px 16px;
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    .main-title { color: #F8FAFC !important; font-size: 22px; font-weight: 800; letter-spacing: 2px; margin: 0; font-family: monospace; }
    .title-subtitle { color: #FFFFFF; font-size: 12px; font-weight: 700; letter-spacing: 1.5px; font-family: monospace; margin-top: 6px; }

    .footer-badge-container { display: flex; justify-content: center; align-items: center; width: 100%; margin-top: 2.5rem; margin-bottom: 1rem; }
    .footer-badge-container div.stButton > button { 
        background: rgba(15, 23, 42, 0.4) !important; backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(51, 65, 85, 0.5) !important; border-left: 2px solid #38BDF8 !important;
        color: #94A3B8 !important; font-size: 9px !important; font-weight: 600 !important; letter-spacing: 1.5px !important; 
        text-transform: uppercase !important; padding: 6px 14px !important; border-radius: 6px !important;
        font-family: monospace !important; width: auto !important; margin: 0 auto !important; min-height: unset !important; transition: all 0.25s ease !important;
    }
    .footer-badge-container div.stButton > button:hover {
        border-color: #38BDF8 !important; color: #38BDF8 !important; background: rgba(30, 41, 59, 0.6) !important;
    }

    .section-header-box { 
        background: rgba(30, 41, 59, 0.45); 
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #3B82F6; border-radius: 16px; padding: 16px 20px; margin-top: 15px; margin-bottom: 18px; 
    }
    .section-title { color: #F8FAFC; font-size: 17px; font-weight: 700; margin: 0; }
    .section-subtitle { color: #94A3B8; font-size: 11px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin-top: 3px; font-family: monospace; }

    .date-banner { 
        background: rgba(30, 64, 175, 0.45); 
        border: 1px solid rgba(96, 165, 250, 0.3); border-left: 4px solid #60A5FA; color: #FFFFFF; font-size: 13px; font-weight: 800; padding: 8px 14px; border-radius: 10px; margin-top: 18px; margin-bottom: 10px; font-family: monospace;
    }

    /* 一體化卡片上半部主體 */
    .integrated-crew-box {
        width: 100% !important;
        box-sizing: border-box !important;
        background: rgba(30, 41, 59, 0.75);
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-bottom: none !important;
        border-left: 4px solid #10B981;
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
        border-bottom-left-radius: 0px !important;
        border-bottom-right-radius: 0px !important;
        padding: 16px 16px 12px 16px;
        margin-bottom: 0px !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.25);
    }

    /* 一體化卡片下半部按鈕：精準對接並 100% 滿寬延伸 */
    div.stElementContainer:has(.integrated-crew-box) + div.stElementContainer div[data-testid="stButton"] > button,
    div.stElementContainer:has(.integrated-crew-box) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button,
    div.element-container:has(.integrated-crew-box) + div.element-container button {
        border-top-left-radius: 0px !important;
        border-top-right-radius: 0px !important;
        border-bottom-left-radius: 14px !important;
        border-bottom-right-radius: 14px !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-left: 4px solid #10B981 !important;
        background: rgba(15, 23, 42, 0.85) !important;
        color: #38BDF8 !important;
        font-size: 13px !important;
        margin-top: -1px !important;
        margin-bottom: 16px !important;
        padding: 9px 12px !important;
        width: 100% !important;
        display: block !important;
        text-align: center !important;
        box-sizing: border-box !important;
    }

    div.stElementContainer:has(.integrated-crew-box) + div.stElementContainer div[data-testid="stButton"] > button:hover,
    div.stElementContainer:has(.integrated-crew-box) + div[data-testid="stElementContainer"] div[data-testid="stButton"] > button:hover,
    div.element-container:has(.integrated-crew-box) + div.element-container button:hover {
        background: rgba(30, 58, 138, 0.85) !important;
        color: #FFFFFF !important;
        border-color: #38BDF8 !important;
    }

    .compact-name { font-size: 16px; font-weight: 800; color: #F8FAFC; }
    .compact-sub { font-size: 12px; color: #CBD5E1; font-family: monospace; }
    .badge-group { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    .long-badge { background: rgba(153, 27, 27, 0.35); border: 1px solid rgba(239, 68, 68, 0.5); color: #FCA5A5; font-size: 10px; padding: 2px 7px; border-radius: 6px; font-weight: 600; }
    .non-line-badge { background: rgba(76, 29, 149, 0.35); border: 1px solid rgba(139, 92, 246, 0.5); color: #C4B5FD; font-size: 10px; padding: 2px 7px; border-radius: 6px; font-weight: 600; }

    div.stButton > button, div.stFormSubmitButton > button { 
        font-weight: 700 !important; padding: 0.5rem 1rem !important; border-radius: 0.5rem !important; 
        background: rgba(30, 41, 59, 0.6) !important; 
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        color: #38BDF8 !important; width: 100% !important; 
        transition: all 0.2s ease !important; letter-spacing: 0.5px; font-family: monospace;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        border-color: rgba(56, 189, 248, 0.6) !important; color: #FFFFFF !important;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.85) 0%, rgba(29, 78, 216, 0.85) 100%) !important;
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

C_HDR, C_BORDER, C_EMPTY = "#0F172A", "#475569", "#F1F5F9"
C_WORK_BG, C_WEEKEND_BG = "#FFFFFF", "#F8FAFC"
C_DO_BG, C_PAY_BG, C_TOWN_BG = "#FFE4E6", "#FFEDD5", "#CBD5E1"
C_DO_TXT, C_PAY_TXT, C_HOLI_TXT, C_OT_TXT, C_NOTE_TXT = "#881337", "#9A3412", "#7C2D12", "#991B1B", "#4C1D95"
C_TOWN_TXT = "#000000"

def parse_device_info(ua_string):
    ua = ua_string.lower()
    if "iphone" in ua: device = "iPhone"
    elif "ipad" in ua: device = "iPad"
    elif "android" in ua: device = "Android Phone"
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
        if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR, exist_ok=True)
        now_tw = datetime.now(TAIWAN_TZ).strftime('%Y-%m-%d %H:%M:%S')
        ua_raw = st.context.headers.get("user-agent", "") if hasattr(st, "context") else ""
        device_info = parse_device_info(ua_raw) if ua_raw else "未知裝置"
        current_operator = st.session_state.get("current_user_id", "未知")
        current_unit = st.session_state.get("current_unit", "TTN")
        log_entry = f"{now_tw} | 單位: {current_unit} | 操作者員編: {current_operator} | 裝置: {device_info} | 動作: {input_str}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(log_entry)
    except: pass

def render_zoomable_image(image_buf):
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
                try: return pd.read_excel(file_path_or_bytes, header=header, engine='openpyxl')
                except: return pd.read_excel(file_path_or_bytes, header=header, engine='xlrd')
        else:
            file_bytes = file_path_or_bytes
            try: return pd.read_excel(io.BytesIO(file_bytes), header=header, engine='openpyxl')
            except: return pd.read_excel(io.BytesIO(file_bytes), header=header, engine='xlrd')
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
    mtimes = [os.path.getmtime(unit_files[role]) if os.path.exists(unit_files[role]) else 0 for role in ["駕駛", "列車長", "服勤員"]]
    member_set = get_unit_member_set(unit_key, tuple(mtimes))
    return emp_input.strip().upper() in member_set

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
        return f"目前檔案：{os.path.basename(path)} | 大小：{size_kb:.1f} KB | 更新時間：{dt.strftime('%Y-%m-%d %H:%M:%S')}"
    return f"目前檔案：尚無上傳檔案"

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
    if not t_str or ":" not in str(t_str): return t_str
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
    if not is_valid_train_code(tr) or not h: return False
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
    if not tr or tr_upper in ["", "無", "NAN"]: return True
    if tr_upper in ["PAY", "FAC"]: return False
    keywords = ["TOWN", "STD", "TTN", "DTT", "OGT", "OGC", "FAC", "DS", "H9", "WRSL"]
    for kw in keywords:
        if re.search(rf"\b{kw}\d*", combined_text): return True
    return not is_valid_train_code(tr_upper)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip() and l.strip() != "."]
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

# --- 升級加粗與描邊能力（位移量由 0.0002 提升至 0.00035）---
def draw_bold_text(ax, x, y, text, **kwargs):
    ax.text(x, y, text, **kwargs)
    offset = 0.00035
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

def render_schedule_figure(start_dt, dates, emp_id, emp_name, cells, unit_label, badge_title="Producer | C.L.F"):
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
    draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"UNIT // {unit_label}    CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))

    badge_w = CW * 0.90
    badge_x = (1.0 - MR) - CW + (CW - badge_w) / 2
    badge_y = ty + TH * 0.42
    badge_h = 0.035

    ax.add_patch(FancyBboxPatch((badge_x, badge_y), badge_w, badge_h, boxstyle="round,pad=0.002,rounding_size=0.01", linewidth=1.0, edgecolor="#334155", facecolor="#1E293B"))
    draw_bold_text(ax, badge_x + badge_w / 2, badge_y + badge_h / 2, badge_title, ha="center", va="center", color="#38BDF8", fontproperties=fp(10.5))

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
                draw_bold_text(ax, cx, ry + RH * 0.48, do_code, ha="center", va="center", color=C_DO_TXT, fontproperties=fp(15))
            elif is_pay_shift and not d["start"]: 
                draw_bold_text(ax, cx, ry + RH * 0.48, tr, ha="center", va="center", color=C_PAY_TXT, fontproperties=fp(15))
            else:
                # --- 核心改動：方案 A 放大並加粗 (Sign-In/Out 13->15pt, 班別 12->13.5pt) ---
                draw_bold_text(ax, cx, ry + RH * 0.65, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(15))
                draw_bold_text(ax, cx, ry + RH * 0.40, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(15))
                draw_bold_text(ax, cx, ry + RH * 0.15, tr, ha="center", va="center", color=C_PAY_TXT if is_pay_shift else "#000000", fontproperties=fp(13.5))

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
    return buf

@st.dialog("完整月班表檢視", width="large")
def show_crew_schedule_modal(emp_input, unit_label, badge_title="Inspector | C.L.F"):
    with st.spinner(f"正在讀取資料與繪製【{emp_input}】的完整月班表，請稍候..."):
        try:
            start_dt, dates, emp_id, emp_name, cells = process_file_data(emp_input)
            buf = render_schedule_figure(start_dt, dates, emp_id, emp_name, cells, unit_label, badge_title=badge_title)
            st.success(f"已成功載入 {emp_name} ({emp_id}) 之完整月班表")
            render_zoomable_image(buf)
            st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"{unit_label}_班表_{emp_name}.png", mime="image/png", key=f"modal_dl_btn_{emp_id}")
        except Exception as e:
            st.error(f"載入完整班表時發生錯誤: {e}")

# ==================== 獨立檢視指定組員完整班表 (Inspector Mode) ====================
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

    with st.spinner(f"正在繪製【{target_emp}】的完整月班表..."):
        try:
            start_dt, dates, emp_id, emp_name, cells = process_file_data(target_emp)
            buf = render_schedule_figure(start_dt, dates, emp_id, emp_name, cells, current_unit, badge_title="Inspector | C.L.F")
            st.success(f"已成功載入 {emp_name} ({emp_id}) 之完整月班表")
            render_zoomable_image(buf)
            st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"{current_unit}_班表_{emp_name}.png", mime="image/png")
        except Exception as e:
            st.error(f"載入完整班表時發生錯誤: {e}")

    st.stop()

# --- 前置授權碼門戶檢查 ---
if not st.session_state["authenticated"] and not st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <div style="font-size: 32px; font-weight: 900; letter-spacing: 1.5px; color: #F8FAFC; font-family: monospace;">CREW DUTY ENGINE</div>
        <div style="color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-top: 8px; font-family: monospace;">
            BUSY DOING NOTHING PRODUCTIVE<br>C.L.F EDITION
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
                if not clean_emp: st.error("請輸入有效的員編")
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
                    st.rerun()
                elif entered_key == CREW_ACCESS_PASSWORD:
                    if verify_crew_membership(selected_unit, clean_emp):
                        st.session_state["authenticated"] = True
                        st.session_state["admin_logged_in"] = False
                        st.session_state["current_unit"] = selected_unit
                        st.session_state["current_user_id"] = clean_emp
                        log_activity("使用者登入系統")
                        st.rerun()
                    else: st.error("非所屬單位組員，或輸入不存在的編號，請確認員編。")
                else: st.error("授權碼或密碼錯誤，請重新輸入")
    st.stop()

# --- 頂部標頭 ---
current_unit_label = st.session_state.get("current_unit", "TTN")
current_operator_id = st.session_state.get("current_user_id", "A")

st.markdown(f"""
<div class="header-container">
    <div class="main-title">CREW DUTY ENGINE</div>
    <div style="color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; font-family: monospace; margin-top: 4px;">
        BUSY DOING NOTHING PRODUCTIVE &bull; C.L.F EDITION
    </div>
    <div class="title-subtitle">
        <span class="online-dot"></span>WELCOME: {current_unit_label} | {current_operator_id}<span class="online-dot"></span>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 測試環境橫幅 ---
st.markdown("""
<div class="test-env-banner">
    <div class="test-env-title">測試環境運行中（TEST ENVIRONMENT）</div>
    <div class="test-env-sub">目前為內部測試階段 | (所屬運轉單位組員查詢使用)</div>
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
                    st.rerun()
                else: st.error("管理員密碼錯誤")
            elif btn_cancel_adm:
                st.session_state["show_admin_login"] = False
                st.rerun()
    st.stop()

# ==================== 管理員專用：Database 智慧控制台 ====================
if st.session_state.get("nav_mode") == "admin_panel" and st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">管理員專用：Database 智慧控制台</div>
        <div class="section-subtitle">Advanced Crew Duty Management & Data Maintenance Center</div>
    </div>
    """, unsafe_allow_html=True)

    admin_target_unit = st.selectbox("選擇要維護的營運單位", ["TTN", "TTC", "TTS"], key="admin_target_unit_sel")
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

    st.subheader(f"📊 【{admin_target_unit}】伺服器狀態 & Dashboard 數據")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        td_ok = os.path.exists(current_unit_files["駕駛"])
        st.metric("駕駛大表 (TD)", "已就緒" if td_ok else "缺檔案", delta="🟢 正常" if td_ok else "🔴 缺失")
    with m2:
        tm_ok = os.path.exists(current_unit_files["列車長"])
        st.metric("列車長大表 (TM)", "已就緒" if tm_ok else "缺檔案", delta="🟢 正常" if tm_ok else "🔴 缺失")
    with m3:
        ta_ok = os.path.exists(current_unit_files["服勤員"])
        st.metric("服勤員大表 (TA)", "已就緒" if ta_ok else "缺檔案", delta="🟢 正常" if ta_ok else "🔴 缺失")
    with m4:
        log_cnt = 0
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f: log_cnt = len(f.readlines())
        st.metric("系統日誌累計", f"{log_cnt} 筆", delta="Activity")

    st.markdown("---")
    st.subheader(f"各大系統模組維護開關控制（當前控制單位：{admin_target_unit}）")

    k_prod = f"maint_sw_{admin_target_unit}_producer"
    k_win = f"maint_sw_{admin_target_unit}_window_filter"
    k_ex = f"maint_sw_{admin_target_unit}_exchange_filter"

    st.session_state[k_prod] = is_module_maintenance(admin_target_unit, "producer")
    st.session_state[k_win] = is_module_maintenance(admin_target_unit, "window_filter")
    st.session_state[k_ex] = is_module_maintenance(admin_target_unit, "exchange_filter")

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.checkbox(
            "【個人月班表圖檔】維護中",
            key=k_prod,
            on_change=toggle_maintenance_callback,
            args=(admin_target_unit, "producer")
        )
    with col_m2:
        st.checkbox(
            "【換班選擇日期】維護中",
            key=k_win,
            on_change=toggle_maintenance_callback,
            args=(admin_target_unit, "window_filter")
        )
    with col_m3:
        st.checkbox(
            "【換假選擇日期】維護中",
            key=k_ex,
            on_change=toggle_maintenance_callback,
            args=(admin_target_unit, "exchange_filter")
        )

    st.markdown("---")
    st.subheader(f"【{admin_target_unit}】班表維護控制台")
    selected_role = st.selectbox("選擇目前要維護的職位類別", ["駕駛", "列車長", "服勤員"], index=2, key="admin_role_select_box")
    target_path = current_unit_files[selected_role]

    uploaded_file_update = st.file_uploader(f"上傳【{admin_target_unit} - {selected_role}】最新大表 (.xlsx)", type=["xlsx", "xls", "csv"], key=f"up_{admin_target_unit}_{selected_role}")
    if uploaded_file_update is not None:
        file_bytes = uploaded_file_update.getvalue()
        current_hash = hashlib.md5(file_bytes).hexdigest()
        hash_key = f"hash_{admin_target_unit}_{selected_role}"

        if st.session_state.get(hash_key) != current_hash:
            try:
                with open(target_path, "wb") as f: f.write(file_bytes)
                st.session_state[hash_key] = current_hash
                log_activity(f"上傳【{admin_target_unit} - {selected_role}】最新大表")
                st.success("檔案上傳成功！")
                time.sleep(0.5); st.rerun()
            except Exception as e: st.error(f"寫入失敗: {e}")

    st.markdown("---")
    st.subheader("📋 系統操作活動紀錄日誌 (Activity Log)")
    col_log1, col_log2 = st.columns([1, 3])
    with col_log1:
        log_filter_keyword = st.text_input("🔍 搜尋日誌關鍵字", placeholder="例如: 員編 / 換班 / 單位")
    with col_log2:
        st.write("")
        if st.button("🗑️ 清空歷史日誌"):
            if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
            st.rerun()

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f: logs = f.readlines()
        parsed_logs = []
        for line in reversed(logs[-50:]):
            if log_filter_keyword and log_filter_keyword.lower() not in line.lower(): continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5:
                parsed_logs.append({
                    "時間": parts[0], "單位": parts[1].replace("單位: ", ""),
                    "操作者": parts[2].replace("操作者員編: ", ""),
                    "裝置": parts[3].replace("裝置: ", ""), "動作": " | ".join(parts[4:]).replace("動作: ", "")
                })
        if parsed_logs: st.dataframe(pd.DataFrame(parsed_logs), use_container_width=True, hide_index=True)
        else: st.info("查無符合過濾條件的日誌")
    else: st.info("尚無任何紀錄")

    st.stop()

# ==================== 一般使用者系統首頁介面 ====================
active_files = get_current_role_files()
missing_files = [role for role in ["駕駛", "列車長", "服勤員"] if not os.path.exists(active_files[role]) or os.path.getsize(active_files[role]) == 0]

if missing_files: st.error(f"【{current_unit_label}】資料庫異常或尚無檔案：請洽管理員上傳！")

td_time = get_file_mtime_str(active_files["駕駛"])
tm_time = get_file_mtime_str(active_files["列車長"])
ta_time = get_file_mtime_str(active_files["服勤員"])
sched_range = get_schedule_range()

st.markdown(f"""
<div class="section-header-box" style="border-left-color: #60A5FA;">
    <div class="section-title">[{current_unit_label}] 目前系統排班週期 & 資料狀態</div>
    <div style="font-size: 18px; color: {"#EF4444" if missing_files else "#60A5FA"}; font-weight: 700; margin-top: 4px;">
        {sched_range if len(missing_files) < 3 else "資料庫異常：請洽管理員！"}
    </div>
    <div class="section-subtitle" style="margin-top: 6px;">
        駕駛: {td_time} | 列車長: {tm_time} | 服勤員: {ta_time}
    </div>
</div>
""", unsafe_allow_html=True)

app_mode = st.radio("系統操作模式選擇", [
    "繪製個人月班表圖檔", 
    "換班｜選擇換班日期（Alpha測試版）",
    "換假｜選擇換假日期（Alpha測試版）"
], horizontal=False, label_visibility="collapsed")

if "last_app_mode" not in st.session_state: st.session_state["last_app_mode"] = app_mode
if st.session_state["last_app_mode"] != app_mode:
    st.session_state["last_app_mode"] = app_mode

st.markdown("---")

if app_mode == "繪製個人月班表圖檔":
    if is_module_maintenance(current_unit_label, "producer") and not st.session_state.get("admin_logged_in", False):
        st.warning(f"[ 系統維護中 ] 【{current_unit_label}】繪製個人月班表圖檔系統維護中")
        st.stop()

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
            with st.spinner("正在解析資料與繪製個人月班表，請稍候..."):
                try:
                    start_dt, dates, emp_id, emp_name, cells = process_file_data(current_input)
                    buf = render_schedule_figure(start_dt, dates, emp_id, emp_name, cells, current_unit_label, badge_title="Producer | C.L.F")
                    st.success("個人班表圖片生成成功")
                    render_zoomable_image(buf)
                    st.download_button("點此下載班表影像檔", data=buf, file_name=f"{current_unit_label}_班表_{emp_name}.png", mime="image/png")
                except Exception as e: st.error(f"錯誤：{e}")

elif app_mode == "換班｜選擇換班日期（Alpha測試版）":
    if is_module_maintenance(current_unit_label, "window_filter") and not st.session_state.get("admin_logged_in", False):
        st.warning(f"[ 系統維護中 ] 【{current_unit_label}】換班選擇日期快篩系統維護中")
        st.stop()

    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">換班檢索｜指定 Sign-In 時段組員快篩</div>
        <div class="section-subtitle">Duty Time Window & Sign-In Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2, key="win_selected_role")
    target_path = active_files[selected_role]

    if not os.path.exists(target_path):
        st.error(f"找不到【{current_unit_label} - {selected_role}】的班表檔案，請先至管理員後台上傳")
    else:
        df_search = safe_read_excel(target_path, header=3)
        df_search.columns = [str(c).strip() for c in df_search.columns]
        date_cols = [re.search(r'(\d+/\d+)', str(col)).group(1) for col in df_search.columns[2:] if re.search(r'(\d+/\d+)', str(col))]

        if date_cols:
            target_date = st.selectbox("選擇換班日期", date_cols, key="win_target_date")

            TIME_OPTIONS = [f"{h:02d}:00" for h in range(19)]
            st.write("**Sign-In 時段區間快選**")
            q1, q2, q3, q4 = st.columns(4)
            with q1:
                if st.button("早班 (05-08)", key="q_0508"): st.session_state["win_time_slider"] = ("05:00", "08:00")
            with q2:
                if st.button("中班 (08-12)", key="q_0812"): st.session_state["win_time_slider"] = ("08:00", "12:00")
            with q3:
                if st.button("晚班 (12-18)", key="q_1218"): st.session_state["win_time_slider"] = ("12:00", "18:00")
            with q4:
                if st.button("全時段 (00-18)", key="q_0018"): st.session_state["win_time_slider"] = ("00:00", "18:00")

            default_slider = st.session_state.get("win_time_slider", ("05:00", "08:00"))
            min_time, max_time_sel = st.select_slider("Sign-In 區間", options=TIME_OPTIONS, value=default_slider, key="win_time_slider")

            filter_col1, filter_col2 = st.columns(2)
            with filter_col1: only_main_line = st.checkbox("僅顯示正線勤務", value=False, key="win_main_line")
            with filter_col2: only_long_shift = st.checkbox("僅顯示長班 (>8.5h)", value=False, key="win_long_shift")

            if st.button("搜尋可換班組員名單", key="btn_window_search"):
                log_activity(f"換班快篩 [{current_unit_label} - {selected_role}] 日期:{target_date}")
                all_cols_list = list(df_search.columns[2:])
                raw_candidates = []

                for _, row in df_search.iterrows():
                    emp_id = str(row.iloc[0]).strip()
                    emp_name = str(row.iloc[1]).strip()
                    if not emp_id or emp_id.upper() in ["NAN", "NONE", ""]: continue

                    target_col_idx = next((idx + 2 for idx, col in enumerate(all_cols_list) if target_date in str(col)), -1)
                    if target_col_idx != -1 and target_col_idx < len(row):
                        cell_raw = row.iloc[target_col_idx]
                        parsed = parse_cell(cell_raw)
                        start_t = parsed["start"]

                        if start_t:
                            tr_upper = str(parsed["train"]).strip().upper()
                            raw_cell_upper = str(cell_raw).upper()
                            is_leave = any(k in raw_cell_upper for k in ["PAY", "FAC", "AL", "SL", "CL"]) or tr_upper in ["PAY", "FAC", "AL", "SL", "CL", "DO", "D2W"]
                            is_non_line = is_town_shift(parsed["train"], parsed["note"])
                            is_long = is_overtime(parsed["hours"], parsed["train"], parsed["note"])

                            next_day_sign_in = "無記錄"
                            if target_col_idx + 1 < len(row):
                                next_parsed = parse_cell(row.iloc[target_col_idx + 1])
                                next_day_sign_in = next_parsed["start"] if next_parsed["start"] else (next_parsed["train"] if next_parsed["train"] else "無記錄")

                            raw_candidates.append({
                                "日期": target_date, "員編": emp_id, "姓名": emp_name,
                                "Sign-In": start_t, "Sign-Out": parsed["end"],
                                "車次": translate_train_code(parsed["train"]),
                                "隔日Sign-In": next_day_sign_in, "長班": is_long,
                                "非正線": is_non_line, "請假": is_leave
                            })

                st.session_state["win_raw_candidates"] = raw_candidates
                st.rerun()

            if st.session_state.get("win_raw_candidates") is not None:
                raw_list = st.session_state["win_raw_candidates"]
                filtered_results = []

                for r in raw_list:
                    if not (min_time <= r["Sign-In"] <= max_time_sel): continue
                    if only_main_line and (r["非正線"] or r["請假"]): continue
                    if only_long_shift and not r["長班"]: continue
                    filtered_results.append(r)

                filtered_results = sorted(filtered_results, key=lambda x: (str(x["Sign-In"]), str(x["Sign-Out"])))

                st.markdown(f"### 換班可選人員名單（共符合 {len(filtered_results)} 筆）")

                if filtered_results:
                    c_col1, c_col2 = st.columns(2)
                    for idx, r in enumerate(filtered_results):
                        target_col = c_col1 if idx % 2 == 0 else c_col2
                        with target_col:
                            badges_html = '<div class="badge-group">'
                            if r['長班']: badges_html += '<span class="long-badge">長班</span>'
                            if r['非正線']: badges_html += '<span class="non-line-badge">非正線</span>'
                            badges_html += '</div>'

                            st.markdown(f"""
                            <div class="integrated-crew-box">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                    <div>
                                        <div class="compact-name">{r['姓名']} <span style="color:#94A3B8; font-size:12px;">({r['員編']})</span></div>
                                        <div style="font-size: 13px; color: #38BDF8; font-weight: 700; margin-top: 2px;">班別：{r['車次']}</div>
                                    </div>
                                    <div style="text-align: right; display: flex; flex-direction: column; gap: 3px;">
                                        <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">Sign-In {r['Sign-In']}</div>
                                        <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">Sign-Out {r['Sign-Out']}</div>
                                    </div>
                                </div>
                                <div style="display: flex; gap: 6px; align-items: center; justify-content: space-between; margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.06);">
                                    <span style="font-size: 11px; color: #94A3B8; font-family: monospace;">隔日 Sign-In：<strong style="color:#FCD34D;">{r['隔日Sign-In']}</strong></span>
                                    {badges_html}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            if st.button(f"檢視 {r['姓名']} 完整班表", key=f"win_btn_{r['員編']}_{idx}", use_container_width=True):
                                show_crew_schedule_modal(r['員編'], current_unit_label, badge_title="Window Filter | C.L.F")
                else: st.info("在指定條件內，找不到符合的人員")

elif app_mode == "換假｜選擇換假日期（Alpha測試版）":
    if is_module_maintenance(current_unit_label, "exchange_filter") and not st.session_state.get("admin_logged_in", False):
        st.warning(f"[ 系統維護中 ] 【{current_unit_label}】換假選擇日期快篩系統維護中")
        st.stop()

    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">換假檢索｜選擇換假日期快篩</div>
        <div class="section-subtitle">Shift Exchange Date Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    if "ex_search_performed" not in st.session_state:
        st.session_state["ex_search_performed"] = False

    ex_c1, ex_c2, ex_c3 = st.columns(3)
    with ex_c1: selected_role = st.selectbox("選擇職位類別", ["服勤員", "駕駛", "列車長"], key="ex_role_select")

    sample_path = active_files.get(selected_role, "")
    
    if not sample_path or not os.path.exists(sample_path):
        st.error(f"找不到【{current_unit_label} - {selected_role}】的班表檔案，請先至管理員後台上傳")
    else:
        try:
            df_ex = safe_read_excel(sample_path, header=3)
            df_ex.columns = [str(c).strip() for c in df_ex.columns]
            date_cols = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in df_ex.columns[2:] if re.search(r'(\d+/\d+)', str(c))]

            if not date_cols:
                st.warning("目前的班表檔案中無法解析出有效的日期欄位。")
            else:
                with ex_c2: 
                    target_date = st.selectbox("選擇想休假日期", date_cols, key="ex_target_date")

                with ex_c3: 
                    return_date = st.selectbox("選擇可還假日期", date_cols, index=min(1, len(date_cols)-1), key="ex_return_date")

                is_cross_week = False
                target_week_str = ""
                try:
                    t_m, t_d = map(int, target_date.split('/'))
                    r_m, r_d = map(int, return_date.split('/'))
                    t_dt = date(2026, t_m, t_d)
                    r_dt = date(2026, r_m, r_d)

                    t_sun = t_dt - timedelta(days=(t_dt.weekday() + 1) % 7)
                    t_sat = t_sun + timedelta(days=6)
                    target_week_str = f"{t_sun.month}/{t_sun.day:02d} (日) ~ {t_sat.month}/{t_sat.day:02d} (六)"

                    r_sun = r_dt - timedelta(days=(r_dt.weekday() + 1) % 7)
                    
                    if t_sun != r_sun:
                        is_cross_week = True
                except:
                    pass

                if is_cross_week:
                    st.warning(f"⚠️ **跨週警示**：您選擇的還假日期「{return_date}」與想休假日期「{target_date}」不在同一週！（想休假當週規範區間為：{target_week_str}）")
                else:
                    st.caption(f"📅 **同一週換假區間：{target_week_str}**")

                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    time_filter_options = ["不限"] + [f"{h:02d}:00 以後" for h in range(5, 17)]
                    return_time_filter = st.selectbox("還假日 Sign-In 時間限制", options=time_filter_options, key="ex_time_filter")
                with col_f2:
                    sort_order = st.selectbox("結果排序方式", ["依 Sign-In 時間 (由早至晚)", "依最早 Sign-Out", "依工時長短"], key="ex_sort_order")

                strict_limit = st.checkbox("嚴格過濾：排除前後 5 天內連續上班已達 6 天以上的人員", value=True, key="ex_strict_limit")

                if st.button("搜尋可換假組員名單", key="btn_ex_search"):
                    log_activity(f"換假快篩 [{current_unit_label} - {selected_role}] 想休:{target_date} 還假:{return_date}")
                    raw_candidates = []
                    all_cols = list(df_ex.columns)
                    target_col_idx = next((idx for idx, col in enumerate(all_cols) if idx >= 2 and target_date in str(col)), -1)
                    return_col_idx = next((idx for idx, col in enumerate(all_cols) if idx >= 2 and return_date in str(col)), -1)

                    if target_col_idx != -1 and return_col_idx != -1:
                        for _, row in df_ex.iterrows():
                            emp_id = str(row.iloc[0]).strip()
                            emp_name = str(row.iloc[1]).strip()
                            if not emp_id or emp_id.upper() in ["NAN", "NONE", ""]: continue

                            if target_col_idx >= len(row) or return_col_idx >= len(row): continue

                            parsed_target = parse_cell(row.iloc[target_col_idx])
                            raw_target_str = str(row.iloc[target_col_idx]).strip()
                            is_target_do = ("DO" in raw_target_str.upper()) or ("D2W" in raw_target_str.upper())
                            if not is_target_do: continue

                            parsed_return = parse_cell(row.iloc[return_col_idx])
                            raw_return_str = str(row.iloc[return_col_idx]).strip().upper()
                            is_return_do = ("DO" in raw_return_str) or ("D2W" in raw_return_str)
                            if is_return_do: continue

                            is_long = is_overtime(parsed_return["hours"], parsed_return["train"], parsed_return["note"])
                            is_non_line = is_town_shift(parsed_return["train"], parsed_return["note"])

                            work_count = 0
                            start_check_idx = max(2, target_col_idx - 5)
                            end_check_idx = min(len(row) - 1, target_col_idx + 5)
                            for c_i in range(start_check_idx, end_check_idx + 1):
                                cell_c = parse_cell(row.iloc[c_i])
                                cell_c_raw = str(row.iloc[c_i]).upper()
                                if cell_c["start"] or (not ("DO" in cell_c_raw or "D2W" in cell_c_raw)):
                                    work_count += 1

                            raw_candidates.append({
                                "員編": emp_id,
                                "姓名": emp_name,
                                "想休日": target_date,
                                "想休狀態": raw_target_str.split("\n")[0] if raw_target_str else "DO",
                                "還休日": return_date,
                                "還假車次": translate_train_code(parsed_return["train"]),
                                "Sign-In": parsed_return["start"],
                                "Sign-Out": parsed_return["end"],
                                "工時": parsed_return["hours"],
                                "長班": is_long,
                                "非正線": is_non_line,
                                "連續上班天數": work_count
                            })

                    st.session_state["ex_raw_candidates"] = raw_candidates
                    st.session_state["ex_search_performed"] = True
                    st.rerun()

                if st.session_state.get("ex_search_performed"):
                    raw_list = st.session_state.get("ex_raw_candidates", [])
                    filtered_candidates = []

                    for cand in raw_list:
                        if return_time_filter != "不限":
                            min_allowed = return_time_filter.split(" ")[0]
                            if not cand["Sign-In"] or cand["Sign-In"] < min_allowed:
                                continue

                        if strict_limit and cand["連續上班天數"] >= 6:
                            continue

                        filtered_candidates.append(cand)

                    if sort_order == "依 Sign-In 時間 (由早至晚)":
                        filtered_candidates = sorted(filtered_candidates, key=lambda x: (x["Sign-In"] or "99:99", x["Sign-Out"] or "99:99"))
                    elif sort_order == "依最早 Sign-Out":
                        filtered_candidates = sorted(filtered_candidates, key=lambda x: (x["Sign-Out"] or "99:99", x["Sign-In"] or "99:99"))
                    elif sort_order == "依工時長短":
                        filtered_candidates = sorted(filtered_candidates, key=lambda x: x["工時"] or "0h00m", reverse=True)

                    st.markdown(f"### 換假可選人員名單（共 {len(filtered_candidates)} 位）")

                    if filtered_candidates:
                        c_col1, c_col2 = st.columns(2)
                        for idx, cand in enumerate(filtered_candidates):
                            cand_name = cand.get('姓名', '')
                            cand_id = cand.get('員編', '')
                            target_col = c_col1 if idx % 2 == 0 else c_col2

                            badges_html = '<div class="badge-group">'
                            if cand.get('長班'): badges_html += '<span class="long-badge">長班</span>'
                            if cand.get('非正線'): badges_html += '<span class="non-line-badge">非正線</span>'
                            badges_html += '</div>'

                            with target_col:
                                st.markdown(f"""
                                <div class="integrated-crew-box">
                                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                        <div>
                                            <div class="compact-name">{cand_name} <span style="color:#94A3B8; font-size:12px;">({cand_id})</span></div>
                                            <div style="font-size: 12px; color: #94A3B8; margin-top: 4px; font-family: monospace;">
                                                還休日：{cand.get('還休日')} ｜ 班別：<strong style="color:#38BDF8;">{cand.get('還假車次', '無')}</strong>
                                            </div>
                                        </div>
                                        <div style="text-align: right; display: flex; flex-direction: column; gap: 3px;">
                                            <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">
                                                Sign-In {cand.get('Sign-In', '--:--')}
                                            </div>
                                            <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">
                                                Sign-Out {cand.get('Sign-Out', '--:--')}
                                            </div>
                                            <div style="font-size: 11px; color: #CBD5E1; font-family: monospace; margin-top: 1px;">
                                                ({cand.get('工時', '')})
                                            </div>
                                        </div>
                                    </div>
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.06);">
                                        <span style="font-size: 12px; color: #FCD34D; font-weight: 700; font-family: monospace;">
                                            我想休：{cand.get('想休日')} ({cand.get('想休狀態')})
                                        </span>
                                        {badges_html}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                                if st.button(f"檢視 {cand_name} 完整班表", key=f"ex_btn_{cand_id}_{idx}", use_container_width=True):
                                    show_crew_schedule_modal(cand_id, current_unit_label, badge_title="Exchange | C.L.F")
                    else:
                        st.info("在指定條件內，找不到符合的可換假人員 (可嘗試放寬還假日 Sign-In 時間限制或取消嚴格過濾)")
        except Exception as e:
            st.error(f"讀取換假資料時發生錯誤：{e}")

# --- 底部頁尾貼紙 ---
st.markdown('<div class="footer-badge-container">', unsafe_allow_html=True)
footer_label = f"ADMIN PANEL [{current_unit_label}] // C.L.F EDITION" if st.session_state.get("admin_logged_in", False) else f"C.L.F EDITION [{current_unit_label}]"
if st.button(footer_label, key="bottom_footer_badge"):
    if st.session_state.get("admin_logged_in", False):
        st.session_state["nav_mode"] = "admin_panel" if st.session_state["nav_mode"] == "home" else "home"
    else: st.session_state["show_admin_login"] = True
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)
