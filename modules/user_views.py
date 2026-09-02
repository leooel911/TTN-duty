import os
import re
import streamlit as st
from datetime import date, timedelta
from config import UNITS
from modules.utils import (
    get_file_mtime_str, is_module_maintenance, log_activity, 
    safe_read_excel, parse_cell, translate_train_code, is_town_shift, is_overtime
)
from modules.services import (
    get_current_role_files, get_schedule_range, process_file_data, 
    calculate_consecutive_work_days
)
from modules.drawing import render_schedule_figure
from modules.components import render_zoomable_image, show_crew_schedule_modal

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
     # 上方自訂標題文字與樣式
    st.markdown("<div style='font-size: 13px; font-weight: 700; color: #94A3B8; margin-bottom: 8px; letter-spacing: 0.5px;'>選擇系統操作模式</div>", unsafe_allow_html=True)

    # 採用無圓點的 Segmented Control 切換列
    app_mode = st.segmented_control(
        "系統操作模式選擇",
        options=[
            "繪製個人月班表圖檔", 
            "換班｜選擇換班日期",
            "換假｜選擇換假日期"
        ],
        default="換假｜選擇換假日期",
        label_visibility="collapsed"
    )

    # 舊版 Streamlit 相容防呆
    if app_mode is None:
        app_mode = "換假｜選擇換假日期"

    if "last_app_mode" not in st.session_state: st.session_state["last_app_mode"] = app_mode
    if st.session_state["last_app_mode"] != app_mode:
        st.session_state["last_app_mode"] = app_mode

    st.markdown("---")

    is_admin_user = st.session_state.get("admin_logged_in", False)

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

        selected_role = st.selectbox("選擇職位類別進行查詢", ["駕駛", "列車長", "服勤員"], index=2, key="win_selected_role")
        target_path = active_files[selected_role]

        if not os.path.exists(target_path):
            st.error(f"找不到【{current_unit_label} - {selected_role}】的班表檔案，請先至管理員後台上傳")
        else:
            df_search = safe_read_excel(target_path, header=3)
            df_search.columns = [str(c).strip() for c in df_search.columns]
            date_cols = [re.search(r'(\d+/\d+)', str(col)).group(1) for col in df_search.columns[2:] if re.search(r'(\d+/\d+)', str(col))]

            if date_cols:
                target_date = st.selectbox("選擇換班日期", date_cols, key="win_target_date")
               
                st.write("**快捷選擇時段：**")
                q_col1, q_col2, q_col3, q_col4 = st.columns(4)
                if q_col1.button("全時段", key="btn_win_all", use_container_width=True):
                    st.session_state["win_time_slider"] = ("04:00", "18:00")
                    st.rerun()
                if q_col2.button("早班", key="btn_win_morn", use_container_width=True):
                    st.session_state["win_time_slider"] = ("05:00", "08:00")
                    st.rerun()
                if q_col3.button("中班", key="btn_win_noon", use_container_width=True):
                    st.session_state["win_time_slider"] = ("08:00", "13:00")
                    st.rerun()
                if q_col4.button("晚班", key="btn_win_night", use_container_width=True):
                    st.session_state["win_time_slider"] = ("13:00", "18:00")
                    st.rerun()               
                TIME_OPTIONS = [f"{h:02d}:00" for h in range(19)]
                default_slider = st.session_state.get("win_time_slider", ("05:00", "08:00"))
                min_time, max_time_sel = st.select_slider("Sign-In 時段區間", options=TIME_OPTIONS, value=default_slider, key="win_time_slider")

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

                            if start_t:
                                tr_upper = str(parsed["train"]).strip().upper()
                                raw_cell_upper = str(cell_raw).upper()
                                is_leave = any(k in raw_cell_upper for k in ["PAY", "FAC", "AL", "SL", "CL"]) or tr_upper in ["PAY", "FAC", "AL", "SL", "CL", "DO", "D2W"]
                                is_non_line = is_town_shift(parsed["train"], parsed["note"])
                                is_long = is_overtime(parsed["hours"], parsed["train"], parsed["note"])

                                next_day_sign_in = "無記錄"
                                if target_col_idx + 1 < len(row):
                                    next_parsed = parse_cell(row.iloc[target_col_idx + 1])
                                    next_day_sign_in = next_parsed["start"] if next_parsed["start"] else (next_parsed["train"] if next_parsed["train"] else "無記錄")

                                raw_candidates.append({
                                    "日期": target_date, "員編": emp_id, "姓名": emp_name,
                                    "Sign-In": start_t, "Sign-Out": parsed["end"],
                                    "車次": translate_train_code(parsed["train"]),
                                    "隔日Sign-In": next_day_sign_in, "長班": is_long,
                                    "非正線": is_non_line, "請假": is_leave
                                })

                    st.session_state["win_raw_candidates"] = raw_candidates
                    st.rerun()

                if st.session_state.get("win_raw_candidates") is not None:
                    raw_list = st.session_state["win_raw_candidates"]
                    filtered_results = []

                    for r in raw_list:
                        if not (min_time <= r["Sign-In"] <= max_time_sel): continue
                        if only_main_line and (r["非正線"] or r["請假"]): continue
                        if only_long_shift and not r["長班"]: continue
                        filtered_results.append(r)

                    filtered_results = sorted(filtered_results, key=lambda x: (str(x["Sign-In"]), str(x["Sign-Out"])))

                    st.markdown(f"### 換班可選人員名單（共符合 {len(filtered_results)} 筆）")

                    if filtered_results:
                        c_col1, c_col2 = st.columns(2)
                        for idx, r in enumerate(filtered_results):
                            target_col = c_col1 if idx % 2 == 0 else c_col2
                            with target_col:
                                badges_html = '<div class="badge-group">'
                                if r['長班']: badges_html += '<span class="long-badge">長班</span>'
                                if r['非正線']: badges_html += '<span class="non-line-badge">非正線</span>'
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
        with ex_c1: selected_role = st.selectbox("選擇職位類別", ["服勤員", "駕駛", "列車長"], key="ex_role_select")

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
                        target_date = st.selectbox("選擇想休假日期", date_cols, key="ex_target_date")

                    with ex_c3: 
                        return_date = st.selectbox("選擇可還假日期", date_cols, index=min(1, len(date_cols)-1), key="ex_return_date")

                    is_cross_week = False
                    target_week_str = ""
                    try:
                        t_m, t_d = map(int, target_date.split('/'))
                        r_m, r_d = map(int, return_date.split('/'))
                        t_dt = date(2026, t_m, t_d)
                        r_dt = date(2026, r_m, r_d)

                        t_sun = t_dt - timedelta(days=(t_dt.weekday() + 1) % 7)
                        t_sat = t_sun + timedelta(days=6)
                        target_week_str = f"{t_sun.month}/{t_sun.day:02d} (日) ~ {t_sat.month}/{t_sat.day:02d} (六)"

                        r_sun = r_dt - timedelta(days=(r_dt.weekday() + 1) % 7)
                        
                        if t_sun != r_sun:
                            is_cross_week = True
                    except:
                        pass

                    if is_cross_week:
                        st.warning(f"**跨週警示**：您選擇的還假日期「{return_date}」與想休假日期「{target_date}」不在同一週！（想休假當週規範區間為：{target_week_str}）")
                    else:
                        st.caption(f"**同一週換假區間：{target_week_str}**")

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
                                raw_target_str = str(row.iloc[target_col_idx]).strip()
                                is_target_do = ("DO" in raw_target_str.upper()) or ("D2W" in raw_target_str.upper())
                                if not is_target_do: continue

                                parsed_return = parse_cell(row.iloc[return_col_idx])
                                raw_return_str = str(row.iloc[return_col_idx]).strip().upper()
                                is_return_do = ("DO" in raw_return_str) or ("D2W" in raw_return_str)
                                if is_return_do: continue

                                is_long = is_overtime(parsed_return["hours"], parsed_return["train"], parsed_return["note"])
                                is_non_line = is_town_shift(parsed_return["train"], parsed_return["note"])

                                max_consecutive_streak = calculate_consecutive_work_days(row, target_col_idx, return_col_idx)

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
                                if not cand["Sign-In"] or cand["Sign-In"] < min_allowed:
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
                            c_col1, c_col2 = st.columns(2)
                            for idx, cand in enumerate(filtered_candidates):
                                cand_name = cand.get('姓名', '')
                                cand_id = cand.get('員編', '')
                                target_col = c_col1 if idx % 2 == 0 else c_col2

                                badges_html = '<div class="badge-group">'
                                if cand.get('長班'): badges_html += '<span class="long-badge">長班</span>'
                                if cand.get('非正線'): badges_html += '<span class="non-line-badge">非正線</span>'
                                badges_html += '</div>'

                                streak_cnt = cand.get('連續上班天數', 0)
                                streak_color = "#FB7185" if streak_cnt >= 6 else "#CBD5E1"

                                with target_col:
                                    st.markdown(f"""
                                    <div class="integrated-crew-box">
                                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                            <div>
                                                <div class="compact-name">{cand_name} <span style="color:#94A3B8; font-size:12px;">({cand_id})</span></div>
                                                <div style="font-size: 12px; color: #94A3B8; margin-top: 4px; font-family: monospace;">
                                                    還休日：{cand.get('還休日')} ｜ 班別：<strong style="color:#38BDF8;">{cand.get('還假車次', '無')}</strong>
                                                </div>
                                            </div>
                                            <div style="text-align: right; display: flex; flex-direction: column; gap: 3px;">
                                                <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">
                                                    Sign-In {cand.get('Sign-In', '--:--')}
                                                </div>
                                                <div style="font-size: 17px; font-weight: 900; color: #4ADE80; font-family: monospace; letter-spacing: 0.5px;">
                                                    Sign-Out {cand.get('Sign-Out', '--:--')}
                                                </div>
                                                <div style="font-size: 11px; color: #CBD5E1; font-family: monospace; margin-top: 1px;">
                                                    ({cand.get('工時', '')})
                                                </div>
                                            </div>
                                        </div>
                                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.06);">
                                            <span style="font-size: 11.5px; color: {streak_color}; font-weight: 700; font-family: monospace;">
                                                換假後連續上班：{streak_cnt} 天
                                            </span>
                                            {badges_html}
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                                    if st.button(f"檢視 {cand_name} 完整班表", key=f"ex_btn_{cand_id}_{idx}", use_container_width=True):
                                        show_crew_schedule_modal(cand_id, current_unit_label, badge_title="Exchange | C.L.F")
                        else:
                            st.info("在指定條件內，找不到符合的可換假人員 (可嘗試放寬還假日 Sign-In 時間限制或取消嚴格過濾)")
            except Exception as e:
                st.error(f"讀取換假資料時發生錯誤：{e}")
