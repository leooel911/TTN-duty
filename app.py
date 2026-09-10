"""
CREW DUTY ENGINE V2 - Main Entrypoint
整合 V1 全套繪圖與算力引擎 + V2 號誌樓滿版介面
"""
import os
import sys

# 🛠️ 1. 最優先加入專案根目錄搜尋路徑，徹底解決 Streamlit Cloud 跨目錄 Import 問題
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

from modules.services import (
    get_crew_full_schedule_json,
    load_system_config,
    search_exchange_candidates_v2,
)
from modules.admin_views import render_admin_panel
from modules.drawing import render_schedule_figure
from modules.components import render_zoomable_image

# 2. 頁面初始化
st.set_page_config(
    page_title="CREW DUTY ENGINE — Dispatch Terminal",
    page_icon="700st.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 3. Session State 初始化
if "current_unit" not in st.session_state:
    st.session_state.current_unit = "TTN"
if "current_emp_id" not in st.session_state:
    st.session_state.current_emp_id = "A026047"
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "nav_mode" not in st.session_state:
    st.session_state.nav_mode = "user"

# 4. 路由判斷：管理員後台模式
if st.session_state.nav_mode == "admin" and st.session_state.admin_logged_in:
    render_admin_panel()
    st.stop()

# 5. 前台 Streamlit 側邊欄控制
with st.sidebar:
    st.title("⚙️ 調度終端系統控制台")
    st.caption("CREW DUTY ENGINE V2 · Real-Data Hybrid")
    st.divider()

    # 切換基地
    unit_sel = st.selectbox(
        "選擇營運基地",
        ["TTN", "TTC", "TTS"],
        index=["TTN", "TTC", "TTS"].index(st.session_state.current_unit)
    )
    if unit_sel != st.session_state.current_unit:
        st.session_state.current_unit = unit_sel
        st.rerun()

    # 輸入員編登入
    input_emp = st.text_input("輸入要查詢/登入的員編", value=st.session_state.current_emp_id)
    if st.button("載入組員班表", use_container_width=True):
        st.session_state.current_emp_id = input_emp.strip().upper()
        st.rerun()

    st.divider()

    # 匯出 V1 高解析度 300 DPI 月曆圖檔按鈕
    if st.button("🖼️ 生成 300 DPI 高清月班表", use_container_width=True):
        st.session_state["show_hd_map"] = True

    st.divider()
    # 管理員後台入口
    if st.button("🔑 開啟管理員後台 (Admin Panel)", use_container_width=True):
        st.session_state.admin_logged_in = True
        st.session_state.nav_mode = "admin"
        st.rerun()

# 6. 高清繪圖對話框處理
if st.session_state.get("show_hd_map", False):
    st.markdown("### 🖼️ 高解析度月班表圖檔預覽 (V1 繪圖引擎)")
    crew_info = get_crew_full_schedule_json(st.session_state.current_emp_id, st.session_state.current_unit)
    if crew_info and "raw_cells" in crew_info:
        buf = render_schedule_figure(
            start_dt=datetime(2026, 9, 1),
            dates=crew_info["raw_dates"],
            emp_id=crew_info["emp_id"],
            emp_name=crew_info["name"],
            cells=crew_info["raw_cells"],
            unit_label=crew_info["unit_name"]
        )
        render_zoomable_image(buf)
        st.download_button("⬇️ 下載高清班表 PNG", buf, file_name=f"{crew_info['emp_id']}_schedule.png", mime="image/png")
    else:
        st.error("無法讀取該組員之完整原始儲存格資料以繪製圖檔。")
    
    if st.button("關閉圖檔預覽"):
        st.session_state["show_hd_map"] = False
        st.rerun()

# 7. 全螢幕滿版 CSS
st.markdown(
    """
    <style>
    [data-testid="stHeader"] { background: transparent !important; height: 0px !important; }
    [data-testid="stToolbar"], footer { display: none !important; }
    [data-testid="stSidebarCollapsedControl"], button[aria-label="Open sidebar"] {
        position: fixed !important; top: 10px !important; left: 10px !important; z-index: 99999999 !important;
        background-color: rgba(20, 28, 38, 0.85) !important; border: 1px solid #232E3A !important;
        border-radius: 8px !important; color: #4C9AE0 !important; backdrop-filter: blur(8px) !important;
    }
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        padding: 0 !important; margin: 0 !important; background-color: #070B10 !important;
        overflow: hidden !important; height: 100dvh !important;
    }
    .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; height: 100dvh !important; }
    iframe { border: none !important; width: 100vw !important; height: 100dvh !important; position: fixed !important; top: 0 !important; left: 0 !important; z-index: 99999 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# 8. 調用算力抓取真實班表 JSON
current_crew = get_crew_full_schedule_json(st.session_state.current_emp_id, st.session_state.current_unit)

user_sched = current_crew["schedule"] if current_crew else []
formatted_schedule = {
    "week1": user_sched[:7],
    "week2": user_sched[7:14],
    "week3": user_sched[14:21]
}

# 調用算力計算快搜名單
dynamic_exchange = search_exchange_candidates_v2(st.session_state.current_unit)

# 9. 前端 HTML 範本
RAW_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>CREW DUTY ENGINE — Dispatch Terminal</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans+TC:wght@400;500;600;700&display=swap');
:root{
  --ink-900:#070B10; --ink-800:#0E141C; --ink-700:#141C26; --ink-600:#1B2530;
  --line:#232E3A; --line-soft:#1A222C; --paper:#ECF1F5; --dim:#8492A1; --dim-2:#59636E;
  --blue:#4C9AE0; --amber:#E3A13D; --red:#E1615C; --green:#4FB88A;
}
*{box-sizing:border-box;}
body{margin:0;padding:0;background:var(--ink-900);color:var(--paper);font-family:'IBM Plex Sans TC','IBM Plex Mono',sans-serif;-webkit-font-smoothing:antialiased;}
.mono{font-family:'IBM Plex Mono',monospace;}
.app{max-width:480px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column;position:relative;background:var(--ink-900);}
.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;padding:14px 16px 10px 48px;background:linear-gradient(var(--ink-900) 70%, transparent);}
.brand{display:flex;align-items:center;gap:9px;}
.brand-mark{width:26px;height:26px;border-radius:6px;background:var(--ink-700);border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:var(--blue);}
.brand-name{font-size:13px;font-weight:600;color:var(--paper);}
.brand-sub{font-size:9.5px;color:var(--dim-2);}
.unit-chip{display:flex;align-items:center;gap:6px;background:var(--ink-700);border:1px solid var(--line);padding:6px 10px;border-radius:8px;font-size:12.5px;font-weight:600;color:var(--paper);cursor:pointer;}
.unit-chip .dot{width:6px;height:6px;border-radius:50%;background:var(--green);}
main{flex:1;padding:0 16px 96px;overflow-x:hidden;}
.screen{display:none;}
.screen.active{display:block;}
.section-label{font-size:11px;color:var(--dim-2);font-weight:600;margin:22px 2px 10px;}
.hero{border:1px solid var(--line);border-radius:14px;background:linear-gradient(165deg, var(--ink-700), var(--ink-800));padding:20px 18px;}
.panel{border:1px solid var(--line);border-radius:12px;background:var(--ink-800);padding:4px 14px;}
.week-head{display:flex;justify-content:space-between;padding:12px 2px 8px;font-size:12px;font-weight:600;color:var(--dim);}
.duty-row{display:flex;align-items:center;gap:12px;padding:11px 2px;border-bottom:1px solid var(--line-soft);}
.duty-row:last-child{border-bottom:none;}
.duty-date{width:38px;text-align:center;}
.duty-date .d{font-size:16px;font-weight:600;color:var(--paper);}
.duty-date .w{font-size:9.5px;color:var(--dim-2);}
.duty-bar{width:3px;align-self:stretch;border-radius:3px;background:var(--blue);}
.duty-bar.off{background:var(--red);}
.duty-main{flex:1;}
.duty-times{font-size:14.5px;font-weight:600;}
.duty-meta{font-size:11px;color:var(--dim-2);margin-top:2px;display:flex;gap:8px;}
.tag{font-size:9.5px;font-weight:600;padding:2.5px 6px;border-radius:5px;}
.tag.amber{color:var(--amber);background:rgba(227,161,61,0.14);}
.tag.red{color:var(--red);background:rgba(225,97,92,0.14);}
.tag.green{color:var(--green);background:rgba(79,184,138,0.14);}
.empty-box{text-align:center;padding:36px 16px;background:var(--ink-800);border:1px solid var(--line);border-radius:14px;margin-top:16px;}
.btn{display:block;width:100%;text-align:center;padding:13px;border-radius:10px;border:none;font-size:14.5px;font-weight:600;cursor:pointer;}
.btn-primary{background:var(--blue);color:var(--ink-900);}
.role-tabs{display:flex;gap:8px;margin-bottom:14px;}
.role-tab{flex:1;text-align:center;padding:9px 0;border-radius:9px;font-size:13px;font-weight:600;color:var(--dim);background:var(--ink-800);border:1px solid var(--line);cursor:pointer;}
.role-tab.active{color:var(--ink-900);background:var(--blue);}
.result-card{border:1px solid var(--line);border-radius:12px;background:var(--ink-800);padding:13px 14px;margin-bottom:10px;}
.tabbar{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:480px;display:flex;background:rgba(14,20,28,0.92);backdrop-filter:blur(10px);border-top:1px solid var(--line);padding:8px 6px;z-index:30;}
.tab-item{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;padding:6px 0;cursor:pointer;color:var(--dim-2);}
.tab-item.active{color:var(--blue);}
</style>
</head>
<body>
<div class="app">
  <header class="topbar">
    <div class="brand">
      <div class="brand-mark">CD</div>
      <div>
        <div class="brand-name">CREW DUTY ENGINE</div>
        <div class="brand-sub">real-data hybrid · C.L.F</div>
      </div>
    </div>
    <div class="unit-chip" onclick="openAdminPanel()">
      <span class="dot"></span>
      <span id="unitText">--</span>
    </div>
  </header>

  <main>
    <section class="screen active" id="screen-home"><div id="homeContent"></div></section>
    <section class="screen" id="screen-schedule"><div class="section-label" id="schedTitle">我的月班表</div><div id="scheduleContent"></div></section>
    <section class="screen" id="screen-exchange">
      <div class="section-label">換班快搜</div>
      <div class="role-tabs">
        <div class="role-tab active" onclick="filterRole('服勤員', this)">服勤員</div>
        <div class="role-tab" onclick="filterRole('駕駛', this)">駕駛</div>
        <div class="role-tab" onclick="filterRole('列車長', this)">列車長</div>
      </div>
      <div id="searchResults"></div>
    </section>
    <section class="screen" id="screen-profile"><div id="profileContent"></div></section>
  </main>

  <nav class="tabbar">
    <div class="tab-item active" data-tab="home" onclick="showTab('home')"><span>今日</span></div>
    <div class="tab-item" data-tab="schedule" onclick="showTab('schedule')"><span>我的班表</span></div>
    <div class="tab-item" data-tab="exchange" onclick="showTab('exchange')"><span>換班快搜</span></div>
    <div class="tab-item" data-tab="profile" onclick="showTab('profile')"><span>我的</span></div>
  </nav>
</div>

<script>
const crewData = __CREW_JSON__;
const scheduleData = __SCHEDULE_JSON__;
const exchangeData = __EXCHANGE_JSON__;

function openAdminPanel(){
  try {
    const btn = window.parent.document.querySelector('button[aria-label="Open sidebar"], [data-testid="stSidebarCollapsedControl"]');
    if(btn) btn.click();
  } catch(e) {}
}

document.getElementById('unitText').textContent = crewData ? crewData.unit : '切換';

const homeBox = document.getElementById('homeContent');
if(!crewData){
  homeBox.innerHTML = `
    <div class="empty-box">
      <div class="title" style="font-weight:700;margin-bottom:6px;">未找到組員班表</div>
      <div class="sub" style="font-size:12px;color:var(--dim-2);margin-bottom:16px;">請點擊左上角「›」按鈕切換基地或輸入正確員編。</div>
      <button class="btn btn-primary" onclick="openAdminPanel()">⚙️ 開啟控制台</button>
    </div>`;
} else {
  homeBox.innerHTML = `
    <div class="hero">
      <div style="font-size:15px;font-weight:700;color:var(--paper);">${crewData.name} (${crewData.emp_id})</div>
      <div style="font-size:11.5px;color:var(--dim-2);margin-top:3px;">基地：${crewData.unit_name} (${crewData.unit}) · 職掌：${crewData.role_title}</div>
    </div>
    <div class="section-label">快速切換</div>
    <div class="panel">
      <div class="duty-row" onclick="showTab('schedule')" style="cursor:pointer;"><div style="flex:1;"><b>我的月班表</b><div style="font-size:11px;color:var(--dim-2);">真實大表解析・班間合規警示</div></div>›</div>
      <div class="duty-row" onclick="showTab('exchange')" style="cursor:pointer;"><div style="flex:1;"><b>換班快搜</b><div style="font-size:11px;color:var(--dim-2);">Sign-In 時段區間搜尋</div></div>›</div>
    </div>`;
}

const schedBox = document.getElementById('scheduleContent');
if(crewData && scheduleData.week1){
  function renderWeekHtml(days){
    return days.map(day => {
      if(day.off){
        return `<div class="duty-row"><div class="duty-date"><div class="d mono">${day.d}</div><div class="w">${day.wd}</div></div><div class="duty-bar off"></div><div class="duty-main"><div style="color:var(--red);font-weight:600;">${day.off}</div></div><span class="tag red">休假</span></div>`;
      }
      const restHtml = day.rest ? `<span style="color:var(--${day.restTag})">班間 ${day.rest}</span>` : '';
      return `<div class="duty-row"><div class="duty-date"><div class="d mono">${day.d}</div><div class="w">${day.wd}</div></div><div class="duty-bar"></div><div class="duty-main"><div class="duty-times mono">${day.start} → ${day.end}</div><div class="duty-meta"><span>${day.code}</span><span>${day.dur}</span>${restHtml}</div></div></div>`;
    }).join('');
  }
  schedBox.innerHTML = `
    <div class="week-head">第 1 週</div><div class="panel">${renderWeekHtml(scheduleData.week1)}</div>
    <div class="week-head">第 2 週</div><div class="panel">${renderWeekHtml(scheduleData.week2)}</div>
    <div class="week-head">第 3 週</div><div class="panel">${renderWeekHtml(scheduleData.week3)}</div>`;
}

function filterRole(role, btn){
  document.querySelectorAll('.role-tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  renderExchange(role);
}

function renderExchange(role){
  const container = document.getElementById('searchResults');
  const pool = exchangeData[role] || [];
  if(pool.length === 0){
    container.innerHTML = `<div class="empty-box"><div style="font-size:13px;color:var(--dim-2);">目前大表中無該職務可換班之組員</div></div>`;
    return;
  }
  container.innerHTML = pool.map(c => `
    <div class="result-card">
      <div style="display:flex;justify-content:space-between;">
        <div><div class="mono" style="font-size:11px;color:var(--dim-2);">${c.id}</div><div style="font-size:14px;font-weight:600;">${c.name}</div></div>
        <span class="tag ${c.restTag}">${c.restBefore}</span>
      </div>
      <div class="mono" style="font-size:17px;font-weight:600;margin-top:6px;">${c.start} → ${c.end}</div>
      <div style="font-size:11px;color:var(--dim-2);margin-top:2px;">${c.streak}</div>
    </div>
  `).join('');
}
renderExchange('服勤員');

function showTab(name){
  document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));
  document.getElementById('screen-'+name).classList.add('active');
  document.querySelectorAll('.tab-item').forEach(t=>t.classList.toggle('active', t.dataset.tab===name));
}
</script>
</body>
</html>
"""

HTML_CODE = RAW_HTML_TEMPLATE.replace(
    "__CREW_JSON__", json.dumps(current_crew, ensure_ascii=False) if current_crew else "null"
).replace(
    "__SCHEDULE_JSON__", json.dumps(formatted_schedule, ensure_ascii=False)
).replace(
    "__EXCHANGE_JSON__", json.dumps(dynamic_exchange, ensure_ascii=False)
)

components.html(HTML_CODE, height=1000, scrolling=False)
