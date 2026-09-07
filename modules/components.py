import base64
import io
import os
import re
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from config import LEAVE_CODES, UNITS
from modules.drawing import render_schedule_figure
from modules.services import process_file_data
from modules.utils import safe_read_excel


def render_zoomable_image(image_bytes: io.BytesIO) -> None:
    """渲染支援長按、雙擊放大與拖曳的圖片元件 (HTML/CSS)"""
    encoded = base64.b64encode(image_bytes.getvalue()).decode()
    html_code = f"""
    <style>
    .img-zoom-container {{
        width: 100%;
        overflow-x: auto;
        overflow-y: hidden;
        text-align: center;
        background-color: #0F172A;
        border-radius: 10px;
        padding: 8px;
        border: 1px solid rgba(56, 189, 248, 0.2);
    }}
    .img-zoom-container img {{
        max-width: 100%;
        height: auto;
        border-radius: 6px;
        transition: transform 0.2s ease;
        cursor: zoom-in;
    }}
    .img-zoom-container img:active {{
        transform: scale(1.5);
        cursor: grabbing;
    }}
    </style>
    <div class="img-zoom-container">
        <img src="data:image/png;base64,{encoded}" alt="Personal Schedule" />
    </div>
    """
    st.components.v1.html(html_code, height=520, scrolling=True)


def show_holiday_notice(holidays: List[str], week_range_str: str = "") -> None:
    """顯示當週節假日與國定假日提醒橫幅"""
    if holidays:
        holiday_list_str = "、".join(holidays)
        st.markdown(
            f"""
            <div style="background: rgba(245, 158, 11, 0.15); border: 1.5px solid #F59E0B; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 13px; color: #FDE68A;">
                <strong>⚠️ 當週包含國定假日：</strong>{holiday_list_str}<br/>
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
    """跳出對話框 (Dialog Modal) 顯示特定組員的完整月班表圖片"""
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
            render_zoomable_image(buf)
            
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
    """跳出對話框 (Dialog Modal) 檢視工單圖片附件"""
    st.markdown(f"### 工單單號：`{ticket_id}` (回報者: {reporter})")
    if os.path.exists(img_path):
        st.image(img_path, use_column_width=True)
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
