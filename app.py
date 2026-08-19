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

st.set_page_config(page_title="🚆 TTN Shift Producer | C.L.F", page_icon="700st.png", layout="centered")

# 📱 完整美化 CSS (包含標題列與卡片結構)
st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding-top: 3.5rem !important; padding-bottom: 3rem !important; }
    .header-container { display: flex; justify-content: space-between; align-items: baseline; width: 100%; margin-bottom: 1rem; }
    .main-title { color: #F8FAFC !important; font-size: 26px; font-weight: 800; margin: 0; }
    .edition-badge { color: #64748B !important; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; }
    .telemetry-title { color: #94A3B8 !important; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .telemetry-value { color: #F8FAFC !important; font-size: 18px; font-weight: 700; font-family: monospace; }
    div.stButton > button { width: 100% !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important; color: #ffffff !important; font-weight: 700; padding: 12px; }
</style>
""", unsafe_allow_html=True)

# 設定
NATIONAL_HOLIDAYS = {"1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節", "6/19": "端午節", "8/25": "中秋節", "9/28": "教師節", "10/10": "國慶日", "10/25": "台灣光復節", "12/25": "行憲紀念日"}
TRANSPORT_PERIODS = {"8/24-8/29": "中秋疏運"}
ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
CREW_ACCESS_PASSWORD = "0900"

# --- 核心邏輯 ---
def draw_bold_text(ax, x, y, text, **kwargs):
    ax.text(x, y, text, **kwargs)
    offset = 0.0001
    for dx, dy in [(offset, 0), (-offset, 0), (0, offset), (0, -offset)]:
        ax.text(x + dx, y + dy, text, **kwargs)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    lines = [l.strip() for l in str(raw).split("\n") if l.strip()]
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    hours = next((l for l in lines if (re.search(r'(\d+h\d+m)', l) or re.search(r'^\d{1,2}:\d{2}$', l)) and l not in times[:2]), "")
    train_code = next((l for l in lines if l not in times and l != hours and not re.match(r'^(DO|PAY|D2W)', l)), "")
    return dict(start=times[0] if len(times) > 0 else "", end=times[1] if len(times) > 1 else "", train=train_code or (lines[0] if any(x in lines[0] for x in ["DO", "PAY"]) else ""), hours=hours)

def process_file_data(input_str):
    input_clean = input_str.strip().upper()
    for role, path in ROLE_FILES.items():
        if os.path.exists(path):
            df = pd.read_excel(path, header=3)
            df.columns = [str(c).strip() for c in df.columns]
            for _, row in df.iterrows():
                if str(row.iloc[0]).strip().upper() == input_clean or str(row.iloc[1]).strip().upper() == input_clean:
                    dates = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in df.columns[2:] if re.search(r'(\d+/\d+)', str(c))]
                    return datetime.strptime("2026/" + dates[0], "%Y/%m/%d").date(), dates, str(row.iloc[0]).strip(), str(row.iloc[1]).strip(), row.iloc[2:].values
    raise ValueError("找不到資料。")

# --- UI 渲染 ---
st.markdown('<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>', unsafe_allow_html=True)
st.markdown('<div class="telemetry-card"><div class="telemetry-title">System Telemetry // 目前系統排班有效週期</div><div class="telemetry-value">請輸入員編載入</div></div>', unsafe_allow_html=True)

target_input = st.text_input("輸入 員編 或 姓名", value="A")
access_password = st.text_input("輸入 系統授權碼", type="password")

if st.button("立即配置個人班表"):
    if access_password == CREW_ACCESS_PASSWORD:
        try:
            start_dt, dates, emp_id, emp_name, cells = process_file_data(target_input)
            weeks = [] # (簡化 build_weeks)
            week = [None] * ((start_dt.weekday() + 1) % 7)
            for dt, raw in zip(dates, cells):
                week.append((dt, parse_cell(raw)))
                if len(week) == 7: weeks.append(week); week = []
            if week: weeks.append(week + [None] * (7 - len(week)))
            
            fig, ax = plt.subplots(figsize=(16, 12), dpi=300)
            ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
            
            RH = 0.75 / len(weeks)
            for ri, week in enumerate(weeks):
                for ci, cell in enumerate(week):
                    if cell:
                        dt, d = cell
                        x, y = 0.02 + ci * 0.138, 0.85 - (ri + 1) * RH
                        ax.add_patch(FancyBboxPatch((x, y), 0.135, RH - 0.005, facecolor="#FFFFFF", edgecolor="#CBD5E1"))
                        draw_bold_text(ax, x + 0.005, y + RH - 0.02, dt, ha="left", va="top", fontproperties=fm.FontProperties(size=8))
                        if d['train']: draw_bold_text(ax, x + 0.067, y + RH * 0.5, d['train'], ha="center", va="center", fontproperties=fm.FontProperties(size=11, weight='bold'))
                        if d['start']: draw_bold_text(ax, x + 0.067, y + RH * 0.78, f"{d['start']} - {d['end']}", ha="center", va="center", fontproperties=fm.FontProperties(size=9))
                        if d['hours']: draw_bold_text(ax, x + 0.13, y + 0.005, f"({d['hours']})", ha="right", va="bottom", color="#475569", fontproperties=fm.FontProperties(size=8))
            
            buf = io.BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight"); buf.seek(0)
            st.image(buf)
            st.download_button("下載班表", data=buf, file_name="duty.png")
        except Exception as e: st.error(f"錯誤: {e}")
