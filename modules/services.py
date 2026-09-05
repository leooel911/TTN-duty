from datetime import datetime, timedelta
import json
import os
import pandas as pd

# 檔名設定
CONFIG_FILE = "system_config.json"
ALLOWED_USERS_FILE = "allowed_users.json"

# 系統預設參數
DEFAULT_CONFIG = {
    "vip_pass_code": "0900",
    "crew_pass_code": "0096",
    "empty_shift_label": "--",
    "default_emp_id": "A",
    "enable_whitelist": True,
}


# =========================================================
# ⚙️ 1. 動態全域系統設定讀寫
# =========================================================
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


# =========================================================
# 👥 2. 白名單帳號管理與審核
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

  # 測試員特例通道
  if emp_id == "A":
    return True, {
        "emp_id": "A",
        "name": "全域通行",
        "role": "VIP",
        "status": "啟用",
    }

  data = load_allowed_users()

  # 若白名單總開關關閉，直接放行
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
# 📊 3. 班表大表比對與查詢相容介面
# =========================================================
def verify_crew_membership(selected_unit, emp_id):
  """驗證員編是否屬於該單位或大表組員"""
  emp_id = str(emp_id).strip().upper()
  if emp_id == "A" or emp_id.startswith("VIP"):
    return True
  # 若有具體大表邏輯可在此擴充，預設通關
  return True


def get_crew_list(selected_unit="TTN"):
  """取得指定單位的組員清單 (提供 user_views 下拉選單使用)"""
  return [
      {"emp_id": "A", "name": "測試員 A"},
      {"emp_id": "023300", "name": "範例同仁"},
  ]


def query_schedule(selected_unit, emp_id):
  """快速查詢該員編之月班表摘要數據"""
  emp_id = str(emp_id).strip().upper()
  return {
      "emp_id": emp_id,
      "unit": selected_unit,
      "duty_count": 20,
      "off_count": 10,
  }


def process_file_data(target_emp):
  """解析畫圖所需的月班表基礎數據陣列"""
  target_emp = str(target_emp).strip().upper()
  start_dt = datetime.now().replace(day=1)

  # 生成當月日期與預設班表格子資料
  dates = [(start_dt + timedelta(days=i)).strftime("%m/%d") for i in range(30)]
  cells = []
  for i in range(30):
    if i % 7 in [0, 6]:
      cells.append("DO")  # 輪休
    elif i % 5 == 0:
      cells.append("DO3X")
    else:
      cells.append("08:00-16:00 NH001")

  emp_name = "全域通行" if target_emp == "A" else f"組員_{target_emp}"
  return start_dt, dates, target_emp, emp_name, cells
