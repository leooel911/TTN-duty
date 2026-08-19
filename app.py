import streamlit as st
import os
import re
import io
import pandas as pd
from datetime import date, timedelta, datetime
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

matplotlib.use('Agg')

st.set_page_config(page_title="🚆 TTN 個人班表出圖系統", page_icon="🚆", layout="centered")

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
    """四重疊影加粗函數"""
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
        else:
            expanded[k.strip()] = v
    return expanded

def pad_time(t_str):
    if not t_str or ":" not in t_str: return t_str
    parts = str(t_str).split(":")
    return f"{int(parts[0]):02d}:{parts[1]}" if len(parts) == 2 else str(t_str)

def fmt_hours(h):
    h_str = str(h)
    return h_str.replace(":", "h") + "m" if ":" in h_str and "h" not in h_str else h_str

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip():
        return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): 
        return dict(start="", train=lines[0], end="", hours="", note="")
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
    matched_row = None
    emp_id, emp_name = "", ""
    
    for idx, row in df.iterrows():
        found_id = str(row.iloc[0]).strip().upper()
        if found_id == target_clean:
            matched_row = row
            emp_id = found_id
            emp_name = str(row.iloc[1]).strip()
            break
                
    if matched_row is None:
        raise ValueError(f"找不到員編「{target_id}」的資料，請確認輸入是否正確。")
        
    col_names = df.columns[2:]
    dates = []
    start_dt = date(2026, 2, 1)
    
    for i, col in enumerate(col_names):
        col_str = str(col).strip()
        match_d = re.search(r'(\d+/\d+)', col_str)
        if match_d:
            dates.append(match_d.group(1))
            if i == 0:
                m, d = map(int, match_d.group(1).split("/"))
                start_dt = date(2026, m, d)
        else:
            dates.append(col_str)
            
    cells = matched_row.iloc[2:].values
            
    return start_dt, dates, emp_id, emp_name, cells

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

C_HDR, C_BORDER, C_EMPTY = "#0F172A", "#475569", "#F1F5F9"
C_WORK_BG, C_WEEKEND_BG = "#FFFFFF", "#F8FAFC"
C_DO_BG, C_PAY_BG, C_TOWN_BG = "#FFE4E6", "#FFEDD5", "#CBD5E1"
C_DO_TXT, C_PAY_TXT, C_HOLI_TXT, C_OT_TXT, C_NOTE_TXT = "#881337", "#9A3412", "#7C2D12", "#991B1B", "#4C1D95"
C_TOWN_TXT = "#000000"

st.title("🚆 TTN 勤務班表產生器")

with st.expander("📁 管理員專用：上傳當月班表檔案（更新後永久保存）"):
    uploaded_file = st.file_uploader("選擇班表檔案 (.xlsx, .xls, .csv, .txt)", type=["xlsx", "xls", "csv", "txt"])
    if uploaded_file is not None:
        with open(SAVED_FILE_PATH, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("✅ 班表已成功上傳並永久保存至伺服器！")

target_id = st.text_input("輸入員編 (例如: A018896)", value="A018896")

if st.button("立即生成個人班表圖片"):
    if not os.path.exists(SAVED_FILE_PATH):
        st.error("❌ 目前伺服器中尚無班表資料，請先展開上方「管理員專用」上傳當月班表檔案！")
    else:
        try:
            start_dt, dates, emp_id, emp_name, cells = process_file_data(SAVED_FILE_PATH, target_id)
            active_transport = parse_transport_periods(TRANSPORT_PERIODS)
            font_prop = setup_font()
            def fp(size=9): return fm.FontProperties(fname=font_prop.get_file(), size=size) if font_prop else fm.FontProperties(size=size)
            
            weeks = build_weeks(start_dt, dates, cells)
            n_weeks = len(weeks)

            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
            fig.patch.set_facecolor("white")

            ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
            TW = 1.0 - ML - MR; CW = TW / 7
            RH = (1.0 - MT - MB - TH - DH) / n_weeks

            ty = 1.0 - MT - TH
            ax.add_patch(FancyBboxPatch((ML, ty), TW, TH, boxstyle="square,pad=0", linewidth=0, facecolor=C_HDR))
            
            # 頂部標題與識別資訊
            draw_bold_text(ax, ML + 0.008, ty + TH * 0.58, TITLE, ha="left", va="center", color="#FFFFFF", fontproperties=fp(12))
            draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]} ({len(dates)} DAYS)", ha="left", va="center", color="#CBD5E1", fontproperties=fp(9))
            
            # 右上角 C.L.F DESIGNS 標誌（微調向左，完美不貼邊）
            # 綠點位置（讓它在文字左側約 0.11 的距離）
            ax.plot(0.935 - 0.11, ty + TH * 0.58, marker='o', markersize=4, color="#22C55E")
            # 文字維持靠右對齊 (ha="right")
            draw_bold_text(ax, 0.935, ty + TH * 0.58, "C.L.F DESIGNS", ha="right", va="center", color="#FFFFFF", fontproperties=fp(8.5))
            dlabels = ["SUN 星期日", "MON 星期一", "TUE 星期二", "WED 星期三", "THU 星期四", "FRI 星期五", "SAT 星期六"]
            dy = ty - DH
            for c in range(7):
                x = ML + c * CW
                ax.add_patch(FancyBboxPatch((x, dy), CW, DH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#475569", facecolor="#94A3B8"))
                draw_bold_text(ax, x + CW / 2, dy + DH / 2, dlabels[c], ha="center", va="center", color="#000000", fontproperties=fp(9.5))

            has_emp_do, has_emp_pay, has_emp_ot, has_emp_town = False, False, False, False
            for week in weeks:
                for cell in week:
                    if cell is not None:
                        _, d = cell
                        tr, note, hours = d["train"], d.get("note", ""), d.get("hours", "")
                        is_hol = "D2W" in tr or "DO2W" in tr or "D2W" in note or "DO2W" in note
                        if is_hol or tr.startswith("DO"): has_emp_do = True
                        elif tr == "PAY": has_emp_pay = True
                        elif is_town_shift(tr, note): has_emp_town = True
                        if is_overtime(hours): has_emp_ot = True

            for ri, week in enumerate(weeks):
                ry = dy - (ri + 1) * RH
                for ci, cell in enumerate(week):
                    x = ML + ci * CW
                    if cell is None:
                        ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=C_EMPTY))
                        continue

                    dt, d = cell
                    tr, note = d["train"], d.get("note", "")
                    is_nt_hol = dt in NATIONAL_HOLIDAYS
                    is_hol = "D2W" in tr or "DO2W" in tr or "D2W" in note or "DO2W" in note

                    if is_hol or tr.startswith("DO"): bg = C_DO_BG
                    elif tr == "PAY": bg = C_PAY_BG
                    elif is_town_shift(tr, note): bg = C_TOWN_BG
                    elif ci == 0 or ci == 6: bg = C_WEEKEND_BG
                    else: bg = C_WORK_BG

                    ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=bg))

                    draw_bold_text(ax, x + 0.005, ry + RH - 0.004, f"{dt} ({NATIONAL_HOLIDAYS[dt]})" if is_nt_hol else dt, ha="left", va="top", color=C_HOLI_TXT if is_nt_hol else "#000000", fontproperties=fp(8.5))

                    if d.get("hours"):
                        ot = is_overtime(d["hours"])
                        draw_bold_text(ax, x + CW - 0.004, ry + 0.003, f"({d['hours']})", ha="right", va="bottom", color=C_OT_TXT if ot else "#000000", fontproperties=fp(8))

                    cx = x + CW / 2
                    if tr.startswith("DO"):
                        if note:
                            draw_bold_text(ax, cx, ry + RH * 0.62, note, ha="center", va="center", color=C_NOTE_TXT, fontproperties=fp(8))
                            draw_bold_text(ax, cx, ry + RH * 0.35, tr, ha="center", va="center", color=C_DO_TXT, fontproperties=fp(10))
                        else:
                            draw_bold_text(ax, cx, ry + RH * 0.48, tr, ha="center", va="center", color=C_DO_TXT, fontproperties=fp(11.5))
                    elif tr == "PAY":
                        draw_bold_text(ax, cx, ry + RH * 0.62, "特休 PAY", ha="center", va="center", color=C_PAY_TXT, fontproperties=fp(10))
                        if d["start"] and d["end"]:
                            draw_bold_text(ax, cx, ry + RH * 0.35, f"{d['start']}～{d['end']}", ha="center", va="center", color="#000000", fontproperties=fp(8.5))
                    else:
                        if note:
                            draw_bold_text(ax, cx, ry + RH * 0.80, note, ha="center", va="center", color=C_NOTE_TXT, fontproperties=fp(8))
                            draw_bold_text(ax, cx, ry + RH * 0.58, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(10))
                            draw_bold_text(ax, cx, ry + RH * 0.38, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(10))
                            draw_bold_text(ax, cx, ry + RH * 0.18, tr, ha="center", va="center", color="#000000", fontproperties=fp(9.5))
                        else:
                            draw_bold_text(ax, cx, ry + RH * 0.68, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(11))
                            draw_bold_text(ax, cx, ry + RH * 0.44, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(11))
                            draw_bold_text(ax, cx, ry + RH * 0.20, tr, ha="center", va="center", color="#000000", fontproperties=fp(10.5))

            legend_y = MB * 0.45
            badge_w, badge_h = CW * 0.90, 0.022
            has_active_transport = any(d in active_transport for d in dates)
            has_active_holiday = any(d in NATIONAL_HOLIDAYS for d in dates)

            pill_legends = [
                (0, "#F1F5F9", "#475569", C_NOTE_TXT, "備註 (Note)"),
                (1, C_DO_BG if has_emp_do else C_WORK_BG, "#E11D48" if has_emp_do else "#64748B", C_DO_TXT if has_emp_do else "#64748B", "休假日 (DO)"),
                (2, C_PAY_BG if has_emp_pay else C_WORK_BG, "#EA580C" if has_emp_pay else "#64748B", C_PAY_TXT if has_emp_pay else "#64748B", "特休 (PAY)"),
                (3, C_WORK_BG, "#DC2626" if has_emp_ot else "#64748B", C_OT_TXT if has_emp_ot else "#64748B", "工時 > 8.5h"),
                (4, "#FFF7ED" if has_active_holiday else C_WORK_BG, "#C2410C" if has_active_holiday else "#64748B", C_HOLI_TXT if has_active_holiday else "#64748B", "國定假日"),
                (5, "#F3E8FF" if has_active_transport else C_WORK_BG, "#7C3AED" if has_active_transport else "#64748B", C_NOTE_TXT if has_active_transport else "#64748B", "疏運"),
                (6, C_TOWN_BG if has_emp_town else C_WORK_BG, "#334155" if has_emp_town else "#64748B", C_TOWN_TXT if has_emp_town else "#64748B", "非正線勤務"),
            ]

            for col_idx, bg_clr, border_clr, txt_clr, label in pill_legends:
                col_x = ML + col_idx * CW
                lx = col_x + (CW - badge_w) / 2
                badge = FancyBboxPatch((lx, legend_y), badge_w, badge_h, boxstyle="round,pad=0.002,rounding_size=0.008", linewidth=1.2, edgecolor=border_clr, facecolor=bg_clr)
                ax.add_patch(badge)
                draw_bold_text(ax, lx + badge_w / 2, legend_y + badge_h / 2, label, ha="center", va="center", color=txt_clr, fontproperties=fp(7.5))

            # 底部灰色版本與設計版權宣告文字
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // TECHNICAL SHIFT SYSTEM v4.19", ha="left", va="bottom", color="#64748B", fontproperties=fp(7.5))
            draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str} | CONFIDENTIAL", ha="right", va="bottom", color="#64748B", fontproperties=fp(7.5))

            buf = io.BytesIO()
            plt.tight_layout(pad=0)
            plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
            buf.seek(0)
            plt.close()

            st.success("🎉 個人班表圖片生成成功！")
            st.image(buf, use_container_width=True)
            st.download_button("📥 點此下載高解析班表圖片", data=buf, file_name=f"TTN班表_{emp_name}.png", mime="image/png")

        except Exception as e:
            st.error(f"❌ 錯誤：{e}")
