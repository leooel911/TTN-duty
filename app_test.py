# ------------------ 修正前（原程式碼問題段落） ------------------
# work_count = 0
# for c_i in range(start_check_idx, end_check_idx + 1):
#     if cell_c["start"] or (not ("DO" in cell_c_raw or "D2W" in cell_c_raw)):
#         work_count += 1

# ------------------ 修正後（計算精準連續上班天數） ------------------
max_consecutive_streak = 0
current_streak = 0

start_check_idx = max(2, target_col_idx - 5)
end_check_idx = min(len(row) - 1, target_col_idx + 5)

for c_i in range(start_check_idx, end_check_idx + 1):
    cell_c_raw = str(row.iloc[c_i]).upper()
    cell_c = parse_cell(row.iloc[c_i])
    
    # 判斷當天是否為休假／請假 (DO, D2W, PAY, FAC 等)
    is_off_day = any(k in cell_c_raw for k in ["DO", "D2W", "PAY", "FAC", "AL", "SL", "CL"]) or (cell_c["train"] in ["DO", "D2W", "PAY", "FAC"])
    
    if not is_off_day:
        current_streak += 1
        if current_streak > max_consecutive_streak:
            max_consecutive_streak = current_streak
    else:
        current_streak = 0

raw_candidates.append({
    "員編": emp_id,
    "姓名": emp_name,
    "想休日": target_date,
    "想休狀態": raw_target_str.split("\n")[0] if raw_target_str else "DO",
    "還休日": return_date,
    "還假車次": translate_train_code(parsed_return["train"]),
    "Sign-In": parsed_return["start"],
    "Sign-Out": parsed_return["end"],
    "工時": parsed_return["hours"],
    "長班": is_long,
    "非正線": is_non_line,
    "連續上班天數": max_consecutive_streak  # 這裡帶入計算出的最長連續天數
})
