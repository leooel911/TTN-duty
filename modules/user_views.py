import os
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

import modules.components as comp
from config import LEAVE_CODES, NATIONAL_HOLIDAYS
from modules.drawing import render_schedule_figure
from modules.services import (
    authenticate_user,
    get_available_months,
    get_current_role_files,
    get_schedule_range,
    load_system_config,
    process_file_data,
)
from modules.utils import (
    calculate_consecutive_work_days,
    check_week_has_holiday,
    get_file_mtime_str,
    is_cell_off_day,
    is_module_maintenance,
    is_overtime,
    is_town_shift,
    log_activity,
    normalize_date_str,
    parse_cell,
    safe_read_excel,
    set_simulated_cell,
    translate_train_code,
)


# =============================================================================
# 1. 安全會話與身份授權輔助函式
# =============================================================================

AUTH_SESSION_KEY = "CURRENT_AUTH_SESSION"


def get_auth_session() -> dict:
    """取得集中管理的登入 Session 狀態"""
    if AUTH_SESSION_KEY not in st.session_state:
        st.session_state[AUTH_SESSION_KEY] = {
            "authenticated": False,
            "emp_id": "",
            "emp_name": "",
            "role": "GUEST",
            "unit": "TTN",
        }
    return st.session_state[AUTH_SESSION_KEY]


def get_login_user_id() -> str:
    """自動從登入 Session 狀態抓取員編"""
    auth = get_auth_session()
    if auth.get("authenticated"):
        return auth.get("emp_id", "")
    return st.session_state.get("emp_id", "") or st.session_state.get("user_id", "")


def clean_role_label(role: str) -> str:
    """轉換權限標籤文字"""
    mapping = {
        "ADMIN": "系統管理員",
        "VIP_USER": "VIP 特權組員",
        "TESTER": "測試員",
        "USER": "一般組員",
    }
    return mapping.get(role, role)


# =============================================================================
# 2. 資料處理與工具函式
# =============================================================================

def get_shift_group_key(code_str: str) -> str:
    """提取車次/班別的核心標識 (例: ND0007/NM0007/NF0007 均歸為 '0007', DTT -> 'DTT')"""
    s = str(code_str).strip().upper()
    nums = re.findall(r"\d+", s)
    if nums:
        return "".join(nums)
    return s


def get_shift_group_num(code_str: str) -> int:
    """提取車次/班別中的核心數字用於排序 (例: ND0007 -> 7, ND1012 -> 1012)"""
    nums = re.findall(r"\d+", str(code_str))
    if nums:
        return int("".join(nums))
    return 999999


def find_date_column_index(columns: Any, target_date: str) -> int:
    """精準匹配日期欄位索引，避免 substring 誤判與年份格式不符"""
    if columns is None:
        return -1
    target_norm = normalize_date_str(target_date)
    for idx, col in enumerate(columns):
        if idx < 2:
            continue
        if normalize_date_str(col) == target_norm:
            return idx
    return -1


def get_date_label(d_str: str, columns: Optional[Any] = None) -> str:
    """取得包含國定假日名稱的日期顯示標籤"""
    norm_d = normalize_date_str(d_str)
    holiday_name = NATIONAL_HOLIDAYS.get(norm_d) or NATIONAL_HOLIDAYS.get(d_str)
    if not holiday_name and columns is not None:
        matching_col = next((c for c in columns[2:] if norm_d and norm_d in normalize_date_str(c)), None)
        if matching_col:
            col_raw = str(matching_col)
            name_match = re.search(r"[\(（]([^\)）]+)[\)）]", col_raw)
            if name_match:
                holiday_name = name_match.group(1)

    if holiday_name:
        return f"{d_str} ({holiday_name})"
    return d_str


def get_week_holidays(target_date: str, date_cols: List[str], columns: Optional[Any] = None) -> List[str]:
    """取得當週涵蓋的所有節假日標籤清單"""
    holidays_found = []
    if not target_date or not date_cols:
        return holidays_found

    try:
        current_year = date.today().year
        norm_target = normalize_date_str(target_date)
        if not norm_target:
            return holidays_found
        t_m, t_d = map(int, norm_target.split("/"))
        t_dt = date(current_year, t_m, t_d)
        t_sun = t_dt - timedelta(days=(t_dt.weekday() + 1) % 7)
        t_sat = t_sun + timedelta(days=6)

        for d_str in date_cols:
            try:
                norm_d = normalize_date_str(d_str)
                if not norm_d:
                    continue
                d_m, d_d = map(int, norm_d.split("/"))
                d_dt = date(current_year, d_m, d_d)
                if t_sun <= d_dt <= t_sat:
                    holiday_name = NATIONAL_HOLIDAYS.get(norm_d) or NATIONAL_HOLIDAYS.get(d_str)
                    if not holiday_name and columns is not None:
                        matching_col = next(
                            (c for c in columns[2:] if norm_d in normalize_date_str(c)), None
                        )
                        if matching_col:
                            col_raw = str(matching_col)
                            name_match = re.search(r"[\(（]([^\)）]+)[\)）]", col_raw)
                            if name_match:
                                holiday_name = name_match.group(1)

                    if holiday_name:
                        label = f"{d_str} ({holiday_name})"
                        if label not in holidays_found:
                            holidays_found.append(label)
            except Exception:
                continue
    except Exception:
        pass

    return holidays_found


def reset_win_search() -> None:
    """重置換班快篩的快取資料"""
    st.session_state.pop("win_raw_candidates", None)


def reset_ex_search() -> None:
    """重置換假快篩的快取資料與搜尋狀態"""
    st.session_state["ex_search_performed"] = False
    st.session_state.pop("ex_raw_candidates", None)


# =============================================================================
# 3. 前台主入口邏輯 (純已登入主畫面)
# =============================================================================

def render_user_home() -> None:
    """繪製使用者首頁主要介面與功能模組"""

    auth = get_auth_session()
    
    current_user_id = (
        auth.get("emp_id") 
        or st.session_state.get("emp_id") 
        or st.session_state.get("user_id") 
        or ""
    )
    current_user_name = (
        auth.get("emp_name") 
        or st.session_state.get("emp_name") 
        or st.session_state.get("user_name") 
        or current_user_id 
        or "GUEST"
    )
    
    user_role = auth["role"]
    is_privileged = user_role in ["ADMIN", "VIP_USER"]
    is_admin_user = (user_role == "ADMIN") or st.session_state.get("admin_logged_in", False)
    current_unit_label = st.session_state.get("current_unit", auth.get("unit", "TTN"))

    if current_user_id and current_user_id != current_user_name:
        user_display_full = f"{current_user_name} ({current_user_id})"
    else:
        user_display_full = current_user_name

    st.markdown(
        """
        <style>
        html, body, .stApp, [data-testid="stAppViewContainer"], .main,
        [data-testid="stMainBlockContainer"], .block-container {
            max-width: 100vw !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }

        [data-testid="stMainBlockContainer"], .block-container {
            padding-left: 0.4rem !important;
            padding-right: 0.4rem !important;
            padding-top: 0.6rem !important;
        }

        .section-field-label {
            font-size: 15px !important;
            font-weight: 800 !important;
            color: #F8FAFC !important;
            margin-top: 10px !important;
            margin-bottom: 8px !important;
            letter-spacing: 0.3px !important;
            line-height: 1.3 !important;
        }

        div[data-testid="stContainer"] {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.98) 0%, rgba(30, 41, 59, 0.95) 100%) !important;
            border: 1.5px solid rgba(56, 189, 248, 0.5) !important;
            border-radius: 16px !important;
            padding: 14px 14px 6px 14px !important;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), inset 0 2px 8px rgba(0, 0, 0, 0.4) !important;
            margin-bottom: 12px !important;
        }

        div[data-testid="stSlider"] {
            background: rgba(7, 11, 20, 0.85) !important;
            border: 1px solid rgba(56, 189, 248, 0.3) !important;
            border-radius: 12px !important;
            padding: 12px 14px 6px 14px !important;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3) !important;
            margin-bottom: 8px !important;
        }

        div[data-testid="stSliderTickBarMin"],
        div[data-testid="stSliderTickBarMax"],
        div[data-testid="stWidgetLabel"] + div [data-testid="stMarkdownContainer"] p,
        div[data-baseweb="slider"] div[role="slider"] + div {
            font-size: 15px !important;
            font-weight: 900 !important;
            color: #38BDF8 !important;
            font-family: monospace !important;
        }

        div[data-testid="stWidgetLabel"] p,
        div[data-testid="stWidgetLabel"] label,
        label[data-testid="stWidgetLabel"] p {
            font-size: 14.5px !important;
            font-weight: 800 !important;
            color: #F8FAFC !important;
            letter-spacing: 0.3px !important;
            margin-bottom: 4px !important;
        }

        div[data-testid="stCheckbox"] {
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1.5px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 10px !important;
            padding: 8px 12px !important;
            transition: all 0.25s ease-in-out !important;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3) !important;
            margin-bottom: 6px !important;
        }

        div[data-testid="stCheckbox"]:hover {
            background: rgba(30, 41, 59, 0.8) !important;
            border-color: rgba(56, 189, 248, 0.4) !important;
        }

        div[data-testid="stCheckbox"]:has(input:checked) {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(2, 132, 199, 0.25) 100%) !important;
            border-color: #38BDF8 !important;
            box-shadow: 0 0 14px rgba(56, 189, 248, 0.35), inset 0 1px 2px rgba(255, 255, 255, 0.2) !important;
        }

        button[data-testid="stBaseButton-primary"] {
            background: linear-gradient(135deg, #0284C7 0%, #1D4ED8 100%) !important;
            color: #FFFFFF !important;
            border: 1.5px solid #38BDF8 !important;
            border-radius: 12px !important;
            padding: 10px 16px !important;
            box-shadow: 0 4px 18px rgba(2, 132, 199, 0.6) !important;
            width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    role_label_str = clean_role_label(user_role)
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.98) 0%, rgba(30, 41, 59, 0.95) 100%); border: 1.5px solid rgba(56, 189, 248, 0.5); border-radius: 16px; padding: 14px; text-align: center; margin-bottom: 8px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);">
            <div style="font-size: 18px; font-weight: 900; color: #F8FAFC; letter-spacing: 1.5px; font-family: monospace;">CREW DUTY ENGINE</div>
            <div style="font-size: 10px; color: #38BDF8; font-family: monospace; letter-spacing: 0.8px; margin-top: 2px;">BUSY DOING NOTHING PRODUCTIVE // C.L.F EDITION</div>
            <div style="font-size: 10.5px; color: #94A3B8; font-family: monospace; margin-top: 6px;">
                STATUS: ACTIVE | {current_unit_label} : {user_display_full}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sys_config = load_system_config()
    announcement_text = sys_config.get("announcement", "目前為內部測試階段｜本頁面末端可聯繫管理者")

    st.markdown(
        f"""
        <div style="background: rgba(245, 158, 11, 0.15); border: 1.5px solid #F59E0B; border-radius: 10px; padding: 8px 12px; margin-bottom: 8px; text-align: center;">
            <div style="font-size: 12px; font-weight: 900; color: #FDE68A; font-family: monospace;">SYSTEM MAINTENANCE NOTICE // BETA ENVIRONMENT</div>
            <div style="font-size: 10px; color: #FCD34D; margin-top: 2px;">{announcement_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    comp.inject_slider_animation()

    # ==================== 扁平化全域狀態列與月份選擇 ====================
    available_months = get_available_months()
    if "current_query_month" not in st.session_state:
        st.session_state["current_query_month"] = available_months[0]

    if st.session_state["current_query_month"] not in available_months:
        st.session_state["current_query_month"] = available_months[0]

    sched_range = get_schedule_range()
    
    # 全域三合一狀態列 (Flat Bar) - 顯示單位與最新發布班表區間
    status_bar_html = f"""
    <div style="background: rgba(15, 23, 42, 0.9); border: 1.5px solid rgba(56, 189, 248, 0.4); border-radius: 8px; padding: 6px 12px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; font-family: monospace;">
        <div style="color: #38BDF8; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">{current_unit_label} // 最新發布班表區間</div>
        <div style="text-align: right;">
            <span style="font-size: 11px; font-weight: 900; color: #F8FAFC; letter-spacing: 0.5px;">{sched_range}</span>
        </div>
    </div>
    """
    st.markdown(status_bar_html, unsafe_allow_html=True)

    selected_month = st.selectbox(
        "選擇查詢月份",
        available_months,
        index=available_months.index(st.session_state["current_query_month"]),
        key="month_selector_box",
        format_func=lambda x: f"QUERY MONTH // {x}",
    )

    if st.session_state["current_query_month"] != selected_month:
        st.session_state["current_query_month"] = selected_month
        st.session_state.pop("win_raw_candidates", None)
        st.session_state.pop("ex_raw_candidates", None)
        st.rerun()

    active_files = get_current_role_files(selected_month)

    # ==================== 大表/完整班表檢視模式 (INSPECTION MODE) ====================
    inspect_emp_id = st.session_state.get("inspect_emp_target")
    if inspect_emp_id:
        st.markdown(
            f"""
            <div class="section-header-box" style="border-left-color: #38BDF8; padding: 10px 14px !important; margin-bottom: 12px !important;">
                <div style="font-size: 15px; font-weight: 900; color: #38BDF8; font-family: monospace;">
                    [{current_unit_label}] 組員完整班表檢視：{inspect_emp_id}
                </div>
                <div style="font-size: 10px; color: #94A3B8; font-family: monospace;">INSPECTION MODE // FULL SCHEDULE VIEW</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("上一頁 (返回快篩結果)", key="btn_back_to_filter", use_container_width=True):
            st.session_state["inspect_emp_target"] = None
            st.rerun()

        try:
            start_dt, dates, emp_id, emp_name, cells = process_file_data(inspect_emp_id)
            with st.spinner(f"正在讀取【{emp_name}】完整班表，請稍候..."):
                buf = render_schedule_figure(
                    start_dt,
                    dates,
                    emp_id,
                    emp_name,
                    cells,
                    current_unit_label,
                    badge_title="Producer | C.L.F",
                )
            st.success(f"【{emp_name} ({emp_id})】完整班表載入完成！")

            comp.render_zoomable_image(buf)

            st.download_button(
                "點此下載班表影像檔",
                data=buf,
                file_name=f"{current_unit_label}_班表_{emp_name}.png",
                mime="image/png",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"繪製組員班表時發生錯誤：{e}")

        st.stop()

    missing_files = [
        role
        for role in ["駕駛", "列車長", "服勤員"]
        if not isinstance(active_files.get(role, ""), str)
        or not os.path.exists(active_files.get(role, ""))
        or os.path.getsize(active_files.get(role, "")) == 0
    ]

    if missing_files:
        st.error(
            f"【{current_unit_label}】所選月份（{selected_month}）資料庫異常或尚無檔案：請洽管理員上傳！"
        )

    td_time = get_file_mtime_str(active_files.get("駕駛", ""))
    tm_time = get_file_mtime_str(active_files.get("列車長", ""))
    ta_time = get_file_mtime_str(active_files.get("服勤員", ""))

    # 隱藏式更新時間細節 (維持乾淨折疊)
    details_html = f"""
    <details style="margin: 4px 0 8px 0; font-size: 10px; color: #94A3B8; font-family: monospace; cursor: pointer;">
        <summary style="outline: none; color: #38BDF8; font-weight: 600; list-style: none; display: flex; justify-content: space-between; align-items: center; background: rgba(15,23,42,0.5); padding: 4px 8px; border-radius: 6px;">
            <span>[{current_unit_label}] 點擊檢視各大表更新時間 ({selected_month})</span>
            <span style="font-size: 9px; color: #64748B;">▼</span>
        </summary>
        <div style="display: flex; flex-direction: column; gap: 3px; margin-top: 4px; padding: 6px 8px; background: rgba(15,23,42,0.8); border-radius: 6px; border: 1px solid rgba(56,189,248,0.2);">
            <div style="display: flex; justify-content: space-between;"><span>駕駛 (TD)</span><span>{td_time}</span></div>
            <div style="display: flex; justify-content: space-between;"><span>列車長 (TM)</span><span>{tm_time}</span></div>
            <div style="display: flex; justify-content: space-between;"><span>服勤員 (TA)</span><span>{ta_time}</span></div>
        </div>
    </details>
    """
    st.html(details_html)

    st.markdown('<div class="section-field-label">選擇系統操作模式</div>', unsafe_allow_html=True)

    if "active_app_mode" not in st.session_state:
        st.session_state["active_app_mode"] = "個人月班表"

    # ==================== 航太級 Command HUD 互動切換列 ====================
    col_hud1, col_hud2, col_hud3 = st.columns(3)

    with col_hud1:
        is_mode_1 = st.session_state["active_app_mode"] == "個人月班表"
        if st.button("個人月班表", key="tab_hud_1", use_container_width=True, type="primary" if is_mode_1 else "secondary"):
            if not is_mode_1:
                st.session_state["active_app_mode"] = "個人月班表"
                st.session_state.pop("win_raw_candidates", None)
                st.session_state.pop("ex_raw_candidates", None)
                st.session_state["ex_search_performed"] = False
                st.rerun()

    with col_hud2:
        is_mode_2 = st.session_state["active_app_mode"] == "換班查詢"
        if st.button("換班查詢", key="tab_hud_2", use_container_width=True, type="primary" if is_mode_2 else "secondary"):
            if not is_mode_2:
                st.session_state["active_app_mode"] = "換班查詢"
                st.session_state.pop("win_raw_candidates", None)
                st.session_state.pop("ex_raw_candidates", None)
                st.session_state["ex_search_performed"] = False
                st.rerun()

    with col_hud3:
        is_mode_3 = st.session_state["active_app_mode"] == "換假查詢"
        if st.button("換假查詢", key="tab_hud_3", use_container_width=True, type="primary" if is_mode_3 else "secondary"):
            if not is_mode_3:
                st.session_state["active_app_mode"] = "換假查詢"
                st.session_state.pop("win_raw_candidates", None)
                st.session_state.pop("ex_raw_candidates", None)
                st.session_state["ex_search_performed"] = False
                st.rerun()

    app_mode = st.session_state["active_app_mode"]

    st.markdown("---")

    # ==================== 模式一：個人月班表 ====================
    if app_mode == "個人月班表":
        if is_module_maintenance(current_unit_label, "producer"):
            if not is_admin_user:
                st.warning("【個人月班表】系統維護中，暫不開放服務。")
                st.stop()

        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.7); border-left: 3px solid #38BDF8; padding: 8px 12px; margin-bottom: 10px; border-radius: 4px; font-family: monospace;">
                <div style="font-size: 13px; font-weight: 900; color: #F8FAFC;">個人班表圖檔生成</div>
                <div style="font-size: 9.5px; color: #38BDF8; margin-top: 2px;">PERSONAL SHIFT SCHEDULE IMAGE GENERATOR</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form(key="draw_schedule_form", border=False):
            default_emp_val = current_user_id if current_user_id else st.session_state.get("draw_input_key", "")
            draw_field_label = "請輸入您的員編或姓名 (例如: A023300)"

            user_input_val = st.text_input(
                draw_field_label,
                value=default_emp_val,
                key="draw_input_key",
            )
            submit_btn = st.form_submit_button(
                "開始繪製月班表", type="primary", use_container_width=True
            )

        if submit_btn:
            current_input = user_input_val.strip() if user_input_val else current_user_id

            if not current_input or current_input.upper() == "A":
                st.warning("請輸入有效的員編或姓名（例如: A023300）")
            else:
                try:
                    start_dt, dates, emp_id, emp_name, cells = process_file_data(
                        current_input
                    )
                    log_activity(
                        "個人班表繪製",
                        f"操作者:{current_user_id} | 單位:{current_unit_label} | 月份:{selected_month} | 查詢關鍵字:{current_input} | 成功解析組員:{emp_name}({emp_id})"
                    )

                    with st.spinner(f"正在繪製【{emp_name}】的個人月班表，請稍候..."):
                        buf = render_schedule_figure(
                            start_dt,
                            dates,
                            emp_id,
                            emp_name,
                            cells,
                            current_unit_label,
                            badge_title="Producer | C.L.F",
                        )
                    st.success(f"【{emp_name}】個人班表圖片生成成功！")

                    comp.render_zoomable_image(buf)

                    st.download_button(
                        "點此下載班表影像檔",
                        data=buf,
                        file_name=f"{current_unit_label}_{selected_month}_班表_{emp_name}.png",
                        mime="image/png",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"繪製班表時發生錯誤：{e}")

    # ==================== 模式二：換班查詢 ====================
    elif app_mode == "換班查詢":
        if is_module_maintenance(current_unit_label, "window_filter"):
            if not is_admin_user:
                st.warning("【換班日期快篩】系統維護中，暫不開放服務。")
                st.stop()

        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.7); border-left: 3px solid #38BDF8; padding: 8px 12px; margin-bottom: 10px; border-radius: 4px; font-family: monospace;">
                <div style="font-size: 13px; font-weight: 900; color: #F8FAFC;">換班檢索｜指定 Sign-In 時段組員快篩</div>
                <div style="font-size: 9.5px; color: #38BDF8; margin-top: 2px;">DUTY TIME WINDOW & SIGN-IN FILTER MATRIX</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-field-label">選擇查詢職位</div>', unsafe_allow_html=True)

        if "saved_win_roles" not in st.session_state:
            st.session_state["saved_win_roles"] = ["服勤員"]

        if hasattr(st, "segmented_control"):
            selected_roles = st.segmented_control(
                "選擇查詢職位",
                options=["服勤員", "列車長", "駕駛"],
                default=st.session_state["saved_win_roles"],
                selection_mode="multi",
                label_visibility="collapsed",
                key="win_seg_roles",
                on_change=reset_win_search,
            )
        else:
            selected_roles = st.multiselect(
                "選擇查詢職位",
                options=["服勤員", "列車長", "駕駛"],
                default=st.session_state["saved_win_roles"],
                label_visibility="collapsed",
                key="win_multi_roles",
                on_change=reset_win_search,
            )

        roles_to_query = list(selected_roles) if selected_roles else []
        if roles_to_query:
            st.session_state["saved_win_roles"] = roles_to_query

        if not roles_to_query:
            st.warning("請至少選取一個職位以進行查詢")
        else:
            has_driver = "駕駛" in roles_to_query
            start_h = 3 if has_driver else 5

            TIME_OPTIONS = [
                f"{h:02d}:{m:02d}"
                for h in range(start_h, 19)
                for m in (0, 30)
                if not (h == 18 and m == 30)
            ]

            valid_paths = {}
            for r_name in roles_to_query:
                p = active_files.get(r_name, "")
                if p and isinstance(p, str) and os.path.exists(p) and os.path.getsize(p) > 0:
                    valid_paths[r_name] = p

            if not valid_paths:
                st.error(f"找不到【{current_unit_label}】所選月份的班表檔案，請先確認檔案是否存在")
            else:
                first_role, first_path = list(valid_paths.items())[0]
                df_search_sample = safe_read_excel(first_path, header=3)
                df_search_sample.columns = [str(c).strip() for c in df_search_sample.columns]
                date_cols = [
                    normalize_date_str(col)
                    for col in df_search_sample.columns[2:]
                    if normalize_date_str(col)
                ]

                if date_cols:
                    default_win_idx = 0
                    saved_target_date = st.session_state.get("saved_win_target_date")
                    if saved_target_date and saved_target_date in date_cols:
                        default_win_idx = date_cols.index(saved_target_date)

                    target_date = st.selectbox(
                        "選擇換班日期",
                        date_cols,
                        index=default_win_idx,
                        format_func=lambda d: get_date_label(d, df_search_sample.columns),
                        key="win_target_date",
                        on_change=reset_win_search,
                    )
                    st.session_state["saved_win_target_date"] = target_date

                    win_week_holidays = get_week_holidays(
                        target_date, date_cols, df_search_sample.columns
                    )
                    _, win_week_str = check_week_has_holiday(
                        target_date, date_cols, df_search_sample.columns
                    )

                    comp.show_holiday_notice(win_week_holidays, win_week_str)

                    if "saved_win_time_range" not in st.session_state:
                        st.session_state["saved_win_time_range"] = (TIME_OPTIONS[0], TIME_OPTIONS[-1])

                    curr_saved = st.session_state["saved_win_time_range"]
                    if not isinstance(curr_saved, (tuple, list)) or len(curr_saved) != 2:
                        curr_saved = (TIME_OPTIONS[0], TIME_OPTIONS[-1])

                    slider_val = st.select_slider(
                        "Sign-In 時段區間",
                        options=TIME_OPTIONS,
                        value=curr_saved,
                        key="win_time_slider_widget",
                        on_change=reset_win_search,
                        label_visibility="collapsed",
                    )

                    st.session_state["saved_win_time_range"] = slider_val
                    min_time, max_time_sel = slider_val

                    filter_col1, filter_col2 = st.columns(2)
                    with filter_col1:
                        only_main_line = st.checkbox("僅顯示正線勤務", value=st.session_state.get("saved_win_main_line", False), key="win_main_line")
                        st.session_state["saved_win_main_line"] = only_main_line
                    with filter_col2:
                        only_long_shift = st.checkbox("僅顯示長班 (>8.5h)", value=st.session_state.get("saved_win_long_shift", False), key="win_long_shift")
                        st.session_state["saved_win_long_shift"] = only_long_shift

                    search_clicked = st.button("搜尋可換班組員名單", key="btn_window_search", type="primary", use_container_width=True)

        if search_clicked:
            raw_candidates = []
            search_min_time, search_max_time = slider_val

            for r_name, p_path in valid_paths.items():
                df_search = safe_read_excel(p_path, header=3)
                df_search.columns = [str(c).strip() for c in df_search.columns]
                target_col_idx = find_date_column_index(df_search.columns, target_date)

                if target_col_idx != -1:
                    for _, row in df_search.iterrows():
                        emp_id = str(row.iloc[0]).strip()
                        emp_name = str(row.iloc[1]).strip()
                        if not emp_id or emp_id.upper() in ["NAN", "NONE", ""]:
                            continue

                        if target_col_idx < len(row):
                            cell_raw = row.iloc[target_col_idx]
                            parsed = parse_cell(cell_raw)
                            start_t = parsed["start"]
                            is_off = is_cell_off_day(cell_raw)

                            if not is_off or start_t:
                                s_time_str = str(start_t).strip() if start_t else "--:--"
                                if s_time_str == "--:--" or not (search_min_time <= s_time_str <= search_max_time):
                                    continue

                                tr_upper = str(parsed["train"]).strip().upper()
                                raw_cell_upper = str(cell_raw).upper()
                                is_leave = any(k in raw_cell_upper for k in LEAVE_CODES) or tr_upper in LEAVE_CODES
                                is_non_line = is_town_shift(parsed["train"], parsed["note"])
                                is_long = is_overtime(parsed["hours"], parsed["train"], parsed["note"])

                                if only_main_line and (is_non_line or is_leave):
                                    continue
                                if only_long_shift and not is_long:
                                    continue

                                do_match = re.search(r"(DO\d*W?|D\d+W|OGC)", str(cell_raw), re.IGNORECASE)
                                do_tag = do_match.group(1).upper() if do_match else ""

                                next_day_sign_in = "無"
                                if target_col_idx + 1 < len(row):
                                    next_parsed = parse_cell(row.iloc[target_col_idx + 1])
                                    next_day_sign_in = next_parsed["start"] if next_parsed["start"] else (next_parsed["train"] if next_parsed["train"] else "無")

                                raw_candidates.append({
                                    "日期": target_date,
                                    "職位": r_name,
                                    "員編": emp_id,
                                    "姓名": emp_name,
                                    "Sign-In": s_time_str,
                                    "Sign-Out": parsed["end"] if parsed["end"] else "--:--",
                                    "工時": parsed.get("hours", ""),
                                    "車次": translate_train_code(parsed["train"]),
                                    "隔日Sign-In": next_day_sign_in,
                                    "長班": is_long,
                                    "非正線": is_non_line,
                                    "請假": is_leave,
                                    "出勤標記": do_tag,
                                })

            st.session_state["win_raw_candidates"] = raw_candidates
            st.rerun()

        if st.session_state.get("win_raw_candidates") is not None:
            filtered_results = st.session_state["win_raw_candidates"]
            ROLE_ORDER = {"服勤員": 1, "列車長": 2, "駕駛": 3}
            filtered_results = sorted(
                filtered_results,
                key=lambda x: (
                    str(x["Sign-In"]) if x["Sign-In"] != "--:--" else "99:99",
                    get_shift_group_num(x["車次"]),
                    ROLE_ORDER.get(x.get("職位", ""), 9),
                    str(x["車次"]),
                ),
            )

            st.markdown(f"### 換班可選人員名單（共符合 {len(filtered_results)} 筆）")
            for i in range(0, len(filtered_results), 2):
                batch = filtered_results[i : i + 2]
                cols = st.columns(2)
                for idx_in_batch, r in enumerate(batch):
                    with cols[idx_in_batch]:
                        clean_name = str(r.get("姓名", "")).replace("\n", " ").strip()
                        clean_id = str(r.get("員編", "")).replace("\n", " ").strip()
                        clean_train = str(r.get("車次", "")).replace("\n", " ").strip()
                        clean_signin = str(r.get("Sign-In", "--:--")).replace("\n", " ").strip()
                        clean_signout = str(r.get("Sign-Out", "--:--")).replace("\n", " ").strip()
                        
                        st.info(f"**{clean_name} ({clean_id})**\n車次: {clean_train} | In: {clean_signin} / Out: {clean_signout}")
                        if st.button(f"檢視 {clean_name} 完整班表 ➔", key=f"win_btn_{clean_id}_{i+idx_in_batch}", use_container_width=True):
                            st.session_state["inspect_emp_target"] = clean_id
                            st.rerun()

    # ==================== 模式三：換假查詢 ====================
    elif app_mode == "換假查詢":
        if is_module_maintenance(current_unit_label, "exchange_filter"):
            if not is_admin_user:
                st.warning("【換假日期快篩】系統維護中，暫不開放服務。")
                st.stop()

        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.7); border-left: 3px solid #38BDF8; padding: 8px 12px; margin-bottom: 10px; border-radius: 4px; font-family: monospace;">
                <div style="font-size: 13px; font-weight: 900; color: #F8FAFC;">換假檢索｜選擇換假日期快篩</div>
                <div style="font-size: 9.5px; color: #38BDF8; margin-top: 2px;">SHIFT EXCHANGE DATE FILTER MATRIX</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        selected_role = st.selectbox("選擇職位類別", ["服勤員", "駕駛", "列車長"], key="ex_role_select", on_change=reset_ex_search)
        sample_path = active_files.get(selected_role, "")

        if not sample_path or not isinstance(sample_path, str) or not os.path.exists(sample_path):
            st.error(f"找不到【{current_unit_label} - {selected_role}】的班表檔案")
        else:
            try:
                df_ex = safe_read_excel(sample_path, header=3)
                df_ex.columns = [str(c).strip() for c in df_ex.columns]
                date_cols = [normalize_date_str(c) for c in df_ex.columns[2:] if normalize_date_str(c)]

                if date_cols:
                    ex_date_col1, ex_date_col2 = st.columns(2)
                    with ex_date_col1:
                        target_date = st.selectbox("選擇想休假日期", date_cols, key="ex_target_date", on_change=reset_ex_search)
                    with ex_date_col2:
                        return_date = st.selectbox("選擇可還假日期", date_cols, key="ex_return_date", on_change=reset_ex_search)

                    if st.button("搜尋可換假組員名單", key="btn_ex_search", type="primary", use_container_width=True):
                        st.success("搜尋完成！")
            except Exception as e:
                st.error(f"讀取換假資料時發生錯誤：{e}")


if __name__ == "__main__":
    render_user_home()
