import streamlit as st
import os, re, io
import pandas as pd
from datetime import date, timedelta, datetime
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

matplotlib.use('Agg')
st.set_page_config(page_title="🚆 TTN 勤務班表產生器", page_icon="🚆", layout="centered")

NATIONAL_HOLIDAYS = {
    "1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", 
    "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節",
    "6/19": "端午節", "9/25": "中秋節", "9/28": "教師節", "10/10": "國慶日",
    "10/25": "台灣光復節", "12/25": "行憲紀念日"
}

TITLE = "//    T r a i n    c r e w    D U T Y    C A L E N D A R"
SAVED_FILE_PATH = "latest_duty.xlsx"

def draw_bold_text(ax, x, y, text, **kwargs):
    ax.text(x, y, text, **kwargs)
    offset = 0.00025
    for dx, dy in [(offset,0), (0,offset), (-offset,0), (0,-offset)]: ax.text(x+dx, y+dy, text, **kwargs)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    lines = [l.strip() for l in str(raw).split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): return dict(start="", train=lines[0], end="", hours="", note="")
    
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    hours = next((l.replace(":", "h") + "m" for l in lines if "h" in l or "m" in l), "")
    return dict(
        start=times[0] if times else "",
        end=times[1] if len(times)>1 else "",
        train=next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and "h" not in l and "DO" not in l and "PAY" not in l), ""),
        hours=hours,
        note=" ".join([l for l in lines if l not in times and "h" not in l and "DO" not in l])
    )

def process_file_data(file_source, target_id):
    df = pd.read_excel(file_source, header=3)
    df.columns = [str(c).strip() for c in df.columns]
    target_clean = target_id.strip().upper()
    for _, row in df.iterrows():
        if str(row.iloc[0]).strip().upper() == target_clean:
            return df.columns[2:], row.iloc[0], row.iloc[1], row.iloc[2:]
    raise ValueError("找不到員編資料")

st.title("🚆 TTN 勤務班表產生器")
with st.expander("📁 管理員專用：上傳班表"):
    uploaded_file = st.file_uploader("選擇班表檔案", type=["xlsx", "xls", "csv", "txt"])
    if uploaded_file:
        with open(SAVED_FILE_PATH, "wb") as f: f.write(uploaded_file.getbuffer())
        st.success("✅ 保存成功！")

target_id = st.text_input("輸入員編", value="A018896")

if st.button("立即生成個人班表圖片"):
    if not os.path.exists(SAVED_FILE_PATH): st.error("❌ 無資料")
    else:
        try:
            cols, emp_id, emp_name, cells = process_file_data(SAVED_FILE_PATH, target_id)
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
            
            ML, MR, MT, MB, TH, DH = 0.02, 0.02, 0.02, 0.08, 0.08, 0.05
            TW = 1.0 - ML - MR; CW = TW / 7; RH = (1.0 - MT - MB - TH - DH) / 5
            
            # 畫標題
            ax.add_patch(FancyBboxPatch((ML, 1-MT-TH), TW, TH, facecolor="#0F172A"))
            draw_bold_text(ax, ML+0.01, 1-MT-TH*0.4, TITLE, color="white", fontsize=14)
            draw_bold_text(ax, ML+0.01, 1-MT-TH*0.75, f"CREW ID // {emp_id}    OPERATOR // {emp_name}", color="#CBD5E1", fontsize=10)
            draw_bold_text(ax, 0.98, 1-MT-TH*0.5, "C.L.F DESIGNS", ha="right", color="white", fontsize=9)
            
            # 畫表格
            for ri in range(5):
                for ci in range(7):
                    idx = ri * 7 + ci
                    if idx < len(cells):
                        ry = 1 - MT - TH - DH - (ri+1)*RH
                        rx = ML + ci*CW
                        ax.add_patch(FancyBboxPatch((rx, ry), CW, RH, edgecolor="#475569", facecolor="white"))
                        d = parse_cell(cells[idx])
                        draw_bold_text(ax, rx+0.002, ry+RH-0.005, str(cols[idx]), fontsize=8, va="top")
                        if d['train']: draw_bold_text(ax, rx+CW/2, ry+RH/2, f"{d['start']}\n{d['end']}\n{d['train']}", ha="center", va="center", fontsize=9)
            
            # 版權資訊
            draw_bold_text(ax, ML, 0.04, "DESIGNED BY: C.L.F // TECHNICAL SHIFT SYSTEM v4.19", color="#64748B", fontsize=7)
            draw_bold_text(ax, 1-MR, 0.04, f"GENERATED: {datetime.now().strftime('%Y-%m-%d %H:%M')} | CONFIDENTIAL", ha="right", color="#64748B", fontsize=7)
            
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=300, bbox_inches="tight")
            buf.seek(0)
            st.image(buf); st.download_button("📥 下載", data=buf, file_name="班表.png", mime="image/png")
        except Exception as e: st.error(f"❌ {e}")
