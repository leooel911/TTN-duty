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

def get_schedule_range():
    active_files = get_current_role_files()
    path = active_files.get("駕駛") or active_files.get("服勤員") or active_files.get("列車長")
    if not path or not os.path.exists(path):
        return "無班表資料"
    try:
        df = safe_read_excel(path, header=3)
        df.columns = [str(c).strip() for c in df.columns]
        date_cols = [re.search(r'(\d+/\d+)', str(col)).group(1) for col in df.columns[2:] if re.search(r'(\d+/\d+)', str(col))]
        if date_cols:
            return f"{date_cols[0]} ~ {date_cols[-1]}"
    except:
        pass
    return "無法解析週期"

def verify_crew_membership(unit_key, emp_input):
    input_clean = str(emp_input).strip().upper()
    if not input_clean: return False
    unit_files = UNITS.get(unit_key, UNITS["TTN"])
    for role in ["駕駛", "列車長", "服勤員"]:
        path = unit_files.get(role, "")
        if os.path.exists(path):
            try:
                df = safe_read_excel(path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    emp_id = str(row.iloc[0]).strip().upper()
                    if emp_id == input_clean:
                        return True
            except: pass
    return False

def process_file_data(emp_input):
    input_clean = str(emp_input).strip().upper()
    active_files = get_current_role_files()
    
    found_row = None
    found_cols = None
    emp_id = ""
    emp_name = ""

    for role in ["服勤員", "駕駛", "列車長"]:
        path = active_files.get(role, "")
        if os.path.exists(path):
            try:
                df = safe_read_excel(path, header=3)
                df.columns = [str(c).strip() for c in df.columns]
                for _, row in df.iterrows():
                    curr_id = str(row.iloc[0]).strip().upper()
                    curr_name = str(row.iloc[1]).strip().upper()
                    if curr_id == input_clean or curr_name == input_clean:
                        found_row = row
                        found_cols = df.columns
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()
                        break
            except: pass
        if found_row is not None: break

    if found_row is None:
        raise ValueError(f"找不到人員 [{emp_input}] 的班表資料")

    dates = []
    cells = []
    start_dt = None

    for idx in range(2, len(found_cols)):
        col_name = str(found_cols[idx]).strip()
        date_match = re.search(r'(\d+/\d+)', col_name)
        if date_match:
            d_str = date_match.group(1)
            dates.append(d_str)
            cells.append(found_row.iloc[idx])
            if start_dt is None:
                try:
                    m, d = map(int, d_str.split('/'))
                    current_year = datetime.now().year
                    start_dt = date(current_year, m, d)
                except: pass

    if start_dt is None:
        start_dt = date.today()

    return start_dt, dates, emp_id, emp_name, cells

def calculate_consecutive_work_days(row, target_col_idx, return_col_idx):
    """
    模擬試算換假後，該組員全月的最長連續出勤天數 (依據勞基法七休一原則)
    - target_col_idx (想休日): 模擬承接勤務 -> 變為出勤態 (不可斷班 -> False)
    - return_col_idx (還休日): 模擬班還出來 -> 變為休假態 (可以斷班 -> True)
    - DO2/DO2W 國定假日與 PAY 特休依據 resets_work_streak 精準採計為不可斷班！
    """
    all_cols = list(row.index)
    
    # 建立該組員當月各天「能否斷班」的真實狀態模擬序列
    streak_reset_flags = []
    
    for idx in range(2, len(all_cols)):
        if idx == return_col_idx:
            # 還休日：組員把班還出來，當天變為休假 -> 可以斷班
            streak_reset_flags.append(True)
        elif idx == target_col_idx:
            # 想休日：組員承接對方的班，當天變為出勤 -> 不可斷班
            streak_reset_flags.append(False)
        else:
            # 原本排班狀態：精準依據 resets_work_streak 判定 (DO2/DO2W/PAY 不可斷班)
            cell_val = row.iloc[idx]
            streak_reset_flags.append(resets_work_streak(cell_val))

    # 計算全月中「最長連續出勤天數」
    max_streak = 0
    current_streak = 0

    for resets in streak_reset_flags:
        if not resets:
            # 不可斷班 -> 連班天數 +1
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
        else:
            # 遇到真正的休假日 -> 連班重置歸零
            current_streak = 0

    return max_streak
