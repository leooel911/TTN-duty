from datetime import date, datetime, timedelta, timezone
import io
import json
import os
import re

from config import (
    DATA_DIR,
    LEAVE_CODES,
    LOG_FILE,
    NATIONAL_HOLIDAYS,
    TAIWAN_TZ,
    UNITS,
)
import pandas as pd
import streamlit as st


# =========================================================
# 🛠️ 1. 模組維護狀態控制 (雙重相容判定：.flag 與 .json)
# =========================================================
def get_maintenance_flag_path(unit, module_key):
  return os.path.join(DATA_DIR, f"maintenance_{unit}_{module_key}.flag")


def set_module_maintenance(unit, module_key, is_maint):
  """開啟或關閉特定模組之維護狀態"""
  if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)
  flag_path = get_maintenance_flag_path(unit, module_key)
  if is_maint:
    with open(flag_path, "w", encoding="utf-8") as f:
      f.write("ON")
  else:
    if os.path.exists(flag_path):
      os.remove(flag_path)


def is_module_maintenance(unit, module_key):
  """檢測特定單位的模組是否處於維護狀態 (支援 .flag 與 .json 雙軌檢測)"""
  # 方式 A：檢查 .flag 檔案是否存在
  flag_path = get_maintenance_flag_path(unit, module_key)
  if os.path.exists(flag_path):
    return True

  # 方式 B：檢查 maintenance.json 檔案設定
  maint_json_paths = [
      os.path.join(DATA_DIR, "maintenance.json"),
      "maintenance.json",
  ]
  for json_path in maint_json_paths:
    if os.path.exists(json_path):
      try:
        with open(json_path, "r", encoding="utf-8") as f:
          data = json.load(f)
        full_key = f"{unit}_{module_key}"
        if data.get(full_key, False):
          return True
      except Exception:
        pass

  return False


# =========================================================
# 👤 2. 個資遮罩與 Excel 相容讀取引擎
# =========================================================
def format_display_name(name):
  """將姓名遮罩顯示 (如: 張小明 -> 小明)"""
  if not name or str(name).strip().upper() in ["NAN", "NONE", ""]:
    return ""
  clean_name = str(name).strip()
  if len(clean_name) <= 2:
    return clean_name
  return clean_name[1:]


@st.cache_data(show_spinner=False)
def safe_read_excel_cached(file_path_or_bytes, header=None, file_mtime=None):
  """高效能快取 Excel 讀取器 (支援 .xlsx 與舊版 .xls)"""
  try:
    if isinstance(file_path_or_bytes, str):
      if file_path_or_bytes.endswith(".xls"):
        return pd.read_excel(file_path_or_bytes, header=header, engine="xlrd")
      else:
        try:
          return pd.read_excel(
              file_path_or_bytes, header=header, engine="openpyxl"
          )
        except Exception:
          return pd.read_excel(file_path_or_bytes, header=header, engine="xlrd")
    else:
      file_bytes = file_path_or_bytes
      try:
        return pd.read_excel(
            io.BytesIO(file_bytes), header=header, engine="openpyxl"
        )
      except Exception:
        return pd.read_excel(
            io.BytesIO(file_bytes), header=header, engine="xlrd"
        )
  except Exception as e:
    raise ValueError(f"無法解析 Excel 檔案格式 (錯誤: {e})")


def safe_read_excel(file_source, header=None):
  if isinstance(file_source, str) and os.path.exists(file_source):
    mtime = os.path.getmtime(file_source)
    return safe_read_excel_cached(file_source, header=header, file_mtime=mtime)
  elif hasattr(file_source, "getvalue"):
    return safe_read_excel_cached(file_source.getvalue(), header=header)
  else:
    return safe_read_excel_cached(file_source, header=header)


def get_employee_name(unit_key, emp_input):
  """全大表員編對照姓名檢索器"""
  input_clean = str(emp_input).strip().upper()
  unit_files = UNITS.get(unit_key, UNITS.get("TTN", {}))
  for role in ["駕駛", "列車長", "服勤員"]:
    path = unit_files.get(role, "")
    if os.path.exists(path):
      try:
        df = safe_read_excel(path, header=3)
        df.columns = [str(c).strip() for c in df.columns]
        for _, row in df.iterrows():
          emp_id = str(row.iloc[0]).strip().upper()
          emp_name = str(row.iloc[1]).strip().upper()
          if emp_id == input_clean or emp_name == input_clean:
            return str(row.iloc[1]).strip()
      except Exception:
        pass
  return ""


# =========================================================
# 📱 3. 裝置解析與操作日誌紀錄 (Audit Trail)
# =========================================================
def parse_device_info(ua_string):
  ua = ua_string.lower()
  if "iphone" in ua:
    device = "iPhone"
  elif "ipad" in ua:
    device = "iPad"
  elif "android" in ua:
    device = "Android Phone"
  elif "macintosh" in ua or "mac os" in ua:
    device = "Mac"
  elif "windows" in ua:
    device = "Windows PC"
  else:
    device = "Desktop / Other"

  if "safari" in ua and "chrome" not in ua and "crios" not in ua:
    browser = "Safari"
  elif "chrome" in ua or "crios" in ua:
    browser = "Chrome"
  elif "line" in ua:
    browser = "LINE App"
  elif "edg" in ua:
    browser = "Edge"
  else:
    browser = "Browser"

  return f"{device} [{browser}]"


def log_activity(input_str):
  try:
    if not os.path.exists(DATA_DIR):
      os.makedirs(DATA_DIR, exist_ok=True)
    now_tw = datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    ua_raw = (
        st.context.headers.get("user-agent", "")
        if hasattr(st, "context")
        else ""
    )
    device_info = parse_device_info(ua_raw) if ua_raw else "未知裝置"
    current_operator = st.session_state.get("current_user_id", "未知")
    current_unit = st.session_state.get("current_unit", "TTN")
    log_entry = (
        f"{now_tw} | 單位: {current_unit} | 操作者員編: {current_operator} | 裝置:"
        f" {device_info} | 動作: {input_str}\n"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as f:
      f.write(log_entry)
  except Exception:
    pass


def load_activity_logs():
  logs = []
  if os.path.exists(LOG_FILE):
    try:
      with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
      for line in reversed(lines):
        line = line.strip()
        if not line:
          continue
        parts = line.split(" | ")
        if len(parts) >= 5:
          timestamp = parts[0]
          unit = parts[1].replace("單位: ", "").strip()
          user_id = parts[2].replace("操作者員編: ", "").strip()
          device = parts[3].replace("裝置: ", "").strip()
          action = parts[4].replace("動作: ", "").strip()
          logs.append({
              "timestamp": timestamp,
              "unit": unit,
              "user_id": user_id,
              "user_name": get_employee_name(unit, user_id) or user_id,
              "device": device,
              "action": action,
              "details": action,
          })
        else:
          logs.append({
              "timestamp": "",
              "unit": "TTN",
              "user_id": "未知",
              "user_name": "未知",
              "device": "未知",
              "action": line,
              "details": line,
          })
    except Exception as e:
      print(f"[Log Parsing Error] {e}")
  return logs


def get_file_mtime_str(path):
  if os.path.exists(path):
    mtime = os.path.getmtime(path)
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone(TAIWAN_TZ)
    size_kb = os.path.getsize(path) / 1024
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({size_kb:.1f} KB)"
  return "尚無檔案"


# =========================================================
# ⏱️ 4. 時間與工時運算工具
# =========================================================
def pad_time(t_str):
  if not t_str or ":" not in str(t_str):
    return str(t_str) if t_str else ""
  parts = str(t_str).split(":")
  return f"{int(parts[0]):02d}:{parts[1]}" if len(parts) == 2 else str(t_str)


def calculate_hours(start_str, end_str):
  if not start_str or not end_str or ":" not in start_str or ":" not in end_str:
    return ""
  try:
    sh, sm = map(int, start_str.split(":"))
    eh, em = map(int, end_str.split(":"))
    start_mins = sh * 60 + sm
    end_mins = eh * 60 + em
    if end_mins <= start_mins:
      end_mins += 24 * 60
    diff_mins = end_mins - start_mins
    return f"{diff_mins // 60}h{diff_mins % 60:02d}m"
  except Exception:
    return ""


def is_valid_train_code(tr):
  if not tr:
    return False
  tr_clean = str(tr).strip().upper()
  if (
      tr_clean.startswith("DO")
      or tr_clean.startswith("D2W")
      or tr_clean.startswith("D3W")
      or "OGC" in tr_clean
  ):
    return False
  if tr_clean in LEAVE_CODES:
    return False
  return bool(re.match(r"^[A-Z]+\d+", tr_clean))


def is_overtime(h, tr, note):
  if not is_valid_train_code(tr) or not h:
    return False
  try:
    p = str(h).replace("h", ":").replace("m", "").split(":")
    return (int(p[0]) * 60 + int(p[1])) > 510
  except Exception:
    return False


def translate_train_code(tr):
  if not tr:
    return "無"
  tr_upper = str(tr).strip().upper()
  mapping = {
      "PAY": "特休 (PAY)",
      "FAC": "家庭照顧假 (FAC)",
      "LEV": "公假 (LEV)",
      "MLP": "生理假 (MLP)",
      "MTR": "事假 (MTR)",
  }
  return mapping.get(tr_upper, tr)


def is_town_shift(tr, note):
  tr_upper = str(tr).strip().upper()
  note_upper = str(note).strip().upper()
  combined_text = f"{tr_upper} {note_upper}"
  if not tr or tr_upper in ["", "無", "NAN"]:
    return True
  if tr_upper in ["PAY", "FAC"]:
    return False
  keywords = [
      "TOWN",
      "STD",
      "TTN",
      "DTT",
      "OGT",
      "OGC",
      "FAC",
      "DS",
      "H9",
      "WRSL",
  ]
  for kw in keywords:
    if re.search(rf"\b{kw}\d*", combined_text):
      return True
  return not is_valid_train_code(tr_upper)


# =========================================================
# 🧩 5. 班表儲存格核心解析 (Cell Parser)
# =========================================================
def parse_cell(raw):
  if pd.isna(raw) or not str(raw).strip():
    return dict(start="", train="無", end="", hours="", note="")

  raw_str = str(raw).strip()
  lines = [
      l.strip()
      for l in raw_str.replace("\r", "").split("\n")
      if l.strip() and l.strip() != "."
  ]
  if not lines:
    return dict(start="", train="無", end="", hours="", note="")

  raw_upper = raw_str.upper()

  times = re.findall(r"\b\d{1,2}:\d{2}\b", raw_str)
  start_time = pad_time(times[0]) if len(times) >= 1 else ""
  end_time = pad_time(times[1]) if len(times) >= 2 else ""
  hours = calculate_hours(start_time, end_time)

  do_match = re.search(r"(DO\d*W?|D\d+W|OGC)", raw_str, re.IGNORECASE)
  note_tag = do_match.group(1).upper() if do_match else ""

  real_train = ""
  for line in lines:
    line_clean = line.strip()
    if re.match(r"^\d{1,2}:\d{2}$", line_clean) or re.search(
        r"^\(?\d+h\d*m?\)?$", line_clean, re.IGNORECASE
    ):
      continue
    if (
        re.match(r"^(DO\d*W?|D\d+W|OGC)$", line_clean, re.IGNORECASE)
        and start_time
    ):
      continue
    if not real_train:
      real_train = line_clean

  found_leave = next((k for k in LEAVE_CODES if k in raw_upper), "")
  if found_leave and not is_valid_train_code(real_train):
    return dict(
        start=start_time,
        end=end_time,
        train=found_leave,
        hours=hours,
        note=found_leave,
    )

  clean_real_train = (
      re.sub(r"[#%]", "", real_train).strip() if real_train else "無"
  )
  notes = [
      l
      for l in lines
      if l not in times
      and l != clean_real_train
      and not re.search(r"^\(?\d+h\d*m?\)?$", l, re.IGNORECASE)
  ]
  note_final = " ".join(notes) if notes else note_tag

  return dict(
      start=start_time,
      end=end_time,
      train=clean_real_train if clean_real_train else "無",
      hours=hours,
      note=note_final,
  )


def is_cell_off_day(raw_val):
  if pd.isna(raw_val) or not str(raw_val).strip():
    return True
  raw_str = str(raw_val).strip().upper()
  if raw_str in ["NAN", "NONE", "", "."]:
    return True

  parsed = parse_cell(raw_val)
  train_code = str(parsed.get("train", "")).strip().upper()
  has_time = bool(parsed.get("start"))
  has_valid_train = is_valid_train_code(train_code)

  if re.search(r"(DO2W|D2W|DO3W|D3W|OGC)", raw_str):
    if has_time or has_valid_train:
      return False
    return True

  if "PAY" in raw_str or train_code == "PAY":
    return False

  if train_code in LEAVE_CODES or any(k in raw_str for k in LEAVE_CODES):
    if not has_valid_train and not train_code.startswith("N"):
      return True

  if has_valid_train or train_code.startswith("N"):
    return False

  if (
      has_time
      and train_code not in LEAVE_CODES
      and not train_code.startswith("DO")
  ):
    return False

  return True


def resets_work_streak(raw_val):
  if pd.isna(raw_val) or not str(raw_val).strip():
    return True

  raw_str = str(raw_val).strip().upper()
  if raw_str in ["NAN", "NONE", "", "."]:
    return True

  parsed = parse_cell(raw_val)
  train_code = str(parsed.get("train", "")).strip().upper()
  has_time = bool(parsed.get("start"))
  has_valid_train = is_valid_train_code(train_code)

  if has_time or has_valid_train:
    return False

  if re.search(r"(DO2W?|D2W|PAY|OGC)", raw_str):
    return False

  return True


# =========================================================
# ⚖️ 6. 班間休息與法規檢查 (Labour Rules Verification)
# =========================================================
def calculate_rest_hours(sign_out_str, next_sign_in_str):
  """計算 Sign-Out 到隔日 Sign-In 的休息小時數"""
  if (
      not sign_out_str
      or not next_sign_in_str
      or "--:--" in (sign_out_str, next_sign_in_str)
  ):
    return None
  try:
    so_h, so_m = map(int, sign_out_str.split(":"))
    si_h, si_m = map(int, next_sign_in_str.split(":"))

    so_dt = datetime(2026, 1, 1, so_h, so_m)
    si_dt = datetime(2026, 1, 2, si_h, si_m)

    diff_hours = (si_dt - so_dt).total_seconds() / 3600.0
    return round(diff_hours, 1)
  except Exception:
    return None


def check_shift_legality(crew_row, target_col_idx, all_cols):
  window_start = max(2, target_col_idx - 6)
  window_end = min(len(all_cols) - 1, target_col_idx + 6)

  eleven_hour_count = 0
  min_interval_found = 99.0
  has_under_11h = False

  for idx in range(window_start, window_end):
    if idx + 1 >= len(all_cols):
      break

    c1 = parse_cell(crew_row.iloc[idx])
    c2 = parse_cell(crew_row.iloc[idx + 1])

    if (
        c1.get("end")
        and c2.get("start")
        and not is_cell_off_day(crew_row.iloc[idx])
        and not is_cell_off_day(crew_row.iloc[idx + 1])
    ):
      rest_h = calculate_rest_hours(c1["end"], c2["start"])
      if rest_h is not None:
        if rest_h < min_interval_found:
          min_interval_found = rest_h

        if rest_h < 11.0:
          has_under_11h = True
        elif 11.0 <= rest_h < 12.0:
          eleven_hour_count += 1

  illegal_reasons = []
  if has_under_11h:
    illegal_reasons.append(f"班間隔不足 11 小時 (最低 {min_interval_found}h)")
  if eleven_hour_count > 1:
    illegal_reasons.append(
        f"7 天內出現 {eleven_hour_count} 次 11~12 小時班間隔 (限 1 次)"
    )

  is_legal = len(illegal_reasons) == 0
  warning_msg = "；".join(illegal_reasons) if illegal_reasons else ""

  return is_legal, warning_msg, {
      "min_interval": (
          min_interval_found if min_interval_found != 99.0 else None
      ),
      "eleven_hr_cnt": eleven_hour_count,
  }


def check_week_has_holiday(target_date_str, date_cols, columns=None):
  """檢查指定日期所在當週 (Sun~Sat) 是否包含國定假日或備註假日"""
  try:
    current_year = date.today().year
    t_m, t_d = map(int, target_date_str.split("/"))
    t_dt = date(current_year, t_m, t_d)
    t_sun = t_dt - timedelta(days=(t_dt.weekday() + 1) % 7)
    t_sat = t_sun + timedelta(days=6)
    week_str = (
        f"{t_sun.month}/{t_sun.day:02d} (日) ~ {t_sat.month}/{t_sat.day:02d} (六)"
    )

    for d_str in date_cols:
      try:
        d_m, d_d = map(int, d_str.split("/"))
        d_dt = date(current_year, d_m, d_d)
        if t_sun <= d_dt <= t_sat:
          if d_str in NATIONAL_HOLIDAYS:
            return True, week_str
          if columns is not None:
            matching_col = next(
                (c for c in columns[2:] if d_str in str(c)), None
            )
            if matching_col and re.search(
                r"[\(（]([^\)）]+)[\)）]", str(matching_col)
            ):
              return True, week_str
      except Exception:
        pass
    return False, week_str
  except Exception:
    return False, ""
