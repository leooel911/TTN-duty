import io
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import streamlit as st
from config import (
    DATA_DIR,
    LEAVE_CODES,
    LOG_FILE,
    NATIONAL_HOLIDAYS,
    TAIWAN_TZ,
    UNITS,
)


# =========================================================
# 1. 模組維護狀態控制 (雙重相容判定：.flag 與 .json)
# =========================================================
def get_maintenance_flag_path(unit: str, module_key: str) -> str:
    """取得特定單位模組的 Flag 檔案路徑"""
    return os.path.join(DATA_DIR, f"maintenance_{unit}_{module_key}.flag")


def set_module_maintenance(unit: str, module_key: str, is_maint: bool) -> None:
    """開啟或關閉特定模組之維護狀態"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    flag_path = get_maintenance_flag_path(unit, module_key)
    if is_maint:
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write("ON")
    else:
        if os.path.exists(flag_path):
            os.remove(flag_path)


def is_module_maintenance(unit: str, module_key: str) -> bool:
    """檢測特定單位的模組是否處於維護狀態 (支援 .flag 與 .json 雙軌檢測)"""
    flag_path = get_maintenance_flag_path(unit, module_key)
    if os.path.exists(flag_path):
        return True

    maint_json_paths = [
        os.path.join(DATA_DIR, "maintenance.json"),
        "maintenance.json",
    ]
    for json_path in maint_json_paths:
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                full_key = f"{unit}_{module_key}"
                if data.get(full_key, False):
                    return True
            except Exception:
                pass

    return False


# =========================================================
# 2. 個資遮罩與 Excel 相容讀取引擎
# =========================================================
def format_display_name(name: Any) -> str:
    """將姓名遮罩顯示 (如: 張小明 -> 小明)"""
    if not name or str(name).strip().upper() in ["NAN", "NONE", ""]:
        return ""
    clean_name = str(name).strip()
    if len(clean_name) <= 2:
        return clean_name
    return clean_name[1:]


@st.cache_data(show_spinner=False)
def safe_read_excel_cached(
    file_path_or_bytes: Union[str, bytes],
    header: Optional[int] = None,
    file_mtime: Optional[float] = None,
) -> pd.DataFrame:
    """高效能快取 Excel 讀取器 (支援 .xlsx 與舊版 .xls)"""
    try:
        if isinstance(file_path_or_bytes, str):
            if file_path_or_bytes.endswith(".xls"):
                return pd.read_excel(file_path_or_bytes, header=header, engine="xlrd")
            else:
                try:
                    return pd.read_excel(
                        file_path_or_bytes, header=header, engine="openpyxl"
                    )
                except Exception:
                    return pd.read_excel(file_path_or_bytes, header=header, engine="xlrd")
        else:
            file_bytes = file_path_or_bytes
            try:
                return pd.read_excel(
                    io.BytesIO(file_bytes), header=header, engine="openpyxl"
                )
            except Exception:
                return pd.read_excel(
                    io.BytesIO(file_bytes), header=header, engine="xlrd"
                )
    except Exception as e:
        raise ValueError(f"無法解析 Excel 檔案格式 (錯誤: {e})")


def safe_read_excel(file_source: Any, header: Optional[int] = None) -> pd.DataFrame:
    """Excel 讀取相容性安全對應入口"""
    if isinstance(file_source, str) and os.path.exists(file_source):
        mtime = os.path.getmtime(file_source)
        return safe_read_excel_cached(file_source, header=header, file_mtime=mtime)
    elif hasattr(file_source, "getvalue"):
        return safe_read_excel_cached(file_source.getvalue(), header=header)
    else:
        return safe_read_excel_cached(file_source, header=header)


@st.cache_data(show_spinner=False)
def get_unit_employee_dict(unit_key: str) -> Dict[str, str]:
    """讀取大表並建置 {員編/姓名: 姓名} 之記憶體字典快取"""
    unit_files = UNITS.get(unit_key, UNITS.get("TTN", {}))
    emp_dict: Dict[str, str] = {}
    for role in ["駕駛", "列車長", "服勤員"]:
        path = unit_files.get(role, "")
        if os.path.exists(path):
            try:
                df = safe_read_excel(path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    emp_id = str(row.iloc[0]).strip().upper()
                    emp_name = str(row.iloc[1]).strip()
                    if (
                        emp_id
                        and emp_id not in ["NAN", "NONE", "員編", "EMP_ID"]
                        and emp_name
                    ):
                        emp_dict[emp_id] = emp_name
                        emp_dict[emp_name.upper()] = emp_name
            except Exception:
                pass
    return emp_dict


def get_employee_name(unit_key: str, emp_input: Any) -> str:
    """全大表員編對照姓名檢索器 (使用記憶體快取)"""
    input_clean = str(emp_input).strip().upper()
    if not input_clean or input_clean in ["NAN", "NONE", ""]:
        return ""

    emp_dict = get_unit_employee_dict(unit_key)
    return emp_dict.get(input_clean, "")


# =========================================================
# 3. 裝置解析與結構化操作日誌紀錄 (Audit Trail)
# =========================================================
def parse_device_info(ua_string: str) -> str:
    """解析 User-Agent 判定使用者裝置與瀏覽器類型"""
    ua = ua_string.lower()
    if "iphone" in ua:
        device = "iPhone"
    elif "ipad" in ua:
        device = "iPad"
    elif "android" in ua:
        device = "Android Phone"
    elif "macintosh" in ua or "mac os" in ua:
        device = "Mac"
    elif "windows" in ua:
        device = "Windows PC"
    else:
        device = "Desktop / Other"

    if "safari" in ua and "chrome" not in ua and "crios" not in ua:
        browser = "Safari"
    elif "chrome" in ua or "crios" in ua:
        browser = "Chrome"
    elif "line" in ua:
        browser = "LINE App"
    elif "edg" in ua:
        browser = "Edge"
    else:
        browser = "Browser"

    return f"{device} [{browser}]"


def log_activity(
    action_or_type: Any,
    details: str = "",
    unit: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """
    結構化紀錄系統日誌
    支援舊版單字串傳入: log_activity("做某事")
    支援新版結構化傳入: log_activity("換班快篩", "詳細參數細節...")
    """
    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)

        now_tw = datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

        ua_raw = ""
        client_ip = "127.0.0.1"
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers
            ua_raw = headers.get("user-agent", "")
            client_ip = (
                headers.get("x-forwarded-for", headers.get("host", "127.0.0.1"))
                .split(",")[0]
                .strip()
            )

        device_info = parse_device_info(ua_raw) if ua_raw else "未知裝置"
        current_operator = user_id or st.session_state.get("current_user_id", "未知")
        current_unit = unit or st.session_state.get("current_unit", "TTN")

        if details:
            full_action = f"[{action_or_type}] {details}"
        else:
            full_action = str(action_or_type)

        log_entry = (
            f"{now_tw} | 單位: {current_unit} | 操作者員編: {current_operator} | "
            f"裝置: {device_info} | IP: {client_ip} | 動作: {full_action}\n"
        )

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass


def load_activity_logs() -> List[Dict[str, Any]]:
    """解析 LOG 檔案，支援舊版格式相容與新版欄位提取"""
    logs: List[Dict[str, Any]] = []
    possible_log_paths = [
        LOG_FILE,
        "activity.log",
        os.path.join(DATA_DIR, "activity.log"),
    ]
    log_path = next((p for p in possible_log_paths if os.path.exists(p)), None)

    if log_path:
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" | ")
                if len(parts) >= 5:
                    timestamp = parts[0]
                    unit = parts[1].replace("單位: ", "").strip()
                    user_id = parts[2].replace("操作者員編: ", "").strip()

                    if len(parts) >= 6 and parts[3].startswith("裝置:"):
                        device = parts[3].replace("裝置: ", "").strip()
                        ip_addr = parts[4].replace("IP: ", "").strip()
                        action = parts[5].replace("動作: ", "").strip()
                    else:
                        device = parts[3].replace("裝置: ", "").strip()
                        ip_addr = "N/A"
                        action = parts[4].replace("動作: ", "").strip()

                    action_type = "一般操作"
                    details_str = action
                    if action.startswith("[") and "]" in action:
                        m = re.match(r"^\[(.*?)\]\s*(.*)$", action)
                        if m:
                            action_type = m.group(1)
                            details_str = m.group(2)

                    logs.append({
                        "timestamp": timestamp,
                        "unit": unit,
                        "user_id": user_id,
                        "user_name": get_employee_name(unit, user_id) or user_id,
                        "device": device,
                        "ip": ip_addr,
                        "action_type": action_type,
                        "action": action,
                        "details": details_str if details_str else action,
                    })
                else:
                    logs.append({
                        "timestamp": "",
                        "unit": "TTN",
                        "user_id": "未知",
                        "user_name": "未知",
                        "device": "未知",
                        "ip": "N/A",
                        "action_type": "系統日誌",
                        "action": line,
                        "details": line,
                    })
        except Exception as e:
            print(f"[Log Parsing Error] {e}")
    return logs


def get_file_mtime_str(path: str) -> str:
    """取得檔案最後修改時間與檔案大小格式化字串"""
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(TAIWAN_TZ)
        size_kb = os.path.getsize(path) / 1024
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({size_kb:.1f} KB)"
    return "尚無檔案"


# =========================================================
# 4. 時間與工時運算工具
# =========================================================
def pad_time(t_str: Any) -> str:
    """對時間字串補齊雙位數格式 (例如: 8:00 -> 08:00)"""
    if not t_str or ":" not in str(t_str):
        return str(t_str) if t_str else ""
    parts = str(t_str).split(":")
    return f"{int(parts[0]):02d}:{parts[1]}" if len(parts) == 2 else str(t_str)


def calculate_hours(start_str: str, end_str: str) -> str:
    """計算起訖時間差，並回傳工時格式字串 (例如: 8h30m)"""
    if not start_str or not end_str or ":" not in start_str or ":" not in end_str:
        return ""
    try:
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        start_mins = sh * 60 + sm
        end_mins = eh * 60 + em
        if end_mins <= start_mins:
            end_mins += 24 * 60
        diff_mins = end_mins - start_mins
        return f"{diff_mins // 60}h{diff_mins % 60:02d}m"
    except Exception:
        return ""


def is_valid_train_code(tr: Any) -> bool:
    """檢查車次代碼是否為正線出勤車次"""
    if not tr:
        return False
    tr_clean = str(tr).strip().upper()
    if (
        tr_clean.startswith("DO")
        or tr_clean.startswith("D2W")
        or tr_clean.startswith("D3W")
        or "OGC" in tr_clean
    ):
        return False
    if tr_clean in LEAVE_CODES:
        return False
    return bool(re.match(r"^[A-Z]+\d+", tr_clean))


def is_overtime(h: Any, tr: Any, note: Any) -> bool:
    """判斷工時是否屬於長班或加班 (> 8.5 小時 / 510 分鐘)"""
    if not is_valid_train_code(tr) or not h:
        return False
    try:
        p = str(h).replace("h", ":").replace("m", "").split(":")
        return (int(p[0]) * 60 + int(p[1])) > 510
    except Exception:
        return False


def translate_train_code(tr: Any) -> str:
    """將假別英文代碼轉譯為可讀說明文字"""
    if not tr:
        return "無"
    tr_upper = str(tr).strip().upper()
    mapping = {
        "PAY": "特休 (PAY)",
        "FAC": "家庭照顧假 (FAC)",
        "LEV": "公假 (LEV)",
        "MLP": "生理假 (MLP)",
        "MTR": "事假 (MTR)",
    }
    return mapping.get(tr_upper, str(tr))


def is_town_shift(tr: Any, note: Any) -> bool:
    """判斷是否為非正線/駐地/庫內勤務"""
    tr_upper = str(tr).strip().upper()
    note_upper = str(note).strip().upper()
    combined_text = f"{tr_upper} {note_upper}"
    if not tr or tr_upper in ["", "無", "NAN"]:
        return True
    if tr_upper in ["PAY", "FAC"]:
        return False
    keywords = [
        "TOWN",
        "STD",
        "TTN",
        "DTT",
        "OGT",
        "OGC",
        "FAC",
        "DS",
        "H9",
        "WRSL",
    ]
    for kw in keywords:
        if re.search(rf"\b{kw}\d*", combined_text):
            return True
    return not is_valid_train_code(tr_upper)


# =========================================================
# 5. 班表儲存格核心解析 (Cell Parser) 與連上天數運算
# =========================================================
def parse_cell(raw: Any) -> Dict[str, str]:
    """精準解析 Excel 儲存格內容，拆解報到時間、車次、報退時間與備註"""
    if pd.isna(raw) or not str(raw).strip():
        return dict(start="", train="無", end="", hours="", note="")

    raw_str = str(raw).strip()
    lines = [
        l.strip()
        for l in raw_str.replace("\r", "").split("\n")
        if l.strip() and l.strip() != "."
    ]
    if not lines:
        return dict(start="", train="無", end="", hours="", note="")

    raw_upper = raw_str.upper()

    times = re.findall(r"\b\d{1,2}:\d{2}\b", raw_str)
    start_time = pad_time(times[0]) if len(times) >= 1 else ""
    end_time = pad_time(times[1]) if len(times) >= 2 else ""
    hours = calculate_hours(start_time, end_time)

    do_match = re.search(r"(DO\d*W?|D\d+W|OGC)", raw_str, re.IGNORECASE)
    note_tag = do_match.group(1).upper() if do_match else ""

    real_train = ""
    for line in lines:
        line_clean = line.strip()
        if re.match(r"^\d{1,2}:\d{2}$", line_clean) or re.search(
            r"^\(?\d+h\d*m?\)?$", line_clean, re.IGNORECASE
        ):
            continue
        if (
            re.match(r"^(DO\d*W?|D\d+W|OGC)$", line_clean, re.IGNORECASE)
            and start_time
        ):
            continue
        if not real_train:
            real_train = line_clean

    found_leave = next((k for k in LEAVE_CODES if k in raw_upper), "")
    if found_leave and not is_valid_train_code(real_train):
        return dict(
            start=start_time,
            end=end_time,
            train=found_leave,
            hours=hours,
            note=found_leave,
        )

    clean_real_train = (
        re.sub(r"[#%]", "", real_train).strip() if real_train else "無"
    )
    notes = [
        l
        for l in lines
        if l not in times
        and l != clean_real_train
        and not re.search(r"^\(?\d+h\d*m?\)?$", l, re.IGNORECASE)
    ]
    note_final = " ".join(notes) if notes else note_tag

    return dict(
        start=start_time,
        end=end_time,
        train=clean_real_train if clean_real_train else "無",
        hours=hours,
        note=note_final,
    )


def is_cell_off_day(raw_val: Any) -> bool:
    """判定儲存格是否屬於休假日/DO/休假"""
    if pd.isna(raw_val) or not str(raw_val).strip():
        return True
    raw_str = str(raw_val).strip().upper()
    if raw_str in ["NAN", "NONE", "", ".", "休", "OFF", "無"]:
        return True

    parsed = parse_cell(raw_val)
    train_code = str(parsed.get("train", "")).strip().upper()
    has_time = bool(parsed.get("start"))
    has_valid_train = is_valid_train_code(train_code)

    if re.search(r"(DO2W|D2W|DO3W|D3W|OGC)", raw_str):
        if has_time or has_valid_train:
            return False
        return True

    if "PAY" in raw_str or train_code == "PAY":
        return False

    if train_code in LEAVE_CODES or any(k in raw_str for k in LEAVE_CODES):
        if not has_valid_train and not train_code.startswith("N"):
            return True

    if has_valid_train or train_code.startswith("N"):
        return False

    if (
        has_time
        and train_code not in LEAVE_CODES
        and not train_code.startswith("DO")
    ):
        return False

    return True


def resets_work_streak(raw_val: Any) -> bool:
    """判定該天是否能中斷連續出勤計數"""
    if pd.isna(raw_val) or not str(raw_val).strip():
        return True

    raw_str = str(raw_val).strip().upper()
    if raw_str in ["NAN", "NONE", "", "."]:
        return True

    parsed = parse_cell(raw_val)
    train_code = str(parsed.get("train", "")).strip().upper()
    has_time = bool(parsed.get("start"))
    has_valid_train = is_valid_train_code(train_code)

    if has_time or has_valid_train:
        return False

    if re.search(r"(DO2W?|D2W|PAY|OGC)", raw_str):
        return False

    return True


def set_simulated_cell(
    series: pd.Series, date_keyword: str, new_val: Any
) -> pd.Series:
    """模擬替換 Series 中特定日期欄位數值以利快篩驗算"""
    key_clean = str(date_keyword).strip()
    matched_col = None
    for col in series.index:
        col_str = str(col).strip()
        if key_clean == col_str or key_clean in col_str:
            matched_col = col
            break
    if matched_col:
        series[matched_col] = new_val
    return series


def calculate_consecutive_work_days(
    series: pd.Series, target_date_str: Optional[str] = None
) -> int:
    """計算指定組員特定日期或全月之連續上班天數數值"""
    date_cols: List[Any] = []
    for col in series.index:
        col_str = str(col).strip()
        if col_str in [
            "員編",
            "EMP_ID",
            "姓名",
            "NAME",
            "單位",
            "UNIT",
            "ROLE",
            "角色權限",
            "帳號狀態",
        ]:
            continue
        if re.search(r"\d{1,2}/\d{1,2}", col_str):
            date_cols.append(col)

    if not date_cols:
        return 0

    work_status: List[bool] = []
    target_idx: Optional[int] = None

    for idx, col in enumerate(date_cols):
        val = series[col]
        is_off = is_cell_off_day(val)
        work_status.append(not is_off)

        if target_date_str and str(target_date_str).strip() in str(col):
            target_idx = idx

    if target_idx is not None:
        if not work_status[target_idx]:
            return 0

        left = 0
        for i in range(target_idx - 1, -1, -1):
            if work_status[i]:
                left += 1
            else:
                break

        right = 0
        for i in range(target_idx + 1, len(work_status)):
            if work_status[i]:
                right += 1
            else:
                break

        return left + 1 + right

    max_s = 0
    curr_s = 0
    for is_w in work_status:
        if is_w:
            curr_s += 1
            if curr_s > max_s:
                max_s = curr_s
        else:
            curr_s = 0
    return max_s


# =========================================================
# 6. 班間休息與法規檢查 (Labour Rules Verification)
# =========================================================
def calculate_rest_hours(
    sign_out_str: str, next_sign_in_str: str
) -> Optional[float]:
    """精準計算 Sign-Out 至隔日 Sign-In 的實際休息小時數（修正跨日運算）"""
    if (
        not sign_out_str
        or not next_sign_in_str
        or "--:--" in (sign_out_str, next_sign_in_str)
    ):
        return None
    try:
        so_h, so_m = map(int, sign_out_str.split(":"))
        si_h, si_m = map(int, next_sign_in_str.split(":"))

        so_mins = so_h * 60 + so_m
        si_mins = si_h * 60 + si_m

        rest_mins = (24 * 60 - so_mins) + si_mins
        return round(rest_mins / 60.0, 1)
    except Exception:
        return None


def check_shift_legality(
    crew_row: pd.Series, target_col_idx: int, all_cols: Any
) -> Tuple[bool, str, Dict[str, Any]]:
    """檢驗指定日期的換班前後班間休息間隔是否合乎法令規範"""
    window_start = max(2, target_col_idx - 6)
    window_end = min(len(all_cols) - 1, target_col_idx + 6)

    eleven_hour_count = 0
    min_interval_found = 99.0
    has_under_11h = False

    for idx in range(window_start, window_end):
        if idx + 1 >= len(all_cols):
            break

        c1 = parse_cell(crew_row.iloc[idx])
        c2 = parse_cell(crew_row.iloc[idx + 1])

        if (
            c1.get("end")
            and c2.get("start")
            and not is_cell_off_day(crew_row.iloc[idx])
            and not is_cell_off_day(crew_row.iloc[idx + 1])
        ):
            rest_h = calculate_rest_hours(c1["end"], c2["start"])
            if rest_h is not None:
                if rest_h < min_interval_found:
                    min_interval_found = rest_h

                if rest_h < 11.0:
                    has_under_11h = True
                elif 11.0 <= rest_h < 12.0:
                    eleven_hour_count += 1

    illegal_reasons: List[str] = []
    if has_under_11h:
        illegal_reasons.append(f"班間隔不足 11 小時 (最低 {min_interval_found}h)")
    if eleven_hour_count > 1:
        illegal_reasons.append(
            f"7 天內出現 {eleven_hour_count} 次 11~12 小時班間隔 (限 1 次)"
        )

    is_legal = len(illegal_reasons) == 0
    warning_msg = "；".join(illegal_reasons) if illegal_reasons else ""

    return is_legal, warning_msg, {
        "min_interval": (
            min_interval_found if min_interval_found != 99.0 else None
        ),
        "eleven_hr_cnt": eleven_hour_count,
    }


def check_week_has_holiday(
    target_date_str: str, date_cols: List[str], columns: Optional[Any] = None
) -> Tuple[bool, str]:
    """檢查指定日期所在當週 (Sun~Sat) 是否包含國定假日或備註假日"""
    try:
        current_year = datetime.now().year
        t_m, t_d = map(int, target_date_str.split("/"))
        t_dt = date(current_year, t_m, t_d)
        t_sun = t_dt - timedelta(days=(t_dt.weekday() + 1) % 7)
        t_sat = t_sun + timedelta(days=6)
        week_str = (
            f"{t_sun.month}/{t_sun.day:02d} (日) ~ {t_sat.month}/{t_sat.day:02d} (六)"
        )

        for d_str in date_cols:
            try:
                d_m, d_d = map(int, d_str.split("/"))
                d_dt = date(current_year, d_m, d_d)
                if t_sun <= d_dt <= t_sat:
                    if d_str in NATIONAL_HOLIDAYS:
                        return True, week_str
                    if columns is not None:
                        matching_col = next(
                            (c for c in columns[2:] if d_str in str(c)), None
                        )
                        if matching_col and re.search(
                            r"[\(（]([^\)）]+)[\)）]", str(matching_col)
                        ):
                            return True, week_str
            except Exception:
                pass
        return False, week_str
    except Exception:
        return False, ""
