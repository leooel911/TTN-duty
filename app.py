import streamlit as st
import os
import re
import io
import pandas as pd
from datetime import date, timedelta, datetime, timezone
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch
import time

matplotlib.use('Agg')

st.set_page_config(page_title="TTN Shift Producer", page_icon="700st.png", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 3rem 1rem !important; }
    .header-container { display: flex; justify-content: space-between; align-items: baseline; width: 100%; margin-bottom: 1rem; }
    .main-title { color: #F8FAFC !important; font-size: 26px; font-weight: 800; letter-spacing: 0.5px; margin: 0; }
    .edition-badge { color: #64748B !important; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); }
    .telemetry-title { color: #94A3B8 !important; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .telemetry-value { color: #F8FAFC !important; font-size: 18px; font-weight: 700; font-family: monospace; }
    .telemetry-sub { margin-top: 10px; padding-top: 8px; border-top: 1px solid #334155; font-size: 13px; color: #94A3B8; }
    .maint-sub { border-top: 1px solid #991B1B !important; color: #FECACA !important; }
    
    .date-banner { background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%); border-left: 5px solid #60A5FA; color: #FFFFFF; font-size: 16px; font-weight: 800; padding: 10px 16px; border-radius: 8px; margin-top: 28px; margin-bottom: 14px; letter-spacing: 1.5px; text-transform: uppercase; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }

    .result-card { background: #1E293B; border-left: 3px solid #3B82F6; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; color: #F8FAFC; }
    .time-row { font-size: 19px; font-weight: 700; color: #60A5FA; margin-bottom: 6px; font-family: monospace; }
    .name-row { font-size: 16px; font-weight: 600; margin-bottom: 6px; color: #E2E8F0; }
    .sub-info-row { font-size: 13px; color: #94A3B8; font-family: monospace; display: flex; gap: 16px; flex-wrap: wrap; }
    
    .stRadio > div { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; }
    .stRadio label { font-size: 15px !important; font-weight: 600 !important; color: #F8FAFC !important; }
    .stTextInput input { font-size: 18px !important; padding: 14px 16px !important; border-radius: 10px !important; background-color: #1E293B !important; color: #F8FAFC !important; border: 1px solid #475569 !important; }
    div.stButton > button { font-size: 18px !important; font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important; color: #ffffff !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

NATIONAL_HOLIDAYS = {
    "1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", 
    "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節",
    "6/19": "端午節", "9/25": "中秋節", "9/28": "教師節", "10/10": "國慶日",
    "10/25": "台灣光復節", "12/25": "行憲紀念日"
}

TRANSPORT_PERIODS = {"9/24-9/29": "中秋疏運"}
TITLE = "TRAIN CREW DUTY CALENDAR"

ROLE_FILES = {
    "駕駛": "TD.xlsx",
    "列車長": "TM.xlsx",
    "服勤員": "TA.xlsx"
}

ADMIN_PASSWORD = "Lf0900"
CREW_ACCESS_PASSWORD = "0900"
MAINTENANCE_FLAG_FILE = "maintenance.flag"

def get_file_mtime(path):
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime)
    return None

def format_mtime(dt):
    if not dt: return "無資料"
    diff = datetime.now() - dt
    if diff.days > 0: return f"{diff.days} 天前"
    hours = diff.seconds // 3600
    if hours > 0: return f"{hours} 小時前"
    return f"{diff.seconds // 60} 分鐘前"

def generate_time_options():
    options = []
    for h in range(24):
        for m in [0, 30]:
            options.append(f"{h:02d}:{m:02d}")
    options.extend(["04:00", "04:30", "05:00", "05:15", "05:26", "05:30", "06:00"])
    return sorted(list(set(options)))

TIME_OPTIONS = generate_time_options()

def set_maintenance_mode(is_maintenance):
    if is_maintenance:
        with open(MAINTENANCE_FLAG_FILE, "w") as f:
            f.write("ON")
    else:
        if os.path.exists(MAINTENANCE_FLAG_FILE):
            os.remove(MAINTENANCE_FLAG_FILE)

def is_maintenance_mode():
    return os.path.exists(MAINTENANCE_FLAG_FILE)

def pad_time(t_str):
    if not t_str or ":" not in t_str: return t_str
    parts = str(t_str).split(":")
    return f"{int(parts[0]):02d}:{parts[1]}" if len(parts) == 2 else str(t_str)

def calculate_hours(start_str, end_str):
    if not start_str or not end_str or ":" not in start_str or ":" not in end_str: return ""
    try:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        start_mins = sh * 60 + sm
        end_mins = eh * 60 + em
        if end_mins <= start_mins: end_mins += 24 * 60
        diff_mins = end_mins - start_mins
        return f"{diff_mins // 60}h{diff_mins % 60:02d}m"
    except: return ""

def is_valid_train_code(tr):
    if not tr: return False
    tr_clean = str(tr).strip().upper()
    leave_codes = ["PAY", "FAC", "DO", "D2W", "AL", "SL", "CL", "ML"]
    if tr_clean in leave_codes or "OGC" in tr_clean: return False
    return bool(re.match(r'^[A-Z]+\d+', tr_clean))

def is_overtime(h, tr, note):
    if not is_valid_train_code(tr):
        return False
    if not h: return False
    try:
        p = str(h).replace("h", ":").replace("m", "").split(":")
        return (int(p[0]) * 60 + int(p[1])) > 510
    except: return False

def translate_train_code(tr):
    if not tr: return "無"
    tr_upper = str(tr).strip().upper()
    mapping = {
        "PAY": "特休 (PAY)",
        "FAC": "家庭照顧假 (FAC)",
        "AL": "年假 (AL)",
        "SL": "病假 (SL)",
        "CL": "事假 (CL)"
    }
    return mapping.get(tr_upper, tr)

def is_town_shift(tr, note):
    tr_upper = str(tr).strip().upper()
    if is_valid_train_code(tr_upper):
        return False
    if tr_upper in ["PAY", "FAC"]:
        return False
    if not tr or tr_upper in ["", "無", "NAN"]:
        return True
    keywords = ["TOWN", "STD", "TTN", "DTT", "OGT", "OGC", "FAC", "DS", "H9", "WRSL"]
    return any(kw in f"{tr_upper} {str(note).upper()}" for kw in keywords)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip()]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): 
        return dict(start="", train=lines[0], end="", hours="", note="")
    
    start_time = pad_time(times[0]) if times else ""
    end_time = pad_time(times[1]) if len(times) > 1 else ""
    hours = calculate_hours(start_time, end_time)
    
    do_str = next((l for l in lines if "DO" in l or "D2W" in l or "PAY" in l or "FAC" in l), "")
    real_train = next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and l != do_str and "h" not in l and "m" not in l), "")
    
    if not real_train:
        non_time_lines = [l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and "h" not in l and "m" not in l]
        if non_time_lines:
            real_train = non_time_lines[0]

    notes = [l for l in lines if l not in times and l != real_train]

    return dict(start=start_time, end=end_time, train=real_train if real_train else "無", hours=hours, note=" ".join(notes))

def process_file_data(input_str):
    input_clean = input_str.strip().upper()
    matched_row, emp_id, emp_name, df_found = None, "", "", None
    for role, path in ROLE_FILES.items():
        if os.path.exists(path):
            df_temp = pd.read_excel(path, header=3)
            df_temp.columns = [str(c).strip() for c in df_temp.columns]
            for idx, row in df_temp.iterrows():
                if str(row.iloc[0]).strip().upper() == input_clean or str(row.iloc[1]).strip().upper() == input_clean:
                    matched_row, emp_id, emp_name, df_found = row, str(row.iloc[0]).strip(), str(row.iloc[1]).strip(), df_temp
                    break
        if matched_row is not None: break
    if matched_row is None: raise ValueError(f"找不到員編或姓名為「{input_str}」的資料。")
    col_names = df_found.columns[2:]
    dates = []
    start_dt = date(2026, 2, 1)
    for i, col in enumerate(col_names):
        col_str = str(col).strip()
        match_d = re.search(r'(\d+/\d+)', col_str)
        if match_d:
            dates.append(match_d.group(1))
            if i == 0: m, d = map(int, match_d.group(1).split("/")); start_dt = date(2026, m, d)
        else: dates.append(col_str)
    return start_dt, dates, emp_id, emp_name, matched_row.iloc[2:].values

def draw_bold_text(ax, x, y, text, **kwargs):
    ax.text(x, y, text, **kwargs)
    offset = 0.0002
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

def build_weeks(start_dt, dates, cells):
    first_wd = (start_dt.weekday() + 1) % 7
    weeks, week = [], [None] * first_wd
    for dt, raw in zip(dates, cells):
        week.append((dt, parse_cell(raw), str(raw) if not pd.isna(raw) else ""))
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

st.markdown("""<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>""", unsafe_allow_html=True)

if is_maintenance_mode():
    st.markdown("""
    <div class="telemetry-card" style="border: 1px solid #EF4444; background: linear-gradient(135deg, #7F1D1D 0%, #450A0A 100%);">
        <div class="telemetry-title" style="color: #FCA5A5;">系統維護公告</div>
        <div class="telemetry-value" style="color: #FEE2E2; font-size: 20px;">系統目前暫停開放維護中</div>
        <div class="telemetry-sub maint-sub">
            管理員正在更新排班資料或進行系統維護，請稍後再試。
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    latest_update = min([get_file_mtime(p) for p in ROLE_FILES.values() if os.path.exists(p)], default=None)
    st.markdown(f"""
    <div class="telemetry-card">
        <div class="telemetry-title">資料庫最後更新時間</div>
        <div class="telemetry-value">{format_mtime(latest_update)}</div>
        <div class="telemetry-sub">Data sync successfully via central server.</div>
    </div>
    """, unsafe_allow_html=True)

    app_mode = st.radio("選擇功能模式", ["生產個人班表圖片檔", "組員動態時段篩選（尋找換班協調專用・Beta測試版）"], horizontal=True)
    st.markdown("---")

    if app_mode == "生產個人班表圖片檔":
        target_input = st.text_input("輸入 員編 或 姓名 (例如: A023300 or 波莉)", value="A")
        access_password = st.text_input("輸入系統授權碼", type="password", value="")

        if st.button("立即生成個人班表圖片檔"):
            if access_password != CREW_ACCESS_PASSWORD: st.error("系統授權碼錯誤，請洽管理員")
            elif not any(os.path.exists(path) for path in ROLE_FILES.values()): st.error("無班表資料")
            else:
                try:
                    start_dt, dates, emp_id, emp_name, cells = process_file_data(target_input)
                    active_transport = parse_transport_periods(TRANSPORT_PERIODS)
                    font_prop = setup_font()
                    def fp(size=9): return fm.FontProperties(fname=font_prop.get_file(), size=size) if font_prop else fm.FontProperties(size=size)
                    
                    weeks = build_weeks(start_dt, dates, cells)
                    fig, ax = plt.subplots(figsize=(16, 11), dpi=300)
                    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
                    fig.patch.set_facecolor("white")
                    ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
                    TW, CW = 1.0 - ML - MR, (1.0 - ML - MR) / 7
                    RH = (1.0 - MT - MB - TH - DH) / len(weeks)
                    ty = 1.0 - MT - TH
                    ax.add_patch(FancyBboxPatch((ML, ty), TW, TH, boxstyle="square,pad=0", linewidth=0, facecolor=C_HDR))
                    
                    draw_bold_text(ax, ML + 0.008, ty + TH * 0.58, TITLE, ha="left", va="center", color="#FFFFFF", fontproperties=fp(16))
                    draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))
                    
                    badge_w = CW * 0.90
                    badge_x = (1.0 - MR) - CW + (CW - badge_w) / 2
                    badge_y = ty + TH * 0.42
                    badge_h = 0.035
                    
                    ax.add_patch(FancyBboxPatch((badge_x, badge_y), badge_w, badge_h, boxstyle="round,pad=0.002,rounding_size=0.01", linewidth=1.0, edgecolor="#334155", facecolor="#1E293B"))
                    draw_bold_text(ax, badge_x + badge_w / 2, badge_y + badge_h / 2, "Producer | C.L.F", ha="center", va="center", color="#38BDF8", fontproperties=fp(10.5))
                    
                    dy = ty - DH
                    for c in range(7):
                        x = ML + c * CW
                        ax.add_patch(FancyBboxPatch((x, dy), CW, DH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#475569", facecolor="#94A3B8"))
                        draw_bold_text(ax, x + CW / 2, dy + DH / 2, ["SUN 星期日", "MON 星期一", "TUE 星期二", "WED 星期三", "THU 星期四", "FRI 星期五", "SAT 星期六"][c], ha="center", va="center", color="#000000", fontproperties=fp(11))

                    has_emp_do, has_emp_pay, has_emp_ot, has_emp_town = False, False, False, False
                    for week in weeks:
                        for item in week:
                            if item is not None:
                                dt, d, raw_cell_str = item
                                tr, note, hours = d["train"], d.get("note", ""), d.get("hours", "")
                                is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d["start"]
                                
                                if is_pure_hol or tr.startswith("DO"): has_emp_do = True
                                elif tr in ["PAY", "FAC"] or "PAY" in raw_cell_str or "FAC" in raw_cell_str: has_emp_pay = True
                                elif is_town_shift(tr, note): has_emp_town = True
                                if is_overtime(hours, tr, note): has_emp_ot = True

                    for ri, week in enumerate(weeks):
                        ry = dy - (ri + 1) * RH
                        for ci, item in enumerate(week):
                            x = ML + ci * CW
                            if item is None: 
                                ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=C_EMPTY))
                                continue
                            dt, d, raw_cell_str = item
                            tr, note = d["train"], d.get("note", "")
                            
                            is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d["start"]
                            is_pay_shift = (tr in ["PAY", "FAC"]) or ("PAY" in raw_cell_str) or ("FAC" in raw_cell_str)
                            
                            bg = C_DO_BG if is_pure_hol else (C_PAY_BG if is_pay_shift else (C_TOWN_BG if is_town_shift(tr, note) else (C_WEEKEND_BG if ci in [0,6] else C_WORK_BG)))
                            ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=bg))
                            
                            if dt in NATIONAL_HOLIDAYS:
                                full_date_str = f"{dt} ({NATIONAL_HOLIDAYS[dt]})"
                                draw_bold_text(ax, x + 0.005, ry + RH - 0.004, full_date_str, ha="left", va="top", color=C_HOLI_TXT, fontproperties=fp(9.5))
                            else:
                                draw_bold_text(ax, x + 0.005, ry + RH - 0.004, dt, ha="left", va="top", color="#000000", fontproperties=fp(10))

                            if dt in active_transport:
                                draw_bold_text(ax, x + CW - 0.004, ry + RH - 0.004, active_transport[dt], ha="right", va="top", color="#7C3AED", fontproperties=fp(8.5))

                            if d.get("hours"): 
                                draw_bold_text(ax, x + CW - 0.004, ry + 0.003, f"({d['hours']})", ha="right", va="bottom", color=C_OT_TXT if is_overtime(d["hours"], tr, note) else "#000000", fontproperties=fp(11.5))
                                
                                do_match = next((l for l in raw_cell_str.split('\n') if "DO" in l or "D2W" in l or "PAY" in l or "FAC" in l or "OGC" in l), "")
                                if do_match:
                                    draw_bold_text(ax, x + CW - 0.004, ry + 0.026, do_match, ha="right", va="bottom", color=C_DO_TXT, fontproperties=fp(10.5))
                            
                            cx = x + CW / 2
                            if is_pure_hol: 
                                do_code = next((l for l in raw_cell_str.split('\n') if "DO" in l or "D2W" in l), "DO")
                                draw_bold_text(ax, cx, ry + RH * 0.48, do_code, ha="center", va="center", color=C_DO_TXT, fontproperties=fp(14))
                            elif is_pay_shift and not d["start"]: 
                                draw_bold_text(ax, cx, ry + RH * 0.48, tr, ha="center", va="center", color=C_PAY_TXT, fontproperties=fp(14))
                            else:
                                draw_bold_text(ax, cx, ry + RH * 0.65, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                                draw_bold_text(ax, cx, ry + RH * 0.40, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                                draw_bold_text(ax, cx, ry + RH * 0.15, tr, ha="center", va="center", color=C_PAY_TXT if is_pay_shift else "#000000", fontproperties=fp(12))

                    legend_y = MB * 0.45
                    badge_w_leg, badge_h_leg = CW * 0.90, 0.022
                    has_active_transport = any(d in active_transport for d in dates)
                    has_active_holiday = any(d in NATIONAL_HOLIDAYS for d in dates)

                    pill_legends = [
                        (0, "#F1F5F9", "#475569", C_NOTE_TXT, "備註"),
                        (1, C_DO_BG if has_emp_do else C_WORK_BG, "#E11D48" if has_emp_do else "#64748B", C_DO_TXT if has_emp_do else "#64748B", "休假日"),
                        (2, C_PAY_BG if has_emp_pay else C_WORK_BG, "#EA580C" if has_emp_pay else "#64748B", C_PAY_TXT if has_emp_pay else "#64748B", "特休"),
                        (3, C_WORK_BG, "#DC2626" if has_emp_ot else "#64748B", C_OT_TXT if has_emp_ot else "#64748B", "工時 > 8.5h"),
                        (4, "#FFF7ED" if has_active_holiday else C_WORK_BG, "#C2410C" if has_active_holiday else "#64748B", C_HOLI_TXT if has_active_holiday else "#64748B", "國定假日"),
                        (5, "#F3E8FF" if has_active_transport else C_WORK_BG, "#7C3AED" if has_active_transport else "#64748B", C_NOTE_TXT if has_active_transport else "#64748B", "疏運"),
                        (6, C_TOWN_BG if has_emp_town else C_WORK_BG, "#334155" if has_emp_town else "#64748B", C_TOWN_TXT if has_emp_town else "#64748B", "非正線勤務"),
                    ]

                    for col_idx, bg_clr, border_clr, txt_clr, label in pill_legends:
                        col_x = ML + col_idx * CW
                        lx = col_x + (CW - badge_w_leg) / 2
                        badge = FancyBboxPatch((lx, legend_y), badge_w_leg, badge_h_leg, boxstyle="round,pad=0.002,rounding_size=0.008", linewidth=1.2, edgecolor=border_clr, facecolor=bg_clr)
                        ax.add_patch(badge)
                        draw_bold_text(ax, lx + badge_w_leg / 2, legend_y + badge_h_leg / 2, label, ha="center", va="center", color=txt_clr, fontproperties=fp(9))

                    tw_tz = timezone(timedelta(hours=8))
                    now_str = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M")
                    
                    draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // v4.19", ha="left", va="bottom", color="#0F172A", fontproperties=fp(12))
                    draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str}", ha="right", va="bottom", color="#0F172A", fontproperties=fp(12))
                    
                    buf = io.BytesIO()
                    plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()
                    st.success("個人班表圖片生成成功")
                    st.image(buf, use_container_width=True)
                    st.info("提醒：長按上方的班表圖片即可一鍵存入手機相簿")
                    st.download_button("點此下載班表影像檔", data=buf, file_name=f"TTN班表_{emp_name}.png", mime="image/png")
                except Exception as e: st.error(f"錯誤：{e}")

    elif app_mode == "組員動態時段篩選（尋找換班協調專用・Beta測試版）":
        st.subheader("乘務時段區間與 Sign-In Time 快篩工具")
        selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2)
        target_path = ROLE_FILES[selected_role]

        if not os.path.exists(target_path):
            st.error(f"找不到【{selected_role}】的班表檔案 ({target_path})，請先至管理員後台上傳")
        else:
            df_search = pd.read_excel(target_path, header=3)
            df_search.columns = [str(c).strip() for c in df_search.columns]
            
            date_cols = []
            for col in df_search.columns[2:]:
                match_d = re.search(r'(\d+/\d+)', str(col))
                if match_d: date_cols.append(match_d.group(1))

            if not date_cols:
                st.error("表中未偵測到有效日期欄位")
            else:
                earliest_time_found = "05:26"
                if selected_role == "駕駛":
                    try:
                        all_found_times = []
                        for _, r_row in df_search.iterrows():
                            for cell_val in r_row.iloc[2:]:
                                p_temp = parse_cell(cell_val)
                                if p_temp["start"]:
                                    all_found_times.append(p_temp["start"])
                        if all_found_times:
                            earliest_time_found = min(all_found_times)
                            if earliest_time_found not in TIME_OPTIONS:
                                TIME_OPTIONS.append(earliest_time_found)
                                TIME_OPTIONS.sort()
                    except:
                        pass

                default_min_idx = TIME_OPTIONS.index(earliest_time_found) if earliest_time_found in TIME_OPTIONS else 0
                default_max_idx = TIME_OPTIONS.index("09:00") if "09:00" in TIME_OPTIONS else len(TIME_OPTIONS)-1

                c1, c2 = st.columns(2)
                with c1: start_date = st.selectbox("起始日期", date_cols, index=0)
                
                start_date_idx = date_cols.index(start_date) if start_date in date_cols else 0
                with c2: end_date = st.selectbox("結束日期", date_cols, index=start_date_idx)

                c3, c4 = st.columns(2)
                with c3: min_time = st.selectbox("Sign-In Time 區間：從", options=TIME_OPTIONS, index=default_min_idx)
                with c4: max_time = st.selectbox("Sign-In Time 區間：到", options=TIME_OPTIONS, index=default_max_idx)

                if st.button("開始區間檢索符合條件人員"):
                    try:
                        s_idx = date_cols.index(start_date)
                        e_idx = date_cols.index(end_date)
                        target_dates = date_cols[s_idx:e_idx+1] if s_idx <= e_idx else []
                    except: target_dates = []

                    if not target_dates:
                        st.warning("起始日期不可大於結束日期")
                    else:
                        search_results = []
                        all_cols_list = list(df_search.columns[2:])

                        for _, row in df_search.iterrows():
                            emp_id = str(row.iloc[0]).strip()
                            emp_name = str(row.iloc[1]).strip()
                            
                            for d_str in target_dates:
                                target_col_idx = -1
                                actual_col_pos = -1
                                for idx, col in enumerate(all_cols_list):
                                    if d_str in str(col):
                                        target_col_idx = idx + 2
                                        actual_col_pos = idx
                                        break
                                
                                if target_col_idx != -1:
                                    cell_raw = row.iloc[target_col_idx]
                                    parsed = parse_cell(cell_raw)
                                    start_t = parsed["start"]
                                    
                                    if start_t and min_time <= start_t <= max_time:
                                        next_day_sign_in = "無記錄"
                                        if actual_col_pos + 1 < len(all_cols_list):
                                            next_cell_raw = row.iloc[target_col_idx + 1]
                                            next_parsed = parse_cell(next_cell_raw)
                                            if next_parsed["start"]: next_day_sign_in = next_parsed["start"]
                                            elif next_parsed["train"]: next_day_sign_in = next_parsed["train"]
                                        
                                        is_long = is_overtime(parsed["hours"], parsed["train"], parsed["note"])
                                        is_non_line = is_town_shift(parsed["train"], parsed["note"])
                                        
                                        search_results.append({
                                            "日期": d_str,
                                            "員編": emp_id,
                                            "姓名": emp_name,
                                            "Sign-In": start_t,
                                            "收工時間": parsed["end"],
                                            "車次": translate_train_code(parsed["train"]),
                                            "隔日Sign-In": next_day_sign_in,
                                            "長班": is_long,
                                            "非正線": is_non_line
                                        })

                        search_results = sorted(search_results, key=lambda x: (x["日期"], x["Sign-In"]))

                        st.markdown(f"### 檢索結果：{start_date} 至 {end_date} ｜ Sign-In {min_time} ~ {max_time}（共符合 {len(search_results)} 筆）")
                        
                        if search_results:
                            current_date_group = None
                            for r in search_results:
                                if r["日期"] != current_date_group:
                                    current_date_group = r["日期"]
                                    st.markdown(f'<div class="date-banner">SERVICE DATE : {current_date_group}</div>', unsafe_allow_html=True)

                                long_shift_badge = '<span style="color:#F87171; font-size:14px; margin-left:8px;">● 長班</span>' if r['長班'] else ''
                                non_line_badge = '<span style="background:#4C1D95; color:#C4B5FD; font-size:11px; padding:2px 6px; border-radius:4px; margin-left:8px; font-weight:600;">非正線勤務</span>' if r['非正線'] else ''
                                
                                st.markdown(f"""
                                <div class="result-card">
                                    <div class="time-row">{r['Sign-In']} ➔ {r['收工時間']} {long_shift_badge} {non_line_badge}</div>
                                    <div class="name-row">{r['姓名']} <span style="color:#94A3B8; font-size:14px;">({r['員編']})</span></div>
                                    <div class="sub-info-row">
                                        <span>班別：{r['車次']}</span>
                                        <span>隔日 Sign-In：{r['隔日Sign-In']}</span>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("在指定的日期與 Sign-In 區間內，沒有找到符合條件的人員")

# --- 管理員專用：Database 區塊 ---
st.markdown("---")
with st.expander("管理員專用：Database"):
    password_input = st.text_input("請輸入管理員密碼", type="password")
    if password_input == ADMIN_PASSWORD:
        st.success("歡迎 LEO")
        
        st.subheader("系統維護控制台")
        current_maint = is_maintenance_mode()
        maint_toggle = st.checkbox("暫停開放系統服務 (維護模式)", value=current_maint)
        if maint_toggle != current_maint:
            set_maintenance_mode(maint_toggle)
            st.rerun()

        st.markdown("---")
        st.subheader("管理員檔案上傳區")
        selected_role = st.selectbox("選擇要上傳的職位類別", ["駕駛", "列車長", "服勤員"])
        uploaded_file = st.file_uploader(f"上傳【{selected_role}】班表檔案", type=["xlsx", "xls", "csv", "txt"])
        if uploaded_file:
            with open(ROLE_FILES[selected_role], "wb") as f: f.write(uploaded_file.getbuffer())
            st.success("上傳成功")
    elif password_input:
        st.error("密碼錯誤，請洽 CLF")
