from datetime import datetime, timedelta

def calculate_rest_hours(sign_out_str, next_sign_in_str):
    """
    計算 Sign-Out 到隔日 Sign-In 的休息時間 (小時)
    """
    if not sign_out_str or not next_sign_in_str or "--:--" in (sign_out_str, next_sign_in_str):
        return None
    try:
        so_h, so_m = map(int, sign_out_str.split(":"))
        si_h, si_m = map(int, next_sign_in_str.split(":"))
        
        # 假設 Sign-Out 是當天，Sign-In 是隔天
        so_dt = datetime(2026, 1, 1, so_h, so_m)
        si_dt = datetime(2026, 1, 2, si_h, si_m)
        
        # 若 Sign-Out 比 Sign-In 早很多 (例如 Sign-Out 08:00, 隔日 Sign-In 20:00)，代表跨越更長時間
        diff_hours = (si_dt - so_dt).total_seconds() / 3600.0
        return round(diff_hours, 1)
    except:
        return None

def check_shift_legality(crew_row, target_col_idx, all_cols):
    """
    驗證組員排班是否符合：
    1. 連續出勤 < 7 天
    2. 班間隔 >= 12h (允許 7 天內 1 次 11h~12h)
    
    返回: (is_legal: bool, warning_msg: str, info_dict: dict)
    """
    from modules.utils import parse_cell, is_cell_off_day

    # 1. 計算前後 7 天的班間隔與 11h 特例次數
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
        
        # 當兩天都有出勤時間時才計算班間隔
        if c1.get("end") and c2.get("start") and not is_cell_off_day(crew_row.iloc[idx]) and not is_cell_off_day(crew_row.iloc[idx + 1]):
            rest_h = calculate_rest_hours(c1["end"], c2["start"])
            if rest_h is not None:
                if rest_h < min_interval_found:
                    min_interval_found = rest_h
                
                if rest_h < 11.0:
                    has_under_11h = True
                elif 11.0 <= rest_h < 12.0:
                    eleven_hour_count += 1

    # 2. 檢驗合規性
    illegal_reasons = []
    
    if has_under_11h:
        illegal_reasons.append(f"班間隔不足 11 小時 (最低 {min_interval_found}h)")
    if eleven_hour_count > 1:
        illegal_reasons.append(f"7 天內出現 {eleven_hour_count} 次 11~12 小時班間隔 (限 1 次)")

    is_legal = len(illegal_reasons) == 0
    warning_msg = "；".join(illegal_reasons) if illegal_reasons else ""

    return is_legal, warning_msg, {
        "min_interval": min_interval_found if min_interval_found != 99.0 else None,
        "eleven_hr_cnt": eleven_hour_count
    }
