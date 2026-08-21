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
    .block-container { padding: 3rem 1rem !important; }
    
    /* 專業科技感標題區樣式 */
    .header-container { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        width: 100%; 
        margin-bottom: 1.5rem; 
        padding-bottom: 12px;
        border-bottom: 1px solid #1E293B;
    }
    .title-left-group {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .main-title { 
        color: #F8FAFC !important; 
        font-size: 24px; 
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
        box-shadow: 0 0 10px #38BDF8;
        display: inline-block;
    }
    .title-subtitle {
        color: #64748B;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        font-family: monospace;
    }
    .edition-badge { 
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important;
        border: 1px solid #334155;
        color: #38BDF8 !important; 
        font-size: 11px; 
        font-weight: 700; 
        letter-spacing: 1.5px; 
        text-transform: uppercase; 
        padding: 8px 14px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        font-family: monospace;
    }

    /* 施工中質感黃色暗調框樣式 */
    .maintenance-msg-box {
        background: linear-gradient(135deg, #271C0C 100%, #171005 100%);
        border: 1px solid #854D0E;
        border-left: 5px solid #CA8A04;
        padding: 16px 20px;
        border-radius: 8px;
        color: #FEF08A;
        font-size: 14px;
        font-weight: 600;
        line-height: 1.6;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 16px rgba(133, 77, 14, 0.2);
    }

    /* 管理員維護解鎖模式識別列 */
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
    
    /* 核心修復：強制讓 Streamlit 的水平區塊（stHorizontalBlock）內的欄位左右並排各分一半 */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        gap: 12px !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 0 !important;
    }

    /* 統一按鈕的高質感與外型 */
    div.stButton > button { 
        font-weight: 700 !important; 
        padding: 12px 10px !important; 
        border-radius: 10px !important; 
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; 
        border: 1px solid #334155 !important;
        border-left: 4px solid #3B82F6 !important;
        color: #38BDF8 !important; 
        width: 100% !important; 
        margin-top: 10px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.25s ease !important;
        letter-spacing: 1px;
    }
    div.stButton > button:hover {
        border-color: #38BDF8 !important;
        border-left-color: #38BDF8 !important;
        color: #FFFFFF !important;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.35), 0 6px 16px rgba(0,0,0,0.5) !important;
        transform: translateY(-2px) !important;
    }

    /* 右側「管理員登入」按鈕的專屬高級琥珀/微紅工業風點綴 */
    .admin-btn-col button {
        border-left-color: #EF4444 !important;
        color: #FCA5A5 !important;
    }
    .admin-btn-col button:hover {
        border-left-color: #F87171 !important;
        background: linear-gradient(135deg, #7F1D1D 0%, #450A0A 100%) !important;
        color: #FFFFFF !important;
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
MAINTENANCE_FLAG_FILE = "maintenance.flag"
LOG_FILE = "activity_log.txt"

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
        log_entry = f"{now_tw} | 裝置: {device_info} | 查詢: {input_str}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(log_entry)
    except: pass

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "admin_bypassed" not in st.session_state: st.session_state["admin_bypassed"] = False
if "direct_to_admin" not in st.session_state: st.session_state["direct_to_admin"] = False
if "user_input_field" not in st.session_state: st.session_state["user_input_field"] = "A"

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

def set_maintenance_mode(is_maintenance):
    if is_maintenance:
        with open(MAINTENANCE_FLAG_FILE, "w") as f: f.write("ON")
    else:
        if os.path.exists(MAINTENANCE_FLAG_FILE): os.remove(MAINTENANCE_FLAG_FILE)

def is_maintenance_mode(): return os.path.exists(MAINTENANCE_FLAG_FILE)

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

# --- 🔒 系統維護模式檢查 ---
if is_maintenance_mode() and not st.session_state.get("admin_bypassed", False) and not st.session_state.get("direct_to_admin", False):
    st.markdown("""<div style="text-align: center; margin-top: 3rem; margin-bottom: 1.5rem;"><div style="font-size: 34px; font-weight: 900; letter-spacing: 1px; color: #EF4444;">SYSTEM UNDER MAINTENANCE</div><div style="color: #64748B; font-size: 11px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-top: 5px;">C.L.F // BUSY DOING NOTHING PRODUCTIVE // C.L.F EDITION</div></div>""", unsafe_allow_html=True)
    
    col_m1, col_m2, col_m3 = st.columns([1, 2, 1])
    with col_m2:
        st.markdown("""<div class="maintenance-msg-box">系統目前正在進行排班資料更新或維護中，請稍候再試。</div>""", unsafe_allow_html=True)
        admin_unlock = st.text_input("管理員密碼", type="password", placeholder="請輸入管理員密碼...", key="maint_unlock_input")
        
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            btn_m1 = st.button("進入系統", key="maint_btn_1")
        with b_col2:
            st.markdown('<div class="admin-btn-col">', unsafe_allow_html=True)
            btn_m2 = st.button("管理員登入", key="maint_btn_2")
            st.markdown('</div>', unsafe_allow_html=True)

        if btn_m1:
            if admin_unlock == ADMIN_PASSWORD:
                st.session_state["admin_bypassed"] = True
                st.success("管理員身分驗證成功")
                st.rerun()
            else:
                st.error("密碼錯誤")
        elif btn_m2:
            if admin_unlock == ADMIN_PASSWORD:
                st.session_state["direct_to_admin"] = True
                st.session_state["admin_bypassed"] = True
                st.success("直接進入管理員後台")
                st.rerun()
            else:
                st.error("管理員密碼錯誤")
    st.stop()

# --- 🔒 前置授權碼門戶檢查（完美左右並排等寬對稱按鈕） ---
if not st.session_state["authenticated"] and not st.session_state.get("admin_bypassed", False) and not st.session_state.get("direct_to_admin", False):
    st.markdown("""<div style="text-align: center; margin-top: 4rem; margin-bottom: 2rem;"><div style="font-size: 40px; font-weight: 900; letter-spacing: 1px; color: #F8FAFC;">CREW DUTY ENGINE</div><div style="color: #64748B; font-size: 12px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-top: 5px;">C.L.F // BUSY DOING NOTHING PRODUCTIVE // C.L.F EDITION</div></div>""", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        entered_key = st.text_input("金鑰 / 密碼", type="password", placeholder="請輸入授權碼或管理員密碼...", label_visibility="collapsed")
        
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            btn_auth = st.button("進入系統", key="auth_btn_1")
        with b_col2:
            st.markdown('<div class="admin-btn-col">', unsafe_allow_html=True)
            btn_admin = st.button("管理員登入", key="auth_btn_2")
            st.markdown('</div>', unsafe_allow_html=True)

        if btn_auth:
            if entered_key == CREW_ACCESS_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("授權碼錯誤，請重新輸入")
        elif btn_admin:
            if entered_key == ADMIN_PASSWORD:
                st.session_state["direct_to_admin"] = True
                st.session_state["admin_bypassed"] = True
                st.success("管理員驗證成功，正在載入後台...")
                st.rerun()
            else:
                st.error("管理員密碼錯誤")
    st.stop()

# --- 🔓 主系統介面 (專業科技感標題區) ---
st.markdown("""
<div class="header-container">
    <div class="title-left-group">
        <div class="main-title"><span class="status-dot"></span>CREW DUTY ENGINE</div>
        <div class="title-subtitle">C.L.F // BUSY DOING NOTHING PRODUCTIVE</div>
    </div>
    <div class="edition-badge">C.L.F EDITION</div>
</div>
""", unsafe_allow_html=True)

# 若目前是管理員透過維護模式解鎖進入，顯示頂部專屬預覽狀態列
if st.session_state.get("admin_bypassed", False) and is_maintenance_mode():
    st.markdown("""
    <div class="admin-bypass-banner">
        <span>[!] ADMIN BYPASS MODE // 目前正處於維護模式預覽中（僅限管理員可見）</span>
    </div>
    """, unsafe_allow_html=True)

# --- 如果是透過管理員登入直接導向，優先展示後台 ---
if st.session_state.get("direct_to_admin", False):
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">管理員專用：Database 控制台</div>
        <div class="section-subtitle">Direct Administrator Dashboard</div>
    </div>
    """, unsafe_allow_html=True)

    st.success("歡迎回來，管理員 LEO")
    
    if st.button("← 返回一般首頁"):
        st.session_state["direct_to_admin"] = False
        st.rerun()

    st.markdown("---")
    st.subheader("查詢紀錄清單")
    col_log_1, col_log_2 = st.columns([1, 1])
    with col_log_1:
        if st.button("🔄 刷新紀錄"): st.rerun()
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
    st.subheader("系統維護控制台")
    current_maint = is_maintenance_mode()
    maint_toggle = st.checkbox("暫停開放系統服務 (維護模式)", value=current_maint)
    if maint_toggle != current_maint:
        set_maintenance_mode(maint_toggle)
        if not maint_toggle:
            st.session_state["admin_bypassed"] = False
        st.rerun()
    
    if current_maint:
        if st.button("解除維護模式（恢復全體開放）"):
            set_maintenance_mode(False)
            st.session_state["admin_bypassed"] = False
            st.success("維護模式已解除")
            st.rerun()

    st.markdown("---")
    st.subheader("管理員檔案上傳區")
    selected_role = st.selectbox("選擇要上傳的職位類別", ["駕駛", "列車長", "服勤員"])
    uploaded_file = st.file_uploader(f"上傳【{selected_role}】班表檔案", type=["xlsx", "xls", "csv", "txt"])
    if uploaded_file:
        with open(ROLE_FILES[selected_role], "wb") as f: f.write(uploaded_file.getbuffer())
        st.success("上傳成功")

    st.stop()

td_time = get_file_mtime_str(ROLE_FILES["駕駛"])
tm_time = get_file_mtime_str(ROLE_FILES["列車長"])
ta_time = get_file_mtime_str(ROLE_FILES["服勤員"])
sched_range = get_schedule_range()

st.markdown(f"""
<div class="telemetry-card">
    <div class="telemetry-title">目前系統排班週期 & 伺服器資料狀態</div>
    <div class="telemetry-value" style="font-size: 22px; color: #60A5FA; margin-bottom: 8px;">{sched_range}</div>
    <div class="telemetry-sub">
        伺服器資料狀態：<br>
        - 駕駛更新：{td_time}<br>
        - 列車長更新：{tm_time}<br>
        - 服勤員更新：{ta_time}
    </div>
</div>
""", unsafe_allow_html=True)

app_mode = st.radio("系統操作模式選擇", ["生產個人班表圖片檔", "換班｜尋找指定時段報到組員（Alpha測試版）"], horizontal=False)
st.markdown("---")

if app_mode == "生產個人班表圖片檔":
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

elif app_mode == "換班｜尋找指定時段報到組員（Alpha測試版）":
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
            with c1: start_date = st.selectbox("起始日期", date_cols, index=0)
            start_date_idx = date_cols.index(start_date) if start_date in date_cols else 0
            with c2: end_date = st.selectbox("結束日期", date_cols, index=start_date_idx)

            c3, c4 = st.columns(2)
            with c3: min_time = st.selectbox("Sign-In Time 區間：從", options=TIME_OPTIONS, index=default_min_idx, key="min_time_selectbox")
            with c4: max_time = st.selectbox("Sign-In Time 區間：到", options=TIME_OPTIONS, index=default_max_idx, key="max_time_selectbox")

            filter_col1, filter_col2 = st.columns(2)
            with filter_col1: only_main_line = st.checkbox("僅顯示正線勤務", value=False)
            with filter_col2: only_long_shift = st.checkbox("僅顯示長班 (>8.5h)", value=False)

            if st.button("開始區間檢索符合條件人員"):
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
                            if r['長班']: badges_html += '<span class="long-badge">●長班</span>'
                            if r['非正線']: badges_html += '<span class="non-line-badge">非正線</span>'
                            badges_html += '</div>'
                            
                            card_html = f"""
                            <div class="compact-card">
                                <div class="time-header-row">
                                    <span class="compact-time">{r['Sign-In']} ➔ {r['收工時間']}</span>
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
