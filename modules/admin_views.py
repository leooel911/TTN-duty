import os
import time
import hashlib
import pandas as pd
import streamlit as st
from datetime import datetime
from config import UNITS, LOG_FILE, FEEDBACK_IMG_DIR
from modules.utils import (
    is_module_maintenance, set_module_maintenance, log_activity, safe_read_excel
)
from modules.services import load_allowed_users, save_allowed_users
from modules.components import view_feedback_img_modal

def render_admin_panel():
    st.markdown("""
    <div class="section-header-box">
        <div class="section-title">管理員專用：Database 智慧控制台</div>
        <div class="section-subtitle">Advanced Crew Duty Management & Data Maintenance Center</div>
    </div>
    """, unsafe_allow_html=True)

    col_unit_sel, col_btn_home, col_btn_logout = st.columns([2, 1, 1])
    with col_unit_sel:
        admin_target_unit = st.selectbox("維護目標單位", ["TTN", "TTC", "TTS"], key="admin_target_unit_sel", label_visibility="collapsed")
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
        "使用者權限管理",
        "客服工單管理中心 (Table View)", 
        "系統操作日誌"
    ])

    # ---------------------------------------------------------
    # TAB 1: 數據與檔案維護
    # ---------------------------------------------------------
    with tab_status:
        st.subheader(f"【{admin_target_unit}】伺服器狀態 & Dashboard 數據")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            td_ok = os.path.exists(current_unit_files["駕駛"])
            st.metric("駕駛大表 (TD)", "已就緒" if td_ok else "缺檔案", delta="正常" if td_ok else "缺失")
        with m2:
            tm_ok = os.path.exists(current_unit_files["列車長"])
            st.metric("列車長大表 (TM)", "已就緒" if tm_ok else "缺檔案", delta="正常" if tm_ok else "缺失")
        with m3:
            ta_ok = os.path.exists(current_unit_files["服勤員"])
            st.metric("服勤員大表 (TA)", "已就緒" if ta_ok else "缺檔案", delta="正常" if ta_ok else "缺失")
        with m4:
            log_cnt = 0
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f: log_cnt = len(f.readlines())
            st.metric("系統日誌累計", f"{log_cnt} 筆", delta="Activity")

        st.markdown("---")
        st.subheader(f"四大系統模組維護開關控制（當前控制單位：{admin_target_unit}）")

        is_prod_maint = is_module_maintenance(admin_target_unit, "producer")
        is_win_maint = is_module_maintenance(admin_target_unit, "window_filter")
        is_ex_maint = is_module_maintenance(admin_target_unit, "exchange_filter")

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            new_prod = st.checkbox("【個人月班表圖檔】維護中", value=is_prod_maint, key=f"cb_{admin_target_unit}_producer")
            if new_prod != is_prod_maint:
                set_module_maintenance(admin_target_unit, "producer", new_prod)
                log_activity(f"設定 [{admin_target_unit}] 個人月班表維護開關: {'開啟維護' if new_prod else '解除維護'}")
                st.rerun()

        with col_m2:
            new_win = st.checkbox("【換班選擇日期】維護中", value=is_win_maint, key=f"cb_{admin_target_unit}_window_filter")
            if new_win != is_win_maint:
                set_module_maintenance(admin_target_unit, "window_filter", new_win)
                log_activity(f"設定 [{admin_target_unit}] 換班選擇日期維護開關: {'開啟維護' if new_win else '解除維護'}")
                st.rerun()

        with col_m3:
            new_ex = st.checkbox("【換假選擇日期】維護中", value=is_ex_maint, key=f"cb_{admin_target_unit}_exchange_filter")
            if new_ex != is_ex_maint:
                set_module_maintenance(admin_target_unit, "exchange_filter", new_ex)
                log_activity(f"設定 [{admin_target_unit}] 換假選擇日期維護開關: {'開啟維護' if new_ex else '解除維護'}")
                st.rerun()

        st.markdown("---")
        st.subheader(f"【{admin_target_unit}】班表維護控制台")
        selected_role = st.selectbox("選擇目前要維護的職位類別", ["駕駛", "列車長", "服勤員"], index=2, key="admin_role_select_box")
        target_path = current_unit_files[selected_role]

        uploaded_file_update = st.file_uploader(f"上傳【{admin_target_unit} - {selected_role}】最新大表 (.xlsx)", type=["xlsx", "xls", "csv"], key=f"up_{admin_target_unit}_{selected_role}")
        if uploaded_file_update is not None:
            file_bytes = uploaded_file_update.getvalue()
            current_hash = hashlib.md5(file_bytes).hexdigest()
            hash_key = f"hash_{admin_target_unit}_{selected_role}"

            if st.session_state.get(hash_key) != current_hash:
                try:
                    with open(target_path, "wb") as f: f.write(file_bytes)
                    st.session_state[hash_key] = current_hash
                    log_activity(f"上傳【{admin_target_unit} - {selected_role}】最新大表")
                    st.success("檔案上傳成功！")
                    time.sleep(0.5); st.rerun()
                except Exception as e: st.error(f"寫入失敗: {e}")

    # ---------------------------------------------------------
    # TAB 2: 使用者權限管理 (新增)
    # ---------------------------------------------------------
    with tab_users:
        st.subheader("使用者登入與存取權限控制（白名單機制）")
        
        data = load_allowed_users()
        users_list = data.get("users", [])

        # 1. 全域驗證開關
        col_sw1, col_sw2 = st.columns([3, 1])
        with col_sw1:
            is_enabled = st.toggle("啟用全系統使用者白名單存取驗證", value=data.get("enabled", True), key="admin_user_whitelist_toggle")
            if is_enabled != data.get("enabled", True):
                data["enabled"] = is_enabled
                save_allowed_users(data)
                log_activity(f"設定白名單驗證開關: {'開啟' if is_enabled else '關閉'}")
                st.success(f"已{'開啟' if is_enabled else '關閉'}白名單驗證機制！")
                time.sleep(0.3)
                st.rerun()

        if not is_enabled:
            st.info("💡 目前白名單驗證已【關閉】，所有組員輸入員編/姓名皆可使用系統。")
        else:
            st.warning("🔒 目前白名單驗證已【開啟】，僅下方列表中「啟用」狀態的人員可存取系統。")

        st.markdown("---")

        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📋 白名單人員總覽", "➕ 單筆新增人員", "📥 批次匯入人員"])

        # 子頁籤 1：白名單總覽
        with sub_tab1:
            if users_list:
                df_u = pd.DataFrame(users_list)
                
                search_kw = st.text_input("🔍 關鍵字過濾員編或姓名", "", key="admin_user_search_kw").strip().upper()
                if search_kw:
                    df_u = df_u[df_u["emp_id"].astype(str).str.upper().str.contains(search_kw) | df_u["name"].astype(str).str.upper().str.contains(search_kw)]

                st.dataframe(
                    df_u,
                    column_config={
                        "emp_id": "員工編號",
                        "name": "姓名",
                        "role": "職務類別",
                        "status": "帳號狀態"
                    },
                    use_container_width=True,
                    hide_index=True
                )

                st.markdown("##### 🛠️ 快速操作區")
                del_col1, del_col2 = st.columns([3, 1])
                with del_col1:
                    target_emp_str = st.selectbox("選擇要操作的人員", [f"{u['emp_id']} - {u['name']}" for u in users_list], key="admin_user_op_select")
                with del_col2:
                    if st.button("❌ 刪除人員", key="btn_del_user_admin", use_container_width=True):
                        target_id = target_emp_str.split(" - ")[0]
                        data["users"] = [u for u in data["users"] if u["emp_id"] != target_id]
                        save_allowed_users(data)
                        log_activity(f"管理員刪除白名單人員: {target_emp_str}")
                        st.success(f"已成功刪除 {target_emp_str}！")
                        time.sleep(0.3)
                        st.rerun()
            else:
                st.info("目前白名單內無任何使用者資料。")

        # 子頁籤 2：單筆新增
        with sub_tab2:
            with st.form("add_single_user_form_admin"):
                new_id = st.text_input("員工編號 (例: A023300)").strip().upper()
                new_name = st.text_input("姓名 (例: 江立夫)").strip()
                new_role = st.selectbox("職務類別", ["服勤員", "列車長", "駕駛", "管理員"])
                submit_btn = st.form_submit_button("新增至白名單", use_container_width=True)

                if submit_btn:
                    if not new_id or not new_name:
                        st.error("請填寫完整的員編與姓名！")
                    elif any(u["emp_id"] == new_id for u in data["users"]):
                        st.warning(f"員編「{new_id}」已存在於白名單中！")
                    else:
                        data["users"].append({
                            "emp_id": new_id,
                            "name": new_name,
                            "role": new_role,
                            "status": "啟用"
                        })
                        save_allowed_users(data)
                        log_activity(f"管理員新增白名單人員: {new_name} ({new_id})")
                        st.success(f"成功新增：{new_name} ({new_id})！")
                        time.sleep(0.3)
                        st.rerun()

        # 子頁籤 3：批次匯入
        with sub_tab3:
            st.caption("請貼上批次資料，每行一筆，格式為：`員編,姓名,職務`（職務選填，預設為服勤員）")
            bulk_text = st.text_area("文字貼上區", placeholder="A023300,江立夫,服勤員\nA022298,葉美君,服勤員", height=150, key="admin_bulk_user_text")
            if st.button("開始批次匯入", key="btn_bulk_import_users", use_container_width=True):
                if bulk_text.strip():
                    count = 0
                    lines = bulk_text.strip().split("\n")
                    for line in lines:
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 2:
                            b_id, b_name = parts[0].upper(), parts[1]
                            b_role = parts[2] if len(parts) >= 3 else "服勤員"
                            if not any(u["emp_id"] == b_id for u in data["users"]):
                                data["users"].append({
                                    "emp_id": b_id,
                                    "name": b_name,
                                    "role": b_role,
                                    "status": "啟用"
                                })
                                count += 1
                    save_allowed_users(data)
                    log_activity(f"管理員批次匯入白名單人員 {count} 筆")
                    st.success(f"成功批次匯入 {count} 筆人員資料！")
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
                        "詳細說明": "無說明內容"
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
                                    if k_clean in ["處理編號", "單號"]: rec["單號"] = v_clean
                                    elif k_clean == "狀態": rec["狀態"] = v_clean
                                    elif k_clean == "類別": rec["類別"] = v_clean
                                    elif k_clean == "單位": rec["單位"] = v_clean
                                    elif k_clean in ["回報者", "回報者員編"]: rec["回報者"] = v_clean
                                    elif k_clean == "時間": rec["時間"] = v_clean
                                    elif k_clean in ["管理員回覆", "回覆"]: rec["管理員回覆"] = v_clean
                            if desc_lines:
                                rec["詳細說明"] = "".join(desc_lines).strip()
                    except Exception as e:
                        rec["詳細說明"] = f"解析失敗: {e}"
                    
                    all_fb_records.append(rec)
        
        all_fb_records = sorted(all_fb_records, key=lambda x: x["stem"], reverse=True)
        
        cnt_total = len(all_fb_records)
        cnt_pending = sum(1 for r in all_fb_records if r["狀態"] == "待處理")
        cnt_processing = sum(1 for r in all_fb_records if r["狀態"] == "處理中")
        cnt_done = sum(1 for r in all_fb_records if r["狀態"] == "已完成")
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("總工單數", f"{cnt_total} 筆")
        kpi2.metric("待處理", f"{cnt_pending} 筆", delta="-需處理" if cnt_pending > 0 else "清空", delta_color="inverse")
        kpi3.metric("處理中", f"{cnt_processing} 筆")
        kpi4.metric("已完成", f"{cnt_done} 筆")
        
        st.markdown("---")
        
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            filter_status = st.selectbox("狀態過濾", ["全部", "待處理", "處理中", "已完成", "已不處理"], index=0, key="admin_fb_filter_status")
        with f_col2:
            filter_unit = st.selectbox("單位過濾", ["全部", "TTN", "TTC", "TTS"], index=0, key="admin_fb_filter_unit")
        with f_col3:
            filter_category = st.selectbox("類別過濾", ["全部", "Bug 問題回報", "功能改進建議", "班表資料不對", "其他"], index=0, key="admin_fb_filter_cat")
            
        filtered_records = []
        for r in all_fb_records:
            if filter_status != "全部" and r["狀態"] != filter_status: continue
            if filter_unit != "全部" and r["單位"] != filter_unit: continue
            if filter_category != "全部" and r["類別"] != filter_category: continue
            filtered_records.append(r)
            
        st.caption(f"共顯示 {len(filtered_records)} 筆紀錄")
        
        if filtered_records:
            t_h1, t_h2, t_h3, t_h4, t_h5, t_h6 = st.columns([2.2, 1.8, 1.3, 3.2, 1.2, 2.3])
            t_h1.markdown("**工單編號 / 時間**")
            t_h2.markdown("**提報人員**")
            t_h3.markdown("**類別**")
            t_h4.markdown("**詳細說明**")
            t_h5.markdown("**狀態**")
            t_h6.markdown("**管理與截圖操作**")
            st.markdown("<hr style='margin: 4px 0 10px 0; border-color: rgba(56, 189, 248, 0.3);'>", unsafe_allow_html=True)
            
            for idx, rec in enumerate(filtered_records):
                status_color_map = {
                    "待處理": "#F59E0B",
                    "處理中": "#38BDF8",
                    "已完成": "#34D399",
                    "已不處理": "#94A3B8"
                }
                st_color = status_color_map.get(rec["狀態"], "#F59E0B")
                
                c1, c2, c3, c4, c5, c6 = st.columns([2.2, 1.8, 1.3, 3.2, 1.2, 2.3])
                
                with c1:
                    st.markdown(f"<span style='font-family:monospace; font-weight:800; color:#38BDF8; font-size:12px;'>{rec['單號']}</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='font-family:monospace; color:#94A3B8; font-size:10px;'>{rec['時間']}</span>", unsafe_allow_html=True)
                    
                with c2:
                    st.markdown(f"<span style='font-family:monospace; color:#F8FAFC; font-weight:700; font-size:11.5px;'>[{rec['單位']}]</span>", unsafe_allow_html=True)
                    st.markdown(f"<span style='font-family:monospace; color:#CBD5E1; font-size:11px;'>{rec['回報者']}</span>", unsafe_allow_html=True)
                    
                with c3:
                    st.markdown(f"<span style='font-family:monospace; color:#E2E8F0; font-size:11.5px;'>{rec['類別']}</span>", unsafe_allow_html=True)
                    
                with c4:
                    st.markdown(f"<span style='font-family:monospace; color:#F8FAFC; font-size:11.5px; white-space:pre-wrap;'>{rec['詳細說明']}</span>", unsafe_allow_html=True)
                    
                with c5:
                    st.markdown(f"<span style='font-family:monospace; font-weight:800; color:{st_color}; font-size:12px;'>【{rec['狀態']}】</span>", unsafe_allow_html=True)
                    
                with c6:
                    act_c1, act_c2 = st.columns(2)
                    with act_c1:
                        if rec["img_path"]:
                            if st.button("檢視", key=f"tbl_img_{idx}", use_container_width=True):
                                view_feedback_img_modal(rec["img_path"], rec["單號"], f"[{rec['單位']}] {rec['回報者']}")
                        else:
                            st.button("無附件", key=f"tbl_no_img_{idx}", disabled=True, use_container_width=True)
                    with act_c2:
                        with st.popover("處置", use_container_width=True):
                            m_status_idx = ["待處理", "處理中", "已完成", "已不處理"].index(rec["狀態"]) if rec["狀態"] in ["待處理", "處理中", "已完成", "已不處理"] else 0
                            new_st = st.selectbox("變更狀態", ["待處理", "處理中", "已完成", "已不處理"], index=m_status_idx, key=f"pop_st_{idx}")
                            new_reply = st.text_input("留言回覆", value="" if rec["管理員回覆"] == "尚無回覆" else rec["管理員回覆"], placeholder="例如: 已發布更新修正", key=f"pop_rp_{idx}")
                            
                            col_p1, col_p2 = st.columns(2)
                            with col_p1:
                                if st.button("儲存", key=f"pop_save_{idx}", use_container_width=True):
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
                                                    ft.write(f"管理員回覆: {new_reply.strip() if new_reply.strip() else '尚無回覆'}\n")
                                                    has_rp = True
                                                else:
                                                    ft.write(line)
                                            if not has_st: ft.write(f"狀態: {new_st}\n")
                                            if not has_rp: ft.write(f"管理員回覆: {new_reply.strip() if new_reply.strip() else '尚無回覆'}\n")
                                        
                                        log_activity(f"管理員處置工單 [{rec['單號']}] -> 狀態:{new_st}")
                                        st.success("完成！")
                                        time.sleep(0.3)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"失敗: {e}")
                            with col_p2:
                                if st.button("刪除", key=f"pop_del_{idx}", use_container_width=True):
                                    try:
                                        if os.path.exists(rec["txt_path"]): os.remove(rec["txt_path"])
                                        if rec["img_path"] and os.path.exists(rec["img_path"]): os.remove(rec["img_path"])
                                        log_activity(f"管理員刪除工單: {rec['單號']}")
                                        st.rerun()
                                    except Exception as e: st.error(f"失敗: {e}")
                
                st.markdown("<hr style='margin: 6px 0; border-color: rgba(255, 255, 255, 0.05);'>", unsafe_allow_html=True)
        else:
            st.info("目前無符合條件的回報紀錄。")

    # ---------------------------------------------------------
    # TAB 4: 系統操作日誌
    # ---------------------------------------------------------
    with tab_logs:
        st.subheader("系統操作活動紀錄日誌 (Activity Log)")
        
        col_log1, col_log2, col_log3 = st.columns([2, 1, 1])
        with col_log1:
            log_filter_keyword = st.text_input("搜尋關鍵字", placeholder="輸入員編、換班或問題回報...", key="admin_log_search_input")
        with col_log2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    log_raw_data = f.read()
                st.download_button(
                    label="📥 下載日誌 CSV",
                    data=log_raw_data,
                    file_name=f"Activity_Log_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="admin_download_log_btn",
                    use_container_width=True
                )
        with col_log3:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("清空歷史日誌", key="admin_clear_log_btn", use_container_width=True):
                if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
                st.rerun()

        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f: logs = f.readlines()
            parsed_logs = []
            for line in reversed(logs[-100:]): # 顯示最近 100 筆
                if log_filter_keyword and log_filter_keyword.lower() not in line.lower(): continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    parsed_logs.append({
                        "時間": parts[0], 
                        "單位": parts[1].replace("單位: ", ""),
                        "操作者": parts[2].replace("操作者員編: ", ""),
                        "裝置": parts[3].replace("裝置: ", ""), 
                        "動作": " | ".join(parts[4:]).replace("動作: ", "")
                    })
            
            if parsed_logs:
                df_parsed = pd.DataFrame(parsed_logs)
                
                with st.expander("📊 查看熱門動作統計圖表", expanded=False):
                    action_counts = df_parsed["動作"].value_counts().head(10)
                    st.bar_chart(action_counts)

                st.dataframe(df_parsed, use_container_width=True, hide_index=True)
            else: st.info("查無符合過濾條件的日誌")
        else: st.info("尚無任何紀錄")
