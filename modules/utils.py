"""
CREW DUTY ENGINE - Core Utilities & Logic (V1)
提供 Excel 安全讀取、儲存格解析、勤務特徵識別、連班計算、時區校正與 IP/設備日誌系統
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import DATA_DIR, LEAVE_CODES, LOG_FILE, NATIONAL_HOLIDAYS, TAIWAN_TZ, UNITS

# 台灣時區預設值 (UTC+8)
TW_TZ = timezone(timedelta(hours=8))

# 預編譯正線車次規則：[第一碼運轉區域 N/C/S] + [第二碼職位別 D/M/F/G/H] + [三位數以上班別數字]
MAINLINE_PATTERN = re.compile(r"^[NCS][DMFGH]\d+", re.IGNORECASE)


def parse_user_agent(ua_string: str) -> str:
    """簡易解析 User-Agent 為易讀的設備與瀏覽器標籤"""
    if not ua_string:
        return "未知設備"

    if "iPhone" in ua_string:
        device = "iPhone"
    elif "iPad" in ua_string:
        device = "iPad"
    elif "Android" in ua_string:
        device = "Android"
    elif "Macintosh" in ua_string:
        device = "Mac"
    elif "Windows" in ua_string:
        device = "Windows"
    else:
        device = "其他裝置"

    if "Edg" in ua_string:
        browser = "Edge"
    elif "Chrome" in ua_string:
        browser = "Chrome"
    elif "Safari" in ua_string:
        browser = "Safari"
    elif "Firefox" in ua_string:
        browser = "Firefox"
    else:
        browser = "其他瀏覽器"

    return f"{device} / {browser}"


def get_client_info() -> Tuple[str, str]:
    """擷取使用者的 IP 位址與裝置資訊 (User-Agent)"""
    try:
        headers = getattr(st.context, "headers", {})
        ip = headers.get("X-Forwarded-For", headers.get("Remote-Addr", "未知 IP"))
        if "," in ip:
            ip = ip.split(",")[0].strip()

        ua = headers.get("User-Agent", "")
        device = parse_user_agent(ua)
        return ip, device
    except Exception:
        return "未知 IP", "未知設備"


def normalize_date_str(val: Any) -> str:
    """將各種日期格式 (如 "2026/09/06", "09/06", "9/6", "09/06(日)") 統一轉換為標準 "M/D" 格式"""
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    m = re.search(r"(?:\d{4}/)?(\d{1,2})/(\d{1,2})", s)
    if m:
        return f"{int(m.group(1))}/{int(m.group(2))}"
    return ""


def get_file_mtime_str(file_path: str) -> str:
    """取得檔案最後修改時間字串 (強制轉為台灣時間)"""
    if isinstance(file_path, str) and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        try:
            mtime = os.path.getmtime(file_path)
            tz = TAIWAN_TZ if TAIWAN_TZ else TW_TZ
            dt = datetime.fromtimestamp(mtime, tz=tz)
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


def clean_time_str(time_str: Optional[str]) -> Optional[str]:
    """將時間字串統一轉換為兩位數小時格式 HH:MM (例如 5:26 -> 05:26)"""
    if not time_str:
        return None
    time_str = str(time_str).strip().replace("：", ":")
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", time_str)
    if m:
        h, mins = int(m.group(1)), m.group(2)
        return f"{h:02d}:{mins}"
    return None


def parse_cell(cell_value: Any) -> Dict[str, Any]:
    """解析乘務大表個別儲存格 (強制嚴格過濾報到時間，排除備註時間干擾)"""
    if pd.isna(cell_value) or cell_value is None:
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

    time_lines = []
    non_time_lines = []
    
    for l in lines:
        time_match = re.search(r"^(\d{1,2}):(\d{2})$", l)
        if time_match:
            h, m = int(time_match.group(1)), time_match.group(2)
            time_lines.append(f"{h:02d}:{m}")
        else:
            inline_match = re.search(r"\b(\d{1,2}):(\d{2})\b", l)
            if inline_match and len(l) <= 8:
                h, m = int(inline_match.group(1)), inline_match.group(2)
                time_lines.append(f"{h:02d}:{m}")
            else:
                non_time_lines.append(l)

    start_time = time_lines[0] if len(time_lines) >= 1 else None
    end_time = time_lines[1] if len(time_lines) >= 2 else None
    hours_raw = time_lines[2] if len(time_lines) >= 3 else None

    hours_str = ""
    if hours_raw:
        try:
            h, m = map(int, hours_raw.split(":"))
            hours_str = f"{h}h{m:02d}m"
        except Exception:
            pass

    train_code = "無"
    if non_time_lines:
        real_trains = [
            l for l in non_time_lines
            if not any(k in l.upper() for k in ["DO", "D2W", "D1", "D2", "OGC", "PAY", "FAC", "LEV", "MLP", "MTR"])
        ]
        if real_trains:
            train_code = real_trains[0]
        else:
            train_code = non_time_lines[0]

    note_lines = [
        l for l in lines
        if l != train_code and not re.search(r"\b\d{1,2}:\d{2}\b", l)
    ]
    note_str = " ".join(note_lines)

    return {
        "train": train_code,
        "start": start_time,
        "end": end_time,
        "hours": hours_str,
        "note": note_str,
    }


def is_cell_off_day(cell_value: Any) -> bool:
    """判斷該儲存格是否為純休假日 (DO / D2W / 休 等)"""
    if pd.isna(cell_value) or cell_value is None:
        return True
    val_str = str(cell_value).strip().upper()
    if not val_str or val_str in ["NAN", "NONE", "休", "OFF"]:
        return True

    parsed = parse_cell(cell_value)
    tr = parsed["train"].upper()

    if tr in ["無", "休", "OFF", "NAN", "NONE"]:
        return True

    if "DO" in val_str or "D2W" in val_str or tr.startswith("DO"):
        if not re.search(r"[A-Z]{1,2}\d{3,4}", val_str):
            return True

    return False


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


def is_town_shift(train_code: str, note: str = "") -> bool:
    """
    判斷是否為「非正線」勤務
    邏輯：只要包含有效車次代碼且「不符合正線規則」(N/C/S + D/M/F/G/H + 數字)，即判定為非正線 (True)
    """
    tr = str(train_code).strip().upper()

    if not tr or tr in ["無", "NAN", "NONE", "休", "OFF", "DO"]:
        return False

    return not bool(MAINLINE_PATTERN.match(tr))


def translate_train_code(code: Any) -> str:
    """轉換車次代碼為友善顯示字串"""
    s = str(code).strip()
    if not s or s in ["無", "nan", "None"]:
        return "例休"
    return s


def calculate_consecutive_work_days(row: pd.Series, target_date_str: str) -> int:
    """計算包含指定日期 (target_date_str) 在內的連續出勤天數 (雙向向左與向右擴展)"""
    norm_target = normalize_date_str(target_date_str)
    if not norm_target:
        return 0

    date_cols = []
    for idx, col in enumerate(row.index):
        if idx >= 2:
            norm_d = normalize_date_str(col)
            if norm_d:
                date_cols.append((idx, norm_d))

    target_pos = -1
    for pos, (col_idx, d_str) in enumerate(date_cols):
        if d_str == norm_target:
            target_pos = pos
            break

    if target_pos == -1:
        return 0

    c_idx, _ = date_cols[target_pos]
    if is_cell_off_day(row.iloc[c_idx]):
        return 0

    left = target_pos
    while left >= 0:
        col_i, _ = date_cols[left]
        if is_cell_off_day(row.iloc[col_i]):
            break
        left -= 1

    right = target_pos
    while right < len(date_cols):
        col_i, _ = date_cols[right]
        if is_cell_off_day(row.iloc[col_i]):
            break
        right += 1

    return right - left - 1


def check_week_has_holiday(target_date: str, date_cols: List[str], columns: Optional[Any] = None) -> Tuple[bool, str]:
    """檢查指定日期所屬週次是否涵蓋國定假日"""
    if not target_date or not date_cols:
        return False, ""
    try:
        cur_year = date.today().year
        norm_target = normalize_date_str(target_date)
        if not norm_target:
            return False, ""
        tm, td = map(int, norm_target.split("/"))
        tdt = date(cur_year, tm, td)
        tsun = tdt - timedelta(days=(tdt.weekday() + 1) % 7)
        tsat = tsun + timedelta(days=6)
        week_str = f"{tsun.strftime('%m/%d')} ~ {tsat.strftime('%m/%d')}"

        has_hol = False
        for d_str in date_cols:
            try:
                norm_d = normalize_date_str(d_str)
                if not norm_d:
                    continue
                dm, dd = map(int, norm_d.split("/"))
                ddt = date(cur_year, dm, dd)
                if tsun <= ddt <= tsat:
                    if norm_d in NATIONAL_HOLIDAYS or d_str in NATIONAL_HOLIDAYS:
                        has_hol = True
                        break
            except Exception:
                continue
        return has_hol, week_str
    except Exception:
        return False, ""


def log_activity(
    action: str,
    details: str = "",
    operator: str = "系統/訪客",
    unit: str = "全站",
    user: Optional[str] = None,
    detail: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """寫入全站系統操作日誌"""
    os.makedirs(DATA_DIR, exist_ok=True)

    tz = TAIWAN_TZ if TAIWAN_TZ else TW_TZ
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    client_ip, client_device = get_client_info()

    effective_operator = str(user if user is not None else operator).strip()
    effective_details = str(detail if detail is not None else details).strip()
    effective_unit = str(unit).strip()

    invalid_users = ["系統/訪客", "訪客", "", "NONE", "NAN"]
    if not effective_operator or effective_operator.upper() in invalid_users:
        effective_operator = (
            st.session_state.get("login_user_id")
            or st.session_state.get("user_input_field")
            or st.session_state.get("current_user_id")
            or "系統/訪客"
        )

    if not effective_unit or effective_unit in ["全站", "", "NONE", "NAN"]:
        effective_unit = st.session_state.get("current_unit", "全站")

    effective_operator = str(effective_operator).strip().upper()
    effective_unit = str(effective_unit).strip().upper()

    log_entry = f"[{now_str}] [{effective_operator}] [{effective_unit}] [{action}] IP:{client_ip} | Dev:{client_device} | {effective_details}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass

    csv_file = os.path.join(DATA_DIR, "system_logs.csv")
    new_log = {
        "時間": now_str,
        "操作者/員編": effective_operator,
        "單位": effective_unit,
        "類別": action,
        "IP": client_ip,
        "設備": client_device,
        "詳細日誌與動作內容": effective_details,
    }
    try:
        df_new = pd.DataFrame([new_log])
        if os.path.exists(csv_file):
            df_new.to_csv(
                csv_file, mode="a", header=False, index=False, encoding="utf-8-sig"
            )
        else:
            df_new.to_csv(
                csv_file, mode="w", header=True, index=False, encoding="utf-8-sig"
            )
    except Exception:
        pass


def load_activity_logs() -> List[Dict[str, str]]:
    """讀取系統歷史操作日誌"""
    csv_file = os.path.join(DATA_DIR, "system_logs.csv")
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            return df.iloc[::-1].to_dict(orient="records")
        except Exception:
            pass

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
    norm_target = normalize_date_str(date_str)
    new_row = row.copy()
    for idx, col in enumerate(new_row.index):
        if idx >= 2:
            norm_d = normalize_date_str(col)
            if norm_d and norm_d == norm_target:
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
    """發送管理員通知郵件"""
    log_activity(
        action="權限申請郵件通知",
        details=f"原因:{req_reason}",
        operator=f"{clean_name}({clean_emp})",
        unit=req_unit,
    )
    return True, "已成功送出權限申請紀錄"
