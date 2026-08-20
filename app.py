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
    
    /* 優化後的精鍊卡片樣式：去除了突兀方框，強調時間與隔日資訊 */
    .result-card { background: #1E293B; border-left: 4px solid #3B82F6; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; color: #F8FAFC; }
    .time-row { font-size: 19px; font-weight: 700; color: #60A5FA; margin-bottom: 6px; font-family: monospace; }
    .name-row { font-size: 16px; font-weight: 600; margin-bottom: 6px; color: #E2E8F0; }
    .sub-info-row { font-size: 13px; color: #94A3B8; font-family: monospace; display: flex; gap: 16px; }
    
    .stRadio > div { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; }
    .stRadio label { font-size: 15px !important; font-weight: 600 !important; color: #F8FAFC !important; }
    .stTextInput input { font-size: 18px !important; padding: 14px 16px !important; border-radius: 10px !important; background-color: #1E293B !important; color: #F8FAFC !important; border: 1px solid #475569 !important; }
    div.stButton > button { font-size: 18px !important; font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important; color: #ffffff !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

ROLE_FILES = {"駕駛": "TD.xlsx", "列車長": "TM.xlsx", "服勤員": "TA.xlsx"}
ADMIN_PASSWORD = "Lf0900"
CREW_ACCESS_PASSWORD = "0900"
MAINTENANCE_FLAG_FILE = "maintenance.flag"

def generate_time_options():
    options = ["05:26"]
    for h in range(24):
        for m in [0, 30]:
            t_str = f"{h:02d}:{m:02d}"
            if t_str not in options: options.append(t_str)
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

st.markdown("""<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>""", unsafe_allow_html=True)

app_mode = st.radio("選擇功能模式", ["生產個人班表圖片檔", "組員動態時段篩選（尋找換班協調專用・Beta測試版）"], horizontal=True)
st.markdown("---")

if app_mode == "生產個人班表圖片檔":
    target_input = st.text_input("輸入 員編 或 姓名", value="A")
    if st.button("立即生成個人班表圖片檔"): st.info("請切換至對應模式。")

elif app_mode == "組員動態時段篩選（尋找換班協調專用・Beta測試版）":
    st.subheader("乘務時段區間與 Sign-In Time 快篩工具")
    selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2)
    target_path = ROLE_FILES[selected_role]

    if not os.path.exists(target_path):
        st.error(f"找不到【{selected_role}】的班表檔案 ({target_path})")
    else:
        df_search = pd.read_excel(target_path, header=3)
        df_search.columns = [str(c).strip() for c in df_search.columns]
        
        date_cols = []
        for col in df_search.columns[2:]:
            match_d = re.search(r'(\d+/\d+)', str(col))
            if match_d: date_cols.append(match_d.group(1))

        if not date_cols:
            st.error("表中未偵測到有效日期欄位")
        else:
            default_min_idx = TIME_OPTIONS.index("05:26") if "05:26" in TIME_OPTIONS else 0
            default_max_idx = TIME_OPTIONS.index("09:00") if "09:00" in TIME_OPTIONS else len(TIME_OPTIONS)-1

            c1, c2 = st.columns(2)
            with c1: start_date = st.selectbox("起始日期", date_cols, index=0)
            
            start_date_idx = date_cols.index(start_date) if start_date in date_cols else 0
            with c2: end_date = st.selectbox("結束日期", date_cols, index=start_date_idx)

            c3, c4 = st.columns(2)
            with c3: min_time = st.selectbox("Sign-In Time 區間：從", options=TIME_OPTIONS, index=default_min_idx)
            with c4: max_time = st.selectbox("Sign-In Time 區間：到", options=TIME_OPTIONS, index=default_max_idx)

            if st.button("開始區間檢索符合條件人員"):
                try:
                    s_idx = date_cols.index(start_date)
                    e_idx = date_cols.index(end_date)
                    target_dates = date_cols[s_idx:e_idx+1] if s_idx <= e_idx else []
                except: target_dates = []

                if not target_dates:
                    st.warning("起始日期不可大於結束日期")
                else:
                    search_results = []
                    all_cols_list = list(df_search.columns[2:])

                    for _, row in df_search.iterrows():
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()
                        
                        for d_str in target_dates:
                            target_col_idx = -1
                            actual_col_pos = -1
                            for idx, col in enumerate(all_cols_list):
                                if d_str in str(col):
                                    target_col_idx = idx + 2
                                    actual_col_pos = idx
                                    break
                            
                            if target_col_idx != -1:
                                cell_raw = row.iloc[target_col_idx]
                                parsed = parse_cell(cell_raw)
                                start_t = parsed["start"]
                                
                                if start_t and min_time <= start_t <= max_time:
                                    # 尋找隔日 Sign-In 時間
                                    next_day_sign_in = "無記錄"
                                    if actual_col_pos + 1 < len(all_cols_list):
                                        next_cell_raw = row.iloc[target_col_idx + 1]
                                        next_parsed = parse_cell(next_cell_raw)
                                        if next_parsed["start"]:
                                            next_day_sign_in = next_parsed["start"]
                                        elif next_parsed["train"]:
                                            next_day_sign_in = next_parsed["train"] # 如果是 DO 或 PAY 等代號
                                    
                                    search_results.append({
                                        "日期": d_str,
                                        "員編": emp_id,
                                        "姓名": emp_name,
                                        "Sign-In": start_t,
                                        "收工時間": parsed["end"],
                                        "車次": parsed["train"] if parsed["train"] else "無",
                                        "隔日Sign-In": next_day_sign_in
                                    })

                    # 依照 Sign-In 時間由早到晚排序
                    search_results = sorted(search_results, key=lambda x: x["Sign-In"])

                    st.markdown(f"### 檢索結果：{start_date} 至 {end_date} ｜ Sign-In {min_time} ~ {max_time}（共符合 {len(search_results)} 筆）")
                    
                    if search_results:
                        for r in search_results:
                            st.markdown(f"""
                            <div class="result-card">
                                <div class="time-row">{r['Sign-In']} ➔ {r['收工時間']}</div>
                                <div class="name-row">{r['姓名']} <span style="color:#94A3B8; font-size:14px;">({r['員編']})</span></div>
                                <div class="sub-info-row">
                                    <span>班別：{r['车次'] if '车次' in r else r['車次']}</span>
                                    <span>隔日 Sign-In：{r['隔日Sign-In']}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("在指定的日期與 Sign-In 區間內，沒有找到符合條件的人員")
