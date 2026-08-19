import streamlit as st
import os
import re
import io
import csv
from datetime import date, timedelta, datetime
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

matplotlib.use('Agg')

# ==========================================
# 【每個月更新區】請將最新的大班表文字貼在下方的引號中間
# ==========================================
DUTY_DATA = """
(請在此貼上當月大班表文字內容)
"""
# ==========================================

st.set_page_config(page_title="🚆 TTN 勤務班表產生器", page_icon="🚆", layout="centered")

def draw_bold_text(ax, x, y, text, **kwargs):
    """四重疊影加粗技術：確保在雲端環境也能呈現紮實粗體"""
    ax.text(x, y, text, **kwargs)
    offset = 0.00025
    ax.text(x + offset, y, text, **kwargs)
    ax.text(x, y + offset, text, **kwargs)
    ax.text(x - offset, y, text, **kwargs)
    ax.text(x, y - offset, text, **kwargs)

def setup_font():
    font_path = "NotoSansTC.ttf"
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        return fm.FontProperties(fname=font_path)
    return None

def parse_cell(raw):
    lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    # 簡化解析邏輯，確保能抓到班別
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): return dict(start="", train=lines[0], end="", hours="", note="")
    
    time_lines = [l for l in lines if ":" in l]
    start_time = time_lines[0] if time_lines else ""
    end_time = time_lines[1] if len(time_lines) > 1 else ""
    train_code = next((l for l in lines if l not in time_lines and "h" not in l and "DO" not in l), lines[0])
    hours = next((l for l in lines if "h" in l), "")
    note = " ".join([l for l in lines if l not in time_lines and l != train_code and "h" not in l])
    return dict(start=start_time, end=end_time, train=train_code, hours=hours, note=note)

def parse_flexible_employees(text, target_name):
    f = io.StringIO(text.strip())
    rows = list(csv.reader(f, delimiter="\t"))
    start_date_str = next((re.search(r'(\d+/\d+)', r[2]).group(1) for r in rows if any("員工" in c for c in r) and len(r)>2), None)
    if not start_date_str: raise ValueError("找不到日期標題，請確認班表格式。")
    start_m, start_d = map(int, start_date_str.split("/"))
    start_dt = date(2026, start_m, start_d)
    for r in rows:
        if len(r) > 1 and r[1].strip() == target_name.strip():
            return start_dt, r[2:], r[0], r[1]
    raise ValueError("找不到同仁資料，請檢查名字是否正確。")

st.title("🚆 TTN 勤務班表產生器")
target_name = st.text_input("輸入你的名字", value="江立夫")

if st.button("立即生成個人班表圖片"):
    try:
        start_dt, cells, emp_id, emp_name = parse_flexible_employees(DUTY_DATA, target_name)
        font_prop = setup_font()
        def fp(size=9): return fm.FontProperties(fname=font_prop.get_file(), size=size) if font_prop else fm.FontProperties(size=size)
        
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        fig.patch.set_facecolor("white")
        
        # 繪圖區塊
        ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
        CW = (1.0 - ML - MR) / 7
        RH = (1.0 - MT - MB - TH - DH) / 5
        
        # 簡單表格背景與黑色文字繪製
        for i in range(len(cells)):
            ci, ri = i % 7, i // 7
            x, y = ML + ci * CW, 1.0 - MT - TH - DH - (ri + 1) * RH
            ax.add_patch(FancyBboxPatch((x, y), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#000000", facecolor="#FFFFFF"))
            
            d = parse_cell(cells[i])
            draw_bold_text(ax, x + CW/2, y + RH*0.6, d['start'], ha="center", va="center", color="#000000", fontproperties=fp(10))
            draw_bold_text(ax, x + CW/2, y + RH*0.3, d['train'], ha="center", va="center", color="#000000", fontproperties=fp(10))
            
        buf = io.BytesIO()
        plt.tight_layout(pad=0)
        plt.savefig(buf, format="png", dpi=300, facecolor="white")
        buf.seek(0)
        
        st.success("🎉 生成成功！")
        st.image(buf, use_container_width=True)
        st.download_button("📥 下載班表圖片", data=buf, file_name="班表.png", mime="image/png")
    except Exception as e: st.error(f"❌ 錯誤：{e}")
