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

# --- 毛玻璃視覺設計 ---
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

    .header-container { 
        display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;
        width: 100%; margin-bottom: 1.2rem; padding: 24px 20px;
        backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    .main-title { color: #F8FAFC !important; font-size: 22px; font-weight: 800; letter-spacing: 2px; margin: 0; font-family: monospace; }
    .title-subtitle { color: #FFFFFF; font-size: 12px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; font-family: monospace; margin-top: 4px; }

    .telemetry-card { 
        background: rgba(30, 41, 59, 0.45) !important; 
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08) !important; border-left: 4px solid #3B82F6 !important; border-radius: 16px; padding: 16px 20px; margin-bottom: 16px; 
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
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
        border: 1px solid rgba(96, 165, 250, 0.3); border-left: 4px solid #60A5FA; color: #FFFFFF; font-size: 13px; font-weight: 800; padding: 10px 16px; border-radius: 12px; margin-top: 24px; margin-bottom: 12px; letter-spacing: 1px; text-transform: uppercase;
        font-family: monospace;
    }

    .integrated-crew-box {
        background: rgba(30, 41, 59, 0.6) !important;
        backdrop-filter: blur(16px) !important; -webkit-backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important; border-left: 4px solid #10B981 !important; 
        border-radius: 14px 14px 0 0 !important;
        padding: 16px !important; margin-bottom: 0px !important;
    }

    .time-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .compact-time { font-size: 13px; font-weight: 700; color: #60A5FA; font-family: monospace; }
    .badge-group { display: flex; gap: 6px; align-items: center; }

    .long-badge { background: rgba(153, 27, 27, 0.3); border: 1px solid rgba(239, 68, 68, 0.5); color: #FCA5A5; font-size: 10px; padding: 2px 8px; border-radius: 6px; font-weight: 600; }
    .non-line-badge { background: rgba(76, 29, 149, 0.3); border: 1px solid rgba(139, 92, 246, 0.5); color: #C4B5FD; font-size: 10px; padding: 2px 8px; border-radius: 6px; font-weight: 600; }

    .compact-name { font-size: 15px; font-weight: 600; color: #E2E8F0; }
    .compact-sub { font-size: 11px; color: #94A3B8; font-family: monospace; margin-top: 3px; }

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

    div.stButton > button[kind="secondary"] { 
        border-radius: 0 0 14px 14px !important; 
        border-top: none !important;
        border-left: 4px solid #10B981 !important; 
        margin-top: 0px !important; 
        margin-bottom: 16px !important;
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
    elif "macintosh" in ua or "mac os" in ua: device = "Mac"
    elif "windows" in ua: device = "Windows PC"
    else: device = "Desktop / Other"
    return device

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

# ==================== 獨立檢視指定組員完整班表 (Inspector Mode) ====================
if st.session_state.get("inspect_emp_target") is not None:
    target_emp = st.session_state["inspect_emp_target"]
    current_unit = st.session_state.get("current_unit", "TTN")
    
    status_placeholder = st.empty()
    progress_bar = st.progress(0)
    status_placeholder.markdown(f'<div class="loading-status-text">「{target_emp}」的完整班表載入中，請稍後...</div>', unsafe_allow_html=True)
    progress_bar.progress(40)

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

        progress_bar.progress(80)

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

        progress_bar.progress(100)
        status_placeholder.empty()
        progress_bar.empty()

        st.success(f"已成功載入 {emp_name} ({emp_id}) 之完整月班表")
        render_zoomable_image(buf)
        st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"{current_unit}_班表_{emp_name}.png", mime="image/png")
    except Exception as e:
        status_placeholder.empty()
        progress_bar.empty()
        st.error(f"載入完整班表時發生錯誤: {e}")

    st.stop()

# --- 前置授權碼門戶檢查 ---
if not st.session_state["authenticated"] and not st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <div style="font-size: 32px; font-weight: 900; letter-spacing: 1.5px; color: #F8FAFC; font-family: monospace;">CREW DUTY ENGINE</div>
        <div style="color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-top: 8px; font-family: monospace;">
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
    <div class="main-title">CREW DUTY ENGINE</div>
    <div style="color: #94A3B8; font-size: 11px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; font-family: monospace; margin-top: 6px;">
        BUSY DOING NOTHING PRODUCTIVE<br>
        C.L.F EDITION
    </div>
    <div class="title-subtitle">
        <span class="online-dot"></span>HELLO WELCOME: {current_unit_label} | {current_operator_id}<span class="online-dot"></span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="test-env-banner">
    <div class="test-env-title">測試環境運行中（TEST ENVIRONMENT）</div>
    <div class="test-env-sub">目前為內部測試階段|(所屬運轉單位組員查詢使用)</div>
</div>
""", unsafe_allow_html=True)

# ==================== 一般系統首頁介面 ====================
active_files = get_current_role_files()
missing_files = []
for role in ["駕駛", "列車長", "服勤員"]:
    path = active_files[role]
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        missing_files.append(role)

td_time = get_file_mtime_str(active_files["駕駛"])
tm_time = get_file_mtime_str(active_files["列車長"])
ta_time = get_file_mtime_str(active_files["服勤員"])
sched_range = get_schedule_range()

st.markdown(f"""
<div class="telemetry-card">
    <div class="telemetry-title">[{current_unit_label}] 目前系統排班週期 & 伺服器資料狀態</div>
    <div class="telemetry-value" style="font-size: 20px; color: #60A5FA; margin-bottom: 6px;">
        {sched_range}
    </div>
    <div class="telemetry-sub">
        - 駕駛更新：{td_time}<br>
        - 列車長更新：{tm_time}<br>
        - 服勤員更新：{ta_time}
    </div>
</div>
""", unsafe_allow_html=True)

app_mode = st.radio("系統操作模式選擇", [
    "繪製個人月班表圖檔", 
    "換班｜指定時段組員名單快篩（Alpha測試版）",
    "換假｜日期快篩（Alpha測試版）"
], horizontal=False, label_visibility="collapsed")

st.markdown("---")

if app_mode == "繪製個人月班表圖檔":
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
            try:
                status_placeholder = st.empty()
                progress_bar = st.progress(0)
                status_placeholder.markdown(f'<div class="loading-status-text">班表繪製中，請稍後...</div>', unsafe_allow_html=True)
                progress_bar.progress(30)

                start_dt, dates, emp_id, emp_name, cells = process_file_data(current_input)
                progress_bar.progress(70)

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
            except Exception as e: 
                status_placeholder.empty()
                progress_bar.empty()
                st.error(f"錯誤：{e}")

elif app_mode == "換班｜指定時段組員名單快篩（Alpha測試版）":
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">指定 Sign-In 時段組員名單快篩</div>
        <div class="section-subtitle">Duty Time Window & Sign-In Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2, key="win_selected_role")
    target_path = active_files[selected_role]

    if not os.path.exists(target_path):
        st.error(f"找不到【{current_unit_label} - {selected_role}】的班表檔案，請先至管理員後台上傳")
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

        date_cols = [re.search(r'(\d+/\d+)', str(col)).group(1) for col in df_search.columns[2:] if re.search(r'(\d+/\d+)', str(col))]

        if not date_cols: st.error("表中未偵測到有效日期欄位")
        else:
            TIME_OPTIONS = [f"{h:02d}:00" for h in range(19)]
            target_default = "03:00" if selected_role == "駕駛" else "05:00"
            earliest_default = target_default if target_default in TIME_OPTIONS else TIME_OPTIONS[0]
            default_min_idx = TIME_OPTIONS.index(earliest_default)

            if "win_start_date" not in st.session_state: st.session_state["win_start_date"] = date_cols[0]
            if "win_end_date" not in st.session_state: st.session_state["win_end_date"] = date_cols[0]

            c1, c2 = st.columns(2)
            with c1: start_date = st.selectbox("起始日期", date_cols, key="win_start_date")
            with c2: end_date = st.selectbox("結束日期", date_cols, key="win_end_date")

            c3, c4 = st.columns(2)
            with c3: min_time = st.selectbox("Sign-In Time 區間：從", options=TIME_OPTIONS, index=default_min_idx, key=f"min_time_selectbox_{selected_role}")
            to_time_options = ["-- (僅查單一時間點)"] + TIME_OPTIONS
            with c4: max_time_sel = st.selectbox("Sign-In Time 區間：到", options=to_time_options, index=1, key=f"max_time_selectbox_{selected_role}_{min_time}")

            filter_col1, filter_col2 = st.columns(2)
            with filter_col1: only_main_line = st.checkbox("僅顯示正線勤務", value=False, key="win_main_line")
            with filter_col2: only_long_shift = st.checkbox("僅顯示長班 (>8.5h)", value=False, key="win_long_shift")

            if st.button("開始區間檢索符合條件人員", key="btn_window_search"):
                log_activity(f"時段快篩 [{current_unit_label} - {selected_role}] {start_date}~{end_date}")
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
                            target_col_idx, actual_col_pos = -1, -1
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
                                    matched_time_cond = (start_t == min_time) if max_time_sel.startswith("--") else (min_time <= start_t <= max_time_sel)
                                    if matched_time_cond:
                                        tr_upper = str(parsed["train"]).strip().upper()
                                        raw_cell_upper = str(cell_raw).upper()
                                        is_leave = "PAY" in raw_cell_upper or "FAC" in raw_cell_upper or tr_upper in ["PAY", "FAC", "DO", "D2W"]
                                        is_non_line = is_town_shift(parsed["train"], parsed["note"])
                                        is_long = is_overtime(parsed["hours"], parsed["train"], parsed["note"])

                                        if only_main_line and (is_non_line or is_leave): continue
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

                    st.markdown(f"### 檢索結果：{start_date} ~ {end_date} （共符合 {len(search_results)} 筆）")

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

                            target_stream_col = c_col1 if (col_idx % 2 == 0) else c_col2
                            
                            # 修復：名單方塊 HTML 與按鈕整合
                            with target_stream_col:
                                with st.container():
                                    st.markdown(f"""
                                    <div class="integrated-crew-box">
                                        <div class="time-header-row">
                                            <span class="compact-time">{r['Sign-In']} -> {r['收工時間']}</span>
                                            {badges_html}
                                        </div>
                                        <div class="compact-name" style="margin-top: 4px;">{r['姓名']} <span style="color:#94A3B8; font-size:12px;">({r['員編']})</span></div>
                                        <div class="compact-sub" style="margin-top: 3px;">班別: {r['車次']}</div>
                                        <div class="compact-sub" style="margin-top: 3px;">隔日勤務時間: {r['隔日Sign-In']}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    if st.button(f"查看 {r['姓名']} 完整班表", key=f"win_inspect_{r['員編']}_{r['日期']}_{idx}", use_container_width=True, type="secondary"):
                                        st.session_state["inspect_emp_target"] = str(r['員編']).strip()
                                        st.rerun()
                                    
                            col_idx += 1
                    else: st.info("無符合條件之人員")

elif app_mode == "換假｜日期快篩（Alpha測試版）":
    if "ex_sub_mode" not in st.session_state: st.session_state["ex_sub_mode"] = "search_form"

    # 修復：換假系統完整班表模式加上載入進度條
    if st.session_state["ex_sub_mode"] == "inspect_image":
        target_emp = st.session_state["ex_selected_emp"]
        saved_role = st.session_state.get("ex_saved_role", "服勤員")
        saved_date = st.session_state.get("ex_saved_target_date", "")

        status_placeholder = st.empty()
        progress_bar = st.progress(0)
        status_placeholder.markdown(f'<div class="loading-status-text">「{target_emp}」的完整班表繪製中，請稍後...</div>', unsafe_allow_html=True)
        progress_bar.progress(40)

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
            start_dt, dates, emp_id, emp_name, cells = process_file_data(current_input)
            active_transport = parse_transport_periods(TRANSPORT_PERIODS)
            font_prop = setup_font()
            def fp(size=9): return fm.FontProperties(fname=font_prop.get_file(), size=size) if font_prop else fm.FontProperties(size=size)

            progress_bar.progress(80)

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

            progress_bar.progress(100)
            status_placeholder.empty()
            progress_bar.empty()

            st.success(f"已成功載入 {emp_name} ({emp_id}) 之完整月班表")
            render_zoomable_image(buf)
            st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"{current_unit_label}_班表_{emp_name}.png", mime="image/png")
        except Exception as e: 
            status_placeholder.empty()
            progress_bar.empty()
            st.error(f"載入完整班表時發生錯誤: {e}")
        st.stop()

    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">換假日期快篩系統</div>
        <div class="section-subtitle">Shift Exchange Date Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    # 換假對象檢索介面維持原邏輯...
