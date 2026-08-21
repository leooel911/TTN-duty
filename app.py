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
    
    .section-header-box { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 5px solid #3B82F6; border-radius: 10px; padding: 16px 20px; margin-top: 20px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .section-title { color: #F8FAFC; font-size: 20px; font-weight: 700; letter-spacing: 0.5px; margin: 0; }
    .section-subtitle { color: #94A3B8; font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

    .date-banner { background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%); border-left: 5px solid #60A5FA; color: #FFFFFF; font-size: 15px; font-weight: 800; padding: 8px 14px; border-radius: 8px; margin-top: 24px; margin-bottom: 10px; letter-spacing: 1px; text-transform: uppercase; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }
    .compact-card { background: #1E293B; border: 1px solid #334155; border-left: 3px solid #3B82F6; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; color: #F8FAFC; transition: all 0.25s ease; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
    
    .stRadio > label { display: none !important; }
    .stRadio > div { background: transparent !important; display: flex; flex-direction: column; gap: 10px; }
    .stRadio label { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px !important; padding: 16px 20px !important; width: 100% !important; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }
    
    div.stButton > button { font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%) !important; color: #ffffff !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# 設定
ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
ADMIN_PASSWORD = "Lf0900"
CREW_ACCESS_PASSWORD = "0900"
LOG_FILE = "activity_log.txt"

# --- 輔助函數 ---
def log_activity(input_str):
    try:
        log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 查詢: {input_str}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(log_entry)
    except: pass

def get_file_mtime_str(path):
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(timezone(timedelta(hours=8)))
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

# --- 登入控制 ---
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    st.markdown("<h1 style='text-align:center'>CREW DUTY ENGINE</h1>", unsafe_allow_html=True)
    entered_key = st.text_input("輸入授權碼", type="password")
    if st.button("安全登入"):
        if entered_key == CREW_ACCESS_PASSWORD:
            st.session_state["authenticated"] = True; st.rerun()
        else: st.error("授權碼錯誤")
    st.stop()

# --- 主介面 ---
st.markdown("""<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>""", unsafe_allow_html=True)

st.markdown(f"""
<div class="telemetry-card">
    <div class="telemetry-title">目前系統排班週期 & 伺服器資料狀態</div>
    <div class="telemetry-value" style="font-size: 20px; color: #60A5FA; margin-bottom: 8px;">{get_schedule_range()}</div>
    <div class="telemetry-sub">
        伺服器資料狀態：<br>
        - 駕駛更新：{get_file_mtime_str(ROLE_FILES["駕駛"])}<br>
        - 列車長更新：{get_file_mtime_str(ROLE_FILES["列車長"])}<br>
        - 服勤員更新：{get_file_mtime_str(ROLE_FILES["服勤員"])}
    </div>
</div>
""", unsafe_allow_html=True)

app_mode = st.radio("系統操作模式", ["生產個人班表圖片檔", "換班｜尋找指定時段報到組員"], horizontal=False)
st.markdown("---")

if app_mode == "生產個人班表圖片檔":
    st.markdown("""<div class="section-header-box"><div class="section-title">個人班表圖檔生成</div><div class="section-subtitle">Personal Shift Schedule Image Generator</div></div>""", unsafe_allow_html=True)
    target_input = st.text_input("輸入 員編 或 姓名 (例如: A023300 or 波莉)", value="A")
    if st.button("立即生成個人班表圖片檔"):
        log_activity(target_input)
        st.success("已觸發繪製流程 (紀錄已更新)")
        # ... (繪圖與生成邏輯請銜接您原本的繪圖區塊) ...

# --- 管理員區塊 ---
with st.expander("管理員專用：Database"):
    password = st.text_input("管理員密碼", type="password")
    if password == ADMIN_PASSWORD:
        st.subheader("查詢紀錄清單")
        col1, col2 = st.columns(2)
        if col1.button("🔄 刷新紀錄"): st.rerun()
        if col2.button("🗑️ 清除紀錄"):
            if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
            st.rerun()
        
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = f.readlines()
                for line in reversed(logs[-20:]): st.text(line.strip())
        else: st.info("無紀錄")
        
        st.markdown("---")
        st.subheader("檔案上傳")
        role = st.selectbox("選擇職位", ["駕駛", "列車長", "服勤員"])
        uploaded = st.file_uploader(f"上傳 {role} 班表")
        if uploaded:
            with open(ROLE_FILES[role], "wb") as f: f.write(uploaded.getbuffer())
            st.success("上傳成功")
    elif password: st.error("密碼錯誤")
