import streamlit as st
import os, re, io
import pandas as pd
from datetime import date, timedelta, datetime
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

matplotlib.use('Agg')
st.set_page_config(page_title="🚆 TTN Shift Producer | C.L.F", page_icon="🚆", layout="centered")

NATIONAL_HOLIDAYS = {
    "1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", 
    "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節",
    "6/19": "端午節", "9/25": "中秋節", "9/28": "教師節", "10/10": "國慶日",
    "10/25": "台灣光復節", "12/25": "行憲紀念日"
}
TRANSPORT_PERIODS = {"9/24-9/29": "中秋疏運"}
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
    return dict(
        start=times[0] if times else "", end=times[1] if len(times)>1 else "",
        train=next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and "h" not in l and "DO" not in l and "PAY" not in l), ""),
        hours=next((l.replace(":", "h") + "m" for l in lines if "h" in l or "m" in l), ""),
        note=" ".join([l for l in lines if l not in times and "h" not in l and "DO" not in l])
    )

def process_file_data(file_source, input_str):
    df = pd.read_excel(file_source, header=3)
    df.columns = [str(c).strip() for c in df.columns]
    input_clean = input_str.strip().upper()
    for _, row in df.iterrows():
        if str(row.iloc[0]).strip().upper() == input_clean or str(row.iloc[1]).strip().upper() == input_clean:
            return date(2026, 2, 1), df.columns[2:], str(row.iloc[0]), str(row.iloc[1]).strip(), row.iloc[2:].values
    raise ValueError(f"找不到員編或姓名為「{input_str}」的資料。")

def setup_font():
    font_path = "NotoSansTC.ttf"
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        return fm.FontProperties(fname=font_path)
    return None

C_HDR, C_WORK_BG, C_WEEKEND_BG = "#0F172A", "#FFFFFF", "#F8FAFC"
C_DO_BG, C_PAY_BG, C_TOWN_BG = "#FFE4E6", "#FFEDD5", "#CBD5E1"
C_DO_TXT, C_PAY_TXT, C_HOLI_TXT, C_OT_TXT, C_NOTE_TXT = "#881337", "#9A3412", "#7C2D12", "#991B1B", "#4C1D95"

st.title("🚆 TTN Shift Producer // C.L.F Edition")
with st.expander("📁 管理員專用：Database"):
    uploaded = st.file_uploader("選擇班表檔案", type=["xlsx", "xls", "csv", "txt"])
    if uploaded:
        with open(SAVED_FILE_PATH, "wb") as f: f.write(uploaded.getbuffer())
        st.success("✅ 保存成功！")

target_input = st.text_input("輸入 員編 或 姓名", value="A018896")

if st.button("立即生成個人班表圖片"):
    if not os.path.exists(SAVED_FILE_PATH): st.error("❌ 無班表資料"); st.stop()
    try:
        start_dt, dates, emp_id, emp_name, cells = process_file_data(SAVED_FILE_PATH, target_input)
        fp = lambda s=9: fm.FontProperties(size=s)
        fig, ax = plt.subplots(figsize=(11.69, 8.27)); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        
        ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
        TW, CW = 1.0 - ML - MR, (1.0 - ML - MR) / 7
        RH = (1.0 - MT - MB - TH - DH) / 5
        ty = 1.0 - MT - TH
        
        # 標題與標誌
        ax.add_patch(FancyBboxPatch((ML, ty), TW, TH, facecolor=C_HDR))
        draw_bold_text(ax, ML+0.008, ty+TH*0.6, TITLE, color="white", fontproperties=fp(12))
        draw_bold_text(ax, ML+0.008, ty+TH*0.25, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", color="#CBD5E1", fontproperties=fp(9))
        ax.plot(0.935-0.095, ty+TH*0.6, marker='o', markersize=4, color="#22C55E")
        draw_bold_text(ax, 0.935, ty+TH*0.6, "Producer | C.L.F", ha="right", color="white", fontproperties=fp(8.5))
        
        # 表格繪製
        dy = ty - DH
        for c in range(7):
            ax.add_patch(FancyBboxPatch((ML+c*CW, dy), CW, DH, facecolor="#94A3B8", edgecolor="#475569"))
            draw_bold_text(ax, ML+c*CW+CW/2, dy+DH/2, ["SUN","MON","TUE","WED","THU","FRI","SAT"][c], ha="center", va="center", fontproperties=fp(9.5))
            
        for i in range(min(35, len(cells))):
            ri, ci = i // 7, i % 7
            x, y = ML + ci*CW, dy-(ri+1)*RH
            d = parse_cell(cells[i])
            ax.add_patch(FancyBboxPatch((x, y), CW, RH, facecolor=C_DO_BG if "DO" in d['train'] else C_WORK_BG, edgecolor="#64748B"))
            draw_bold_text(ax, x+0.004, y+RH-0.004, str(dates[i]), va="top", fontproperties=fp(8.5))
            if d['train']: draw_bold_text(ax, x+CW/2, y+RH/2, f"{d['start']}\n{d['end']}\n{d['train']}", ha="center", va="center", fontproperties=fp(9))
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        draw_bold_text(ax, ML, MB*0.12, "DESIGNED BY: C.L.F // TECHNICAL SHIFT SYSTEM v4.19", color="#64748B", fontproperties=fp(7.5))
        draw_bold_text(ax, 1.0-MR, MB*0.12, f"GENERATED: {now} | CONFIDENTIAL", ha="right", color="#64748B", fontproperties=fp(7.5))
        
        buf = io.BytesIO(); plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, facecolor="white"); buf.seek(0)
        st.success("🎉 生成成功！"); st.image(buf, use_container_width=True)
        st.download_button("📥 下載班表", buf, f"TTN_{emp_name}.png", "image/png")
    except Exception as e: st.error(f"❌ {e}")
