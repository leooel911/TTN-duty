import os
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

import modules.components as comp
from config import LEAVE_CODES, NATIONAL_HOLIDAYS
from modules.drawing import render_schedule_figure
from modules.services import (
    authenticate_user,
    get_current_role_files,
    get_schedule_range,
    load_system_config,
    process_file_data,
)
from modules.utils import (
    calculate_consecutive_work_days,
    check_week_has_holiday,
    get_file_mtime_str,
    is_cell_off_day,
    is_module_maintenance,
    is_overtime,
    is_town_shift,
    log_activity,
    normalize_date_str,
    parse_cell,
    safe_read_excel,
    set_simulated_cell,
    translate_train_code,
)


# =============================================================================
# 1. 安全會話與身份授權輔助函式
# =============================================================================

AUTH_SESSION_KEY = "CURRENT_AUTH_SESSION"


def get_auth_session() -> dict:
    """取得集中管理的登入 Session 狀態"""
    if AUTH_SESSION_KEY not in st.session_state:
        st.session_state[AUTH_SESSION_KEY] = {
            "authenticated": False,
            "emp_id": "",
            "emp_name": "",
            "role": "GUEST",
            "unit": "TTN",
        }
    return st.session_state[AUTH_SESSION_KEY]


def get_login_user_id() -> str:
    """自動從登入 Session 狀態抓取員編"""
    auth = get_auth_session()
    if auth.get("authenticated"):
        return auth.get("emp_id", "")
    return ""


def clean_role_label(role: str) -> str:
    """轉換權限標籤文字"""
    mapping = {
        "ADMIN": "系統管理員",
        "VIP_USER": "VIP 特權組員",
        "TESTER": "測試員",
        "USER": "一般組員",
    }
    return mapping.get(role, role)


# =============================================================================
# 2. 資料處理與工具函式
# =============================================================================

def get_shift_group_key(code_str: str) -> str:
    """提取車次/班別的核心標識 (例: ND0007/NM0007/NF0007 均歸為 '0007', DTT -> 'DTT')"""
    s = str(code_str).strip().upper()
    nums = re.findall(r"\d+", s)
    if nums:
        return "".join(nums)
    return s


def get_shift_group_num(code_str: str) -> int:
    """提取車次/班別中的核心數字用於排序 (例: ND0007 -> 7, ND1012 -> 1012)"""
    nums = re.findall(r"\d+", str(code_str))
    if nums:
        return int("".join(nums))
    return 999999


def find_date_column_index(columns: Any, target_date: str) -> int:
    """精準匹配日期欄位索引，避免 substring 誤判與年份格式不符"""
    if columns is None:
        return -1
    target_norm = normalize_date_str(target_date)
    for idx, col in enumerate(columns):
        if idx < 2:
            continue
        if normalize_date_str(col) == target_norm:
            return idx
    return -1


def get_date_label(d_str: str, columns: Optional[Any] = None) -> str:
    """取得包含國定假日名稱的日期顯示標籤"""
    norm_d = normalize_date_str(d_str)
    holiday_name = NATIONAL_HOLIDAYS.get(norm_d) or NATIONAL_HOLIDAYS.get(d_str)
    if not holiday_name and columns is not None:
        matching_col = next((c for c in columns[2:] if norm_d and norm_d in normalize_date_str(c)), None)
        if matching_col:
            col_raw = str(matching_col)
            name_match = re.search(r"[\(（]([^\)）]+)[\)）]", col_raw)
            if name_match:
                holiday_name = name_match.group(1)

    if holiday_name:
        return f"{d_str} ({holiday_name})"
    return d_str


def get_week_holidays(target_date: str, date_cols: List[str], columns: Optional[Any] = None) -> List[str]:
    """取得當週涵蓋的所有節假日標籤清單"""
    holidays_found = []
    if not target_date or not date_cols:
        return holidays_found

    try:
        current_year = date.today().year
        norm_target = normalize_date_str(target_date)
        if not norm_target:
            return holidays_found
        t_m, t_d = map(int, norm_target.split("/"))
        t_dt = date(current_year, t_m, t_d)
        t_sun = t_dt - timedelta(days=(t_dt.weekday() + 1) % 7)
        t_sat = t_sun + timedelta(days=6)

        for d_str in date_cols:
            try:
                norm_d = normalize_date_str(d_str)
                if not norm_d:
                    continue
                d_m, d_d = map(int, norm_d.split("/"))
                d_dt = date(current_year, d_m, d_d)
                if t_sun <= d_dt <= t_sat:
                    holiday_name = NATIONAL_HOLIDAYS.get(norm_d) or NATIONAL_HOLIDAYS.get(d_str)
                    if not holiday_name and columns is not None:
                        matching_col = next(
                            (c for c in columns[2:] if norm_d in normalize_date_str(c)), None
                        )
                        if matching_col:
                            col_raw = str(matching_col)
                            name_match = re.search(r"[\(（]([^\)）]+)[\)）]", col_raw)
                            if name_match:
                                holiday_name = name_match.group(1)

                    if holiday_name:
                        label = f"{d_str} ({holiday_name})"
                        if label not in holidays_found:
                            holidays_found.append(label)
            except Exception:
                continue
    except Exception:
        pass

    return holidays_found


def reset_win_search() -> None:
    """重置換班快篩的快取資料"""
    st.session_state.pop("win_raw_candidates", None)


def reset_ex_search() -> None:
    """重置換假快篩的快取資料與搜尋狀態"""
    st.session_state["ex_search_performed"] = False
    st.session_state.pop("ex_raw_candidates", None)


# =============================================================================
# 3. 前台主入口邏輯 (純已登入主畫面)
# =============================================================================

def render_user_home() -> None:
    """繪製使用者首頁主要介面與功能模組"""

    auth = get_auth_session()
    current_user_id = auth["emp_id"]
    current_user_name = auth.get("emp_name", current_user_id)
    user_role = auth["role"]
    is_privileged = user_role in ["ADMIN", "VIP_USER"]
    is_admin_user = (user_role == "ADMIN") or st.session_state.get("admin_logged_in", False)
    current_unit_label = st.session_state.get("current_unit", auth.get("unit", "TTN"))

    st.markdown(
        """
        <style>
        html, body, .stApp, [data-testid="stAppViewContainer"], .main,
        [data-testid="stMainBlockContainer"], .block-container {
            max-width: 100vw !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }

        [data-testid="stMainBlockContainer"], .block-container {
            padding-left: 0.4rem !important;
            padding-right: 0.4rem !important;
            padding-top: 0.6rem !important;
        }

        .section-field-label {
            font-size: 15px !important;
            font-weight: 800 !important;
            color: #F8FAFC !important;
            margin-top: 10px !important;
            margin-bottom: 8px !important;
            letter-spacing: 0.3px !important;
            line-height: 1.3 !important;
        }

        div[data-testid="stWidgetLabel"] p,
        div[data-testid="stWidgetLabel"] label,
        label[data-testid="stWidgetLabel"] p {
            font-size: 15px !important;
            font-weight: 800 !important;
            color: #F8FAFC !important;
            letter-spacing: 0.3px !important;
            margin-bottom: 6px !important;
        }

        div[data-testid="stCheckbox"] {
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1.5px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 10px !important;
            padding: 8px 12px !important;
            transition: all 0.25s ease-in-out !important;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3) !important;
            margin-bottom: 6px !important;
        }

        div[data-testid="stCheckbox"]:hover {
            background: rgba(30, 41, 59, 0.8) !important;
            border-color: rgba(56, 189, 248, 0.4) !important;
        }

        div[data-testid="stCheckbox"]:has(input:checked) {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(2, 132, 199, 0.25) 100%) !important;
            border-color: #38BDF8 !important;
            box-shadow: 0 0 14px rgba(56, 189, 248, 0.35), inset 0 1px 2px rgba(255, 255, 255, 0.2) !important;
        }

        div[data-testid="stCheckbox"] input[type="checkbox"]:checked + div {
            background-color: #00A3FF !important;
            border-color: #38BDF8 !important;
        }

        div[data-testid="stCheckbox"] label p {
            font-size: 13.5px !important;
            font-weight: 700 !important;
            color: #94A3B8 !important;
            transition: color 0.2s ease !important;
        }

        div[data-testid="stCheckbox"]:has(input:checked) label p {
            color: #F8FAFC !important;
            font-weight: 800 !important;
        }

        div[data-testid="stSegmentedControl"] {
            width: 100% !important;
            max-width: 100% !important;
            margin-bottom: 12px !important;
        }

        div[data-testid="stSegmentedControl"] > div,
        div[data-testid="stSegmentedControl"] div[data-baseweb="segmented-control"],
        div[data-testid="stSegmentedControl"] div[role="radiogroup"],
        div[data-testid="stSegmentedControl"] div[role="group"] {
            display: flex !important;
            flex-direction: row !important;
            width: 100% !important;
            max-width: 100% !important;
            background: rgba(15, 23, 42, 0.8) !important;
            border: 1.5px solid rgba(56, 189, 248, 0.35) !important;
            border-radius: 12px !important;
            padding: 4px !important;
            gap: 4px !important;
            box-sizing: border-box !important;
            box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.6) !important;
        }

        div[data-testid="stSegmentedControl"] button,
        div[data-testid="stSegmentedControl"] [data-testid="stSegmentedControlOption"],
        div[data-testid="stSegmentedControl"] label {
            flex: 1 1 0% !important;
            width: 33.333% !important;
            min-width: 0 !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
            border-radius: 8px !important;
            border: none !important;
            background: transparent !important;
            color: #94A3B8 !important;
            padding: 8px 4px !important;
            margin: 0 !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: none !important;
            cursor: pointer !important;
        }

        div[data-testid="stSegmentedControl"] button:hover,
        div[data-testid="stSegmentedControl"] [data-testid="stSegmentedControlOption"]:hover {
            color: #F1F5F9 !important;
            background: rgba(255, 255, 255, 0.06) !important;
        }

        div[data-testid="stSegmentedControl"] button[aria-selected="true"],
        div[data-testid="stSegmentedControl"] button[aria-checked="true"],
        div[data-testid="stSegmentedControl"] [data-testid="stSegmentedControlOption"][aria-selected="true"],
        div[data-testid="stSegmentedControl"] [data-testid="stSegmentedControlOption"][data-checked="true"],
        div[data-testid="stSegmentedControl"] label:has(input:checked) {
            background: linear-gradient(135deg, #0284C7 0%, #00A3FF 100%) !important;
            color: #FFFFFF !important;
            font-weight: 900 !important;
            border-radius: 8px !important;
            box-shadow: 0 0 14px rgba(0, 163, 255, 0.65), inset 0 1px 1px rgba(255, 255, 255, 0.35) !important;
        }

        div[data-testid="stSegmentedControl"] p,
        div[data-testid="stSegmentedControl"] span {
            font-size: 14px !important;
            font-weight: 800 !important;
            letter-spacing: 0.5px !important;
            margin: 0 !important;
            text-align: center !important;
            white-space: nowrap !important;
        }

        div[data-testid="stSegmentedControl"] button[aria-selected="true"] p,
        div[data-testid="stSegmentedControl"] button[aria-checked="true"] p,
        div[data-testid="stSegmentedControl"] [data-testid="stSegmentedControlOption"][aria-selected="true"] p,
        div[data-testid="stSegmentedControl"] [data-testid="stSegmentedControlOption"][data-checked="true"] p {
            color: #FFFFFF !important;
            text-shadow: 0 0 8px rgba(255, 255, 255, 0.6) !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.crew-card-integrated),
        div[data-testid="stHorizontalBlock"]:has(.crew-card-integrated-warn) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            width: 100% !important;
            max-width: 100% !important;
            gap: 6px !important;
            box-sizing: border-box !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.crew-card-integrated) > div[data-testid="column"],
        div[data-testid="stHorizontalBlock"]:has(.crew-card-integrated-warn) > div[data-testid="column"] {
            width: calc(50% - 3px) !important;
            max-width: calc(50% - 3px) !important;
            min-width: 0 !important;
            flex: 0 0 calc(50% - 3px) !important;
            box-sizing: border-box !important;
            overflow: hidden !important;
        }

        div[data-testid="stHorizontalBlock"]:has(.crew-card-integrated) *,
        div[data-testid="stHorizontalBlock"]:has(.crew-card-integrated-warn) * {
            min-width: 0 !important;
            box-sizing: border-box !important;
        }

        .crew-card-integrated, .crew-card-integrated-warn {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%);
            border: 1.5px solid rgba(56, 189, 248, 0.45) !important;
            border-bottom: none !important;
            border-top-left-radius: 8px !important;
            border-top-right-radius: 8px !important;
            border-bottom-left-radius: 0px !important;
            border-bottom-right-radius: 0px !important;
            padding: 8px 8px 6px 8px !important;
            box-sizing: border-box !important;
            width: 100% !important;
            overflow: hidden !important;
            transition: all 0.25s ease-in-out !important;
        }

        .crew-card-integrated-warn {
            border-color: #F43F5E !important;
            box-shadow: 0 4px 14px rgba(244, 63, 94, 0.3) !important;
        }

        .card-theme-0 {
            border-color: rgba(56, 189, 248, 0.65) !important;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(14, 116, 144, 0.2) 100%) !important;
            box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15) !important;
        }
        .card-theme-0 .train-code-text { color: #38BDF8 !important; }

        .card-theme-1 {
            border-color: rgba(52, 211, 153, 0.65) !important;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(6, 95, 70, 0.2) 100%) !important;
            box-shadow: 0 4px 12px rgba(52, 211, 153, 0.15) !important;
        }
        .card-theme-1 .train-code-text { color: #34D399 !important; }

        .card-theme-2 {
            border-color: rgba(251, 191, 36, 0.65) !important;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(120, 53, 15, 0.2) 100%) !important;
            box-shadow: 0 4px 12px rgba(251, 191, 36, 0.15) !important;
        }
        .card-theme-2 .train-code-text { color: #FBBF24 !important; }

        .card-theme-3 {
            border-color: rgba(192, 132, 252, 0.65) !important;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(88, 28, 135, 0.2) 100%) !important;
            box-shadow: 0 4px 12px rgba(192, 132, 252, 0.15) !important;
        }
        .card-theme-3 .train-code-text { color: #C084FC !important; }

        .card-theme-4 {
            border-color: rgba(251, 146, 60, 0.65) !important;
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(124, 45, 18, 0.2) 100%) !important;
            box-shadow: 0 4px 12px rgba(251, 146, 60, 0.15) !important;
        }
        .card-theme-4 .train-code-text { color: #FB923C !important; }

        div[data-testid="stElementContainer"]:has(.crew-card-integrated) + div[data-testid="stElementContainer"],
        div[data-testid="stElementContainer"]:has(.crew-card-integrated-warn) + div[data-testid="stElementContainer"] {
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
        }

        div[data-testid="stElementContainer"]:has(.crew-card-integrated) + div[data-testid="stElementContainer"] button,
        div[data-testid="stElementContainer"]:has(.crew-card-integrated-warn) + div[data-testid="stElementContainer"] button {
            width: 100% !important;
            min-width: 0 !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            border-top-left-radius: 0px !important;
            border-top-right-radius: 0px !important;
            border-bottom-left-radius: 8px !important;
            border-bottom-right-radius: 8px !important;
            margin-top: -16px !important;
            margin-bottom: 8px !important;
            box-shadow: none !important;
            font-weight: 700 !important;
            padding: 3px 2px !important;
            letter-spacing: -0.3px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            background-color: rgba(15, 23, 42, 0.95) !important;
            transition: all 0.2s ease-in-out !important;
        }

        div[data-testid="stElementContainer"]:has(.crew-card-integrated) + div[data-testid="stElementContainer"] button p,
        div[data-testid="stElementContainer"]:has(.crew-card-integrated-warn) + div[data-testid="stElementContainer"] button p {
            font-size: 10.5px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            width: 100% !important;
            margin: 0 !important;
            line-height: 1.2 !important;
        }

        div[data-testid="stElementContainer"]:has(.card-theme-0) + div[data-testid="stElementContainer"] button { border: 1.5px solid rgba(56, 189, 248, 0.65) !important; border-top: 1px dashed rgba(56, 189, 248, 0.3) !important; color: #38BDF8 !important; }
        div[data-testid="stElementContainer"]:has(.card-theme-1) + div[data-testid="stElementContainer"] button { border: 1.5px solid rgba(52, 211, 153, 0.65) !important; border-top: 1px dashed rgba(52, 211, 153, 0.3) !important; color: #34D399 !important; }
        div[data-testid="stElementContainer"]:has(.card-theme-2) + div[data-testid="stElementContainer"] button { border: 1.5px solid rgba(251, 191, 36, 0.65) !important; border-top: 1px dashed rgba(251, 191, 36, 0.3) !important; color: #FBBF24 !important; }
        div[data-testid="stElementContainer"]:has(.card-theme-3) + div[data-testid="stElementContainer"] button { border: 1.5px solid rgba(192, 132, 252, 0.65) !important; border-top: 1px dashed rgba(192, 132, 252, 0.3) !important; color: #C084FC !important; }
        div[data-testid="stElementContainer"]:has(.card-theme-4) + div[data-testid="stElementContainer"] button { border: 1.5px solid rgba(251, 146, 60, 0.65) !important; border-top: 1px dashed rgba(251, 146, 60, 0.3) !important; color: #FB923C !important; }

        div[data-testid="stElementContainer"]:has(.crew-card-integrated-warn) + div[data-testid="stElementContainer"] button {
            border: 1.5px solid #F43F5E !important;
            border-top: 1px dashed rgba(244, 63, 94, 0.3) !important;
            color: #FDA4AF !important;
        }

        button[data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-primaryFormSubmit"],
        button[kind="primary"],
        button[kind="primaryFormSubmit"],
        div[data-testid="stFormSubmitButton"] > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"],
        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] {
            background: linear-gradient(135deg, #0284C7 0%, #1D4ED8 100%) !important;
            color: #FFFFFF !important;
            border: 1.5px solid #38BDF8 !important;
            border-radius: 12px !important;
            padding: 10px 16px !important;
            box-shadow: 0 4px 18px rgba(2, 132, 199, 0.6) !important;
            transition: all 0.25s ease-in-out !important;
            margin-top: 6px !important;
            margin-bottom: 12px !important;
            width: 100% !important;
        }

        button[data-testid="stBaseButton-primary"]:hover,
        button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
        button[kind="primary"]:hover,
        button[kind="primaryFormSubmit"]:hover,
        div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover,
        div[data-testid="stButton"] > button[kind="primary"]:hover,
        div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"]:hover {
            background: linear-gradient(135deg, #0369A1 0%, #1E40AF 100%) !important;
            border-color: #38BDF8 !important;
            box-shadow: 0 6px 24px rgba(56, 189, 248, 0.8) !important;
            transform: translateY(-1px) !important;
        }

        button[data-testid="stBaseButton-primary"] p,
        button[data-testid="stBaseButton-primaryFormSubmit"] p,
        button[kind="primary"] p,
        button[kind="primaryFormSubmit"] p {
            font-size: 15px !important;
            font-weight: 800 !important;
            color: #FFFFFF !important;
            letter-spacing: 0.6px !important;
        }

        button[data-testid="stBaseButton-secondary"],
        button[kind="secondary"],
        div[data-testid="stButton"] > button[kind="secondary"],
        div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"] {
            background: rgba(15, 23, 42, 0.6) !important;
            color: #94A3B8 !important;
            border: 1.5px solid rgba(255, 255, 255, 0.15) !important;
            box-shadow: none !important;
            border-radius: 10px !important;
            padding: 8px 12px !important;
            transition: all 0.2s ease-in-out !important;
        }

        button[data-testid="stBaseButton-secondary"]:hover,
        button[kind="secondary"]:hover,
        div[data-testid="stButton"] > button[kind="secondary"]:hover,
        div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"]:hover {
            background: rgba(255, 255, 255, 0.08) !important;
            color: #F1F5F9 !important;
            border-color: rgba(56, 189, 248, 0.4) !important;
        }

        button[data-testid="stBaseButton-secondary"] p,
        button[kind="secondary"] p,
        div[data-testid="stButton"] > button[kind="secondary"] p,
        div[data-testid="stButton"] > button[data-testid="stBaseButton-secondary"] p {
            color: #94A3B8 !important;
            font-size: 14px !important;
            font-weight: 600 !important;
        }

        .badge-group {
            display: flex;
            gap: 2px;
            align-items: center;
            justify-content: flex-end;
            flex-wrap: nowrap;
        }
        .role-badge-driver { font-size: 8.5px; font-weight: 800; color: #38BDF8; background: rgba(56, 189, 248, 0.2); padding: 1px 4px; border-radius: 3px; white-space: nowrap; font-family: monospace; }
        .role-badge-conductor { font-size: 8.5px; font-weight: 800; color: #34D399; background: rgba(52, 211, 153, 0.2); padding: 1px 4px; border-radius: 3px; white-space: nowrap; font-family: monospace; }
        .role-badge-crew { font-size: 8.5px; font-weight: 800; color: #FBBF24; background: rgba(251, 191, 36, 0.2); padding: 1px 4px; border-radius: 3px; white-space: nowrap; font-family: monospace; }
        .non-line-badge { font-size: 8.5px; font-weight: 700; color: #C084FC; background: rgba(168, 85, 247, 0.2); padding: 1px 3px; border-radius: 3px; white-space: nowrap; }
        .long-badge { font-size: 8.5px; font-weight: 700; color: #FB7185; background: rgba(244, 63, 94, 0.2); padding: 1px 3px; border-radius: 3px; white-space: nowrap; }
        .do2w-badge { font-size: 8.5px; font-weight: 700; color: #FBBF24; background: rgba(245, 158, 11, 0.2); padding: 1px 3px; border-radius: 3px; white-space: nowrap; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    active_files = get_current_role_files()

    # ==================== 大表/完整班表檢視模式 (INSPECTION MODE) ====================
    inspect_emp_id = st.session_state.get("inspect_emp_target")
    if inspect_emp_id:
        st.markdown(
            f"""
            <div class="section-header-box" style="border-left-color: #38BDF8; padding: 10px 14px !important; margin-bottom: 12px !important;">
                <div style="font-size: 15px; font-weight: 900; color: #38BDF8; font-family: monospace;">
                    [{current_unit_label}] 組員完整班表檢視：{inspect_emp_id}
                </div>
                <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">INSPECTION MODE // FULL SCHEDULE VIEW</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("上一頁 (返回快篩結果)", key="btn_back_to_filter", use_container_width=True):
            st.session_state["inspect_emp_target"] = None
            st.rerun()

        try:
            start_dt, dates, emp_id, emp_name, cells = process_file_data(inspect_emp_id)
            with st.spinner(f"正在讀取【{emp_name}】完整班表，請稍候..."):
                buf = render_schedule_figure(
                    start_dt,
                    dates,
                    emp_id,
                    emp_name,
                    cells,
                    current_unit_label,
                    badge_title="Producer | C.L.F",
                )
            st.success(f"【{emp_name} ({emp_id})】完整班表載入完成！")

            comp.render_zoomable_image(buf)

            st.download_button(
                "點此下載班表影像檔",
                data=buf,
                file_name=f"{current_unit_label}_班表_{emp_name}.png",
                mime="image/png",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"繪製組員班表時發生錯誤：{e}")

        st.stop()

    missing_files = [
        role
        for role in ["駕駛", "列車長", "服勤員"]
        if not os.path.exists(active_files.get(role, ""))
        or os.path.getsize(active_files.get(role, "")) == 0
    ]

    if missing_files:
        st.error(
            f"【{current_unit_label}】資料庫異常或尚無檔案：請洽管理員上傳！"
        )

    td_time = get_file_mtime_str(active_files.get("駕駛", ""))
    tm_time = get_file_mtime_str(active_files.get("列車長", ""))
    ta_time = get_file_mtime_str(active_files.get("服勤員", ""))
    sched_range = get_schedule_range()

    st.markdown(
        f"""
    <div class="section-header-box" style="border-left-color: #60A5FA; padding: 8px 12px !important; margin: 6px 0 !important;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="section-title" style="font-size: 13px !important;">[{current_unit_label}] 排班週期</span>
            <span style="font-size: 14px; color: {"#EF4444" if missing_files else "#60A5FA"}; font-weight: 800; font-family: monospace;">
                {sched_range if len(missing_files) < 3 else "資料庫異常"}
            </span>

        </div>
        <details style="margin-top: 4px; font-size: 10px; color: #94A3B8; font-family: monospace; cursor: pointer;">
            <summary style="outline: none; color: #38BDF8; font-weight: 600; list-style: none; display: flex; justify-content: space-between; align-items: center;">
                <span>點擊檢視各大表更新時間</span>
                <span style="font-size: 9px; color: #64748B;">▼</span>
            </summary>
            <div style="display: flex; flex-direction: column; gap: 3px; margin-top: 6px; padding-top: 6px; border-top: 1px dashed rgba(255,255,255,0.1);">
                <div style="display: flex; justify-content: space-between;"><span>駕駛 (TD)</span><span>{td_time}</span></div>
                <div style="display: flex; justify-content: space-between;"><span>列車長 (TM)</span><span>{tm_time}</span></div>
                <div style="display: flex; justify-content: space-between;"><span>服勤員 (TA)</span><span>{ta_time}</span></div>
            </div>
        </details>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    <div style='font-size: 13px; font-weight: 700; color: #94A3B8; margin-bottom: 8px;'>選擇系統操作模式</div>
    """,
        unsafe_allow_html=True,
    )

    MODE_OPTIONS = [
        "繪製個人月班表圖檔",
        "換班｜選擇換班日期",
        "換假｜選擇換假日期",
    ]

    if "active_app_mode" not in st.session_state:
        st.session_state["active_app_mode"] = "繪製個人月班表圖檔"

    try:
        current_mode_idx = MODE_OPTIONS.index(st.session_state["active_app_mode"])
    except ValueError:
        current_mode_idx = 0

    app_mode = st.radio(
        "系統操作模式選擇",
        MODE_OPTIONS,
        index=current_mode_idx,
        horizontal=False,
        label_visibility="collapsed",
        key="user_app_mode",
    )

    if app_mode != st.session_state["active_app_mode"]:
        st.session_state["active_app_mode"] = app_mode
        st.session_state.pop("win_raw_candidates", None)
        st.session_state.pop("ex_raw_candidates", None)
        st.session_state["ex_search_performed"] = False

        modal_keys_to_clear = [
            "show_feedback_modal", "show_feedback_dialog",
            "feedback_open", "show_issue_modal", "show_feedback"
        ]
        for mk in modal_keys_to_clear:
            if mk in st.session_state:
                st.session_state[mk] = False

    st.markdown("---")

    # ==================== 模式一：繪製個人月班表圖檔 ====================
    if app_mode == "繪製個人月班表圖檔":
        if is_module_maintenance(current_unit_label, "producer"):
            if not is_admin_user:
                st.markdown(
                    f"""
                    <div style="background: rgba(239, 68, 68, 0.15); border: 1.5px solid #EF4444; border-radius: 10px; padding: 16px; margin-bottom: 16px; text-align: center;">
                        <div style="font-size: 16px; font-weight: 900; color: #FCA5A5; font-family: monospace;">SYSTEM MAINTENANCE // 系統維護中</div>
                        <div style="font-size: 15px; font-weight: 800; color: #FDE68A; margin: 8px 0;">
                            【{current_unit_label}】個人月班表圖檔生成系統進行維護中
                        </div>
                        <div style="font-size: 12px; color: #CBD5E1;">
                            目前正在進行系統升級維護，暫不開放服務，請稍後再試。
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.stop()
            else:
                st.markdown(
                    f"""
                    <div style="background: rgba(245, 158, 11, 0.15); border: 1.5px solid #F59E0B; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; font-size: 13px; color: #FDE68A;">
                        <strong>【管理員維護預覽】</strong> 當前【{current_unit_label} - 個人月班表圖檔】已開啟維護模式（一般組員已被阻擋），您正以管理員身分預覽測試。
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown(
            """
        <div class="section-header-box">
            <div class="section-title">個人班表圖檔生成</div>
            <div class="section-subtitle">Personal Shift Schedule Image Generator</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        with st.form(key="draw_schedule_form", border=False):
            draw_default_val = current_user_id if not is_privileged else st.session_state.get("draw_input_key", current_user_id)
            draw_field_label = (
                f"員編或姓名 (已鎖定個人帳號：{current_user_name})"
                if not is_privileged
                else "員編或姓名 (特權/管理員模式：可查詢全體組員)"
            )

            st.text_input(
                draw_field_label,
                value=draw_default_val,
                disabled=not is_privileged,
                key="draw_input_key",
            )
            submit_btn = st.form_submit_button(
                "開始繪製月班表", type="primary", use_container_width=True
            )

        if submit_btn:
            current_input = current_user_id if not is_privileged else st.session_state.get("draw_input_key", "").strip()

            if not current_input or current_input.upper() == "A":
                st.warning("請輸入有效的員編或姓名（例如: A023300）")
            else:
                try:
                    start_dt, dates, emp_id, emp_name, cells = process_file_data(
                        current_input
                    )
                    log_activity(
                        "個人班表繪製",
                        f"操作者:{current_user_id} | 單位:{current_unit_label} | 查詢關鍵字:{current_input} | 成功解析組員:{emp_name}({emp_id})"
                    )

                    with st.spinner(f"正在繪製【{emp_name}】的個人月班表，請稍候..."):
                        buf = render_schedule_figure(
                            start_dt,
                            dates,
                            emp_id,
                            emp_name,
                            cells,
                            current_unit_label,
                            badge_title="Producer | C.L.F",
                        )
                    st.success(f"【{emp_name}】個人班表圖片生成成功！")

                    comp.render_zoomable_image(buf)

                    st.download_button(
                        "點此下載班表影像檔",
                        data=buf,
                        file_name=f"{current_unit_label}_班表_{emp_name}.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"繪製班表時發生錯誤：{e}")

    # ==================== 模式二：換班｜選擇換班日期 ====================
    elif app_mode == "換班｜選擇換班日期":
        if is_module_maintenance(current_unit_label, "window_filter"):
            if not is_admin_user:
                st.markdown(
                    f"""
                    <div style="background: rgba(239, 68, 68, 0.15); border: 1.5px solid #EF4444; border-radius: 10px; padding: 16px; margin-bottom: 16px; text-align: center;">
                        <div style="font-size: 16px; font-weight: 900; color: #FCA5A5; font-family: monospace;">SYSTEM MAINTENANCE // 系統維護中</div>
                        <div style="font-size: 15px; font-weight: 800; color: #FDE68A; margin: 8px 0;">
                            【{current_unit_label}】換班選擇日期快篩系統進行維護中
                        </div>
                        <div style="font-size: 12px; color: #CBD5E1;">
                            目前正在進行系統升級維護，暫不開放服務，請稍後再試。
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.stop()
            else:
                st.markdown(
                    f"""
                    <div style="background: rgba(245, 158, 11, 0.15); border: 1.5px solid #F59E0B; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; font-size: 13px; color: #FDE68A;">
                        <strong>【管理員維護預覽】</strong> 當前【{current_unit_label} - 換班日期快篩】已開啟維護模式（一般組員已被阻擋），您正以管理員身分預覽測試。
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown(
            """
        <div class="section-header-box">
            <div class="section-title">換班檢索｜指定 Sign-In 時段組員快篩</div>
            <div class="section-subtitle">Duty Time Window & Sign-In Filter Matrix</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-field-label">點擊選擇查詢職位</div>', unsafe_allow_html=True)

        if "saved_win_roles" not in st.session_state:
            st.session_state["saved_win_roles"] = ["服勤員"]

        if hasattr(st, "segmented_control"):
            selected_roles = st.segmented_control(
                "點擊選擇查詢職位",
                options=["服勤員", "列車長", "駕駛"],
                default=st.session_state["saved_win_roles"],
                selection_mode="multi",
                label_visibility="collapsed",
                key="win_seg_roles",
                on_change=reset_win_search,
            )
        else:
            selected_roles = st.multiselect(
                "點擊選擇查詢職位",
                options=["服勤員", "列車長", "駕駛"],
                default=st.session_state["saved_win_roles"],
                label_visibility="collapsed",
                key="win_multi_roles",
                on_change=reset_win_search,
            )

        roles_to_query = list(selected_roles) if selected_roles else []
        if roles_to_query:
            st.session_state["saved_win_roles"] = roles_to_query

        if not roles_to_query:
            st.warning("⚠️請至少選取一個職位 以進行查詢！")
        else:
            has_driver = "駕駛" in roles_to_query
            start_h = 3 if has_driver else 5
            morn_start_time = f"{start_h:02d}:00"

            TIME_OPTIONS = [
                f"{h:02d}:{m:02d}"
                for h in range(start_h, 19)
                for m in (0, 30)
                if not (h == 18 and m == 30)
            ]

            if "saved_win_time_slider" not in st.session_state:
                st.session_state["saved_win_time_slider"] = (morn_start_time, "10:00")

            slider_default = st.session_state["saved_win_time_slider"]
            if (
                not isinstance(slider_default, (tuple, list))
                or len(slider_default) != 2
                or slider_default[0] not in TIME_OPTIONS
                or slider_default[1] not in TIME_OPTIONS
            ):
                slider_default = (morn_start_time, "10:00")

            valid_paths = {}
            for r_name in roles_to_query:
                p = active_files.get(r_name, "")
                if p and os.path.exists(p) and os.path.getsize(p) > 0:
                    valid_paths[r_name] = p

            if not valid_paths:
                st.error(
                    f"找不到【{current_unit_label}】所選職位的班表檔案，請先至管理員後台上傳"
                )
            else:
                first_role, first_path = list(valid_paths.items())[0]
                df_search_sample = safe_read_excel(first_path, header=3)
                df_search_sample.columns = [str(c).strip() for c in df_search_sample.columns]
                date_cols = [
                    normalize_date_str(col)
                    for col in df_search_sample.columns[2:]
                    if normalize_date_str(col)
                ]

                if date_cols:
                    default_win_idx = 0
                    saved_target_date = st.session_state.get("saved_win_target_date")
                    if saved_target_date and saved_target_date in date_cols:
                        default_win_idx = date_cols.index(saved_target_date)
                    else:
                        tomorrow_dt = date.today() + timedelta(days=1)
                        found_idx = None
                        for idx, d_str in enumerate(date_cols):
                            parts = d_str.split("/")
                            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                                if int(parts[0]) == tomorrow_dt.month and int(parts[1]) == tomorrow_dt.day:
                                    found_idx = idx
                                    break
                        if found_idx is None:
                            today_dt = date.today()
                            for idx, d_str in enumerate(date_cols):
                                parts = d_str.split("/")
                                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                                    if int(parts[0]) == today_dt.month and int(parts[1]) == today_dt.day:
                                        found_idx = idx
                                        break
                        default_win_idx = found_idx if found_idx is not None else 0

                    target_date = st.selectbox(
                        "選擇換班日期",
                        date_cols,
                        index=default_win_idx,
                        format_func=lambda d: get_date_label(d, df_search_sample.columns),
                        key="win_target_date",
                        on_change=reset_win_search,
                    )
                    st.session_state["saved_win_target_date"] = target_date

                    win_week_holidays = get_week_holidays(
                        target_date, date_cols, df_search_sample.columns
                    )
                    _, win_week_str = check_week_has_holiday(
                        target_date, date_cols, df_search_sample.columns
                    )

                    comp.show_holiday_notice(win_week_holidays, win_week_str)

                    st.markdown('<div class="section-field-label">快捷選擇時段：</div>', unsafe_allow_html=True)

                    btn_all_label = f"全時段 ({morn_start_time}~18:00)"
                    btn_morn_label = f"早班 ({morn_start_time}~10:00)"
                    btn_noon_label = "中班 (10:00~13:00)"
                    btn_night_label = "晚班 (13:00~18:00)"

                    if st.button(btn_all_label, key="btn_win_all", use_container_width=True):
                        target_range = (morn_start_time, "18:00")
                        st.session_state["saved_win_time_slider"] = target_range
                        st.session_state["win_time_slider"] = target_range
                        reset_win_search()
                        st.rerun()

                    if st.button(btn_morn_label, key="btn_win_morn", use_container_width=True):
                        target_range = (morn_start_time, "10:00")
                        st.session_state["saved_win_time_slider"] = target_range
                        st.session_state["win_time_slider"] = target_range
                        reset_win_search()
                        st.rerun()

                    if st.button(btn_noon_label, key="btn_win_noon", use_container_width=True):
                        target_range = ("10:00", "13:00")
                        st.session_state["saved_win_time_slider"] = target_range
                        st.session_state["win_time_slider"] = target_range
                        reset_win_search()
                        st.rerun()

                    if st.button(btn_night_label, key="btn_win_night", use_container_width=True):
                        target_range = ("13:00", "18:00")
                        st.session_state["saved_win_time_slider"] = target_range
                        st.session_state["win_time_slider"] = target_range
                        reset_win_search()
                        st.rerun()

                    if "win_time_slider" not in st.session_state:
                        st.session_state["win_time_slider"] = slider_default

                    slider_val = st.select_slider(
                        "Sign-In 時段區間 (拖曳調整)",
                        options=TIME_OPTIONS,
                        key="win_time_slider",
                        on_change=reset_win_search,
                    )
                    st.session_state["saved_win_time_slider"] = slider_val

                    if isinstance(slider_val, (tuple, list)) and len(slider_val) == 2:
                        min_time, max_time_sel = slider_val
                    else:
                        min_time, max_time_sel = TIME_OPTIONS[0], TIME_OPTIONS[-1]

                    st.markdown('<div class="section-field-label">進階篩選條件</div>', unsafe_allow_html=True)

                    if "saved_win_main_line" not in st.session_state:
                        st.session_state["saved_win_main_line"] = False
                    if "saved_win_long_shift" not in st.session_state:
                        st.session_state["saved_win_long_shift"] = False

                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        only_main_line = st.checkbox(
                            "僅顯示正線勤務",
                            value=st.session_state["saved_win_main_line"],
                            key="win_main_line",
                        )
                        st.session_state["saved_win_main_line"] = only_main_line
                    with filter_col2:
                        only_long_shift = st.checkbox(
                            "僅顯示長班 (>8.5h)",
                            value=st.session_state["saved_win_long_shift"],
                            key="win_long_shift",
                        )
                        st.session_state["saved_win_long_shift"] = only_long_shift

                    if st.button("搜尋可換班組員名單", key="btn_window_search", type="primary", use_container_width=True):
                        raw_candidates = []

                        for r_name, p_path in valid_paths.items():
                            df_search = safe_read_excel(p_path, header=3)
                            df_search.columns = [str(c).strip() for c in df_search.columns]
                            target_col_idx = find_date_column_index(df_search.columns, target_date)

                            if target_col_idx != -1:
                                for _, row in df_search.iterrows():
                                    emp_id = str(row.iloc[0]).strip()
                                    emp_name = str(row.iloc[1]).strip()
                                    if not emp_id or emp_id.upper() in ["NAN", "NONE", ""]:
                                        continue

                                    if target_col_idx < len(row):
                                        cell_raw = row.iloc[target_col_idx]
                                        parsed = parse_cell(cell_raw)
                                        start_t = parsed["start"]

                                        is_off = is_cell_off_day(cell_raw)

                                        if not is_off or start_t:
                                            tr_upper = str(parsed["train"]).strip().upper()
                                            raw_cell_upper = str(cell_raw).upper()
                                            is_leave = (
                                                any(k in raw_cell_upper for k in LEAVE_CODES)
                                                or tr_upper in LEAVE_CODES
                                            )
                                            is_non_line = is_town_shift(parsed["train"], parsed["note"])
                                            is_long = is_overtime(
                                                parsed["hours"], parsed["train"], parsed["note"]
                                            )

                                            do_match = re.search(
                                                r"(DO\d*W?|D\d+W|OGC)", str(cell_raw), re.IGNORECASE
                                            )
                                            do_tag = do_match.group(1).upper() if do_match else ""

                                            next_day_sign_in = "無"
                                            if target_col_idx + 1 < len(row):
                                                next_parsed = parse_cell(row.iloc[target_col_idx + 1])
                                                next_day_sign_in = (
                                                    next_parsed["start"]
                                                    if next_parsed["start"]
                                                    else (
                                                        next_parsed["train"]
                                                        if next_parsed["train"]
                                                        else "無"
                                                    )
                                                )

                                            raw_candidates.append({
                                                "日期": target_date,
                                                "職位": r_name,
                                                "員編": emp_id,
                                                "姓名": emp_name,
                                                "Sign-In": start_t if start_t else "--:--",
                                                "Sign-Out": parsed["end"] if parsed["end"] else "--:--",
                                                "工時": parsed.get("hours", ""),
                                                "車次": translate_train_code(parsed["train"]),
                                                "隔日Sign-In": next_day_sign_in,
                                                "長班": is_long,
                                                "非正線": is_non_line,
                                                "請假": is_leave,
                                                "出勤標記": do_tag,
                                            })

                        st.session_state["win_raw_candidates"] = raw_candidates
                        st.rerun()

                    if st.session_state.get("win_raw_candidates") is not None:
                        raw_list = st.session_state["win_raw_candidates"]
                        filtered_results = []

                        for r in raw_list:
                            if r["Sign-In"] == "--:--":
                                if not (min_time <= morn_start_time and max_time_sel >= "18:00"):
                                    continue
                            else:
                                if not (min_time <= r["Sign-In"] <= max_time_sel):
                                    continue

                            if only_main_line and (r["非正線"] or r["請假"]):
                                continue
                            if only_long_shift and not r["長班"]:
                                continue
                            filtered_results.append(r)

                        ROLE_ORDER = {"服勤員": 1, "列車長": 2, "駕駛": 3}
                        filtered_results = sorted(
                            filtered_results,
                            key=lambda x: (
                                str(x["Sign-In"]) if x["Sign-In"] != "--:--" else "99:99",
                                get_shift_group_num(x["車次"]),
                                ROLE_ORDER.get(x.get("職位", ""), 9),
                                str(x["車次"]),
                            ),
                        )

                        unique_groups_in_order = []
                        for r in filtered_results:
                            g_key = get_shift_group_key(r["車次"])
                            if g_key not in unique_groups_in_order:
                                unique_groups_in_order.append(g_key)

                        shift_key_to_theme = {g_key: idx % 5 for idx, g_key in enumerate(unique_groups_in_order)}

                        log_activity(
                            "換班日期快篩",
                            f"單位:{current_unit_label} | 選擇職位:{'/'.join(roles_to_query)} | 日期:{target_date} | "
                            f"時段:{min_time}~{max_time_sel} | 僅正線:{only_main_line} | "
                            f"僅長班:{only_long_shift} | 命中數:{len(filtered_results)}筆"
                        )

                        st.markdown(
                            f"### 換班可選人員名單（共符合 {len(filtered_results)} 筆）"
                        )

                        if filtered_results:
                            cnt_do2w = sum(
                                1
                                for r in filtered_results
                                if "DO2" in r.get("出勤標記", "")
                                or "OGC" in r.get("出勤標記", "")
                            )
                            cnt_long = sum(1 for r in filtered_results if r.get("長班"))

                            st.markdown(
                                f"""
                                <div style="display: flex; gap: 8px; margin-bottom: 12px; margin-top: 4px;">
                                    <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1.5px solid rgba(56, 189, 248, 0.5); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                        <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">符合資格人數</div>
                                        <div style="font-size: 17px; font-weight: 900; color: #38BDF8; font-family: monospace;">{len(filtered_results)} <span style="font-size: 10px;">位</span></div>
                                    </div>
                                    <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1.5px solid rgba(245, 158, 11, 0.5); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                        <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">含 DO2W 標記</div>
                                        <div style="font-size: 17px; font-weight: 900; color: #FBBF24; font-family: monospace;">{cnt_do2w} <span style="font-size: 10px;">人</span></div>
                                    </div>
                                    <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1.5px solid rgba(244, 63, 94, 0.5); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                        <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">長班 (>8.5h)</div>
                                        <div style="font-size: 17px; font-weight: 900; color: #FB7185; font-family: monospace;">{cnt_long} <span style="font-size: 10px;">人</span></div>
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            for i in range(0, len(filtered_results), 2):
                                batch = filtered_results[i : i + 2]
                                cols = st.columns(2)

                                for idx_in_batch, r in enumerate(batch):
                                    with cols[idx_in_batch]:
                                        do_tag = r.get("出勤標記", "")
                                        r_role = r.get("職位", "")

                                        badges_html = '<div class="badge-group">'
                                        if r_role == "駕駛":
                                            badges_html += '<span class="role-badge-driver">TD</span>'
                                        elif r_role == "列車長":
                                            badges_html += '<span class="role-badge-conductor">TM</span>'
                                        elif r_role == "服勤員":
                                            badges_html += '<span class="role-badge-crew">TA</span>'

                                        if r.get("非正線"):
                                            badges_html += '<span class="non-line-badge">非正線</span>'
                                        if r.get("長班"):
                                            badges_html += '<span class="long-badge">長班</span>'
                                        if do_tag:
                                            badges_html += f'<span class="do2w-badge">[{do_tag}]</span>'
                                        badges_html += "</div>"

                                        clean_name = str(r.get("姓名", "")).replace("\n", " ").strip()
                                        clean_id = str(r.get("員編", "")).replace("\n", " ").strip()
                                        clean_train = str(r.get("車次", "")).replace("\n", " ").strip()
                                        clean_signin = str(r.get("Sign-In", "--:--")).replace("\n", " ").strip()
                                        clean_signout = str(r.get("Sign-Out", "--:--")).replace("\n", " ").strip()
                                        clean_next_signin = str(r.get("隔日Sign-In", "無")).replace("\n", " ").strip()

                                        g_key = get_shift_group_key(clean_train)
                                        theme_idx = shift_key_to_theme.get(g_key, 0)
                                        card_class = f"crew-card-integrated card-theme-{theme_idx}"

                                        card_html = f"""<div class="{card_class}">
<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
    <div style="font-size: 13px; font-weight: 800; color: #F8FAFC; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 60%;">
        {clean_name} <span style="color:#94A3B8; font-size:9.5px; font-weight:500;">({clean_id})</span>
    </div>
    {badges_html}
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px; padding-top: 4px; border-top: 1px solid rgba(255,255,255,0.1); width: 100%;">
    <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0;">
        <div class="train-code-text" style="font-size: 13.5px; font-weight: 900; letter-spacing: 0.3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{clean_train}</div>
        <div style="font-size: 9.5px; color: #94A3B8; font-family: monospace; white-space: nowrap;">隔日: <strong style="color:#FCD34D;">{clean_next_signin}</strong></div>
    </div>
    <div style="text-align: right; display: flex; flex-direction: column; gap: 1px; flex-shrink: 0;">
        <div style="font-size: 12px; font-weight: 900; color: #4ADE80; font-family: monospace; line-height: 1.1;">In {clean_signin}</div>
        <div style="font-size: 12px; font-weight: 900; color: #38BDF8; font-family: monospace; line-height: 1.1;">Out {clean_signout}</div>
    </div>
</div>
</div>"""

                                        st.markdown(card_html, unsafe_allow_html=True)

                                        if st.button(
                                            f"檢視 {clean_name} 完整班表 ➔",
                                            key=f"win_btn_{clean_id}_{i+idx_in_batch}",
                                            use_container_width=True,
                                        ):
                                            log_activity("快篩彈窗檢視班表", f"單位:{current_unit_label} | 目標組員:{clean_name}({clean_id})")
                                            st.session_state["inspect_emp_target"] = clean_id
                                            st.rerun()
                        else:
                            st.info("在指定條件內，找不到符合的人員")

    # ==================== 模式三：換假｜選擇換假日期 ====================
    elif app_mode == "換假｜選擇換假日期":
        if is_module_maintenance(current_unit_label, "exchange_filter"):
            if not is_admin_user:
                st.markdown(
                    f"""
                    <div style="background: rgba(239, 68, 68, 0.15); border: 1.5px solid #EF4444; border-radius: 10px; padding: 16px; margin-bottom: 16px; text-align: center;">
                        <div style="font-size: 16px; font-weight: 900; color: #FCA5A5; font-family: monospace;">SYSTEM MAINTENANCE // 系統維護中</div>
                        <div style="font-size: 15px; font-weight: 800; color: #FDE68A; margin: 8px 0;">
                            【{current_unit_label}】換假選擇日期快篩系統進行維護中
                        </div>
                        <div style="font-size: 12px; color: #CBD5E1;">
                            目前正在進行系統升級維護，暫不開放服務，請稍後再試。
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.stop()
            else:
                st.markdown(
                    f"""
                    <div style="background: rgba(245, 158, 11, 0.15); border: 1.5px solid #F59E0B; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; font-size: 13px; color: #FDE68A;">
                        <strong>【管理員維護預覽】</strong> 當前【{current_unit_label} - 換假日期快篩】已開啟維護模式（一般組員已被阻擋），您正以管理員身分預覽測試。
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown(
            """
        <div class="section-header-box">
            <div class="section-title">換假檢索｜選擇換假日期快篩</div>
            <div class="section-subtitle">Shift Exchange Date Filter Matrix</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        if "ex_search_performed" not in st.session_state:
            st.session_state["ex_search_performed"] = False

        if "saved_ex_role" not in st.session_state:
            st.session_state["saved_ex_role"] = "服勤員"

        ex_roles = ["服勤員", "駕駛", "列車長"]
        try:
            ex_role_idx = ex_roles.index(st.session_state["saved_ex_role"])
        except ValueError:
            ex_role_idx = 0

        selected_role = st.selectbox(
            "選擇職位類別",
            ex_roles,
            index=ex_role_idx,
            key="ex_role_select",
            on_change=reset_ex_search,
        )
        st.session_state["saved_ex_role"] = selected_role

        sample_path = active_files.get(selected_role, "")

        if not sample_path or not os.path.exists(sample_path):
            st.error(
                f"找不到【{current_unit_label} -"
                f" {selected_role}】的班表檔案，請先至管理員後台上傳"
            )
        else:
            try:
                df_ex = safe_read_excel(sample_path, header=3)
                df_ex.columns = [str(c).strip() for c in df_ex.columns]
                date_cols = [
                    normalize_date_str(c)
                    for c in df_ex.columns[2:]
                    if normalize_date_str(c)
                ]

                if not date_cols:
                    st.warning("目前的班表檔案中無法解析出有效的日期欄位。")
                else:
                    ex_date_col1, ex_date_col2 = st.columns(2)

                    default_ex_idx = 0
                    saved_ex_target = st.session_state.get("saved_ex_target_date")
                    if saved_ex_target and saved_ex_target in date_cols:
                        default_ex_idx = date_cols.index(saved_ex_target)
                    else:
                        tomorrow_dt = date.today() + timedelta(days=1)
                        found_idx = None
                        for idx, d_str in enumerate(date_cols):
                            parts = d_str.split("/")
                            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                                if int(parts[0]) == tomorrow_dt.month and int(parts[1]) == tomorrow_dt.day:
                                    found_idx = idx
                                    break
                        if found_idx is None:
                            today_dt = date.today()
                            for idx, d_str in enumerate(date_cols):
                                parts = d_str.split("/")
                                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                                    if int(parts[0]) == today_dt.month and int(parts[1]) == today_dt.day:
                                        found_idx = idx
                                        break
                        default_ex_idx = found_idx if found_idx is not None else 0

                    with ex_date_col1:
                        target_date = st.selectbox(
                            "選擇想休假日期",
                            date_cols,
                            index=default_ex_idx,
                            format_func=lambda d: get_date_label(d, df_ex.columns),
                            key="ex_target_date",
                            on_change=reset_ex_search,
                        )
                        st.session_state["saved_ex_target_date"] = target_date

                    same_week_options = []
                    is_week_has_do2w, target_week_str = check_week_has_holiday(
                        target_date, date_cols, df_ex.columns
                    )

                    try:
                        current_year = date.today().year
                        norm_target = normalize_date_str(target_date)
                        t_m, t_d = map(int, norm_target.split("/"))
                        t_dt = date(current_year, t_m, t_d)
                        t_sun = t_dt - timedelta(days=(t_dt.weekday() + 1) % 7)
                        t_sat = t_sun + timedelta(days=6)

                        for d_str in date_cols:
                            try:
                                norm_d = normalize_date_str(d_str)
                                d_m, d_d = map(int, norm_d.split("/"))
                                d_dt = date(current_year, d_m, d_d)
                                if t_sun <= d_dt <= t_sat and norm_d != norm_target:
                                    same_week_options.append(d_str)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    return_date_options = (
                        same_week_options
                        if same_week_options
                        else [d for d in date_cols if normalize_date_str(d) != normalize_date_str(target_date)]
                    )

                    if not return_date_options:
                        st.warning("找不到可還假期的其他有效日期。")
                        return_date = None
                    else:
                        saved_ex_return = st.session_state.get("saved_ex_return_date")
                        if saved_ex_return and saved_ex_return in return_date_options:
                            return_date_idx = return_date_options.index(saved_ex_return)
                        else:
                            return_date_idx = 0

                        with ex_date_col2:
                            return_date = st.selectbox(
                                "選擇可還假日期",
                                return_date_options,
                                index=return_date_idx,
                                format_func=lambda d: get_date_label(d, df_ex.columns),
                                key="ex_return_date",
                                on_change=reset_ex_search,
                            )
                            st.session_state["saved_ex_return_date"] = return_date

                    if return_date:
                        ex_week_holidays = list(
                            set(
                                get_week_holidays(target_date, date_cols, df_ex.columns)
                                + get_week_holidays(return_date, date_cols, df_ex.columns)
                            )
                        )

                        comp.show_holiday_notice(ex_week_holidays, target_week_str)

                        st.caption(
                            f" **同一週規範換假區間：{target_week_str}**（還假選單已自動設定於當週區間）"
                        )

                        if "saved_ex_time_filter" not in st.session_state:
                            st.session_state["saved_ex_time_filter"] = "不限"
                        if "saved_ex_sort_order" not in st.session_state:
                            st.session_state["saved_ex_sort_order"] = "依 Sign-In 時間 (由早至晚)"
                        if "saved_ex_strict_limit" not in st.session_state:
                            st.session_state["saved_ex_strict_limit"] = True

                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            time_filter_options = ["不限"] + [
                                f"{h:02d}:00 以後" for h in range(5, 17)
                            ]
                            try:
                                time_filter_idx = time_filter_options.index(st.session_state["saved_ex_time_filter"])
                            except ValueError:
                                time_filter_idx = 0

                            return_time_filter = st.selectbox(
                                "還假日 Sign-In 時間限制",
                                options=time_filter_options,
                                index=time_filter_idx,
                                key="ex_time_filter",
                            )
                            st.session_state["saved_ex_time_filter"] = return_time_filter

                        with col_f2:
                            sort_options = [
                                "依 Sign-In 時間 (由早至晚)",
                                "依同類班別末四碼數字",
                                "依最早 Sign-Out",
                                "依工時長短",
                            ]
                            try:
                                sort_idx = sort_options.index(st.session_state["saved_ex_sort_order"])
                            except ValueError:
                                sort_idx = 0

                            sort_order = st.selectbox(
                                "結果排序方式",
                                sort_options,
                                index=sort_idx,
                                key="ex_sort_order",
                            )
                            st.session_state["saved_ex_sort_order"] = sort_order

                        strict_limit = st.checkbox(
                            "嚴格過濾：排除換假後連續上班已達 6 天以上的人員",
                            value=st.session_state["saved_ex_strict_limit"],
                            key="ex_strict_limit",
                        )
                        st.session_state["saved_ex_strict_limit"] = strict_limit

                        if st.button("搜尋可換假組員名單", key="btn_ex_search", type="primary", use_container_width=True):
                            raw_candidates = []

                            target_col_idx = find_date_column_index(df_ex.columns, target_date)
                            return_col_idx = find_date_column_index(df_ex.columns, return_date)

                            if target_col_idx != -1 and return_col_idx != -1:
                                for _, row in df_ex.iterrows():
                                    emp_id = str(row.iloc[0]).strip()
                                    emp_name = str(row.iloc[1]).strip()
                                    if not emp_id or emp_id.upper() in ["NAN", "NONE", ""]:
                                        continue
                                    if target_col_idx >= len(row) or return_col_idx >= len(row):
                                        continue

                                    parsed_target = parse_cell(row.iloc[target_col_idx])
                                    raw_target_str = str(row.iloc[target_col_idx]).strip().upper()

                                    is_target_leave = (
                                        any(k in raw_target_str for k in LEAVE_CODES)
                                        or parsed_target["train"] in LEAVE_CODES
                                    )
                                    if is_target_leave:
                                        continue

                                    is_target_do = is_cell_off_day(row.iloc[target_col_idx])
                                    if not is_target_do:
                                        continue

                                    parsed_return = parse_cell(row.iloc[return_col_idx])
                                    raw_return_str = str(row.iloc[return_col_idx]).strip()
                                    raw_return_upper = raw_return_str.upper()

                                    is_return_leave = (
                                        any(k in raw_return_upper for k in LEAVE_CODES)
                                        or parsed_return["train"] in LEAVE_CODES
                                    )
                                    is_return_do = is_cell_off_day(row.iloc[return_col_idx])
                                    if is_return_do or is_return_leave:
                                        continue

                                    is_long = is_overtime(
                                        parsed_return["hours"],
                                        parsed_return["train"],
                                        parsed_return["note"],
                                    )
                                    is_non_line = is_town_shift(
                                        parsed_return["train"], parsed_return["note"]
                                    )

                                    return_do_match = re.search(
                                        r"(DO\d*W?|D\d+W|OGC)", raw_return_str, re.IGNORECASE
                                    )
                                    return_do_tag = return_do_match.group(1).upper() if return_do_match else ""

                                    raw_target_cell = str(row.iloc[target_col_idx]).upper()
                                    raw_return_cell = str(row.iloc[return_col_idx]).upper()
                                    has_do2w_tag = bool(
                                        re.search(
                                            r"(DO[23]W|D[23]W|OGC)",
                                            raw_target_cell + raw_return_cell,
                                            re.IGNORECASE,
                                        )
                                    )

                                    sim_row = row.copy()
                                    sim_row = set_simulated_cell(sim_row, target_date, "勤")
                                    sim_row = set_simulated_cell(sim_row, return_date, "休")

                                    max_consecutive_streak = calculate_consecutive_work_days(
                                        sim_row, target_date
                                    )

                                    raw_candidates.append({
                                        "員編": emp_id,
                                        "姓名": emp_name,
                                        "想休日": target_date,
                                        "想休狀態": (
                                            raw_target_str.split("\n")[0]
                                            if raw_target_str
                                            else "DO"
                                        ),
                                        "還休日": return_date,
                                        "還假車次": translate_train_code(parsed_return["train"]),
                                        "Sign-In": (
                                            parsed_return["start"]
                                            if parsed_return["start"]
                                            else "--:--"
                                        ),
                                        "Sign-Out": (
                                            parsed_return["end"]
                                            if parsed_return["end"]
                                            else "--:--"
                                        ),
                                        "工時": parsed_return["hours"],
                                        "長班": is_long,
                                        "非正線": is_non_line,
                                        "出勤標記": return_do_tag,
                                        "有DO2W標記": has_do2w_tag,
                                        "連續上班天數": max_consecutive_streak,
                                    })

                            st.session_state["ex_raw_candidates"] = raw_candidates
                            st.session_state["ex_search_performed"] = True
                            st.rerun()

                        if st.session_state.get("ex_search_performed"):
                            raw_list = st.session_state.get("ex_raw_candidates", [])
                            filtered_candidates = []

                            for cand in raw_list:
                                if return_time_filter != "不限":
                                    min_allowed = return_time_filter.split(" ")[0]
                                    if (
                                        not cand["Sign-In"]
                                        or cand["Sign-In"] == "--:--"
                                        or cand["Sign-In"] < min_allowed
                                    ):
                                        continue

                                if strict_limit and cand["連續上班天數"] >= 6:
                                    continue

                                filtered_candidates.append(cand)

                            if sort_order == "依 Sign-In 時間 (由早至晚)":
                                filtered_candidates = sorted(
                                    filtered_candidates,
                                    key=lambda x: (
                                        x["Sign-In"] if x["Sign-In"] != "--:--" else "99:99",
                                        get_shift_group_num(x["還假車次"]),
                                        str(x["還假車次"]),
                                    ),
                                )
                            elif sort_order == "依同類班別末四碼數字":
                                filtered_candidates = sorted(
                                    filtered_candidates,
                                    key=lambda x: (
                                        get_shift_group_num(x["還假車次"]),
                                        x["Sign-In"] if x["Sign-In"] != "--:--" else "99:99",
                                        str(x["還假車次"]),
                                    ),
                                )
                            elif sort_order == "依最早 Sign-Out":
                                filtered_candidates = sorted(
                                    filtered_candidates,
                                    key=lambda x: (
                                        x["Sign-Out"] if x["Sign-Out"] != "--:--" else "99:99",
                                        x["Sign-In"] if x["Sign-In"] != "--:--" else "99:99",
                                    ),
                                )
                            elif sort_order == "依工時長短":
                                filtered_candidates = sorted(
                                    filtered_candidates,
                                    key=lambda x: x["工時"] or "0h00m",
                                    reverse=True,
                                )

                            log_activity(
                                "換假日期快篩",
                                f"單位:{current_unit_label} | 職位:{selected_role} | 想休:{target_date} | "
                                f"還假:{return_date} | 時間限制:{return_time_filter} | "
                                f"排序:{sort_order} | 嚴格連六:{strict_limit} | 命中數:{len(filtered_candidates)}筆"
                            )

                            st.markdown(
                                f"### 換假可選人員名單（共 {len(filtered_candidates)} 位）"
                            )

                            if filtered_candidates:
                                cnt_do2w = sum(
                                    1
                                    for c in filtered_candidates
                                    if c.get("有DO2W標記")
                                    or "DO2" in c.get("出勤標記", "")
                                )
                                cnt_streak6 = sum(
                                    1
                                    for c in filtered_candidates
                                    if c.get("連續上班天數", 0) >= 6
                                )

                                st.markdown(
                                    f"""
                                    <div style="display: flex; gap: 8px; margin-bottom: 12px; margin-top: 4px;">
                                        <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1.5px solid rgba(56, 189, 248, 0.5); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                            <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">可換假總人數</div>
                                            <div style="font-size: 17px; font-weight: 900; color: #38BDF8; font-family: monospace;">{len(filtered_candidates)} <span style="font-size: 10px;">位</span></div>
                                        </div>
                                        <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1.5px solid rgba(245, 158, 11, 0.5); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                            <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">含 DO2W 標記</div>
                                            <div style="font-size: 17px; font-weight: 900; color: #FBBF24; font-family: monospace;">{cnt_do2w} <span style="font-size: 10px;">人</span></div>
                                        </div>
                                        <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1.5px solid rgba(244, 63, 94, 0.5); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                            <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">連班 6 天以上</div>
                                            <div style="font-size: 17px; font-weight: 900; color: #FB7185; font-family: monospace;">{cnt_streak6} <span style="font-size: 10px;">人</span></div>
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                                for i in range(0, len(filtered_candidates), 2):
                                    batch = filtered_candidates[i : i + 2]
                                    cols = st.columns(2)

                                    for idx_in_batch, cand in enumerate(batch):
                                        with cols[idx_in_batch]:
                                            do_tag = cand.get("出勤標記", "")

                                            badges_html = '<div class="badge-group">'
                                            if cand.get("非正線"):
                                                badges_html += '<span class="non-line-badge">非正線</span>'
                                            if cand.get("長班"):
                                                badges_html += '<span class="long-badge">長班</span>'
                                            if cand.get("有DO2W標記") or do_tag:
                                                tag_text = do_tag if do_tag else "DO2W"
                                                badges_html += f'<span class="do2w-badge">[{tag_text}]</span>'
                                            badges_html += "</div>"

                                            streak_cnt = cand.get("連續上班天數", 0)

                                            clean_cand_name = str(cand.get("姓名", "")).replace("\n", " ").strip()
                                            clean_cand_id = str(cand.get("員編", "")).replace("\n", " ").strip()
                                            clean_cand_return_date = str(cand.get("還休日", "")).replace("\n", " ").strip()
                                            clean_cand_return_train = str(cand.get("還假車次", "無")).replace("\n", " ").strip()
                                            clean_cand_signin = str(cand.get("Sign-In", "--:--")).replace("\n", " ").strip()
                                            clean_cand_signout = str(cand.get("Sign-Out", "--:--")).replace("\n", " ").strip()

                                            card_class = "crew-card-integrated-warn" if streak_cnt >= 6 else "crew-card-integrated card-theme-0"

                                            card_html = f"""<div class="{card_class}">
<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
    <div style="font-size: 13px; font-weight: 800; color: #F8FAFC; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 60%;">
        {clean_cand_name} <span style="color:#94A3B8; font-size:9.5px; font-weight:500;">({clean_cand_id})</span>
    </div>
    {badges_html}
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px; padding-top: 4px; border-top: 1px solid rgba(255,255,255,0.1); width: 100%;">
    <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0;">
        <div class="train-code-text" style="font-size: 13.5px; font-weight: 900; letter-spacing: 0.3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{clean_cand_return_train}</div>
        <div style="font-size: 9.5px; color: #94A3B8; font-family: monospace; white-space: nowrap;">還休:{clean_cand_return_date} ｜ <strong style="color:{"#FB7185" if streak_cnt >= 6 else "#CBD5E1"};">連:{streak_cnt}天</strong></div>
    </div>
    <div style="text-align: right; display: flex; flex-direction: column; gap: 1px; flex-shrink: 0;">
        <div style="font-size: 12px; font-weight: 900; color: #4ADE80; font-family: monospace; line-height: 1.1;">In {clean_cand_signin}</div>
        <div style="font-size: 9.5px; color: #38BDF8; font-family: monospace; line-height: 1.1;">Out {clean_cand_signout}</div>
    </div>
</div>
</div>"""

                                            st.markdown(card_html, unsafe_allow_html=True)

                                            if st.button(
                                                f"檢視 {clean_cand_name} 完整班表 ➔",
                                                key=f"ex_btn_{clean_cand_id}_{i+idx_in_batch}",
                                                use_container_width=True,
                                            ):
                                                log_activity("快篩彈窗檢視班表", f"單位:{current_unit_label} | 目標組員:{clean_cand_name}({clean_cand_id})")
                                                st.session_state["inspect_emp_target"] = clean_cand_id
                                                st.rerun()
                            else:
                                st.info(
                                    "在指定條件內，找不到符合的可換假人員"
                                    " (可嘗試放寬還假日 Sign-In 時間限制或取消嚴格過濾)"
                                )
            except Exception as e:
                st.error(f"讀取換假資料時發生錯誤：{e}")


if __name__ == "__main__":
    render_user_home()
