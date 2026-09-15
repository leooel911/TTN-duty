import base64
import io
import os
import re
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from config import FEEDBACK_IMG_DIR, LEAVE_CODES, UNITS
from modules.drawing import render_schedule_figure
from modules.utils import log_activity, safe_read_excel, send_admin_email


def _convert_to_b64_url(image_bytes: Any) -> str:
    if hasattr(image_bytes, "getvalue"):
        raw_bytes = image_bytes.getvalue()
    elif isinstance(image_bytes, bytes):
        raw_bytes = image_bytes
    elif isinstance(image_bytes, str) and os.path.exists(image_bytes):
        try:
            with open(image_bytes, "rb") as f:
                raw_bytes = f.read()
        except Exception:
            raw_bytes = b""
    else:
        raw_bytes = b""

    if not raw_bytes:
        return ""
    b64_str = base64.b64encode(raw_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"


def render_zoomable_image(image_bytes: Any, height: int = 380) -> None:
    img_data_url = _convert_to_b64_url(image_bytes)

    st.markdown(
        """
        <style>
        [data-testid="stImage"] button,
        button[title="View fullscreen"],
        [data-testid="StyledFullScreenButton"] {
            display: none !important;
        }
        div[data-testid="stCustomComponentV1"] {
            margin-bottom: 2px !important;
            margin-top: -4px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not img_data_url:
        st.warning("班表影像載入失敗，無法生成預覽。")
        return

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            html, body {{
                margin: 0 !important; padding: 0 !important;
                background: transparent;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
                overflow: hidden;
            }}
            .viewer-wrapper {{ width: 100%; text-align: center; padding: 0 0 4px 0; margin: 0; }}
            .img-container {{ width: 100%; cursor: zoom-in; position: relative; display: block; }}
            .img-container img {{
                width: 100%; height: auto; max-width: 100%;
                border-radius: 10px; border: 1.5px solid rgba(56, 189, 248, 0.4);
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); display: block;
            }}
            .zoom-trigger-btn {{
                width: 100%; margin-top: 6px; padding: 10px 14px;
                background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
                border: 1.5px solid rgba(56, 189, 248, 0.5); border-radius: 8px;
                color: #38BDF8; font-size: 13.5px; font-weight: 700; cursor: pointer;
            }}
            .hint-text {{ font-size: 12px; color: #94A3B8; font-weight: 500; margin-top: 8px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="viewer-wrapper" id="main-wrapper">
            <div class="img-container" id="img-box">
                <img id="target-schedule-img" src="{img_data_url}" alt="班表圖片">
            </div>
            <button class="zoom-trigger-btn" id="btn-open-viewer">點擊可縮放此班表</button>
            <div class="hint-text">提示：手機使用者可長按圖片儲存至相簿</div>
        </div>
        <script>
            function sendHeight() {{
                const wrapper = document.getElementById('main-wrapper');
                if (wrapper) {{
                    window.parent.postMessage({{ type: "streamlit:setFrameHeight", height: wrapper.offsetHeight + 14 }}, "*");
                }}
            }}
            document.addEventListener("DOMContentLoaded", function() {{
                const image = document.getElementById('target-schedule-img');
                const triggerBtn = document.getElementById('btn-open-viewer');
                if (image.complete) sendHeight(); else image.onload = sendHeight;
                setTimeout(sendHeight, 150);
                const viewer = new Viewer(image, {{ inline: false, navbar: false, title: false, toolbar: {{ zoomIn: 1, zoomOut: 1, oneToOne: 1, reset: 1 }}, tooltip: true, movable: true, zoomable: true, pinchZoom: true }});
                triggerBtn.addEventListener('click', () => viewer.show());
            }});
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height, scrolling=False)


@st.dialog("班表全螢幕放大檢視", width="large")
def show_zoom_schedule_modal(image_bytes: Any) -> None:
    render_zoomable_image(image_bytes, height=360)


def show_holiday_notice(holidays: List[str], week_range_str: str = "") -> None:
    if holidays:
        holiday_list_str = "、".join(holidays)
        st.markdown(
            f"""
            <div style="background: rgba(245, 158, 11, 0.15); border: 1.5px solid #F59E0B; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 13px; color: #FDE68A;">
                <strong>當週包含國定假日：</strong>{holiday_list_str}<br/>
                <span style="font-size: 11px; color: #CBD5E1;">請注意：換班 / 換假時，若涉及國定假日，請務必遵循公司規定辦理！</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


@st.dialog("檢視問題回報截圖", width="large")
def view_feedback_img_modal(img_path: str, ticket_id: str, reporter: str) -> None:
    st.markdown(f"### 工單單號：`{ticket_id}` (回報者: {reporter})")
    if os.path.exists(img_path):
        st.image(img_path, use_container_width=True)
        with open(img_path, "rb") as file:
            st.download_button("下載此截圖附件", data=file, file_name=os.path.basename(img_path), mime="image/png", use_container_width=True)
    else:
        st.error("找不到該截圖檔案，可能已被移除。")


def render_feedback_hub_popover(unit_label: str = "TTN", user_id: str = "", is_admin: bool = False) -> None:
    """使用 st.popover 呈現精緻的浮動互動中心，完美結合提交與查詢且絕不重複彈出"""
    with st.popover("系統問題回報與進度查詢中心", use_container_width=True):
        tab_submit, tab_query = st.tabs(["📝 提交新回報", "🔍 查詢我的回報進度"])
        
        with tab_submit:
            st.markdown(f"#### 系統問題與建議回報 [{unit_label}]")
            with st.form(key="feedback_form_popover", clear_on_submit=True):
                fb_category = st.selectbox("問題 / 建議類型", ["系統 Bug 回報", "排班資料疑義", "功能改善建議", "其他"], key="fb_pop_cat")
                fb_reporter = st.text_input("回報者員編 / 姓名", value=user_id if user_id else "", key="fb_pop_rep")
                fb_desc = st.text_area("詳細說明內容", height=120, key="fb_pop_desc")
                uploaded_img = st.file_uploader("上傳問題畫面截圖 (選填)", type=["png", "jpg", "jpeg"], key="fb_pop_img")
                submit_fb = st.form_submit_button("確認提交回報", type="primary", use_container_width=True)

            if submit_fb:
                if not fb_desc.strip():
                    st.warning("請填寫詳細說明內容！")
                else:
                    try:
                        os.makedirs(FEEDBACK_IMG_DIR, exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        ticket_id = f"FB-{timestamp}"
                        if uploaded_img is not None:
                            ext = os.path.splitext(uploaded_img.name)[1]
                            with open(os.path.join(FEEDBACK_IMG_DIR, f"{ticket_id}{ext}"), "wb") as f:
                                f.write(uploaded_img.getbuffer())

                        content = (
                            f"處理編號: {ticket_id}\n狀態: 待處理\n類別: {fb_category}\n單位: {unit_label}\n"
                            f"回報者: {fb_reporter.strip() or '未提供'}\n時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"管理員回覆: 尚無回覆\n詳細說明:\n{fb_desc.strip()}"
                        )
                        with open(os.path.join(FEEDBACK_IMG_DIR, f"{ticket_id}.txt"), "w", encoding="utf-8") as f:
                            f.write(content)
                        
                        log_activity("提交問題回報工單", f"單位:{unit_label} | 單號:{ticket_id}")

                        email_success = True
                        try:
                            email_subject = f"【新工單與問題回報】單號: {ticket_id}"
                            email_content = f"系統收到來自營運單位【{unit_label}】的新問題回報：\n\n----------------------------------------\n{content}\n----------------------------------------\n\n請管理員盡快登入後台處理！"
                            send_admin_email(email_subject, email_content)
                        except Exception as mail_err:
                            email_success = False
                            print(f"工單通知信發送失敗: {mail_err}")

                        st.toast(f"回報成功！工單編號：{ticket_id}")
                        if not email_success:
                            st.toast("管理員通知發送失敗")
                        st.rerun()
                    except Exception as e:
                        st.error(f"提交失敗：{e}")

        with tab_query:
            st.markdown("#### 歷史回報與處理進度查詢")
            if not is_admin:
                st.markdown(f"目前登入身分：`{user_id}`（僅顯示與您相關的回報紀錄）")
            else:
                st.markdown("管理員檢視模式：可檢視全體回報紀錄")

            if not os.path.exists(FEEDBACK_IMG_DIR):
                st.info("目前尚無任何回報紀錄。")
                return
                
            txt_files = [f for f in os.listdir(FEEDBACK_IMG_DIR) if f.endswith(".txt")]
            if not txt_files:
                st.info("目前尚無任何回報紀錄。")
                return
                
            tickets = []
            for file_name in sorted(txt_files, reverse=True):
                file_path = os.path.join(FEEDBACK_IMG_DIR, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    ticket_info = {"raw_content": content, "filename": file_name}
                    for line in content.split("\n"):
                        if ":" in line:
                            k, v = line.split(":", 1)
                            ticket_info[k.strip()] = v.strip()
                    tickets.append(ticket_info)
                except Exception:
                    continue
            
            if not is_admin:
                u_clean = user_id.strip().upper()
                filtered_tickets = [
                    t for t in tickets 
                    if u_clean in t.get("回報者", "").upper()
                ]
            else:
                search_query = st.text_input("管理員檢索 (輸入員編或單號)", key="admin_ticket_search_popover")
                if search_query.strip():
                    q = search_query.strip().upper()
                    filtered_tickets = [
                        t for t in tickets 
                        if q in t.get("處理編號", "").upper() or q in t.get("回報者", "").upper()
                    ]
                else:
                    filtered_tickets = tickets

            if not filtered_tickets:
                st.warning("找不到符合條件的工單紀錄。")
            else:
                st.markdown(f"共找到 **{len(filtered_tickets)}** 筆紀錄：")
                for t in filtered_tickets:
                    ticket_id = t.get("處理編號", "未知單號")
                    status = t.get("狀態", "待處理")
                    category = t.get("類別", "一般")
                    reporter = t.get("回報者", "未提供")
                    time_str = t.get("時間", "未知時間")
                    admin_reply = t.get("管理員回覆", "尚無回覆")
                    
                    with st.expander(f"單號: {ticket_id} | 狀態: {status} | 類別: {category} ({time_str})"):
                        st.markdown(f"**回報者**：{reporter}")
                        st.markdown(f"**提交時間**：{time_str}")
                        st.markdown(f"**目前狀態**：{status}")
                        st.markdown(f"**管理員回覆**：\n> {admin_reply}")
                        
                        base_id = ticket_id.split()[0]
                        img_path_found = None
                        for ext in [".png", ".jpg", ".jpeg"]:
                            p = os.path.join(FEEDBACK_IMG_DIR, f"{base_id}{ext}")
                            if os.path.exists(p):
                                img_path_found = p
                                break
                        if img_path_found:
                            if st.button("檢視上傳截圖附件", key=f"btn_view_img_pop_{ticket_id}"):
                                view_feedback_img_modal(img_path_found, ticket_id, reporter)
