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

st.set_page_config(page_title="TRAIN CREW DUTY ENGINE", page_icon="700st.png", layout="centered")

TAIWAN_TZ = timezone(timedelta(hours=8))

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 4.5rem 1rem 3rem 1rem !important; }
    
    @keyframes online-green-pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.7); }
        70% { transform: scale(1.05); box-shadow: 0 0 0 8px rgba(74, 222, 128, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
    }
    .online-dot {
        width: 8px; height: 8px; background-color: #4ADE80; border-radius: 50%; display: inline-block;
        animation: online-green-pulse 2s infinite ease-in-out; box-shadow: 0 0 10px #4ADE80; margin: 0 8px; vertical-align: middle;
    }
    .header-container { 
        display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;
        width: 100%; margin-bottom: 1.5rem; padding: 22px 20px;
        background: linear-gradient(135deg, #131C31 0%, #0F172A 100%);
        border: 2px solid #38BDF8; border-radius: 14px;
    }
    .title-left-group { display: flex; flex-direction: column; align-items: center; gap: 6px; width: 100%; }
    .main-title { color: #F8FAFC !important; font-size: 24px; font-weight: 800; letter-spacing: 2px; margin: 0; font-family: monospace; }
    .title-subtitle { color: #FFFFFF; font-size: 13px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; font-family: monospace; margin-top: 4px; }
    
    .section-header-box { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 5px solid #3B82F6; border-radius: 10px; padding: 16px 20px; margin-top: 20px; margin-bottom: 20px; }
    .section-title { color: #F8FAFC; font-size: 20px; font-weight: 700; margin: 0; }
    .section-subtitle { color: #94A3B8; font-size: 12px; text-transform: uppercase; margin-top: 4px; }
    .date-banner { background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%); border-left: 5px solid #60A5FA; color: #FFFFFF; font-size: 15px; font-weight: 800; padding: 8px 14px; border-radius: 8px; margin-top: 24px; margin-bottom: 10px; }
    .compact-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 4px solid #3B82F6; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; color: #F8FAFC; }
    .integrated-crew-box { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 4px solid #10B981; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    .time-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .compact-time { font-size: 14px; font-weight: 700; color: #60A5FA; font-family: monospace; }
    .badge-group { display: flex; gap: 4px; align-items: center; }
    .long-badge { background: rgba(153, 27, 27, 0.4); border: 1px solid #EF4444; color: #FCA5A5; font-size: 10px; padding: 1px 6px; border-radius: 4px; }
    .non-line-badge { background: rgba(76, 29, 149, 0.4); border: 1px solid #8B5CF6; color: #C4B5FD; font-size: 10px; padding: 1px 6px; border-radius: 4px; }
    .compact-name { font-size: 15px; font-weight: 600; color: #E2E8F0; }
    .compact-sub { font-size: 12px; color: #94A3B8; font-family: monospace; margin-top: 2px; }
    .action-divider { height: 1px; background: #334155; margin: 12px 0 4px 0; }
    
    div.stButton > button, div.stFormSubmitButton > button { 
        font-weight: 700 !important; padding: 12px 18px !important; border-radius: 10px !important; 
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important;
        border-left: 4px solid #38BDF8 !important; color: #F8FAFC !important; width: 100% !important; 
        margin-top: 6px !important; margin-bottom: 6px !important; font-family: monospace;
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
TITLE = "TRAIN CREW DUTY CALENDAR (SANDBOX)"

ROLE_FILES = {
    "駕駛": "TD.xlsx",
    "列車長": "TM.xlsx",
    "服勤員": "TA.xlsx"
}

BASE_FILES = {
    "駕駛": "TD_base.xlsx",
    "列車長": "TM_base.xlsx",
    "服勤員": "TA_base.xlsx"
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

def log_activity(input_str):
    try:
        now_tw = datetime.now(TAIWAN_TZ).strftime('%Y-%m-%d %H:%M:%S')
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(f"{now_tw} | 查詢: {input_str}\n")
    except: pass

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "admin_logged_in" not in st.session_state: st.session_state["admin_logged_in"] = False
if "nav_mode" not in st.session_state: st.session_state["nav_mode"] = "home"
if "inspect_emp_target" not in st.session_state: st.session_state["inspect_emp_target"] = None
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

# --- 核心字典對照引擎 ---
def build_shift_dict_from_base(base_path):
    dict_map = {}
    if not os.path.exists(base_path): return dict_map
    try:
        df = pd.read_excel(base_path, header=3)
        for _, row in df.iterrows():
            for cell in row.iloc[2:]:
                if pd.isna(cell): continue
                cell_str = str(cell).strip()
                lines = [l.strip() for l in cell_str.split("\n") if l.strip()]
                times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
                if len(times) >= 2:
                    start_t, end_t = times[0], times[1]
                    non_time = [l for l in lines if l not in times and not "h" in l and not "m" in l]
                    if non_time:
                        code = non_time[0].upper()
                        dict_map[code] = {"start": start_t, "end": end_t}
    except: pass
    return dict_map

def parse_cell_with_dict(raw, shift_dict):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    
    code_candidate = lines[0].upper()
    if code_candidate in shift_dict:
        t_info = shift_dict[code_candidate]
        start_time, end_time = t_info["start"], t_info["end"]
        hours = calculate_hours(start_time, end_time)
        return dict(start=start_time, end=end_time, train=code_candidate, hours=hours, note="")
    
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0] or "PAY" in lines[0] or "FAC" in lines[0]):
        return dict(start="", train=lines[0], end="", hours="", note="")

    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
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

def parse_cell(raw):
    return parse_cell_with_dict(raw, {})

def process_file_data(input_str):
    input_clean = input_str.strip().upper()
    matched_row, emp_id, emp_name, df_found, role_matched = None, "", "", None, ""
    for role, path in ROLE_FILES.items():
        if os.path.exists(path):
            df_temp = pd.read_excel(path, header=3)
            df_temp.columns = [str(c).strip() for c in df_temp.columns]
            for idx, row in df_temp.iterrows():
                if str(row.iloc[0]).strip().upper() == input_clean or str(row.iloc[1]).strip().upper() == input_clean:
                    matched_row, emp_id, emp_name, df_found, role_matched = row, str(row.iloc[0]).strip(), str(row.iloc[1]).strip(), df_temp, role
                    break
        if matched_row is not None: break
    if matched_row is None: raise ValueError(f"找不到員編或姓名為「{input_str}」的資料。")
    
    base_p = BASE_FILES.get(role_matched, "")
    shift_dict = build_shift_dict_from_base(base_p) if base_p else {}

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
        
    raw_cells = matched_row.iloc[2:].values
    return start_dt, dates, emp_id, emp_name, raw_cells, shift_dict

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

def build_weeks_with_dict(start_dt, dates, cells, shift_dict):
    first_wd = (start_dt.weekday() + 1) % 7
    weeks, week = [], [None] * first_wd
    for dt, raw in zip(dates, cells):
        week.append((dt, parse_cell_with_dict(raw, shift_dict), str(raw) if not pd.isna(raw) else ""))
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

# --- 授權驗證門戶 ---
if not st.session_state["authenticated"] and not st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <div style="font-size: 34px; font-weight: 900; color: #F8FAFC; font-family: monospace;">CREW DUTY ENGINE</div>
        <div style="color: #64748B; font-size: 11px; font-weight: 600; letter-spacing: 2.5px; text-transform: uppercase; margin-top: 6px; font-family: monospace;">
            BUSY DOING NOTHING PRODUCTIVE<br>C.L.F EDITION (SANDBOX)
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        with st.form("auth_form"):
            entered_emp = st.text_input("使用者員編", value="A", max_chars=10)
            entered_key = st.text_input("系統授權碼", type="password")
            if st.form_submit_button("進入系統"):
                if entered_key == CREW_ACCESS_PASSWORD:
                    st.session_state["authenticated"] = True
                    st.session_state["current_user_id"] = entered_emp.strip()
                    st.rerun()
                elif entered_key == ADMIN_PASSWORD:
                    st.session_state["admin_logged_in"] = True
                    st.session_state["nav_mode"] = "admin_panel"
                    st.rerun()
                else:
                    st.error("授權碼錯誤")
    st.stop()

# --- 管理員後台控制台 ---
if st.session_state.get("nav_mode") == "admin_panel" and st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">管理員專用：Database 控制台與 21號後異動對照設定</div>
        <div class="section-subtitle">Direct Administrator Dashboard</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("← 返回一般系統首頁"):
        st.session_state["nav_mode"] = "home"
        st.rerun()

    st.markdown("---")
    st.subheader("各職位 20 號基準表（字典用）與正式異動新檔管理")
    selected_role = st.selectbox("選擇要管理的職位類別", ["駕駛", "列車長", "服勤員"])
    
    target_path = ROLE_FILES[selected_role]
    base_target_path = BASE_FILES[selected_role]

    col_up1, col_up2 = st.columns(2)
    with col_up1:
        st.markdown(f"**1. 正式班表檔案（{selected_role}）**")
        uploaded_file = st.file_uploader(f"上傳最新班表 ({selected_role})", type=["xlsx", "xls"], key=f"up_{selected_role}")
        if uploaded_file is not None:
            with open(target_path, "wb") as f: f.write(uploaded_file.getbuffer())
            st.success(f"【{selected_role}】正式班表上傳成功")
            st.rerun()
        st.write("狀態：" + ("已上傳" if os.path.exists(target_path) else "無檔案"))

    with col_up2:
        st.markdown(f"**2. 20號基準總表（建立時間對照字典用）**")
        base_file = st.file_uploader(f"上傳 20號基準總表 ({selected_role})", type=["xlsx", "xls"], key=f"base_up_{selected_role}")
        if base_file is not None:
            with open(base_target_path, "wb") as f: f.write(base_file.getbuffer())
            st.success(f"【{selected_role}】20號基準表上傳成功並已建立對照字典！")
            st.rerun()
        st.write("狀態：" + ("已設定基準表" if os.path.exists(base_target_path) else "尚未設定基準表"))

    st.stop()

# --- 標頭與操作模式 ---
st.markdown(f"""
<div class="header-container">
    <div class="title-left-group">
        <div class="main-title">CREW DUTY ENGINE</div>
        <div class="title-subtitle"><span class="online-dot"></span>Hello welcome: {st.session_state.get("current_user_id", "A")}<span class="online-dot"></span></div>
    </div>
</div>
""", unsafe_allow_html=True)

app_mode = st.radio("系統操作模式選擇", [
    "繪製個人月班表圖檔", 
    "換班｜指定時段組員快篩（Alpha測試版）",
    "換假｜日期快篩（Alpha測試版）"
], horizontal=False, label_visibility="collapsed")

st.markdown("---")

# 1. 繪製個人月班表圖檔
if app_mode == "繪製個人月班表圖檔":
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">個人班表圖檔生成</div>
        <div class="section-subtitle">Personal Shift Schedule Image Generator</div>
    </div>
    """, unsafe_allow_html=True)

    target_input = st.text_input("輸入 員編 或 姓名", value="A", key="user_input_field")

    if st.button("立即生成個人班表圖片檔"):
        if not target_input.strip():
            st.warning("請輸入員編或姓名")
        else:
            try:
                start_dt, dates, emp_id, emp_name, cells, shift_dict = process_file_data(target_input)
                active_transport = parse_transport_periods(TRANSPORT_PERIODS)
                font_prop = setup_font()
                def fp(size=9): return fm.FontProperties(fname=font_prop.get_file(), size=size) if font_prop else fm.FontProperties(size=size)
                
                weeks = build_weeks_with_dict(start_dt, dates, cells, shift_dict)
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
                        
                        bg = C_DO_BG if is_pure_hol else (C_PAY_BG if is_pay_shift else (C_WEEKEND_BG if ci in [0,6] else C_WORK_BG))
                        ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=bg))
                        
                        if dt in NATIONAL_HOLIDAYS:
                            draw_bold_text(ax, x + 0.005, ry + RH - 0.004, f"{dt} ({NATIONAL_HOLIDAYS[dt]})", ha="left", va="top", color=C_HOLI_TXT, fontproperties=fp(9.5))
                        else:
                            draw_bold_text(ax, x + 0.005, ry + RH - 0.004, dt, ha="left", va="top", color="#000000", fontproperties=fp(10))

                        cx = x + CW / 2
                        if is_pure_hol: 
                            draw_bold_text(ax, cx, ry + RH * 0.48, tr if tr else "DO", ha="center", va="center", color=C_DO_TXT, fontproperties=fp(14))
                        elif is_pay_shift and not d["start"]: 
                            draw_bold_text(ax, cx, ry + RH * 0.48, tr, ha="center", va="center", color=C_PAY_TXT, fontproperties=fp(14))
                        else:
                            draw_bold_text(ax, cx, ry + RH * 0.65, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                            draw_bold_text(ax, cx, ry + RH * 0.40, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                            draw_bold_text(ax, cx, ry + RH * 0.15, tr, ha="center", va="center", color=C_PAY_TXT if is_pay_shift else "#000000", fontproperties=fp(12))

                buf = io.BytesIO()
                plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()
                
                st.success("個人班表圖片生成成功")
                st.image(buf, use_container_width=True)
                st.download_button("點此下載班表影像檔", data=buf, file_name=f"TTN班表_{emp_name}.png", mime="image/png")
            except Exception as e: st.error(f"錯誤：{e}")

# 2. 換班時段快篩
elif app_mode == "換班｜指定時段組員快篩（Alpha測試版）":
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">指定 Sign-In 時段組員名單快篩</div>
        <div class="section-subtitle">Duty Time Window & Sign-In Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2)
    target_path = ROLE_FILES[selected_role]
    base_p = BASE_FILES[selected_role]
    shift_dict = build_shift_dict_from_base(base_p)

    if not os.path.exists(target_path):
        st.error(f"找不到【{selected_role}】的班表檔案，請先至管理員後台上傳")
    else:
        df_search = pd.read_excel(target_path, header=3)
        df_search.columns = [str(c).strip() for c in df_search.columns]
        date_cols = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in df_search.columns[2:] if re.search(r'(\d+/\d+)', str(c))]

        if date_cols:
            c1, c2 = st.columns(2)
            with c1: start_date = st.selectbox("起始日期", date_cols, index=0)
            with c2: end_date = st.selectbox("結束日期", date_cols, index=0)
            
            c3, c4 = st.columns(2)
            with c3: min_time = st.text_input("Sign-In 從", "05:00")
            with c4: max_time = st.text_input("Sign-In 到", "15:00")

            if st.button("開始區間檢索符合條件人員"):
                s_idx, e_idx = date_cols.index(start_date), date_cols.index(end_date)
                target_dates = date_cols[s_idx:e_idx+1]
                results = []
                
                for _, row in df_search.iterrows():
                    emp_id, emp_name = str(row.iloc[0]).strip(), str(row.iloc[1]).strip()
                    for d_str in target_dates:
                        for idx, col in enumerate(df_search.columns[2:]):
                            if d_str in str(col):
                                cell_raw = row.iloc[idx + 2]
                                parsed = parse_cell_with_dict(cell_raw, shift_dict)
                                if parsed["start"] and min_time <= parsed["start"] <= max_time:
                                    results.append({"日期": d_str, "員編": emp_id, "姓名": emp_name, "開始時間": parsed["start"], "結束時間": parsed["end"], "車次代碼": parsed["train"]})
                
                st.markdown(f"### 檢索結果：共符合 {len(results)} 筆")
                if results:
                    st.dataframe(pd.DataFrame(results), use_container_width=True)

# 3. 換假日期快篩
elif app_mode == "換假｜日期快篩（Alpha測試版）":
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">換假日期快篩系統</div>
        <div class="section-subtitle">Shift Exchange Date Filter Matrix</div>
    </div>
    """, unsafe_allow_html=True)

    selected_role = st.selectbox("選擇職位類別進行換假查詢", ["服勤員", "駕駛", "列車長"])
    target_path = ROLE_FILES[selected_role]
    base_p = BASE_FILES[selected_role]
    shift_dict = build_shift_dict_from_base(base_p)

    if not os.path.exists(target_path):
        st.error(f"找不到【{selected_role}】的班表檔案，請先至管理員後台上傳")
    else:
        df_ex = pd.read_excel(target_path, header=3)
        df_ex.columns = [str(c).strip() for c in df_ex.columns]
        date_cols = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in df_ex.columns[2:] if re.search(r'(\d+/\d+)', str(c))]

        if date_cols:
            ex_c1, ex_c2 = st.columns(2)
            with ex_c1: target_date = st.selectbox("想休假的日期", date_cols, index=0)
            with ex_c2: return_date = st.selectbox("可還假的日期(上班日)", date_cols, index=min(1, len(date_cols)-1))

            if st.button("開始尋找可換假對象"):
                t_idx, r_idx = date_cols.index(target_date), date_cols.index(return_date)
                candidates = []
                
                for _, row in df_ex.iterrows():
                    emp_id, emp_name = str(row.iloc[0]).strip(), str(row.iloc[1]).strip()
                    
                    # 尋找目標日與還假日的儲存格
                    t_cell, r_cell = None, None
                    for idx, col in enumerate(df_ex.columns[2:]):
                        col_str = str(col)
                        if target_date in col_str: t_cell = row.iloc[idx + 2]
                        if return_date in col_str: r_cell = row.iloc[idx + 2]
                    
                    p_target = parse_cell_with_dict(t_cell, shift_dict)
                    p_return = parse_cell_with_dict(r_cell, shift_dict)
                    
                    # 判斷當天是否為休假 (DO) 且還假日是否有班
                    is_rest = "DO" in str(t_cell).upper() or "D2W" in str(t_cell).upper()
                    is_work_return = p_return["start"] != "" or is_valid_train_code(p_return["train"])
                    
                    if is_rest and is_work_return:
                        candidates.append({
                            "員編": emp_id,
                            "姓名": emp_name,
                            "想休日期狀態": f"{target_date} (休假)",
                            "還假日期狀態": f"{return_date} ({p_return['start']}->{p_return['end']} {p_return['train']})"
                        })
                
                st.markdown(f"### 換假對象檢索結果：共找到 {len(candidates)} 位符合條件")
                if candidates:
                    st.dataframe(pd.DataFrame(candidates), use_container_width=True)

# --- 底部貼紙 ---
st.markdown('<div style="text-align: center; margin-top: 3rem;"><hr style="border-color: #334155;">', unsafe_allow_html=True)
if st.button("ADMIN PANEL // C.L.F EDITION (SANDBOX)"):
    st.session_state["admin_logged_in"] = True
    st.session_state["nav_mode"] = "admin_panel"
    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)
