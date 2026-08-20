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
    .result-card { background: #1E293B; border-left: 4px solid #3B82F6; border-radius: 8px; padding: 16px; margin-bottom: 12px; color: #F8FAFC; }
    .time-row { font-size: 18px; font-weight: 700; color: #60A5FA; margin-bottom: 8px; font-family: monospace; }
    .name-row { font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #E2E8F0; }
    .train-row { display: inline-block; background: #0F172A; padding: 4px 12px; border-radius: 6px; font-weight: 700; color: #38BDF8; border: 1px solid #334155; }
    .stRadio > div { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; }
    .stRadio label { font-size: 15px !important; font-weight: 600 !important; color: #F8FAFC !important; }
    .stTextInput input { font-size: 18px !important; padding: 14px 16px !important; border-radius: 10px !important; background-color: #1E293B !important; color: #F8FAFC !important; border: 1px solid #475569 !important; }
    div.stButton > button { font-size: 18px !important; font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important; color: #ffffff !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 資料設定 ---
ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
ADMIN_PASSWORD = "Lf0900"
CREW_ACCESS_PASSWORD = "0900"
MAINTENANCE_FLAG_FILE = "maintenance.flag"

def generate_time_options():
    options = ["05:26"]
    for h in range(24):
        for m in [0, 30]:
            t = f"{h:02d}:{m:02d}"
            if t not in options: options.append(t)
    return sorted(list(set(options)))

TIME_OPTIONS = generate_time_options()

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    lines = [l.strip() for l in str(raw).split("\n") if l.strip()]
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    start_t = times[0] if times else ""
    end_t = times[1] if len(times) > 1 else ""
    train = next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and "DO" not in l and "PAY" not in l and "h" not in l), "")
    return dict(start=start_t, end=end_t, train=train)

# --- 主程式流程 ---
st.markdown("""<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>""", unsafe_allow_html=True)

app_mode = st.radio("選擇功能模式", ["生產個人班表圖片檔", "組員動態時段篩選（尋找換班協調專用・Beta測試版）"], horizontal=True)
st.markdown("---")

if app_mode == "生產個人班表圖片檔":
    target_input = st.text_input("輸入 員編 或 姓名", value="A")
    if st.button("立即生成個人班表圖片檔"):
        st.info("功能運作中...")

elif app_mode == "組員動態時段篩選（尋找換班協調專用・Beta測試版）":
    st.subheader("乘務時段區間與 Sign-In Time 快篩工具")
    selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2)
    target_path = ROLE_FILES[selected_role]

    if not os.path.exists(target_path):
        st.error(f"檔案 {target_path} 不存在")
    else:
        df = pd.read_excel(target_path, header=3)
        df.columns = [str(c).strip() for c in df.columns]
        date_cols = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in df.columns[2:] if re.search(r'(\d+/\d+)', str(c))]
        
        c1, c2 = st.columns(2)
        start_date = c1.selectbox("起始日期", date_cols, index=0)
        end_date = c2.selectbox("結束日期", date_cols, index=date_cols.index(start_date))

        c3, c4 = st.columns(2)
        min_time = c3.selectbox("Sign-In Time 區間：從", options=TIME_OPTIONS, index=TIME_OPTIONS.index("05:26") if "05:26" in TIME_OPTIONS else 0)
        max_time = c4.selectbox("Sign-In Time 區間：到", options=TIME_OPTIONS, index=TIME_OPTIONS.index("09:00") if "09:00" in TIME_OPTIONS else len(TIME_OPTIONS)-1)

        if st.button("開始區間檢索符合條件人員"):
            results = []
            target_dates = date_cols[date_cols.index(start_date):date_cols.index(end_date)+1]
            for _, row in df.iterrows():
                for d in target_dates:
                    col_idx = [i for i, c in enumerate(df.columns) if d in str(c)]
                    if col_idx:
                        parsed = parse_cell(row.iloc[col_idx[0]])
                        if parsed["start"] and min_time <= parsed["start"] <= max_time:
                            results.append({"日期": d, "姓名": row.iloc[1], "員編": row.iloc[0], "Sign-In": parsed["start"], "下班": parsed["end"], "班別": parsed["train"]})
            
            st.markdown(f"### 檢索結果 (共 {len(results)} 筆)")
            for r in results:
                st.markdown(f"""
                <div class="result-card">
                    <div class="time-row">{r['Sign-In']} ➔ {r['下班']}</div>
                    <div class="name-row">{r['姓名']} <span style="color:#94A3B8; font-size:14px;">({r['員編']})</span></div>
                    <div class="train-row">班別：{r['班別'] if r['班別'] else '無記錄'}</div>
                </div>
                """, unsafe_allow_html=True)
