import os
from datetime import timedelta, timezone
from typing import Any, Dict, List, Tuple

# 時區設定
TAIWAN_TZ: timezone = timezone(timedelta(hours=8))

# 基礎路徑定義 (自動對應專案內的 data 資料夾)
DATA_DIR: str = os.path.join(os.getcwd(), "data")
FEEDBACK_IMG_DIR: str = os.path.join(DATA_DIR, "feedback_uploads")
LOG_FILE: str = os.path.join(DATA_DIR, "activity_log.txt")

# 全站統一設定檔與白名單路徑
SYSTEM_CONFIG_FILE: str = os.path.join(DATA_DIR, "system_config.json")
ALLOWED_USERS_FILE: str = os.path.join(DATA_DIR, "allowed_users.json")
WHITELIST_FILE: str = os.path.join(DATA_DIR, "whitelist.json")

# 各基地所屬單位班表與 Mapping 映射路徑設定 (完整對應 TTN、TTC、TTS 的最新版班表結構)
UNITS: Dict[str, Dict[str, Any]] = {
    "TTN": {
        "駕駛": os.path.join(DATA_DIR, "TTN", "最新版班表", "TTN_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTN", "最新版班表", "TTN_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTN", "最新版班表", "TTN_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTN", "最新版班表", "TTN_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTN", "最新版班表", "TTN_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTN", "最新版班表", "TTN_shift_mapping_TA.xlsx"),
        },
    },
    "TTC": {
        "駕駛": os.path.join(DATA_DIR, "TTC", "最新版班表", "TTC_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTC", "最新版班表", "TTC_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTC", "最新版班表", "TTC_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTC", "最新版班表", "TTC_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTC", "最新版班表", "TTC_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTC", "最新版班表", "TTC_shift_mapping_TA.xlsx"),
        },
    },
    "TTS": {
        "駕駛": os.path.join(DATA_DIR, "TTS", "最新版班表", "TTS_TD.xlsx"),
        "列車長": os.path.join(DATA_DIR, "TTS", "最新版班表", "TTS_TM.xlsx"),
        "服勤員": os.path.join(DATA_DIR, "TTS", "最新版班表", "TTS_TA.xlsx"),
        "mapping": {
            "駕駛": os.path.join(DATA_DIR, "TTS", "最新版班表", "TTS_shift_mapping_TD.xlsx"),
            "列車長": os.path.join(DATA_DIR, "TTS", "最新版班表", "TTS_shift_mapping_TM.xlsx"),
            "服勤員": os.path.join(DATA_DIR, "TTS", "最新版班表", "TTS_shift_mapping_TA.xlsx"),
        },
    },
}

# 國定假日標記對照字典
NATIONAL_HOLIDAYS: Dict[str, str] = {
    "1/1": "元旦",
    "2/16": "除夕",
    "2/17": "初一",
    "2/18": "初二",
    "2/19": "初三",
    "2/28": "和平紀念日",
    "4/4": "兒童節",
    "4/5": "清明節",
    "5/1": "勞動節",
    "6/19": "端午節",
    "9/25": "中秋節",
    "9/28": "教師節",
    "10/10": "國慶日",
    "10/25": "台灣光復節",
    "12/25": "行憲紀念日",
}

# 疏運期間標記字典
TRANSPORT_PERIODS: Dict[str, str] = {
    "9/24-9/29": "中秋疏運",
    "10/4-10/10": "雙十節疏運",
    "10/25-10/31": "光復節疏運",
}

TITLE: str = "TRAIN CREW DUTY CALENDAR"

# 預設系統通行密碼預設值
ADMIN_PASSWORD: str = "Lf090000"
CREW_ACCESS_PASSWORD: str = "0"

# 完整通用請假代碼集
LEAVE_CODES: List[str] = [
    "PAY",
    "CMP",
    "FAC",
    "FAC1",
    "FPL",
    "HPS",
    "HPS1",
    "LEV",
    "LU",
    "LUP",
    "LUTS",
    "MAT",
    "ML",
    "MLP",
    "MTR",
    "NHS",
    "NHS1",
    "NHS2",
    "NTD",
    "OPI",
    "PAT",
    "PAY1",
    "RCL",
    "TRN",
    "UNP",
    "UNP1",
    "UNP2",
    "WRSL",
]

# 班表圖像渲染色調定義
C_HDR: str = "#0F172A"
C_BORDER: str = "#475569"
C_EMPTY: str = "#F1F5F9"
C_WORK_BG: str = "#FFFFFF"
C_WEEKEND_BG: str = "#F8FAFC"
C_DO_BG: str = "#FFE4E6"
C_PAY_BG: str = "#FFEDD5"
C_TOWN_BG: str = "#CBD5E1"

C_DO_TXT: str = "#881337"
C_PAY_TXT: str = "#9A3412"
C_HOLI_TXT: str = "#7C2D12"
C_OT_TXT: str = "#EF4444"
C_NOTE_TXT: str = "#4C1D95"
C_TOWN_TXT: str = "#000000"

# 全站專業級 CSS 美化樣式 (已將 Radio 調整為極簡、輕量、不佔空間的專業清單膠囊風格)
# 全站專業級 CSS 美化樣式 (已加入彈出對話框內輸入框的深色防白化修正)
CUSTOM_CSS: str = """
<style>
    header[data-testid="stHeader"] { background: transparent !important; }
    div[data-testid="stToolbar"] { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    .stApp { 
        background: radial-gradient(circle at 50% 0%, #0f172a 0%, #090d16 55%, #020617 100%) !important; 
        color: #F8FAFC !important; 
        background-attachment: fixed !important;
    }
    
    .hours-badge {
        background: rgba(56, 189, 248, 0.15) !important;
        color: #38BDF8 !important;
        border: 1px solid rgba(56, 189, 248, 0.4) !important;
        border-radius: 6px !important;
        padding: 2px 6px !important;
        font-size: 10.5px !important;
        font-weight: 800 !important;
        font-family: monospace !important;
        line-height: 1.2 !important;
    }
    
    .do2w-badge {
        background: rgba(245, 158, 11, 0.2) !important;
        color: #FDE68A !important;
        border: 1px solid #F59E0B !important;
        border-radius: 6px !important;
        padding: 2px 6px !important;
        font-size: 10.5px !important;
        font-weight: 800 !important;
        font-family: monospace !important;
        line-height: 1.2 !important;
    }
    
    @media (min-width: 1024px) {
        .block-container { padding: 2.5rem 1.5rem 2.5rem 1.5rem !important; max-width: 1080px !important; }
    }
    @media (max-width: 1023px) {
        .block-container { padding: 1rem 0.75rem 2rem 0.75rem !important; max-width: 100% !important; }
    }

    div[data-testid="stButton"], div.stButton { width: 100% !important; }
    div[data-testid="stButton"] > button, div.stButton > button {
        width: 100% !important;
        min-height: 44px !important;
        border-radius: 8px !important;
        font-family: monospace !important;
    }

    /* ========================================================= */
    /* 強化版：全面覆蓋一般頁面與對話框 (Dialog) 內的輸入框與下拉選單 */
    /* ========================================================= */
    .stTextInput > div > div > div,
    .stSelectbox > div > div > div,
    div[data-baseweb="input"],
    div[data-baseweb="base-input"],
    div[data-baseweb="select"] {
        background-color: #1E293B !important;
        border: 1px solid #475569 !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
    }
    
    div[data-baseweb="textarea"] {
        background-color: #1E293B !important;
        border: 1px solid #475569 !important;
        border-radius: 8px !important;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    input, textarea {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
        padding: 8px 12px !important;
        font-family: monospace !important;
    }
    
    div[data-testid="stTextInput"] input::placeholder,
    div[data-testid="stTextArea"] textarea::placeholder {
        color: #64748B !important;
        -webkit-text-fill-color: #64748B !important;
    }
    
    .stTextInput > div > div > div:focus-within,
    .stSelectbox > div > div > div:focus-within,
    div[data-baseweb="input"]:focus-within {
        border-color: #38BDF8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.3) !important;
    }

    div[data-baseweb="popover"] div {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
    }

    /* ========================================================= */
    /* 專業化 UI：極簡、輕量、不佔空間的輕膠囊 Radio 按鈕         */
    /* ========================================================= */
    div[data-testid="stRadio"] {
        background: transparent !important;
        border: none !important;
        padding: 0px !important;
        box-shadow: none !important;
    }
    
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        gap: 6px !important;
    }
    
    div[data-testid="stRadio"] label {
        background: rgba(30, 41, 59, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
        padding: 8px 12px !important;
        margin: 0 !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
    }
    
    div[data-testid="stRadio"] label:hover {
        background: rgba(56, 189, 248, 0.15) !important;
        border-color: rgba(56, 189, 248, 0.4) !important;
    }
    
    div[data-testid="stRadio"] label p {
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-family: monospace !important;
        font-size: 13px !important;
        margin: 0 !important;
    }
    
    div[data-testid="stRadio"] label:has(input:checked) {
        background: rgba(30, 58, 138, 0.5) !important;
        border-color: #38BDF8 !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.2) !important;
    }
    
    div[data-testid="stRadio"] label:has(input:checked) p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    div[data-baseweb="tab-list"] {
        gap: 8px !important;
        background: rgba(15, 23, 42, 0.6) !important;
        padding: 6px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
    }
    button[data-baseweb="tab"] {
        border-radius: 8px !important;
        color: #94A3B8 !important;
        font-weight: 700 !important;
        font-size: 13px !important;
        padding: 8px 18px !important;
        background: transparent !important;
        font-family: monospace !important;
    }
    button[aria-selected="true"] {
        background: rgba(56, 189, 248, 0.25) !important;
        color: #38BDF8 !important;
        border: 1px solid rgba(56, 189, 248, 0.5) !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.2) !important;
    }

    div[data-baseweb="slider"] div[role="slider"] {
        background-color: #38BDF8 !important;
        border-color: #38BDF8 !important;
    }
    div[data-baseweb="slider"] div > div > div {
        background-color: #38BDF8 !important;
    }

    div[data-baseweb="slider"] {
        padding-top: 10px !important;
        padding-bottom: 10px !important;
    }

    @keyframes online-green-pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.6); }
        70% { transform: scale(1.05); box-shadow: 0 0 0 6px rgba(74, 222, 128, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }
    }

    .online-dot {
        width: 6px; height: 6px; background-color: #4ADE80; border-radius: 50%;
        display: inline-block; animation: online-green-pulse 2.5s infinite ease-in-out;
        box-shadow: 0 0 8px #4ADE80; margin: 0 5px; vertical-align: middle;
    }

    .header-container { 
        display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;
        width: 100%; margin-bottom: 0.8rem !important; padding: 14px 12px !important;
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    .main-title { color: #F8FAFC !important; font-size: 17px !important; font-weight: 900; letter-spacing: 1.5px; margin: 0; font-family: monospace; }
    .title-subtitle { color: #94A3B8; font-size: 10.5px !important; font-weight: 600; letter-spacing: 1px; font-family: monospace; margin-top: 4px; }

    .test-env-banner {
        border: 1px solid rgba(245, 158, 11, 0.5); border-radius: 10px; padding: 8px 12px !important; margin-bottom: 1rem !important;
        text-align: center; background: rgba(39, 28, 12, 0.7); backdrop-filter: blur(12px); font-family: monospace;
    }
    .test-env-title { color: #FDE68A; font-size: 11.5px !important; font-weight: 800; letter-spacing: 1.2px; }
    .test-env-sub { color: #FCD34D; font-size: 10px !important; font-weight: 500; opacity: 0.9; margin-top: 2px; }

    .section-header-box { 
        background: rgba(30, 41, 59, 0.6); 
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #38BDF8; border-radius: 10px; padding: 10px 14px !important; margin-top: 10px !important; margin-bottom: 12px !important; 
    }
    .section-title { color: #F8FAFC; font-size: 14px !important; font-weight: 700; margin: 0; font-family: monospace; }
    .section-subtitle { color: #94A3B8; font-size: 10px !important; font-weight: 600; text-transform: uppercase; font-family: monospace; letter-spacing: 0.5px; }

    .long-badge {
        background: rgba(239, 68, 68, 0.2) !important;
        color: #F87171 !important;
        border: 1px solid rgba(239, 68, 68, 0.5) !important;
        border-radius: 6px !important;
        padding: 2px 6px !important;
        font-size: 10.5px !important;
        font-weight: 800 !important;
        font-family: monospace !important;
        line-height: 1.2 !important;
    }
    .non-line-badge {
        background: rgba(148, 163, 184, 0.2) !important;
        color: #CBD5E1 !important;
        border: 1px solid rgba(148, 163, 184, 0.4) !important;
        border-radius: 6px !important;
        padding: 2px 6px !important;
        font-size: 10.5px !important;
        font-weight: 800 !important;
        font-family: monospace !important;
        line-height: 1.2 !important;
    }

    div.stButton > button, div.stFormSubmitButton > button { 
        font-weight: 700 !important; padding: 0.5rem 1rem !important; border-radius: 0.5rem !important; 
        background: rgba(30, 41, 59, 0.75) !important; 
        border: 1px solid rgba(56, 189, 248, 0.3) !important;
        color: #38BDF8 !important; width: 100% !important; 
        transition: all 0.2s ease !important; letter-spacing: 0.5px; font-family: monospace;
    }
    div.stButton > button:hover {
        background: rgba(56, 189, 248, 0.2) !important;
        border-color: #38BDF8 !important;
        color: #FFFFFF !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.25) !important;
    }
</style>
"""
# ==========================================
# 📧 系統管理員郵件通知與 SMTP 參數設定
# ==========================================
SMTP_SERVER: str = "smtp.gmail.com"        # 例如使用 Gmail 伺服器
SMTP_PORT: int = 587                       # TLS 連接埠
SENDER_EMAIL: str = "leooel911@gmail.com"     # 填入你的 Google 帳號
SENDER_PASSWORD: str = "aoisluiqatzsmlec"        # 填入 Gmail 的「應用程式密碼」(16碼)
ADMIN_RECEIVE_EMAIL: str = "leooel911@gmail.com" # 收件人信箱
