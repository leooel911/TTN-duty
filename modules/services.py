import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from config import DATA_DIR, SYSTEM_CONFIG_FILE, UNITS, WHITELIST_FILE
from modules.utils import get_employee_name, safe_read_excel

DEFAULT_CONFIG: Dict[str, Any] = {
    "vip_pass_code": "0900",
    "crew_pass_code": "0096",
    "vip_password": "0900",
    "user_password": "0096",
    "admin_password": "Lf090000",
    "empty_shift_label": "--",
    "default_emp_id": "A",
    "enable_whitelist": True,
    "strict_streak_limit": 6,
    "announcement": "目前為內部測試階段｜本頁面可聯繫後台管理者",
    "enable_beta_notice": True,
}


def load_system_config() -> Dict[str, Any]:
    """載入系統動態參數設定，若檔案不存在則自動建立"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SYSTEM_CONFIG_FILE):
        save_system_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(SYSTEM_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                config.setdefault(k, v)
            return config
    except Exception:
        return DEFAULT_CONFIG


def save_system_config(config_dict: Dict[str, Any]) -> bool:
    """儲存系統動態參數設定至 DATA_DIR/system_config.json"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SYSTEM_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error saving system config: {e}")
        return False


def load_whitelist(unit_code: str = "TTN") -> Dict[str, Any]:
    """讀取指定營運單位的白名單"""
    whitelist_path = WHITELIST_FILE
    full_data: Dict[str, Any] = {}

    if os.path.exists(whitelist_path):
        try:
            with open(whitelist_path, "r", encoding="utf-8") as f:
                full_data = json.load(f)
                if full_data and not any(k in UNITS for k in full_data.keys()):
                    full_data = {u: full_data.copy() for u in UNITS.keys()}
        except Exception:
            full_data = {}

    if unit_code not in full_data:
        unit_default: Dict[str, Any] = {
            "ADMIN": {
                "name": f"[{unit_code}] 系統管理員",
                "role": "ADMIN",
                "note": f"[{unit_code}] 預設管理員帳號",
                "created_at": datetime.now().strftime("%Y-%m-%d"),
            }
        }
        full_data[unit_code] = unit_default

    raw_unit_data = full_data.get(unit_code, {})
    normalized_data = {}
    for uid, info in raw_unit_data.items():
        normalized_data[str(uid).strip().upper()] = info

    return normalized_data


def is_user_allowed(selected_unit: str, emp_id: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """檢查員編是否在指定單位的白名單內或具有全域通行權限"""
    emp_id_str = str(emp_id).strip().upper()

    if emp_id_str == "A":
        return True, {
            "emp_id": "A",
            "name": "全域通行",
            "role": "VIP_USER",
            "status": "啟用",
        }

    unit_whitelist = load_whitelist(selected_unit)
    if emp_id_str in unit_whitelist:
        u_info = unit_whitelist[emp_id_str]
        return True, {
            "emp_id": emp_id_str,
            "name": u_info.get("name", u_info.get("姓名", "組員")),
            "role": u_info.get("role", u_info.get("身份", "TESTER")),
            "status": "啟用",
        }

    for u_code in UNITS.keys():
        if u_code != selected_unit:
            other_wl = load_whitelist(u_code)
            if emp_id_str in other_wl:
                other_info = other_wl[emp_id_str]
                role_str = str(other_info.get("role", "")).upper()
                if "VIP" in role_str or role_str == "ADMIN":
                    return True, {
                        "emp_id": emp_id_str,
                        "name": other_info.get("name", "全域通行"),
                        "role": other_info.get("role", "VIP_USER"),
                        "status": "啟用",
                    }

    return False, None


def get_current_role_files() -> Dict[str, Any]:
    """取得目前所屬單位的各大表檔案路徑字典"""
    current_unit = st.session_state.get("current_unit", "TTN")
    return UNITS.get(current_unit, UNITS.get("TTN", {}))


def get_schedule_range() -> str:
    """取得當前班表涵蓋的時間區間範圍"""
    role_files = get_current_role_files()
    for path in role_files.values():
        if isinstance(path, str) and os.path.exists(path):
            try:
                df = safe_read_excel(path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                date_cols = [
                    re.search(r"(\d+/\d+)", str(c)).group(1)
                    for c in df.columns[2:]
                    if re.search(r"(\d+/\d+)", str(c))
                ]
                if date_cols:
                    return f"{date_cols[0]} ~ {date_cols[-1]}"
            except Exception:
                pass
    start_dt = datetime.now().replace(day=1)
    end_dt = start_dt + timedelta(days=29)
    return f"{start_dt.strftime('%Y/%m/%d')} ~ {end_dt.strftime('%Y/%m/%d')}"


def verify_crew_membership(selected_unit: str, emp_id: str) -> bool:
    """驗證組員是否屬於指定單位"""
    emp_id_str = str(emp_id).strip().upper()

    wl = load_whitelist(selected_unit)
    if emp_id_str in wl:
        return True

    unit_files = UNITS.get(selected_unit, {})
    for role_name, file_path in unit_files.items():
        if isinstance(file_path, str) and os.path.exists(file_path):
            try:
                df = safe_read_excel(file_path, header=3)
                for _, row in df.iterrows():
                    r_id = str(row.iloc[0]).strip().upper()
                    if r_id == emp_id_str:
                        return True
            except Exception:
                pass
    return False


def process_file_data(
    target_emp: str,
) -> Tuple[datetime, List[str], str, str, List[str]]:
    """真實讀取 Excel 大表，解析指定組員的班表儲存格資料"""
    target_emp_str = str(target_emp).strip().upper()
    current_unit = st.session_state.get("current_unit", "TTN")
    role_files = get_current_role_files()

    found_row = None
    found_df = None
    emp_id = target_emp_str
    emp_name = ""

    for role, path in role_files.items():
        if isinstance(path, str) and os.path.exists(path):
            try:
                df = safe_read_excel(path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    r_id = str(row.iloc[0]).strip().upper()
                    r_name = str(row.iloc[1]).strip().upper()
                    if r_id == target_emp_str or r_name == target_emp_str:
                        found_row = row
                        found_df = df
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()
                        break
                if found_row is not None:
                    break
            except Exception:
                pass

    if found_row is None:
        raise ValueError(
            f"在 [{current_unit}] 大表中找不到員編或姓名：{target_emp}"
        )

    all_cols = list(found_df.columns)
    dates: List[str] = []
    date_col_indices: List[int] = []
    start_dt: Optional[datetime] = None
    current_year = datetime.now().year

    for idx in range(2, len(all_cols)):
        col_name = str(all_cols[idx]).strip()
        m = re.search(r"(\d+/\d+)", col_name)
        if m:
            d_str = m.group(1)
            dates.append(d_str)
            date_col_indices.append(idx)
            if start_dt is None:
                try:
                    m_val, d_val = map(int, d_str.split("/"))
                    start_dt = datetime(current_year, m_val, d_val)
                except Exception:
                    pass

    if start_dt is None:
        start_dt = datetime.now().replace(day=1)

    cells: List[str] = []
    for col_idx in date_col_indices:
        if col_idx < len(found_row):
            cell_val = found_row.iloc[col_idx]
            cells.append("" if pd.isna(cell_val) else str(cell_val).strip())
        else:
            cells.append("")

    return start_dt, dates, emp_id, emp_name, cells
