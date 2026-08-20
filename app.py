import streamlit as st
import os
import re
import io
import pandas as pd
from datetime import date, timedelta, datetime, timezone
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

matplotlib.use('Agg')

st.set_page_config(page_title="TTN Shift Producer", page_icon="700st.png", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 3rem 1rem !important; }
    .header-container { display: flex; justify-content: space-between; align-items: baseline; width: 100%; margin-bottom: 1rem; }
    .main-title { color: #F8FAFC !important; font-size: 26px; font-weight: 800; letter-spacing: 0.5px; margin: 0; }
    .edition-badge { color: #64748B !important; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); }
    .telemetry-title { color: #94A3B8 !important; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .telemetry-value { color: #F8FAFC !important; font-size: 18px; font-weight: 700; font-family: monospace; }
    
    /* 優化後的結果卡片樣式 */
    .result-card {
        background: #1E293B;
        border-left: 4px solid #3B82F6;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        color: #F8FAFC;
    }
    .time-row { font-size: 18px; font-weight: 700; color: #60A5FA; margin-bottom: 8px; font-family: monospace; }
    .name-row { font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #E2E8F0; }
    .train-row { 
        display: inline-block;
        background: #0F172A; 
        padding: 4px 12px; 
        border-radius: 6px; 
        font-weight: 700; 
        color: #38BDF8; 
        border: 1px solid #334155;
    }
    .stRadio > div { background-color: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; }
    .stRadio label { font-size: 15px !important; font-weight: 600 !important; color: #F8FAFC !important; }
    .stTextInput input { font-size: 18px !important; padding: 14px 16px !important; border-radius: 10px !important; background-color: #1E293B !important; color: #F8FAFC !important; border: 1px solid #475569 !important; }
    div.stButton > button { font-size: 18px !important; font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important; color: #ffffff !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5) !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# (其餘邏輯函數維持不變)
# ... [保留原有的功能函數與邏輯] ...

# 修正篩選結果的顯示區塊
elif app_mode == "組員動態時段篩選（尋找換班協調專用・Beta測試版）":
    # ... [前段檢索代碼維持不變] ...
    if st.button("開始區間檢索符合條件人員"):
        # ... [搜尋邏輯維持不變] ...
        if search_results:
            st.markdown(f"### 檢索結果 (共 {len(search_results)} 筆)")
            for r in search_results:
                st.markdown(f"""
                <div class="result-card">
                    <div class="time-row">{r['Sign-In']} ➔ {r['收工時間']}</div>
                    <div class="name-row">{r['姓名']} <span style="color:#94A3B8; font-size:14px;">({r['員編']})</span></div>
                    <div class="train-row">班別：{r['車次'] if r['車次'] else '無記錄'}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("在指定的日期與 Sign-In 區間內，沒有找到符合條件的人員")
