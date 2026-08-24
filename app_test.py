def merge_update_file_with_mapping(base_path, update_df):
    """具備自動清除特殊符號（#、% 等）與智慧對照容錯的合併引擎"""
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    status_text.markdown('<div class="loading-status-text">階段 1/4：正在初始化符號過濾與智慧對照引擎...</div>', unsafe_allow_html=True)
    progress_bar.progress(20)
    time.sleep(0.2)

    if not os.path.exists(base_path):
        status_text.empty()
        progress_bar.empty()
        return update_df
    
    base_raw = pd.read_excel(base_path, header=None)
    shift_map = load_shift_mapping_dict()
    
    status_text.markdown('<div class="loading-status-text">階段 2/4：動態掃描基準大表與更新檔的表頭、日期欄位...</div>', unsafe_allow_html=True)
    progress_bar.progress(45)
    time.sleep(0.2)

    # 1. 動態尋找基準檔表頭與日期欄位
    base_header_row = -1
    base_date_col_map = {}
    for r_idx in range(min(6, len(base_raw))):
        row_vals = [str(val).strip() for val in base_raw.iloc[r_idx].values]
        date_count = sum(1 for val in row_vals if re.search(r'\d{1,2}/\d{1,2}', val))
        if date_count >= 3:
            base_header_row = r_idx
            break
    if base_header_row == -1: base_header_row = 3

    for c_idx, val in enumerate(base_raw.iloc[base_header_row].values):
        m = re.search(r'(\d+/\d+)', str(val))
        if m:
            clean_d = f"{int(m.group(1).split('/')[0])}/{int(m.group(1).split('/')[1])}"
            base_date_col_map[clean_d] = c_idx

    # 建立基準檔員編對應表（純數字萃取）
    base_emp_row_map = {}
    for r_idx in range(base_header_row + 1, len(base_raw)):
        raw_emp = str(base_raw.iloc[r_idx, 0]).strip()
        if raw_emp and raw_emp.upper() != "NAN":
            pure_emp = re.sub(r'\D', '', raw_emp)
            if pure_emp: base_emp_row_map[pure_emp] = r_idx

    # 2. 動態尋找更新檔表頭與日期欄位
    update_header_row = -1
    update_date_col_map = {}
    for r_idx in range(min(6, len(update_df))):
        row_vals = [str(val).strip() for val in update_df.iloc[r_idx].values]
        date_count = sum(1 for val in row_vals if re.search(r'\d{1,2}/\d{1,2}', val))
        if date_count >= 2:
            update_header_row = r_idx
            break
    if update_header_row == -1: update_header_row = 0

    for c_idx, val in enumerate(update_df.iloc[update_header_row].values):
        m = re.search(r'(\d+/\d+)', str(val))
        if m:
            clean_d = f"{int(m.group(1).split('/')[0])}/{int(m.group(1).split('/')[1])}"
            update_date_col_map[clean_d] = c_idx

    bridge_col_mapping = {}
    for d_str, b_c_idx in base_date_col_map.items():
        if d_str in update_date_col_map:
            bridge_col_mapping[b_c_idx] = update_date_col_map[d_str]

    status_text.markdown('<div class="loading-status-text">階段 3/4：正在清除 #、% 等特殊符號並執行對照表查詢...</div>', unsafe_allow_html=True)
    progress_bar.progress(75)

    start_up_row = update_header_row + 1
    for r_idx in range(start_up_row, len(update_df)):
        raw_up_emp = str(update_df.iloc[r_idx, 0]).strip()
        if not raw_up_emp or raw_up_emp.upper() == "NAN": continue
        
        pure_up_emp = re.sub(r'\D', '', raw_up_emp)
        if pure_up_emp not in base_emp_row_map: continue
            
        target_row_idx = base_emp_row_map[pure_up_emp]
        
        for b_c_idx, u_c_idx in bridge_col_mapping.items():
            up_val = update_df.iloc[r_idx, u_c_idx]
            if not pd.isna(up_val):
                up_val_str = str(up_val).strip()
                if not up_val_str or up_val_str.lower() in [".", "nan", "none"]: continue
                
                # 【核心修改】自動過濾並清除代碼中的 #、% 或其他特殊符號，還原純代碼
                # 例如將 "NH5902#" 或 "NH0541%" 清理成 "NH5902" 或 "NH0541"
                clean_code = re.sub(r'[#%]', '', up_val_str).strip().upper()
                
                # [核心邏輯] 1. 先從對照表（窗口3）查詢淨化後的代碼
                if clean_code in shift_map:
                    info = shift_map[clean_code]
                    # 即使原代碼有帶 # 或 %，我們仍可選擇在排班表中保留原始外觀或直接帶入時間
                    # 這裡我們將格式化帶入標準完整時間結構
                    formatted_cell = f"{info['start']}\n\n{clean_code}\n{info['end']}\n{info['hours']}"
                    base_raw.iloc[target_row_idx, b_c_idx] = formatted_cell
                else:
                    # [核心邏輯] 2. 若對照表中找不到，直接以更新檔原始字串寫入
                    base_raw.iloc[target_row_idx, b_c_idx] = up_val_str

    progress_bar.progress(100)
    status_text.markdown('<div class="loading-status-text">階段 4/4：符號過濾與合併對應完成！</div>', unsafe_allow_html=True)
    time.sleep(0.3)

    base_raw.to_excel(base_path, index=False, header=False)
    status_text.empty()
    progress_bar.empty()
    
    return pd.read_excel(base_path, header=base_header_row)
