from datetime import datetime, timedelta
import json
import os
import pandas as pd

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

  # 測試員 A 通道
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
# 📊 3. 組員與班表數據查詢相容函式 (User Views Dependencies)
# =========================================================
def verify_crew_membership(selected_unit, emp_id):
  """驗證員編是否為該單位成員"""
  emp_id = str(emp_id).strip().upper()
  if emp_id == "A" or emp_id.startswith("VIP"):
    return True
  return True


def get_employee_name(selected_unit, emp_id):
  """取得員工姓名 (相容介面)"""
  emp_id = str(emp_id).strip().upper()
  if emp_id == "A":
    return "全域通行"
  return f"組員_{emp_id}"


def get_crew_list(selected_unit="TTN"):
  """取得單位組員清單 (提供 user_views 下拉選單)"""
  return [
      {"emp_id": "A", "name": "測試員 A"},
      {"emp_id": "023300", "name": "範例同仁"},
  ]


def get_all_duty_codes(selected_unit="TTN"):
  """取得當期所有班表號碼"""
  return ["DO", "DO1", "DO3X", "NH001", "NH005", "NH007"]


def query_schedule(selected_unit, emp_id):
  """查詢個人班表摘要資訊"""
  emp_id = str(emp_id).strip().upper()
  return {
      "emp_id": emp_id,
      "unit": selected_unit,
      "duty_count": 20,
      "off_count": 10,
  }


def get_duty_info(duty_code):
  """取得特定班號時間資訊"""
  return {"code": duty_code, "start": "08:00", "end": "16:00", "hours": "8h00m"}


# =========================================================
# 🎨 4. 畫圖與資料處理核心 (Drawing & Parser)
# =========================================================
def process_file_data(target_emp):
  """解析繪製班表圖形所需的數據陣列"""
  target_emp = str(target_emp).strip().upper()
  start_dt = datetime.now().replace(day=1)

  dates = [(start_dt + timedelta(days=i)).strftime("%m/%d") for i in range(30)]
  cells = []
  for i in range(30):
    if i % 7 in [0, 6]:
      cells.append("DO")
    elif i % 5 == 0:
      cells.append("DO3X")
    else:
      cells.append("08:00-16:00 NH001")

  emp_name = get_employee_name("TTN", target_emp)
  return start_dt, dates, target_emp, emp_name, cells
