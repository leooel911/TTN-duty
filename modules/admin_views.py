import io
import json
import os
import zipfile
from datetime import datetime

from config import DATA_DIR, LOG_FILE, UNITS
from modules.utils import (
    get_employee_name,
    get_file_mtime_str,
    is_module_maintenance,
    load_activity_logs,
    log_activity,
    safe_read_excel,
    set_module_maintenance,
)
import pandas as pd
import streamlit as st


# =========================================================
# 🛠️ 1. 日誌清空與全站備份輔助工具
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
  """打包 data 資料夾與系統設定檔為 ZIP 下載檔"""
  buf = io.BytesIO()
  with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    if os.path.exists(DATA_DIR):
      for root, _, files in os.walk(DATA_DIR):
        for file in files:
          file_path = os.path.join(root, file)
          arcname = os.path.relpath(file_path, start=DATA_DIR)
          zf.write(file_path, arcname=os.path.join("data", arcname))
    for root_file in ["activity.log", "maintenance.json", "whitelist.json"]:
      if os.path.exists(root_file):
        zf.write(root_file, arcname=root_file)
  buf.seek(0)
  return buf


# =========================================================
# 👑 2. 管理員後台主視圖 (Admin Panel)
# =========================================================
def render_admin_home():
  st.markdown("## ⚙️ 系統管理後台 (Administrator Console)")

  current_unit = st.session_state.get("current_unit", "TTN")

  # 管理員五大分頁
  tab1, tab2, tab3, tab4, tab5 = st.tabs([
      "📂 大表上傳與組員快查",
      "🛠️ 模組維護模式",
      "👤 白名單帳號管理",
      "⚙️ 全域系統參數",
      "📜 系統日誌與備份",
  ])

  # ---------------------------------------------------------
  # Tab 1: 大表上傳與組員快查
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
              st.success(f"{role_name} 班表大表已成功更新！")
              log_activity(f"管理員上傳 {current_unit} - {role_name} 大表")
              st.cache_data.clear()
              st.rerun()
            except Exception as e:
              st.error(f"檔案寫入失敗：{e}")

    st.markdown("---")
    st.markdown("#### 🔍 組員資料速查庫")
    emp_input = st.text_input(
        "輸入員編查詢姓名對照",
        placeholder="如: 023300",
        key="admin_emp_search",
    ).strip()
    if emp_input:
      found_name = get_employee_name(current_unit, emp_input)
      if found_name:
        st.success(f"員編 `[{emp_input}]` 對應姓名為：**{found_name}**")
      else:
        st.warning(f"在大表中未找到員編 `[{emp_input}]` 之對應姓名。")

  # ---------------------------------------------------------
  # Tab 2: 模組維護模式
  # ---------------------------------------------------------
  with tab2:
    st.markdown(f"### 🛠️ [{current_unit}] 系統模組維護開關")
    st.info("開啟維護後，一般組員將無法存取該功能，管理員仍可登入後台預覽。")

    modules_def = [
        ("producer", "📊 個人月班表圖檔生成系統"),
        ("window_filter", "🔄 換班｜選擇換班日期快篩"),
        ("exchange_filter", "🌴 換假｜選擇換假日期快篩"),
    ]

    for m_key, m_title in modules_def:
      c_title, c_sw = st.columns([3, 1])
      is_maint = is_module_maintenance(current_unit, m_key)

      with c_title:
        st.markdown(f"**{m_title}**")
        st.caption(
            "狀態："
            + (
                "<span style='color:#EF4444; font-weight:800;'>維護中 (已阻擋組員)</span>"
                if is_maint
                else "<span style='color:#34D399; font-weight:800;'>正常開放中</span>"
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
  # Tab 3: 白名單帳號管理
  # ---------------------------------------------------------
  with tab3:
    st.markdown("### 👤 白名單與 VIP 通行帳號管理")
    whitelist_path = os.path.join(DATA_DIR, "whitelist.json")

    whitelist_data = {}
    if os.path.exists(whitelist_path):
      try:
        with open(whitelist_path, "r", encoding="utf-8") as f:
          whitelist_data = json.load(f)
      except Exception:
        whitelist_data = {}

    st.json(whitelist_data if whitelist_data else {"info": "尚無特定白名單設定"})

  # ---------------------------------------------------------
  # Tab 4: 全域系統參數
  # ---------------------------------------------------------
  with tab4:
    st.markdown("### ⚙️ 全域系統參數與切換")
    selected_u = st.selectbox(
        "當前操作車廊/單位切換",
        options=list(UNITS.keys()),
        index=list(UNITS.keys()).index(current_unit)
        if current_unit in UNITS
        else 0,
        key="admin_unit_selector",
    )
    if selected_u != current_unit:
      st.session_state["current_unit"] = selected_u
      log_activity(f"管理員切換單位至：{selected_u}")
      st.rerun()

  # ---------------------------------------------------------
  # Tab 5: 系統日誌與備份 (包含新增的「清空紀錄」按鈕)
  # ---------------------------------------------------------
  with tab5:
    st.markdown("### 📜 系統操作日誌與資料打包備份")

    logs = load_activity_logs()

    # 🔑 頁面標頭與右側清空按鈕
    col_log_title, col_log_btn = st.columns([3, 1])

    with col_log_title:
      st.markdown(f"#### 👁️ 最近系統操作日誌 (共 {len(logs)} 筆)")

    with col_log_btn:
      st.markdown(
          "<div style='height: 2px;'></div>", unsafe_allow_html=True
      )  # 微調對齊
      if st.button(
          "🗑️ 清空紀錄",
          key="btn_clear_activity_logs",
          type="secondary",
          use_container_width=True,
      ):
        clear_logs()
        st.success("已成功清空所有系統操作日誌！")
        st.rerun()

    # 顯示操作日誌表格
    if logs:
      df_logs = pd.DataFrame(logs)
      # 欄位重新命名對照
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
    st.caption("點擊下方按鈕可將系統班表大表、設定檔與日誌打包為 ZIP 下載備份。")

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
