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
    .result-card { background: #1E293B; border-left: 4px solid #3B82F6; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; color: #F8FAFC; }
    .time-row { font-size: 19px; font-weight: 700; color: #60A5FA; margin-bottom: 6px; font-family: monospace; }
    .name-row { font-size: 16px; font-weight: 600; margin-bottom: 6px; color: #E2E8F0; }
    .sub-info-row { font-size: 13px; color: #94A3B8; font-family: monospace; display: flex; gap: 16px; flex-wrap: wrap; }
    .stRadio > div { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; }
    .stRadio label { font-size: 15px !important; font-weight: 600 !important; color: #F8FAFC !important; }
    .stTextInput input { font-size: 18px !important; padding: 14px 16px !important; border-radius: 10px !important; background-color: #1E293B !important; color: #F8FAFC !important; border: 1px solid #475569 !important; }
    div.stButton > button { font-size: 18px !important; font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important; color: #ffffff !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 基本設定 ---
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

def is_overtime(h):
    if not h: return False
    try:
        p = str(h).replace("h", ":").replace("m", "").split(":")
        return (int(p[0]) * 60 + int(p[1])) > 510
    except: return False

def is_town_shift(tr, note):
    # 擴充非正線勤務與特殊班別關鍵字（包含 WRSL, TTN 等）
    keywords = ["TOWN", "STD", "TTN", "DTT", "OGT", "FAC", "DS", "H9", "OGC", "WRSL"]
    return any(kw in f"{tr} {note}".upper() for kw in keywords)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): 
        return dict(start="", train=lines[0], end="", hours="", note="")
    
    if "PAY" in lines and not times: return dict(start="", train="PAY", end="", hours="", note="")

    start_time = pad_time(times[0]) if times else ""
    end_time = pad_time(times[1]) if len(times) > 1 else ""
    hours = calculate_hours(start_time, end_time)
    
    do_str = next((l for l in lines if "DO" in l or "D2W" in l or "PAY" in l), "")
    real_train = next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and l != do_str and "h" not in l and "m" not in l), "")
    notes = [l for l in lines if l not in times and l != real_train]

    return dict(start=start_time, end=end_time, train=real_train, hours=hours, note=" ".join(notes))

# --- 主體 ---
st.markdown("""<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>""", unsafe_allow_html=True)
app_mode = st.radio("選擇功能模式", ["生產個人班表圖片檔", "組員動態時段篩選（尋找換班協調專用・Beta測試版）"], horizontal=True)
st.markdown("---")

if app_mode == "組員動態時段篩選（尋找換班協調專用・Beta測試版）":
    selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2)
    target_path = ROLE_FILES[selected_role]

    if not os.path.exists(target_path):
        st.error(f"找不到班表檔案")
    else:
        df = pd.read_excel(target_path, header=3)
        df.columns = [str(c).strip() for c in df.columns]
        date_cols = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in df.columns[2:] if re.search(r'(\d+/\d+)', str(c))]
        
        c1, c2 = st.columns(2)
        start_date = c1.selectbox("起始日期", date_cols, index=0)
        end_date = c2.selectbox("結束日期", date_cols, index=date_cols.index(start_date))

        c3, c4 = st.columns(2)
        min_time = c3.selectbox("Sign-In Time 區間：從", options=TIME_OPTIONS, index=TIME_OPTIONS.index("05:26"))
        max_time = c4.selectbox("Sign-In Time 區間：到", options=TIME_OPTIONS, index=TIME_OPTIONS.index("09:00"))

        if st.button("開始區間檢索符合條件人員"):
            results = []
            target_dates = date_cols[date_cols.index(start_date):date_cols.index(end_date)+1]
            all_cols = list(df.columns[2:])
            for _, row in df.iterrows():
                for d in target_dates:
                    col_idx = next((i for i, c in enumerate(all_cols) if d in str(c)), -1)
                    if col_idx != -1:
                        cell_raw = row.iloc[col_idx + 2]
                        parsed = parse_cell(cell_raw)
                        if parsed["start"] and min_time <= parsed["start"] <= max_time:
                            # 找隔日
                            next_day_val = "無記錄"
                            if col_idx + 1 < len(all_cols):
                                next_p = parse_cell(row.iloc[col_idx + 3])
                                next_day_val = next_p["start"] if next_p["start"] else (next_p["train"] if next_p["train"] else "無記錄")
                            
                            # 判斷是否為非正線勤務
                            is_non_line = is_town_shift(parsed["train"], parsed["note"])

                            results.append({
                                "Sign-In": parsed["start"], "下班": parsed["end"], "姓名": row.iloc[1], 
                                "員編": row.iloc[0], "車次": parsed["train"], "隔日": next_day_val,
                                "長班": is_overtime(parsed["hours"]), "非正線": is_non_line
                            })
            
            results.sort(key=lambda x: x["Sign-In"])
            st.markdown(f"### 檢索結果 (共 {len(results)} 筆)")
            for r in results:
                # 長班標記與非正線標記
                long_shift_badge = '<span style="color:#F87171; font-size:14px; margin-left:8px;">● 長班</span>' if r['長班'] else ''
                non_line_badge = '<span style="background:#4C1D95; color:#C4B5FD; font-size:11px; padding:2px 6px; border-radius:4px; margin-left:8px; font-weight:600;">非正線勤務</span>' if r['非正線'] else ''
                
                st.markdown(f"""
                <div class="result-card">
                    <div class="time-row">{r['Sign-In']} ➔ {r['下班']} {long_shift_badge} {non_line_badge}</div>
                    <div class="name-row">{r['姓名']} <span style="color:#94A3B8; font-size:14px;">({r['員編']})</span></div>
                    <div class="sub-info-row">
                        <span>班別：{r['車次'] if r['車次'] else '無'}</span>
                        <span>隔日 Sign-In：{r['隔日']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
else:
    st.write("請切換至篩選模式進行查詢。")
