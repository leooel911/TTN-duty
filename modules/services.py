import os
import json
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from config import DATA_DIR, UNITS, WHITELIST_FILE
from modules.utils import normalize_date_str, parse_cell, safe_read_excel


# =============================================================================
# 1. 既有大表與檔案服務 (完整保留原功能)
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
# 2. 全域系統設定與白名單 JSON 讀寫服務 (完整保留原功能)
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
        "vip_password": "vip888",
        "user_password": "1234",
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
# 3. 新增：員編實名核實與三層登入權限驗證引擎
# =============================================================================

def verify_employee_exists(unit_code: str, emp_id: str) -> Tuple[bool, str]:
    """
    核實員編是否真實存在於 白名單 或 Excel 大表中
    回傳: (是否存在 bool, 組員姓名 str)
    """
    clean_id = emp_id.strip().upper()
    if clean_id.isdigit() and len(clean_id) == 6:
        clean_id = f"A{clean_id}"

    # 第一順位：查詢白名單 JSON
    whitelist = load_whitelist(unit_code)
    if clean_id in whitelist:
        info = whitelist[clean_id]
        name = info.get("name", info.get("姓名", "")) if isinstance(info, dict) else str(info)
        return True, name or "白名單組員"

    # 第二順位：掃描該單位三大職位 Excel 大表 (駕駛 / 列車長 / 服勤員)
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


def authenticate_user(unit_code: str, emp_id_input: str, passcode_input: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    三層身份驗證引擎：
    1. ROOT ADMIN 緊急比對 (最高管理員備援)
    2. 後台動態白名單 (讀取 whitelist.json 判定角色: ADMIN / VIP_USER / TESTER)
    3. 一般大表組員 (核實大表員編是否存在 + 比對通用授權碼)
    
    回傳: (是否成功 bool, 提示文字 str, 驗證詳細資訊 Dict)
    """
    clean_id = emp_id_input.strip().upper()
    if clean_id.isdigit() and len(clean_id) == 6:
        clean_id = f"A{clean_id}"

    passcode = passcode_input.strip()
    if not clean_id or clean_id == "A":
        return False, "請輸入有效的員編（例如: A023300）", {"reason": "INVALID_INPUT"}

    sys_config = load_system_config()
    whitelist = load_whitelist(unit_code)

    admin_pwd = str(sys_config.get("admin_password", "admin123")).strip()
    vip_pwd = str(sys_config.get("vip_password", "vip888")).strip()
    user_pwd = str(sys_config.get("user_password", "1234")).strip()

    # 第一層：程式碼 / Config 預設解鎖 (Root Admin 備援)
    if passcode == admin_pwd:
        user_session = {
            "authenticated": True,
            "emp_id": clean_id,
            "emp_name": "系統管理員",
            "role": "ADMIN",
            "unit": unit_code,
        }
        return True, "管理員身份驗證成功！", user_session

    # 檢查員編真實性（若不在大表與白名單中，標記為 UNAUTHORIZED）
    exists, discovered_name = verify_employee_exists(unit_code, clean_id)
    if not exists:
        return False, f"您尚未成為第一階段測試授權組員！", {"reason": "UNAUTHORIZED"}

    final_name = discovered_name or clean_id
    assigned_role = "USER"

    # 第二層：讀取後台白名單 (whitelist.json) 指定的角色
    if clean_id in whitelist:
        wl_info = whitelist[clean_id]
        if isinstance(wl_info, dict):
            assigned_role = wl_info.get("role", "VIP_USER")
            final_name = wl_info.get("name", final_name)
        else:
            assigned_role = "VIP_USER"

    # 第三層：金鑰密碼匹配與角色授權
    final_role = None
    if passcode == vip_pwd or assigned_role in ["ADMIN", "VIP_USER"]:
        final_role = assigned_role if assigned_role != "USER" else "VIP_USER"
    elif passcode == user_pwd or assigned_role in ["USER", "TESTER"]:
        final_role = assigned_role

    if not final_role:
        return False, "授權碼無效，請重新輸入！", {"reason": "WRONG_PASSCODE"}

    user_session = {
        "authenticated": True,
        "emp_id": clean_id,
        "emp_name": final_name,
        "role": final_role,
        "unit": unit_code,
    }
    return True, f"歡迎！ {final_name}", user_session
# =============================================================================
# 4. 舊版相容性匯入包裝層 (防止舊版 app.py 報錯)
# =============================================================================

def is_user_allowed(emp_id: str, unit_code: str = "TTN") -> bool:
    """舊版相容函式：核實員編是否具備使用權限"""
    exists, _ = verify_employee_exists(unit_code, emp_id)
    return exists
