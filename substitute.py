import streamlit as st
import os
import re
import pandas as pd
from datetime import datetime, timezone, timedelta

# 🛡️ 獨立防火牆測試頁面：乘務換班與時段快篩工具
st.set_page_config(page_title="TTN Substitute Finder | C.L.F", page_icon="700st.png", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding-top: 2.5rem !important; padding-bottom: 2rem !important; }
    .main-title { color: #F8FAFC !important; font-size: 24px; font-weight: 800; margin-bottom: 1rem; }
    .card { background: #1E293B; border: 1px solid #334155; border-radius: 10px; padding: 15px; margin-bottom: 12px; }
</style>
""", unsafe_allow_html=True)

ROLE_FILES = {
    "駕駛": "TD.xlsx",
    "列車長": "TM.xlsx",
    "服勤員": "TA.xlsx"
}

def pad_time(t_str):
    if not t_str or ":" not in t_str: return t_str
    parts = str(t_str).split(":")
    return f"{int(parts[0]):02d}:{parts[1]}" if len(parts) == 2 else str(t_str)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="")
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): 
        return dict(start="", train=lines[0], end="", hours="")
    if "PAY" in lines:
        return dict(start="", train="PAY", end="", hours="")
    
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    start_time = pad_time(times[0]) if times else ""
    end_time = pad_time(times[1]) if len(times) > 1 else ""
    
    do_str = next((l for l in lines if "DO" in l or "D2W" in l or "PAY" in l), "")
    real_train = next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and l != do_str and "h" not in l and "m" not in l), "")

    return dict(start=start_time, end=end_time, train=real_train)

st.markdown('<div class="main-title">🛡️ 乘務時段快篩與換班對象協尋 (測試防火牆)</div>', unsafe_allow_html=True)

# 選擇職位
selected_role = st.selectbox("選擇職位類別", ["駕駛", "列車長", "服勤員"])
target_path = ROLE_FILES[selected_role]

if not os.path.exists(target_path):
    st.error(f"找不到【{selected_role}】的班表檔案 ({target_path})，請先至主系統上傳。")
else:
    # 讀取 Excel
    df = pd.read_excel(target_path, header=3)
    df.columns = [str(c).strip() for c in df.columns]
    
    # 找出所有日期欄位
    col_names = list(df.columns[2:])
    date_cols = []
    for col in col_names:
        match_d = re.search(r'(\d+/\d+)', str(col))
        if match_d:
            date_cols.append(match_d.group(1))

    col1, col2 = st.columns(2)
    with col1:
        chosen_date = st.selectbox("選擇查詢日期", date_cols if date_cols else ["無日期"])
    with col2:
        max_start_time = st.text_input("篩選：報到時間早於 (含)", value="09:00")

    if st.button("開始檢索符合條件人員"):
        if not chosen_date or chosen_date == "無日期":
            st.warning("請選擇有效的日期！")
        else:
            # 找出對應的欄位名稱
            target_col_idx = -1
            for idx, col in enumerate(df.columns[2:]):
                if chosen_date in str(col):
                    target_col_idx = idx + 2
                    break
            
            if target_col_idx == -1:
                st.error("在表中找不到對應的日期欄位。")
            else:
                results = []
                for _, row in df.iterrows():
                    emp_id = str(row.iloc[0]).strip()
                    emp_name = str(row.iloc[1]).strip()
                    cell_raw = row.iloc[target_col_idx]
                    
                    parsed = parse_cell(cell_raw)
                    start_t = parsed["start"]
                    
                    # 篩選邏輯：有開始時間，且小於等於設定的時間
                    if start_t and start_t <= max_start_time:
                        results.append({
                            "員編": emp_id,
                            "姓名": emp_name,
                            "報到時間": start_t,
                            "收工時間": parsed["end"],
                            "車次": parsed["train"]
                        })
                
                st.markdown(f"### 📋 查詢結果：{chosen_date} 於 {max_start_time} 前報到之{selected_role}（共 {len(results)} 人）")
                
                if results:
                    for r in results:
                        st.markdown(f"""
                        <div class="card">
                            <b>👤 {r['姓名']}</b> ({r['員編']})<br>
                            🕒 報到：<b>{r['報到時間']}</b> ➔ 收工：{r['收工時間']}<br>
                            🚆 當日車次：<code>{r['車次'] if r['車次'] else '無車次記錄'}</code>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("沒有找到符合該條件的人員。")
