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

matplotlib.use('Agg')

# 🚆 將頁面標籤圖示 (Favicon) 改為 700st.png
st.set_page_config(page_title="🚆 TTN Shift Producer | C.L.F", page_icon="700st.png", layout="centered")

# 📱 強制鎖定深色模式與按鈕保護的 CSS
st.markdown("""
<style>
    /* 全域頁面背景與上下邊距優化 */
    .stApp {
        background-color: #0B0F19 !important;
        color: #F8FAFC !important;
    }
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    /* 頂部導航列容器：左右並排，讓 C.L.F Edition 完美靠右 */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        width: 100%;
        margin-bottom: 1rem;
    }
    /* 主標題：放大至 26px，強制不換行 */
    .main-title {
        color: #F8FAFC !important;
        font-size: 26px;
        font-weight: 800;
        letter-spacing: 0.5px;
        white-space: nowrap;
        margin: 0;
    }
    /* 右上角極小署名標籤 */
    .edition-badge {
        color: #64748B !important;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    /* 科技感系統狀態卡片 */
    .telemetry-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important;
        border: 1px solid #334155 !important;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    }
    .telemetry-title {
        color: #94A3B8 !important;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .telemetry-value {
        color: #F8FAFC !important;
        font-size: 18px;
        font-weight: 700;
        font-family: monospace;
    }
    /* 手機端輸入框優化 */
    .stTextInput input {
        font-size: 18px !important;
        padding: 14px 16px !important;
        border-radius: 10px !important;
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid #475569 !important;
    }
    .stTextInput label {
        font-size: 15px !important;
        font-weight: 600 !important;
        color: #E2E8F0 !important;
    }
    /* 🚀 強制保護主啟動按鈕 */
    div.stButton {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
    }
    div.stButton > button {
        font-size: 18px !important;
        font-weight: 700 !important;
        padding: 16px 24px !important;
        border-radius: 12px !important;
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5) !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
        margin-top: 10px;
        letter-spacing: 0.5px;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 50%, #1E40AF 100%) !important;
        color: #ffffff !important;
        box-shadow: 0 8px 25px rgba(37, 99, 235, 0.7) !important;
        transform: translateY(-2px);
    }
    /* 下載按鈕同步強制保護 */
    div.stDownloadButton {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
    }
    div.stDownloadButton > button {
        font-size: 16px !important;
        font-weight: 600 !important;
        padding: 14px 20px !important;
        border-radius: 10px !important;
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: #ffffff !important;
        width: 100% !important;
        box-shadow: 0 4px 14px rgba(5, 150, 105, 0.4) !important;
    }
</style>
""", unsafe_allow_html=True)

# 2026 全年完整國定假日與紀念日對照表
NATIONAL_HOLIDAYS = {
    "1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", 
    "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節",
    "6/19": "端午節", "9/25": "中秋節", "9/28": "教師節", "10/10": "國慶日",
    "10/25": "台灣光復節", "12/25": "行憲紀念日"
}

TRANSPORT_PERIODS = {"9/24-9/29": "中秋疏運"}
TITLE = "//    T r a i n    c r e w    D U T Y    C A L E N D A R"

# 三種職位的獨立檔案路徑
ROLE_FILES = {
    "駕駛": "TD.xlsx",
    "列車長": "TM.xlsx",
    "服勤員": "TA.xlsx"
}

# 🔐 設定管理員密碼與組員查詢授權密碼
ADMIN_PASSWORD = "Lf0900"
CREW_ACCESS_PASSWORD = "0900"

def get_file_info(path):
    """取得檔案檔名與最後更新日期資訊"""
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        tw_tz = timezone(timedelta(hours=8))
        time_str = datetime.fromtimestamp(mtime, tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        return path, time_str
    return "尚無檔案", "尚未上傳"

def get_system_duty_period():
    for role, path in ROLE_FILES.items():
        if os.path.exists(path):
            try:
                df_temp = pd.read_excel(path, header=3)
                col_names = [str(c).strip() for c in df_temp.columns[2:]]
                dates = []
                for col in col_names:
                    match_d = re.search(r'(\d+/\d+)', col)
                    if match_d: dates.append(match_d.group(1))
                if dates: return f"{dates[0]} 至 {dates[-1]}"
            except: continue
    return "尚未載入有效排班資料"

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

def is_overtime(h):
    if not h: return False
    try:
        p = str(h).replace("h", ":").replace("m", "").split(":")
        return (int(p[0]) * 60 + int(p[1])) > 510
    except: return False

def is_town_shift(tr, note):
    return any(kw in f"{tr} {note}".upper() for kw in ["TOWN", "STD", "TTN", "DTT", "OGT", "回廠", "訓練"])

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

st.markdown("""<div class="header-container"><div class="main-title">CREW DUTY ENGINE</div><div class="edition-badge">C.L.F Edition</div></div>""", unsafe_allow_html=True)
st.markdown(f"""<div class="telemetry-card"><div class="telemetry-title">System Telemetry // 目前系統排班有效週期</div><div class="telemetry-value">{get_system_duty_period()}</div></div>""", unsafe_allow_html=True)

target_input = st.text_input("輸入 員編 或 姓名 (例如: A023300)", value="A")
access_password = st.text_input("輸入 系統授權碼", type="password", value="")

if st.button("立即配置個人班表圖片檔"):
    if access_password != CREW_ACCESS_PASSWORD: st.error("系統授權碼錯誤！")
    elif not any(os.path.exists(path) for path in ROLE_FILES.values()): st.error("無班表資料！")
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
            
            # 頂部標題與識別資訊
            draw_bold_text(ax, ML + 0.008, ty + TH * 0.58, TITLE, ha="left", va="center", color="#FFFFFF", fontproperties=fp(16))
            draw_bold_text(ax, ML + 0.008, ty + TH * 0.25, f"CREW ID // {emp_id}    OPERATOR // {emp_name}    TIMELINE // {dates[0]} ~ {dates[-1]}", ha="left", va="center", color="#CBD5E1", fontproperties=fp(11))
            
            # 💡 右上角 Producer | C.L.F 加上獨立的科技風邊框 (Pill Badge) 往左移至 0.95 座標
            badge_x, badge_y, badge_w, badge_h = 0.905, ty + TH * 0.42, 0.085, 0.035
            ax.add_patch(FancyBboxPatch((badge_x, badge_y), badge_w, badge_h, boxstyle="round,pad=0.002,rounding_size=0.01", linewidth=1.0, edgecolor="#334155", facecolor="#1E293B"))
            draw_bold_text(ax, badge_x + badge_w / 2, badge_y + badge_h / 2, "Producer | C.L.F", ha="center", va="center", color="#38BDF8", fontproperties=fp(10))
            
            dy = ty - DH
            for c in range(7):
                x = ML + c * CW
                ax.add_patch(FancyBboxPatch((x, dy), CW, DH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#475569", facecolor="#94A3B8"))
                draw_bold_text(ax, x + CW / 2, dy + DH / 2, ["SUN 星期日", "MON 星期一", "TUE 星期二", "WED 星期三", "THU 星期四", "FRI 星期五", "SAT 星期六"][c], ha="center", va="center", color="#000000", fontproperties=fp(11))

            for ri, week in enumerate(weeks):
                ry = dy - (ri + 1) * RH
                for ci, cell in enumerate(week):
                    x = ML + ci * CW
                    if cell is None: ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=C_EMPTY)); continue
                    dt, d = cell
                    tr, note = d["train"], d.get("note", "")
                    is_hol = "D2W" in tr or "DO2W" in tr or "D2W" in note or "DO2W" in note
                    bg = C_DO_BG if (is_hol or tr.startswith("DO")) else (C_PAY_BG if tr=="PAY" else (C_TOWN_BG if is_town_shift(tr, note) else (C_WEEKEND_BG if ci in [0,6] else C_WORK_BG)))
                    ax.add_patch(FancyBboxPatch((x, ry), CW, RH, boxstyle="square,pad=0", linewidth=1.0, edgecolor="#64748B", facecolor=bg))
                    draw_bold_text(ax, x + 0.005, ry + RH - 0.004, dt, ha="left", va="top", color=C_HOLI_TXT if dt in NATIONAL_HOLIDAYS else "#000000", fontproperties=fp(10))
                    if d.get("hours"): draw_bold_text(ax, x + CW - 0.004, ry + 0.003, f"({d['hours']})", ha="right", va="bottom", color=C_OT_TXT if is_overtime(d["hours"]) else "#000000", fontproperties=fp(9))
                    cx = x + CW / 2
                    if tr.startswith("DO"): draw_bold_text(ax, cx, ry + RH * 0.48, tr, ha="center", va="center", color=C_DO_TXT, fontproperties=fp(14))
                    elif tr == "PAY": draw_bold_text(ax, cx, ry + RH * 0.6, "特休", ha="center", va="center", color=C_PAY_TXT, fontproperties=fp(12))
                    else:
                        draw_bold_text(ax, cx, ry + RH * 0.65, d["start"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                        draw_bold_text(ax, cx, ry + RH * 0.4, d["end"], ha="center", va="center", color="#000000", fontproperties=fp(13))
                        draw_bold_text(ax, cx, ry + RH * 0.15, tr, ha="center", va="center", color="#000000", fontproperties=fp(12))

            tw_tz = timezone(timedelta(hours=8))
            now_str = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M")
            
            # 💡 底部版權與時間文字再度加大（字體改為 12），顏色改為深黑（#0F172A）超醒目
            draw_bold_text(ax, ML, MB * 0.12, "DESIGNED BY: C.L.F // v4.19", ha="left", va="bottom", color="#0F172A", fontproperties=fp(12))
            draw_bold_text(ax, 1.0 - MR, MB * 0.12, f"GENERATED: {now_str}", ha="right", va="bottom", color="#0F172A", fontproperties=fp(12))
            
            buf = io.BytesIO()
            plt.tight_layout(pad=0); plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white", pad_inches=0.1); buf.seek(0); plt.close()
            st.success("個人班表圖片生成成功！")
            st.image(buf, use_container_width=True)
            st.info(" 💡 **提醒**：「**長按上方的班表圖片**」即可一鍵存入手機相簿！")
            st.download_button("點此下載班表影像檔", data=buf, file_name=f"TTN班表_{emp_name}.png", mime="image/png")
        except Exception as e: st.error(f"錯誤：{e}")

st.markdown("---")
with st.expander("管理員專用：Database"):
    password_input = st.text_input("請輸入管理員密碼", type="password")
    if password_input == ADMIN_PASSWORD:
        st.subheader("目前各職位班表狀態")
        status_data = [{"職位": role, "存檔名稱": get_file_info(path)[0], "最後更新時間": get_file_info(path)[1]} for role, path in ROLE_FILES.items()]
        st.table(pd.DataFrame(status_data))
        selected_role = st.selectbox("選擇要上傳的職位類別", ["駕駛", "列車長", "服勤員"])
        uploaded_file = st.file_uploader(f"上傳【{selected_role}】班表檔案", type=["xlsx", "xls", "csv", "txt"])
        if uploaded_file:
            with open(ROLE_FILES[selected_role], "wb") as f: f.write(uploaded_file.getbuffer())
            st.success("上傳成功！")
