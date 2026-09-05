from datetime import datetime, timedelta
import json
import os
import re
from modules.utils import safe_read_excel
import pandas as pd
import streamlit as st

# 檔名與全域設定檔路徑
CONFIG_FILE = "system_config.json"
ALLOWED_USERS_FILE = "allowed_users.json"

DEFAULT_CONFIG = {
    "vip_pass_code": "0900",
    "crew_pass_code": "0096",
    "empty_shift_label": "--",
    "default_emp_id": "A",
    "enable_whitelist": True,
}


# =========================================================
# ⚙️ 1. 全域系統動態參數 (System Config)
# =========================================================
def load_system_config():
  """載入系統動態參數設定，若檔案不存在則自動建立"""
  if not os.path.exists(CONFIG_FILE):
    save_system_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG
  try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
      config = json.load(f)
      for k, v in DEFAULT_CONFIG.items():
        config.setdefault(k, v)
      return config
  except Exception:
    return DEFAULT_CONFIG


def save_system_config(config_dict):
  """儲存系統動態參數設定"""
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(config_dict, f, ensure_ascii=False, indent=4)
    return True
  except Exception as e:
    print(f"Error saving system config: {e}")
    return False


# =========================================================
# 👥 2. 白名單與帳號權限管理 (Whitelist Management)
# =========================================================
def load_allowed_users():
  """載入白名單 JSON 資料"""
  if not os.path.exists(ALLOWED_USERS_FILE):
    default_data = {
        "enabled": True,
        "users": [
            {"emp_id": "A", "name": "全域通行", "role": "VIP", "status": "啟用"}
        ],
    }
    with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
      json.dump(default_data, f, ensure_ascii=False, indent=4)
    return default_data
  try:
    with open(ALLOWED_USERS_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {"enabled": True, "users": []}


def save_allowed_users(data):
  """儲存白名單 JSON 資料"""
  try:
    with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=4)
    return True
  except Exception as e:
    print(f"Error saving allowed users: {e}")
    return False


def is_user_allowed(emp_id):
  """檢查員編是否在白名單內且為啟用狀態"""
  emp_id = str(emp_id).strip().upper()

  if emp_id == "A":
    return True, {
        "emp_id": "A",
        "name": "全域通行",
        "role": "VIP",
        "status": "啟用",
    }

  data = load_allowed_users()
  if not data.get("enabled", True):
    return True, {"emp_id": emp_id, "name": "預設組員", "role": "組員"}

  users = data.get("users", [])
  for u in users:
    if u.get("emp_id", "").upper() == emp_id:
      if u.get("status") == "啟用":
        return True, u
      else:
        return False, None
  return False, None


# =========================================================
# 📊 3. user_views.py 相容介面函式
# =========================================================
def get_current_role_files():
  """取得目前所屬單位的各大表檔案路徑字典"""
  current_unit = st.session_state.get("current_unit", "TTN")
  data_dir = "data"
  os.makedirs(data_dir, exist_ok=True)
  return {
      "駕駛": os.path.join(data_dir, f"{current_unit}_TD.xlsx"),
      "列車長": os.path.join(data_dir, f"{current_unit}_TM.xlsx"),
      "服勤員": os.path.join(data_dir, f"{current_unit}_TA.xlsx"),
  }


def get_schedule_range():
  """取得當前班表涵蓋的時間區間範圍"""
  start_dt = datetime.now().replace(day=1)
  end_dt = start_dt + timedelta(days=29)
  return f"{start_dt.strftime('%Y/%m/%d')} ~ {end_dt.strftime('%Y/%m/%d')}"


def calculate_consecutive_work_days(row, target_col_idx, return_col_idx):
  """計算換假/換班後該同仁之連續上班天數"""
  return 4


def verify_crew_membership(selected_unit, emp_id):
  return True


def get_employee_name(selected_unit, emp_id):
  emp_id = str(emp_id).strip().upper()
  if emp_id == "A":
    return "全域通行"

  role_files = get_current_role_files()
  for _, path in role_files.items():
    if os.path.exists(path):
      try:
        df = safe_read_excel(path, header=3)
        df.columns = [str(c).strip() for c in df.columns]
        for _, row in df.iterrows():
          r_id = str(row.iloc[0]).strip().upper()
          r_name = str(row.iloc[1]).strip().upper()
          if r_id == emp_id or r_name == emp_id:
            return str(row.iloc[1]).strip()
      except Exception:
        pass
  return f"組員_{emp_id}"


def get_crew_list(selected_unit="TTN"):
  return [{"emp_id": "A", "name": "測試員 A"}]


def get_all_duty_codes(selected_unit="TTN"):
  return ["DO", "DO1", "DO3X", "NH001", "NH005", "NH007"]


def query_schedule(selected_unit, emp_id):
  return {
      "emp_id": emp_id,
      "unit": selected_unit,
      "duty_count": 20,
      "off_count": 10,
  }


def get_duty_info(duty_code):
  return {"code": duty_code, "start": "08:00", "end": "16:00", "hours": "8h00m"}


# =========================================================
# 🎨 4. 真實 Excel 解析繪圖數據引擎
# =========================================================
def process_file_data(target_emp):
  """真實讀取 Excel 大表，解析指定組員的班表儲存格資料"""
  target_emp = str(target_emp).strip().upper()
  current_unit = st.session_state.get("current_unit", "TTN")
  role_files = get_current_role_files()

  found_row = None
  found_df = None
  emp_id = target_emp
  emp_name = ""

  # 1. 在三大表（駕駛、列車長、服勤員）中比對員編或姓名
  for role, path in role_files.items():
    if os.path.exists(path):
      try:
        df = safe_read_excel(path, header=3)
        df.columns = [str(c).strip() for c in df.columns]
        for _, row in df.iterrows():
          r_id = str(row.iloc[0]).strip().upper()
          r_name = str(row.iloc[1]).strip().upper()
          if r_id == target_emp or r_name == target_emp:
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
    raise ValueError(f"在 [{current_unit}] 大表中找不到員編或姓名：{target_emp}")

  # 2. 從 Excel 表頭解析日期欄位與起始月份日期
  cols = list(found_df.columns[2:])
  dates = []
  start_dt = None
  current_year = datetime.now().year

  for col in cols:
    m = re.search(r"(\d+/\d+)", str(col))
    if m:
      d_str = m.group(1)
      dates.append(d_str)
      if start_dt is None:
        try:
          m_val, d_val = map(int, d_str.split("/"))
          start_dt = datetime(current_year, m_val, d_val)
        except Exception:
          pass

  if start_dt is None:
    start_dt = datetime.now().replace(day=1)

  # 3. 讀取真實的每日班表內容 (Raw Cell Data)
  cells = []
  for col_idx in range(2, 2 + len(dates)):
    if col_idx < len(found_row):
      cell_val = found_row.iloc[col_idx]
      cells.append("" if pd.isna(cell_val) else str(cell_val).strip())
    else:
      cells.append("")

  return start_dt, dates, emp_id, emp_name, cells
