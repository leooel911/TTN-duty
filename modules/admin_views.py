import io
import json
import os
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st
from config import DATA_DIR, FEEDBACK_IMG_DIR, LOG_FILE, UNITS, WHITELIST_FILE
from modules.components import view_feedback_img_modal
from modules.services import load_system_config, save_system_config
from modules.utils import (
    get_file_mtime_str,
    is_module_maintenance,
    load_activity_logs,
    log_activity,
    safe_read_excel,
    set_module_maintenance,
)


# =========================================================
#  1. 資料處理與輔助工具函式
# =========================================================
def clear_logs():
    """徹底清空全站系統操作日誌檔"""
    possible_paths = [
        LOG_FILE,
        "activity.log",
        os.path.join(DATA_DIR, "activity.log"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                with open(p, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass


def create_backup_zip():
    """打包 data 資料夾、回報工單截圖與系統設定檔為 ZIP 下載檔"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DATA_DIR):
            for root, _, files in os.walk(DATA_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=DATA_DIR)
                    zf.write(file_path, arcname=os.path.join("data", arcname))

        if os.path.exists(FEEDBACK_IMG_DIR) and not FEEDBACK_IMG_DIR.startswith(DATA_DIR):
            for root, _, files in os.walk(FEEDBACK_IMG_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=FEEDBACK_IMG_DIR)
                    zf.write(file_path, arcname=os.path.join("feedback", arcname))

        for root_file in [
            "activity.log",
            "maintenance.json",
            "whitelist.json",
            "system_config.json",
        ]:
            if os.path.exists(root_file):
                zf.write(root_file, arcname=root_file)
    buf.seek(0)
    return buf


def load_whitelist(unit_code="TTN"):
    """讀取指定營運單位的白名單（嚴格獨立隔離）"""
    whitelist_path = WHITELIST_FILE
    full_data = {}

    if os.path.exists(whitelist_path):
        try:
            with open(whitelist_path, "r", encoding="utf-8") as f:
                full_data = json.load(f)
                if full_data and not any(k in UNITS for k in full_data.keys()):
                    full_data = {"TTN": full_data}
        except Exception:
            full_data = {}

    if unit_code not in full_data:
        unit_default = {
            "ADMIN": {
                "name": f"[{unit_code}] 系統管理員",
                "role": "ADMIN",
                "note": f"[{unit_code}] 預設管理員帳號",
                "created_at": datetime.now().strftime("%Y-%m-%d"),
            }
        }
        if unit_code == "TTN":
            unit_default["A023300"] = {
                "name": "波莉",
                "role": "VIP_USER (全域通行)",
                "note": "TTN 預設測試員",
                "created_at": datetime.now().strftime("%Y-%m-%d"),
            }
        full_data[unit_code] = unit_default

    return full_data.get(unit_code, {})


def save_whitelist(unit_code, unit_data):
    """儲存特定營運單位的白名單"""
    whitelist_path = WHITELIST_FILE
    os.makedirs(DATA_DIR, exist_ok=True)

    full_data = {}
    if os.path.exists(whitelist_path):
        try:
            with open(whitelist_path, "r", encoding="utf-8") as f:
                full_data = json.load(f)
                if full_data and not any(k in UNITS for k in full_data.keys()):
                    full_data = {"TTN": full_data}
        except Exception:
            full_data = {}

    full_data[unit_code] = unit_data

    with open(whitelist_path, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)


@st.cache_data(ttl=60)
def get_all_crew_options(unit_code):
    """動態解析指定單位的各大表，建立（員編 - 姓名）快選選單選項"""
    unit_files = UNITS.get(unit_code, UNITS.get("TTN", {}))
    crew_options = []
    seen_uids = set()

    for role_name in ["駕駛", "列車長", "服勤員"]:
        file_path = unit_files.get(role_name, "")
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            try:
                df = safe_read_excel(file_path, header=3)
                for _, row in df.iterrows():
                    uid = str(row.iloc[0]).strip()
                    uname = str(row.iloc[1]).strip()
                    if uid and uid.upper() not in ["NAN", "NONE", "", "員編", "代碼"]:
                        if uid not in seen_uids:
                            seen_uids.add(uid)
                            label = f"{uid} - {uname} ({role_name})"
                            crew_options.append({"label": label, "uid": uid, "name": uname})
            except Exception:
                pass
    return crew_options


def load_all_feedback_tickets():
    """讀取 FEEDBACK_IMG_DIR 中所有的 txt 工單與對應截圖"""
    tickets = []
    if not os.path.exists(FEEDBACK_IMG_DIR):
        return tickets

    for fname in os.listdir(FEEDBACK_IMG_DIR):
        if fname.endswith(".txt"):
            txt_path = os.path.join(FEEDBACK_IMG_DIR, fname)
            base_name = fname[:-4]
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = f.read()

                lines = content.split("\n")
                info = {}
                desc_lines = []
                is_desc = False

                for line in lines:
                    if line.startswith("詳細說明:"):
                        is_desc = True
                        continue
                    if is_desc:
                        desc_lines.append(line)
                    elif ":" in line:
                        k, v = line.split(":", 1)
                        info[k.strip()] = v.strip()

                info["詳細說明"] = "\n".join(desc_lines).strip()
                info["_txt_path"] = txt_path
                info["_base_name"] = base_name

                # 尋找對應的截圖附件
                img_file = None
                for ext in [".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"]:
                    candidate = os.path.join(FEEDBACK_IMG_DIR, f"{base_name}{ext}")
                    if os.path.exists(candidate):
                        img_file = candidate
                        break
                info["_img_path"] = img_file

                tickets.append(info)
            except Exception:
                pass

    tickets = sorted(tickets, key=lambda x: x.get("時間", ""), reverse=True)
    return tickets


def save_feedback_ticket(ticket_info):
    """更新儲存工單 txt 檔案內容"""
    txt_path = ticket_info.get("_txt_path")
    if not txt_path:
        return

    ticket_id = ticket_info.get("處理編號", "")
    status = ticket_info.get("狀態", "待處理")
    category = ticket_info.get("類別", "")
    unit = ticket_info.get("單位", "")
    reporter = ticket_info.get("回報者", "")
    time_str = ticket_info.get("時間", "")
    reply = ticket_info.get("管理員回覆", "尚無回覆")
    desc = ticket_info.get("詳細說明", "")

    content = (
        f"處理編號: {ticket_id}\n"
        f"狀態: {status}\n"
        f"類別: {category}\n"
        f"單位: {unit}\n"
        f"回報者: {reporter}\n"
        f"時間: {time_str}\n"
        f"管理員回覆: {reply}\n"
        f"詳細說明:\n{desc}"
    )

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)


# =========================================================
#  2. 管理員後台主視圖 (Admin Panel)
# =========================================================
def render_admin_panel():
    current_unit = st.session_state.get("current_unit", "TTN")

    # ---------------------------------------------------------
    # 頂部標頭：包含【標題】、【切換營運單位選單】與【返回首頁按鈕】
    # ---------------------------------------------------------
    col_head_title, col_head_unit, col_head_btn = st.columns([2.2, 1.2, 1])

    with col_head_title:
        st.markdown("## ⚙️ 系統管理後台 (Administrator Console)")

    with col_head_unit:
        unit_options = list(UNITS.keys())
        selected_u = st.selectbox(
            "切換營運單位",
            options=unit_options,
            index=unit_options.index(current_unit) if current_unit in unit_options else 0,
            key="admin_header_unit_selector",
        )
        if selected_u != current_unit:
            st.session_state["current_unit"] = selected_u
            st.cache_data.clear()
            log_activity(f"管理員切換單位至：{selected_u}")
            st.rerun()

    with col_head_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button(
            "🏠 返回前台首頁",
            key="btn_top_return_home",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["admin_logged_in"] = False
            st.rerun()

    # 管理員六大分頁
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📂 大表上傳與管理",
        "🛠️ 模組維護模式",
        "👤 白名單與組員權限管理",
        "⚙️ 全域系統參數",
        "📜 系統日誌與備份",
        "📋 工單與問題回報管理",
    ])

    # ---------------------------------------------------------
    # Tab 1: 大表上傳與管理
    # ---------------------------------------------------------
    with tab1:
        st.markdown(f"### 📂 [{current_unit}] 班表大表 Excel 上傳與管理")
        unit_files = UNITS.get(current_unit, UNITS.get("TTN", {}))

        col_u1, col_u2, col_u3 = st.columns(3)
        roles = [
            ("駕駛", "TD", col_u1),
            ("列車長", "TM", col_u2),
            ("服勤員", "TA", col_u3),
        ]

        for role_name, role_code, col in roles:
            with col:
                st.markdown(f"#### {role_name} ({role_code})")
                target_path = unit_files.get(role_name, "")
                st.caption(f"更新時間：{get_file_mtime_str(target_path)}")

                uploaded_file = st.file_uploader(
                    f"上傳 {role_name} 大表 (.xlsx / .xls)",
                    type=["xlsx", "xls"],
                    key=f"upload_{current_unit}_{role_code}",
                )

                if uploaded_file is not None:
                    if st.button(
                        f"確認覆蓋上傳 {role_name} 大表",
                        key=f"btn_save_{role_code}",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            st.success(f"[{current_unit}] {role_name} 班表大表已成功更新！")
                            log_activity(f"管理員上傳 {current_unit} - {role_name} 大表")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"檔案寫入失敗：{e}")

    # ---------------------------------------------------------
    # Tab 2: 模組維護模式
    # ---------------------------------------------------------
    with tab2:
        st.markdown(f"### 🛠️ [{current_unit}] 系統模組維護開關")
        st.info("開啟維護後，一般組員將無法存取該功能，管理員仍可登入後台預覽。")

        modules_def = [
            ("producer", " 個人月班表圖檔生成系統"),
            ("window_filter", " 換班｜選擇換班日期快篩"),
            ("exchange_filter", " 換假｜選擇換假日期快篩"),
        ]

        for m_key, m_title in modules_def:
            c_title, c_sw = st.columns([3, 1])
            is_maint = is_module_maintenance(current_unit, m_key)

            with c_title:
                st.markdown(f"**{m_title}**")
                st.caption(
                    "狀態："
                    + (
                        "<span style='color:#EF4444; font-weight:800;'>🔴 維護中 (已阻擋組員)</span>"
                        if is_maint
                        else "<span style='color:#34D399; font-weight:800;'>🟢 正常開放中</span>"
                    ),
                    unsafe_allow_html=True,
                )

            with c_sw:
                new_state = st.toggle(
                    "開啟維護",
                    value=is_maint,
                    key=f"toggle_maint_{current_unit}_{m_key}",
                )
                if new_state != is_maint:
                    set_module_maintenance(current_unit, m_key, new_state)
                    state_str = "開啟" if new_state else "關閉"
                    log_activity(
                        f"管理員 {state_str} {current_unit} - {m_title} 維護模式"
                    )
                    st.rerun()

    # ---------------------------------------------------------
    # Tab 3: 白名單與組員權限管理
    # ---------------------------------------------------------
    with tab3:
        st.markdown(f"### 👤 白名單與組員權限管理 [{current_unit}]")
        whitelist_data = load_whitelist(current_unit)

        ver_key = f"wl_reset_ver_{current_unit}"
        if ver_key not in st.session_state:
            st.session_state[ver_key] = 0
        current_ver = st.session_state[ver_key]
        table_key = f"wl_table_select_{current_unit}_{current_ver}"

        col_wl_left, col_wl_right = st.columns([1.3, 1])

        wl_rows = []
        if whitelist_data:
            for uid, info in whitelist_data.items():
                if isinstance(info, dict):
                    wl_rows.append({
                        "員編/帳號": uid,
                        "姓名": info.get("name", info.get("姓名", "未設定")),
                        "身份權限": info.get("role", info.get("身份", "VIP")),
                        "備註": info.get("note", info.get("備註", "-")),
                    })
                else:
                    wl_rows.append({
                        "員編/帳號": uid,
                        "姓名": str(info),
                        "身份權限": "VIP",
                        "備註": "-",
                    })

        df_wl = pd.DataFrame(wl_rows) if wl_rows else pd.DataFrame(columns=["員編/帳號", "姓名", "身份權限", "備註"])

        selected_row_data = None
        with col_wl_left:
            st.markdown(f"#### 📋 現有白名單名冊 [{current_unit}]")
            st.caption("💡 **直覺操作**：直接點擊左表任一組員，右側卡片將自動填入資料進行修改或刪除。")

            search_keyword = st.text_input(
                "🔍 搜尋過濾白名單人員",
                placeholder="輸入員編、姓名、身份或備註...",
                key=f"whitelist_search_kw_{current_unit}",
            ).strip()

            filtered_df = df_wl.copy()
            if search_keyword and not filtered_df.empty:
                kw = search_keyword.lower()
                filtered_df = filtered_df[
                    filtered_df["員編/帳號"].astype(str).str.lower().str.contains(kw) |
                    filtered_df["姓名"].astype(str).str.lower().str.contains(kw) |
                    filtered_df["身份權限"].astype(str).str.lower().str.contains(kw) |
                    filtered_df["備註"].astype(str).str.lower().str.contains(kw)
                ]

            if not filtered_df.empty:
                event = st.dataframe(
                    filtered_df,
                    use_container_width=True,
                    height=400,
                    selection_mode="single-row",
                    on_select="rerun",
                    key=table_key,
                )

                selected_rows = event.selection.get("rows", [])
                if selected_rows:
                    selected_idx = selected_rows[0]
                    if 0 <= selected_idx < len(filtered_df):
                        selected_row_data = filtered_df.iloc[selected_idx].to_dict()
            else:
                st.info(f"目前【{current_unit}】尚無匹配的白名單人員紀錄。")

        with col_wl_right:
            st.markdown("#### ⚡ 權限維護與快速編輯")

            col_mode_txt, col_mode_btn = st.columns([2, 1])
            with col_mode_txt:
                if selected_row_data:
                    st.success(f"📌 已點選：**{selected_row_data['員編/帳號']} - {selected_row_data['姓名']}**")
                else:
                    st.info("✨ 當前模式：**新增全新人員**")

            with col_mode_btn:
                if selected_row_data:
                    if st.button("➕ 切換新增", key=f"btn_reset_add_{current_unit}", use_container_width=True):
                        st.session_state[ver_key] += 1
                        st.rerun()

            crew_options = get_all_crew_options(current_unit)
            options_dict = {"-- 或點此快選大表組員帶入 --": {"uid": "", "name": ""}}
            for item in crew_options:
                options_dict[item["label"]] = {"uid": item["uid"], "name": item["name"]}

            def sync_crew_to_inputs():
                sel = st.session_state.get(f"wl_quick_crew_select_{current_unit}", "")
                if sel in options_dict and options_dict[sel]["uid"]:
                    st.session_state[f"input_wl_uid_{current_unit}"] = options_dict[sel]["uid"]
                    st.session_state[f"input_wl_uname_{current_unit}"] = options_dict[sel]["name"]

            st.selectbox(
                "⚡ 大表人員快選帶入",
                options=list(options_dict.keys()),
                key=f"wl_quick_crew_select_{current_unit}",
                on_change=sync_crew_to_inputs,
            )

            default_uid = selected_row_data["員編/帳號"] if selected_row_data else ""
            default_uname = selected_row_data["姓名"] if selected_row_data else ""
            default_role = selected_row_data["身份權限"] if selected_row_data else "VIP_USER (全域通行)"
            default_note = selected_row_data["備註"] if selected_row_data else ""

            edit_uid = st.text_input(
                "員編 / 帳號 ID",
                value=default_uid,
                placeholder="例: A023300",
                key=f"input_wl_uid_{current_unit}",
                disabled=True if selected_row_data else False,
            )

            edit_uname = st.text_input(
                "姓名",
                value=default_uname,
                placeholder="例: 張小明",
                key=f"input_wl_uname_{current_unit}",
            )

            role_options = ["VIP_USER (全域通行)", "ADMIN", "TESTER"]
            role_idx = role_options.index(default_role) if default_role in role_options else 0
            edit_role = st.selectbox(
                "設定使用者權限身份",
                role_options,
                index=role_idx,
                key=f"input_wl_role_{current_unit}",
            )

            edit_note = st.text_input(
                "備註說明",
                value="" if default_note == "-" else default_note,
                placeholder="例: 全域通行權限設定",
                key=f"input_wl_note_{current_unit}",
            )

            st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

            col_b1, col_b2 = st.columns(2)

            with col_b1:
                btn_save_label = "💾 更新權限" if selected_row_data else "➕ 新增人員"
                if st.button(
                    btn_save_label,
                    type="primary",
                    use_container_width=True,
                    key=f"btn_save_wl_{current_unit}",
                ):
                    target_uid = edit_uid.strip()
                    if target_uid:
                        whitelist_data[target_uid] = {
                            "name": edit_uname.strip() or "未命名",
                            "role": edit_role,
                            "note": edit_note.strip(),
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        }
                        save_whitelist(current_unit, whitelist_data)
                        log_activity(
                            f"管理員更新 [{current_unit}] 組員權限：{target_uid} -> {edit_role}"
                        )
                        st.session_state[ver_key] += 1
                        st.success(f"已成功儲存/更新【{current_unit}】權限：{target_uid}")
                        st.rerun()
                    else:
                        st.warning("請填寫員編 / 帳號 ID")

            with col_b2:
                if selected_row_data:
                    if st.button(
                        "🗑️ 刪除此人員",
                        type="secondary",
                        use_container_width=True,
                        key=f"btn_del_wl_{current_unit}",
                    ):
                        target_uid = selected_row_data["員編/帳號"]
                        if target_uid in whitelist_data:
                            del whitelist_data[target_uid]
                            save_whitelist(current_unit, whitelist_data)
                            log_activity(f"管理員移除 [{current_unit}] 組員權限：{target_uid}")
                            st.session_state[ver_key] += 1
                            st.success(f"已成功移除【{current_unit}】權限：{target_uid}")
                            st.rerun()
                else:
                    st.button(
                        "🗑️ 刪除人員",
                        disabled=True,
                        use_container_width=True,
                        help="請點選左側名冊中的人員以進行刪除",
                    )

    # ---------------------------------------------------------
    # Tab 4: 全域系統參數
    # ---------------------------------------------------------
    with tab4:
        st.markdown("### ⚙️ 全域系統參數與授權碼設定")

        if "cfg_toast" in st.session_state:
            t_type, t_msg = st.session_state["cfg_toast"]
            if t_type == "success":
                st.success(t_msg)
            elif t_type == "error":
                st.error(t_msg)
            del st.session_state["cfg_toast"]

        sys_config = load_system_config()

        with st.form(key="global_sys_config_form"):
            col_p1, col_p2 = st.columns(2)

            with col_p1:
                st.markdown("#### 🔑 通行授權碼設定")
                st.caption("💡 若無須修改密碼，保持留空即可。")

                st.markdown("**【一般組員】通行授權碼**")
                new_user_pwd = st.text_input(
                    "設定新 一般組員授權碼",
                    type="password",
                    placeholder="留空則保持原授權碼不變",
                    key="user_pwd_input",
                )
                confirm_user_pwd = st.text_input(
                    "確認新 一般組員授權碼",
                    type="password",
                    placeholder="再次輸入新一般組員授權碼",
                    key="user_pwd_confirm",
                )

                st.markdown("---")

                st.markdown("**【VIP 組員】通行授權碼**")
                new_vip_pwd = st.text_input(
                    "設定新 VIP 授權碼",
                    type="password",
                    placeholder="留空則保持原 VIP 授權碼不變",
                    key="vip_pwd_input",
                )
                confirm_vip_pwd = st.text_input(
                    "確認新 VIP 授權碼",
                    type="password",
                    placeholder="再次輸入新 VIP 授權碼",
                    key="vip_pwd_confirm",
                )

                st.markdown("---")

                st.markdown("**【管理員】解鎖密碼**")
                new_admin_pwd = st.text_input(
                    "設定新 管理員解鎖密碼",
                    type="password",
                    placeholder="留空則保持原密碼不變",
                    key="admin_pwd_input",
                )
                confirm_admin_pwd = st.text_input(
                    "確認新 管理員解鎖密碼",
                    type="password",
                    placeholder="再次輸入新管理員密碼",
                    key="admin_pwd_confirm",
                )

            with col_p2:
                st.markdown("#### 🚨 換假嚴格過濾天數門檻")
                streak_threshold = st.number_input(
                    "連續上班天數警戒門檻（預設 6 天）",
                    min_value=3,
                    max_value=12,
                    value=int(sys_config.get("strict_streak_limit", 6)),
                    step=1,
                )

                st.markdown("---")
                st.markdown("#### 📢 前台公告與橫幅標語設定")
                announce_text = st.text_area(
                    "前台頂部公告文字",
                    value=sys_config.get(
                        "announcement", "目前為內部測試階段｜本頁面可聯繫後台管理者"
                    ),
                    height=100,
                )
                enable_notice = st.checkbox(
                    "顯示 Beta 測試環境告示橫幅",
                    value=sys_config.get("enable_beta_notice", True),
                )

            submit_sys_cfg = st.form_submit_button(
                "💾 儲存全域系統設定", type="primary", use_container_width=True
            )

            if submit_sys_cfg:
                pwd_updates = []
                has_error = False
                error_msgs = []

                if new_user_pwd or confirm_user_pwd:
                    if new_user_pwd != confirm_user_pwd:
                        error_msgs.append("【一般組員授權碼】兩次輸入不一致！")
                        has_error = True
                    elif new_user_pwd.strip():
                        sys_config["user_password"] = new_user_pwd.strip()
                        sys_config["crew_pass_code"] = new_user_pwd.strip()
                        pwd_updates.append("一般組員授權碼")

                if new_vip_pwd or confirm_vip_pwd:
                    if new_vip_pwd != confirm_vip_pwd:
                        error_msgs.append("【VIP 授權碼】兩次輸入不一致！")
                        has_error = True
                    elif new_vip_pwd.strip():
                        sys_config["vip_password"] = new_vip_pwd.strip()
                        sys_config["vip_pass_code"] = new_vip_pwd.strip()
                        pwd_updates.append("VIP 授權碼")

                if new_admin_pwd or confirm_admin_pwd:
                    if new_admin_pwd != confirm_admin_pwd:
                        error_msgs.append("【管理員解鎖密碼】兩次輸入不一致！")
                        has_error = True
                    elif new_admin_pwd.strip():
                        sys_config["admin_password"] = new_admin_pwd.strip()
                        pwd_updates.append("管理員解鎖密碼")

                if has_error:
                    st.session_state["cfg_toast"] = (
                        "error",
                        "❌ " + "；".join(error_msgs),
                    )
                    st.rerun()
                else:
                    sys_config["announcement"] = announce_text.strip()
                    sys_config["strict_streak_limit"] = streak_threshold
                    sys_config["enable_beta_notice"] = enable_notice
                    save_system_config(sys_config)
                    log_activity("管理員更新全域系統設定與通行授權碼")

                    msg_prefix = "與".join(pwd_updates) + "及" if pwd_updates else ""
                    st.session_state["cfg_toast"] = (
                        "success",
                        f"🎉 {msg_prefix}全域系統設定已成功更新並即刻生效！",
                    )
                    st.rerun()

    # ---------------------------------------------------------
    # Tab 5: 系統日誌與備份
    # ---------------------------------------------------------
    with tab5:
        st.markdown("### 📜 系統操作日誌與資料打包備份")

        logs = load_activity_logs()

        col_log_title, col_log_btn = st.columns([3, 1])

        with col_log_title:
            st.markdown(f"#### 👁️ 最近系統操作日誌 (共 {len(logs)} 筆)")

        with col_log_btn:
            st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
            if st.button(
                "🗑️ 清空紀錄",
                key="btn_clear_activity_logs",
                type="secondary",
                use_container_width=True,
            ):
                clear_logs()
                st.success("已成功清空所有系統操作日誌！")
                st.rerun()

        if logs:
            df_logs = pd.DataFrame(logs)
            rename_dict = {
                "timestamp": "紀錄時間",
                "unit": "單位",
                "user_id": "操作者員編",
                "user_name": "姓名",
                "device": "使用裝置",
                "action": "操作動作細節",
            }
            df_logs = df_logs.rename(
                columns={k: v for k, v in rename_dict.items() if k in df_logs.columns}
            )
            display_cols = [
                c
                for c in [
                    "紀錄時間",
                    "單位",
                    "操作者員編",
                    "姓名",
                    "使用裝置",
                    "操作動作細節",
                ]
                if c in df_logs.columns
            ]
            st.dataframe(df_logs[display_cols], use_container_width=True, height=350)
        else:
            st.info("目前尚無任何系統操作日誌紀錄。")

        st.markdown("---")
        st.markdown("#### 📦 一鍵備份全站數據與設定")
        st.caption("點擊下方按鈕可將系統班表大表、設定檔、回報工單與日誌打包為 ZIP 下載備份。")

        zip_buf = create_backup_zip()
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "📥 打包下載全站備份檔 (.zip)",
            data=zip_buf,
            file_name=f"system_backup_{now_str}.zip",
            mime="application/zip",
            type="primary",
            key="btn_download_backup",
        )

    # ---------------------------------------------------------
    # Tab 6: 工單與問題回報管理
    # ---------------------------------------------------------
    with tab6:
        st.markdown("### 📋 工單與問題回報管理")

        all_tickets = load_all_feedback_tickets()

        if not all_tickets:
            st.info("目前尚無任何問題回報工單紀錄。")
        else:
            cnt_pending = sum(1 for t in all_tickets if t.get("狀態") == "待處理")
            cnt_processing = sum(1 for t in all_tickets if t.get("狀態") == "處理中")
            cnt_done = sum(1 for t in all_tickets if t.get("狀態") in ["已完成", "已解決"])

            st.markdown(
                f"""
                <div style="display: flex; gap: 10px; margin-bottom: 16px;">
                    <div style="flex: 1; background: rgba(244, 63, 94, 0.15); border: 1px solid #F43F5E; border-radius: 8px; padding: 10px; text-align: center;">
                        <div style="font-size: 11px; color: #FDA4AF;">待處理工單</div>
                        <div style="font-size: 20px; font-weight: 900; color: #F43F5E;">{cnt_pending} <span style="font-size: 12px;">筆</span></div>
                    </div>
                    <div style="flex: 1; background: rgba(245, 158, 11, 0.15); border: 1px solid #F59E0B; border-radius: 8px; padding: 10px; text-align: center;">
                        <div style="font-size: 11px; color: #FDE68A;">處理中工單</div>
                        <div style="font-size: 20px; font-weight: 900; color: #FBBF24;">{cnt_processing} <span style="font-size: 12px;">筆</span></div>
                    </div>
                    <div style="flex: 1; background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 8px; padding: 10px; text-align: center;">
                        <div style="font-size: 11px; color: #A7F3D0;">已完成工單</div>
                        <div style="font-size: 20px; font-weight: 900; color: #34D399;">{cnt_done} <span style="font-size: 12px;">筆</span></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            filter_status = st.radio(
                "工單狀態篩選",
                ["全部", "待處理", "處理中", "已完成", "已不處理"],
                horizontal=True,
                key="admin_ticket_status_filter",
            )

            filtered_tickets = [
                t for t in all_tickets
                if filter_status == "全部" or t.get("狀態") == filter_status
            ]

            st.caption(f"列表顯示共 {len(filtered_tickets)} 筆工單：")

            for idx, t in enumerate(filtered_tickets):
                ticket_id = t.get("處理編號", "未知單號")
                curr_status = t.get("狀態", "待處理")
                category = t.get("類別", "一般")
                reporter = t.get("回報者", "未知")
                time_str = t.get("時間", "")
                unit = t.get("單位", "")

                status_badge = (
                    "🔴 [待處理]" if curr_status == "待處理"
                    else ("🟡 [處理中]" if curr_status == "處理中"
                          else ("🟢 [已完成]" if curr_status in ["已完成", "已解決"] else "⚪ [已不處理]"))
                )

                expander_title = f"{status_badge} 單號：{ticket_id} ｜ [{unit}] {category} ({reporter} - {time_str})"

                with st.expander(expander_title):
                    st.markdown(f"**提報單位：** `{unit}` ｜ **提報組員：** `{reporter}` ｜ **提報時間：** `{time_str}`")
                    st.markdown(f"**回報類別：** {category}")
                    st.markdown("**詳細內容說明：**")
                    st.info(t.get("詳細說明", "無描述"))

                    img_path = t.get("_img_path")
                    if img_path and os.path.exists(img_path):
                        st.markdown("📷 **附加螢幕截圖：**")
                        if st.button(f"🔍 點此查看/下載截圖附件", key=f"btn_view_img_{ticket_id}_{idx}"):
                            view_feedback_img_modal(img_path, ticket_id, reporter)

                    c1, c2 = st.columns([1, 2])
                    with c1:
                        status_options = ["待處理", "處理中", "已完成", "已不處理"]
                        default_idx = status_options.index(curr_status) if curr_status in status_options else 0
                        new_status = st.selectbox(
                            "變更工單狀態",
                            status_options,
                            index=default_idx,
                            key=f"status_select_{ticket_id}_{idx}",
                        )
                    with c2:
                        new_reply = st.text_input(
                            "處理備註 / 給組員的回覆",
                            value=t.get("管理員回覆", ""),
                            key=f"reply_input_{ticket_id}_{idx}",
                            placeholder="例如：已於 9/6 修正程式...",
                        )

                    cb1, cb2 = st.columns(2)
                    with cb1:
                        if st.button("💾 更新工單狀態與備註", key=f"btn_update_t_{ticket_id}_{idx}", type="primary", use_container_width=True):
                            t["狀態"] = new_status
                            t["管理員回覆"] = new_reply
                            save_feedback_ticket(t)
                            log_activity(f"管理員更新工單 [{ticket_id}] 狀態為：{new_status}")
                            st.success(f"工單 `{ticket_id}` 狀態已成功更新！")
                            st.rerun()

                    with cb2:
                        if st.button("🗑️ 刪除此工單", key=f"btn_del_t_{ticket_id}_{idx}", use_container_width=True):
                            txt_p = t.get("_txt_path")
                            if txt_p and os.path.exists(txt_p):
                                os.remove(txt_p)
                            img_p = t.get("_img_path")
                            if img_p and os.path.exists(img_p):
                                os.remove(img_p)
                            log_activity(f"管理員刪除工單 [{ticket_id}]")
                            st.success(f"已成功刪除工單 `{ticket_id}`！")
                            st.rerun()


# 相容別名宣告
render_admin_home = render_admin_panel
