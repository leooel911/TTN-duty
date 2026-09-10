"""
CREW DUTY ENGINE - Core Utilities & Logic (V1)
提供 Excel 安全讀取、儲存格解析、勤務特徵識別、連班計算與日誌系統
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import DATA_DIR, LEAVE_CODES, LOG_FILE, NATIONAL_HOLIDAYS, TAIWAN_TZ, UNITS


def get_file_mtime_str(file_path: str) -> str:
    """取得檔案最後修改時間字串"""
    if isinstance(file_path, str) and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        try:
            mtime = os.path.getmtime(file_path)
            dt = datetime.fromtimestamp(mtime, tz=TAIWAN_TZ)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "時間讀取失敗"
    return "尚無檔案"


def safe_read_excel(file_path: str, header: int = 3) -> pd.DataFrame:
    """安全讀取 Excel 檔案，處理例外狀況"""
    if not (isinstance(file_path, str) and os.path.exists(file_path) and os.path.getsize(file_path) > 0):
        return pd.DataFrame()
    try:
        return pd.read_excel(file_path, header=header)
    except Exception:
        return pd.DataFrame()


def parse_cell(cell_value: Any) -> Dict[str, Any]:
    """解析乘務大表個別儲存格 (強健處理隱藏字元、全角冒號，並強制時間補零為 HH:MM)"""
    if pd.isna(cell_value):
        return {"train": "無", "start": None, "end": None, "hours": None, "note": ""}

    val_str = (
        str(cell_value)
        .replace("\r", "")
        .replace("\xa0", " ")
        .replace("：", ":")
        .strip()
    )
    if not val_str or val_str.lower() in ["nan", "none", ""]:
        return {"train": "無", "start": None, "end": None, "hours": None, "note": ""}

    lines = [l.strip() for l in val_str.split("\n") if l.strip()]
    if not lines:
        return {"train": "無", "start": None, "end": None, "hours": None, "note": ""}

    # 1. 抓取所有符合時間格式的字串
    raw_times = re.findall(r"\b\d{1,2}:\d{2}\b", val_str)

    # 2. 強制格式化為兩位數小時 HH:MM (將 "5:26" 轉為 "05:26")
    all_times = []
    for tm in raw_times:
        parts = tm.split(":")
        all_times.append(f"{int(parts[0]):02d}:{parts[1]}")

    # 3. 分離非時間欄位 (車次班號、請假註記等)
    non_time_lines = [l for l in lines if not re.search(r"\d{1,2}:\d{2}", l)]

    # 4. 若儲存格內無時間列
    if not all_times:
        first_line = lines[0]
        return {
            "train": first_line,
            "start": None,
            "end": None,
            "hours": None,
            "note": " ".join(lines[1:]) if len(lines) > 1 else "",
        }

    # 5. 時間列精準按順序對位
    start_time = all_times[0] if len(all_times) >= 1 else None
    end_time = all_times[1] if len(all_times) >= 2 else None
    hours_str = all_times[2] if len(all_times) >= 3 else None

    # 6. 車次班號 (train_code) 解析
    train_code = "無"
    if non_time_lines:
        real_trains = [
            l for l in non_time_lines
            if not any(k in l.upper() for k in ["DO", "D2W", "D1", "D2", "OGC", "PAY", "FAC"])
        ]
        if real_trains:
            train_code = real_trains[0]
        else:
            train_code = non_time_lines[0]

    note_str = " ".join([l for l in lines if l not in [train_code, start_time, end_time, hours_str]])

    return {
        "train": train_code,
        "start": start_time,
        "end": end_time,
        "hours": hours_str,
        "note": note_str,
    }


def is_cell_off_day(cell_value: Any) -> bool:
    """判斷該儲存格是否為純休假日 (DO / D2W 等)"""
    parsed = parse_cell(cell_value)
    tr = parsed["train"].upper()
    val_str = str(cell_value).upper()
    return "DO" in val_str or "D2W" in val_str or tr.startswith("DO") or tr in ["休", "D1", "D2"]


def is_overtime(hours_str: Optional[str], train_code: str = "", note: str = "") -> bool:
    """檢核工時是否大於 8.5 小時 (支援 H:MM、HH:MM、8.5h、8h30 等格式)"""
    if not hours_str:
        return False
    try:
        s = str(hours_str).strip()

        colon_m = re.search(r"(\d{1,2}):(\d{2})", s)
        if colon_m:
            h = int(colon_m.group(1))
            m = int(colon_m.group(2))
            return (h + m / 60.0) > 8.5

        hm_m = re.search(r"(\d+)\s*h\s*(\d+)?", s, re.I)
        if hm_m:
            h = int(hm_m.group(1))
            m = int(hm_m.group(2)) if hm_m.group(2) else 0
            return (h + m / 60.0) > 8.5

        f_m = re.search(r"(\d+(?:\.\d+)?)", s)
        if f_m:
            return float(f_m.group(1)) > 8.5
    except Exception:
        pass
    return False


def is_town_shift(train_code: str, note: str) -> bool:
    """判斷是否為非正線勤務 (TOWN, STD, DS, 庫備等)"""
    tr = str(train_code).upper()
    nt = str(note).upper()
    keys = ["TOWN", "STD", "DS", "駐廠", "預備", "庫", "備"]
    return any(k in tr or k in nt for k in keys)


def translate_train_code(code: Any) -> str:
    """轉換車次代碼為友善顯示字串"""
    s = str(code).strip()
    if not s or s in ["無", "nan", "None"]:
        return "例休"
    return s


def calculate_consecutive_work_days(row: pd.Series, target_date_str: str) -> int:
    """計算指定日期起的連續出勤天數"""
    streak = 0
    date_cols = []
    for idx, col in enumerate(row.index):
        if idx >= 2:
            m = re.search(r"(\d{1,2}/\d{1,2})", str(col))
            if m:
                date_cols.append((idx, m.group(1)))

    target_pos = -1
    for pos, (col_idx, d_str) in enumerate(date_cols):
        if d_str == target_date_str:
            target_pos = pos
            break

    if target_pos != -1:
        for p in range(target_pos, -1, -1):
            c_idx, _ = date_cols[p]
            cell_val = row.iloc[c_idx]
            if is_cell_off_day(cell_val):
                break
            streak += 1
    return streak


def check_week_has_holiday(target_date: str, date_cols: List[str], columns: Optional[Any] = None) -> Tuple[bool, str]:
    """檢查指定日期所屬週次是否涵蓋國定假日"""
    if not target_date or not date_cols:
        return False, ""
    try:
        cur_year = date.today().year
        tm, td = map(int, target_date.split("/"))
        tdt = date(cur_year, tm, td)
        tsun = tdt - timedelta(days=(tdt.weekday() + 1) % 7)
        tsat = tsun + timedelta(days=6)
        week_str = f"{tsun.strftime('%m/%d')} ~ {tsat.strftime('%m/%d')}"

        has_hol = False
        for d_str in date_cols:
            try:
                dm, dd = map(int, d_str.split("/"))
                ddt = date(cur_year, dm, dd)
                if tsun <= ddt <= tsat:
                    if d_str in NATIONAL_HOLIDAYS:
                        has_hol = True
                        break
            except Exception:
                continue
        return has_hol, week_str
    except Exception:
        return False, ""


def log_activity(action: str, details: str = "") -> None:
    """寫入全站系統操作日誌"""
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{now}] {action} | {details}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass


def load_activity_logs() -> List[Dict[str, str]]:
    """讀取系統歷史操作日誌"""
    if not os.path.exists(LOG_FILE):
        return []
    logs = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                if line.strip():
                    m = re.match(r"\[(.*?)\] (.*)", line.strip())
                    if m:
                        logs.append({"timestamp": m.group(1), "action": m.group(2)})
    except Exception:
        pass
    return logs[::-1]


MAINTENANCE_FILE = os.path.join(DATA_DIR, "maintenance.json")


def is_module_maintenance(unit_code: str, module_key: str) -> bool:
    """讀取模組維護狀態"""
    if os.path.exists(MAINTENANCE_FILE):
        try:
            with open(MAINTENANCE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(unit_code, {}).get(module_key, False)
        except Exception:
            pass
    return False


def set_module_maintenance(unit_code: str, module_key: str, state: bool) -> None:
    """寫入模組維護狀態"""
    os.makedirs(DATA_DIR, exist_ok=True)
    data = {}
    if os.path.exists(MAINTENANCE_FILE):
        try:
            with open(MAINTENANCE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    if unit_code not in data:
        data[unit_code] = {}
    data[unit_code][module_key] = state
    with open(MAINTENANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_simulated_cell(row: pd.Series, date_str: str, val: str) -> pd.Series:
    """模擬換假試算時更新該日期的儲存格"""
    new_row = row.copy()
    for idx, col in enumerate(new_row.index):
        if idx >= 2:
            m = re.search(r"(\d{1,2}/\d{1,2})", str(col))
            if m and m.group(1) == date_str:
                new_row.iloc[idx] = val
                break
    return new_row


def get_employee_name(unit_code: str, emp_id: str) -> str:
    """依員編向 Excel 大表查詢姓名"""
    emp_id_str = str(emp_id).strip().upper()
    unit_files = UNITS.get(unit_code, {})
    for role, path in unit_files.items():
        if isinstance(path, str) and os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                df = safe_read_excel(path, header=3)
                for _, row in df.iterrows():
                    if str(row.iloc[0]).strip().upper() == emp_id_str:
                        return str(row.iloc[1]).strip()
            except Exception:
                pass
    return ""


def format_display_name(name: str) -> str:
    """格式化顯示姓名"""
    s = str(name).strip()
    return s if s else ""


def send_admin_email(req_unit: str, clean_emp: str, clean_name: str, req_reason: str) -> Tuple[bool, str]:
    """發送管理員通知郵件 (紀錄於系統日誌)"""
    log_activity("權限申請郵件通知", f"單位:{req_unit} | 員編:{clean_emp} | 姓名:{clean_name}")
    return True, "已成功送出權限申請紀錄"
