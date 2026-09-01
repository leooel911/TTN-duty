import os
import re
import io
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from config import DATA_DIR, LOG_FILE, TAIWAN_TZ, UNITS

def get_maintenance_flag_path(unit, module_key):
    return os.path.join(DATA_DIR, f"maintenance_{unit}_{module_key}.flag")

def set_module_maintenance(unit, module_key, is_maint):
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR, exist_ok=True)
    flag_path = get_maintenance_flag_path(unit, module_key)
    if is_maint:
        with open(flag_path, "w") as f: f.write("ON")
    else:
        if os.path.exists(flag_path): os.remove(flag_path)

def is_module_maintenance(unit, module_key):
    flag_path = get_maintenance_flag_path(unit, module_key)
    return os.path.exists(flag_path)

def format_display_name(name):
    if not name or str(name).strip().upper() in ["NAN", "NONE", ""]:
        return ""
    clean_name = str(name).strip()
    if len(clean_name) <= 2:
        return clean_name
    return clean_name[1:]

@st.cache_data(show_spinner=False)
def safe_read_excel_cached(file_path_or_bytes, header=None, file_mtime=None):
    try:
        if isinstance(file_path_or_bytes, str):
            if file_path_or_bytes.endswith('.xls'):
                return pd.read_excel(file_path_or_bytes, header=header, engine='xlrd')
            else:
                try: return pd.read_excel(file_path_or_bytes, header=header, engine='openpyxl')
                except: return pd.read_excel(file_path_or_bytes, header=header, engine='xlrd')
        else:
            file_bytes = file_path_or_bytes
            try: return pd.read_excel(io.BytesIO(file_bytes), header=header, engine='openpyxl')
            except: return pd.read_excel(io.BytesIO(file_bytes), header=header, engine='xlrd')
    except Exception as e:
        raise ValueError(f"無法解析 Excel 檔案格式 (錯誤: {e})")

def safe_read_excel(file_source, header=None):
    if isinstance(file_source, str) and os.path.exists(file_source):
        mtime = os.path.getmtime(file_source)
        return safe_read_excel_cached(file_source, header=header, file_mtime=mtime)
    elif hasattr(file_source, "getvalue"):
        return safe_read_excel_cached(file_source.getvalue(), header=header)
    else:
        return safe_read_excel_cached(file_source, header=header)

def get_employee_name(unit_key, emp_input):
    input_clean = str(emp_input).strip().upper()
    unit_files = UNITS.get(unit_key, UNITS["TTN"])
    for role in ["駕駛", "列車長", "服勤員"]:
        path = unit_files.get(role, "")
        if os.path.exists(path):
            try:
                df = safe_read_excel(path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    emp_id = str(row.iloc[0]).strip().upper()
                    emp_name = str(row.iloc[1]).strip().upper()
                    if emp_id == input_clean or emp_name == input_clean:
                        return str(row.iloc[1]).strip()
            except: pass
    return ""

def parse_device_info(ua_string):
    ua = ua_string.lower()
    if "iphone" in ua: device = "iPhone"
    elif "ipad" in ua: device = "iPad"
    elif "android" in ua: device = "Android Phone"
    elif "macintosh" in ua or "mac os" in ua: device = "Mac"
    elif "windows" in ua: device = "Windows PC"
    else: device = "Desktop / Other"

    if "safari" in ua and "chrome" not in ua and "crios" not in ua: browser = "Safari"
    elif "chrome" in ua or "crios" in ua: browser = "Chrome"
    elif "line" in ua: browser = "LINE App"
    elif "edg" in ua: browser = "Edge"
    else: browser = "Browser"

    return f"{device} [{browser}]"

def log_activity(input_str):
    try:
        if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR, exist_ok=True)
        now_tw = datetime.now(TAIWAN_TZ).strftime('%Y-%m-%d %H:%M:%S')
        ua_raw = st.context.headers.get("user-agent", "") if hasattr(st, "context") else ""
        device_info = parse_device_info(ua_raw) if ua_raw else "未知裝置"
        current_operator = st.session_state.get("current_user_id", "未知")
        current_unit = st.session_state.get("current_unit", "TTN")
        log_entry = f"{now_tw} | 單位: {current_unit} | 操作者員編: {current_operator} | 裝置: {device_info} | 動作: {input_str}\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(log_entry)
    except: pass

def load_activity_logs():
    """解析你的實體 LOG_FILE 文字檔為 DataFrame 格式，供管理員後台讀取分析與下載"""
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line: continue
                parts = line.split(" | ")
                if len(parts) >= 5:
                    timestamp = parts[0]
                    unit = parts[1].replace("單位: ", "").strip()
                    user_id = parts[2].replace("操作者員編: ", "").strip()
                    device = parts[3].replace("裝置: ", "").strip()
                    action = parts[4].replace("動作: ", "").strip()
                    logs.append({
                        "timestamp": timestamp,
                        "unit": unit,
                        "user_id": user_id,
                        "user_name": get_employee_name(unit, user_id) or user_id,
                        "device": device,
                        "action": action,
                        "details": action
                    })
                else:
                    logs.append({
                        "timestamp": "",
                        "unit": "TTN",
                        "user_id": "未知",
                        "user_name": "未知",
                        "device": "未知",
                        "action": line,
                        "details": line
                    })
        except Exception as e:
            print(f"[Log Parsing Error] {e}")
    return logs

def get_file_mtime_str(path):
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(TAIWAN_TZ)
        size_kb = os.path.getsize(path) / 1024
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({size_kb:.1f} KB)"
    return "尚無檔案"

def pad_time(t_str):
    if not t_str or ":" not in str(t_str): return t_str
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
    if not is_valid_train_code(tr) or not h: return False
    try:
        p = str(h).replace("h", ":").replace("m", "").split(":")
        return (int(p[0]) * 60 + int(p[1])) > 510
    except: return False

def translate_train_code(tr):
    if not tr: return "無"
    tr_upper = str(tr).strip().upper()
    mapping = {"PAY": "特休 (PAY)", "FAC": "家庭照顧假 (FAC)", "LEV": "公假 (LEV)", "MLP": "身理假 (MLP)", "MTR": "事假 (MTR)"}
    return mapping.get(tr_upper, tr)

def is_town_shift(tr, note):
    tr_upper = str(tr).strip().upper()
    note_upper = str(note).strip().upper()
    combined_text = f"{tr_upper} {note_upper}"
    if not tr or tr_upper in ["", "無", "NAN"]: return True
    if tr_upper in ["PAY", "FAC"]: return False
    keywords = ["TOWN", "STD", "TTN", "DTT", "OGT", "OGC", "FAC", "DS", "H9", "WRSL"]
    for kw in keywords:
        if re.search(rf"\b{kw}\d*", combined_text): return True
    return not is_valid_train_code(tr_upper)

def parse_cell(raw):
    if pd.isna(raw) or not str(raw).strip(): return dict(start="", train="", end="", hours="", note="")
    raw_str = str(raw).strip()
    lines = [l.strip() for l in raw_str.split("\n") if l.strip() and l.strip() != "."]
    if not lines: return dict(start="", train="", end="", hours="", note="")
    times = [l for l in lines if re.match(r'^\d{1,2}:\d{2}$', l)]
    if len(lines) == 1 and ("DO" in lines[0] or "D2W" in lines[0]): return dict(start="", train=lines[0], end="", hours="", note="")

    start_time = pad_time(times[0]) if times else ""
    end_time = pad_time(times[1]) if len(times) > 1 else ""
    hours = calculate_hours(start_time, end_time)

    do_str = next((l for l in lines if "DO" in l or "D2W" in l or "PAY" in l or "FAC" in l), "")
    real_train = next((l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and l != do_str and "h" not in l and "m" not in l), "")
    if not real_train:
        non_time_lines = [l for l in lines if not re.match(r'^\d{1,2}:\d{2}$', l) and "h" not in l and "m" not in l]
        if non_time_lines: real_train = non_time_lines[0]

    notes = [l for l in lines if l not in times and l != real_train]
    clean_real_train = re.sub(r'[#%]', '', real_train).strip() if real_train else "無"
    return dict(start=start_time, end=end_time, train=clean_real_train if clean_real_train else "無", hours=hours, note=" ".join(notes))

def is_cell_off_day(raw_val):
    if pd.isna(raw_val) or not str(raw_val).strip():
        return True
    raw_str = str(raw_val).strip().upper()
    if raw_str in ["NAN", "NONE", "", "."]:
        return True
    parsed = parse_cell(raw_val)
    off_keywords = ["DO", "D2W", "PAY", "FAC", "AL", "SL", "CL", "ML"]
    if any(k in raw_str for k in off_keywords) or parsed["train"] in off_keywords:
        return True
    if not parsed["start"] and (not parsed["train"] or parsed["train"] == "無"):
        return True
    return False
