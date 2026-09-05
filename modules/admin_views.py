import hashlib
import os
import time
from datetime import datetime

from config import FEEDBACK_IMG_DIR, LOG_FILE, UNITS
from modules.components import view_feedback_img_modal
from modules.services import load_allowed_users, save_allowed_users
from modules.utils import (
    is_module_maintenance,
    log_activity,
    safe_read_excel,
    set_module_maintenance,
)
import pandas as pd
import streamlit as st


def render_admin_panel():
  st.markdown(
      """
    <div class="section-header-box">
        <div class="section-title">管理員專用：Database 智慧控制台</div>
        <div class="section-subtitle">Advanced Crew Duty Management & Data Maintenance Center</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

  col_unit_sel, col_btn_home, col_btn_logout = st.columns([2, 1, 1])
  with col_unit_sel:
    admin_target_unit = st.selectbox(
        "維護目標單位",
        ["TTN", "TTC", "TTS"],
        key="admin_target_unit_sel",
        label_visibility="collapsed",
    )
    current_unit_files = UNITS[admin_target_unit]
  with col_btn_home:
    if st.button("返回一般系統首頁", key="admin_back_to_home_btn"):
      st.session_state["current_unit"] = admin_target_unit
      st.session_state["nav_mode"] = "home"
      st.rerun()
  with col_btn_logout:
    if st.button("登出管理員身分", key="admin_logout_btn_top"):
      log_activity("管理員登出後台")
      st.session_state["admin_logged_in"] = False
      st.session_state["nav_mode"] = "home"
      st.rerun()

  tab_status, tab_users, tab_gallery, tab_logs = st.tabs([
      "數據與檔案維護",
      "使用者權限與全系統開放",
      "客服工單管理中心 (Table View)",
      "系統操作日誌",
  ])

  # ---------------------------------------------------------
  # TAB 1: 數據與檔案維護
  # ---------------------------------------------------------
  with tab_status:
    st.subheader(f"【{admin_target_unit}】伺服器狀態 & Dashboard 數據")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
      td_ok = os.path.exists(current_unit_files["駕駛"])
      st.metric(
          "駕駛大表 (TD)",
          "已就緒" if td_ok else "缺檔案",
          delta="正常" if td_ok else "缺失",
      )
    with m2:
      tm_ok = os.path.exists(current_unit_files["列車長"])
      st.metric(
          "列車長大表 (TM)",
          "已就緒" if tm_ok else "缺檔案",
          delta="正常" if tm_ok else "缺失",
      )
    with m3:
      ta_ok = os.path.exists(current_unit_files["服勤員"])
      st.metric(
          "服勤員大表 (TA)",
          "已就緒" if ta_ok else "缺檔案",
          delta="正常" if ta_ok else "缺失",
      )
    with m4:
      log_cnt = 0
      if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
          log_cnt = len(f.readlines())
      st.metric("系統日誌累計", f"{log_cnt} 筆", delta="Activity")

    st.markdown("---")
    st.subheader(
        f"三大系統模組維護開關控制（當前控制單位：{admin_target_unit}）"
    )

    is_prod_maint = is_module_maintenance(admin_target_unit, "producer")
    is_win_maint = is_module_maintenance(admin_target_unit, "window_filter")
    is_ex_maint = is_module_maintenance(admin_target_unit, "exchange_filter")

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
      new_prod = st.checkbox(
          "【個人月班表圖檔】維護中",
          value=is_prod_maint,
          key=f"cb_{admin_target_unit}_producer",
      )
      if new_prod != is_prod_maint:
        set_module_maintenance(admin_target_unit, "producer", new_prod)
        log_activity(
            f"設定 [{admin_target_unit}] 個人月班表維護開關:"
            f" {'開啟維護' if new_prod else '解除維護'}"
        )
        st.rerun()

    with col_m2:
      new_win = st.checkbox(
          "【換班選擇日期】維護中",
          value=is_win_maint,
          key=f"cb_{admin_target_unit}_window_filter",
      )
      if new_win != is_win_maint:
        set_module_maintenance(admin_target_unit, "window_filter", new_win)
        log_activity(
            f"設定 [{admin_target_unit}] 換班選擇日期維護開關:"
            f" {'開啟維護' if new_win else '解除維護'}"
        )
        st.rerun()

    with col_m3:
      new_ex = st.checkbox(
          "【換假選擇日期】維護中",
          value=is_ex_maint,
          key=f"cb_{admin_target_unit}_exchange_filter",
      )
      if new_ex != is_ex_maint:
        set_module_maintenance(admin_target_unit, "exchange_filter", new_ex)
        log_activity(
            f"設定 [{admin_target_unit}] 換假選擇日期維護開關:"
            f" {'開啟維護' if new_ex else '解除維護'}"
        )
        st.rerun()

    st.markdown("---")
    st.subheader(f"【{admin_target_unit}】班表維護控制台")
    selected_role = st.selectbox(
        "選擇目前要維護的職位類別",
        ["駕駛", "列車長", "服勤員"],
        index=2,
        key="admin_role_select_box",
    )
    target_path = current_unit_files[selected_role]

    uploaded_file_update = st.file_uploader(
        f"上傳【{admin_target_unit} - {selected_role}】最新大表 (.xlsx)",
        type=["xlsx", "xls", "csv"],
        key=f"up_{admin_target_unit}_{selected_role}",
    )
    if uploaded_file_update is not None:
      file_bytes = uploaded_file_update.getvalue()
      current_hash = hashlib.md5(file_bytes).hexdigest()
      hash_key = f"hash_{admin_target_unit}_{selected_role}"

      if st.session_state.get(hash_key) != current_hash:
        try:
          with open(target_path, "wb") as f:
            f.write(file_bytes)
          st.session_state[hash_key] = current_hash
          log_activity(f"上傳【{admin_target_unit} - {selected_role}】最新大表")
          st.success("檔案上傳成功！")
          time.sleep(0.5)
          st.rerun()
        except Exception as e:
          st.error(f"寫入失敗: {e}")

  # ---------------------------------------------------------
  # TAB 2: 使用者權限與全系統開放控制
  # ---------------------------------------------------------
  with tab_users:
    st.subheader("使用者登入門檻與全系統開放模式控制")

    data = load_allowed_users()
    users_list = data.get("users", [])
    is_enabled = data.get("enabled", True)

    # 1. 全系統開放 / 白名單模式 Toggle 主控區
    st.markdown("##### ⚙️ 存取驗證開關切換")
    col_sw1, col_sw2 = st.columns([3, 1])
    with col_sw1:
      toggle_state = st.toggle(
          "啟用全系統使用者白名單存取驗證",
          value=is_enabled,
          key="admin_user_whitelist_toggle",
      )
      if toggle_state != is_enabled:
        data["enabled"] = toggle_state
        save_allowed_users(data)
        log_activity(
            "設定白名單驗證開關:"
            f" {'開啟 (白名單管控)' if toggle_state else '關閉 (全系統開放)'}"
        )
        st.success(
            "已切換為："
            f"{'【白名單管控模式】' if toggle_state else '【全系統開放模式】'}！"
        )
        time.sleep(0.3)
        st.rerun()

    # 系統動態模式狀態 Banner
    if not is_enabled:
      st.success(
          "🌐 **當前模式：全系統開放中（白名單驗證已關閉）**\n\n"
          "所有在排班大表內的組員只要輸入正確員編/姓名與通用授權碼即可自由登入使用系統。"
      )
    else:
      st.warning(
          "🔒 **當前模式：白名單嚴格管控中（白名單驗證已開啟）**\n\n"
          "僅下方列表中「啟用」狀態的人員可登入系統，非名單內人員將無法通過登入驗證。"
      )

    st.markdown("---")

    sub_tab1, sub_tab2 = st.tabs(
        ["📋 白名單人員總覽 (高效分頁管理)", "⚡ 關鍵字搜尋新增"]
    )

    # 子頁籤 1：白名單總覽（支援線上權限調整、分頁與滾動視窗）
    with sub_tab1:
      if users_list:
        col_sch, col_page = st.columns([3, 2])
        with col_sch:
          search_kw = (
              st.text_input(
                  "🔍 關鍵字過濾員編或姓名",
                  "",
                  key="admin_user_search_kw",
              )
              .strip()
              .upper()
          )

        filtered_users = users_list
        if search_kw:
          filtered_users = [
              u
              for u in users_list
              if search_kw in str(u.get("emp_id", "")).upper()
              or search_kw in str(u.get("name", "")).upper()
          ]

        total_count = len(filtered_users)
        page_size = 10
        total_pages = max(1, (total_count + page_size - 1) // page_size)

        with col_page:
          current_page = st.number_input(
              f"頁碼 (共 {total_count} 筆 / {total_pages} 頁)",
              min_value=1,
              max_value=total_pages,
              value=1,
              step=1,
              key="admin_user_page_input",
          )

        start_idx = (current_page - 1) * page_size
        page_users = filtered_users[start_idx : start_idx + page_size]

        if page_users:
          # 使用固定高度滾動容器，保護頁面不被拉長
          with st.container(height=460):
            # 表頭
            h1, h2, h3, h4, h5 = st.columns([2.2, 2.2, 2.5, 1.8, 3])
            h1.markdown("**員工編號**")
            h2.markdown("**姓名**")
            h3.markdown("**職務 / 權限類別**")
            h4.markdown("**帳號狀態**")
            h5.markdown("**一鍵處置操作**")
            st.markdown(
                "<hr style='margin: 4px 0 10px 0; border-color: rgba(56, 189,"
                " 248, 0.3);'>",
                unsafe_allow_html=True,
            )

            # 逐列印出當頁人員與操作按鈕
            for idx, u in enumerate(page_users):
              u_id = u.get("emp_id", "")
              u_name = u.get("name", "")
              u_role = u.get("role", "服勤員")
              u_status = u.get("status", "啟用")

              c1, c2, c3, c4, c5 = st.columns([2.2, 2.2, 2.5, 1.8, 3])
              with c1:
                st.markdown(
                    "<span style='font-family:monospace; font-weight:700;"
                    f" color:#38BDF8;'>{u_id}</span>",
                    unsafe_allow_html=True,
                )
              with c2:
                st.markdown(
                    "<span style='font-family:monospace; font-weight:700;"
                    f" color:#F8FAFC;'>{u_name}</span>",
                    unsafe_allow_html=True,
                )

              # 【新增功能】可動態調整權限/職務的下拉選單 (支援 VIP)
              with c3:
                role_options = ["服勤員", "列車長", "駕駛", "管理員", "VIP"]
                current_role_idx = (
                    role_options.index(u_role) if u_role in role_options else 0
                )
                new_role = st.selectbox(
                    "調整權限",
                    options=role_options,
                    index=current_role_idx,
                    key=f"sel_role_{u_id}_{idx}",
                    label_visibility="collapsed",
                )

                if new_role != u_role:
                  target_obj = next(
                      (item for item in data["users"] if item["emp_id"] == u_id),
                      None,
                  )
                  if target_obj:
                    target_obj["role"] = new_role
                    save_allowed_users(data)
                    log_activity(
                        f"管理員變更人員 [{u_id} {u_name}] 權限/職務:"
                        f" {u_role} -> {new_role}"
                    )
                    st.toast(
                        f"✅ 已成功將 {u_name} ({u_id}) 權限調整為：{new_role}"
                    )
                    time.sleep(0.3)
                    st.rerun()

              with c4:
                st_color = "#34D399" if u_status == "啟用" else "#F87171"
                st.markdown(
                    f"<span style='font-weight:800; color:{st_color};'>【{u_status}】</span>",
                    unsafe_allow_html=True,
                )
              with c5:
                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                  toggle_label = "🔴 停用" if u_status == "啟用" else "🟢 啟用"
                  if st.button(
                      toggle_label,
                      key=f"btn_st_{u_id}_{idx}",
                      use_container_width=True,
                  ):
                    target_obj = next(
                        (
                            item
                            for item in data["users"]
                            if item["emp_id"] == u_id
                        ),
                        None,
                    )
                    if target_obj:
                      target_obj["status"] = (
                          "停用" if u_status == "啟用" else "啟用"
                      )
                      save_allowed_users(data)
                      log_activity(
                          "管理員切換白名單人員狀態:"
                          f" {u_id} -> {target_obj['status']}"
                      )
                      st.rerun()
                with btn_c2:
                  if st.button(
                      "❌ 刪除", key=f"btn_del_{u_id}_{idx}", use_container_width=True
                  ):
                    data["users"] = [
                        item for item in data["users"] if item["emp_id"] != u_id
                    ]
                    save_allowed_users(data)
                    log_activity(f"管理員刪除白名單人員: {u_id} ({u_name})")
                    st.rerun()

              st.markdown(
                  "<hr style='margin: 4px 0; border-color: rgba(255, 255, 255,"
                  " 0.05);'>",
                  unsafe_allow_html=True,
              )
        else:
          st.info("查無符合過濾條件的人員。")
      else:
        st.info("目前白名單內無任何使用者資料。")

    # 子頁籤 2：關鍵字即時動態搜尋 + 下拉選單自動比對
    with sub_tab2:
      st.markdown(
          "##### 🔍 關鍵字即時搜尋 (輸入姓名關鍵字如 `波莉` 或員編 `023300`)"
      )

      search_input_kw = st.text_input(
          "輸入關鍵字 (例如: 波莉 / 023300)",
          value="",
          key="admin_live_search_kw_inp",
      ).strip()

      if search_input_kw:
        kw_upper = search_input_kw.upper()
        matched_crew = []

        # 從各大表中即時比對姓名或員編
        for r_name in ["服勤員", "列車長", "駕駛"]:
          p_path = current_unit_files.get(r_name, "")
          if os.path.exists(p_path):
            try:
              df_c = safe_read_excel(p_path, header=3)
              for _, row_c in df_c.iterrows():
                c_id = str(row_c.iloc[0]).strip().upper()
                c_name = str(row_c.iloc[1]).strip()
                if c_id and c_id != "NAN" and c_name and c_name != "NAN":
                  if kw_upper in c_id or kw_upper in c_name.upper():
                    is_added = any(
                        u["emp_id"] == c_id for u in data["users"]
                    )
                    matched_crew.append({
                        "emp_id": c_id,
                        "name": c_name,
                        "role": r_name,
                        "is_added": is_added,
                        "label": (
                            f"{c_name} ({c_id}) ｜ 職務: {r_name}"
                            + (" ⚠️ [已在白名單]" if is_added else "")
                        ),
                    })
            except Exception:
              pass

        if matched_crew:
          st.markdown(
              f"**👇 自動跳出符合「{search_input_kw}」的人員選單（共"
              f" {len(matched_crew)} 筆）：**"
          )
          selected_cand_label = st.selectbox(
              "請選擇要新增的人員",
              options=[c["label"] for c in matched_crew],
              key="admin_matched_crew_selectbox",
          )
          cand_obj = next(
              (c for c in matched_crew if c["label"] == selected_cand_label),
              None,
          )

          if cand_obj:
            if cand_obj["is_added"]:
              st.warning(
                  f"⚠️ **{cand_obj['name']} ({cand_obj['emp_id']})**"
                  " 已經在白名單中了，無需重複新增！"
              )
            else:
              st.success(
                  f"已選取：**{cand_obj['name']}** ｜ 員編：`{cand_obj['emp_id']}`"
                  f" ｜ 職務：`{cand_obj['role']}`"
              )
              if st.button(
                  "⚡ 一鍵新增至白名單",
                  key="btn_confirm_add_matched",
                  use_container_width=True,
              ):
                data["users"].append({
                    "emp_id": cand_obj["emp_id"],
                    "name": cand_obj["name"],
                    "role": cand_obj["role"],
                    "status": "啟用",
                })
                save_allowed_users(data)
                log_activity(
                    f"新增白名單人員: {cand_obj['name']} ({cand_obj['emp_id']})"
                )
                st.success(
                    f"已成功新增：{cand_obj['name']} ({cand_obj['emp_id']})！"
                )
                time.sleep(0.3)
                st.rerun()
        else:
          st.info(f"在大表中找不到與「{search_input_kw}」符合的人員紀錄。")

      st.markdown("---")
      st.markdown("##### ✍️ 完全手動新增 (若排班大表中無此人時使用)")
      with st.form("add_custom_user_form"):
        custom_id = (
            st.text_input(
                "員工編號 (例: VIP001 或 023300)",
                value="VIP",
                key="custom_user_id",
            )
            .strip()
            .upper()
        )
        custom_name = st.text_input(
            "姓名 (例: 波莉)", key="custom_user_name"
        ).strip()
        # 【修改處】將 VIP 納入可選擇的職務類別中
        custom_role = st.selectbox(
            "職務類別",
            ["VIP", "管理員", "服勤員", "列車長", "駕駛"],
            key="custom_user_role",
        )
        custom_sub = st.form_submit_button(
            "手動新增至白名單", use_container_width=True
        )

        if custom_sub:
          if not custom_id or not custom_name:
            st.error("請完整填寫員編與姓名！")
          elif any(u["emp_id"] == custom_id for u in data["users"]):
            st.warning(f"員編「{custom_id}」已存在於白名單中！")
          else:
            data["users"].append({
                "emp_id": custom_id,
                "name": custom_name,
                "role": custom_role,
                "status": "啟用",
            })
            save_allowed_users(data)
            log_activity(f"手動新增白名單人員: {custom_name} ({custom_id})")
            st.success(f"已成功新增：{custom_name} ({custom_id})！")
            time.sleep(0.3)
            st.rerun()

  # ---------------------------------------------------------
  # TAB 3: 客服工單管理中心
  # ---------------------------------------------------------
  with tab_gallery:
    st.subheader("使用者問題與建議／客服工單管理中心")

    all_fb_records = []
    if os.path.exists(FEEDBACK_IMG_DIR):
      for fname in os.listdir(FEEDBACK_IMG_DIR):
        if fname.endswith(".txt"):
          txt_path = os.path.join(FEEDBACK_IMG_DIR, fname)
          stem = os.path.splitext(fname)[0]

          img_path = None
          for ext in [".png", ".jpg", ".jpeg"]:
            test_img = os.path.join(FEEDBACK_IMG_DIR, f"{stem}{ext}")
            if os.path.exists(test_img):
              img_path = test_img
              break

          rec = {
              "stem": stem,
              "txt_path": txt_path,
              "img_path": img_path,
              "單號": stem,
              "狀態": "待處理",
              "類別": "其他",
              "單位": "全域",
              "回報者": "未知",
              "時間": "未知",
              "管理員回覆": "尚無回覆",
              "詳細說明": "無說明內容",
          }

          try:
            with open(txt_path, "r", encoding="utf-8") as ft:
              lines = ft.readlines()
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
                  k_clean = k.strip()
                  v_clean = v.strip()
                  if k_clean in ["處理編號", "單號"]:
                    rec["單號"] = v_clean
                  elif k_clean == "狀態":
                    rec["狀態"] = v_clean
                  elif k_clean == "類別":
                    rec["類別"] = v_clean
                  elif k_clean == "單位":
                    rec["單位"] = v_clean
                  elif k_clean in ["回報者", "回報者員編"]:
                    rec["回報者"] = v_clean
                  elif k_clean == "時間":
                    rec["時間"] = v_clean
                  elif k_clean in ["管理員回覆", "回覆"]:
                    rec["管理員回覆"] = v_clean
              if desc_lines:
                rec["詳細說明"] = "".join(desc_lines).strip()
          except Exception as e:
            rec["詳細說明"] = f"解析失敗: {e}"

          all_fb_records.append(rec)

    all_fb_records = sorted(
        all_fb_records, key=lambda x: x["stem"], reverse=True
    )

    cnt_total = len(all_fb_records)
    cnt_pending = sum(1 for r in all_fb_records if r["狀態"] == "待處理")
    cnt_processing = sum(1 for r in all_fb_records if r["狀態"] == "處理中")
    cnt_done = sum(1 for r in all_fb_records if r["狀態"] == "已完成")

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("總工單數", f"{cnt_total} 筆")
    kpi2.metric(
        "待處理",
        f"{cnt_pending} 筆",
        delta="-需處理" if cnt_pending > 0 else "清空",
        delta_color="inverse",
    )
    kpi3.metric("處理中", f"{cnt_processing} 筆")
    kpi4.metric("已完成", f"{cnt_done} 筆")

    st.markdown("---")

    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
      filter_status = st.selectbox(
          "狀態過濾",
          ["全部", "待處理", "處理中", "已完成", "已不處理"],
          index=0,
          key="admin_fb_filter_status",
      )
    with f_col2:
      filter_unit = st.selectbox(
          "單位過濾",
          ["全部", "TTN", "TTC", "TTS"],
          index=0,
          key="admin_fb_filter_unit",
      )
    with f_col3:
      filter_category = st.selectbox(
          "類別過濾",
          [
              "全部",
              "Bug 問題回報",
              "功能改進建議",
              "班表資料不對",
              "其他",
          ],
          index=0,
          key="admin_fb_filter_cat",
      )

    filtered_records = []
    for r in all_fb_records:
      if filter_status != "全部" and r["狀態"] != filter_status:
        continue
      if filter_unit != "全部" and r["單位"] != filter_unit:
        continue
      if filter_category != "全部" and r["類別"] != filter_category:
        continue
      filtered_records.append(r)

    st.caption(f"共顯示 {len(filtered_records)} 筆紀錄")

    if filtered_records:
      t_h1, t_h2, t_h3, t_h4, t_h5, t_h6 = st.columns(
          [2.2, 1.8, 1.3, 3.2, 1.2, 2.3]
      )
      t_h1.markdown("**工單編號 / 時間**")
      t_h2.markdown("**提報人員**")
      t_h3.markdown("**類別**")
      t_h4.markdown("**詳細說明**")
      t_h5.markdown("**狀態**")
      t_h6.markdown("**管理與截圖操作**")
      st.markdown(
          "<hr style='margin: 4px 0 10px 0; border-color: rgba(56, 189, 248,"
          " 0.3);'>",
          unsafe_allow_html=True,
      )

      for idx, rec in enumerate(filtered_records):
        status_color_map = {
            "待處理": "#F59E0B",
            "處理中": "#38BDF8",
            "已完成": "#34D399",
            "已不處理": "#94A3B8",
        }
        st_color = status_color_map.get(rec["狀態"], "#F59E0B")

        c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1.8, 1.3, 3.2, 1.2, 2.3])

        with c1:
          st.markdown(
              "<span style='font-family:monospace; font-weight:800;"
              f" color:#38BDF8; font-size:12px;'>{rec['單號']}</span>",
              unsafe_allow_html=True,
          )
          st.markdown(
              "<span style='font-family:monospace; color:#94A3B8;"
              f" font-size:10px;'>{rec['時間']}</span>",
              unsafe_allow_html=True,
          )

        with c2:
          st.markdown(
              "<span style='font-family:monospace; color:#F8FAFC;"
              " font-weight:700;"
              f" font-size:11.5px;'>[{rec['單位']}]</span>",
              unsafe_allow_html=True,
          )
          st.markdown(
              "<span style='font-family:monospace; color:#CBD5E1;"
              f" font-size:11px;'>{rec['回報者']}</span>",
              unsafe_allow_html=True,
          )

        with c3:
          st.markdown(
              "<span style='font-family:monospace; color:#E2E8F0;"
              f" font-size:11.5px;'>{rec['類別']}</span>",
              unsafe_allow_html=True,
          )

        with c4:
          st.markdown(
              "<span style='font-family:monospace; color:#F8FAFC;"
              " font-size:11.5px;"
              f" white-space:pre-wrap;'>{rec['詳細說明']}</span>",
              unsafe_allow_html=True,
          )

        with c5:
          st.markdown(
              "<span style='font-family:monospace; font-weight:800;"
              f" color:{st_color}; font-size:12px;'>【{rec['狀態']}】</span>",
              unsafe_allow_html=True,
          )

        with c6:
          act_c1, act_c2 = st.columns(2)
          with act_c1:
            if rec["img_path"]:
              if st.button(
                  "檢視", key=f"tbl_img_{idx}", use_container_width=True
              ):
                view_feedback_img_modal(
                    rec["img_path"],
                    rec["單號"],
                    f"[{rec['單位']}] {rec['回報者']}",
                )
            else:
              st.button(
                  "無附件",
                  key=f"tbl_no_img_{idx}",
                  disabled=True,
                  use_container_width=True,
              )
          with act_c2:
            with st.popover("處置", use_container_width=True):
              m_status_idx = (
                  ["待處理", "處理中", "已完成", "已不處理"].index(
                      rec["狀態"]
                  )
                  if rec["狀態"] in ["待處理", "處理中", "已完成", "已不處理"]
                  else 0
              )
              new_st = st.selectbox(
                  "變更狀態",
                  ["待處理", "處理中", "已完成", "已不處理"],
                  index=m_status_idx,
                  key=f"pop_st_{idx}",
              )
              new_reply = st.text_input(
                  "留言回覆",
                  value=""
                  if rec["管理員回覆"] == "尚無回覆"
                  else rec["管理員回覆"],
                  placeholder="例如: 已發布更新修正",
                  key=f"pop_rp_{idx}",
              )

              col_p1, col_p2 = st.columns(2)
              with col_p1:
                if st.button(
                    "儲存", key=f"pop_save_{idx}", use_container_width=True
                ):
                  try:
                    lines_to_write = []
                    if os.path.exists(rec["txt_path"]):
                      with open(rec["txt_path"], "r", encoding="utf-8") as ft:
                        lines_to_write = ft.readlines()

                    with open(rec["txt_path"], "w", encoding="utf-8") as ft:
                      has_st, has_rp = False, False
                      for line in lines_to_write:
                        if line.startswith("狀態:"):
                          ft.write(f"狀態: {new_st}\n")
                          has_st = True
                        elif line.startswith("管理員回覆:"):
                          ft.write(
                              "管理員回覆:"
                              f" {new_reply.strip() if new_reply.strip() else '尚無回覆'}\n"
                          )
                          has_rp = True
                        else:
                          ft.write(line)
                      if not has_st:
                        ft.write(f"狀態: {new_st}\n")
                      if not has_rp:
                        ft.write(
                            "管理員回覆:"
                            f" {new_reply.strip() if new_reply.strip() else '尚無回覆'}\n"
                        )

                    log_activity(
                        f"管理員處置工單 [{rec['單號']}] -> 狀態:{new_st}"
                    )
                    st.success("完成！")
                    time.sleep(0.3)
                    st.rerun()
                  except Exception as e:
                    st.error(f"失敗: {e}")
              with col_p2:
                if st.button(
                    "刪除", key=f"pop_del_{idx}", use_container_width=True
                ):
                  try:
                    if os.path.exists(rec["txt_path"]):
                      os.remove(rec["txt_path"])
                    if rec["img_path"] and os.path.exists(rec["img_path"]):
                      os.remove(rec["img_path"])
                    log_activity(f"管理員刪除工單: {rec['單號']}")
                    st.rerun()
                  except Exception as e:
                    st.error(f"失敗: {e}")

        st.markdown(
            "<hr style='margin: 6px 0; border-color: rgba(255, 255, 255,"
            " 0.05);'>",
            unsafe_allow_html=True,
        )
    else:
      st.info("目前無符合條件的回報紀錄。")

  # ---------------------------------------------------------
  # TAB 4: 系統操作日誌
  # ---------------------------------------------------------
  with tab_logs:
    st.subheader("系統操作活動紀錄日誌 (Activity Log)")

    col_log1, col_log2, col_log3 = st.columns([2, 1, 1])
    with col_log1:
      log_filter_keyword = st.text_input(
          "搜尋關鍵字",
          placeholder="輸入員編、換班或問題回報...",
          key="admin_log_search_input",
      )
    with col_log2:
      st.markdown(
          "<div style='height: 28px;'></div>", unsafe_allow_html=True
      )
      if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
          log_raw_data = f.read()
        st.download_button(
            label="📥 下載日誌 CSV",
            data=log_raw_data,
            file_name=(
                f"Activity_Log_{datetime.now().strftime('%Y%m%d')}.csv"
            ),
            mime="text/csv",
            key="admin_download_log_btn",
            use_container_width=True,
        )
    with col_log3:
      st.markdown(
          "<div style='height: 28px;'></div>", unsafe_allow_html=True
      )
      if st.button(
          "清空歷史日誌",
          key="admin_clear_log_btn",
          use_container_width=True,
      ):
        if os.path.exists(LOG_FILE):
          os.remove(LOG_FILE)
        st.rerun()

    if os.path.exists(LOG_FILE):
      with open(LOG_FILE, "r", encoding="utf-8") as f:
        logs = f.readlines()
      parsed_logs = []
      for line in reversed(logs[-100:]):  # 顯示最近 100 筆
        if (
            log_filter_keyword
            and log_filter_keyword.lower() not in line.lower()
        ):
          continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 5:
          parsed_logs.append({
              "時間": parts[0],
              "單位": parts[1].replace("單位: ", ""),
              "操作者": parts[2].replace("操作者員編: ", ""),
              "裝置": parts[3].replace("裝置: ", ""),
              "動作": " | ".join(parts[4:]).replace("動作: ", ""),
          })

      if parsed_logs:
        df_parsed = pd.DataFrame(parsed_logs)

        with st.expander("📊 查看熱門動作統計圖表", expanded=False):
          action_counts = df_parsed["動作"].value_counts().head(10)
          st.bar_chart(action_counts)

        st.dataframe(
            df_parsed, use_container_width=True, hide_index=True
        )
      else:
        st.info("查無符合過濾條件的日誌")
    else:
      st.info("尚無任何紀錄")
