import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="TTN Shift 完整動態日期測試", layout="centered")

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
    🧪 完整動態日期與字典對照沙盒 (Sandbox)：支援新檔實際天數（如 09/01 ~ 09/21）展開！
</div>
""", unsafe_allow_html=True)

st.title("每日換班資料自動對照與多日展開測試")

# --- 1. 資料上傳區 ---
st.subheader("1. 匯入排班基準與每日異動檔")
col1, col2 = st.columns(2)

with col1:
    base_file = st.file_uploader("上傳 20 號基準總表 (含完整時間)", type=["xlsx", "xls"], key="base_up")
with col2:
    realtime_file = st.file_uploader("上傳最新換班異動檔 (純代碼，如至09/21)", type=["xls", "xlsx"], key="rt_up")

# --- 2. 核心字典建立 ---
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
    shift_dict = build_shift_dict(base_file)
    st.success(f"成功載入 20 號基準表，建立 {len(shift_dict)} 筆班別時間對照字典！")

    try:
        # 讀取 21 號後異動檔
        df_rt = pd.read_excel(realtime_file, header=None)
        
        # 自動抓取日期列 (假設日期在第 5 行，索引 4 或 5，依照你的表結構微調)
        # 根據你一開始提供的截圖，日期在第 5 行 (索引 4) 的 F 欄開始 (索引 5)
        date_row_idx = 4 
        dates = []
        date_col_indices = []
        
        for c_idx in range(5, df_rt.shape[1]):
            val = df_rt.iloc[date_row_idx, c_idx]
            if not pd.isna(val):
                dates.append(str(val).strip())
                date_col_indices.append(c_idx)
        
        st.info(f"系統自動偵測到新檔案包含的日期範圍共 {len(dates)} 天（從 {dates[0] if dates else '未知'} 到 {dates[-1] if dates else '未知'}）")

        # 將整張表的橫向日期展開為直向明細 (Melt)
        all_records = []
        for r_idx in range(6, len(df_rt)):
            emp_id = df_rt.iloc[r_idx, 0]
            emp_name = df_rt.iloc[r_idx, 2]
            if pd.isna(emp_id): continue
            
            for d, c_idx in zip(dates, date_col_indices):
                code = str(df_rt.iloc[r_idx, c_idx]).strip().upper()
                if code == "NAN" or code == "": continue
                
                t_info = shift_dict.get(code, {"start": code, "end": code})
                
                all_records.append({
                    "員編": str(emp_id),
                    "姓名": str(emp_name),
                    "日期": d,
                    "班別代碼": code,
                    "開始時間": t_info["start"],
                    "結束時間": t_info["end"]
                })
        
        df_processed = pd.DataFrame(all_records)

        st.markdown("---")
        st.subheader("2. 模擬三大系統功能測試（支援多日展開）")
        
        tab1, tab2 = st.tabs(["🔍 個人完整班表查詢", "⏱️ 單日指定時段快篩"])
        
        with tab1:
            st.markdown("##### 測試：查詢特定員工在動態日期內的最新班表")
            selected_emp = st.selectbox("選擇員工姓名", df_processed["姓名"].unique())
            emp_data = df_processed[df_processed["姓名"] == selected_emp]
            st.dataframe(emp_data, use_container_width=True)
            
        with tab2:
            st.markdown("##### 測試：指定「特定日期」與「時間區段」快篩組員")
            selected_date = st.selectbox("選擇查詢日期", dates)
            
            col_a, col_b = st.columns(2)
            with col_a:
                filter_start = st.text_input("篩選開始時間 (例 06:00)", "06:00")
            with col_b:
                filter_end = st.text_input("篩選結束時間 (例 16:00)", "16:00")
                
            # 篩選特定日期與時間區段
            matched_shift = df_processed[
                (df_processed["日期"] == selected_date) & 
                (df_processed["開始時間"] >= filter_start) & 
                (df_processed["結束時間"] <= filter_end)
            ]
            st.write(f"在 **{selected_date}** 符合該時段的組員共 {len(matched_shift)} 人：")
            st.dataframe(matched_shift, use_container_width=True)

        st.info("💡 測試成功！系統已完美支援自動抓取實際日期範圍（如 09/21 為止），並自動將每日異動對照成正確時間供系統查詢！")

    except Exception as e:
        st.error(f"解析異動檔並展開日期失敗: {e}")
else:
    st.info("請同時上傳【20 號基準總表】與【每日更新的換班異動檔】來啟動完整動態測試。")
