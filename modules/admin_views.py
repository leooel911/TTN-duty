def parse_structured_log(raw_log: Any) -> Dict[str, str]:
    """高靈敏度解析日誌條目，自動修正欄位錯位、nan無效值與精準提取員編"""
    timestamp = "--"
    user_info = "系統/訪客"
    unit_info = "全站"
    category = "一般操作"
    action_detail = ""

    # 常見非人名/非員編之雜訊詞彙黑名單
    INVALID_USERS = {
        "系統/訪客", "訪客", "", "NONE", "NAN", "NONE", "NAN", "由早至晚", 
        "依 SIGN-IN 時間", "依 SIGN-IN 時間 (由早至晚)", "服勤員", "列車長", 
        "駕駛", "TTN", "KHH", "TXG", "TNA", "全站", "未命名"
    }

    if isinstance(raw_log, dict):
        timestamp = str(raw_log.get("timestamp", raw_log.get("時間", "--")))
        action_detail = str(raw_log.get("detail", raw_log.get("詳細日誌與動作內容", raw_log.get("action", raw_log.get("動作", ""))))).strip()
        user_info = str(raw_log.get("user", raw_log.get("操作者", raw_log.get("操作者/員編", "系統/訪客")))).strip()
        unit_info = str(raw_log.get("unit", raw_log.get("單位", "全站"))).strip()
        category = str(raw_log.get("category", raw_log.get("類別", raw_log.get("action", raw_log.get("動作", "一般操作"))))).strip()
    else:
        raw_str = str(raw_log).strip()
        parts = [p.strip() for p in raw_str.split("|")]
        if len(parts) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}", parts[0]):
            timestamp = parts[0]
            action_detail = " | ".join(parts[1:])
        else:
            action_detail = raw_str

    # 1. 處理 nan / None 錯位問題：若詳細內容為 nan，則將 category 的文字移過來
    if action_detail.lower() in ["nan", "none", ""]:
        if category.lower() not in ["nan", "none", ""]:
            action_detail = category
        else:
            action_detail = "系統操作紀錄"

    # 2. 自動修正與歸類【動作類別 Category】
    full_text_for_cat = f"{category} {action_detail}"
    if "使用者登入" in full_text_for_cat:
        category = "帳號登入"
    elif "管理員登入" in full_text_for_cat or "登入後台" in full_text_for_cat:
        category = "管理員操作"
    elif "換班" in full_text_for_cat:
        category = "換班快篩"
    elif "換假" in full_text_for_cat:
        category = "換假快篩"
    elif "繪製" in full_text_for_cat or "圖檔" in full_text_for_cat or "班表" in full_text_for_cat:
        category = "月班表繪製"
    elif "工單" in full_text_for_cat or "回報" in full_text_for_cat:
        category = "問題與申請"
    elif category in ["一般操作", ""]:
        category = "系統操作"

    # 3. 自動解析【營運單位 Unit】
    unit_match = re.search(r"單位[:：]\s*([A-Za-z0-9_]+)", action_detail)
    if unit_match and unit_match.group(1).upper() not in ["NAN", "NONE"]:
        unit_info = unit_match.group(1).upper()

    # 4. 高靈敏度比對與修正【操作者 / 員編 User】
    if user_info.upper() in INVALID_USERS or user_info in INVALID_USERS:
        full_text = f"{action_detail} {category}"
        
        # Priority A: 標準 7 碼員編 (如 A026925, A021987, A023300)
        emp_code_match = re.search(r"\b([A-Za-z]\d{6})\b", full_text)
        # Priority B: 使用者登入系統: A026925
        login_match = re.search(r"使用者登入系統[:：]\s*([^\s\(]+)", full_text)
        # Priority C: 組員/目標組員/解析組員/操作者/員編: XXX
        crew_match = re.search(r"(?:組員|目標組員|解析組員|操作者|員編)[:：]\s*([^\s\|,\(\)]+)", full_text)

        if emp_code_match:
            user_info = emp_code_match.group(1).upper()
        elif login_match and login_match.group(1).strip().upper() not in INVALID_USERS:
            user_info = login_match.group(1).strip().upper()
        elif crew_match and crew_match.group(1).strip().upper() not in INVALID_USERS:
            user_info = crew_match.group(1).strip()
        elif "管理員" in full_text:
            user_info = "ADMIN (管理員)"
        else:
            user_info = "系統/訪客"

    return {
        "時間 (Timestamp)": timestamp,
        "操作者/員編 (User)": user_info,
        "營運單位 (Unit)": unit_info,
        "操作類別 (Category)": category,
        "詳細日誌紀錄 (Log Detail)": action_detail,
    }
