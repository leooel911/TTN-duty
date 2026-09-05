import os
import re
import streamlit as st
from datetime import date, timedelta
from config import UNITS, NATIONAL_HOLIDAYS, LEAVE_CODES
from modules.utils import (
    get_file_mtime_str, is_module_maintenance, log_activity, 
    safe_read_excel, parse_cell, translate_train_code, is_town_shift, is_overtime,
    is_cell_off_day, calculate_rest_hours, check_shift_legality, check_week_has_holiday
)
from modules.services import (
    get_current_role_files, get_schedule_range, process_file_data, 
    calculate_consecutive_work_days
)
from modules.drawing import render_schedule_figure
from modules.components import render_zoomable_image, show_crew_schedule_modal

# --- 通用日期選單格式化函式 (對齊 NATIONAL_HOLIDAYS 與 Excel 欄位備註) ---
def get_date_label(d_str, columns=None):
    holiday_name = NATIONAL_HOLIDAYS.get(d_str)
    if not holiday_name and columns is not None:
        matching_col = next((c for c in columns[2:] if d_str in str(c)), None)
        if matching_col:
            col_raw = str(matching_col)
            name_match = re.search(r'[\(（]([^\)）]+)[\)）]', col_raw)
            if name_match:
                holiday_name = name_match.group(1)

    if holiday_name:
        return f"{d_str} ({holiday_name})"
    return d_str

# --- 自動重置狀態回呼函數 ---
def reset_win_search():
    """切換換班條件時，自動清空舊的換班快照"""
    st.session_state.pop("win_raw_candidates", None)

def reset_ex_search():
    """切換換假條件時，自動清空舊的換假快照"""
    st.session_state["ex_search_performed"] = False
    st.session_state.pop("ex_raw_candidates", None)

def render_user_home():
    active_files = get_current_role_files()
    current_unit_label = st.session_state.get("current_unit", "TTN")
    missing_files = [role for role in ["駕駛", "列車長", "服勤員"] if not os.path.exists(active_files[role]) or os.path.getsize(active_files[role]) == 0]

    if missing_files: st.error(f"【{current_unit_label}】資料庫異常或尚無檔案：請洽管理員上傳！")

    td_time = get_file_mtime_str(active_files["駕駛"])
    tm_time = get_file_mtime_str(active_files["列車長"])
    ta_time = get_file_mtime_str(active_files["服勤員"])
    sched_range = get_schedule_range()

    st.markdown(f"""
    <div class="section-header-box" style="border-left-color: #60A5FA; padding: 8px 12px !important; margin: 6px 0 !important;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="section-title" style="font-size: 13px !important;">[{current_unit_label}] 排班週期</span>
            <span style="font-size: 14px; color: {"#EF4444" if missing_files else "#60A5FA"}; font-weight: 800; font-family: monospace;">
                {sched_range if len(missing_files) < 3 else "資料庫異常"}
            </span>
        </div>
        <details style="margin-top: 4px; font-size: 10px; color: #94A3B8; font-family: monospace; cursor: pointer;">
            <summary style="outline: none; color: #38BDF8; font-weight: 600; list-style: none; display: flex; justify-content: space-between; align-items: center;">
                <span>點擊檢視各大表更新時間</span>
                <span style="font-size: 9px; color: #64748B;">▼</span>
            </summary>
            <div style="display: flex; flex-direction: column; gap: 3px; margin-top: 6px; padding-top: 6px; border-top: 1px dashed rgba(255,255,255,0.1);">
                <div style="display: flex; justify-content: space-between;"><span>駕駛 (TD)</span><span>{td_time}</span></div>
                <div style="display: flex; justify-content: space-between;"><span>列車長 (TM)</span><span>{tm_time}</span></div>
                <div style="display: flex; justify-content: space-between;"><span>服勤員 (TA)</span><span>{ta_time}</span></div>
            </div>
        </details>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='font-size: 13px; font-weight: 700; color: #94A3B8; margin-bottom: 8px;'>選擇系統操作模式</div>", unsafe_allow_html=True)

    app_mode = st.radio(
        "系統操作模式選擇",
        [
            "繪製個人月班表圖檔",
            "換班｜選擇換班日期",
            "換假｜選擇換假日期"
        ],
        horizontal=False,
        label_visibility="collapsed"
    )

    if "last_app_mode" not in st.session_state: 
        st.session_state["last_app_mode"] = app_mode

    if st.session_state["last_app_mode"] != app_mode:
        st.session_state["last_app_mode"] = app_mode
        st.session_state.pop("win_raw_candidates", None)
        st.session_state.pop("ex_raw_candidates", None)
        st.session_state["ex_search_performed"] = False

    st.markdown("---")

    is_admin_user = st.session_state.get("admin_logged_in", False)

    # ==================== 模式一：繪製個人月班表圖檔 ====================
    if app_mode == "繪製個人月班表圖檔":
        if is_module_maintenance(current_unit_label, "producer"):
            if not is_admin_user:
                st.markdown(f"""
                <div class="user-maint-banner">
                    <div class="user-maint-title">SYSTEM MAINTENANCE // 系統維護中</div>
                    <div style="font-size: 15px; font-weight: 800; color: #FDE68A; margin: 6px 0;">
                        【{current_unit_label}】個人月班表圖檔生成系統進行維護中
                    </div>
                    <div class="user-maint-sub">
                        正在進行系統維護，暫不開放服務，請稍後再試。
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.stop()
            else:
                st.markdown(f"""
                <div class="admin-maint-banner">
                    <strong>【管理員維護模式檢視】</strong> 當前【{current_unit_label} - 個人月班表圖檔】模組已設為「維護中」（一般組員已被阻擋），您目前正以管理員身分進行預覽與功能測試。
                </div>
                """, unsafe_allow_html=True)

        st.markdown("""
        <div class="section-header-box">
            <div class="section-title">個人班表圖檔生成</div>
            <div class="section-subtitle">Personal Shift Schedule Image Generator</div>
        </div>
        """, unsafe_allow_html=True)

        target_input = st.text_input("輸入 員編 或 姓名 (例如: A023300 or 波莉)", value="A", key="user_input_field")

        if st.button("立即生成班表圖片檔"):
            current_input = st.session_state.get("user_input_field", "").strip()
            if not current_input:
                st.warning("請輸入員編或姓名")
            else:
                log_activity(f"生成個人班表圖檔查詢: {current_input}")
                try:
                    start_dt, dates, emp_id, emp_name, cells = process_file_data(current_input)
                    with st.spinner(f"正在繪製【{emp_name}】的個人月班表，請稍候..."):
                        buf = render_schedule_figure(start_dt, dates, emp_id, emp_name, cells, current_unit_label, badge_title="Producer | C.L.F")
                    st.success(f"【{emp_name}】個人班表圖片生成成功！")
                    render_zoomable_image(buf)
                    st.download_button("點此下載班表影像檔", data=buf, file_name=f"{current_unit_label}_班表_{emp_name}.png", mime="image/png")
                except Exception as e:
                    st.error(f"錯誤：{e}")

    # ==================== 模式二：換班｜選擇換班日期 ====================
    elif app_mode == "換班｜選擇換班日期":
        if is_module_maintenance(current_unit_label, "window_filter"):
            if not is_admin_user:
                st.markdown(f"""
                <div class="user-maint-banner">
                    <div class="user-maint-title">SYSTEM MAINTENANCE // 系統維護中</div>
                    <div style="font-size: 15px; font-weight: 800; color: #FDE68A; margin: 6px 0;">
                        【{current_unit_label}】換班選擇日期快篩系統進行維護中
                    </div>
                    <div class="user-maint-sub">
                        正在進行系統維護，暫不開放服務，請稍後再試。
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.stop()
            else:
                st.markdown(f"""
                <div class="admin-maint-banner">
                    <strong>【管理員維護模式檢視】</strong> 當前【{current_unit_label} - 換班選擇日期快篩】模組已設為「維護中」（一般組員已被阻擋），您目前正以管理員身分進行預覽與功能測試。
                </div>
                """, unsafe_allow_html=True)

        st.markdown("""
        <div class="section-header-box">
            <div class="section-title">換班檢索｜指定 Sign-In 時段組員快篩</div>
            <div class="section-subtitle">Duty Time Window & Sign-In Filter Matrix</div>
        </div>
        """, unsafe_allow_html=True)

        selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2, key="win_selected_role", on_change=reset_win_search)
        target_path = active_files[selected_role]

        morn_start_time = "03:00" if selected_role == "駕駛" else "05:00"

        if "last_win_selected_role" not in st.session_state or st.session_state["last_win_selected_role"] != selected_role:
            st.session_state["last_win_selected_role"] = selected_role
            st.session_state["win_time_slider"] = (morn_start_time, "10:00")
        elif "win_time_slider" not in st.session_state:
            st.session_state["win_time_slider"] = (morn_start_time, "10:00")

        if not os.path.exists(target_path):
            st.error(f"找不到【{current_unit_label} - {selected_role}】的班表檔案，請先至管理員後台上傳")
        else:
            df_search = safe_read_excel(target_path, header=3)
            df_search.columns = [str(c).strip() for c in df_search.columns]
            date_cols = [re.search(r'(\d+/\d+)', str(col)).group(1) for col in df_search.columns[2:] if re.search(r'(\d+/\d+)', str(col))]

            if date_cols:
                target_date = st.selectbox(
                    "選擇換班日期", 
                    date_cols, 
                    format_func=lambda d: get_date_label(d, df_search.columns),
                    key="win_target_date", 
                    on_change=reset_win_search
                )

                # 當週國定假日 Alert 檢查
                is_win_week_has_do2w, win_week_str = check_week_has_holiday(target_date, date_cols, df_search.columns)

                if is_win_week_has_do2w:
                    st.markdown(f"""
                    <div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px; color: #FDE68A; font-weight: 700;">
                        ⚠️ 提醒：您選擇的當週區間（{win_week_str}）包含 DO2W 國定假日！請留意換假/換班之DO2W出勤規範。
                    </div>
                    """, unsafe_allow_html=True)

                st.write("**快捷選擇時段：**")
                q_col1, q_col2, q_col3, q_col4 = st.columns(4)

                btn_all_label = f"全時段 ({morn_start_time}~18:00)"
                btn_morn_label = f"早班 ({morn_start_time}~10:00)"
                btn_noon_label = "中班 (10:00~13:00)"
                btn_night_label = "晚班 (13:00~18:00)"

                if q_col1.button(btn_all_label, key="btn_win_all", use_container_width=True):
                    st.session_state["win_time_slider"] = (morn_start_time, "18:00")
                    reset_win_search()
                    st.rerun()
                if q_col2.button(btn_morn_label, key="btn_win_morn", use_container_width=True):
                    st.session_state["win_time_slider"] = (morn_start_time, "10:00")
                    reset_win_search()
                    st.rerun()
                if q_col3.button(btn_noon_label, key="btn_win_noon", use_container_width=True):
                    st.session_state["win_time_slider"] = ("10:00", "13:00")
                    reset_win_search()
                    st.rerun()
                if q_col4.button(btn_night_label, key="btn_win_night", use_container_width=True):
                    st.session_state["win_time_slider"] = ("13:00", "18:00")
                    reset_win_search()
                    st.rerun()                

                TIME_OPTIONS = [f"{h:02d}:00" for h in range(19)]
                min_time, max_time_sel = st.select_slider(
                    "Sign-In 時段區間", 
                    options=TIME_OPTIONS, 
                    value=st.session_state.get("win_time_slider", (morn_start_time, "10:00")), 
                    key="win_time_slider"
                )

                filter_col1, filter_col2 = st.columns(2)
                with filter_col1: only_main_line = st.checkbox("僅顯示正線勤務", value=False, key="win_main_line")
                with filter_col2: only_long_shift = st.checkbox("僅顯示長班 (>8.5h)", value=False, key="win_long_shift")

                if st.button("搜尋可換班組員名單", key="btn_window_search"):
                    log_activity(f"換班快篩 [{current_unit_label} - {selected_role}] 日期:{target_date}")
                    all_cols_list = list(df_search.columns[2:])
                    raw_candidates = []

                    for _, row in df_search.iterrows():
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()
                        if not emp_id or emp_id.upper() in ["NAN", "NONE", ""]: continue

                        target_col_idx = next((idx + 2 for idx, col in enumerate(all_cols_list) if target_date in str(col)), -1)
                        if target_col_idx != -1 and target_col_idx < len(row):
                            cell_raw = row.iloc[target_col_idx]
                            parsed = parse_cell(cell_raw)
                            start_t = parsed["start"]
                            
                            is_off = is_cell_off_day(cell_raw)

                            if not is_off or start_t:
                                tr_upper = str(parsed["train"]).strip().upper()
                                raw_cell_upper = str(cell_raw).upper()
                                is_leave = any(k in raw_cell_upper for k in LEAVE_CODES) or tr_upper in LEAVE_CODES
                                is_non_line = is_town_shift(parsed["train"], parsed["note"])
                                is_long = is_overtime(parsed["hours"], parsed["train"], parsed["note"])

                                do_tag = parsed.get("note", "")
                                if not do_tag:
                                    do_match = re.search(r'(DO\d*W?|D\d+W|OGC)', str(cell_raw), re.IGNORECASE)
                                    do_tag = do_match.group(1).upper() if do_match else ""

                                next_day_sign_in = "無記錄"
                                if target_col_idx + 1 < len(row):
                                    next_parsed = parse_cell(row.iloc[target_col_idx + 1])
                                    next_day_sign_in = next_parsed["start"] if next_parsed["start"] else (next_parsed["train"] if next_parsed["train"] else "無記錄")

                                raw_candidates.append({
                                    "日期": target_date, "員編": emp_id, "姓名": emp_name,
                                    "Sign-In": start_t if start_t else "--:--", 
                                    "Sign-Out": parsed["end"] if parsed["end"] else "--:--",
                                    "工時": parsed.get("hours", ""),
                                    "車次": translate_train_code(parsed["train"]),
                                    "隔日Sign-In": next_day_sign_in, "長班": is_long,
                                    "非正線": is_non_line, "請假": is_leave,
                                    "出勤標記": do_tag
                                })

                    st.session_state["win_raw_candidates"] = raw_candidates
                    st.rerun()

                if st.session_state.get("win_raw_candidates") is not None:
                    raw_list = st.session_state["win_raw_candidates"]
                    filtered_results = []

                    for r in raw_list:
                        if r["Sign-In"] != "--:--":
                            if not (min_time <= r["Sign-In"] <= max_time_sel): continue
                        if only_main_line and (r["非正線"] or r["請假"]): continue
                        if only_long_shift and not r["長班"]: continue
                        filtered_results.append(r)

                    filtered_results = sorted(filtered_results, key=lambda x: (str(x["Sign-In"]), str(x["Sign-Out"])))

                    st.markdown(f"### 換班可選人員名單（共符合 {len(filtered_results)} 筆）")

                    if filtered_results:
                        # 戰情室 KPI 統計指標 Bar
                        cnt_do2w = sum(1 for r in filtered_results if 'DO2' in r.get('出勤標記', '') or 'OGC' in r.get('出勤標記', ''))
                        cnt_long = sum(1 for r in filtered_results if r.get('長班'))

                        st.markdown(f"""
                        <div style="display: flex; gap: 8px; margin-bottom: 12px; margin-top: 4px;">
                            <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">符合資格人數</div>
                                <div style="font-size: 17px; font-weight: 900; color: #38BDF8; font-family: monospace;">{len(filtered_results)} <span style="font-size: 10px;">位</span></div>
                            </div>
                            <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">含 DO2W 標記</div>
                                <div style="font-size: 17px; font-weight: 900; color: #FBBF24; font-family: monospace;">{cnt_do2w} <span style="font-size: 10px;">人</span></div>
                            </div>
                            <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">長班 (>8.5h)</div>
                                <div style="font-size: 17px; font-weight: 900; color: #FB7185; font-family: monospace;">{cnt_long} <span style="font-size: 10px;">人</span></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        c_col1, c_col2 = st.columns(2)
                        for idx, r in enumerate(filtered_results):
                            target_col = c_col1 if idx % 2 == 0 else c_col2
                            with target_col:
                                do_tag = r.get('出勤標記', '')
                                shift_hours = r.get("工時", "")

                                # 工時顯示：右上角微小灰色文字
                                hours_display_html = f'<div style="font-size: 11px; color: #CBD5E1; font-family: monospace; margin-top: 1px;">({shift_hours})</div>' if shift_hours else ""

                                # 組合標籤組 (獨立排版：非正線、長班、DO2W)
                                badges_html = '<div class="badge-group">'
                                if r.get('非正線'): badges_html += '<span class="non-line-badge">非正線</span>'
                                if r.get('長班'): badges_html += '<span class="long-badge">長班</span>'
                                if do_tag: badges_html += f'<span class="do2w-badge">[{do_tag}]</span>'
                                badges_html += '</div>'

                                st.markdown(f"""
                                <div class="integrated-crew-box">
                                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                        <div>
                                            <div class="compact-name">{r['姓名']} <span style="color:#94A3B8; font-size:12px;">({r['員編']})</span></div>
                                            <div style="font-size: 13px; color: #38BDF8; font-weight: 700; margin-top: 2px;">班別：{r['車次']}</div>
                                        </div>
                                        <div style="text-align: right; display: flex; flex-direction: column; gap: 3px;">
                                            <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">Sign-In {r['Sign-In']}</div>
                                            <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">Sign-Out {r['Sign-Out']}</div>
                                            {hours_display_html}
                                        </div>
                                    </div>
                                    <div style="display: flex; gap: 6px; align-items: center; justify-content: space-between; margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.06);">
                                        <span style="font-size: 11px; color: #94A3B8; font-family: monospace;">隔日 Sign-In：<strong style="color:#FCD34D;">{r['隔日Sign-In']}</strong></span>
                                        {badges_html}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                                if st.button(f"檢視 {r['姓名']} 完整班表", key=f"win_btn_{r['員編']}_{idx}", use_container_width=True):
                                    show_crew_schedule_modal(r['員編'], current_unit_label, badge_title="Window Filter | C.L.F")
                    else: st.info("在指定條件內，找不到符合的人員")

    # ==================== 模式三：換假｜選擇換假日期 ====================
    elif app_mode == "換假｜選擇換假日期":
        if is_module_maintenance(current_unit_label, "exchange_filter"):
            if not is_admin_user:
                st.markdown(f"""
                <div class="user-maint-banner">
                    <div class="user-maint-title">SYSTEM MAINTENANCE // 系統維護中</div>
                    <div style="font-size: 15px; font-weight: 800; color: #FDE68A; margin: 6px 0;">
                        【{current_unit_label}】換假選擇日期快篩系統進行維護中
                    </div>
                    <div class="user-maint-sub">
                        正在進行系統維護，暫不開放服務，請稍後再試。
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.stop()
            else:
                st.markdown(f"""
                <div class="admin-maint-banner">
                    <strong>【管理員維護模式檢視】</strong> 當前【{current_unit_label} - 換假選擇日期快篩】模組已設為「維護中」（一般組員已被阻擋），您目前正以管理員身分進行預覽與功能測試。
                </div>
                """, unsafe_allow_html=True)

        st.markdown("""
        <div class="section-header-box">
            <div class="section-title">換假檢索｜選擇換假日期快篩</div>
            <div class="section-subtitle">Shift Exchange Date Filter Matrix</div>
        </div>
        """, unsafe_allow_html=True)

        if "ex_search_performed" not in st.session_state:
            st.session_state["ex_search_performed"] = False

        ex_c1, ex_c2, ex_c3 = st.columns(3)
        with ex_c1: selected_role = st.selectbox("選擇職位類別", ["服勤員", "駕駛", "列車長"], key="ex_role_select", on_change=reset_ex_search)

        sample_path = active_files.get(selected_role, "")
        
        if not sample_path or not os.path.exists(sample_path):
            st.error(f"找不到【{current_unit_label} - {selected_role}】的班表檔案，請先至管理員後台上傳")
        else:
            try:
                df_ex = safe_read_excel(sample_path, header=3)
                df_ex.columns = [str(c).strip() for c in df_ex.columns]
                date_cols = [re.search(r'(\d+/\d+)', str(c)).group(1) for c in df_ex.columns[2:] if re.search(r'(\d+/\d+)', str(c))]

                if not date_cols:
                    st.warning("目前的班表檔案中無法解析出有效的日期欄位。")
                else:
                    with ex_c2: 
                        target_date = st.selectbox(
                            "選擇想休假日期", 
                            date_cols, 
                            format_func=lambda d: get_date_label(d, df_ex.columns),
                            key="ex_target_date", 
                            on_change=reset_ex_search
                        )

                    # 計算當週區間與國定假日 Alert
                    same_week_options = []
                    is_week_has_do2w, target_week_str = check_week_has_holiday(target_date, date_cols, df_ex.columns)

                    try:
                        current_year = date.today().year
                        t_m, t_d = map(int, target_date.split('/'))
                        t_dt = date(current_year, t_m, t_d)
                        t_sun = t_dt - timedelta(days=(t_dt.weekday() + 1) % 7)
                        t_sat = t_sun + timedelta(days=6)

                        for d_str in date_cols:
                            try:
                                d_m, d_d = map(int, d_str.split('/'))
                                d_dt = date(current_year, d_m, d_d)
                                if t_sun <= d_dt <= t_sat and d_str != target_date:
                                    same_week_options.append(d_str)
                            except: pass
                    except: pass

                    return_date_options = same_week_options if same_week_options else [d for d in date_cols if d != target_date]

                    if "ex_prev_target_date" not in st.session_state or st.session_state["ex_prev_target_date"] != target_date:
                        st.session_state["ex_prev_target_date"] = target_date
                        if return_date_options:
                            st.session_state["ex_return_date"] = return_date_options[0]

                    if "ex_return_date" in st.session_state and st.session_state["ex_return_date"] not in return_date_options:
                        if return_date_options:
                            st.session_state["ex_return_date"] = return_date_options[0]

                    with ex_c3: 
                        return_date = st.selectbox(
                            "選擇可還假日期", 
                            return_date_options, 
                            format_func=lambda d: get_date_label(d, df_ex.columns),
                            key="ex_return_date", 
                            on_change=reset_ex_search
                        )

                    # 頂部國定假日 Alert Banner
                    if is_week_has_do2w:
                        st.markdown(f"""
                        <div style="background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 10px 14px; margin: 8px 0; font-size: 13px; color: #FDE68A; font-weight: 700;">
                            ⚠️ 提醒：您選擇的當週區間（{target_week_str}）包含 DO2W 國定假日！請留意換假/換班之DO2W出勤規範。
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.caption(f" **同一週規範換假區間：{target_week_str}**（還假選單已自動設定於當週區間）")

                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        time_filter_options = ["不限"] + [f"{h:02d}:00 以後" for h in range(5, 17)]
                        return_time_filter = st.selectbox("還假日 Sign-In 時間限制", options=time_filter_options, key="ex_time_filter")
                    with col_f2:
                        sort_order = st.selectbox("結果排序方式", ["依 Sign-In 時間 (由早至晚)", "依最早 Sign-Out", "依工時長短"], key="ex_sort_order")

                    strict_limit = st.checkbox("嚴格過濾：排除換假後連續上班已達 6 天以上的人員", value=True, key="ex_strict_limit")

                    if st.button("搜尋可換假組員名單", key="btn_ex_search"):
                        log_activity(f"換假快篩 [{current_unit_label} - {selected_role}] 想休:{target_date} 還假:{return_date}")
                        raw_candidates = []
                        all_cols = list(df_ex.columns)
                        
                        target_col_idx = next((idx for idx, col in enumerate(all_cols) if idx >= 2 and target_date in str(col)), -1)
                        return_col_idx = next((idx for idx, col in enumerate(all_cols) if idx >= 2 and return_date in str(col)), -1)

                        if target_col_idx != -1 and return_col_idx != -1:
                            for _, row in df_ex.iterrows():
                                emp_id = str(row.iloc[0]).strip()
                                emp_name = str(row.iloc[1]).strip()
                                if not emp_id or emp_id.upper() in ["NAN", "NONE", ""]: continue
                                if target_col_idx >= len(row) or return_col_idx >= len(row): continue

                                parsed_target = parse_cell(row.iloc[target_col_idx])
                                raw_target_str = str(row.iloc[target_col_idx]).strip().upper()
                                
                                is_target_leave = any(k in raw_target_str for k in LEAVE_CODES) or parsed_target["train"] in LEAVE_CODES
                                if is_target_leave: continue

                                is_target_do = is_cell_off_day(row.iloc[target_col_idx])
                                if not is_target_do: continue

                                parsed_return = parse_cell(row.iloc[return_col_idx])
                                raw_return_str = str(row.iloc[return_col_idx]).strip()
                                raw_return_upper = raw_return_str.upper()

                                is_return_leave = any(k in raw_return_upper for k in LEAVE_CODES) or parsed_return["train"] in LEAVE_CODES
                                is_return_do = is_cell_off_day(row.iloc[return_col_idx])
                                if is_return_do or is_return_leave: continue

                                is_long = is_overtime(parsed_return["hours"], parsed_return["train"], parsed_return["note"])
                                is_non_line = is_town_shift(parsed_return["train"], parsed_return["note"])

                                return_do_tag = parsed_return.get("note", "")
                                if not return_do_tag:
                                    do_match = re.search(r'(DO\d*W?|D\d+W|OGC)', raw_return_str, re.IGNORECASE)
                                    return_do_tag = do_match.group(1).upper() if do_match else ""

                                raw_target_cell = str(row.iloc[target_col_idx]).upper()
                                raw_return_cell = str(row.iloc[return_col_idx]).upper()
                                has_do2w_tag = bool(re.search(r'(DO[23]W|D[23]W|OGC)', raw_target_cell + raw_return_cell, re.IGNORECASE))

                                max_consecutive_streak = calculate_consecutive_work_days(row, target_col_idx, return_col_idx)

                                raw_candidates.append({
                                    "員編": emp_id,
                                    "姓名": emp_name,
                                    "想休日": target_date,
                                    "想休狀態": raw_target_str.split("\n")[0] if raw_target_str else "DO",
                                    "還休日": return_date,
                                    "還假車次": translate_train_code(parsed_return["train"]),
                                    "Sign-In": parsed_return["start"] if parsed_return["start"] else "--:--",
                                    "Sign-Out": parsed_return["end"] if parsed_return["end"] else "--:--",
                                    "工時": parsed_return["hours"],
                                    "長班": is_long,
                                    "非正線": is_non_line,
                                    "出勤標記": return_do_tag,
                                    "有DO2W標記": has_do2w_tag,
                                    "連續上班天數": max_consecutive_streak
                                })

                        st.session_state["ex_raw_candidates"] = raw_candidates
                        st.session_state["ex_search_performed"] = True
                        st.rerun()

                    if st.session_state.get("ex_search_performed"):
                        raw_list = st.session_state.get("ex_raw_candidates", [])
                        filtered_candidates = []

                        for cand in raw_list:
                            if return_time_filter != "不限":
                                min_allowed = return_time_filter.split(" ")[0]
                                if not cand["Sign-In"] or cand["Sign-In"] == "--:--" or cand["Sign-In"] < min_allowed:
                                    continue

                            if strict_limit and cand["連續上班天數"] >= 6:
                                continue

                            filtered_candidates.append(cand)

                        if sort_order == "依 Sign-In 時間 (由早至晚)":
                            filtered_candidates = sorted(filtered_candidates, key=lambda x: (x["Sign-In"] or "99:99", x["Sign-Out"] or "99:99"))
                        elif sort_order == "依最早 Sign-Out":
                            filtered_candidates = sorted(filtered_candidates, key=lambda x: (x["Sign-Out"] or "99:99", x["Sign-In"] or "99:99"))
                        elif sort_order == "依工時長短":
                            filtered_candidates = sorted(filtered_candidates, key=lambda x: x["工時"] or "0h00m", reverse=True)

                        st.markdown(f"### 換假可選人員名單（共 {len(filtered_candidates)} 位）")

                        if filtered_candidates:
                            # 戰情室 KPI 統計指標 Bar
                            cnt_do2w = sum(1 for c in filtered_candidates if c.get('有DO2W標記') or 'DO2' in c.get('出勤標記', ''))
                            cnt_streak6 = sum(1 for c in filtered_candidates if c.get('連續上班天數', 0) >= 6)

                            st.markdown(f"""
                            <div style="display: flex; gap: 8px; margin-bottom: 12px; margin-top: 4px;">
                                <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                    <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">可換假總人數</div>
                                    <div style="font-size: 17px; font-weight: 900; color: #38BDF8; font-family: monospace;">{len(filtered_candidates)} <span style="font-size: 10px;">位</span></div>
                                </div>
                                <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                    <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">含 DO2W 標記</div>
                                    <div style="font-size: 17px; font-weight: 900; color: #FBBF24; font-family: monospace;">{cnt_do2w} <span style="font-size: 10px;">人</span></div>
                                </div>
                                <div style="flex: 1; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 8px; padding: 6px 10px; text-align: center;">
                                    <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">連班 6 天以上</div>
                                    <div style="font-size: 17px; font-weight: 900; color: #FB7185; font-family: monospace;">{cnt_streak6} <span style="font-size: 10px;">人</span></div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            c_col1, c_col2 = st.columns(2)
                            for idx, cand in enumerate(filtered_candidates):
                                cand_name = cand.get('姓名', '')
                                cand_id = cand.get('員編', '')
                                target_col = c_col1 if idx % 2 == 0 else c_col2

                                do_tag = cand.get('出勤標記', '')
                                cand_hours = cand.get('工時', '')

                                # 工時顯示：右上角微小灰色文字 (與換班系統統一)
                                hours_display_html = f'<div style="font-size: 11px; color: #CBD5E1; font-family: monospace; margin-top: 1px;">({cand_hours})</div>' if cand_hours else ""

                                # 組合標籤組 (獨立排版：非正線、長班、DO2W)
                                badges_html = '<div class="badge-group">'
                                if cand.get('非正線'): badges_html += '<span class="non-line-badge">非正線</span>'
                                if cand.get('長班'): badges_html += '<span class="long-badge">長班</span>'
                                if cand.get('有DO2W標記') or do_tag:
                                    tag_text = do_tag if do_tag else "DO2W"
                                    badges_html += f'<span class="do2w-badge">[{tag_text}]</span>'
                                badges_html += '</div>'

                                streak_cnt = cand.get('連續上班天數', 0)
                                streak_color = "#FB7185" if streak_cnt >= 6 else "#CBD5E1"

                                card_border_color = "rgba(56, 189, 248, 0.25)"
                                warning_banner_html = ""

                                if streak_cnt >= 7:
                                    card_border_color = "#F43F5E"
                                    warning_banner_html = f"""
                                    <div style="background: rgba(225, 29, 72, 0.2); border: 1px solid #F43F5E; border-radius: 6px; padding: 4px 8px; margin-top: 6px; font-size: 11px; color: #FDA4AF; font-weight: 700; font-family: monospace;">
                                        注意：換假後連續上班達 {streak_cnt} 天，請注意七休一規範！
                                    </div>
                                    """

                                with target_col:
                                    st.markdown(f"""
                                    <div class="integrated-crew-box" style="border-color: {card_border_color} !important;">
                                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                            <div>
                                                <div class="compact-name">{cand_name} <span style="color:#94A3B8; font-size:12px;">({cand_id})</span></div>
                                                <div style="font-size: 12px; color: #94A3B8; margin-top: 4px; font-family: monospace;">
                                                    還休日：<strong style="color: #94A3B8;">{cand.get('還休日')}</strong> ｜ 班別：<strong style="color:#38BDF8;">{cand.get('還假車次', '無')}</strong>
                                                </div>
                                            </div>
                                            <div style="text-align: right; display: flex; flex-direction: column; gap: 3px;">
                                                <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">
                                                    Sign-In {cand.get('Sign-In', '--:--')}
                                                </div>
                                                <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">
                                                    Sign-Out {cand.get('Sign-Out', '--:--')}
                                                </div>
                                                {hours_display_html}
                                            </div>
                                        </div>
                                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.06);">
                                            <span style="font-size: 11.5px; color: {streak_color}; font-weight: 700; font-family: monospace;">
                                                換假後連續上班：{streak_cnt} 天
                                            </span>
                                            {badges_html}
                                        </div>
                                        {warning_banner_html}
                                    </div>
                                    """, unsafe_allow_html=True)

                                    if st.button(f"檢視 {cand_name} 完整班表", key=f"ex_btn_{cand_id}_{idx}", use_container_width=True):
                                        show_crew_schedule_modal(cand_id, current_unit_label, badge_title="Exchange | C.L.F")
                        else:
                            st.info("在指定條件內，找不到符合的可換假人員 (可嘗試放寬還假日 Sign-In 時間限制或取消嚴格過濾)")
            except Exception as e:
                st.error(f"讀取換假資料時發生錯誤：{e}")
