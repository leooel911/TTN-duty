import streamlit as st
import os
import re
import io
import csv
from datetime import date, timedelta, datetime
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

# 【每個月更新這裡就好】
DUTY_DATA = """
(這裡貼上你每個月的大班表內容)
"""

# ... (其他的函數保持不變) ...

# 調整介面：只留名字輸入框，刪除文字貼上區
st.title("🚆 TTN 勤務班表產生器")
target_name = st.text_input("輸入你的名字", value="江立夫")

if st.button("立即生成個人班表圖片"):
    if not DUTY_DATA.strip() or "(這裡貼上)" in DUTY_DATA:
        st.error("請通知管理員更新班表資料！")
    else:
        try:
            # 這裡把原本的 raw_text_input 改成讀取上面的 DUTY_DATA 變數
            start_dt, dates, emp_data, file_date_str = parse_flexible_employees(DUTY_DATA, target_name)
            # ... (後續繪圖邏輯與上面完全一樣) ...
