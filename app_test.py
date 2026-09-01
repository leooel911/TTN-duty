import streamlit as str_module
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
import hashlib
import base64

matplotlib.use('Agg')

st.set_page_config(page_title="TTN Shift Producer", page_icon="700st.png", layout="centered")

TAIWAN_TZ = timezone(timedelta(hours=8))

DATA_DIR = os.path.join(os.getcwd(), "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

UNITS = {
    "TTN": {
        "駕駛": os.path.join(DATA_DIR, "TTN_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTN_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTN_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTN_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTN_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTN_shift_mapping_TA.xlsx")
        }
    },
    "TTC": {
        "駕駛": os.path.join(DATA_DIR, "TTC_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTC_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTC_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTC_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTC_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTC_shift_mapping_TA.xlsx")
        }
    },
    "TTS": {
        "駕駛": os.path.join(DATA_DIR, "TTS_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTS_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTS_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTS_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTS_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTS_shift_mapping_TA.xlsx")
        }
    }
}

LOG_FILE = os.path.join(DATA_DIR, "activity_log.txt")

# --- 單位獨立維護開關的核心檔案處理邏輯 ---
def get_maintenance_flag_path(unit, module_key):
    return os.path.join(DATA_DIR, f"maintenance_{unit}_{module_key}.flag")

def set_module_maintenance(unit, module_key, is_maint):
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR, exist_ok=True)
    flag_path = get_maintenance_flag_path(unit, module_key)
    if is_maint:
        with open(flag_path, "w") as f: f.write("ON")
    else:
        if os.path.exists(flag_path): os.remove(flag_path)

def is_module_maintenance(unit, module_key):
    flag_path = get_maintenance_flag_path(unit, module_key)
    return os.path.exists(flag_path)

# --- 升級版毛玻璃與響應式視覺設計 (Glassmorphism & Integrated UI) ---
st.markdown("""
<style>
    .stApp { 
        background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f172a 50%, #020617 100%) !important; 
        color: #F8FAFC !important; 
        background-attachment: fixed !important;
    }
    
    /* 桌面端與行動端寬度適配 */
    @media (min-width: 1024px) {
        .block-container { padding: 3.5rem 1.5rem 3rem 1.5rem !important; max-width: 1050px !important;The error is caused by a typo in your import statement. Matplotlib's plotting submodule is named **`pyplot`**, not `plt` (`plt` is the standard alias assigned to it).

Change **line 9** in `/mount/src/ttn-duty/app_test.py` from:

```python
import matplotlib.plt as plt
