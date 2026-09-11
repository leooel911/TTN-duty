import io
import json
import os
import re
import zipfile
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 安全載入設定檔與工具模組 (具備防崩潰安全降級機制)
# -----------------------------------------------------------------------------
try:
    from config import DATA_DIR, FEEDBACK_IMG_DIR, LOG_FILE, UNITS, WHITELIST_FILE
except Exception:
    DATA_DIR = "data"
    FEEDBACK_IMG_DIR = "feedback"
    LOG_FILE = "activity.log"
    UNITS = {"TTN": {}}
    WHITELIST_FILE = "whitelist.json"

try:
    from modules.services import load_system_config, save_system_config
except Exception:
    def load_system_config() -> Dict[str, Any]:
        return {}
    def save_system_config(cfg: Dict[str, Any]) -> None:
        pass

try:
    from modules.utils import (
        get_employee_name,
        get_file_mtime_str,
        is_module_maintenance,
        load_activity_logs,
        log_activity,
        safe_read_excel,
        set_module_maintenance,
    )
except Exception:
    def get_employee_name(unit: str, uid: str) -> str:
        return ""
    def get_file_mtime_str(path: str) -> str:
        return "--"
    def is_module_maintenance(unit: str, mod: str) -> bool:
        return False
    def set_module_maintenance(unit: str, mod: str, state: bool) -> None:
        pass
    def load_activity_logs() -> List[Any]:
        return []
    def log_activity(msg: str) -> None:
        pass
    def safe_read_excel(path: str, header: int = 0) -> pd.DataFrame:
        return pd.DataFrame()


# -----------------------------------------------------------------------------
# 2. 系統輔助函式
# -----------------------------------------------------------------------------
def clear_logs() -> None:
    """徹底清空全站系統操作日誌檔與記憶體快取（安全保留登入 Session）"""
    possible_paths = [
        LOG_FILE,
        "activity.log",
        "activity_log.csv",
        "data/activity.log",
        "data/activity_log.csv",
        os.path.join(DATA_DIR, "activity.log"),
        os.path.join(DATA_DIR, "activity_log.csv"),
    ]
    for p in set(possible_paths):
        if p and os.path.exists(p):
            try:
                with open(p, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass

    st.cache_data.clear()


@st.dialog("⚠️ 確定要清空全站系統日誌嗎？")
def show_confirm_clear_logs_modal() -> None:
    """防誤觸對話框：清空全站日誌"""
    st.warning("此動作將徹底清除所有歷史操作與稽核紀錄，且無法恢復！")
    st.markdown("請確認是否繼續？")

    col_confirm1, col_confirm2 = st.columns(2)
    with col_confirm1:
        if st.button("確認完全清空", type="primary", key="btn_modal_do_clear", use_container_width=True):
            clear_logs()
            st.rerun()
    with col_confirm2:
        if st.button("取消", key="btn_modal_cancel_clear", use_container_width=True):
            st.rerun()


def create_backup_zip() -> io.BytesIO:
    """打包數據資料夾為 ZIP 下載檔"""
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
            "activity_log.csv",
            "maintenance.json",
            "whitelist.json",
            "system_config.json",
        ]:
            if os.path.exists(root_file):
                zf.write(root_file, arcname=root_file)
    buf.seek(0)
    return buf


def load_whitelist(unit_code: str = "TTN") -> Dict[str, Any]:
    """讀取指定營運單位的白名單"""
    whitelist_path = WHITELIST_FILE
    full_data: Dict[str, Any] = {}

    if os.path.exists(whitelist_path):
        try:
            with open(whitelist_path, "r", encoding="utf-8", errors="ignore") as f:
                full_data = json.load(f)
                if full_data and not any(k in UNITS for k in full_data.keys()):
                    full_data = {u: full_data.copy() for u in UNITS.keys()}
        except Exception:
            full_data = {}

    if unit_code not in full_data:
        unit_default: Dict[str, Any] = {
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
                "role": "VIP_USER",
                "note": "TTN 預設測試員",
                "created_at": datetime.now().strftime("%Y-%m-%d"),
            }
        full_data[unit_code] = unit_default

    raw_unit_data = full_data.get(unit_code, {})
    normalized_data = {}
    for uid, info in raw_unit_data.items():
        normalized_data[str(uid).strip().upper()] = info

    return normalized_data


def save_whitelist(unit_code: str, unit_data: Dict[str, Any]) -> None:
    """儲存特定營運單位的白名單"""
    whitelist_path = WHITELIST_FILE
    os.makedirs(DATA_DIR, exist_ok=True)

    full_data: Dict[str, Any] = {}
    if os.path.exists(whitelist_path):
        try:
            with open(whitelist_path, "r", encoding="utf-8", errors="ignore") as f:
                full_data = json.load(f)
                if full_data and not any(k in UNITS for k in full_data.keys()):
                    full_data = {u: full_data.copy() for u in UNITS.keys()}
        except Exception:
            full_data = {}

    normalized_data = {}
    for uid, info in unit_data.items():
        normalized_data[str(uid).strip().upper()] = info

    full_data[unit_code] = normalized_data

    with open(whitelist_path, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)

    st.cache_data.clear()


@st.cache_data(ttl=60)
def get_all_crew_options(unit_code: str) -> List[Dict[str, str]]:
    """動態解析指定單位的各大表建立選單"""
    unit_files = UNITS.get(unit_code, UNITS.get("TTN", {}))
    crew_options: List[Dict[str, str]] = []
    seen_uids = set()

    for role_name in ["駕駛", "列車長", "服勤員"]:
        file_path = unit_files.get(role_name, "")
        if isinstance(file_path, str) and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            try:
                df = safe_read_excel(file_path, header=3)
                for _, row in df.iterrows():
                    uid = str(row.iloc[0]).strip().upper()
                    uname = str(row.iloc[1]).strip()
                    if uid and uid not in ["NAN", "NONE", "", "員編", "代碼"]:
                        if uid not in seen_uids:
                            seen_uids.add(uid)
                            label = f"{uid} - {uname} ({role_name})"
                            crew_options.append({
                                "label": label,
                                "uid": uid,
                                "name": uname,
                            })
            except Exception:
                pass
    return crew_options


def load_all_feedback_tickets() -> List[Dict[str, Any]]:
    """讀取所有問題回報工單"""
    tickets: List[Dict[str, Any]] = []
    if not os.path.exists(FEEDBACK_IMG_DIR):
        return tickets

    for fname in os.listdir(FEEDBACK_IMG_DIR):
        if fname.endswith(".txt"):
            txt_path = os.path.join(FEEDBACK_IMG_DIR, fname)
            base_name = fname[:-4]
            try:
                with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                lines = content.split("\n")
                info: Dict[str, Any] = {}
                desc_lines: List[str] = []
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

    tickets = sorted(tickets, key=lambda x: str(x.get("時間", "")), reverse=True)
    return tickets


def save_feedback_ticket(ticket_info: Dict[str, Any]) -> None:
    """更新儲存工單內容"""
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


def parse_structured_log(raw_log: Any) -> Dict[str, str]:
    """高靈敏度解析日誌：有查到大表姓名顯示『員編 (姓名)』，沒查到則顯示登入時的原始資料"""
    timestamp = "--"
    user_info = "系統/訪客"
    unit_info = "全站"
    category = "一般操作"
    action_detail = ""

    INVALID_USERS = {
        "系統/訪客", "訪客", "", "NONE", "NAN", "由早至晚", 
        "依 SIGN-IN 時間", "依 SIGN-IN 時間 (由早至晚)", "服勤員", "列車長", 
        "駕駛", "TTN", "KHH", "TXG", "TNA", "全站", "未命名"
    }

    if isinstance(raw_log, dict):
        timestamp = str(raw_log.get("timestamp", raw_log.get("時間", "--"))).strip()
        act_val = str(raw_log.get("action", raw_log.get("動作", ""))).strip()
        dtl_val = str(raw_log.get("detail", raw_log.get("詳細日誌與動作內容", ""))).strip()

        if dtl_val.lower() in ["nan", "none", ""]:
            action_detail = act_val if act_val.lower() not in ["nan", "none", ""] else "系統操作紀錄"
        else:
            action_detail = dtl_val

        user_info = str(raw_log.get("user", raw_log.get("操作者", raw_log.get("操作者/員編", "系統/訪客")))).strip()
        unit_info = str(raw_log.get("unit", raw_log.get("單位", "全站"))).strip()
        category = str(raw_log.get("category", raw_log.get("類別", act_val or "一般操作"))).strip()
    else:
        raw_str = str(raw_log).strip()
        parts = [p.strip() for p in raw_str.split("|")]
        if len(parts) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}", parts[0]):
            timestamp = parts[0]
            action_detail = " | ".join(parts[1:])
        else:
            action_detail = raw_str

    full_text = f"{category} {action_detail}"
    if "使用者登入" in full_text:
        category = "帳號登入"
    elif "管理員登入" in full_text or "登入後台" in full_text:
        category = "管理員操作"
    elif "換班" in full_text:
        category = "換班快篩"
    elif "換假" in full_text:
        category = "換假快篩"
    elif "繪製" in full_text or "圖檔" in full_text or "班表" in full_text:
        category = "月班表繪製"
    elif "工單" in full_text or "回報" in full_text:
        category = "問題與申請"
    elif category in ["一般操作", "", "nan", "NaN", "None"]:
        category = "系統操作"

    unit_match = re.search(r"單位[:：]\s*([A-Za-z0-9_]+)", action_detail)
    if unit_match and unit_match.group(1).upper() not in ["NAN", "NONE"]:
        unit_info = unit_match.group(1).upper()

    if user_info.upper() in INVALID_USERS or user_info in INVALID_USERS:
        emp_code_match = re.search(r"\b([A-Za-z]\d{6})\b", action_detail)
        login_match = re.search(r"使用者登入系統[:：]\s*([^\s\(]+)", action_detail)
        crew_match = re.search(r"(?:組員|目標組員|解析組員|操作者|員編)[:：]\s*([^\s\|,\(\)]+)", action_detail)

        if emp_code_match:
            user_info = emp_code_match.group(1).upper()
        elif login_match and login_match.group(1).strip().upper() not in INVALID_USERS:
            user_info = login_match.group(1).strip().upper()
        elif crew_match and crew_match.group(1).strip().upper() not in INVALID_USERS:
            user_info = crew_match.group(1).strip()
        elif "管理員" in action_detail:
            user_info = "ADMIN (管理員)"
        else:
            user_info = "系統/訪客"

    emp_match = re.search(r"\b([A-Za-z]\d{6})\b", user_info)
    if emp_match:
        clean_emp_id = emp_match.group(1).upper()
        emp_name = get_employee_name(unit_info, clean_emp_id)
        if emp_name:
            user_info = f"{clean_emp_id} ({emp_name})"

    return {
        "時間 (Timestamp)": timestamp,
        "操作者/員編 (User)": user_info,
        "營運單位 (Unit)": unit_info,
        "操作類別 (Category)": category,
        "詳細日誌紀錄 (Log Detail)": action_detail,
    }


def extract_device_info(detail_str: str) -> str:
    """提取裝置資訊"""
    m = re.search(r"^\[(.*?)\]", str(detail_str).strip())
    if m:
        dev = m.group(1)
        if any(k in dev for k in ["iPhone", "Android", "iPad", "Mac", "Windows", "Linux", "Web"]):
            return dev
    return "Web 介面"


# -----------------------------------------------------------------------------
# 3. 後台主畫面 UI
# -----------------------------------------------------------------------------
def render_admin_panel() -> None:
    """系統管理員後台控制台"""
    try:
        from modules.components import view_feedback_img_modal
    except ImportError:
        view_feedback_img_modal = None

    st.markdown(
        """
        <style>
        .admin-stat-card {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.8) 100%);
            border: 1.5px solid rgba(56, 189, 248, 0.35);
            border-radius: 12px;
            padding: 12px 16px;
            text-align: center;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
            transition: all 0.25s ease-in-out;
        }
        .admin-stat-card:hover {
            border-color: #38BDF8;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.4);
            transform: translateY(-2px);
        }
        .stat-val {
            font-size: 22px;
            font-weight: 900;
            font-family: monospace;
            color: #38BDF8;
            line-height: 1.2;
        }
        .stat-lbl {
            font-size: 11px;
            font-weight: 700;
            color: #94A3B8;
            letter-spacing: 0.5px;
            margin-top: 2px;
        }
        .admin-card-box {
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    current_unit = st.session_state.get("current_unit", "TTN")

    col_head_title, col_head_unit, col_head_btn = st.columns([2.2, 1.2, 1])

    with col_head_title:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 24px; font-weight: 900; color: #38BDF8; letter-spacing: 0.5px;">⚙️ 系統管理後台</span>
                <span style="font-size: 10px; font-weight: 800; color: #000; background: #38BDF8; padding: 2px 8px; border-radius: 12px; font-family: monospace;">ADMIN CONSOLE</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_head_unit:
        unit_options = list(UNITS.keys()) if isinstance(UNITS, dict) and UNITS else ["TTN"]
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
            "🚪 返回前台首頁",
            key="btn_top_return_home",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["admin_logged_in"] = False
            st.rerun()

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 大表上傳與管理",
        "🛠️ 模組維護模式",
        "👥 白名單與組員權限",
        "⚙️ 全域系統參數",
        "📜 系統日誌與備份",
        "🎫 工單與問題回報",
    ])

    # ==================== Tab 1 ====================
    with tab1:
        st.markdown(f"### 📊 [{current_unit}] 班表大表 Excel 上傳與管理")
        st.caption("即時監控各大表 Excel 檔案狀態，並提供直接覆蓋更新功能。")
        unit_files = UNITS.get(current_unit, UNITS.get("TTN", {})) if isinstance(UNITS, dict) else {}

        col_u1, col_u2, col_u3 = st.columns(3)
        roles = [
            ("駕駛", "TD", col_u1),
            ("列車長", "TM", col_u2),
            ("服勤員", "TA", col_u3),
        ]

        for role_name, role_code, col in roles:
            with col:
                target_path = unit_files.get(role_name, "")
                exists = os.path.exists(target_path) and os.path.getsize(target_path) > 0 if target_path else False
                f_size_kb = round(os.path.getsize(target_path) / 1024, 1) if exists else 0
                mtime_str = get_file_mtime_str(target_path) if exists else "檔案不存在"

                status_pill = (
                    "<span style='color:#34D399; font-weight:800;'>🟢 檔案正常</span>"
                    if exists
                    else "<span style='color:#EF4444; font-weight:800;'>🔴 缺失 / 異常</span>"
                )

                st.markdown(
                    f"""
                    <div class="admin-card-box">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 16px; font-weight: 800; color: #F8FAFC;">{role_name} ({role_code})</span>
                            {status_pill}
                        </div>
                        <div style="font-size: 11px; color: #94A3B8; font-family: monospace; display: flex; flex-direction: column; gap: 3px;">
                            <div>檔案大小：<strong style="color:#CBD5E1;">{f_size_kb} KB</strong></div>
                            <div>更新時間：<strong style="color:#CBD5E1;">{mtime_str}</strong></div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                uploaded_file = st.file_uploader(
                    f"選擇 {role_name} 大表 (.xlsx / .xls)",
                    type=["xlsx", "xls"],
                    key=f"upload_{current_unit}_{role_code}",
                )

                if uploaded_file is not None and target_path:
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

    # ==================== Tab 2 ====================
    with tab2:
        st.markdown(f"### 🛠️ [{current_unit}] 系統模組維護開關")
        st.info("💡 開啟維護後，一般組員將無法存取該功能，管理員仍可登入後台預覽測試。")

        modules_def = [
            ("producer", "個人月班表圖檔生成系統", "負責生成個人高解析度月班表圖片與圖檔下載"),
            ("window_filter", "換班｜選擇換班日期快篩", "提供指定 Sign-In 時段區間與多職位組員快篩"),
            ("exchange_filter", "換假｜選擇換假日期快篩", "提供想休日與還休日相符組員配對與連班過濾"),
        ]

        m_cols = st.columns(3)
        for idx, (m_key, m_title, m_desc) in enumerate(modules_def):
            with m_cols[idx]:
                is_maint = is_module_maintenance(current_unit, m_key)
                border_color = "#EF4444" if is_maint else "#34D399"
                status_html = (
                    "<span style='color:#EF4444; font-weight:900;'>🔴 維護中</span>"
                    if is_maint
                    else "<span style='color:#34D399; font-weight:900;'>🟢 正常開放中</span>"
                )

                st.markdown(
                    f"""
                    <div style="background: rgba(15, 23, 42, 0.8); border: 1.5px solid {border_color}; border-radius: 12px; padding: 14px; height: 140px; display: flex; flex-direction: column; justify-content: space-between;">
                        <div>
                            <div style="font-size: 15px; font-weight: 800; color: #F8FAFC; margin-bottom: 4px;">{m_title}</div>
                            <div style="font-size: 11px; color: #94A3B8;">{m_desc}</div>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 8px;">
                            <span style="font-size: 11px; color: #CBD5E1;">當前狀態：</span>
                            {status_html}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                new_state = st.toggle(
                    "開啟維護狀態",
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

    # ==================== Tab 3 ====================
    with tab3:
        st.markdown(f"### 👥 白名單與組員權限管理 [{current_unit}]")
        whitelist_data = load_whitelist(current_unit)

        cnt_total = len(whitelist_data)
        cnt_admin = sum(1 for v in whitelist_data.values() if isinstance(v, dict) and v.get("role") == "ADMIN")
        cnt_vip = sum(1 for v in whitelist_data.values() if isinstance(v, dict) and v.get("role") in ["VIP_USER", "TESTER"])

        st.markdown(
            f"""
            <div style="display: flex; gap: 10px; margin-bottom: 16px;">
                <div class="admin-stat-card" style="flex: 1;">
                    <div class="stat-val">{cnt_total} <span style="font-size: 12px;">位</span></div>
                    <div class="stat-lbl">白名單總人數</div>
                </div>
                <div class="admin-stat-card" style="flex: 1; border-color: rgba(52, 211, 153, 0.4);">
                    <div class="stat-val" style="color: #34D399;">{cnt_admin} <span style="font-size: 12px;">位</span></div>
                    <div class="stat-lbl">系統管理員 (ADMIN)</div>
                </div>
                <div class="admin-stat-card" style="flex: 1; border-color: rgba(251, 191, 36, 0.4);">
                    <div class="stat-val" style="color: #FBBF24;">{cnt_vip} <span style="font-size: 12px;">位</span></div>
                    <div class="stat-lbl">VIP / 測試員 (TESTER)</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        ver_key = f"wl_reset_ver_{current_unit}"
        if ver_key not in st.session_state:
            st.session_state[ver_key] = 0
        current_ver = st.session_state[ver_key]
        table_key = f"wl_table_select_{current_unit}_{current_ver}"

        col_wl_left, col_wl_right = st.columns([1.3, 1])

        wl_rows: List[Dict[str, Any]] = []
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

        selected_row_data: Optional[Dict[str, Any]] = None
        with col_wl_left:
            st.markdown(f"#### 現有白名單名冊 [{current_unit}]")

            search_keyword = st.text_input(
                "搜尋過濾白名單人員",
                placeholder="輸入員編、姓名、身份或備註...",
                key=f"whitelist_search_kw_{current_unit}",
            ).strip()

            filtered_df = df_wl.copy()
            if search_keyword and not filtered_df.empty:
                kw = search_keyword.lower()
                filtered_df = filtered_df[
                    filtered_df["員編/帳號"].astype(str).str.lower().str.contains(kw)
                    | filtered_df["姓名"].astype(str).str.lower().str.contains(kw)
                    | filtered_df["身份權限"].astype(str).str.lower().str.contains(kw)
                    | filtered_df["備註"].astype(str).str.lower().str.contains(kw)
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

                selection_data = getattr(event, "selection", {})
                selected_rows = selection_data.get("rows", []) if isinstance(selection_data, dict) else []
                if selected_rows:
                    selected_idx = selected_rows[0]
                    if 0 <= selected_idx < len(filtered_df):
                        selected_row_data = filtered_df.iloc[selected_idx].to_dict()
            else:
                st.info(f"目前【{current_unit}】尚無匹配的白名單人員紀錄。")

        with col_wl_right:
            st.markdown("#### 權限維護與快速編輯")

            col_mode_txt, col_mode_btn = st.columns([2, 1])
            with col_mode_txt:
                if selected_row_data:
                    st.success(f"已點選：**{selected_row_data['員編/帳號']} - {selected_row_data['姓名']}**")
                else:
                    st.info("當前模式：**新增全新人員**")

            with col_mode_btn:
                if selected_row_data:
                    if st.button("切換新增", key=f"btn_reset_add_{current_unit}", use_container_width=True):
                        st.session_state[ver_key] += 1
                        st.rerun()

            crew_options = get_all_crew_options(current_unit)
            options_dict: Dict[str, Dict[str, str]] = {"-- 或點此快選大表組員帶入 --": {"uid": "", "name": ""}}
            for item in crew_options:
                options_dict[item["label"]] = {"uid": item["uid"], "name": item["name"]}

            def sync_crew_to_inputs() -> None:
                sel = st.session_state.get(f"wl_quick_crew_select_{current_unit}", "")
                if sel in options_dict and options_dict[sel]["uid"]:
                    st.session_state[f"input_wl_uid_{current_unit}"] = options_dict[sel]["uid"]
                    st.session_state[f"input_wl_uname_{current_unit}"] = options_dict[sel]["name"]

            st.selectbox(
                "大表人員快選帶入",
                options=list(options_dict.keys()),
                key=f"wl_quick_crew_select_{current_unit}",
                on_change=sync_crew_to_inputs,
            )

            default_uid = str(selected_row_data["員編/帳號"]).upper() if selected_row_data else ""
            default_uname = str(selected_row_data["姓名"]) if selected_row_data else ""
            default_role = str(selected_row_data["身份權限"]) if selected_row_data else "TESTER"
            default_note = str(selected_row_data["備註"]) if selected_row_data else ""

            edit_uid = st.text_input(
                "員編 / 帳號 ID",
                value=default_uid,
                placeholder="例: A026048",
                key=f"input_wl_uid_{current_unit}",
                disabled=True if selected_row_data else False,
            )

            edit_uname = st.text_input(
                "姓名",
                value=default_uname,
                placeholder="例: 張小明",
                key=f"input_wl_uname_{current_unit}",
            )

            role_options = ["TESTER", "VIP_USER (全域通行)", "ADMIN"]
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

            col_b1, col_b2 = st.columns(2)

            with col_b1:
                btn_save_label = "更新權限" if selected_row_data else "新增人員"
                if st.button(
                    btn_save_label,
                    type="primary",
                    use_container_width=True,
                    key=f"btn_save_wl_{current_unit}",
                ):
                    target_uid = edit_uid.strip().upper()
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
                        "刪除此人員",
                        type="secondary",
                        use_container_width=True,
                        key=f"btn_del_wl_{current_unit}",
                    ):
                        target_uid = str(selected_row_data["員編/帳號"]).strip().upper()
                        if target_uid in whitelist_data:
                            del whitelist_data[target_uid]
                            save_whitelist(current_unit, whitelist_data)
                            log_activity(f"管理員移除 [{current_unit}] 組員權限：{target_uid}")
                            st.session_state[ver_key] += 1
                            st.success(f"已成功移除【{current_unit}】權限：{target_uid}")
                            st.rerun()
                else:
                    st.button("刪除人員", disabled=True, use_container_width=True)

    # ==================== Tab 4 ====================
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
                st.markdown("#### 🔐 通行授權碼設定")

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
                st.markdown("#### ⚠️ 換假嚴格過濾天數門檻")
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
                    value=str(
                        sys_config.get(
                            "announcement",
                            "目前為內部測試階段｜本頁面可聯繫後台管理者",
                        )
                    ),
                    height=100,
                )
                enable_notice = st.checkbox(
                    "顯示 Beta 測試環境告示橫幅",
                    value=bool(sys_config.get("enable_beta_notice", True)),
                )

            submit_sys_cfg = st.form_submit_button(
                "儲存全域系統設定", type="primary", use_container_width=True
            )

            if submit_sys_cfg:
                pwd_updates: List[str] = []
                has_error = False
                error_msgs: List[str] = []

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
                        " " + "；".join(error_msgs),
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
                        f"{msg_prefix}全域系統設定已成功更新並即刻生效！",
                    )
                    st.rerun()

    # ==================== Tab 5 ====================
    with tab5:
        st.markdown("### 📜 全站系統操作日誌與數據稽核儀表板")

        raw_logs = load_activity_logs()
        parsed_logs = [parse_structured_log(entry) for entry in raw_logs]
        df_logs = pd.DataFrame(parsed_logs) if parsed_logs else pd.DataFrame(columns=[
            "時間 (Timestamp)", "操作者/員編 (User)", "營運單位 (Unit)", "操作類別 (Category)", "詳細日誌紀錄 (Log Detail)"
        ])

        if not df_logs.empty and "詳細日誌紀錄 (Log Detail)" in df_logs.columns:
            df_logs["裝置 (Device)"] = df_logs["詳細日誌紀錄 (Log Detail)"].apply(extract_device_info)
        else:
            df_logs["裝置 (Device)"] = "Web 介面"

        if not df_logs.empty and "時間 (Timestamp)" in df_logs.columns:
            df_logs["時間_DT"] = pd.to_datetime(df_logs["時間 (Timestamp)"], errors="coerce")
            df_logs = df_logs.sort_values(by="時間_DT", ascending=False)

        today_str = date.today().strftime("%Y-%m-%d")
        total_log_count = len(df_logs)

        df_today = df_logs[df_logs["時間 (Timestamp)"].astype(str).str.startswith(today_str)] if not df_logs.empty else pd.DataFrame()
        today_logs_count = len(df_today)
        active_users_today = df_today["操作者/員編 (User)"].nunique() if not df_today.empty else 0

        mobile_count = sum(
            1 for dev in df_logs["裝置 (Device)"]
            if any(k in str(dev) for k in ["iPhone", "Android", "iPad"])
        ) if not df_logs.empty else 0

        mobile_pct_str = f"{(mobile_count / total_log_count * 100):.1f}%" if total_log_count > 0 else "0.0%"

        st.markdown(
            f"""
            <div style="display: flex; gap: 10px; margin-bottom: 16px;">
                <div class="admin-stat-card" style="flex: 1;">
                    <div class="stat-val">{total_log_count:,} <span style="font-size: 11px;">筆</span></div>
                    <div class="stat-lbl">歷史總日誌數</div>
                </div>
                <div class="admin-stat-card" style="flex: 1; border-color: rgba(52, 211, 153, 0.4);">
                    <div class="stat-val" style="color: #34D399;">{today_logs_count:,} <span style="font-size: 11px;">筆</span></div>
                    <div class="stat-lbl">今日操作筆數</div>
                </div>
                <div class="admin-stat-card" style="flex: 1; border-color: rgba(251, 191, 36, 0.4);">
                    <div class="stat-val" style="color: #FBBF24;">{active_users_today} <span style="font-size: 11px;">人</span></div>
                    <div class="stat-lbl">今日活躍人數</div>
                </div>
                <div class="admin-stat-card" style="flex: 1; border-color: rgba(192, 132, 252, 0.4);">
                    <div class="stat-val" style="color: #C084FC;">{mobile_pct_str}</div>
                    <div class="stat-lbl">行動裝置占比</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("🔍 展開 / 收合 日誌進階篩選條件", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)

            with f_col1:
                all_units = ["全站 / 全部單位"] + sorted([u for u in df_logs["營運單位 (Unit)"].unique() if u and u != "全站"]) if not df_logs.empty else ["全站 / 全部單位"]
                sel_unit = st.selectbox("依單位過濾", all_units, key="log_unit_filter")

            with f_col2:
                all_cats = ["全部分類", "換班快篩", "換假快篩", "月班表繪製", "管理員操作", "帳號登入", "問題與申請", "一般操作"]
                sel_cat = st.selectbox("依操作類別過濾", all_cats, key="log_cat_filter")

            with f_col3:
                all_devs = ["全部裝置"] + sorted(list(df_logs["裝置 (Device)"].unique())) if not df_logs.empty else ["全部裝置"]
                sel_dev = st.selectbox("依裝置 / 載具過濾", all_devs, key="log_dev_filter")

            f_col4, f_col5 = st.columns([1.2, 1.8])
            with f_col4:
                quick_time = st.radio("時間區間快速切換", ["全部", "今天", "近 3 天", "近 7 天"], horizontal=True, key="log_quick_time")
            with f_col5:
                log_kw = st.text_input("搜尋員編 / 車次 / 關鍵字", placeholder="例: A023300 或 換班...", key="log_search_kw").strip()

        df_filtered_logs = df_logs.copy()

        if not df_filtered_logs.empty:
            if sel_unit != "全站 / 全部單位":
                df_filtered_logs = df_filtered_logs[df_filtered_logs["營運單位 (Unit)"] == sel_unit]

            if sel_cat != "全部分類":
                df_filtered_logs = df_filtered_logs[df_filtered_logs["操作類別 (Category)"] == sel_cat]

            if sel_dev != "全部裝置":
                df_filtered_logs = df_filtered_logs[df_filtered_logs["裝置 (Device)"] == sel_dev]

            if quick_time == "今天":
                df_filtered_logs = df_filtered_logs[df_filtered_logs["時間 (Timestamp)"].astype(str).str.startswith(today_str)]
            elif quick_time == "近 3 天" and "時間_DT" in df_filtered_logs.columns:
                three_days_ago = datetime.now() - pd.Timedelta(days=3)
                df_filtered_logs = df_filtered_logs[df_filtered_logs["時間_DT"] >= three_days_ago]
            elif quick_time == "近 7 天" and "時間_DT" in df_filtered_logs.columns:
                seven_days_ago = datetime.now() - pd.Timedelta(days=7)
                df_filtered_logs = df_filtered_logs[df_filtered_logs["時間_DT"] >= seven_days_ago]

            if log_kw:
                pattern = re.escape(log_kw)
                df_filtered_logs = df_filtered_logs[
                    df_filtered_logs["操作者/員編 (User)"].astype(str).str.contains(pattern, case=False, na=False)
                    | df_filtered_logs["詳細日誌紀錄 (Log Detail)"].astype(str).str.contains(pattern, case=False, na=False)
                    | df_filtered_logs["時間 (Timestamp)"].astype(str).str.contains(pattern, case=False, na=False)
                ]

        col_log_header, col_log_actions = st.columns([3, 1])

        with col_log_header:
            st.markdown(f"##### 📋 查詢結果（共 {len(df_filtered_logs)} 筆紀錄）")

        with col_log_actions:
            if st.button("🗑️ 清空全站日誌", key="btn_clear_activity_logs", type="secondary", use_container_width=True):
                show_confirm_clear_logs_modal()

        if not df_filtered_logs.empty:
            display_cols = [
                "時間 (Timestamp)",
                "操作者/員編 (User)",
                "營運單位 (Unit)",
                "操作類別 (Category)",
                "詳細日誌紀錄 (Log Detail)",
            ]
            display_df = df_filtered_logs[display_cols]

            st.dataframe(
                display_df,
                use_container_width=True,
                height=420,
                hide_index=True,
                column_config={
                    "時間 (Timestamp)": st.column_config.TextColumn("時間 (Y-M-D H:M:S)", width="medium"),
                    "操作者/員編 (User)": st.column_config.TextColumn("操作者 / 員編", width="small"),
                    "營運單位 (Unit)": st.column_config.TextColumn("單位", width="small"),
                    "操作類別 (Category)": st.column_config.TextColumn("動作類別", width="medium"),
                    "詳細日誌紀錄 (Log Detail)": st.column_config.TextColumn("詳細日誌內容 (載具與操作細節)", width="large"),
                },
            )

            csv_data = display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 下載篩選出的日誌檔 (.CSV)",
                data=csv_data,
                file_name=f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="btn_download_logs_csv",
            )
        else:
            st.info("目前尚無符合過濾條件的系統操作日誌紀錄。")

        st.markdown("---")

        st.markdown("#### 📦 一鍵備份全站數據與設定檔")
        st.caption("備份內容包含：`data/` 底下所有 Excel 大表、日誌檔 `activity_log.csv` / `activity.log`、白名單 `whitelist.json` 與系統設定檔。")

        zip_buf = create_backup_zip()
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "💾 打包下載全站備份檔 (.ZIP)",
            data=zip_buf,
            file_name=f"system_backup_{now_str}.zip",
            mime="application/zip",
            type="primary",
            key="btn_download_backup",
        )

    # ==================== Tab 6 ====================
    with tab6:
        st.markdown("### 🎫 工單與問題回報管理")

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
                    <div class="admin-stat-card" style="flex: 1; border-color: rgba(244, 63, 94, 0.5);">
                        <div class="stat-val" style="color: #F43F5E;">{cnt_pending} <span style="font-size: 11px;">筆</span></div>
                        <div class="stat-lbl">待處理工單</div>
                    </div>
                    <div class="admin-stat-card" style="flex: 1; border-color: rgba(245, 158, 11, 0.5);">
                        <div class="stat-val" style="color: #FBBF24;">{cnt_processing} <span style="font-size: 11px;">筆</span></div>
                        <div class="stat-lbl">處理中工單</div>
                    </div>
                    <div class="admin-stat-card" style="flex: 1; border-color: rgba(52, 211, 153, 0.5);">
                        <div class="stat-val" style="color: #34D399;">{cnt_done} <span style="font-size: 11px;">筆</span></div>
                        <div class="stat-lbl">已完成工單</div>
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

            st.caption(f"列表顯示共 **{len(filtered_tickets)}** 筆工單：")

            for idx, t in enumerate(filtered_tickets):
                ticket_id = str(t.get("處理編號", "未知單號"))
                curr_status = str(t.get("狀態", "待處理"))
                category = str(t.get("類別", "一般"))
                reporter = str(t.get("回報者", "未知"))
                time_str = str(t.get("時間", ""))
                unit = str(t.get("單位", ""))

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
                        st.markdown("附加螢幕截圖：")
                        if st.button(f"點此查看/下載截圖附件", key=f"btn_view_img_{ticket_id}_{idx}"):
                            if callable(view_feedback_img_modal):
                                view_feedback_img_modal(img_path, ticket_id, reporter)
                            else:
                                st.image(img_path, caption=f"工單 {ticket_id} 截圖附件 ({reporter})")

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
                            value=str(t.get("管理員回覆", "")),
                            key=f"reply_input_{ticket_id}_{idx}",
                            placeholder="例如：已修正程式...",
                        )

                    cb1, cb2 = st.columns(2)
                    with cb1:
                        if st.button("更新工單狀態與備註", key=f"btn_update_t_{ticket_id}_{idx}", type="primary", use_container_width=True):
                            t["狀態"] = new_status
                            t["管理員回覆"] = new_reply
                            save_feedback_ticket(t)
                            log_activity(f"管理員更新工單 [{ticket_id}] 狀態為：{new_status}")
                            st.success(f"工單 `{ticket_id}` 狀態已成功更新！")
                            st.rerun()

                    with cb2:
                        if st.button("刪除此工單", key=f"btn_del_t_{ticket_id}_{idx}", use_container_width=True):
                            txt_p = t.get("_txt_path")
                            if txt_p and os.path.exists(txt_p):
                                os.remove(txt_p)
                            img_p = t.get("_img_path")
                            if img_p and os.path.exists(img_p):
                                os.remove(img_p)
                            log_activity(f"管理員刪除工單 [{ticket_id}]")
                            st.success(f"已成功刪除工單 `{ticket_id}`！")
                            st.rerun()


render_admin_home = render_admin_panel
