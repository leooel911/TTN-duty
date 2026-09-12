import json
import os
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from config import DATA_DIR, UNITS, WHITELIST_FILE
from modules.utils import normalize_date_str, parse_cell, safe_read_excel


# =============================================================================
# 1. 既有大表與檔案服務
# =============================================================================

def get_current_role_files() -> Dict[str, str]:
    """取得當前選擇單位的各大表檔案路徑"""
    current_unit = st.session_state.get("current_unit", "TTN")
    return UNITS.get(current_unit, UNITS.get("TTN", {}))


def get_schedule_range() -> str:
    """自動從當前大表中解析出排班週期範圍（例如：09/01 ~ 09/30）"""
    unit_files = get_current_role_files()
    for role_name in ["駕駛", "列車長", "服勤員"]:
        f_path = unit_files.get(role_name, "")
        if f_path and os.path.exists(f_path) and os.path.getsize(f_path) > 0:
            try:
                df = safe_read_excel(f_path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                date_cols = [
                    normalize_date_str(col)
                    for col in df.columns[2:]
                    if normalize_date_str(col)
                ]
                if date_cols:
                    return f"{date_cols[0]} ~ {date_cols[-1]}"
            except Exception:
                continue
    return "無有效日期數據"


def process_file_data(emp_input: str) -> Tuple[datetime, List[str], str, str, List[Dict[str, Any]]]:
    """
    掃描三大大表，解析指定員編/姓名之完整月班表資料
    回傳: (開始日期物件, 日期標籤清單, 解析員編, 解析姓名, 格子解析資料列表)
    """
    clean_keyword = emp_input.strip().upper()
    unit_files = get_current_role_files()
    
    target_row = None
    target_columns = None
    
    for role_name in ["駕駛", "列車長", "服勤員"]:
        f_path = unit_files.get(role_name, "")
        if f_path and os.path.exists(f_path) and os.path.getsize(f_path) > 0:
            try:
                df = safe_read_excel(f_path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    row_id = str(row.iloc[0]).strip().upper()
                    row_name = str(row.iloc[1]).strip()
                    if clean_keyword in [row_id, row_name, f"A{clean_keyword}"]:
                        target_row = row
                        target_columns = df.columns
                        break
            except Exception:
                continue
        if target_row is not None:
            break

    if target_row is None:
        raise ValueError(f"在當前大表中找不到符合關鍵字【{emp_input}】的組員資料！")

    emp_id = str(target_row.iloc[0]).strip().upper()
    emp_name = str(target_row.iloc[1]).strip()
    
    dates = []
    cells = []
    current_year = date.today().year

    for idx in range(2, len(target_columns)):
        col_raw = str(target_columns[idx])
        norm_d = normalize_date_str(col_raw)
        if not norm_d:
            continue
        dates.append(norm_d)
        cell_val = target_row.iloc[idx] if idx < len(target_row) else ""
        parsed = parse_cell(cell_val)
        cells.append(parsed)

    first_m, first_d = map(int, dates[0].split("/"))
    start_dt = datetime(current_year, first_m, first_d)

    return start_dt, dates, emp_id, emp_name, cells


# =============================================================================
# 2. 全域系統設定與白名單 JSON 讀寫服務
# =============================================================================

def load_system_config() -> Dict[str, Any]:
    """讀取全域系統設定檔 (system_config.json)"""
    config_path = os.path.join(DATA_DIR, "system_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "admin_password": "admin123",
        "vip_password": "0",       # 高級 VIP 快捷授權碼：0
        "user_password": "09000",   # 一般組員預設授權碼：09000
        "strict_streak_limit": 6,
        "enable_beta_notice": True,
        "announcement": "目前為內部測試階段｜本頁面可聯繫後台管理者",
    }


def save_system_config(cfg: Dict[str, Any]) -> None:
    """寫入全域系統設定檔"""
    os.makedirs(DATA_DIR, exist_ok=True)
    config_path = os.path.join(DATA_DIR, "system_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_whitelist(unit_code: str = "TTN") -> Dict[str, Any]:
    """讀取指定單位的白名單 (whitelist.json)"""
    wl_path = os.path.join(DATA_DIR, WHITELIST_FILE)
    if os.path.exists(wl_path):
        try:
            with open(wl_path, "r", encoding="utf-8") as f:
                all_wl = json.load(f)
                return all_wl.get(unit_code, {})
        except Exception:
            pass
    return {}


def save_whitelist(unit_code: str, unit_data: Dict[str, Any]) -> None:
    """寫入指定單位的白名單"""
    os.makedirs(DATA_DIR, exist_ok=True)
    wl_path = os.path.join(DATA_DIR, WHITELIST_FILE)
    all_wl = {}
    if os.path.exists(wl_path):
        try:
            with open(wl_path, "r", encoding="utf-8") as f:
                all_wl = json.load(f)
        except Exception:
            all_wl = {}
    
    all_wl[unit_code] = unit_data
    with open(wl_path, "w", encoding="utf-8") as f:
        json.dump(all_wl, f, ensure_ascii=False, indent=2)


# =============================================================================
# 3. 員編實名核實與雙軌驗證引擎
# =============================================================================

def check_excel_employee_exists(unit_code: str, emp_id: str) -> Tuple[bool, str]:
    """專門檢查員編是否真實存在於 Excel 班表大表中"""
    clean_id = emp_id.strip().upper()
    if clean_id.isdigit() and len(clean_id) == 6:
        clean_id = f"A{clean_id}"

    unit_files = UNITS.get(unit_code, {})
    for role_name in ["駕駛", "列車長", "服勤員"]:
        f_path = unit_files.get(role_name, "")
        if f_path and os.path.exists(f_path) and os.path.getsize(f_path) > 0:
            try:
                df = safe_read_excel(f_path, header=3)
                for _, row in df.iterrows():
                    row_id = str(row.iloc[0]).strip().upper()
                    if row_id == clean_id:
                        row_name = str(row.iloc[1]).strip()
                        return True, row_name
            except Exception:
                continue
    return False, ""


def verify_employee_exists(unit_code: str, emp_id: str) -> Tuple[bool, str]:
    """核實員編是否真實存在（白名單或 Excel）"""
    clean_id = emp_id.strip().upper()
    if not clean_id or clean_id == "A":
        return False, ""

    if clean_id.isdigit() and len(clean_id) == 6:
        clean_id = f"A{clean_id}"

    whitelist = load_whitelist(unit_code)
    if clean_id in whitelist:
        info = whitelist[clean_id]
        name = info.get("name", info.get("姓名", "")) if isinstance(info, dict) else str(info)
        return True, name or "白名單組員"

    return check_excel_employee_exists(unit_code, clean_id)


def get_employee_name(unit_code: str, emp_id: str) -> str:
    """依據單位與員編查找組員姓名"""
    exists, name = verify_employee_exists(unit_code, emp_id)
    return name if exists else ""


def authenticate_user(unit_code: str, emp_id_input: str, passcode_input: str) -> Tuple[bool, str, Dict[str, Any]]:
    """雙軌登入驗證引擎（優先套用白名單「姓名」欄位）"""
    clean_id = emp_id_input.strip().upper()
    if clean_id.isdigit() and len(clean_id) == 6:
        clean_id = f"A{clean_id}"

    passcode = passcode_input.strip()

    sys_config = load_system_config()
    admin_pwd = sys_config.get("admin_password", "admin123")
    default_vip_pwd = sys_config.get("vip_password", "0")
    user_pwd = sys_config.get("user_password", "09000")

    whitelist = load_whitelist(unit_code)

    # 先嘗試抓取白名單中對應員編的「姓名」
    wl_name = ""
    if clean_id in whitelist:
        w_info = whitelist[clean_id]
        if isinstance(w_info, dict):
            wl_name = w_info.get("name") or w_info.get("姓名") or ""
        elif isinstance(w_info, str):
            wl_name = w_info.strip()

    # -------------------------------------------------------------------------
    # 軌道一：高級 VIP / 特權測試員驗證
    # -------------------------------------------------------------------------

    # 1. 最高系統管理員 (ADMIN)
    if passcode == admin_pwd:
        return True, "歡迎系統管理員！", {
            "authenticated": True,
            "emp_id": clean_id if clean_id and clean_id != "A" else "ADMIN",
            "emp_name": wl_name or "系統管理員",
            "role": "ADMIN",
            "unit": unit_code,
        }

    # 2. 比對白名單中的「客製化獨立 VIP 登入碼」
    for w_id, w_info in whitelist.items():
        if isinstance(w_info, dict):
            custom_pass = str(w_info.get("passcode", "")).strip()
            w_role = w_info.get("role", "VIP_USER")
            if custom_pass and custom_pass == passcode and w_role in ["ADMIN", "VIP_USER"]:
                v_name = w_info.get("name") or w_info.get("姓名") or w_id
                return True, f"歡迎 VIP 特權組員【{v_name}】！", {
                    "authenticated": True,
                    "emp_id": w_id,
                    "emp_name": v_name,
                    "role": w_role,
                    "unit": unit_code,
                }

    # 3. 通用高級 VIP 測試員 (輸入授權碼 0 登入)
    if passcode == default_vip_pwd or passcode == "0":
        display_name = wl_name if wl_name else ("VIP 測試員" if clean_id == "A" else clean_id)
        return True, f"歡迎 VIP 組員【{display_name}】！", {
            "authenticated": True,
            "emp_id": clean_id if clean_id else "VIP001",
            "emp_name": display_name,
            "role": "VIP_USER",
            "unit": unit_code,
        }

    # -------------------------------------------------------------------------
    # 軌道二：一般組員實名驗證 (必須為真實員編 + 大表存在 + 白名單存在 + 授權碼 09000)
    # -------------------------------------------------------------------------

    if not clean_id or clean_id == "A":
        return False, "一般組員請輸入正確員編（例如: A023300 或 023300）！", {"reason": "INVALID_EMP_ID"}

    if clean_id not in whitelist:
        return False, f"員編【{clean_id}】尚未加入【{unit_code}】白名單，無法登入！", {"reason": "NOT_IN_WHITELIST"}

    exists_in_excel, excel_name = check_excel_employee_exists(unit_code, clean_id)
    if not exists_in_excel:
        return False, f"員編【{clean_id}】未在【{unit_code}】班表大表中找到，請核對所屬單位！", {"reason": "NOT_IN_EXCEL"}

    if passcode != user_pwd and passcode != "09000":
        return False, "授權碼無效！一般組員授權碼為 09000", {"reason": "WRONG_PASSCODE"}

    final_name = wl_name if wl_name else excel_name

    return True, f"歡迎！{final_name}", {
        "authenticated": True,
        "emp_id": clean_id,
        "emp_name": final_name,
        "role": "USER",
        "unit": unit_code,
    }


# =============================================================================
# 4. 舊版相容性匯入包裝層
# =============================================================================

def is_user_allowed(first_arg: str, second_arg: str = "TTN") -> Tuple[bool, Any]:
    """舊版相容函式"""
    if first_arg in ["TTN", "KSH", "TCH"]:
        unit_code, emp_id = first_arg, second_arg
    else:
        emp_id, unit_code = first_arg, second_arg
        
    exists, info = verify_employee_exists(unit_code, emp_id)
    return exists, info


def verify_crew_membership(first_arg: str, second_arg: str = "TTN") -> Tuple[bool, Any]:
    """舊版相容函式"""
    if first_arg in ["TTN", "KSH", "TCH"]:
        unit_code, emp_id = first_arg, second_arg
    else:
        emp_id, unit_code = first_arg, second_arg
        
    return verify_employee_exists(unit_code, emp_id)
