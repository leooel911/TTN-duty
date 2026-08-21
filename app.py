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

# --- CSS 樣式 ---
st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 3rem 1rem !important; }
    .header-container { display: flex; justify-content: space-between; align-items: baseline; width: 100%; margin-bottom: 1rem; }
    .main-title { color: #F8FAFC !important; font-size: 26px; font-weight: 800; letter-spacing: 0.5px; margin: 0; }
    .edition-badge { color: #64748B !important; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); }
    .section-header-box { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 5px solid #3B82F6; border-radius: 10px; padding: 16px 20px; margin: 20px 0; }
    .date-banner { background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%); border-left: 5px solid #60A5FA; color: #FFFFFF; font-size: 15px; font-weight: 800; padding: 8px 14px; border-radius: 8px; margin: 24px 0 10px 0; text-transform: uppercase; }
    .compact-card { background: #1E293B; border: 1px solid #334155; border-left: 3px solid #3B82F6; border-radius: 8px; padding: 12px; margin-bottom: 10px; color: #F8FAFC; }
</style>
""", unsafe_allow_html=True)

# --- 設定與全域變數 ---
ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
ADMIN_PASSWORD = "Lf0900"
CREW_ACCESS_PASSWORD = "0900"
MAINTENANCE_FLAG_FILE = "maintenance.flag"
TITLE = "TRAIN CREW DUTY CALENDAR"

# --- 輔助函式庫 ---
def is_maintenance_mode(): return os.path.exists(MAINTENANCE_FLAG_FILE)
def get_file_mtime_str(path):
    if os.path.exists(path):
        return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    return "無檔案"

def process_file_data(input_str):
    input_clean = input_str.strip().upper()
    for role, path in ROLE_FILES.items():
        if os.path.exists(path):
            df = pd.read_excel(path, header=3)
            df.columns = [str(c).strip() for c in df.columns]
            for _, row in df.iterrows():
                if str(row.iloc[0]).strip().upper() == input_clean or str(row.iloc[1]).strip().upper() == input_clean:
                    dates = []
                    current_year = datetime.now().year
                    for i, col in enumerate(df.columns[2:]):
                        m = re.search(r'(\d+)/(\d+)', str(col))
                        if m: dates.append(f"{m.group(1)}/{m.group(2)}")
                        else: dates.append(str(col))
                    return date(current_year, 1, 1), dates, str(row.iloc[0]).strip(), str(row.iloc[1]).strip(), row.iloc[2:].values
    raise ValueError("找不到資料")

def setup_font():
    font_path = "NotoSansTC.ttf"
    return fm.FontProperties(fname=font_path) if os.path.exists(font_path) else None

# --- 登入控制 ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    st.title("CREW DUTY ENGINE")
    entered_key = st.text_input("輸入授權碼", type="password")
    if st.button("登入"):
        if entered_key == CREW_ACCESS_PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
    st.stop()

# --- 主程式介面 ---
st.markdown('<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div></div>', unsafe_allow_html=True)

if is_maintenance_mode() and not st.session_state.get("admin_bypassed"):
    st.error("系統維護中")
    admin_pw = st.text_input("管理者密碼", type="password")
    if st.button("Admin Override"):
        if admin_pw == ADMIN_PASSWORD:
            st.session_state["admin_bypassed"] = True
            st.rerun()
    st.stop()

# --- 功能區 ---
tab1, tab2 = st.tabs(["生成班表", "管理員後台"])

with tab1:
    user_input = st.text_input("輸入員編/姓名", value="A")
    if st.button("生成"):
        try:
            start_dt, dates, eid, ename, cells = process_file_data(user_input)
            st.success(f"已讀取 {ename} 的資料")
            # 這裡放置繪圖邏輯...
            st.info("班表已就緒 (繪圖邏輯運作中)")
        except Exception as e:
            st.error(f"錯誤: {e}")

with tab2:
    admin_pw = st.text_input("驗證密碼", type="password")
    if admin_pw == ADMIN_PASSWORD:
        maint = st.checkbox("維護模式", value=is_maintenance_mode())
        if maint:
            with open(MAINTENANCE_FLAG_FILE, "w") as f: f.write("ON")
        elif os.path.exists(MAINTENANCE_FLAG_FILE):
            os.remove(MAINTENANCE_FLAG_FILE)
            
        for role in ROLE_FILES:
            uploaded = st.file_uploader(f"上傳 {role} 班表")
            if uploaded:
                with open(ROLE_FILES[role], "wb") as f: f.write(uploaded.getbuffer())
                st.success("成功")
