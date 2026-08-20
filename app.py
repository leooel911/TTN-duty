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

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 3rem 1rem !important; }
    .header-container { display: flex; justify-content: space-between; align-items: baseline; width: 100%; margin-bottom: 1rem; }
    .main-title { color: #F8FAFC !important; font-size: 26px; font-weight: 800; letter-spacing: 0.5px; margin: 0; }
    .edition-badge { color: #64748B !important; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); }
    .telemetry-title { color: #94A3B8 !important; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .telemetry-value { color: #F8FAFC !important; font-size: 18px; font-weight: 700; font-family: monospace; }
    .telemetry-sub { margin-top: 10px; padding-top: 8px; border-top: 1px solid #334155; font-size: 13px; color: #94A3B8; }
    .maint-sub { border-top: 1px solid #991B1B !important; color: #FECACA !important; }
    
    .date-banner { background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%); border-left: 5px solid #60A5FA; color: #FFFFFF; font-size: 16px; font-weight: 800; padding: 10px 16px; border-radius: 8px; margin-top: 28px; margin-bottom: 14px; letter-spacing: 1.5px; text-transform: uppercase; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }

    .result-card { background: #1E293B; border-left: 3px solid #3B82F6; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; color: #F8FAFC; }
    .time-row { font-size: 19px; font-weight: 700; color: #60A5FA; margin-bottom: 6px; font-family: monospace; }
    .name-row { font-size: 16px; font-weight: 600; margin-bottom: 6px; color: #E2E8F0; }
    .sub-info-row { font-size: 13px; color: #94A3B8; font-family: monospace; display: flex; gap: 16px; flex-wrap: wrap; }
    
    .stRadio > div { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; }
    .stRadio label { font-size: 15px !important; font-weight: 600 !important; color: #F8FAFC !important; }
    .stTextInput input { font-size: 18px !important; padding: 14px 16px !important; border-radius: 10px !important; background-color: #1E293B !important; color: #F8FAFC !important; border: 1px solid #475569 !important; }
    div.stButton > button { font-size: 18px !important; font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important; color: #ffffff !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 工具函式 ---
def get_file_mtime(path):
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime)
    return None

def format_mtime(dt):
    if not dt: return "無資料"
    diff = datetime.now() - dt
    if diff.days > 0: return f"{diff.days} 天前"
    hours = diff.seconds // 3600
    if hours > 0: return f"{hours} 小時前"
    return f"{diff.seconds // 60} 分鐘前"

# --- 常數 ---
NATIONAL_HOLIDAYS = {"1/1": "元旦", "2/28": "和平紀念日", "5/1": "勞動節", "10/10": "國慶日"}
TRANSPORT_PERIODS = {"9/24-9/29": "中秋疏運"}
TITLE = "TRAIN CREW DUTY CALENDAR"
ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
ADMIN_PASSWORD, CREW_ACCESS_PASSWORD = "Lf0900", "0900"
MAINTENANCE_FLAG_FILE = "maintenance.flag"

# ... (其餘原有的 parse_cell, is_town_shift 等函式保持不變) ...
def generate_time_options():
    options = []
    for h in range(24):
        for m in [0, 30]: options.append(f"{h:02d}:{m:02d}")
    options.extend(["04:00", "04:30", "05:00", "05:15", "05:26", "05:30", "06:00"])
    return sorted(list(set(options)))

TIME_OPTIONS = generate_time_options()
def set_maintenance_mode(is_maintenance):
    if is_maintenance: with open(MAINTENANCE_FLAG_FILE, "w") as f: f.write("ON")
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
    ax.text(x + offset, y, text, **kwargs)
    ax.text(x, y + offset, text, **kwargs)
    ax.text(x - offset, y, text, **kwargs)
    ax.text(x, y - offset, text, **kwargs)
def parse_transport_periods(raw_periods, year=2026):
    expanded = {}
    for k, v in raw_periods.items():
        if "-" in k:
            parts = k.split("-")
            s_m, s_d = map(int, parts[0].strip().split("/"))
            e_m, e_d = map(int, parts[1].strip().split("/"))
            cur = date(year, s_m, s_d)
            end_dt = date(year, e_m, e_d)
            while cur <= end_dt:
                expanded[f"{cur.month}/{cur.day}"] = v
                cur += timedelta(days=1)
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

# --- Main Interface ---
st.markdown("""<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>""", unsafe_allow_html=True)

if is_maintenance_mode():
    st.markdown("""
    <div class="telemetry-card" style="border: 1px solid #EF4444; background: linear-gradient(135deg, #7F1D1D 0%, #450A0A 100%);">
        <div class="telemetry-title" style="color: #FCA5A5;">系統維護公告</div>
        <div class="telemetry-value" style="color: #FEE2E2; font-size: 20px;">系統目前暫停開放維護中</div>
        <div class="telemetry-sub maint-sub">管理員正在更新排班資料或進行系統維護，請稍後再試。</div>
    </div>
    """, unsafe_allow_html=True)
else:
    # 顯示更新時間卡片
    latest_update = min([get_file_mtime(p) for p in ROLE_FILES.values() if os.path.exists(p)], default=None)
    st.markdown(f"""
    <div class="telemetry-card">
        <div class="telemetry-title">資料庫最後更新時間</div>
        <div class="telemetry-value">{format_mtime(latest_update)}</div>
        <div class="telemetry-sub">Data sync successfully via central server.</div>
    </div>
    """, unsafe_allow_html=True)

    app_mode = st.radio("選擇功能模式", ["生產個人班表圖片檔", "組員動態時段篩選（尋找換班協調專用・Beta測試版）"], horizontal=True)
    st.markdown("---")
    
    # ... (後面原本的邏輯維持原樣即可) ...
    # 記得補上原本的繪圖邏輯與篩選邏輯區塊，程式碼在此處省略以節省空間，請繼續使用你原本的邏輯。
