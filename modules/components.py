import base64
from datetime import datetime
import io
import os

from config import FEEDBACK_IMG_DIR, TAIWAN_TZ
from modules.drawing import render_schedule_figure
from modules.services import process_file_data
from modules.utils import log_activity
import streamlit as st


# =========================================================
# 🖼️ 核心修復：可放大/縮放圖片渲染器 (解決 BytesIO 純白畫面問題)
# =========================================================
def render_zoomable_image(image_source, height=650):
  """縮放圖片元件：自動重置 BytesIO 指針，解決純白畫面與位元組讀取問題"""
  if image_source is None:
    st.warning("⚠️ 尚未取得有效的圖片資料。")
    return

  try:
    # 🔑 關鍵步驟 1：若為 BytesIO，強制將讀取指針拉回開頭 (seek to 0)
    if hasattr(image_source, "seek"):
      image_source.seek(0)

    # 🔑 關鍵步驟 2：解析並轉為 base64 安全編碼
    if isinstance(image_source, io.BytesIO):
      img_bytes = image_source.getvalue()
    elif isinstance(image_source, bytes):
      img_bytes = image_source
    elif isinstance(image_source, str) and os.path.exists(image_source):
      with open(image_source, "rb") as f:
        img_bytes = f.read()
    else:
      st.image(image_source, use_container_width=True)
      return

    if not img_bytes:
      st.error("❌ 圖片內容為空，請重新繪製。")
      return

    b64_str = base64.b64encode(img_bytes).decode("utf-8")

    # 🔑 關鍵步驟 3：使用深色自訂 HTML 容器渲染，支援自動捲動與高解析度放大
    html_code = f"""
        <div style="width:100%; text-align:center; background-color:#0f172a; padding:12px; border-radius:10px; border: 1px solid rgba(255,255,255,0.1);">
            <img src="data:image/png;base64,{b64_str}" style="max-width:100%; height:auto; border-radius:6px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);" />
        </div>
        """
    st.components.v1.html(html_code, height=height, scrolling=True)

  except Exception as e:
    # 備援渲染機制 (即使發送例外，也先 reset 指針後嘗試原生渲染)
    try:
      if hasattr(image_source, "seek"):
        image_source.seek(0)
      st.image(image_source, use_container_width=True)
    except Exception:
      st.error(f"渲染圖片時發生錯誤: {e}")


# =========================================================
# 🔍 檢視回報附件截圖彈窗
# =========================================================
@st.dialog("檢視回報附件截圖", width="medium")
def view_feedback_img_modal(img_path, ticket_id, user_info):
  st.caption(f"處理單號：{ticket_id} ｜ 回報人員：{user_info}")
  if os.path.exists(img_path):
    st.image(img_path, use_container_width=True)
    with open(img_path, "rb") as f_img:
      st.download_button(
          "下載原始圖檔",
          data=f_img.read(),
          file_name=os.path.basename(img_path),
          mime="image/png",
          use_container_width=True,
      )
  else:
    st.error("找不到該附件圖檔，可能已被刪除。")


# =========================================================
# 💬 系統問題與建議彈窗 (雙頁籤：線上回報 / 我的歷史回報)
# =========================================================
@st.dialog("系統問題與建議", width="medium")
def show_feedback_modal():
  current_unit = st.session_state.get("current_unit", "TTN")
  current_user = st.session_state.get("current_user_id", "未知")

  tab_create, tab_my_records = st.tabs(["線上回報", "我的歷史回報"])

  with tab_create:
    if "fb_submitted_id" in st.session_state:
      ticket_id = st.session_state["fb_submitted_id"]
      st.success("反饋已成功送出！系統已紀錄您的處理編號。")
      st.markdown(
          f"""
            <div style="background: rgba(16, 185, 129, 0.15); border: 1.5px solid #10B981; border-radius: 12px; padding: 16px; text-align: center; margin: 12px 0;">
                <div style="font-size: 12px; color: #CBD5E1; font-family: monospace;">系統處理編號 (Ticket ID)</div>
                <div style="font-size: 22px; font-weight: 800; color: #34D399; font-family: monospace; letter-spacing: 1.5px; margin-top: 4px;">
                    {ticket_id}
                </div>
                <div style="font-size: 11px; color: #94A3B8; font-family: monospace; margin-top: 6px;">
                    您可以隨時切換至「我的歷史回報」頁籤查看即時處理進度與留言。
                </div>
            </div>
            """,
          unsafe_allow_html=True,
      )

      if st.button(
          "確認並完成",
          key="confirm_fb_success_btn",
          use_container_width=True,
      ):
        del st.session_state["fb_submitted_id"]
        st.rerun()
    else:
      st.caption(f"回報人員：{current_unit} | {current_user}")
      fb_type = st.selectbox(
          "反饋類別",
          ["Bug 問題回報", "功能改進建議", "班表資料不對", "其他"],
          key="fb_type_sel",
      )
      fb_content = st.text_area(
          "詳細說明",
          placeholder="請輸入您遇到的問題或建議內容...",
          height=110,
          max_chars=500,
          key="fb_content_txt",
      )
      uploaded_img = st.file_uploader(
          "上傳螢幕截圖 (選填，限 PNG/JPG)",
          type=["png", "jpg", "jpeg"],
          key="fb_img_uploader",
      )

      col_sb1, col_sb2 = st.columns(2)
      with col_sb1:
        if st.button(
            "確認送出", key="submit_fb_btn", use_container_width=True
        ):
          if fb_content.strip():
            clean_content = fb_content.strip()
            now_dt = datetime.now(TAIWAN_TZ)
            now_stamp = now_dt.strftime("%Y%m%d_%H%M%S")
            now_human = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            clean_user_id = (
                str(current_user).split(" ")[0].replace("/", "_")
            )

            ticket_id = (
                f"FB-{now_dt.strftime('%Y%m%d-%H%M%S')}-{current_unit}"
            )
            base_name = f"{now_stamp}_{current_unit}_{clean_user_id}"

            # 確保 FEEDBACK_IMG_DIR 資料夾存在
            os.makedirs(FEEDBACK_IMG_DIR, exist_ok=True)

            txt_path = os.path.join(FEEDBACK_IMG_DIR, f"{base_name}.txt")
            with open(txt_path, "w", encoding="utf-8") as f_txt:
              f_txt.write(
                  f"處理編號: {ticket_id}\n狀態: 待處理\n類別: {fb_type}\n單位:"
                  f" {current_unit}\n回報者: {current_user}\n時間:"
                  f" {now_human}\n管理員回覆: 尚無回覆\n詳細說明:\n{clean_content}"
              )

            img_log_str = ""
            if uploaded_img is not None:
              ext = uploaded_img.name.split(".")[-1]
              saved_filename = f"{base_name}.{ext}"
              saved_path = os.path.join(FEEDBACK_IMG_DIR, saved_filename)
              with open(saved_path, "wb") as f_img:
                f_img.write(uploaded_img.getvalue())
              img_log_str = f" | 截圖檔名: {saved_filename}"

            log_activity(
                f"【問題回報】單號:{ticket_id} | 類別:{fb_type} |"
                f" 內容:{clean_content.replace('\n', ' ')}{img_log_str}"
            )

            st.session_state["fb_submitted_id"] = ticket_id
            st.rerun()
          else:
            st.warning("請填寫詳細說明後再送出")
      with col_sb2:
        if st.button(
            "關閉視窗", key="close_fb_btn_1", use_container_width=True
        ):
          st.rerun()

  with tab_my_records:
    st.caption(f"登入組員：{current_unit} ｜ {current_user}")

    my_records = []
    if os.path.exists(FEEDBACK_IMG_DIR):
      for fname in os.listdir(FEEDBACK_IMG_DIR):
        if fname.endswith(".txt"):
          fpath = os.path.join(FEEDBACK_IMG_DIR, fname)
          try:
            with open(fpath, "r", encoding="utf-8") as f:
              content = f.read()
              lines = content.split("\n")
              info = {}
              desc_lines = []
              is_desc = False
              for line in lines:
                if line.startswith("詳細說明:"):
                  is_desc = True
                  continue
                if is_desc:
                  desc_lines.append(line)
                elif ":" in line:
                  k, v = line.split(":", 1)
                  info[k.strip()] = v.strip()
              info["詳細說明"] = "\n".join(desc_lines).strip()

              reporter = info.get("回報者", "")
              user_clean_token = str(current_user).split(" ")[0]
              if (
                  user_clean_token in reporter
                  or reporter in current_user
              ):
                my_records.append(info)
          except Exception:
            pass

    if my_records:
      my_records = sorted(
          my_records, key=lambda x: x.get("時間", ""), reverse=True
      )
      st.write(f"**您的歷史回報（共 {len(my_records)} 筆）**")

      for rec in my_records:
        status = rec.get("狀態", "待處理")
        status_colors = {
            "待處理": ("#F59E0B", "rgba(245, 158, 11, 0.15)"),
            "處理中": ("#38BDF8", "rgba(56, 189, 248, 0.15)"),
            "已完成": ("#34D399", "rgba(52, 211, 153, 0.15)"),
            "已不處理": ("#94A3B8", "rgba(148, 163, 184, 0.15)"),
        }
        txt_color, bg_color = status_colors.get(
            status, ("#F59E0B", "rgba(245, 158, 11, 0.15)")
        )

        st.markdown(
            f"""
                <div style="background: {bg_color}; border: 1px solid {txt_color}; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 13px; font-weight: 800; color: #F8FAFC; font-family: monospace;">{rec.get("處理編號", "未知單號")}</span>
                        <span style="font-size: 12px; font-weight: 800; color: {txt_color}; font-family: monospace;">【{status}】</span>
                    </div>
                    <div style="font-size: 11px; color: #94A3B8; font-family: monospace; margin-top: 4px;">
                        提報時間：{rec.get("時間", "未知")} ｜ 類別：{rec.get("類別", "無")}
                    </div>
                    <div style="font-size: 12px; color: #CBD5E1; font-family: monospace; margin-top: 6px; background: rgba(15, 23, 42, 0.5); padding: 6px 10px; border-radius: 6px;">
                        {rec.get("詳細說明", "")}
                    </div>
                    <div style="margin-top: 6px; font-size: 11.5px; font-family: monospace;">
                        <span style="color: #38BDF8; font-weight: 700;">管理員回覆：</span>
                        <span style="color: #F8FAFC;">{rec.get("管理員回覆", "尚無回覆")}</span>
                    </div>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.info("尚無您的歷史回報紀錄。")


# =========================================================
# 📅 完整月班表檢視彈窗
# =========================================================
@st.dialog("完整月班表檢視", width="large")
def show_crew_schedule_modal(
    emp_input, unit_label, badge_title="Inspector | C.L.F"
):
  try:
    start_dt, dates, emp_id, emp_name, cells = process_file_data(
        emp_input
    )
    with st.spinner(f"正在繪製【{emp_name}】的完整月班表，請稍候..."):
      buf = render_schedule_figure(
          start_dt,
          dates,
          emp_id,
          emp_name,
          cells,
          unit_label,
          badge_title=badge_title,
      )
      st.success(f"已成功載入【{emp_name}】({emp_id}) 之完整月班表")
      render_zoomable_image(buf)
      st.download_button(
          "下載此組員月班表圖檔",
          data=buf,
          file_name=f"{unit_label}_班表_{emp_name}.png",
          mime="image/png",
          key=f"modal_dl_btn_{emp_id}",
      )
  except Exception as e:
    st.error(f"載入完整班表時發生錯誤: {e}")
