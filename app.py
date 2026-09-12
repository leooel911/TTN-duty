import streamlit as st
from config import ADMIN_PASSWORD, CREW_ACCESS_PASSWORD, CUSTOM_CSS
from modules.admin_views import render_admin_panel
from modules.components import render_zoomable_image, show_feedback_modal
from modules.drawing import render_schedule_figure
from modules.services import (
    authenticate_user,
    is_user_allowed,
    load_system_config,
    process_file_data,
    verify_crew_membership,
)
from modules.user_views import render_user_home
from modules.utils import (
    format_display_name,
    get_employee_name,
    log_activity,
    send_admin_email,
)

# ---------------------------------------------------------
# 載入全域動態設定 (每次 Rerun 時重新載入最新設定)
# ---------------------------------------------------------
sys_cfg = load_system_config()
ADMIN_PASS_CODE = sys_cfg.get("admin_password") or ADMIN_PASSWORD
DEFAULT_EMP_ID = sys_cfg.get("default_emp_id", "A")

st.set_page_config(
    page_title="TTN Shift Producer", page_icon="700st.png", layout="centered"
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------
# 權限申請彈出視窗對話框 (Dialog)
# ---------------------------------------------------------
@st.dialog("申請系統使用權限")
def show_apply_permission_dialog():
    st.markdown(
        """
        <div style="font-size: 13px; color: #94A3B8; margin-bottom: 12px;">
            請填寫基本資料，送出後系統將自動發送通知信給管理員進行審核與開通。
        </div>
        """,
        unsafe_allow_html=True,
    )

    req_unit = st.selectbox("選擇所屬單位", ["TTN", "TTC", "TTS", "其他單位"], key="dlg_req_unit")
    req_emp_id = st.text_input("使用者員編 (例如: 023300)", key="dlg_req_emp_id")
    req_name = st.text_input("真實姓名 (例如: 波莉)", key="dlg_req_name")
    req_reason = st.text_area("申請原因 / 備註 (選填)", key="dlg_req_reason", help="說明用途可加速審核")

    col_sub1, col_sub2 = st.columns([1, 1])
    with col_sub1:
        submit_clicked = st.button("確認送出申請", type="primary", use_container_width=True)
    with col_sub2:
        if st.button("關閉視窗", use_container_width=True):
            st.session_state["show_apply_dialog"] = False
            st.rerun()

    if submit_clicked:
        clean_emp = req_emp_id.strip().upper()
        clean_name = req_name.strip()

        if not clean_emp or not clean_name:
            st.warning("請完整填寫「員編」與「姓名」！")
        else:
            with st.spinner("正在記錄申請並發送通知信..."):
                log_activity(
                    action="權限申請",
                    detail=f"單位:{req_unit} | 員編:{clean_emp} | 姓名:{clean_name} | 原因:{req_reason}",
                    user=clean_emp,
                    unit=req_unit,
                )
                success, msg = send_admin_email(req_unit, clean_emp, clean_name, req_reason)

            if success:
                st.success("申請已成功送出！管理員已收到信件通知，請靜候開通。")
            else:
                st.success("申請已成功記錄！(已登記於系統，可聯繫管理員)")

            st.session_state["show_apply_dialog"] = False


# ---------------------------------------------------------
# Session State 初始化
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "admin_logged_in" not in st.session_state:
    st.session_state["admin_logged_in"] = False
if "user_input_field" not in st.session_state:
    st.session_state["user_input_field"] = DEFAULT_EMP_ID
if "show_admin_login" not in st.session_state:
    st.session_state["show_admin_login"] = False
if "show_feedback_dialog" not in st.session_state:
    st.session_state["show_feedback_dialog"] = False
if "show_apply_dialog" not in st.session_state:
    st.session_state["show_apply_dialog"] = False
if "inspect_emp_target" not in st.session_state:
    st.session_state["inspect_emp_target"] = None
if "nav_mode" not in st.session_state:
    st.session_state["nav_mode"] = "home"
if "page" not in st.session_state:
    st.session_state["page"] = "user"
if "current_user_id" not in st.session_state:
    st.session_state["current_user_id"] = DEFAULT_EMP_ID
if "login_user_id" not in st.session_state:
    st.session_state["login_user_id"] = DEFAULT_EMP_ID
if "current_unit" not in st.session_state:
    st.session_state["current_unit"] = "TTN"


# ---------------------------------------------------------
# 🛡️ 前置授權碼門戶檢查 (無 Form 化設計，徹底杜絕重複渲染)
# ---------------------------------------------------------
is_authed = st.session_state.get("authenticated", False)
is_admin_authed = st.session_state.get("admin_logged_in", False)

if not is_authed and not is_admin_authed:
    st.markdown(
        """
    <div style="text-align: center; margin-top: 1.5rem; margin-bottom: 1.2rem;">
        <div style="font-size: 26px; font-weight: 900; letter-spacing: 1.5px; color: #F8FAFC; font-family: monospace;">CREW DUTY ENGINE</div>
        <div style="color: #94A3B8; font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; margin-top: 6px; font-family: monospace;">
            BUSY DOING NOTHING PRODUCTIVE<br>C.L.F EDITION
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2.4, 1])
    with col2:
        with st.expander("登入前系統說明與試用須知（點擊展開）", expanded=False):
            st.markdown(
                """
            <div style="font-size: 12.5px; color: #CBD5E1; line-height: 1.7; font-family: monospace;">
                <div style="color: #38BDF8; font-weight: 800; margin-bottom: 6px;">系統開放試用公告</div>
                本系統目前為正式環境第一階段特定人員內部測試。<br><br>
                <div style="color: #FBBF24; font-weight: 800; margin-bottom: 4px;">重要提醒與注意事項：</div>
                1. <b>排班依據</b>：本系統班表僅供個人調假與換班快篩參考，<b>即時班表務必以公司官方公告為準</b>。<br>
                2. <b>資訊安全</b>：班表相關資料屬內部營運資訊，<b>請勿外流授權碼與班表截圖</b>。<br>
                3. <b>權限與回報</b>：尚無權限者請點選下方<b>「申請使用權限」</b>；登入後若發現資料有誤，請善用頁尾<b>「問題回報」</b>。
            </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        
        selected_unit = st.selectbox("選擇所屬單位", ["TTN", "TTC", "TTS"], key="login_unit_box")
        entered_emp = st.text_input(
            "使用者員編 (範例：023300)",
            value=DEFAULT_EMP_ID,
            placeholder="例如: 023300",
            max_chars=10,
            key="login_emp_box",
        )
        entered_key = st.text_input(
            "系統授權碼", type="password", placeholder="請輸入系統授權碼...", key="login_key_box"
        )

        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            btn_auth = st.button("進入系統", type="primary", use_container_width=True)
        with col_b2:
            btn_apply = st.button("申請使用權限", use_container_width=True)

        if btn_apply:
            st.session_state["show_apply_dialog"] = True
            st.rerun()

        if btn_auth:
            success, message, user_session = authenticate_user(selected_unit, entered_emp, entered_key)
            
            if success:
                role = user_session.get("role", "USER")
                is_adm = (role == "ADMIN")
                
                st.session_state["authenticated"] = True
                st.session_state["admin_logged_in"] = is_adm
                st.session_state["show_admin_login"] = False  # 強制關閉管理員登入彈窗，防止 VIP 發生跳兩次
                st.session_state["nav_mode"] = "admin_panel" if is_adm else "home"
                st.session_state["page"] = "admin" if is_adm else "user"
                st.session_state["current_unit"] = user_session.get("unit", selected_unit)
                st.session_state["login_user_id"] = user_session.get("emp_id", "")
                
                emp_name = user_session.get("emp_name", "")
                emp_id = user_session.get("emp_id", "")
                
                if is_adm:
                    st.session_state["current_user_id"] = f"ADMIN ({emp_id})"
                else:
                    st.session_state["current_user_id"] = f"{emp_name} ({emp_id})" if emp_name else emp_id

                log_activity(
                    action="帳號登入",
                    detail=f"登入成功: {emp_name} ({emp_id}) | 角色: {role}",
                    user=emp_id,
                    unit=selected_unit,
                )
                st.rerun()
            else:
                st.error(f"❌ {message}")

        if st.session_state.get("show_apply_dialog", False):
            show_apply_permission_dialog()

    st.stop()


# ---------------------------------------------------------
# 組員完整班表檢視模式 (Inspector Mode)
# ---------------------------------------------------------
if st.session_state.get("inspect_emp_target") is not None:
    target_emp = st.session_state["inspect_emp_target"]
    current_unit = st.session_state.get("current_unit", "TTN")

    st.markdown(
        f"""
    <div class="section-header-box">
        <div class="section-title">[{current_unit}] 組員完整班表檢視: {target_emp}</div>
        <div class="section-subtitle">Inspection Mode // Full Schedule View</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if st.button("上一頁 (返回快篩結果)"):
        st.session_state["inspect_emp_target"] = None
        st.rerun()

    try:
        start_dt, dates, emp_id, emp_name, cells = process_file_data(target_emp)
        with st.spinner(f"正在繪製【{emp_name}】的完整月班表，請稍候..."):
            buf = render_schedule_figure(
                start_dt,
                dates,
                emp_id,
                emp_name,
                cells,
                current_unit,
                badge_title="Inspector | C.L.F",
            )
            st.success(f"已成功載入【{emp_name}】({emp_id}) 之完整月班表")
            render_zoomable_image(buf)

            col_dl1, col_dl2 = st.columns([1, 1])
            with col_dl1:
                st.download_button(
                    "下載此組員月班表圖檔",
                    data=buf,
                    file_name=f"{current_unit}_班表_{emp_name}.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with col_dl2:
                st.markdown(
                    """
                    <div style="display: flex; align-items: center; height: 100%; font-size: 12px; color: #94A3B8; font-weight: 500; font-family: monospace; padding-left: 6px;">
                        提示：手機使用者可長按圖片儲存至相簿
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    except Exception as e:
        st.error(f"載入組員【{target_emp}】班表時發生錯誤：{e}")

    st.stop()


# ---------------------------------------------------------
# 主頁面 Header 資訊區
# ---------------------------------------------------------
current_unit_label = st.session_state.get("current_unit", "TTN")
current_operator_id = st.session_state.get("current_user_id", DEFAULT_EMP_ID)

st.markdown(
    f"""
<div class="header-container">
    <div class="main-title">CREW DUTY ENGINE</div>
    <div style="color: #94A3B8; font-size: 10px; font-weight: 600; letter-spacing: 1.2px; text-transform: uppercase; font-family: monospace; margin-top: 3px;">
        BUSY DOING NOTHING PRODUCTIVE &bull; C.L.F EDITION
    </div>
    <div class="title-subtitle">
        <span class="online-dot"></span>WELCOME: {current_unit_label} | {current_operator_id}<span class="online-dot"></span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 動態公告與橫幅標語渲染 (連動 sys_config)
# ---------------------------------------------------------
enable_beta_banner = sys_cfg.get("enable_beta_notice", True)
announcement_msg = sys_cfg.get("announcement", "目前為內部測試階段｜本頁末端可聯繫後台管理者")

if enable_beta_banner:
    st.markdown(
        f"""
    <div class="test-env-banner">
        <div class="test-env-title">Beta測試環境運行中（BETA TEST ENVIRONMENT）</div>
        <div class="test-env-sub">{announcement_msg}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------
# 管理員二次密碼驗證彈窗
# ---------------------------------------------------------
if st.session_state.get("show_admin_login", False) and not st.session_state.get(
    "admin_logged_in", False
):
    st.markdown(
        """
    <div class="section-header-box">
        <div class="section-title">管理員身分驗證</div>
        <div class="section-subtitle">Administrator Security Verification</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        with st.form("admin_login_form"):
            adm_pwd_input = st.text_input(
                "管理員密碼",
                type="password",
                placeholder="請輸入管理員解鎖密碼...",
                key="badge_admin_pwd_box",
            )
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                btn_submit_adm = st.form_submit_button("登入後台")
            with col_btn2:
                btn_cancel_adm = st.form_submit_button("取消")

            if btn_submit_adm:
                if adm_pwd_input == ADMIN_PASS_CODE:
                    curr_op = st.session_state.get("user_input_field", DEFAULT_EMP_ID)
                    admin_uid = f"ADMIN_{curr_op}"
                    st.session_state["admin_logged_in"] = True
                    st.session_state["nav_mode"] = "admin_panel"
                    st.session_state["page"] = "admin"
                    st.session_state["show_admin_login"] = False
                    st.session_state["current_user_id"] = f"ADMIN ({curr_op})"
                    st.session_state["login_user_id"] = admin_uid
                    log_activity(
                        action="管理員操作",
                        detail=f"管理員登入後台 ({curr_op})",
                        user=admin_uid,
                        unit=st.session_state.get("current_unit", "全站"),
                    )
                    st.rerun()
                else:
                    st.error("管理員密碼錯誤")
            elif btn_cancel_adm:
                st.session_state["show_admin_login"] = False
                st.rerun()
    st.stop()

# ---------------------------------------------------------
# 路由切換 (管理員後台 / 一般使用者頁面)
# ---------------------------------------------------------
is_admin_active = (
    st.session_state.get("nav_mode") == "admin_panel"
    or st.session_state.get("page") == "admin"
) and st.session_state.get("page") != "user"

if is_admin_active and st.session_state.get("admin_logged_in", False):
    render_admin_panel()
else:
    render_user_home()

st.markdown(
    '<div style="margin-top: 2rem; padding-top: 0.8rem; border-top: 1px'
    ' dashed rgba(255,255,255,0.08);"></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 頁尾功能按鈕與彈窗觸發
# ---------------------------------------------------------
col_f1, col_f2 = st.columns(2)

with col_f1:
    if st.button(
        "問題回報與建議",
        key="btn_footer_feedback_left",
        use_container_width=True,
    ):
        st.session_state["show_feedback_dialog"] = True
        st.rerun()

with col_f2:
    admin_btn_label = (
        "ADMIN PANEL [Leo]"
        if st.session_state.get("admin_logged_in", False)
        else "ADMIN PANEL [C.L.F]"
    )
    if st.button(
        admin_btn_label, key="btn_footer_admin_right", use_container_width=True
    ):
        if st.session_state.get("admin_logged_in", False):
            if is_admin_active:
                st.session_state["nav_mode"] = "home"
                st.session_state["page"] = "user"
            else:
                st.session_state["nav_mode"] = "admin_panel"
                st.session_state["page"] = "admin"
        else:
            st.session_state["show_admin_login"] = True
        st.rerun()

if st.session_state.get("show_feedback_dialog", False):
    show_feedback_modal()
