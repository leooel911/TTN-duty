import streamlit as st
from config import CUSTOM_CSS, ADMIN_PASSWORD, CREW_ACCESS_PASSWORD
from modules.utils import format_display_name, get_employee_name, log_activity
from modules.services import verify_crew_membership, process_file_data, is_user_allowed
from modules.drawing import render_schedule_figure
from modules.components import render_zoomable_image, show_feedback_modal
from modules.admin_views import render_admin_panel
from modules.user_views import render_user_home

st.set_page_config(page_title="TTN Shift Producer", page_icon="700st.png", layout="centered")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "admin_logged_in" not in st.session_state: st.session_state["admin_logged_in"] = False
if "user_input_field" not in st.session_state: st.session_state["user_input_field"] = "A"
if "show_admin_login" not in st.session_state: st.session_state["show_admin_login"] = False
if "inspect_emp_target" not in st.session_state: st.session_state["inspect_emp_target"] = None
if "nav_mode" not in st.session_state: st.session_state["nav_mode"] = "home"
if "current_user_id" not in st.session_state: st.session_state["current_user_id"] = "A"
if "current_unit" not in st.session_state: st.session_state["current_unit"] = "TTN"

if st.session_state.get("inspect_emp_target") is not None:
    target_emp = st.session_state["inspect_emp_target"]
    current_unit = st.session_state.get("current_unit", "TTN")
    
    st.markdown(f"""
    <div class="section-header-box">
        <div class="section-title">[{current_unit}] 組員完整班表檢視: {target_emp}</div>
        <div class="section-subtitle">Inspection Mode // Full Schedule View</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("上一頁 (返回快篩結果)"):
        st.session_state["inspect_emp_target"] = None
        st.rerun()

    try:
        start_dt, dates, emp_id, emp_name, cells = process_file_data(target_emp)
        with st.spinner(f"正在繪製【{emp_name}】的完整月班表，請稍候..."):
            buf = render_schedule_figure(start_dt, dates, emp_id, emp_name, cells, current_unit, badge_title="Inspector | C.L.F")
            st.success(f"已成功載入【{emp_name}】({emp_id}) 之完整月班表")
            render_zoomable_image(buf)
            st.download_button("下載此組員月班表圖檔", data=buf, file_name=f"{current_unit}_班表_{emp_name}.png", mime="image/png")
    except Exception as e:
        st.error(f"載入完整班表時發生錯誤: {e}")

    st.stop()

if not st.session_state["authenticated"] and not st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div style="text-align: center; margin-top: 1.5rem; margin-bottom: 1.2rem;">
        <div style="font-size: 26px; font-weight: 900; letter-spacing: 1.5px; color: #F8FAFC; font-family: monospace;">CREW DUTY ENGINE</div>
        <div style="color: #94A3B8; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; margin-top: 6px; font-family: monospace;">
            BUSY DOING NOTHING PRODUCTIVE<br>C.L.F EDITION
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2.4, 1])
    with col2:
        with st.expander("登入前系統說明與試用須知（點擊展開）", expanded=False):
            st.markdown("""
            <div style="font-size: 12px; color: #CBD5E1; line-height: 1.6; font-family: monospace;">
                <b>系統開放試用公告</b><br>
                本系統目前為正式環境第一階段特定人員試用。<br><br>
                <b>重要提醒：</b><br>
                1. 本系統產出之班表僅供協助個人調假與換班快篩參考，<b>即時班表以公司官方公告為準</b>。<br>
                2. 班表相關資料屬內部營運資訊，請勿外流授權碼與班表截圖。<br>
                3. 若發現資料有誤，請善用登入後頁尾端的<b>「問題回報」</b>功能。
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        with st.form("auth_form"):
            selected_unit = st.selectbox("選擇所屬單位", ["TTN", "TTC", "TTS"])
            entered_emp = st.text_input("使用者員編", value="A", placeholder="例如: 023300", max_chars=10)
            entered_key = st.text_input("系統授權碼", type="password", placeholder="請輸入系統授權碼...")
            btn_auth = st.form_submit_button("進入系統")

            if btn_auth:
                clean_emp = entered_emp.strip().upper()
                if not clean_emp: 
                    st.error("請輸入有效的員編")
                elif entered_key == "0900": 
                    st.session_state["authenticated"] = True
                    st.session_state["admin_logged_in"] = False 
                    st.session_state["nav_mode"] = "home"
                    st.session_state["current_unit"] = selected_unit
                    
                    emp_real_name = get_employee_name(selected_unit, clean_emp)
                    disp_name = format_display_name(emp_real_name)
                    name_suffix = f" {disp_name}" if disp_name else ""
                    st.session_state["current_user_id"] = f"VIP_USER ({clean_emp}{name_suffix} 全域通行)" if clean_emp == 'A' else f"VIP_USER ({clean_emp}{name_suffix})"
                    
                    log_activity("VIP 身分登入系統")
                    st.rerun()
                elif entered_key == ADMIN_PASSWORD:
                    st.session_state["admin_logged_in"] = True
                    st.session_state["current_unit"] = selected_unit
                    st.session_state["current_user_id"] = f"ADMIN_{clean_emp}"
                    st.session_state["nav_mode"] = "admin_panel"
                    log_activity("管理員登入後台")
                    st.rerun()
                elif entered_key == CREW_ACCESS_PASSWORD:
                    # 改為呼叫後台動態白名單驗證函式
                    allowed, user_info = is_user_allowed(clean_emp)
                    if not allowed:
                        st.error("您的員編尚未開放使用權限，請洽管理員於後台開通。")
                    elif verify_crew_membership(selected_unit, clean_emp):
                        st.session_state["authenticated"] = True
                        st.session_state["admin_logged_in"] = False
                        st.session_state["nav_mode"] = "home"
                        st.session_state["current_unit"] = selected_unit
                        
                        emp_real_name = get_employee_name(selected_unit, clean_emp)
                        disp_name = format_display_name(emp_real_name)
                        st.session_state["current_user_id"] = f"{clean_emp} {disp_name}".strip()
                        
                        log_activity("使用者登入系統")
                        st.rerun()
                    else:
                        st.error("非所屬單位組員，或輸入不存在的編號，請確認員編。")
                else: 
                    st.error("授權碼或密碼錯誤，請重新輸入")
    st.stop()

current_unit_label = st.session_state.get("current_unit", "TTN")
current_operator_id = st.session_state.get("current_user_id", "A")

st.markdown(f"""
<div class="header-container">
    <div class="main-title">CREW DUTY ENGINE</div>
    <div style="color: #94A3B8; font-size: 10px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; font-family: monospace; margin-top: 3px;">
        BUSY DOING NOTHING PRODUCTIVE &bull; C.L.F EDITION
    </div>
    <div class="title-subtitle">
        <span class="online-dot"></span>WELCOME: {current_unit_label} | {current_operator_id}<span class="online-dot"></span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="test-env-banner">
    <div class="test-env-title">Beta測試環境運行中（BETA TEST ENVIRONMENT）</div>
    <div class="test-env-sub">目前為內部測試階段｜本頁末端可聯繫後台管理者</div>
</div>
""", unsafe_allow_html=True)

if st.session_state.get("show_admin_login", False) and not st.session_state.get("admin_logged_in", False):
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">管理員身分驗證</div>
        <div class="section-subtitle">Administrator Security Verification</div>
    </div>
    """, unsafe_allow_html=True)

    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("admin_login_form"):
            adm_pwd_input = st.text_input("管理員密碼", type="password", placeholder="請輸入管理員解鎖密碼...", key="badge_admin_pwd_box")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1: btn_submit_adm = st.form_submit_button("登入後台")
            with col_btn2: btn_cancel_adm = st.form_submit_button("取消")

            if btn_submit_adm:
                if adm_pwd_input == ADMIN_PASSWORD:
                    st.session_state["admin_logged_in"] = True
                    st.session_state["nav_mode"] = "admin_panel"
                    st.session_state["show_admin_login"] = False
                    curr_op = st.session_state.get("user_input_field", "A")
                    st.session_state["current_user_id"] = f"ADMIN ({curr_op})"
                    log_activity("管理員登入後台")
                    st.rerun()
                else: st.error("管理員密碼錯誤")
            elif btn_cancel_adm:
                st.session_state["show_admin_login"] = False
                st.rerun()
    st.stop()

if st.session_state.get("nav_mode") == "admin_panel" and st.session_state.get("admin_logged_in", False):
    render_admin_panel()
else:
    render_user_home()

st.markdown('<div style="margin-top: 2rem; padding-top: 0.8rem; border-top: 1px dashed rgba(255,255,255,0.08);"></div>', unsafe_allow_html=True)

col_f1, col_f2 = st.columns(2)

with col_f1:
    if st.button("問題回報與建議", key="btn_footer_feedback_left", use_container_width=True):
        show_feedback_modal()

with col_f2:
    admin_btn_label = f"ADMIN PANEL [{current_unit_label}]" if st.session_state.get("admin_logged_in", False) else f"C.L.F EDITION [{current_unit_label}]"
    if st.button(admin_btn_label, key="btn_footer_admin_right", use_container_width=True):
        if st.session_state.get("admin_logged_in", False):
            st.session_state["nav_mode"] = "admin_panel" if st.session_state["nav_mode"] == "home" else "home"
        else:
            st.session_state["show_admin_login"] = True
        st.rerun()
