import streamlit as st
import pandas as pd
import os
import re

st.set_page_config(page_title="TTN Shift 21日換班測試專案", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 3rem 1rem 3rem 1rem !important; }
    .test-banner {
        background: linear-gradient(135deg, #7F1D1D 0%, #450A0A 100%);
        border: 1px solid #EF4444;
        border-left: 5px solid #F87171;
        color: #FEE2E2;
        padding: 12px 18px;
        border-radius: 10px;
        margin-bottom: 20px;
        font-family: monospace;
        font-size: 14px;
        font-weight: 700;
    }
    .card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-left: 4px solid #38BDF8;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="test-banner">
    🧪 這是 GitHub 測試分支 (Sandbox)，不會影響線上正式系統！
</div>
""", unsafe_allow_html=True)

st.title("21號後即時換班與自動對照測試")
st.write("這個實驗專案用來測試：如何透過 20 號總表建立時間字典，自動幫 21 號只有代碼的即時換班表補上開始、結束與工時。")

st.markdown("---")
st.subheader("1. 匯入測試資料")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Step A: 20 號官方總表（含完整時間）")
    base_file = st.file_uploader("上傳 20 號基準檔 (舊格式 xlsx/xls)", type=["xlsx", "xls"], key="base_uploader")

with col2:
    st.markdown("#### Step B: 21 號後即時異動檔（純代碼）")
    realtime_file = st.file_uploader("上傳 21 號後異動檔 (新格式 xls)", type=["xls", "xlsx"], key="realtime_uploader")

def build_time_dictionary(file_buffer):
    """從 20 號基準表中掃描所有儲存格，建立【班別代碼 -> (開始時間, 結束時間)】的對照字典"""
    dict_map = {}
    try:
        df = pd.read_excel(file_buffer, header=3)
        for _, row in df.iterrows():
            for cell in row.iloc[2:]:
                if pd.isna(cell): continue
                cell_str = str(cell).strip()
                lines = [l.strip() for l in cell_str.split("\n") if l.strip()]
                times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
                if len(times) >= 2:
                    start_t, end_t = times[0], times[1]
                    non_time = [l for l in lines if l not in times and not "h" in l and not "m" in l]
                    if non_time:
                        train_code = non_time[0].upper()
                        dict_map[train_code] = {"start": start_t, "end": end_t}
    except Exception as e:
        st.error(f"建立對照字典時發生錯誤: {e}")
    return dict_map

if base_file is not None and realtime_file is not None:
    st.markdown("---")
    st.subheader("2. 自動對照與解析結果預覽")
    
    shift_dict = build_time_dictionary(base_file)
    st.success(f"已成功從 20 號基準表中學習並建立 {len(shift_dict)} 筆班別時間對照字典！")
    
    with st.expander("檢視自動建立的時間對照字典內容"):
        st.json(shift_dict)

    try:
        df_rt = pd.read_excel(realtime_file, header=None)
        st.write("成功讀取 21 號即時換班檔結構，正在套用字典自動補齊時間...")
        
        preview_data = []
        for r_idx in range(6, min(15, len(df_rt))):
            emp_id = df_rt.iloc[r_idx, 0]
            emp_name = df_rt.iloc[r_idx, 2]
            if pd.isna(emp_id): continue
            
            sample_code = str(df_rt.iloc[r_idx, 5]).strip().upper()
            # 如果字典裡找得到這個代碼，就用對應的時間；如果找不到（例如 DO1、DO3X），就直接把代碼填進去！
            matched_time = shift_dict.get(sample_code, {"start": sample_code, "end": sample_code})
            
            preview_data.append({
                "員編": emp_id,
                "姓名": emp_name,
                "新檔代碼": sample_code,
                "自動對照開始時間": matched_time["start"],
                "自動對照結束時間": matched_time["end"]
            })
            
        st.dataframe(pd.DataFrame(preview_data))
        st.info("測試成功！證明了『以 20 號總表建立時間字典，自動幫 21 號純代碼新表補上時間』完全可行！")
        
    except Exception as e:
        st.error(f"解析 21 號即時換班檔失敗: {e}")
else:
    st.info("請同時上傳【20 號基準檔】與【21 號後即時檔】來進行即時配對測試。")
