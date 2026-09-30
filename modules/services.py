import json
import os
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
import subprocess
import glob

import pandas as pd
import streamlit as st
from config import DATA_DIR, UNITS, WHITELIST_FILE
from modules.utils import normalize_date_str, parse_cell, safe_read_excel


def auto_git_push_data(commit_msg="Auto update data via admin panel"):
    """自動將 data/ 變更推送至雙重 GitHub 專案，防止雲端重置清空"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if "modules" in script_dir:
            script_dir = os.path.dirname(script_dir)
        os.chdir(script_dir)
        
        subprocess.run(["git", "add", "data/"], check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], check=False)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        subprocess.run(["git", "push", "ttn", "main"], check=True)
    except Exception as e:
        print(f"Git auto-sync error: {e}")


def get_available_months() -> List[str]:
    """自動掃描 data/ 單位子資料夾下的「最新版班表」與內部欄位，抓取所有可用的月份（格式: YYYY-MM）"""
    current_unit = st.session_state.get("current_unit", "TTN")
    unit_files = UNITS.get(current_unit, UNITS.get("TTN", {}))
    
    months = set()
    current_year = date.today().year
    
    # 1. 優先掃描新架構的資料夾：data/{current_unit}/最新版班表/{YYYY-MM}/
    new_style_dir = os.path.join(DATA_DIR, current_unit, "最新版班表")
    if os.path.exists(new_style_dir):
        for sub_name in os.listdir(new_style_dir):
            if re.match(r"^\d{4}-\d{2}$", sub_name):
                sub_path = os.path.join(new_style_dir, sub_name)
                if os.path.isdir(sub_path) and os.listdir(sub_path):
                    months.add(sub_name)
    
    # 2. 相容舊版從檔名中解析月份代碼
    all_files = glob.glob(os.path.join(DATA_DIR, f"{current_unit}*.xlsx"))
    for f in all_files:
        filename = os.path.basename(f)
        match_6 = re.search(r"_(\d{6})_", filename)
        if match_6:
            ym = match_6.group(1)
            months.add(f"{ym[:4]}-{ym[4:]}")
            continue
        match_2 = re.search(r"(\d{2})\.xlsx$", filename)
        if match_2:
            m_str = match_2.group(1)
            if m_str.isdigit() and 1 <= int(m_str) <= 12:
                months.add(f"{current_year}-{m_str}")
                
    # 3. 從 Excel 檔案內部日期欄位掃描
    if isinstance(unit_files, dict):
        for role_name, default_path in unit_files.items():
            pattern = os.path.join(DATA_DIR, f"{current_unit}*{role_name}*.xlsx")
            matched_files = glob.glob(pattern)
            
            if not matched_files and isinstance(default_path, str) and default_path and os.path.exists(default_path):
                matched_files = [default_path]
                
            for f_path in matched_files:
                if f_path and isinstance(f_path, str) and os.path.exists(f_path) and os.path.getsize(f_path) > 0:
                    try:
                        df = safe_read_excel(f_path, header=3)
                        df.columns = [str(c).strip() for c in df.columns]
                        for col in df.columns[2:]:
                            norm_d = normalize_date_str(col)
                            if norm_d and "/" in norm_d:
                                parts = norm_d.split("/")
                                if parts[0].isdigit():
                                    m = int(parts[0])
                                    months.add(f"{current_year}-{m:02d}")
                    except Exception:
                        continue
                    
    sorted_months = sorted(list(months), reverse=True)
    if not sorted_months:
        current_ym = date.today().strftime("%Y-%m")
        return [current_ym]
    return sorted_months


def get_current_role_files(target_month: Optional[str] = None) -> Dict[str, str]:
    """根據當前單位與指定的月份，動態對應並回傳對應的職位班表檔案路徑（完整支援新舊資料夾架構）"""
    current_unit = st.session_state.get("current_unit", "TTN")
    
    if not target_month:
        target_month = st.session_state.get("current_query_month")
        if not target_month:
            available = get_available_months()
            target_month = available[0] if available else date.today().strftime("%Y-%m")
            
    role_to_pos = {"駕駛": "TD", "列車長": "TM", "服勤員": "TA"}
    default_files = UNITS.get(current_unit, UNITS.get("TTN", {}))
    
    result = {}
    for role, default_path in default_files.items():
        selected_path = ""
        pos = role_to_pos.get(role, "")
        
        # 1. 優先尋找新架構路徑：data/{current_unit}/最新版班表/{target_month}/{current_unit}_{pos}.xlsx
        if pos:
            new_path = os.path.join(DATA_DIR, current_unit, "最新版班表", target_month, f"{current_unit}_{pos}.xlsx")
            if os.path.exists(new_path) and os.path.getsize(new_path) > 0:
                selected_path = new_path
                
        # 2. 若找不到，嘗試舊版命名規則與備用路徑
        if not selected_path:
            clean_month = target_month.replace("-", "")
            short_month = clean_month[-2:]
            keywords = [pos, role] if pos else [role]
            
            for kw in keywords:
                possible_patterns = [
                    os.path.join(DATA_DIR, f"{current_unit}{kw}{short_month}.xlsx"),
                    os.path.join(DATA_DIR, f"{current_unit}_{kw}_{short_month}.xlsx"),
                    os.path.join(DATA_DIR, f"{current_unit}_{clean_month}_{role}.xlsx"),
                    os.path.join(DATA_DIR, f"{current_unit}_{role}.xlsx"),
                ]
                for p in possible_patterns:
                    if os.path.exists(p) and os.path.getsize(p) > 0:
                        selected_path = p
                        break
                if selected_path:
                    break
                    
        if not selected_path:
            if isinstance(default_path, str) and os.path.exists(default_path) and os.path.getsize(default_path) > 0:
                selected_path = default_path
                
        result[role] = selected_path
        
    return result


def get_schedule_range() -> str:
    unit_files = get_current_role_files()
    for role_name in ["駕駛", "列車長", "服勤員"]:
        f_path = unit_files.get(role_name, "")
        if f_path and isinstance(f_path, str) and os.path.exists(f_path) and os.path.getsize(f_path) > 0:
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
    clean_keyword = emp_input.strip().upper()
    unit_files = get_current_role_files()
    
    target_row = None
    target_columns = None
    
    for role_name in ["駕駛", "列車長", "服勤員"]:
        f_path = unit_files.get(role_name, "")
        if f_path and isinstance(f_path, str) and os.path.exists(f_path) and os.path.getsize(f_path) > 0:
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
        raise ValueError(f"在當前選定月份的大表中找不到符合關鍵字【{emp_input}】的組員資料！")

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


def load_system_config() -> Dict[str, Any]:
    config_path = os.path.join(DATA_DIR, "system_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "admin_password": "Lf090000",
        "vip_password": "0",
        "user_password": "09000",
        "strict_streak_limit": 6,
        "enable_beta_notice": True,
        "announcement": "目前為內部測試階段｜本頁面末端可聯繫管理者",
        "enable_strict_test_mode": False,
        "strict_allowed_employees": [],
    }


def save_system_config(cfg: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    config_path = os.path.join(DATA_DIR, "system_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    auto_git_push_data("Auto-update system config")


def load_whitelist(unit_code: str = "TTN") -> Dict[str, Any]:
    """優先讀取獨立的單位白名單檔案 (whitelist_ttn.json)，並相容舊版共用檔"""
    os.makedirs(DATA_DIR, exist_ok=True)
    unit_path = os.path.join(DATA_DIR, f"whitelist_{unit_code.lower()}.json")
    if os.path.exists(unit_path):
        try:
            with open(unit_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    return content
        except Exception:
            pass

    wl_path = os.path.join(DATA_DIR, WHITELIST_FILE)
    if os.path.exists(wl_path):
        try:
            with open(wl_path, "r", encoding="utf-8") as f:
                all_wl = json.load(f)
                if isinstance(all_wl, dict):
                    if unit_code in all_wl:
                        return all_wl.get(unit_code, {})
                    return all_wl
        except Exception:
            pass
    return {}


def save_whitelist(unit_code: str, unit_data: Dict[str, Any]) -> None:
    """直接儲存至該單位的獨立白名單檔案中"""
    os.makedirs(DATA_DIR, exist_ok=True)
    unit_path = os.path.join(DATA_DIR, f"whitelist_{unit_code.lower()}.json")
    try:
        with open(unit_path, "w", encoding="utf-8") as f:
            json.dump(unit_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"儲存白名單失敗: {e}")
    
    auto_git_push_data(f"Auto-update whitelist for {unit_code}")


def check_excel_employee_exists(unit_code: str, emp_id: str) -> Tuple[bool, str]:
    clean_id = emp_id.strip().upper()
    if clean_id.isdigit() and len(clean_id) == 6:
        clean_id = f"A{clean_id}"

    unit_files = get_current_role_files()
    for role_name in ["駕駛", "列車長", "服勤員"]:
        f_path = unit_files.get(role_name, "")
        if f_path and isinstance(f_path, str) and os.path.exists(f_path) and os.path.getsize(f_path) > 0:
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
    clean_id = emp_id.strip().upper()
    if not clean_id or clean_id == "A":
        return False, ""

    if clean_id.isdigit() and len(clean_id) == 6:
        clean_id = f"A{clean_id}"

    sys_config = load_system_config()
    strict_mode = sys_config.get("enable_strict_test_mode", False)
    allowed_list = sys_config.get("strict_allowed_employees", [])

    if strict_mode:
        if clean_id not in allowed_list and clean_id != "ADMIN":
            return False, ""

    whitelist = load_whitelist(unit_code)
    if clean_id in whitelist:
        info = whitelist[clean_id]
        name = info.get("name", info.get("姓名", "")) if isinstance(info, dict) else str(info)
        return True, name or "白名單組員"

    return check_excel_employee_exists(unit_code, clean_id)


def get_employee_name(unit_code: str, emp_id: str) -> str:
    exists, name = verify_employee_exists(unit_code, emp_id)
    return name if exists else ""


def authenticate_user(unit_code: str, emp_id_input: str, passcode_input: str) -> Tuple[bool, str, Dict[str, Any]]:
    clean_id = emp_id_input.strip().upper()
    if clean_id.isdigit() and len(clean_id) == 6:
        clean_id = f"A{clean_id}"

    passcode = passcode_input.strip()

    sys_config = load_system_config()
    admin_pwd = sys_config.get("admin_password", "Lf090000")
    default_vip_pwd = sys_config.get("vip_password", "0")
    user_pwd = sys_config.get("user_password", "09000")

    strict_mode = sys_config.get("enable_strict_test_mode", False)
    allowed_list = sys_config.get("strict_allowed_employees", [])

    whitelist = load_whitelist(unit_code)
    wl_info = whitelist.get(clean_id, {})
    wl_name = ""
    wl_role = "USER"
    custom_pass = ""

    if isinstance(wl_info, dict):
        wl_name = wl_info.get("name") or wl_info.get("姓名") or ""
        wl_role = wl_info.get("role", "VIP_USER")
        custom_pass = str(wl_info.get("passcode", "")).strip()
    elif isinstance(wl_info, str):
        wl_name = wl_info.strip()

    if passcode == admin_pwd or wl_role == "ADMIN":
        if passcode != admin_pwd:
            return False, "管理員密碼錯誤！", {"reason": "WRONG_ADMIN_PASSWORD"}
        return True, "歡迎系統管理員！", {
            "authenticated": True,
            "emp_id": clean_id if clean_id and clean_id != "A" else "ADMIN",
            "emp_name": wl_name or "系統管理員",
            "role": "ADMIN",
            "unit": unit_code,
        }

    if strict_mode:
        if clean_id not in allowed_list and clean_id != "ADMIN":
            return False, "目前系統處於測試管制期間，您的員編尚未開放測試權限！", {"reason": "STRICT_MODE_BLOCKED"}

    if clean_id in whitelist and wl_role in ["VIP_USER", "TESTER"]:
        if custom_pass and custom_pass != "-":
            if passcode == custom_pass:
                return True, f"歡迎 VIP 組員【{wl_name}】！", {
                    "authenticated": True, "emp_id": clean_id, "emp_name": wl_name, "role": wl_role, "unit": unit_code,
                }
            else:
                return False, "授權碼無效！請再次確認:", {"reason": "WRONG_VIP_PASSCODE"}

        if passcode == default_vip_pwd or passcode == "0" or passcode == user_pwd or passcode == "09000":
            return True, f"歡迎 VIP 組員【{wl_name}】！", {
                "authenticated": True, "emp_id": clean_id, "emp_name": wl_name, "role": wl_role, "unit": unit_code,
            }
        else:
            return False, "授權碼無效！請再次確認:", {"reason": "WRONG_PASSCODE"}

    if clean_id == "A" and (passcode in [default_vip_pwd, "0", user_pwd, "09000"]):
        return True, "歡迎 VIP 測試員！", {
            "authenticated": True, "emp_id": "VIP001", "emp_name": "VIP 測試員", "role": "VIP_USER", "unit": unit_code,
        }

    if not clean_id or clean_id == "A":
        return False, "一般組員請輸入正確員編（例如:A023300）！", {"reason": "INVALID_EMP_ID"}

    exists_in_excel, excel_name = check_excel_employee_exists(unit_code, clean_id)
    if not exists_in_excel and clean_id not in whitelist:
        return False, f"員編【{clean_id}】未在【{unit_code}】目前選定月份的班表大表中找到，請核對所屬單位或切換查詢月份！", {"reason": "NOT_IN_EXCEL"}

    if passcode != user_pwd and passcode != "09000":
        return False, "授權碼無效！請再次確認:", {"reason": "WRONG_PASSCODE"}

    final_name = wl_name if wl_name else excel_name
    return True, f"歡迎！{final_name}", {
        "authenticated": True, "emp_id": clean_id, "emp_name": final_name, "role": "USER", "unit": unit_code,
    }


def is_user_allowed(first_arg: str, second_arg: str = "TTN") -> Tuple[bool, Any]:
    if first_arg in ["TTN", "KSH", "TCH"]:
        unit_code, emp_id = first_arg, second_arg
    else:
        emp_id, unit_code = first_arg, second_arg
    return verify_employee_exists(unit_code, emp_id)


def verify_crew_membership(first_arg: str, second_arg: str = "TTN") -> Tuple[bool, Any]:
    if first_arg in ["TTN", "TTC", "TTS"]:
        unit_code, emp_id = first_arg, second_arg
    else:
        emp_id, unit_code = first_arg, second_arg
    return verify_employee_exists(unit_code, emp_id)
