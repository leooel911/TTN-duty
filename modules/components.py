import base64
import os
import re
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
import streamlit as st
from config import FEEDBACK_IMG_DIR, LEAVE_CODES, UNITS
from modules.drawing import render_schedule_figure
from modules.services import process_file_data
from modules.utils import log_activity, safe_read_excel


def render_zoomable_modal_image(image_bytes: Any) -> None:
    """彈窗專用：無按鈕、支援手機雙指捏合放大與單指拖曳的純手勢圖片元件"""
    if hasattr(image_bytes, "getvalue"):
        raw_bytes = image_bytes.getvalue()
    elif isinstance(image_bytes, bytes):
        raw_bytes = image_bytes
    else:
        raw_bytes = b""

    encoded = base64.b64encode(raw_bytes).decode("utf-8")

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <script src="https://cdn.jsdelivr.net/npm/@panzoom/panzoom@4.5.1/dist/panzoom.min.js"></script>
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      html, body {{
        width: 100%;
        height: 100%;
        margin: 0;
        padding: 0;
        background-color: transparent;
        overflow: hidden;
      }}
      .modal-viewport {{
        width: 100%;
        height: 60vh;
        background: #020617;
        border-radius: 8px;
        overflow: hidden;
        position: relative;
        touch-action: none;
        cursor: grab;
        display: flex;
        justify-content: center;
        align-items: center;
        border: 1px solid rgba(56, 189, 248, 0.3);
      }}
      .modal-viewport:active {{
        cursor: grabbing;
      }}
      .modal-img {{
        width: 100%;
        height: auto;
        display: block;
        user-select: none;
        -webkit-user-drag: none;
      }}
    </style>
    </head>
    <body>

    <div class="modal-viewport" id="panzoomArea">
      <img id="scheduleImg" src="data:image/png;base64,{encoded}" alt="Schedule Preview" class="modal-img" />
    </div>

    <script>
      let panzoom = null;
      const elem = document.getElementById('scheduleImg');

      function initPanzoom() {{
        if (!panzoom) {{
          panzoom = Panzoom(elem, {{
            maxScale: 6,
            minScale: 1,
            startScale: 1,
            contain: 'outside'
          }});
          const parent = document.getElementById('panzoomArea');
          parent.addEventListener('wheel', panzoom.zoomWithWheel);
        }}
      }}

      if (elem.complete) {{
        initPanzoom();
      }} else {{
        elem.onload = initPanzoom;
      }}
    </script>
    </body>
    </html>
    """
    st.components.v1.html(html_code, height=420, scrolling=False, key="modal_panzoom_canvas")


@st.dialog("班表全螢幕放大檢視", width="large")
def show_zoom_schedule_modal(image_bytes: Any) -> None:
    """彈窗視窗：呈現純手勢縮放班表"""
    st.caption("💡 提示：手機端支援雙指捏合放大與單指滑動拖曳（亦可點擊右上角 ✕ 關閉）")
    render_zoomable_modal_image(image_bytes)
    
    if st.button("關閉全螢幕視窗", use_container_width=True, key="close_modal_inner_btn"):
        st.session_state["show_zoom_modal"] = False
        st.rerun()


def render_zoomable_image(image_bytes: Any) -> None:
    """主頁面預覽：完整展示原圖，徹底隱藏 Streamlit 原生全螢幕按鈕，並精簡點擊放大觸發器"""
    if hasattr(image_bytes, "getvalue"):
        raw_bytes = image_bytes.getvalue()
    elif isinstance(image_bytes, bytes):
        raw_bytes = image_bytes
    else:
        raw_bytes = b""

    # 強制隱藏 Streamlit 原生圖片 hover 時右上角浮現的放大與全螢幕按鈕
    st.markdown(
        """
        <style>
        [data-testid="stImage"] button,
        button[title="View fullscreen"],
        [data-testid="StyledFullScreenButton"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 1. 完整無裁切呈現預覽圖
    st.image(raw_bytes, use_container_width=True)

    # 2. 點擊觸發按鈕，透過 Session State 持久化狀態
    if st.button("放大點擊檢視全螢幕班表", type="secondary", use_container_width=True, key="trigger_zoom_modal"):
        st.session_state["show_zoom_modal"] = True
        st.rerun()

    # 3. 只要 Session State 標記為 True，就穩定維持彈窗開啟
    if st.session_state.get("show_zoom_modal", False):
        show_zoom_schedule_modal(raw_bytes)


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
            render_zoomable_modal_image(buf)

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
