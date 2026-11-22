import glob
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
import openpyxl
import pandas as pd


POS_KEYWORDS = {
    "TD": ["TD", "駕駛"],
    "TM": ["TM", "列車長"],
    "TA": ["TA", "服勤員"],
}


def matches_position(filename: str, pos: str) -> bool:
    """判斷檔名是否符合指定職位（支援英文代號與中文職稱）"""
    up_name = filename.upper()
    keywords = POS_KEYWORDS.get(pos.upper(), [pos.upper()])
    return any(kw.upper() in up_name for kw in keywords)


# ==============================================================================
# 共用工具函式
# ==============================================================================

def format_time_hhmm(t_str: str) -> str:
    """將時間字串統一格式化為 HH:MM 規範 (例如 5:30 -> 05:30)，無效或無時間回傳 '-'"""
    if not t_str or not isinstance(t_str, str):
        return "-"
    s = t_str.strip()
    if s == "-" or ":" not in s:
        return "-"
    parts = s.split(":")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    return s


def clean_shift_code(raw_code) -> str:
    """清洗班別代號字串，去除標籤、時間與前後特殊符號 (如 #, %, *, ＠ 等)"""
    if not raw_code:
        return ""
    code_str = str(raw_code).strip()
    code_str = re.sub(r"(N型變動班|常態固定班)", "", code_str)

    lines = [l.strip() for l in code_str.split("\n") if l.strip()]
    real_codes = []
    for l in lines:
        if not re.match(r"^\d{1,2}:\d{2}$", l) and l not in ["DO1", "DO2", "DO3X", "DO2W", "DO3W", "OGC"]:
            real_codes.append(l)

    if real_codes:
        clean_c = re.sub(r"[^A-Za-z0-9]+$", "", real_codes[0])
        clean_c = re.sub(r"^[^A-Za-z0-9]+", "", clean_c).strip()
        return clean_c.upper()

    clean_c = re.sub(r"[^A-Za-z0-9]+$", "", code_str.replace("\n", ""))
    clean_c = re.sub(r"^[^A-Za-z0-9]+", "", clean_c).strip()
    return clean_c.upper()


def is_non_shift_code(code: str) -> bool:
    """判斷是否為非工作/休假/受訓/公假代號"""
    if not code:
        return True
    c = code.upper()
    non_shift_prefix = (
        "DO", "AL", "SL", "CL", "HL", "OFF", "PAY",
        "FAC", "LEV", "CMP", "DTT", "LUT", "LUTS", "TOWN", "WRSL"
    )
    return c.startswith(non_shift_prefix)


def normalize_date_label(val) -> str:
    """將各式日期/時間格式標籤統一為 MM/DD 乾淨字串"""
    if pd.isna(val):
        return ""
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime("%m/%d")
    s = str(val).strip()
    m = re.search(r"(\d{1,2})/(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}"
    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m_iso:
        return f"{int(m_iso.group(2)):02d}/{int(m_iso.group(3)):02d}"
    return s


def sort_dates_chronologically(dates_set: set) -> list:
    """針對套用日期進行正確時間軸排序 (自動支援跨 12月/1月 大表區間)"""
    parsed = []
    for d in dates_set:
        m = re.search(r"(\d{1,2})/(\d{1,2})", str(d))
        if m:
            parsed.append((int(m.group(1)), int(m.group(2)), str(d)))
        else:
            parsed.append((99, 99, str(d)))

    months = [p[0] for p in parsed if p[0] != 99]
    has_year_boundary = any(m >= 11 for m in months) and any(m <= 2 for m in months)

    def sort_key(item):
        m, d, _ = item
        if has_year_boundary and m <= 2:
            return (m + 12, d)
        return (m, d)

    sorted_items = sorted(parsed, key=sort_key)
    return [item[2] for item in sorted_items]


def time_to_minutes(t_str: str) -> int:
    """將 HH:MM 時間轉為分鐘數以供排序"""
    if not isinstance(t_str, str) or ":" not in t_str:
        return 9999
    try:
        parts = t_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 9999


# ==============================================================================
# 第一階段：產出各單位與職位之《當月班別時間對照表》
# ==============================================================================

def generate_shift_dictionary_for_all(base_folder: str):
    print("==================================================")
    print("    【階段一】北、中、南三單位多職位專屬對照表產出")
    print("==================================================")

    units = {
        "北 (TTN)": "TTN",
        "中 (TTC)": "TTC",
        "南 (TTS)": "TTS"
    }
    positions = ["TD", "TM", "TA"]

    for unit_name, prefix in units.items():
        print("\n--------------------------------------------------")
        print(f"🏢 [對照表產出] 正在處理單位：{unit_name}")
        print("--------------------------------------------------")

        unit_dir = os.path.join(base_folder, "data", prefix)
        if not os.path.exists(unit_dir):
            print(f"  ⚠️ 找不到單位資料夾：data/{prefix}，跳過對照表產出。")
            continue

        mapping_dir = os.path.join(unit_dir, "班別時間對照表")
        os.makedirs(mapping_dir, exist_ok=True)

        all_files = []
        for root, _, files in os.walk(unit_dir):
            if "班別時間對照表" in root or "最新版班表" in root or "每日下載更新檔" in root:
                continue
            for f in files:
                f_upper = f.upper()
                if f.startswith("~$") or f == ".DS_Store":
                    continue
                if "更新" in f_upper or "TTNTA" in f_upper or "TCMSR" in f_upper:
                    if "大表" not in f_upper and "公告" not in f_upper:
                        continue
                if f.lower().endswith((".xls", ".xlsx", ".csv")):
                    all_files.append(os.path.join(root, f))

        print(f"  🔍 搜尋目錄：{unit_dir}")
        print(f"  📂 找到可讀大表檔案總數：{len(all_files)} 個")

        for pos in positions:
            master_candidates = [
                f for f in all_files
                if matches_position(os.path.basename(f), pos)
                and "對照" not in os.path.basename(f)
            ]

            if not master_candidates:
                print(f"  ⚠️ 找不到【{unit_name} - {pos}】的主檔，跳過。")
                continue

            print(f"  📁 鎖定解析檔案 ({len(master_candidates)} 個)：{[os.path.basename(f) for f in master_candidates]}")

            shift_record_dict = {}

            for file_path in master_candidates:
                try:
                    if file_path.endswith(".csv"):
                        try:
                            df = pd.read_csv(file_path, header=None, encoding="utf-8-sig")
                        except Exception:
                            df = pd.read_csv(file_path, header=None, encoding="big5")
                    else:
                        df = pd.read_excel(file_path, header=None)
                except Exception as e:
                    print(f"  ❌ 讀取檔案失敗 ({os.path.basename(file_path)}): {e}")
                    continue

                header_row_idx = None
                for r in range(min(15, len(df))):
                    row_vals = [normalize_date_label(x) for x in df.iloc[r].dropna().values]
                    date_matches = [x for x in row_vals if re.search(r"\d{1,2}/\d{1,2}", x)]
                    if len(date_matches) >= 3:
                        header_row_idx = r
                        break

                if header_row_idx is None:
                    print(f"  ⚠️ 無法定位日期標頭列 ({os.path.basename(file_path)})，跳過。")
                    continue

                day_row_idx = header_row_idx + 1 if header_row_idx + 1 < len(df) else None
                emp_start_row_idx = day_row_idx + 1 if day_row_idx else header_row_idx + 1

                for r in range(emp_start_row_idx, min(emp_start_row_idx + 5, len(df))):
                    if pd.notna(df.iloc[r, 0]) and str(df.iloc[r, 0]).strip():
                        emp_start_row_idx = r
                        break

                dates_raw = df.iloc[header_row_idx, :].values
                days_raw = df.iloc[day_row_idx, :].values if day_row_idx is not None else [None] * len(dates_raw)

                data_cols = []
                for c in range(len(dates_raw)):
                    d_norm = normalize_date_label(dates_raw[c])
                    if re.search(r"\d{1,2}/\d{1,2}", d_norm):
                        data_cols.append(c)

                for row_idx in range(emp_start_row_idx, len(df)):
                    row = df.iloc[row_idx]
                    emp_id = row.iloc[0]
                    if pd.isna(emp_id) or not str(emp_id).strip():
                        continue

                    for col_idx in data_cols:
                        cell_val = row.iloc[col_idx]
                        if pd.isna(cell_val):
                            continue
                        cell_str = str(cell_val).strip()
                        if not cell_str:
                            continue

                        parts = [p.strip() for p in re.split(r"[\r\n]+", cell_str) if p.strip()]
                        if not parts:
                            continue

                        times = []
                        codes = []
                        for p in parts:
                            if re.match(r"^\d{1,2}:\d{2}$", p):
                                times.append(format_time_hhmm(p))
                            else:
                                codes.append(p)

                        date_str = normalize_date_label(dates_raw[col_idx])
                        day_str = (
                            str(days_raw[col_idx]).strip()
                            if day_row_idx and col_idx < len(days_raw) and pd.notna(days_raw[col_idx])
                            else ""
                        )
                        if day_str.upper() in ["NAN", "NONE"]:
                            day_str = ""

                        date_info = f"{date_str}({day_str})" if day_str else str(date_str)

                        for code in codes:
                            clean_c = clean_shift_code(code)
                            if not clean_c or is_non_shift_code(clean_c):
                                continue

                            start_t = times[0] if len(times) > 0 else "-"
                            end_t = times[1] if len(times) > 1 else "-"
                            dur = times[2] if len(times) > 2 else "-"

                            key = (clean_c, start_t, end_t, dur)
                            if key not in shift_record_dict:
                                shift_record_dict[key] = set([date_info])
                            else:
                                shift_record_dict[key].add(date_info)

            if not shift_record_dict:
                print(f"  ⚠️ 【{unit_name} - {pos}】未解析到任何班別資料。")
                continue

            codes_with_valid_times = set(k[0] for k in shift_record_dict.keys() if k[1] != "-")
            filtered_dict = {}
            for key, dates in shift_record_dict.items():
                code, start_t, end_t, dur = key
                if start_t == "-" and code in codes_with_valid_times:
                    continue
                filtered_dict[key] = dates

            rows_result = []
            for (code, start_t, end_t, dur), dates_set in filtered_dict.items():
                sorted_dates = sort_dates_chronologically(dates_set)
                date_str_display = ", ".join(sorted_dates)
                rows_result.append({
                    "班別代號": code,
                    "上班時間": start_t,
                    "下班時間": end_t,
                    "預估工時": dur,
                    "適用日期/星期": date_str_display
                })

            df_result = pd.DataFrame(rows_result).drop_duplicates()
            df_result["time_mins"] = df_result["上班時間"].apply(time_to_minutes)
            df_result = df_result.sort_values(by=["班別代號", "time_mins"]).drop(columns=["time_mins"])

            output_filename = os.path.join(mapping_dir, f"{prefix}_{pos}_當月班別時間對照表.xlsx")
            df_result.to_excel(output_filename, index=False)
            print(f"    ✅ 成功產出：{os.path.basename(output_filename)} (存於 {mapping_dir})")

    print("\n==================================================")
    print("    🎉 【階段一】所有單位與職位的時間對照表製作完成！")
    print("==================================================\n")


# ==============================================================================
# 第二階段：讀取對照表與更新檔，覆寫大表並輸出新版班表
# ==============================================================================

def load_shift_mapping(mapping_file_path: str):
    """讀取班別時間對照表，建立特定日期對照字典與全域備用字典"""
    wb = openpyxl.load_workbook(mapping_file_path, data_only=True)
    ws = wb.active

    header_row = [cell.value for cell in ws[1]]
    col_map = {}
    for idx, col_name in enumerate(header_row):
        if col_name:
            col_map[str(col_name).strip()] = idx

    shift_dict = {}
    global_shift_dict = {}

    for row in ws.iter_rows(min_row=2, values_only=True):
        if "班別代號" in col_map:
            code_raw = row[col_map["班別代號"]]
            code = str(code_raw).strip().upper() if code_raw is not None else None
            start_time = str(row[col_map["上班時間"]]).strip() if "上班時間" in col_map and row[col_map["上班時間"]] is not None else ""
            end_time = str(row[col_map["下班時間"]]).strip() if "下班時間" in col_map and row[col_map["下班時間"]] is not None else ""
            work_hours = str(row[col_map["預估工時"]]).strip() if "預估工時" in col_map and row[col_map["預估工時"]] is not None else ""
            date_info = str(row[col_map["適用日期/星期"]]).strip() if "適用日期/星期" in col_map and row[col_map["適用日期/星期"]] is not None else ""
        else:
            code_raw = row[0]
            code = str(code_raw).strip().upper() if code_raw is not None else None
            start_time = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            end_time = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
            work_hours = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
            date_info = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""

        if not code or code in ["NONE", "NAN"]:
            continue

        info = {
            "start": format_time_hhmm(start_time),
            "end": format_time_hhmm(end_time),
            "hours": work_hours
        }

        if code not in global_shift_dict or (global_shift_dict[code]["start"] == "-" and info["start"] != "-"):
            global_shift_dict[code] = info

        if date_info and "全年固定" not in date_info:
            found_dates = re.findall(r"(\d{1,2})/(\d{1,2})", date_info)
            for m, d in found_dates:
                date_key = f"{int(m):02d}/{int(d):02d}"
                dict_key = (code, date_key)
                if dict_key not in shift_dict or (shift_dict[dict_key]["start"] == "-" and info["start"] != "-"):
                    shift_dict[dict_key] = info

    return shift_dict, global_shift_dict


def parse_daily_update_file(file_path: str) -> dict:
    """精準解析每日下載更新檔，排除元資料干擾"""
    if os.path.basename(file_path).startswith("~$") or os.path.basename(file_path) == ".DS_Store":
        return {}

    if file_path.endswith(".csv"):
        try:
            df = pd.read_csv(file_path, header=None, encoding="utf-8-sig")
        except Exception:
            df = pd.read_csv(file_path, header=None, encoding="big5")
    elif file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path, header=None, engine="openpyxl")
    elif file_path.endswith(".xls"):
        df = pd.read_excel(file_path, header=None)
    else:
        return {}

    schedule_data = {}
    r = 0
    while r < len(df):
        row_vals = df.iloc[r].tolist()
        date_cols = {}

        for c_idx, val in enumerate(row_vals):
            if pd.notna(val):
                val_str = str(val).strip()
                if "UPDATE" in val_str.upper() or "更新" in val_str or "~" in val_str:
                    continue
                match = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", val_str)
                if match:
                    m, d = int(match.group(1)), int(match.group(2))
                    if 1 <= m <= 12 and 1 <= d <= 31:
                        date_cols[c_idx] = f"{m:02d}/{d:02d}"

        if len(date_cols) >= 3:
            curr_r = r + 1
            while curr_r < len(df):
                emp_id = df.iloc[curr_r, 0]

                if pd.isna(emp_id) or str(emp_id).strip() == "":
                    next_row_vals = [str(x).strip() for x in df.iloc[curr_r].tolist() if pd.notna(x)]
                    date_matches_in_next = sum(
                        1 for x in next_row_vals
                        if re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", x)
                        and "UPDATE" not in x.upper() and "更新" not in x and "~" not in x
                    )
                    if date_matches_in_next >= 3:
                        r = curr_r - 1
                        break
                    curr_r += 1
                    continue

                emp_id_str = str(emp_id).strip()
                digits = re.findall(r"\d+", emp_id_str)
                if digits:
                    emp_id_clean = digits[0].zfill(6)

                    for col_idx, date_str in date_cols.items():
                        raw_shift = df.iloc[curr_r, col_idx]
                        if pd.notna(raw_shift) and str(raw_shift).strip() != "":
                            shift_code = clean_shift_code(raw_shift)
                            if shift_code:
                                schedule_data[(emp_id_clean, date_str)] = shift_code

                curr_r += 1
            r = curr_r
        else:
            r += 1

    return schedule_data


def detect_target_year_month(master_file: str, date_to_col: dict) -> str:
    """自動判讀符合系統要求的 YYYY-MM 格式（例如 2026-12）"""
    base_name = os.path.basename(master_file)
    parent_dir = os.path.basename(os.path.dirname(master_file))
    check_str = f"{parent_dir}/{base_name}"

    match_ym = re.search(r"(20\d{2})年(\d{1,2})月", check_str)
    if match_ym:
        return f"{match_ym.group(1)}-{int(match_ym.group(2)):02d}"

    year_match = re.search(r"(20\d{2})", check_str)
    year = year_match.group(1) if year_match else str(datetime.now().year)

    match_month = re.search(r"(\d{1,2})\s*月", check_str)
    if match_month:
        month = int(match_month.group(1))
    else:
        months_found = []
        for date_str in date_to_col.keys():
            parts = date_str.split("/")
            if len(parts) == 2:
                months_found.append(int(parts[0]))
        if months_found:
            month_counts = Counter(months_found)
            month = month_counts.most_common(1)[0][0]
        else:
            month = datetime.now().month

    return f"{year}-{month:02d}"


def process_single_position(unit_name: str, prefix: str, pos: str, master_file: str, update_files: list, unit_dir: str):
    print("\n--------------------------------------------------")
    print(f"    開始處理【{unit_name}】職位：【 {pos} 】")
    print("--------------------------------------------------")

    mapping_dir = os.path.join(unit_dir, "班別時間對照表")
    ref_file = os.path.join(mapping_dir, f"{prefix}_{pos}_當月班別時間對照表.xlsx")
    if not os.path.exists(ref_file):
        possible_refs = [
            f for f in glob.glob(os.path.join(mapping_dir, f"*{pos}*對照表*.xlsx"))
            if not os.path.basename(f).startswith("~$")
        ]
        if possible_refs:
            ref_file = possible_refs[0]
        else:
            print(f"❌ 錯誤：找不到【{unit_name} - {pos}】的專屬對照表！")
            return

    print(f"📖 讀取專屬對照表：{os.path.basename(ref_file)}")
    shift_dict, global_shift_dict = load_shift_mapping(ref_file)
    print(f"📊 載入大表主檔：{os.path.basename(master_file)}")

    all_updates = {}
    for update_file in update_files:
        fname = os.path.basename(update_file)
        if fname.startswith("~$") or fname == ".DS_Store":
            continue
        print(f"📄 讀取更新檔：{fname}")
        data = parse_daily_update_file(update_file)
        print(f"    └─ 成功擷取出 {len(data)} 筆排班紀錄")
        all_updates.update(data)

    df_master = pd.read_excel(master_file, header=None)

    date_to_col = {}
    header_row_idx = 3
    for r_check in range(min(10, len(df_master))):
        row_vals = df_master.iloc[r_check].tolist()
        matches = [re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", str(v)) for v in row_vals if pd.notna(v)]
        valid_matches = [m for m in matches if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31]
        if len(valid_matches) >= 3:
            header_row_idx = r_check
            break

    row_vals = df_master.iloc[header_row_idx].tolist()
    for c_idx, val in enumerate(row_vals):
        if pd.notna(val):
            val_str = str(val).strip()
            match = re.search(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)", val_str)
            if match:
                m, d = int(match.group(1)), int(match.group(2))
                if 1 <= m <= 12 and 1 <= d <= 31:
                    date_to_col[f"{m:02d}/{d:02d}"] = c_idx

    target_ym = detect_target_year_month(master_file, date_to_col)

    emp_to_row = {}
    emp_start_idx = header_row_idx + 2
    for r_idx in range(emp_start_idx, len(df_master)):
        val = df_master.iloc[r_idx, 0]
        if pd.notna(val):
            digits = re.findall(r"\d+", str(val).strip())
            if digits:
                emp_id_clean = digits[0].zfill(6)
                emp_to_row[emp_id_clean] = r_idx

    updated_count = 0
    d2w_preserved_count = 0

    for (emp_id, date_str), code in all_updates.items():
        if emp_id in emp_to_row and date_str in date_to_col:
            r = emp_to_row[emp_id]
            c = date_to_col[date_str]

            old_val = str(df_master.iloc[r, c]) if pd.notna(df_master.iloc[r, c]) else ""
            d2w_match = re.search(r"\b(DO?\d*W|D\d*W|OGC)\b", old_val, re.IGNORECASE)
            d2w_tag = d2w_match.group(1).upper() if d2w_match else ""

            upper_code = code.upper()
            match_key = (upper_code, date_str)

            info = None
            if match_key in shift_dict and shift_dict[match_key]["start"] != "-":
                info = shift_dict[match_key]
            elif upper_code in global_shift_dict and global_shift_dict[upper_code]["start"] != "-":
                info = global_shift_dict[upper_code]

            if info and info["start"] != "-":
                if d2w_tag:
                    cell_content = f"{info['start']}\n{d2w_tag}\n{code}\n{info['end']}\n{info['hours']}"
                    d2w_preserved_count += 1
                else:
                    cell_content = f"{info['start']}\n{code}\n{info['end']}\n{info['hours']}"
            else:
                cell_content = f"{d2w_tag}\n{code}".strip() if d2w_tag else code
                if d2w_tag:
                    d2w_preserved_count += 1

            df_master.iloc[r, c] = cell_content
            updated_count += 1

    print(f"🎯 【{unit_name} - {pos}】成功覆寫 {updated_count} 個排班儲存格！(保留 {d2w_preserved_count} 筆 DO2W 標記)")

    output_base_dir = os.path.join(unit_dir, "最新版班表")
    output_sub_dir = os.path.join(output_base_dir, target_ym)
    if not os.path.exists(output_sub_dir):
        os.makedirs(output_sub_dir, exist_ok=True)

    output_filename = f"{prefix}_{pos}.xlsx"
    output_path = os.path.join(output_sub_dir, output_filename)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_master.to_excel(writer, index=False, header=False)
        ws = writer.sheets["Sheet1"]
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and "\n" in str(cell.value):
                    cell.alignment = openpyxl.styles.Alignment(wrap_text=True, horizontal="center", vertical="center")

    print(f"✅ 【{unit_name} - {pos} ({target_ym})】更新完成！已儲存至：{output_path}")


# ==============================================================================
# 第三階段：雙分支雲端同步
# ==============================================================================

def _cleanup_ds_store(root_dir: str):
    """移除 .DS_Store 避免無意義的 Git 合併衝突"""
    for dirpath, _, filenames in os.walk(root_dir):
        if ".git" in dirpath.split(os.sep):
            continue
        for fn in filenames:
            if fn == ".DS_Store":
                try:
                    os.remove(os.path.join(dirpath, fn))
                except OSError:
                    pass


def _safe_merge_branch(branch: str):
    """抓取並合併指定遠端分支，若遇到衝突自動保留本地版本 (--ours) 並完成合併"""
    subprocess.run(["git", "fetch", "origin", branch], check=True)
    merge_res = subprocess.run(
        ["git", "merge", f"origin/{branch}", "--no-edit", "--allow-unrelated-histories", "-X", "ours"],
        capture_output=True,
        text=True,
    )
    if merge_res.returncode != 0:
        print(f"⚠️ 合併 {branch} 出現衝突，自動套用本地版本 (-X ours) 並完成提交...")
        subprocess.run(["git", "checkout", "--ours", "."], check=False)
        subprocess.run(["git", "add", "-A"], check=False)
        subprocess.run(["git", "commit", "--no-edit"], check=False)


def auto_git_push(script_dir: str):
    print("\n--------------------------------------------------")
    print("🚀 正在安全同步更新至 GitHub (TTN-duty 雙分支)...")
    print("--------------------------------------------------")
    try:
        os.chdir(script_dir)
        _cleanup_ds_store(script_dir)

        subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/leooel911/TTN-duty.git"], check=False)
        subprocess.run(["git", "rebase", "--abort"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(["git", "merge", "--abort"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        subprocess.run(["git", "add", "data/"], check=True)

        commit_msg = f"Auto-update active schedule {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=False)

        print("📥 正在從 origin 抓取 main 最新狀態並進行安全合併...")
        _safe_merge_branch("main")
        print("☁️ 正在推送至正式環境 (main)...")
        subprocess.run(["git", "push", "origin", "main"], check=True)

        print("📥 正在從 origin 抓取 testing 最新狀態並進行安全合併...")
        _safe_merge_branch("testing")
        print("☁️ 正在推送至測試環境 (testing)...")
        subprocess.run(["git", "push", "origin", "HEAD:testing"], check=True)

        print("✨ 【雙分支安全同步完成】")
    except Exception as e:
        print(f"💡 提示：自動同步 GitHub 狀態：{e}")


def update_all_positions(base_folder: str):
    print("==================================================")
    print("    【階段二】北、中、南三單位多職位全自動更新程式")
    print("==================================================")

    units = {
        "北 (TTN)": "TTN",
        "中 (TTC)": "TTC",
        "南 (TTS)": "TTS"
    }
    positions = ["TD", "TM", "TA"]
    processed_any = False

    for unit_name, prefix in units.items():
        print("\n--------------------------------------------------")
        print(f"🏢 [班表更新] 正在處理單位：{unit_name}")
        print("--------------------------------------------------")

        unit_dir = os.path.join(base_folder, "data", prefix)
        if not os.path.exists(unit_dir):
            print(f"  ⚠️ 找不到單位資料夾：data/{prefix}")
            continue

        master_dir = None
        update_dir = None
        for sub_name in os.listdir(unit_dir):
            sub_path = os.path.join(unit_dir, sub_name)
            if os.path.isdir(sub_path):
                if "20號大表" in sub_name or "大表" in sub_name:
                    master_dir = sub_path
                elif "更新檔" in sub_name or "更新" in sub_name:
                    update_dir = sub_path

        print(f"  🔍 [DEBUG] 找到大表目錄：{master_dir}")
        print(f"  🔍 [DEBUG] 找到更新檔目錄：{update_dir}")

        raw_master_files = glob.glob(os.path.join(master_dir, "*.*")) if master_dir else []
        raw_update_files = (
            glob.glob(os.path.join(update_dir, "**", "*.*"), recursive=True)
            if update_dir
            else glob.glob(os.path.join(unit_dir, "*.*"))
        )

        master_files = [
            f for f in raw_master_files
            if not os.path.basename(f).startswith("~$") and os.path.basename(f) != ".DS_Store"
        ]
        update_files = [
            f for f in raw_update_files
            if not os.path.basename(f).startswith("~$") and os.path.basename(f) != ".DS_Store"
        ]

        for pos in positions:
            master_candidates = [
                f for f in master_files
                if matches_position(os.path.basename(f), pos)
                and "更新" not in os.path.basename(f)
                and "對照" not in os.path.basename(f)
            ]

            if not master_candidates:
                print(f"  ⚠️ 找不到【{unit_name} - {pos}】的大表主檔")
                continue

            master_file = master_candidates[0]

            update_candidates = [
                f for f in update_files
                if matches_position(os.path.basename(f), pos)
                and "對照" not in os.path.basename(f)
            ]

            if update_candidates:
                processed_any = True
                process_single_position(unit_name, prefix, pos, master_file, update_candidates, unit_dir)
            else:
                print(f"  ⚠️ 找不到【{unit_name} - {pos}】的對應更新檔")

    if not processed_any:
        print("💡 提示：未找到任何對應單位的更新檔。")

    print("\n==================================================")
    print("    🎉 檢查完畢，準備執行雙分支雲端同步！")
    print("==================================================")
    auto_git_push(base_folder)


# ==============================================================================
# 主進入點：一鍵依序執行「產出對照表 -> 更新大表 -> GitHub 雙分支同步」
# ==============================================================================

def run_full_pipeline():
    base_folder = os.path.dirname(os.path.abspath(__file__))
    if not base_folder:
        base_folder = os.getcwd()

    generate_shift_dictionary_for_all(base_folder)
    update_all_positions(base_folder)


if __name__ == "__main__":
    run_full_pipeline()