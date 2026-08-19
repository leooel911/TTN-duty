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

# CSS 優化：強制深色模式與排版
st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 3.5rem 1rem 3rem 1rem !important; }
    .header-container { display: flex; justify-content: space-between; align-items: baseline; width: 100%; margin-bottom: 1rem; }
    .main-title { color: #F8FAFC !important; font-size: 26px; font-weight: 800; margin: 0; }
    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; }
    div.stButton > button { width: 100% !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important; color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

# 設定
NATIONAL_HOLIDAYS = {"1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節", "6/19": "端午節", "8/25": "中秋節", "9/28": "教師節", "10/10": "國慶日", "10/25": "台灣光復節", "12/25": "行憲紀念日"}
TRANSPORT_PERIODS = {"8/24-8/29": "中秋疏運"}
ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
CREW_ACCESS_PASSWORD = "0900"
ADMIN_PASSWORD = "Lf0900"

def draw_bold_text(ax, x, y, text, **kwargs):
    ax.text(x, y, text, **kwargs)
    offset = 0.0001
    for dx, dy in [(offset, 0), (-offset, 0), (0, offset), (0, -offset)]:
        ax.text(x + dx, y + dy, text, **kwargs)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    # 提取工時：強制尋找含有 h 或 : 的行
    hours = next((l for l in lines if (re.search(r'(\d+h\d+m)', l) or re.search(r'^\d{1,2}:\d{2}$', l)) and l not in times[:2]), "")
    
    # 車次代號提取：強制抓取非時間、非工時、非DO/PAY關鍵字的行
    train_code = ""
    for l in lines:
        if l not in times and l != hours and not re.match(r'^(DO|PAY|D2W)', l):
            train_code = l
            break
            
    return dict(
        start=times[0] if len(times) > 0 else "",
        end=times[1] if len(times) > 1 else "",
        train=train_code if train_code else (lines[0] if re.match(r'^(DO|PAY)', lines[0]) else ""),
        hours=hours,
        note=""
    )

def process_file_data(input_str):
    input_clean = input_str.strip().upper()
    matched_row, df_found = None, None
    for role, path in ROLE_FILES.items():
        if os.path.exists(path):
            df_temp = pd.read_excel(path, header=3)
            df_temp.columns = [str(c).strip() for c in df_temp.columns]
            for idx, row in df_temp.iterrows():
                if str(row.iloc[0]).strip().upper() == input_clean or str(row.iloc[1]).strip().upper() == input_clean:
                    matched_row, df_found = row, df_temp
                    break
        if matched_row is not None: break
    if matched_row is None: raise ValueError("找不到資料。")
    col_names = df_found.columns[2:]
    dates = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in col_names if re.search(r'(\d+/\d+)', str(c))]
    start_dt = datetime.strptime("2026/" + dates[0], "%Y/%m/%d").date()
    return start_dt, dates, str(matched_row.iloc[0]).strip(), str(matched_row.iloc[1]).strip(), matched_row.iloc[2:].values

def is_overtime(h):
    # 簡化超時判斷
    return "h" in str(h) and int(re.search(r'(\d+)h', str(h)).group(1)) >= 9

def build_weeks(start_dt, dates, cells):
    weeks, week = [], [None] * ((start_dt.weekday() + 1) % 7)
    for dt, raw in zip(dates, cells):
        week.append((dt, parse_cell(raw)))
        if len(week) == 7: weeks.append(week); week = []
    if week: weeks.append(week + [None] * (7 - len(week)))
    return weeks

# --- UI ---
target_input = st.text_input("輸入 員編 或 姓名", value="A")
access_password = st.text_input("輸入 系統授權碼", type="password")

if st.button("立即配置個人班表"):
    if access_password == CREW_ACCESS_PASSWORD:
        try:
            start_dt, dates, emp_id, emp_name, cells = process_file_data(target_input)
            weeks = build_weeks(start_dt, dates, cells)
            active_transport = {f"{k.split('-')[0].split('/')[0]}/{k.split('-')[0].split('/')[1]}": v for k, v in TRANSPORT_PERIODS.items()} # 簡化疏運對照
            
            fig, ax = plt.subplots(figsize=(16, 12), dpi=300)
            ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
            
            RH = 0.75 / len(weeks)
            for ri, week in enumerate(weeks):
                for ci, cell in enumerate(week):
                    if cell:
                        dt, d = cell
                        x, y = 0.02 + ci * 0.138, 0.85 - (ri + 1) * RH
                        ax.add_patch(FancyBboxPatch((x, y), 0.135, RH - 0.005, facecolor="#FFFFFF", edgecolor="#CBD5E1"))
                        
                        # 資訊繪製
                        draw_bold_text(ax, x + 0.005, y + RH - 0.02, dt, ha="left", va="top", fontproperties=fm.FontProperties(size=8))
                        if d['train']: draw_bold_text(ax, x + 0.067, y + RH * 0.5, d['train'], ha="center", va="center", fontproperties=fm.FontProperties(size=11, weight='bold'))
                        if d['start']: draw_bold_text(ax, x + 0.067, y + RH * 0.78, f"{d['start']} - {d['end']}", ha="center", va="center", fontproperties=fm.FontProperties(size=9))
                        if d['hours']: draw_bold_text(ax, x + 0.13, y + 0.005, f"({d['hours']})", ha="right", va="bottom", color="#991B1B" if is_overtime(d['hours']) else "#475569", fontproperties=fm.FontProperties(size=8))

            buf = io.BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight"); buf.seek(0)
            st.image(buf)
            st.download_button("下載班表", data=buf, file_name="duty.png")
        except Exception as e: st.error(f"解析錯誤: {e}")
