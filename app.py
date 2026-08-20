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
</style>
""", unsafe_allow_html=True)

# --- 常數與設定 ---
ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
ADMIN_PASSWORD, CREW_ACCESS_PASSWORD = "Lf0900", "0900"
MAINTENANCE_FLAG_FILE = "maintenance.flag"

# --- 核心處理函式 ---
def get_file_mtime(path):
    return datetime.fromtimestamp(os.path.getmtime(path)) if os.path.exists(path) else None

def format_mtime(dt):
    if not dt: return "無檔案"
    diff = datetime.now() - dt
    if diff.days > 0: return f"{diff.days} 天前"
    hours = diff.seconds // 3600
    if hours > 0: return f"{hours} 小時前"
    return f"{diff.seconds // 60} 分鐘前"

def is_maintenance_mode(): return os.path.exists(MAINTENANCE_FLAG_FILE)

def set_maintenance_mode(is_maint):
    if is_maint: 
        with open(MAINTENANCE_FLAG_FILE, "w") as f: f.write("ON")
    elif os.path.exists(MAINTENANCE_FLAG_FILE): 
        os.remove(MAINTENANCE_FLAG_FILE)

# (這裡請保留你原本的 parse_cell, is_town_shift, is_overtime, calculate_hours, build_weeks, draw_bold_text 等所有功能函式)
# --- 為了篇幅，此處省略重複的內部邏輯函式，請確認你的程式碼中已包含這些基礎函數 ---
# [提示：請確保上方函式定義區塊完整，接續下方介面邏輯]

# --- 介面主邏輯 ---
st.markdown("""<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>""", unsafe_allow_html=True)

if is_maintenance_mode():
    st.markdown("""<div class="telemetry-card" style="border: 1px solid #EF4444; background: linear-gradient(135deg, #7F1D1D 0%, #450A0A 100%);">
        <div class="telemetry-title" style="color: #FCA5A5;">系統維護公告</div>
        <div class="telemetry-value" style="color: #FEE2E2; font-size: 20px;">系統目前暫停開放維護中</div>
        <div class="telemetry-sub maint-sub">管理員正在更新排班資料，請稍後再試。</div>
    </div>""", unsafe_allow_html=True)
else:
    # 顯示各職位更新時間
    cols = st.columns(3)
    for i, (role, path) in enumerate(ROLE_FILES.items()):
        mtime = get_file_mtime(path)
        cols[i].metric(f"{role} 更新時間", format_mtime(mtime))
    
    st.markdown("---")
    app_mode = st.radio("選擇功能模式", ["生產個人班表圖片檔", "組員動態時段篩選"], horizontal=True)
    
    if app_mode == "生產個人班表圖片檔":
        # ... (原本繪圖區塊邏輯) ...
        pass
    else:
        # ... (原本篩選區塊邏輯) ...
        pass

# --- 管理員區塊 ---
with st.expander("管理員專用：Database"):
    password = st.text_input("管理員密碼", type="password")
    if password == ADMIN_PASSWORD:
        # ... (維護模式與檔案上傳邏輯) ...
        pass
