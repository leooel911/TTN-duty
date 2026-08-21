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
import time

matplotlib.use('Agg')

st.set_page_config(page_title="TTN Shift Producer", page_icon="700st.png", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0B0F19 !important; color: #F8FAFC !important; }
    .block-container { padding: 3rem 1rem !important; }
    .header-container { display: flex; justify-content: space-between; align-items: baseline; width: 100%; margin-bottom: 1rem; }
    .main-title { color: #F8FAFC !important; font-size: 26px; font-weight: 800; letter-spacing: 0.5px; margin: 0; }
    .edition-badge { color: #64748B !important; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
    .telemetry-card { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4); position: relative; overflow: hidden; }
    .telemetry-card::before { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: #3B82F6; }
    .telemetry-title { color: #94A3B8 !important; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
    .telemetry-value { color: #F8FAFC !important; font-size: 18px; font-weight: 700; font-family: monospace; }
    .telemetry-sub { margin-top: 10px; padding-top: 8px; border-top: 1px solid #334155; font-size: 13px; color: #94A3B8; }
    .maint-sub { border-top: 1px solid #991B1B !important; color: #FECACA !important; }
    
    .section-header-box { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); border: 1px solid #334155; border-left: 5px solid #3B82F6; border-radius: 10px; padding: 16px 20px; margin-top: 20px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .section-title { color: #F8FAFC; font-size: 20px; font-weight: 700; letter-spacing: 0.5px; margin: 0; }
    .section-subtitle { color: #94A3B8; font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

    .date-banner { background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%); border-left: 5px solid #60A5FA; color: #FFFFFF; font-size: 15px; font-weight: 800; padding: 8px 14px; border-radius: 8px; margin-top: 24px; margin-bottom: 10px; letter-spacing: 1px; text-transform: uppercase; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }

    .compact-card { background: #1E293B; border: 1px solid #334155; border-left: 3px solid #3B82F6; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; color: #F8FAFC; transition: all 0.25s ease; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
    .compact-card:hover { border-color: #38BDF8; box-shadow: 0 0 16px rgba(56, 189, 248, 0.25), 0 4px 12px rgba(0,0,0,0.4); transform: translateY(-2px); }
    
    .admin-override-btn div.stButton > button { border: 1px solid #334155 !important; transition: all 0.25s ease !important; }
    .admin-override-btn div.stButton > button:hover { border-color: #EF4444 !important; box-shadow: 0 0 18px rgba(239, 68, 68, 0.5), 0 4px 12px rgba(0,0,0,0.4) !important; transform: translateY(-2px) !important; }
    
    .time-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .compact-time { font-size: 14px; font-weight: 700; color: #60A5FA; font-family: monospace; }
    .badge-group { display: flex; gap: 4px; align-items: center; }
    .long-badge { background: #991B1B; color: #FEE2E2; font-size: 10px; padding: 1px 5px; border-radius: 4px; font-weight: 600; }
    .non-line-badge { background: #4C1D95; color: #C4B5FD; font-size: 10px; padding: 1px 5px; border-radius: 4px; font-weight: 600; }
    
    .compact-name { font-size: 15px; font-weight: 600; color: #E2E8F0; }
    .compact-sub { font-size: 12px; color: #94A3B8; font-family: monospace; margin-top: 2px; }
    
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #00FFCC 0%, #00E5FF 50%, #38BDF8 100%) !important; box-shadow: 0 0 16px rgba(0, 255, 204, 0.9), 0 0 8px rgba(0, 229, 255, 0.7) !important; border-radius: 6px; }
    .loading-status-text { font-family: monospace; font-size: 14px; color: #00FFCC; letter-spacing: 0.5px; margin-bottom: 6px; font-weight: 700; text-shadow: 0 0 8px rgba(0, 255, 204, 0.5); }

    .stRadio > label { display: none !important; }
    .stRadio > div { background: transparent !important; border: none !important; padding: 0 !important; box-shadow: none !important; display: flex; flex-direction: column; gap: 10px; }
    .stRadio label { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important; border: 1px solid #334155 !important; border-radius: 12px !important; padding: 16px 20px !important; width: 100% !important; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); transition: all 0.2s ease; cursor: pointer; }
    .stRadio label:hover { border-color: #3B82F6 !important; background: linear-gradient(135deg, #334155 0%, #1E293B 100%) !important; }
    .stRadio label span { font-size: 17px !important; font-weight: 700 !important; color: #F8FAFC !important; }
    
    .stTextInput input { font-size: 18px !important; padding: 14px 16px !important; border-radius: 10px !important; background-color: #1E293B !important; color: #F8FAFC !important; border: 1px solid #475569 !important; }
    div.stButton > button { font-size: 18px !important; font-weight: 700 !important; padding: 16px 24px !important; border-radius: 12px !important; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 50%, #1D4ED8 100%) !important; color: #ffffff !important; width: 100% !important; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# (其餘邏輯函數與程式主體保持與你提供的內容完全一致)
# [由於長度限制，這裡省略部分函數體，請保持你原本程式碼中後續的邏輯函數不變]
# ... (這裡連接你原本提供的程式碼後續所有邏輯)
