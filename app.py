import streamlit as st
import os, io
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

st.set_page_config(page_title="🚆 TTN 勤務班表", layout="centered")
SAVED_FILE_PATH = "latest_duty.xlsx"

st.title("🚆 TTN 勤務班表產生器")
with st.expander("📁 管理員專用：上傳班表"):
    uploaded = st.file_uploader("選擇班表檔案", type=["xlsx", "xls", "csv", "txt"])
    if uploaded:
        with open(SAVED_FILE_PATH, "wb") as f: f.write(uploaded.getbuffer())
        st.success("✅ 保存成功")

target_id = st.text_input("輸入員編", value="A018896")

if st.button("生成個人班表"):
    if not os.path.exists(SAVED_FILE_PATH): st.error("❌ 無資料"); st.stop()
    
    # 讀取 Excel
    df = pd.read_excel(SAVED_FILE_PATH, header=3)
    df.columns = [str(c).strip() for c in df.columns]
    
    # 找員工
    row = df[df.iloc[:, 0].astype(str).str.upper() == target_id.strip().upper()]
    if row.empty: st.error("❌ 找不到該員編"); st.stop()
    
    row = row.iloc[0]
    dates = df.columns[2:]
    cells = row.iloc[2:].values
    
    # 畫圖
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_axis_off()
    
    # 建立表格
    table_data = []
    # 將資料切分成 7 天一列 (共 5 週)
    for i in range(0, len(dates), 7):
        week_dates = dates[i:i+7]
        week_cells = cells[i:i+7]
        # 顯示日期
        table_data.append([str(d) for d in week_dates])
        # 顯示內容
        table_data.append([str(c).replace("\n", " ") if str(c) != 'nan' else "" for c in week_cells])
    
    table = ax.table(cellText=table_data, colLabels=["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"], 
                     loc='center', cellLoc='center')
    
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 2)
    
    plt.title(f"CREW ID: {row.iloc[0]} | {row.iloc[1]}", fontsize=12)
    
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    st.image(buf)
    st.download_button("📥 下載班表", buf, "班表.png", "image/png")
