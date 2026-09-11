def parse_structured_log(raw_log: Any) -> Dict[str, str]:
    """高靈敏度解析日誌：有查到大表姓名顯示『員編 (姓名)』，沒查到則顯示登入時的原始資料"""
    timestamp = "--"
    user_info = "系統/訪客"
    unit_info = "全站"
    category = "一般操作"
    action_detail = ""

    # 常見無效/非人名詞彙黑名單
    INVALID_USERS = {
        "系統/訪客", "訪客", "", "NONE", "NAN", "由早至晚", 
        "依 SIGN-IN 時間", "依 SIGN-IN 時間 (由早至晚)", "服勤員", "列車長", 
        "駕駛", "TTN", "KHH", "TXG", "TNA", "全站", "未命名"
    }

    if isinstance(raw_log, dict):
        timestamp = str(raw_log.get("timestamp", raw_log.get("時間", "--"))).strip()
        act_val = str(raw_log.get("action", raw_log.get("動作", ""))).strip()
        dtl_val = str(raw_log.get("detail", raw_log.get("詳細日誌與動作內容", ""))).strip()

        # 欄位錯位修正
        if dtl_val.lower() in ["nan", "none", ""]:
            action_detail = act_val if act_val.lower() not in ["nan", "none", ""] else "系統操作紀錄"
        else:
            action_detail = dtl_val

        # 抓取登入時寫入的原始 User 資料
        user_info = str(raw_log.get("user", raw_log.get("操作者", raw_log.get("操作者/員編", "系統/訪客")))).strip()
        unit_info = str(raw_log.get("unit", raw_log.get("單位", "全站"))).strip()
        category = str(raw_log.get("category", raw_log.get("類別", act_val or "一般操作"))).strip()
    else:
        raw_str = str(raw_log).strip()
        parts = [p.strip() for p in raw_str.split("|")]
        if len(parts) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}", parts[0]):
            timestamp = parts[0]
            action_detail = " | ".join(parts[1:])
        else:
            action_detail = raw_str

    # 1. 自動修正與歸類【動作類別 Category】
    full_text = f"{category} {action_detail}"
    if "使用者登入" in full_text:
        category = "帳號登入"
    elif "管理員登入" in full_text or "登入後台" in full_text:
        category = "管理員操作"
    elif "換班" in full_text:
        category = "換班快篩"
    elif "換假" in full_text:
        category = "換假快篩"
    elif "繪製" in full_text or "圖檔" in full_text or "班表" in full_text:
        category = "月班表繪製"
    elif "工單" in full_text or "回報" in full_text:
        category = "問題與申請"
    elif category in ["一般操作", "", "nan", "NaN", "None"]:
        category = "系統操作"

    # 2. 自動解析【營運單位 Unit】
    unit_match = re.search(r"單位[:：]\s*([A-Za-z0-9_]+)", action_detail)
    if unit_match and unit_match.group(1).upper() not in ["NAN", "NONE"]:
        unit_info = unit_match.group(1).upper()

    # 3. 保底：若 user_info 為舊的無效字串，從內文自動提取員編
    if user_info.upper() in INVALID_USERS or user_info in INVALID_USERS:
        emp_code_match = re.search(r"\b([A-Za-z]\d{6})\b", action_detail)
        login_match = re.search(r"使用者登入系統[:：]\s*([^\s\(]+)", action_detail)
        crew_match = re.search(r"(?:組員|目標組員|解析組員|操作者|員編)[:：]\s*([^\s\|,\(\)]+)", action_detail)

        if emp_code_match:
            user_info = emp_code_match.group(1).upper()
        elif login_match and login_match.group(1).strip().upper() not in INVALID_USERS:
            user_info = login_match.group(1).strip().upper()
        elif crew_match and crew_match.group(1).strip().upper() not in INVALID_USERS:
            user_info = crew_match.group(1).strip()
        elif "管理員" in action_detail:
            user_info = "ADMIN (管理員)"
        else:
            user_info = "系統/訪客"

    # 4. 🔥 核心比對邏輯：
    # 判斷有無 7 碼標準員編，若向 Excel 大表有查到名字 -> 顯示「員編 (姓名)」
    # 若查無名字 -> 原封不動保留登入時寫入的原始資料 (例如 VIP_USER (A) 或 A026925)
    emp_match = re.search(r"\b([A-Za-z]\d{6})\b", user_info)
    if emp_match:
        clean_emp_id = emp_match.group(1).upper()
        emp_name = get_employee_name(unit_info, clean_emp_id)
        if emp_name:
            user_info = f"{clean_emp_id} ({emp_name})"

    return {
        "時間 (Timestamp)": timestamp,
        "操作者/員編 (User)": user_info,
        "營運單位 (Unit)": unit_info,
        "操作類別 (Category)": category,
        "詳細日誌紀錄 (Log Detail)": action_detail,
    }
