import streamlit as st
import os, re, io
import pandas as pd
from datetime import datetime
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

matplotlib.use('Agg')
st.set_page_config(page_title="🚆 TTN 勤務班表產生器", layout="centered")

SAVED_FILE_PATH = "latest_duty.xlsx"

def draw_bold_text(ax, x, y, text, **kwargs):
    ax.text(x, y, text, **kwargs)
    offset = 0.0003
    for dx, dy in [(offset,0), (0,offset), (-offset,0), (0,-offset)]:
        ax.text(x+dx, y+dy, text, **kwargs)

def get_df():
    if not os.path.exists(SAVED_FILE_PATH): return None
    return pd.read_excel(SAVED_FILE_PATH, header=3)

st.title("🚆 TTN 勤務班表產生器")
with st.expander("📁 管理員：上傳班表"):
    uploaded = st.file_uploader("選擇檔案", type=["xlsx", "xls", "csv", "txt"])
    if uploaded:
        with open(SAVED_FILE_PATH, "wb") as f: f.write(uploaded.getbuffer())
        st.success("✅ 保存成功")

target_id = st.text_input("輸入員編", value="A018896")

if st.button("生成班表"):
    df = get_df()
    if df is None: st.error("❌ 無班表資料"); st.stop()
    
    # 找員工資料
    df.columns = [str(c).strip() for c in df.columns]
    row = df[df.iloc[:, 0].astype(str).str.upper() == target_id.strip().upper()]
    if row.empty: st.error("❌ 找不到該員編"); st.stop()
    
    row = row.iloc[0]
    emp_id, emp_name = row.iloc[0], row.iloc[1]
    cells = row.iloc[2:].values
    dates = df.columns[2:]

    fig, ax = plt.subplots(figsize=(12, 8.5))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    
    # 排版變數
    ML, MR, MT, MB, TH, DH = 0.02, 0.02, 0.02, 0.08, 0.08, 0.05
    TW, CW = 1.0 - ML - MR, (1.0 - ML - MR) / 7
    RH = (1.0 - MT - MB - TH - DH) / 5
    
    # 畫頂部
    ax.add_patch(FancyBboxPatch((ML, 1-MT-TH), TW, TH, facecolor="#0F172A"))
    draw_bold_text(ax, ML+0.01, 1-MT-TH*0.4, "// T r a i n    c r e w    D U T Y    C A L E N D A R", color="white", fontsize=14)
    draw_bold_text(ax, ML+0.01, 1-MT-TH*0.75, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", color="#CBD5E1", fontsize=10)
    draw_bold_text(ax, 0.98, 1-MT-TH*0.5, "C.L.F DESIGNS", ha="right", color="white", fontsize=9)
    
    # 畫格子
    labels = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for i in range(7):
        ax.add_patch(FancyBboxPatch((ML+i*CW, 1-MT-TH-DH), CW, DH, facecolor="#94A3B8", edgecolor="#475569"))
        draw_bold_text(ax, ML+i*CW+CW/2, 1-MT-TH-DH/2, labels[i], ha="center", va="center", fontsize=10)

    for i in range(min(35, len(cells))):
        ri, ci = i // 7, i % 7
        rx, ry = ML + ci*CW, 1 - MT - TH - DH - (ri+1)*RH
        ax.add_patch(FancyBboxPatch((rx, ry), CW, RH, facecolor="white", edgecolor="#475569"))
        draw_bold_text(ax, rx+0.002, ry+RH-0.005, str(dates[i]), fontsize=8, va="top")
        txt = str(cells[i])
        if txt != 'nan':
            draw_bold_text(ax, rx+CW/2, ry+RH/2, txt.replace("\n", " "), ha="center", va="center", fontsize=8)

    # 底部
    draw_bold_text(ax, ML, 0.04, "DESIGNED BY: C.L.F // v4.19", color="#64748B", fontsize=7)
    draw_bold_text(ax, 1-MR, 0.04, f"GENERATED: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ha="right", color="#64748B", fontsize=7)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    st.image(buf); st.download_button("📥 下載班表", buf, "班表.png", "image/png")
