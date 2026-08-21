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
    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); position: relative; overflow: hidden; }
    .telemetry-card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: #3B82F6; }
    .telemetry-title { color: #94A3B8 !important; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .telemetry-value { color: #F8FAFC !important; font-size: 18px; font-weight: 700; font-family: monospace; }
    .telemetry-sub { margin-top: 10px; padding-top: 8px; border-top: 1px solid #334155; font-size: 13px; color: #94A3B8; }
    .maint-sub { border-top: 1px solid #991B1B !important; color: #FECACA !important; }
    .section-header-box { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 5px solid #3B82F6; border-radius: 10px; padding: 16px 20px; margin-top: 20px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .section-title { color: #F8FAFC; font-size: 20px; font-weight: 700; letter-spacing: 0.5px; margin: 0; }
    .section-subtitle { color: #94A3B8; font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }
    .date-banner { background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%); border-left: 5px solid #60A5FA; color: #FFFFFF; font-size: 15px; font-weight: 800; padding: 8px 14px; border-radius: 8px; margin-top: 24px; margin-bottom: 10px; letter-spacing: 1px; text-transform: uppercase; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }
    .compact-card { background: #1E293B; border: 1px solid #334155; border-left: 3px solid #3B82F6; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; color: #F8FAFC; transition: all 0.25s ease; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
    .admin-override-btn div.stButton > button { border: 1px solid #334155 !important; transition: all 0.25s ease !important; }
    .stRadio label { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px !important; padding: 16px 20px !important; width: 100% !important; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); transition: all 0.2s ease; cursor: pointer; }
    div.stButton > button { font-size: 18px !important; font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important; color: #ffffff !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 常數 ---
NATIONAL_HOLIDAYS = {"1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節", "6/19": "端午節", "9/25": "中秋節", "9/28": "教師節", "10/10": "國慶日", "10/25": "台灣光復節", "12/25": "行憲紀念日"}
TRANSPORT_PERIODS = {"9/24-9/29": "中秋疏運"}
ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
ADMIN_PASSWORD = "Lf0900"
CREW_ACCESS_PASSWORD = "0900"
MAINTENANCE_FLAG_FILE = "maintenance.flag"

# --- 初始化狀態 ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "admin_bypassed" not in st.session_state: st.session_state["admin_bypassed"] = False
if "user_input_field" not in st.session_state: st.session_state["user_input_field"] = "A"

# --- 核心邏輯函式 ---
def get_file_mtime_str(path):
    if os.path.exists(path):
        return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
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

def is_maintenance_mode(): return os.path.exists(MAINTENANCE_FLAG_FILE)

def set_maintenance_mode(is_maint):
    if is_maint: 
        with open(MAINTENANCE_FLAG_FILE, "w") as f: f.write("ON")
    elif os.path.exists(MAINTENANCE_FLAG_FILE): os.remove(MAINTENANCE_FLAG_FILE)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    lines = [l.strip() for l in str(raw).split("\n") if l.strip()]
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    start = times[0] if times else ""
    end = times[1] if len(times) > 1 else ""
    train = next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and "h" not in l), "無")
    return dict(start=start, end=end, train=train, hours="", note="")

def process_file_data(input_str):
    input_clean = input_str.strip().upper()
    for role, path in ROLE_FILES.items():
        if os.path.exists(path):
            df = pd.read_excel(path, header=3)
            df.columns = [str(c).strip() for c in df.columns]
            for _, row in df.iterrows():
                if str(row.iloc[0]).strip().upper() == input_clean or str(row.iloc[1]).strip().upper() == input_clean:
                    dates = [re.search(r'(\d+/\d+)', str(c)).group(1) if re.search(r'(\d+/\d+)', str(c)) else str(c) for c in df.columns[2:]]
                    return date(datetime.now().year, 1, 1), dates, str(row.iloc[0]).strip(), str(row.iloc[1]).strip(), row.iloc[2:].values
    raise ValueError("找不到人員資料")

# --- 路由：登入檢查 ---
if not st.session_state["authenticated"]:
    st.markdown("""<div style="text-align: center; margin-top: 4rem;"><div style="font-size: 40px; font-weight: 900; color: #F8FAFC;">CREW DUTY ENGINE</div><div style="color: #64748B; font-size: 12px; text-transform: uppercase; margin-top: 5px;">C.L.F Edition</div></div>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        entered_key = st.text_input("授權碼", type="password", label_visibility="collapsed")
        if st.button("安全登入"):
            if entered_key == CREW_ACCESS_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
    st.stop()

# --- 主程式區 ---
st.markdown('<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>', unsafe_allow_html=True)

# 維護模式檢查
if is_maintenance_mode() and not st.session_state["admin_bypassed"]:
    st.error("系統維護中")
    admin_pw = st.text_input("管理員密碼", type="password")
    if st.button("Admin Override"):
        if admin_pw == ADMIN_PASSWORD:
            st.session_state["admin_bypassed"] = True
            st.rerun()
    st.stop()

# 顯示系統狀態
st.markdown(f'<div class="telemetry-card"><div class="telemetry-title">資料同步狀態</div><div class="telemetry-value">{get_schedule_range()}</div></div>', unsafe_allow_html=True)

# 功能選項
app_mode = st.radio("功能選擇", ["生產個人班表圖片檔", "尋找指定時段報到組員"], horizontal=True)

if app_mode == "生產個人班表圖片檔":
    target_input = st.text_input("輸入員編/姓名", value=st.session_state["user_input_field"])
    if st.button("生成圖片"):
        try:
            start_dt, dates, eid, ename, cells = process_file_data(target_input)
            st.success(f"已生成 {ename} 的班表")
            # 這裡您可以繼續放置原本的 Matplotlib 繪圖邏輯
        except Exception as e: st.error(f"錯誤: {e}")

with st.expander("管理員專用"):
    if st.text_input("密碼", type="password") == ADMIN_PASSWORD:
        if st.checkbox("維護模式", value=is_maintenance_mode()): set_maintenance_mode(True)
        else: set_maintenance_mode(False)
        for r in ROLE_FILES:
            up = st.file_uploader(f"上傳 {r}")
            if up:
                with open(ROLE_FILES[r], "wb") as f: f.write(up.getbuffer())
                st.success("成功")
