import os
from datetime import timezone, timedelta

TAIWAN_TZ = timezone(timedelta(hours=8))

DATA_DIR = os.path.join(os.getcwd(), "data")
FEEDBACK_IMG_DIR = os.path.join(DATA_DIR, "feedback_uploads")
LOG_FILE = os.path.join(DATA_DIR, "activity_log.txt")

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

NATIONAL_HOLIDAYS = {
    "1/1": "元旦", "2/16": "除夕", "2/17": "初一", "2/18": "初二", "2/19": "初三", 
    "2/28": "和平紀念日", "4/4": "兒童節", "4/5": "清明節", "5/1": "勞動節",
    "6/19": "端午節", "9/25": "中秋節", "9/28": "教師節", "10/10": "國慶日",
    "10/25": "台灣光復節", "12/25": "行憲紀念日"
}

TRANSPORT_PERIODS = {"9/24-9/29": "中秋疏運"}
TITLE = "TRAIN CREW DUTY CALENDAR"

ADMIN_PASSWORD = "Lf090000"
CREW_ACCESS_PASSWORD = "0096"
PILOT_ALLOW_LIST = {"A021987", "A019702", "A023293", "A023442", "A023423", "A026495", "A026662", "A026663", "A026679", "A021578"}

C_HDR, C_BORDER, C_EMPTY = "#0F172A", "#475569", "#F1F5F9"
C_WORK_BG, C_WEEKEND_BG = "#FFFFFF", "#F8FAFC"
C_DO_BG, C_PAY_BG, C_TOWN_BG = "#FFE4E6", "#FFEDD5", "#CBD5E1"
C_DO_TXT, C_PAY_TXT, C_HOLI_TXT, C_OT_TXT, C_NOTE_TXT = "#881337", "#9A3412", "#7C2D12", "#991B1B", "#4C1D95"
C_TOWN_TXT = "#000000"

CUSTOM_CSS = """
<style>
    header[data-testid="stHeader"] { background: transparent !important; }
    div[data-testid="stToolbar"] { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    .stApp { 
        background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f172a 50%, #020617 100%) !important; 
        color: #F8FAFC !important; 
        background-attachment: fixed !important;
    }
    
    @media (min-width: 1024px) {
        .block-container { padding: 2.5rem 1.5rem 2.5rem 1.5rem !important; max-width: 1050px !important; }
    }
    @media (max-width: 1023px) {
        .block-container { padding: 0.8rem 0.6rem 1.5rem 0.6rem !important; max-width: 100% !important; }
    }

    div[data-testid="stButton"], div.stButton { width: 100% !important; }
    div[data-testid="stButton"] > button, div.stButton > button {
        width: 100% !important;
        min-height: 42px !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="input"],
    div[data-testid="stTextArea"] div[data-baseweb="textarea"] {
        background: rgba(15, 23, 42, 0.75) !important;
        border: 1px solid rgba(56, 189, 248, 0.35) !important;
        border-radius: 10px !important;
        padding: 2px 4px !important;
        transition: all 0.25s ease !important;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #F8FAFC !important;
        padding: 6px 10px !important;
        font-family: monospace !important;
    }
    div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
    div[data-testid="stTextArea"] div[data-baseweb="textarea"]:focus-within {
        border-color: #38BDF8 !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.35) !important;
    }

    div[role="radiogroup"] {
        display: flex;
        flex-direction: column;
        gap: 6px !important;
        width: 100%;
        margin-top: 4px !important;
        margin-bottom: 8px !important;
    }
    div[role="radiogroup"] > label {
        background: rgba(30, 41, 59, 0.65) !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-left: 4px solid #38BDF8 !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
        margin: 0 !important;
        cursor: pointer !important;
        transition: all 0.2s ease-in-out !important;
        width: 100% !important;
    }
    div[role="radiogroup"] > label[data-checked="true"], div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(30, 64, 175, 0.65) !important;
        border-color: #60A5FA !important;
        border-left-color: #60A5FA !important;
        box-shadow: 0 0 10px rgba(96, 165, 250, 0.25);
    }
    div[role="radiogroup"] > label p {
        font-size: 13.5px !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
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
        width: 100%; margin-bottom: 0.6rem !important; padding: 10px 10px !important;
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 14px;
    }
    .main-title { color: #F8FAFC !important; font-size: 16px !important; font-weight: 800; letter-spacing: 1.2px; margin: 0; font-family: monospace; }
    .title-subtitle { color: #FFFFFF; font-size: 10px !important; font-weight: 700; letter-spacing: 0.8px; font-family: monospace; margin-top: 2px; }

    .test-env-banner {
        border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 10px; padding: 6px 10px !important; margin-bottom: 0.8rem !important;
        text-align: center; background: rgba(39, 28, 12, 0.55); backdrop-filter: blur(12px); font-family: monospace;
    }
    .test-env-title { color: #FDE68A; font-size: 11px !important; font-weight: 800; letter-spacing: 1px; }
    .test-env-sub { color: #FCD34D; font-size: 9.5px !important; font-weight: 500; opacity: 0.85; margin-top: 1px; }

    div.stButton > button[key*="btn_footer_feedback_left"],
    div.stButton > button[key*="btn_footer_admin_right"] {
        background: rgba(30, 41, 59, 0.45) !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        color: #94A3B8 !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        border-radius: 20px !important;
        padding: 4px 10px !important;
        min-height: 32px !important;
        height: 32px !important;
        letter-spacing: 0.5px !important;
        transition: all 0.25s ease !important;
        box-shadow: none !important;
        font-family: monospace !important;
    }
    div.stButton > button[key*="btn_footer_feedback_left"]:hover,
    div.stButton > button[key*="btn_footer_admin_right"]:hover {
        background: rgba(56, 189, 248, 0.15) !important;
        border-color: #38BDF8 !important;
        color: #38BDF8 !important;
        box-shadow: 0 0 10px rgba(56, 189, 248, 0.25) !important;
    }

    .admin-maint-banner {
        border: 1px solid rgba(245, 158, 11, 0.6);
        border-left: 5px solid #F59E0B;
        border-radius: 10px;
        padding: 8px 12px;
        margin-bottom: 0.8rem;
        background: rgba(245, 158, 11, 0.12);
        backdrop-filter: blur(8px);
        color: #FDE68A;
        font-size: 11.5px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    .user-maint-banner {
        border: 1px solid rgba(245, 158, 11, 0.45);
        border-left: 5px solid #F59E0B;
        border-radius: 12px;
        padding: 14px 16px;
        margin-top: 10px;
        margin-bottom: 14px;
        background: radial-gradient(circle at 50% 0%, rgba(69, 41, 10, 0.6) 0%, rgba(24, 18, 11, 0.75) 100%);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        text-align: center;
    }
    .user-maint-title {
        color: #FDE68A;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 1.2px;
        font-family: monospace;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .user-maint-sub {
        color: #CBD5E1;
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.5px;
        font-family: monospace;
        margin-top: 4px;
        opacity: 0.85;
    }

    .section-header-box { 
        background: rgba(30, 41, 59, 0.45); 
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid #3B82F6; border-radius: 12px; padding: 10px 14px !important; margin-top: 8px !important; margin-bottom: 10px !important; 
    }
    .section-title { color: #F8FAFC; font-size: 14px !important; font-weight: 700; margin: 0; }
    .section-subtitle { color: #94A3B8; font-size: 9.5px !important; font-weight: 500; text-transform: uppercase; font-family: monospace; }

    .integrated-crew-box {
        width: 100% !important;
        box-sizing: border-box !important;
        background: rgba(30, 41, 59, 0.75);
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-bottom: none !important;
        border-left: 4px solid #10B981;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        border-bottom-left-radius: 0px !important;
        border-bottom-right-radius: 0px !important;
        padding: 12px 12px 8px 12px;
        margin-bottom: 0px !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.25);
    }

    .compact-name {
        font-size: 15px !important;
        font-weight: 800 !important;
        color: #F8FAFC !important;
    }
    .badge-group {
        display: flex;
        gap: 4px;
        align-items: center;
    }
    .long-badge {
        background: rgba(225, 29, 72, 0.2) !important;
        color: #FB7185 !important;
        border: 1px solid rgba(244, 63, 94, 0.5) !important;
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
        font-weight: 700 !important; padding: 0.4rem 0.8rem !important; border-radius: 0.5rem !important; 
        background: rgba(30, 41, 59, 0.6) !important; 
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        color: #38BDF8 !important; width: 100% !important; 
        transition: all 0.2s ease !important; letter-spacing: 0.5px; font-family: monospace;
    }

    div[data-baseweb="tab-list"] {
        gap: 8px !important;
        background: rgba(15, 23, 42, 0.5) !important;
        padding: 6px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(56, 189, 248, 0.2) !important;
    }
    button[data-baseweb="tab"] {
        border-radius: 8px !important;
        color: #94A3B8 !important;
        font-weight: 700 !important;
        font-size: 12.5px !important;
        padding: 8px 16px !important;
        background: transparent !important;
    }
    button[aria-selected="true"] {
        background: rgba(56, 189, 248, 0.2) !important;
        color: #38BDF8 !important;
        border: 1px solid rgba(56, 189, 248, 0.4) !important;
    }
</style>
"""
