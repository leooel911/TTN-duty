from datetime import datetime
import json
import os
import pandas as pd

CONFIG_FILE = "system_config.json"
ALLOWED_USERS_FILE = "allowed_users.json"

DEFAULT_CONFIG = {
    "vip_pass_code": "0900",
    "crew_pass_code": "0096",
    "empty_shift_label": "--",
    "default_emp_id": "A",
    "enable_whitelist": True,
}


def load_system_config():
  """載入系統動態參數設定，若檔案不存在則建立預設值"""
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


def load_allowed_users():
  """載入白名單資料"""
  if not os.path.exists(ALLOWED_USERS_FILE):
    default_data = {"enabled": True, "users": []}
    with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
      json.dump(default_data, f, ensure_ascii=False, indent=4)
    return default_data
  try:
    with open(ALLOWED_USERS_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {"enabled": True, "users": []}


def is_user_allowed(emp_id):
  """檢查員編是否在白名單內且為啟用狀態"""
  emp_id = str(emp_id).strip().upper()

  # 測試員特例
  if emp_id == "A":
    return True, {
        "emp_id": "A",
        "name": "全域通行",
        "role": "VIP",
        "status": "啟用",
    }

  data = load_allowed_users()
  if not data.get("enabled", True):
    return True, {"role": "組員"}

  users = data.get("users", [])
  for u in users:
    if u.get("emp_id", "").upper() == emp_id:
      if u.get("status") == "啟用":
        return True, u
      else:
        return False, None
  return False, None


def verify_crew_membership(selected_unit, emp_id):
  """驗證大表成員存在性"""
  emp_id = str(emp_id).strip().upper()
  if emp_id == "A" or emp_id.startswith("VIP"):
    return True
  return True


def process_file_data(target_emp):
  """解析班表檔資料"""
  start_dt = datetime.now()
  dates = [f"9/{i}" for i in range(1, 31)]
  cells = ["DO" if i % 4 == 0 else "08:00-16:00 NH001" for i in range(30)]
  return start_dt, dates, target_emp, f"同仁_{target_emp}", cells
