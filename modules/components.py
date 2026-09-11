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
from modules.services import process_file_data
from modules.utils import log_activity, safe_read_excel


def _convert_to_b64_url(image_bytes: Any) -> str:
    """內部輔助工具：將各種影像格式（BytesIO / bytes / 檔案路徑）統一轉換為 Base64 Data URL"""
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


def render_zoomable_image(image_bytes: Any, height: int = 340) -> None:
    """
    主頁面班表圖片呈現元件（整合 Viewer.js 手勢燈箱）
    優化點：
    1. 支援行動端/手機雙指縮放 (Pinch-to-zoom)、雙擊放大與拖曳平移。
    2. 整合 JS ResizeObserver 與 postMessage("streamlit:setFrameHeight")，根據內容實測高度自動摺疊，徹底消除黑底大空隙。
    3. 自動隱藏 Streamlit 原生全螢幕浮動遮罩。
    """
    img_data_url = _convert_to_b64_url(image_bytes)

    # 1. 隱藏 Streamlit 原生全螢幕浮動按鈕，並縮減 iframe 外圍 Margin
    st.markdown(
        """
        <style>
        [data-testid="stImage"] button,
        button[title="View fullscreen"],
        [data-testid="StyledFullScreenButton"] {
            display: none !important;
        }
        div[data-testid="stCustomComponentV1"] {
            margin-bottom: -12px !important;
            margin-top: -6px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not img_data_url:
        st.warning("⚠️ 班表影像載入失敗，無法生成預覽。")
        return

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
        <!-- 引入 Viewer.js CSS & JS CDN -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.js"></script>
        <style>
            * {{
                box-sizing: border-box;
            }}
            html, body {{
                margin: 0 !important;
                padding: 0 !important;
                background: transparent;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
                overflow: hidden;
            }}
            .viewer-wrapper {{
                width: 100%;
                text-align: center;
                padding: 0;
                margin: 0;
            }}
            .img-container {{
                width: 100%;
                cursor: zoom-in;
                position: relative;
                display: block;
            }}
            .img-container img {{
                width: 100%;
                height: auto;
                max-width: 100%;
                border-radius: 10px;
                border: 1.5px solid rgba(56, 189, 248, 0.4);
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
                display: block;
                transition: border-color 0.2s ease;
            }}
            .img-container img:hover {{
                border-color: #38BDF8;
            }}
            .zoom-trigger-btn {{
                width: 100%;
                margin-top: 6px;
                padding: 10px 14px;
                background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
                border: 1.5px solid rgba(56, 189, 248, 0.5);
                border-radius: 8px;
                color: #38BDF8;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.5px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                transition: all 0.2s ease;
            }}
            .zoom-trigger-btn:hover {{
                background: rgba(56, 189, 248, 0.15);
                border-color: #38BDF8;
                box-shadow: 0 0 12px rgba(56, 189, 248, 0.3);
            }}
        </style>
    </head>
    <body>
        <div class="viewer-wrapper" id="main-wrapper">
            <div class="img-container" id="img-box">
                <img id="target-schedule-img" src="{img_data_url}" alt="班表圖片">
            </div>
            <button class="zoom-trigger-btn" id="btn-open-viewer">
                點擊可縮放此班表
            </button>
        </div>

        <script>
            // 自動向 Streamlit 匯報渲染內容的實際高度，實現動態自適應
            function sendHeight() {{
                const wrapper = document.getElementById('main-wrapper');
                if (wrapper) {{
                    const actualHeight = wrapper.offsetHeight + 4;
                    window.parent.postMessage({{
                        type: "streamlit:setFrameHeight",
                        height: actualHeight
                    }}, "*");
                }}
            }}

            document.addEventListener("DOMContentLoaded", function() {{
                const image = document.getElementById('target-schedule-img');
                const triggerBtn = document.getElementById('btn-open-viewer');

                // 圖片載入各階段觸發高度校準
                if (image.complete) {{
                    sendHeight();
                }} else {{
                    image.onload = sendHeight;
                }}
                setTimeout(sendHeight, 150);
                setTimeout(sendHeight, 500);

                // 註冊 ResizeObserver 確保螢幕旋轉或視窗改變時高度即時更正
                if (window.ResizeObserver) {{
                    const ro = new ResizeObserver(() => sendHeight());
                    ro.observe(document.body);
                }}

                // 初始化 Viewer.js 手勢燈箱
                const viewer = new Viewer(image, {{
                    inline: false,          // 點擊後跳出 Modal 全螢幕燈箱
                    navbar: false,          // 隱藏縮圖清單
                    title: false,           // 隱藏檔名檔頭
                    toolbar: {{
                        zoomIn: 1,
                        zoomOut: 1,
                        oneToOne: 1,
                        reset: 1,
                    }},
                    tooltip: true,
                    movable: true,          // 允許手勢拖曳平移
                    zoomable: true,         // 允許縮放
                    rotatable: false,       // 停用不必要的旋轉
                    scalable: false,
                    transition: true,
                    backdrop: true,
                    pinchZoom: true,        // 啟用行動端雙指 Pinch 縮放
                    slideOnTouch: false
                }});

                // 點擊圖片或下方按鈕皆可開啟燈箱
                triggerBtn.addEventListener('click', function() {{
                    viewer.show();
                }});
            }});
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height, scrolling=False)


@st.dialog("班表全螢幕放大檢視", width="large")
def show_zoom_schedule_modal(image_bytes: Any) -> None:
    """對話框彈窗：亦採用 Viewer.js 強化手勢操作體驗"""
    render_zoomable_image(image_bytes, height=360)


def show_holiday_notice(holidays: List[str], week_range_str: str = "") -> None:
    """顯示當週節假日與國定假日提醒橫幅"""
    if holidays:
        holiday_list_str = "、".join(holidays)
        st.markdown(
            f"""
            <div style="background: rgba(245, 158, 11, 0.15); border: 1.5px solid #F59E0B; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 13px; color: #FDE68A;">
                <strong>當週包含國定假日：</strong>{holiday_list_str}<br/>
                <span style="font-size: 11px; color: #CBD5E1;">請注意：換班 / 換假時，若涉及國定假日或雙倍薪當週，請務必遵循公司規定辦理！</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


@st.dialog("組員詳細月班表圖檔", width="large")
def show_crew_schedule_modal(
    emp_id: str,
    unit_label: str = "TTN",
    badge_title: str = "Crew Schedule | C.L.F",
) -> None:
    """跳出對話框顯示特定組員的完整月班表圖片"""
    st.markdown(f"### 查詢組員員編：`{emp_id}` ({unit_label})")

    with st.spinner(f"正在擷取並繪製組員【{emp_id}】的月班表..."):
        try:
            start_dt, dates, parsed_id, emp_name, cells = process_file_data(emp_id)
            buf = render_schedule_figure(
                start_dt,
                dates,
                parsed_id,
                emp_name,
                cells,
                unit_label,
                badge_title=badge_title,
            )
            st.success(f"已成功載入【{emp_name} ({parsed_id})】的完整班表")
            render_zoomable_image(buf, height=360)

            st.download_button(
                label=f"下載 {emp_name} 月班表圖檔",
                data=buf,
                file_name=f"{unit_label}_班表_{emp_name}_{parsed_id}.png",
                mime="image/png",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"無法繪製該組員班表：{e}")


@st.dialog("檢視問題回報截圖", width="large")
def view_feedback_img_modal(img_path: str, ticket_id: str, reporter: str) -> None:
    """跳出對話框檢視工單圖片附件"""
    st.markdown(f"### 工單單號：`{ticket_id}` (回報者: {reporter})")
    if os.path.exists(img_path):
        st.image(img_path, use_container_width=True)
        with open(img_path, "rb") as file:
            st.download_button(
                label="下載此截圖附件",
                data=file,
                file_name=os.path.basename(img_path),
                mime="image/png",
                use_container_width=True,
            )
    else:
        st.error("找不到該截圖檔案，可能已被移除。")


@st.dialog("系統問題與建議回報", width="large")
def show_feedback_modal(unit_label: str = "TTN", user_id: str = "") -> None:
    """跳出問題與建議回報對話框"""
    st.markdown(f"### 系統問題與建議回報 [{unit_label}]")
    st.caption("若你在使用過程中遇到系統 Bug、排班顯示錯誤或有改善建議，歡迎填寫以下表單。")

    with st.form(key="feedback_form_modal", clear_on_submit=True):
        fb_category = st.selectbox(
            "問題 / 建議類型",
            ["系統 Bug 回報", "排班資料疑義", "功能改善建議", "其他"],
            key="fb_modal_category",
        )

        fb_reporter = st.text_input(
            "回報者員編 / 姓名",
            value=user_id if user_id else "",
            placeholder="例: A023300 波莉",
            key="fb_modal_reporter",
        )

        fb_desc = st.text_area(
            "詳細說明內容",
            placeholder="請詳細描述您遇到的問題或希望改善的功能...",
            height=120,
            key="fb_modal_desc",
        )

        uploaded_img = st.file_uploader(
            "上傳問題畫面截圖 (選填，支援 png, jpg)",
            type=["png", "jpg", "jpeg"],
            key="fb_modal_img",
        )

        submit_fb = st.form_submit_button(
            "確認提交回報", type="primary", use_container_width=True
        )

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
                    img_filename = f"{ticket_id}{ext}"
                    img_save_path = os.path.join(FEEDBACK_IMG_DIR, img_filename)
                    with open(img_save_path, "wb") as f:
                        f.write(uploaded_img.getbuffer())

                txt_filename = f"{ticket_id}.txt"
                txt_save_path = os.path.join(FEEDBACK_IMG_DIR, txt_filename)

                content = (
                    f"處理編號: {ticket_id}\n"
                    f"狀態: 待處理\n"
                    f"類別: {fb_category}\n"
                    f"單位: {unit_label}\n"
                    f"回報者: {fb_reporter.strip() or '未提供'}\n"
                    f"時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"管理員回覆: 尚無回覆\n"
                    f"詳細說明:\n{fb_desc.strip()}"
                )

                with open(txt_save_path, "w", encoding="utf-8") as f:
                    f.write(content)

                log_activity(
                    "提交問題回報工單",
                    f"單位:{unit_label} | 單號:{ticket_id} | 類別:{fb_category}",
                )
                st.success(f"回報成功！工單編號：`{ticket_id}`，感謝您的寶貴建議！")
                st.rerun()
            except Exception as e:
                st.error(f"提交失敗，請再試一次：{e}")
