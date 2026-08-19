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

# 2026 全年完整國定假日與紀念日對照表
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
    ax.text(x + offset, y, text, **kwargs)
    ax.text(x, y + offset, text, **kwargs)
    ax.text(x - offset, y, text, **kwargs)
    ax.text(x, y - offset, text, **kwargs)

def parse_transport_periods(raw_periods, year=2026):
    expanded = {}
    for k, v in raw_periods.items():
        if "-" in k:
            parts = k.split("-")
            s_m, s_d = map(int, parts[0].strip().split("/"))
            e_m, e_d = map(int, parts[1].strip().split("/"))
            cur = date(year, s_m, s_d)
            end_dt = date(year, e_m, e_d)
            while cur <= end_dt:
                expanded[f"{cur.month}/{cur.day}"] = v
                cur += timedelta(days=1)
        else: expanded[k.strip()] = v
    return expanded

def pad_time(t_str):
    if not t_str or ":" not in t_str: return t_str
    parts = str(t_str).split(":")
    return f"{int(parts[0]):02d}:{parts[1]}" if len(parts) == 2 else str(t_str)

def fmt_hours(h):
    h_str = str(h)
    return h_str.replace(":", "h") + "m" if ":" in h_str and "h" not in h_str else h_str

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): return dict(start="", train=lines[0], end="", hours="", note="")
    if "PAY" in lines:
        times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
        return dict(start=pad_time(times[0]) if times else "", train="PAY", end=pad_time(times[1]) if len(times)>1 else "", hours="", note="")
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    hours = next((fmt_hours(l) for l in lines if "h" in l or "m" in l), "")
    start_time = pad_time(times[0]) if times else ""
    end_time = pad_time(times[1]) if len(times) > 1 else ""
    train_code = next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and "h" not in l and "DO" not in l and "PAY" not in l), "")
    notes = [l for l in lines if l not in times and l != train_code and "h" not in l]
    return dict(start=start_time, end=end_time, train=train_code, hours=hours, note=" ".join(notes))

def process_file_data(file_source, target_id):
    df = pd.read_excel(file_source, header=3)
    df.columns = [str(c).strip() for c in df.columns]
    target_clean = target_id.strip().upper()
    for _, row in df.iterrows():
        if str(row.iloc[0]).strip().upper() == target_clean:
            return date(2026, 2, 1), df.columns[2:], str(row.iloc[0]), str(row.iloc[1]).strip(), row.iloc[2:].values
    raise ValueError("找不到資料")

def is_overtime(h):
    if not h: return False
    try:
        p = str(h).replace("h", ":").replace("m", "").split(":")
        return (int(p[0]) * 60 + int(p[1])) > 510
    except: return False

def is_town_shift(tr, note):
    combined = f"{tr} {note}".upper()
    return any(kw in combined for kw in ["TOWN", "STD", "TTN", "DTT", "工廠", "回廠", "訓練"])

def build_weeks(start_dt, dates, cells):
    first_wd = (start_dt.weekday() + 1) % 7
    weeks, week = [], [None] * first_wd
    for dt, raw in zip(dates, cells):
        week.append((dt, parse_cell(raw)))
        if len(week) == 7: weeks.append(week); week = []
    if week:
        while len(week) < 7: week.append(None)
        weeks.append(week)
    return weeks

def setup_font():
    font_path = "NotoSansTC.ttf"
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        return fm.FontProperties(fname=font_path)
    return None

C_HDR, C_WORK_BG, C_WEEKEND_BG = "#0F172A", "#FFFFFF", "#F8FAFC"
C_DO_BG, C_PAY_BG, C_TOWN_BG = "#FFE4E6", "#FFEDD5", "#CBD5E1"
C_DO_TXT, C_PAY_TXT, C_HOLI_TXT, C_OT_TXT, C_NOTE_TXT = "#881337", "#9A3412", "#7C2D12", "#991B1B", "#4C1D95"

st.title("🚆 TTN 勤務班表產生器")
with st.expander("📁 管理員專用：上傳班表"):
    uploaded_file = st.file_uploader("選擇班表檔案", type=["xlsx", "xls", "csv", "txt"])
    if uploaded_file:
        with open(SAVED_FILE_PATH, "wb") as f: f.write(uploaded_file.getbuffer())
        st.success("✅ 保存成功！")

target_id = st.text_input("輸入員編", value="A018896")

if st.button("立即生成個人班表圖片"):
    if not os.path.exists(SAVED_FILE_PATH): st.error("❌ 無資料"); st.stop()
    try:
        start_dt, dates, emp_id, emp_name, cells = process_file_data(SAVED_FILE_PATH, target_id)
        font_prop = setup_font()
        def fp(s=9): return fm.FontProperties(fname=font_prop.get_file(), size=s) if font_prop else fm.FontProperties(size=s)
        
        weeks = build_weeks(start_dt, dates, cells)
        fig, ax = plt.subplots(figsize=(11.69, 8.27)); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
        
        ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
        TW, CW = 1.0 - ML - MR, (1.0 - ML - MR) / 7
        RH = (1.0 - MT - MB - TH - DH) / len(weeks)
        ty = 1.0 - MT - TH
        
        # 標題列
        ax.add_patch(FancyBboxPatch((ML, ty), TW, TH, boxstyle="square,pad=0", linewidth=0, facecolor=C_HDR))
        draw_bold_text(ax, ML+0.008, ty+TH*0.6, TITLE, color="white", fontproperties=fp(12))
        draw_bold_text(ax, ML+0.008, ty+TH*0.25, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]} ({len(dates)} DAYS)", color="#CBD5E1", fontproperties=fp(9))
        ax.plot(0.935, ty+TH*0.6, marker='o', markersize=4, color="#22C55E")
        draw_bold_text(ax, 0.955, ty+TH*0.6, "C.L.F DESIGNS", ha="right", color="white", fontproperties=fp(8.5))
        
        # 繪製表格
        dy = ty - DH
        for c in range(7):
            ax.add_patch(FancyBboxPatch((ML+c*CW, dy), CW, DH, facecolor="#94A3B8", edgecolor="#475569"))
            draw_bold_text(ax, ML+c*CW+CW/2, dy+DH/2, ["SUN 星期日","MON 星期一","TUE 星期二","WED 星期三","THU 星期四","FRI 星期五","SAT 星期六"][c], ha="center", va="center", fontproperties=fp(9.5))
            
        for ri, week in enumerate(weeks):
            for ci, cell in enumerate(week):
                if cell:
                    dt, d = cell
                    x, y, bg = ML+ci*CW, dy-(ri+1)*RH, C_WORK_BG
                    if "DO" in d['train']: bg = C_DO_BG
                    elif d['train'] == "PAY": bg = C_PAY_BG
                    ax.add_patch(FancyBboxPatch((x, y), CW, RH, facecolor=bg, edgecolor="#64748B"))
                    draw_bold_text(ax, x+0.004, y+RH-0.004, dt, va="top", fontproperties=fp(8.5))
                    draw_bold_text(ax, x+CW/2, y+RH/2, f"{d['start']}\n{d['end']}\n{d['train']}", ha="center", va="center", fontproperties=fp(9))
                    
        # 底部
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        draw_bold_text(ax, ML, MB*0.2, "DESIGNED BY: C.L.F // TECHNICAL SHIFT SYSTEM v4.19", color="#64748B", fontproperties=fp(7.5))
        draw_bold_text(ax, 1.0-MR, MB*0.2, f"GENERATED: {now} | CONFIDENTIAL", ha="right", color="#64748B", fontproperties=fp(7.5))
        
        buf = io.BytesIO()
        plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
        buf.seek(0); plt.close()
        st.success("🎉 生成成功！"); st.image(buf, use_container_width=True)
        st.download_button("📥 下載班表", buf, f"TTN_{emp_name}.png", "image/png")
    except Exception as e: st.error(f"❌ {e}")
