"""
CREW DUTY ENGINE - Core Utilities & Logic
包含儲存格解析、班間合規檢核、工時過濾、檔案安全讀取與日誌系統
"""
import io
import json
import os
import sys

# 自動錨定專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import streamlit as st

try:
    from config import (
        DATA_DIR,
        LEAVE_CODES,
        LOG_FILE,
        NATIONAL_HOLIDAYS,
        TAIWAN_TZ,
        UNITS,
    )
except ImportError:
    DATA_DIR = os.path.join(BASE_DIR, "data")
    LOG_FILE = os.path.join(DATA_DIR, "activity_log.txt")
    TAIWAN_TZ = timezone(timedelta(hours=8))
    LEAVE_CODES = ["PAY", "FAC", "LEV", "MLP", "MTR", "UNP"]
    NATIONAL_HOLIDAYS = {}
    UNITS = {}

def get_file_mtime_str(file_path: str) -> str:
    """取得檔案最後修改時間字串"""
    if os.path.exists(file_path):
        try:
            mtime = os.path.getmtime(file_path)
            dt = datetime.fromtimestamp(mtime, tz=TAIWAN_TZ)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "時間取得失敗"
    return "無檔案"

def safe_read_excel(file_path: str, header: int = 3) -> pd.DataFrame:
    """安全讀取 Excel 檔案，處理例外狀況"""
    if not os.path.exists(file_path):
        return pd.DataFrame()
    try:
        df = pd.read_excel(file_path, header=header)
        return df
    except Exception as e:
        st.error(f"讀取 Excel 失敗 ({file_path}): {e}")
        return pd.DataFrame()

def parse_cell(cell_value: Any) -> Dict[str, Any]:
    """解析乘務大表個別儲存格 (含換行車次代碼、簽到退時間、請假與備註)"""
    val_str = str(cell_value).strip() if pd.notna(cell_value) else ""
    if not val_str or val_str.lower() in ["nan", "none", ""]:
        return {"train": "無", "start": None, "end": None, "hours": None, "note": ""}

    lines = [l.strip() for l in val_str.split("\n") if l.strip()]
    train_code = lines[0] if lines else "無"

    # 搜尋簽到與簽退時間 (例如: 06:12 - 14:35 或 06:12~14:35)
    time_match = re.search(r"(\d{2}:\d{2})\s*[\-~～]\s*(\d{2}:\d{2})", val_str)
    start_time, end_time = None, None
    if time_match:
        start_time = time_match.group(1)
        end_time = time_match.group(2)

    # 搜尋總工時 (例如: 8h15m 或 8.25h)
    hours_match = re.search(r"(\d+(?:\.\d+)?(?:h|m|小時|分)+)", val_str, re.IGNORECASE)
    hours_str = hours_match.group(1) if hours_match else None

    # 解析其他備註標籤
    note_lines = lines[1:] if len(lines) > 1 else []
    note_str = " ".join(note_lines)

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
    return "DO" in val_str or "D2W" in val_str or tr.startswith("DO")

def is_overtime(hours_str: Optional[str], train_code: str, note: str) -> bool:
    """檢核工時是否大於 8.5 小時"""
    if not hours_str:
        return False
    try:
        # 匹配小時與分鐘
        h_m = re.search(r"(\d+)\s*h\s*(\d+)?", hours_str, re.I)
        if h_m:
            h = int(h_m.group(1))
            m = int(h_m.group(2)) if h_m.group(2) else 0
            return (h + m / 60.0) > 8.5
        f_m = re.search(r"(\d+\.\d+)", hours_str)
        if f_m:
            return float(f_m.group(1)) > 8.5
    except Exception:
        pass
    return False

def is_town_shift(train_code: str, note: str) -> bool:
    """判斷是否為非正線勤務 (TOWN, STD, DS 等)"""
    tr = train_code.upper()
    return any(k in tr for k in ["TOWN", "STD", "DS", "駐廠", "預備"])

def translate_train_code(code: str) -> str:
    """轉換車次代碼為閱讀友善顯示"""
    if not code or code in ["無", "nan", "None"]:
        return "例休"
    return code

def check_shift_legality(row: pd.Series, col_idx: int, all_cols: List[Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    班間休息合規性檢核 (標準 11 小時檢核)
    """
    curr_cell = row.iloc[col_idx]
    curr_p = parse_cell(curr_cell)

    if not curr_p["start"] or col_idx <= 2:
        return True, "正常", {"min_interval": 12.0}

    prev_cell = row.iloc[col_idx - 1]
    prev_p = parse_cell(prev_cell)

    if not prev_p["end"]:
        return True, "正常", {"min_interval": 12.0}

    try:
        # 計算前一日簽退與今日簽到的時間差
        p_end_h, p_end_m = map(int, prev_p["end"].split(":"))
        c_start_h, c_start_m = map(int, curr_p["start"].split(":"))

        # 前一日簽退轉為分鐘，今日簽到加上 24 小時轉換
        prev_end_mins = p_end_h * 60 + p_end_m
        curr_start_mins = (c_start_h + 24) * 60 + c_start_m

        diff_hours = round((curr_start_mins - prev_end_mins) / 60.0, 1)

        if diff_hours < 11.0:
            return False, f"⚠️ 班間休息不足 11 小時 ({diff_hours}h)", {"min_interval": diff_hours}
        elif diff_hours < 12.0:
            return True, f"⚡ 班間休息接近臨界點 ({diff_hours}h)", {"min_interval": diff_hours}
        return True, "正常", {"min_interval": diff_hours}
    except Exception:
        return True, "計算異常", {"min_interval": 12.0}

def calculate_consecutive_work_days(row: pd.Series, end_col_idx: int) -> int:
    """計算連續出勤天數 (連六檢核)"""
    streak = 0
    for idx in range(end_col_idx, 1, -1):
        cell = row.iloc[idx]
        if is_cell_off_day(cell):
            break
        streak += 1
    return streak

def log_activity(msg: str) -> None:
    """紀錄系統操作日誌"""
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{now}] {msg}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass

def load_activity_logs() -> List[Dict[str, str]]:
    """讀取歷史系統日誌"""
    if not os.path.exists(LOG_FILE):
        return []
    logs = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                if line.strip():
                    m = re.match(r"\[(.*?)\] (.*)", line.strip())
                    if m:
                        logs.append({"time": m.group(1), "action": m.group(2)})
    except Exception:
        pass
    return logs[::-1]
