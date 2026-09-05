from datetime import datetime
import io
import os
import zipfile

from modules.services import (
    load_allowed_users,
    load_system_config,
    save_allowed_users,
    save_system_config,
)
import pandas as pd
import streamlit as st


def render_admin_panel():
  st.markdown("## 🛡️ 後台管理控制台")

  tab1, tab2, tab3 = st.tabs(
      ["👥 白名單帳號管理", "⚙️ 全域系統參數設定", "📜 系統備份與日誌"]
  )

  # =========================================================
  # Tab 1: 白名單帳號管理 (完整互動操作介面)
  # =========================================================
  with tab1:
    st.markdown("### 👥 動態白名單權限管理")
    data = load_allowed_users()

    # 1. 白名單審核總開關
    is_enabled = data.get("enabled", True)
    new_enabled = st.toggle(
        "啟用白名單審核機制",
        value=is_enabled,
        help="若關閉，所有在大表內的組員均可直接登入",
    )
    if new_enabled != is_enabled:
      data["enabled"] = new_enabled
      save_allowed_users(data)
      st.toast("白名單開關狀態已更新！")
      st.rerun()

    st.markdown("---")

    # 2. 新增人員快捷表單
    with st.expander("➕ 新增白名單人員", expanded=False):
      with st.form("add_user_form"):
        col_u1, col_u2 = st.columns(2)
        with col_u1:
          new_emp_id = (
              st.text_input("員編", placeholder="例如: 023300")
              .strip()
              .upper()
          )
          new_name = st.text_input("姓名", placeholder="例如: 張小明").strip()
        with col_u2:
          new_role = st.selectbox("角色權限", ["組員", "VIP"])
          new_status = st.selectbox("帳號狀態", ["啟用", "停用"])

        btn_add_user = st.form_submit_button(
            "新增至白名單", type="primary"
        )

        if btn_add_user:
          if not new_emp_id:
            st.error("請輸入有效員編！")
          else:
            users = data.get("users", [])
            existing = next(
                (
                    u
                    for u in users
                    if u.get("emp_id", "").upper() == new_emp_id
                ),
                None,
            )
            if existing:
              existing["name"] = new_name
              existing["role"] = new_role
              existing["status"] = new_status
              st.success(f"已更新員編 [{new_emp_id}] 之權限與資料！")
            else:
              users.append({
                  "emp_id": new_emp_id,
                  "name": new_name,
                  "role": new_role,
                  "status": new_status,
              })
              st.success(
                  f"已成功新增員編 [{new_emp_id}] 至白名單！"
              )

            data["users"] = users
            save_allowed_users(data)
            st.rerun()

    # 3. 線上白名單列表編輯器 (可直接在表格內修改或刪除)
    st.markdown("#### 📋 現有白名單人員列表")
    users_list = data.get("users", [])

    if not users_list:
      st.info("目前白名單內無任何人員資料。")
    else:
      df_users = pd.DataFrame(users_list)
      for col in ["emp_id", "name", "role", "status"]:
        if col not in df_users.columns:
          df_users[col] = ""

      edited_df = st.data_editor(
          df_users,
          column_config={
              "emp_id": st.column_config.TextColumn("員編", required=True),
              "name": st.column_config.TextColumn("姓名"),
              "role": st.column_config.SelectboxColumn(
                  "角色權限", options=["組員", "VIP"], required=True
              ),
              "status": st.column_config.SelectboxColumn(
                  "帳號狀態", options=["啟用", "停用"], required=True
              ),
          },
          num_rows="dynamic",
          use_container_width=True,
          key="data_editor_whitelist",
      )

      if st.button("💾 儲存白名單變更", type="primary"):
        updated_users = edited_df.to_dict(orient="records")
        cleaned_users = []
        for u in updated_users:
          emp = str(u.get("emp_id", "")).strip().upper()
          if emp and emp != "NAN":
            cleaned_users.append({
                "emp_id": emp,
                "name": str(u.get("name", "")).strip(),
                "role": str(u.get("role", "組員")).strip(),
                "status": str(u.get("status", "啟用")).strip(),
            })
        data["users"] = cleaned_users
        save_allowed_users(data)
        st.success("✅ 白名單資料已成功更新並儲存！")
        st.rerun()

  # =========================================================
  # Tab 2: 全域系統參數設定
  # =========================================================
  with tab2:
    st.markdown("### ⚙️ 系統核心通行碼與圖表顯示參數")
    st.info(
        "💡"
        " 此處修改的設定會即時生效於前端登入頁與班表繪製引擎，免改 Code！"
    )

    curr_cfg = load_system_config()

    with st.form("sys_config_form"):
      col_c1, col_c2 = st.columns(2)

      with col_c1:
        vip_code = st.text_input(
            "VIP 快速通行碼",
            value=curr_cfg.get("vip_pass_code", "0900"),
            help="測試員與 VIP 免比對大表使用的權限金鑰",
        )
        crew_code = st.text_input(
            "一般組員授權碼",
            value=curr_cfg.get("crew_pass_code", "0096"),
            help="一般同仁登入驗證使用的授權碼",
        )
        default_emp = st.text_input(
            "預設登入員編",
            value=curr_cfg.get("default_emp_id", "A"),
            help="前端登入頁面開啟時預設帶入的員編內容",
        )

      with col_c2:
        options_list = ["--", "無", "休", "OFF", "留白（不顯示文字）"]
        curr_val = curr_cfg.get("empty_shift_label", "--")
        if curr_val == "":
          curr_val = "留白（不顯示文字）"
        idx = (
            options_list.index(curr_val) if curr_val in options_list else 0
        )

        empty_label = st.selectbox(
            "班表無勤務/空值顯示方式",
            options=options_list,
            index=idx,
            help="當班表該日沒有班表號碼時，圖表儲存格內要印出的符號",
        )

        enable_wl = st.toggle(
            "強制啟用動態白名單審核",
            value=curr_cfg.get("enable_whitelist", True),
            help="關閉後一般同仁只要在大表內即可用組員授權碼登入",
        )

      btn_save_cfg = st.form_submit_button("💾 儲存全域設定", type="primary")

      if btn_save_cfg:
        new_cfg = {
            "vip_pass_code": vip_code.strip(),
            "crew_pass_code": crew_code.strip(),
            "empty_shift_label": (
                "" if empty_label == "留白（不顯示文字）" else empty_label
            ),
            "default_emp_id": default_emp.strip(),
            "enable_whitelist": enable_wl,
        }
        if save_system_config(new_cfg):
          st.success("✅ 全域系統參數已成功儲存並即時生效！")
          st.rerun()
        else:
          st.error("❌ 儲存設定時發生錯誤，請檢查檔案權限。")

  # =========================================================
  # Tab 3: 系統備份與日誌
  # =========================================================
  with tab3:
    st.markdown("### 📦 一鍵備份系統數據與設定檔")

    def make_backup_zip():
      buf = io.BytesIO()
      with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ["allowed_users.json", "system_config.json", "config.py"]:
          if os.path.exists(fname):
            zf.write(fname)
      buf.seek(0)
      return buf

    st.download_button(
        "📥 一鍵打包下載全站設定與白名單備份 (ZIP)",
        data=make_backup_zip(),
        file_name=(
            f"TTN_Engine_Backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        ),
        mime="application/zip",
    )
