from datetime import datetime
import io
import json
import os
import zipfile

from config import LOG_FILE
from modules.components import render_zoomable_image
from modules.drawing import render_schedule_figure
from modules.services import (
    get_employee_name,
    load_allowed_users,
    load_system_config,
    process_file_data,
    save_allowed_users,
    save_system_config,
)
from modules.utils import (
    get_file_mtime_str,
    load_activity_logs,
    log_activity,
    safe_read_excel,
)
import pandas as pd
import streamlit as st

MAINT_FILE = "maintenance.json"


# --- 工具函式：讀取大表中所有同仁清單 ---
def get_all_excel_crew(current_unit):
  data_dir = "data"
  role_files = {
      "駕駛": os.path.join(data_dir, f"{current_unit}_TD.xlsx"),
      "列車長": os.path.join(data_dir, f"{current_unit}_TM.xlsx"),
      "服勤員": os.path.join(data_dir, f"{current_unit}_TA.xlsx"),
  }
  crew_list = []
  seen_ids = set()

  for role_name, path in role_files.items():
    if os.path.exists(path):
      try:
        df = safe_read_excel(path, header=3)
        df.columns = [str(c).strip() for c in df.columns]
        for _, row in df.iterrows():
          eid = str(row.iloc[0]).strip().upper()
          ename = str(row.iloc[1]).strip()
          if (
              eid
              and eid not in seen_ids
              and eid.upper() not in ["NAN", "NONE", "員編", "EMP_ID"]
          ):
            seen_ids.add(eid)
            crew_list.append(
                {"emp_id": eid, "name": ename, "role_type": role_name}
            )
      except Exception:
        pass
  return crew_list


def load_maintenance_status():
  if not os.path.exists(MAINT_FILE):
    return {}
  try:
    with open(MAINT_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {}


def save_maintenance_status(data):
  try:
    with open(MAINT_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=4)
    return True
  except Exception as e:
    st.error(f"儲存維護設定失敗: {e}")
    return False


def render_admin_panel():
  current_unit = st.session_state.get("current_unit", "TTN")

  # 🔝 頂部列：後台標題與「返回系統首頁」按鈕
  col_title, col_btn = st.columns([3, 1])
  with col_title:
    st.markdown(f"## 🛡️ 後台管理控制台 [{current_unit}]")
  with col_btn:
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    if st.button(
        "🏠 返回系統首頁",
        key="btn_back_home",
        type="secondary",
        use_container_width=True,
    ):
      st.session_state["admin_logged_in"] = False
      st.session_state["page"] = "user"
      st.toast("已安全切換回前端查詢首頁")
      st.rerun()

  st.markdown("---")

  tab1, tab2, tab3, tab4, tab5 = st.tabs([
      "📁 大表上傳與組員快查",
      "🛠️ 模組維護模式",
      "👥 白名單帳號管理",
      "⚙️ 全域系統參數",
      "📜 系統日誌與備份",
  ])

  # =========================================================
  # Tab 1: 班表大表上傳與全域組員班表檢索
  # =========================================================
  with tab1:
    st.markdown(f"### 📁 [{current_unit}] 班表 Excel 大表上傳管理")
    st.info("💡 上傳後的 Excel 大表將儲存並即時生效於查詢與班表圖檔繪製。")

    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)

    role_files = {
        "駕駛": os.path.join(data_dir, f"{current_unit}_TD.xlsx"),
        "列車長": os.path.join(data_dir, f"{current_unit}_TM.xlsx"),
        "服勤員": os.path.join(data_dir, f"{current_unit}_TA.xlsx"),
    }

    col_u1, col_u2, col_u3 = st.columns(3)
    roles = [("駕駛", col_u1), ("列車長", col_u2), ("服勤員", col_u3)]

    for role_name, col in roles:
      file_path = role_files[role_name]
      with col:
        st.markdown(f"#### 🔹 {role_name}大表")
        if os.path.exists(file_path):
          size_kb = round(os.path.getsize(file_path) / 1024, 1)
          mtime = get_file_mtime_str(file_path)
          st.success(f"狀態：已建置 ({size_kb} KB)\n\n更新時間：{mtime}")
        else:
          st.warning("狀態：尚未上傳檔案")

        uploaded_file = st.file_uploader(
            f"選擇 {role_name} Excel 檔 (.xlsx)",
            type=["xlsx", "xls"],
            key=f"uploader_{current_unit}_{role_name}",
        )

        if uploaded_file is not None:
          if st.button(
              f"確認覆蓋上傳【{role_name}】",
              key=f"btn_upload_{role_name}",
              type="primary",
          ):
            with open(file_path, "wb") as f:
              f.write(uploaded_file.getbuffer())
            log_activity(f"後台覆蓋上傳 [{current_unit}] {role_name} 班表大表")
            st.success(f"✅ {role_name}班表大表已成功覆蓋更新！")
            st.rerun()

    st.markdown("---")
    st.markdown("### 🔎 全大表組員班表即時快查 (Admin Inspector)")
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
      inspect_target = st.text_input(
          "輸入欲查詢之員編或姓名",
          placeholder="例如: 023300 或 波莉",
          key="admin_inspect_input",
      )
    with col_s2:
      st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
      btn_inspect = st.button("即時檢析圖檔", type="primary")

    if btn_inspect and inspect_target.strip():
      target_clean = inspect_target.strip().upper()
      try:
        start_dt, dates, emp_id, emp_name, cells = process_file_data(
            target_clean
        )
        with st.spinner(f"正在繪製【{emp_name}】的月班表圖檔..."):
          buf = render_schedule_figure(
              start_dt,
              dates,
              emp_id,
              emp_name,
              cells,
              current_unit,
              badge_title="Admin Inspector | C.L.F",
          )
        log_activity(f"後台即時快查組員班表: [{emp_id}] {emp_name}")
        st.success(f"已成功載入【{emp_name}】({emp_id}) 之月班表圖檔")
        render_zoomable_image(buf)
      except Exception as e:
        st.error(f"檢索發生錯誤: {e}")

  # =========================================================
  # Tab 2: 模組維護模式控制
  # =========================================================
  with tab2:
    st.markdown(f"### 🛠️ [{current_unit}] 各功能模組維護模式切換")
    st.warning("開啟維護模式後，一般組員將無法使用該模組（管理員不受限）。")

    maint_data = load_maintenance_status()

    modules = [
        ("producer", "個人月班表圖檔繪製系統"),
        ("window_filter", "換班｜選擇換班日期快篩"),
        ("exchange_filter", "換假｜選擇換假日期快篩"),
    ]

    updated = False
    for mod_key, mod_name in modules:
      full_key = f"{current_unit}_{mod_key}"
      is_maint = maint_data.get(full_key, False)

      new_val = st.toggle(
          f"【{mod_name}】設為維護中",
          value=is_maint,
          key=f"toggle_maint_{full_key}",
      )
      if new_val != is_maint:
        maint_data[full_key] = new_val
        updated = True
        log_activity(
            f"變更維護模式: [{full_key}] ->"
            f" {'開啟維護' if new_val else '關閉維護'}"
        )

    if updated:
      if save_maintenance_status(maint_data):
        st.toast("✅ 模組維護狀態已儲存更新！")
        st.rerun()

  # =========================================================
  # Tab 3: 白名單帳號管理 (修正人員刪除失效問題)
  # =========================================================
  with tab3:
    st.markdown("### 👥 動態白名單權限管理")
    wl_data = load_allowed_users()

    is_enabled = wl_data.get("enabled", True)
    new_enabled = st.toggle(
        "啟用白名單審核機制",
        value=is_enabled,
        help="若關閉，所有在大表內的組員均可直接登入",
    )
    if new_enabled != is_enabled:
      wl_data["enabled"] = new_enabled
      save_allowed_users(wl_data)
      log_activity(
          f"變更白名單審核機制開關: {'啟用' if new_enabled else '關閉'}"
      )
      st.toast("白名單開關狀態已更新！")
      st.rerun()

    st.markdown("---")

    # 1. 新增人員表單
    with st.expander("➕ 新增白名單人員", expanded=True):
      add_mode = st.radio(
          "選擇新增方式",
          ["全大表名單快捷選擇", "手動輸入員編 (姓名自動帶入)"],
          horizontal=True,
          key="add_user_mode",
      )

      users = wl_data.get("users", [])

      if add_mode == "全大表名單快捷選擇":
        excel_crew = get_all_excel_crew(current_unit)
        if not excel_crew:
          st.warning("⚠️ 目前各大表尚未上傳，請先至第一頁籤上傳班表 Excel 檔。")
        else:
          options_map = {
              f"[{c['emp_id']}] {c['name']} ({c['role_type']})": c
              for c in excel_crew
          }

          selected_label = st.selectbox(
              "選擇欲加入白名單之同仁",
              options=list(options_map.keys()),
              index=None,
              placeholder="請點擊選擇同仁...",
              key="quick_select_crew",
          )

          col_q1, col_q2 = st.columns(2)
          with col_q1:
            quick_role = st.selectbox(
                "角色權限",
                options=["組員", "VIP"],
                index=None,
                placeholder="請選擇角色權限...",
                key="quick_role",
            )
          with col_q2:
            quick_status = st.selectbox(
                "帳號狀態",
                options=["啟用", "停用"],
                index=None,
                placeholder="請選擇帳號狀態...",
                key="quick_status",
            )

          if st.button("➕ 加入所選同仁至白名單", type="primary"):
            if not selected_label:
              st.error("請先選擇欲加入之同仁！")
            elif not quick_role:
              st.error("請選擇角色權限！")
            elif not quick_status:
              st.error("請選擇帳號狀態！")
            else:
              target_info = options_map[selected_label]
              q_id = target_info["emp_id"]
              q_name = target_info["name"]

              existing = next(
                  (u for u in users if u.get("emp_id", "").upper() == q_id), None
              )
              if existing:
                existing["name"] = q_name
                existing["role"] = quick_role
                existing["status"] = quick_status
                st.success(f"已更新員編 [{q_id}] {q_name} 之權限資料！")
              else:
                users.append({
                    "emp_id": q_id,
                    "name": q_name,
                    "role": quick_role,
                    "status": quick_status,
                })
                st.success(f"已成功新增 [{q_id}] {q_name} 至白名單！")

              wl_data["users"] = users
              save_allowed_users(wl_data)
              log_activity(
                  f"新增白名單: [{q_id}] {q_name} (角色:{quick_role},"
                  f" 狀態:{quick_status})"
              )
              st.rerun()

      else:
        with st.form("add_user_form_manual"):
          col_u1, col_u2 = st.columns(2)
          with col_u1:
            new_emp_id = (
                st.text_input("員編", placeholder="例如: A021987")
                .strip()
                .upper()
            )
            new_name = st.text_input(
                "姓名 (可留空，系統自動比對大表帶入)",
                placeholder="若留空將自動帶入大表姓名",
            ).strip()
          with col_u2:
            new_role = st.selectbox(
                "角色權限",
                options=["組員", "VIP"],
                index=None,
                placeholder="請選擇角色權限...",
            )
            new_status = st.selectbox(
                "帳號狀態",
                options=["啟用", "停用"],
                index=None,
                placeholder="請選擇帳號狀態...",
            )

          btn_add_user = st.form_submit_button(
              "新增至白名單", type="primary"
          )

          if btn_add_user:
            if not new_emp_id:
              st.error("請輸入有效員編！")
            elif not new_role:
              st.error("請選擇角色權限！")
            elif not new_status:
              st.error("請選擇帳號狀態！")
            else:
              auto_fetched_name = get_employee_name(current_unit, new_emp_id)
              final_name = (
                  new_name
                  if new_name
                  else (
                      auto_fetched_name
                      if auto_fetched_name
                      else f"組員_{new_emp_id}"
                  )
              )

              existing = next(
                  (
                      u
                      for u in users
                      if u.get("emp_id", "").upper() == new_emp_id
                  ),
                  None,
              )
              if existing:
                existing["name"] = final_name
                existing["role"] = new_role
                existing["status"] = new_status
                st.success(
                    f"已更新員編 [{new_emp_id}] 資料 (姓名: {final_name})！"
                )
              else:
                users.append({
                    "emp_id": new_emp_id,
                    "name": final_name,
                    "role": new_role,
                    "status": new_status,
                })
                st.success(
                    f"已新增員編 [{new_emp_id}] ({final_name}) 至白名單！"
                )

              wl_data["users"] = users
              save_allowed_users(wl_data)
              log_activity(
                  f"手動新增白名單: [{new_emp_id}] {final_name}"
                  f" (角色:{new_role}, 狀態:{new_status})"
              )
              st.rerun()

    # 2. 🔍 白名單即時搜尋與多重篩選列
    st.markdown("#### 📋 現有白名單人員列表與檢索")

    col_srch1, col_srch2, col_srch3 = st.columns([2, 1, 1])
    with col_srch1:
      search_kw = (
          st.text_input(
              "🔍 搜尋員編或姓名",
              placeholder="輸入關鍵字比對 (例如: 0233 或 小明)...",
              key="wl_search_kw",
          )
          .strip()
          .upper()
      )
    with col_srch2:
      filter_role = st.selectbox(
          "角色篩選", ["全部", "組員", "VIP"], key="wl_filter_role"
      )
    with col_srch3:
      filter_status = st.selectbox(
          "狀態篩選", ["全部", "啟用", "停用"], key="wl_filter_status"
      )

    users_list = wl_data.get("users", [])

    filtered_users = []
    for u in users_list:
      emp = str(u.get("emp_id", "")).strip().upper()
      name = str(u.get("name", "")).strip().upper()
      role = u.get("role", "組員")
      status = u.get("status", "啟用")

      if search_kw and (search_kw not in emp and search_kw not in name):
        continue
      if filter_role != "全部" and role != filter_role:
        continue
      if filter_status != "全部" and status != filter_status:
        continue

      filtered_users.append(u)

    st.caption(
        f"📊 檢索結果：顯示 {len(filtered_users)} 筆 / 共 {len(users_list)} 筆資料"
    )

    if not filtered_users:
      st.info("搜尋無結果，請調整關鍵字或篩選條件。")
    else:
      df_users = pd.DataFrame(filtered_users)
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
        updated_records = edited_df.to_dict(orient="records")

        # 1. 取得這批畫面上顯示的人員員編集合
        displayed_emp_ids = {
            str(u.get("emp_id", "")).strip().upper() for u in filtered_users
        }

        # 2. 取得編輯/刪除後留下的員編 map 與集合
        updated_map = {}
        remaining_emp_ids = set()
        for r in updated_records:
          emp = str(r.get("emp_id", "")).strip().upper()
          if emp and emp != "NAN":
            updated_map[emp] = r
            remaining_emp_ids.add(emp)

        # 3. 算出現場被按垃圾桶刪除的員編集合
        deleted_emp_ids = displayed_emp_ids - remaining_emp_ids

        # 4. 重構白名單
        final_users = []
        for orig in users_list:
          orig_emp = str(orig.get("emp_id", "")).strip().upper()

          # 若這筆資料屬於本次被刪除的人，跳過不保留
          if orig_emp in deleted_emp_ids:
            continue

          # 若這筆資料屬於修改後的人，寫入修改後的內容
          if orig_emp in updated_map:
            u_rec = updated_map.pop(orig_emp)
            final_users.append({
                "emp_id": orig_emp,
                "name": str(u_rec.get("name", "")).strip(),
                "role": str(u_rec.get("role", "組員")).strip(),
                "status": str(u_rec.get("status", "啟用")).strip(),
            })
          else:
            final_users.append(orig)

        # 5. 補上直接在表格最下方手動新增的新行
        for new_emp, u_rec in updated_map.items():
          final_users.append({
              "emp_id": new_emp,
              "name": str(u_rec.get("name", "")).strip(),
              "role": str(u_rec.get("role", "組員")).strip(),
              "status": str(u_rec.get("status", "啟用")).strip(),
          })

        wl_data["users"] = final_users
        save_allowed_users(wl_data)
        log_activity(
            f"儲存白名單列表變更 (刪除 {len(deleted_emp_ids)} 筆人員)"
        )
        st.success("✅ 白名單變更（包含人員刪除與修改）已成功儲存！")
        st.rerun()

  # =========================================================
  # Tab 4: 全域系統參數設定
  # =========================================================
  with tab4:
    st.markdown("### ⚙️ 系統核心通行碼與圖表顯示參數")
    st.info("💡 修改設定後將即時生效，無需重啟應用程式。")

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
          log_activity("更新全域系統參數與金鑰設定")
          st.success("✅ 全域系統參數已成功儲存並即時生效！")
          st.rerun()
        else:
          st.error("❌ 儲存設定時發生錯誤，請檢查檔案權限。")

  # =========================================================
  # Tab 5: 系統日誌與備份打包
  # =========================================================
  with tab5:
    st.markdown("### 📜 系統操作日誌與資料打包備份")

    logs = load_activity_logs()

    if logs:
      st.markdown(f"#### 🔍 最近系統操作日誌 (共 {len(logs)} 筆)")
      df_logs = pd.DataFrame(logs)
      col_order = [
          "timestamp",
          "unit",
          "user_id",
          "user_name",
          "device",
          "action",
      ]
      existing_cols = [c for c in col_order if c in df_logs.columns]

      df_logs_disp = df_logs[existing_cols].rename(
          columns={
              "timestamp": "紀錄時間",
              "unit": "單位",
              "user_id": "操作者員編",
              "user_name": "姓名",
              "device": "使用裝置",
              "action": "操作動作細節",
          }
      )
      st.dataframe(df_logs_disp, use_container_width=True, height=280)
    elif os.path.exists(LOG_FILE):
      try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
          raw_lines = f.readlines()
        if raw_lines:
          st.text_area(
              "系統原始日誌 (最新 100 筆)",
              "".join(raw_lines[-100:]),
              height=220,
          )
        else:
          st.info("日誌紀錄檔目前為空，尚無操作紀錄。")
      except Exception as e:
        st.error(f"讀取日誌發生錯誤: {e}")
    else:
      st.info(
          "尚無日誌紀錄檔（系統將於使用者進行班表查詢、換班/換假檢索或變更後台設定時自動建立）。"
      )

    st.markdown("---")
    st.markdown("#### 📦 一鍵備份全站數據與設定")

    def make_backup_zip():
      buf = io.BytesIO()
      with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in [
            "allowed_users.json",
            "system_config.json",
            "maintenance.json",
            "config.py",
            LOG_FILE,
        ]:
          if os.path.exists(fname):
            zf.write(fname, os.path.basename(fname))
        if os.path.exists("data"):
          for root, _, files in os.walk("data"):
            for file in files:
              full_p = os.path.join(root, file)
              zf.write(full_p, os.path.relpath(full_p, "."))
      buf.seek(0)
      return buf

    st.download_button(
        "📥 一鍵打包下載全站資料與設定備份 (ZIP)",
        data=make_backup_zip(),
        file_name=(
            f"TTN_Engine_Full_Backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        ),
        mime="application/zip",
        type="primary",
    )
