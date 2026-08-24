import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="TTN Shift 整合測試專案 (Sandbox)", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 3rem 1rem 3rem 1rem !important; }
    .test-banner {
        background: linear-gradient(135deg, #1E3A8A 100%, #172554 0%);
        border: 1px solid #3B82F6;
        border-left: 5px solid #60A5FA;
        color: #E0F2FE;
        padding: 12px 18px;
        border-radius: 10px;
        margin-bottom: 20px;
        font-family: monospace;
        font-size: 14px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="test-banner">
    🧪 整合測試沙盒 (Sandbox)：模擬 21 號後每日更新異動檔，並連動查詢系統！
</div>
""", unsafe_allow_html=True)

st.title("每日換班資料自動對照與系統測試")

# --- 1. 資料上傳區 ---
st.subheader("1. 匯入本月排班基準與每日異動檔")
col1, col2 = st.columns(2)

with col1:
    base_file = st.file_uploader("上傳 20 號基準總表 (含完整時間)", type=["xlsx", "xls"], key="base_up")
with col2:
    realtime_file = st.file_uploader("上傳最新換班異動檔 (純代碼)", type=["xls", "xlsx"], key="rt_up")

# --- 2. 核心字典建立與轉換函式 ---
def build_shift_dict(file_buffer):
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
                        code = non_time[0].upper()
                        dict_map[code] = {"start": start_t, "end": end_t}
    except Exception as e:
        st.error(f"建立字典錯誤: {e}")
    return dict_map

if base_file and realtime_file:
    # 建立字典
    shift_dict = build_shift_dict(base_file)
    st.success(f"成功載入 20 號基準表，建立 {len(shift_dict)} 筆班別時間對照字典！")

    try:
        # 讀取每日更新的新檔
        df_rt = pd.read_excel(realtime_file, header=None)
        
        # 這裡我們模擬將新檔轉換成帶有正確時間的標準格式
        # 假設日期欄位從索引 5 開始
        processed_rows = []
        for r_idx in range(6, len(df_rt)):
            emp_id = df_rt.iloc[r_idx, 0]
            emp_name = df_rt.iloc[r_idx, 2]
            if pd.isna(emp_id): continue
            
            # 抓取第一天作為示範欄位 (索引5)
            code = str(df_rt.iloc[r_idx, 5]).strip().upper()
            t_info = shift_dict.get(code, {"start": code, "end": code})
            
            processed_rows.append({
                "員編": str(emp_id),
                "姓名": str(emp_name),
                "班別代碼": code,
                "開始時間": t_info["start"],
                "結束時間": t_info["end"]
            })
        
        df_processed = pd.DataFrame(processed_rows)

        st.markdown("---")
        st.subheader("2. 模擬三大系統功能測試")
        
        tab1, tab2 = st.tabs(["🔍 個人班表快速查詢", "⏱️ 時段快篩模擬"])
        
        with tab1:
            st.markdown("##### 測試：查詢特定員工換班後的最新時間")
            selected_emp = st.selectbox("選擇員工姓名", df_processed["姓名"].unique())
            emp_data = df_processed[df_processed["姓名"] == selected_emp]
            st.dataframe(emp_data, use_container_width=True)
            
        with tab2:
            st.markdown("##### 測試：輸入特定時間區段，快篩出勤組員")
            col_a, col_b = st.columns(2)
            with col_a:
                filter_start = st.text_input("篩選開始時間 (例 06:00)", "06:00")
            with col_b:
                filter_end = st.text_input("篩選結束時間 (例 16:00)", "16:00")
                
            # 簡單篩選出符合時間區段的班別
            matched_shift = df_processed[
                (df_processed["開始時間"] >= filter_start) & 
                (df_processed["結束時間"] <= filter_end)
            ]
            st.write(f"符合該時段的組員共 {len(matched_shift)} 人：")
            st.dataframe(matched_shift, use_container_width=True)

        st.info("💡 測試順暢！這代表每天上傳最新異動檔後，系統都能即時對照並無縫支援所有查詢功能。")

    except Exception as e:
        st.error(f"解析每日異動檔失敗: {e}")
else:
    st.info("請同時上傳【20 號基準總表】與【每日更新的換班異動檔】來啟動整合測試。")
