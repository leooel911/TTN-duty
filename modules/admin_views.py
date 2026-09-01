import os
import time
import hashlib
import pandas as pd
import streamlit as st
from config import UNITS, LOG_FILE, FEEDBACK_IMG_DIR
from modules.utils import (
    is_module_maintenance, set_module_maintenance, log_activity, safe_read_excel
)
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

    tab_status, tab_gallery, tab_logs = st.tabs([
        "數據與檔案維護", 
        "客服工單管理中心 (Table View)", 
        "系統操作日誌"
    ])

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

    with tab_logs:
        st.subheader("系統操作活動紀錄日誌 (Activity Log)")
        
        col_log1, col_log2 = st.columns([2.5, 1])
        with col_log1:
            log_filter_keyword = st.text_input("搜尋關鍵字", placeholder="輸入員編、換班或問題回報...", key="admin_log_search_input")
        with col_log2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("清空歷史日誌", key="admin_clear_log_btn"):
                if os.path.exists(LOG_FILE): os.remove(LOG_FILE)
                st.rerun()

        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f: logs = f.readlines()
            parsed_logs = []
            for line in reversed(logs[-80:]):
                if log_filter_keyword and log_filter_keyword.lower() not in line.lower(): continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    parsed_logs.append({
                        "時間": parts[0], "單位": parts[1].replace("單位: ", ""),
                        "操作者": parts[2].replace("操作者員編: ", ""),
                        "裝置": parts[3].replace("裝置: ", ""), "動作": " | ".join(parts[4:]).replace("動作: ", "")
                    })
            if parsed_logs: st.dataframe(pd.DataFrame(parsed_logs), use_container_width=True, hide_index=True)
            else: st.info("查無符合過濾條件的日誌")
        else: st.info("尚無任何紀錄")