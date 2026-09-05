import os
import re
import pandas as pd
import streamlit as st
from datetime import date, datetime
from config import UNITS
from modules.utils import (
    safe_read_excel, parse_cell, resets_work_streak, 
    is_valid_train_code, is_cell_off_day
)

def get_current_role_files():
    current_unit = st.session_state.get("current_unit", "TTN")
    return UNITS.get(current_unit, UNITS["TTN"])

@st.cache_data(show_spinner=False)
def get_unit_member_set(unit_key, file_mtimes_tuple):
    unit_files = UNITS.get(unit_key, UNITS["TTN"])
    members = set()
    for role in ["駕駛", "列車長", "服勤員"]:
        path = unit_files.get(role, "")
        if os.path.exists(path):
            try:
                df = safe_read_excel(path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    emp_id = str(row.iloc[0]).strip().upper()
                    emp_name = str(row.iloc[1]).strip().upper()
                    if emp_id and emp_id != "NAN": members.add(emp_id)
                    if emp_name and emp_name != "NAN": members.add(emp_name)
            except Exception:
                pass
    return members

def verify_crew_membership(unit_key, emp_input):
    if not emp_input or not str(emp_input).strip():
        return False
    unit_files = UNITS.get(unit_key, UNITS["TTN"])
    mtimes = [
        os.path.getmtime(unit_files[role]) if os.path.exists(unit_files.get(role, "")) else 0 
        for role in ["駕駛", "列車長", "服勤員"]
    ]
    member_set = get_unit_member_set(unit_key, tuple(mtimes))
    return emp_input.strip().upper() in member_set

def get_schedule_range():
    active_files = get_current_role_files()
    path = active_files.get("駕駛") or active_files.get("服勤員") or active_files.get("列車長")
    if not path or not os.path.exists(path):
        return "無班表資料"
    try:
        df = safe_read_excel(path, header=3)
        df.columns = [str(c).strip() for c in df.columns]
        date_cols = [
            re.search(r'(\d+/\d+)', str(col)).group(1) 
            for col in df.columns[2:] 
            if re.search(r'(\d+/\d+)', str(col))
        ]
        if date_cols:
            return f"{date_cols[0]} ~ {date_cols[-1]}"
    except Exception:
        pass
    return "無法解析週期"

def process_file_data(input_str):
    input_clean = str(input_str).strip().upper()
    matched_row, emp_id, emp_name, df_found = None, "", "", None
    active_files = get_current_role_files()

    for role in ["服勤員", "駕駛", "列車長"]:
        path = active_files.get(role, "")
        if os.path.exists(path):
            try:
                df_temp = safe_read_excel(path, header=3)
                df_temp.columns = [str(c).strip() for c in df_temp.columns]
                for idx, row in df_temp.iterrows():
                    curr_id = str(row.iloc[0]).strip().upper()
                    curr_name = str(row.iloc[1]).strip().upper()
                    if curr_id == input_clean or curr_name == input_clean:
                        matched_row = row
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()
                        df_found = df_temp
                        break
                if matched_row is not None:
                    break
            except Exception:
                pass

    if matched_row is None:
        raise ValueError(f"找不到員編或姓名為「{input_str}」的資料。")

    col_names = df_found.columns[2:]
    dates = []
    cells = []
    start_dt = None

    for idx, col_name in enumerate(col_names):
        c_str = str(col_name).strip()
        date_match = re.search(r'(\d+/\d+)', c_str)
        if date_match:
            d_str = date_match.group(1)
            dates.append(d_str)
            if start_dt is None:
                try:
                    m, d = map(int, d_str.split('/'))
                    current_year = date.today().year
                    start_dt = date(current_year, m, d)
                except Exception:
                    pass
        else:
            dates.append(c_str)
        cells.append(matched_row.iloc[idx + 2])

    if start_dt is None:
        start_dt = date.today()

    return start_dt, dates, emp_id, emp_name, cells

def calculate_consecutive_work_days(row, target_col_idx, return_col_idx):
    """
    模擬試算換假後，該組員全月的最長連續出勤天數 (依據勞基法七休一原則)
    - target_col_idx (想休日): 模擬承接勤務 -> 變為出勤態 (不可斷班)
    - return_col_idx (還休日): 模擬班還出來 -> 變為休假態 (可以斷班)
    """
    all_cols = list(row.index)
    streak_reset_flags = []

    for idx in range(2, len(all_cols)):
        if idx == return_col_idx:
            # 還休日：變為休假 -> 可以斷班
            streak_reset_flags.append(True)
        elif idx == target_col_idx:
            # 想休日：變為出勤 -> 不可斷班
            streak_reset_flags.append(False)
        else:
            cell_val = row.iloc[idx]
            # 原本排班狀態：精準依據 resets_work_streak 判定
            streak_reset_flags.append(resets_work_streak(cell_val))

    max_streak = 0
    current_streak = 0

    for resets in streak_reset_flags:
        if not resets:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
        else:
            current_streak = 0

    return max_streak
