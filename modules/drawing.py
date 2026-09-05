import io
import os
from datetime import date, datetime, timedelta
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from config import (
    C_DO_BG,
    C_DO_TXT,
    C_EMPTY,
    C_HDR,
    C_HOLI_TXT,
    C_NOTE_TXT,
    C_OT_TXT,
    C_PAY_BG,
    C_PAY_TXT,
    C_TOWN_BG,
    C_TOWN_TXT,
    C_WEEKEND_BG,
    C_WORK_BG,
    NATIONAL_HOLIDAYS,
    TAIWAN_TZ,
    TITLE,
    TRANSPORT_PERIODS,
)
from modules.utils import is_overtime, is_town_shift

matplotlib.use("Agg")


def setup_font():
  font_path = "NotoSansTC.ttf"
  if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    return fm.FontProperties(fname=font_path)
  return None


def draw_bold_text(ax, x, y, text, **kwargs):
  ax.text(x, y, text, **kwargs)
  offset = 0.00035
  ax.text(x + offset, y, text, **kwargs)
  ax.text(x, y + offset, text, **kwargs)
  ax.text(x - offset, y, text, **kwargs)
  ax.text(x, y - offset, text, **kwargs)


def parse_transport_periods(raw_periods, year=2026):
  expanded = {}
  for k, v in raw_periods.items():
    if "-" in k:
      parts = k.split("-")
      s_m, s_d = map(int, parts[0].strip().split("/"))
      e_m, e_d = map(int, parts[1].strip().split("/"))
      cur = date(year, s_m, s_d)
      end_dt = date(year, e_m, e_d)
      while cur <= end_dt:
        expanded[f"{cur.month}/{cur.day}"] = v
        cur += timedelta(days=1)
    else:
      expanded[k.strip()] = v
  return expanded


def build_weeks(start_dt, dates, cells):
  from modules.utils import parse_cell

  first_wd = (start_dt.weekday() + 1) % 7
  weeks, week = [], [None] * first_wd
  for dt, raw in zip(dates, cells):
    week.append(
        (dt, parse_cell(raw), str(raw) if not str(raw) == "nan" else "")
    )
    if len(week) == 7:
      weeks.append(week)
      week = []
  if week:
    while len(week) < 7:
      week.append(None)
    weeks.append(week)
  return weeks


def render_schedule_figure(
    start_dt,
    dates,
    emp_id,
    emp_name,
    cells,
    unit_label,
    badge_title="Producer | C.L.F",
):
  active_transport = parse_transport_periods(TRANSPORT_PERIODS)
  font_prop = setup_font()

  def fp(size=9):
    return (
        fm.FontProperties(fname=font_prop.get_file(), size=size)
        if font_prop
        else fm.FontProperties(size=size)
    )

  weeks = build_weeks(start_dt, dates, cells)
  fig, ax = plt.subplots(figsize=(16, 11), dpi=300)
  ax.set_xlim(0, 1)
  ax.set_ylim(0, 1)
  ax.axis("off")
  fig.patch.set_facecolor("white")
  ML, MR, MT, MB, TH, DH = 0.015, 0.015, 0.015, 0.08, 0.09, 0.055
  TW, CW = 1.0 - ML - MR, (1.0 - ML - MR) / 7
  RH = (1.0 - MT - MB - TH - DH) / len(weeks)
  ty = 1.0 - MT - TH
  ax.add_patch(
      FancyBboxPatch(
          (ML, ty),
          TW,
          TH,
          boxstyle="square,pad=0",
          linewidth=0,
          facecolor=C_HDR,
      )
  )

  draw_bold_text(
      ax,
      ML + 0.008,
      ty + TH * 0.58,
      TITLE,
      ha="left",
      va="center",
      color="#FFFFFF",
      fontproperties=fp(16),
  )
  draw_bold_text(
      ax,
      ML + 0.008,
      ty + TH * 0.25,
      f"UNIT // {unit_label}    CREW ID // {emp_id}    OPERATOR // {emp_name} "
      f"   TIMELINE // {dates[0]} ~ {dates[-1]}",
      ha="left",
      va="center",
      color="#CBD5E1",
      fontproperties=fp(11),
  )

  badge_w = CW * 0.90
  badge_x = (1.0 - MR) - CW + (CW - badge_w) / 2
  badge_y = ty + TH * 0.42
  badge_h = 0.035

  ax.add_patch(
      FancyBboxPatch(
          (badge_x, badge_y),
          badge_w,
          badge_h,
          boxstyle="round,pad=0.002,rounding_size=0.01",
          linewidth=1.0,
          edgecolor="#334155",
          facecolor="#1E293B",
      )
  )
  draw_bold_text(
      ax,
      badge_x + badge_w / 2,
      badge_y + badge_h / 2,
      badge_title,
      ha="center",
      va="center",
      color="#38BDF8",
      fontproperties=fp(10.5),
  )

  dy = ty - DH
  for c in range(7):
    x = ML + c * CW
    ax.add_patch(
        FancyBboxPatch(
            (x, dy),
            CW,
            DH,
            boxstyle="square,pad=0",
            linewidth=1.0,
            edgecolor="#475569",
            facecolor="#94A3B8",
        )
    )
    draw_bold_text(
        ax,
        x + CW / 2,
        dy + DH / 2,
        [
            "SUN 星期日",
            "MON 星期一",
            "TUE 星期二",
            "WED 星期三",
            "THU 星期四",
            "FRI 星期五",
            "SAT 星期六",
        ][c],
        ha="center",
        va="center",
        color="#000000",
        fontproperties=fp(11),
    )

  has_emp_do, has_emp_pay, has_emp_ot, has_emp_town = (
      False,
      False,
      False,
      False,
  )
  for week in weeks:
    for item in week:
      if item is not None:
        dt, d, raw_cell_str = item
        tr, note, hours = d["train"], d.get("note", ""), d.get("hours", "")
        is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d[
            "start"
        ]
        if is_pure_hol or tr.startswith("DO"):
          has_emp_do = True
        elif (
            tr in ["PAY", "FAC"]
            or "PAY" in raw_cell_str
            or "FAC" in raw_cell_str
        ):
          has_emp_pay = True
        elif is_town_shift(tr, note):
          has_emp_town = True
        if is_overtime(hours, tr, note):
          has_emp_ot = True

  for ri, week in enumerate(weeks):
    ry = dy - (ri + 1) * RH
    for ci, item in enumerate(week):
      x = ML + ci * CW
      if item is None:
        ax.add_patch(
            FancyBboxPatch(
                (x, ry),
                CW,
                RH,
                boxstyle="square,pad=0",
                linewidth=1.0,
                edgecolor="#64748B",
                facecolor=C_EMPTY,
            )
        )
        continue
      dt, d, raw_cell_str = item
      tr, note = d["train"], d.get("note", "")

      is_pure_hol = ("DO" in raw_cell_str or "D2W" in raw_cell_str) and not d[
          "start"
      ]
      is_pay_shift = (
          (tr in ["PAY", "FAC"])
          or ("PAY" in raw_cell_str)
          or ("FAC" in raw_cell_str)
      )

      bg = (
          C_DO_BG
          if is_pure_hol
          else (
              C_PAY_BG
              if is_pay_shift
              else (
                  C_TOWN_BG
                  if is_town_shift(tr, note)
                  else (C_WEEKEND_BG if ci in [0, 6] else C_WORK_BG)
              )
          )
      )
      ax.add_patch(
          FancyBboxPatch(
              (x, ry),
              CW,
              RH,
              boxstyle="square,pad=0",
              linewidth=1.0,
              edgecolor="#64748B",
              facecolor=bg,
          )
      )

      if dt in NATIONAL_HOLIDAYS:
        full_date_str = f"{dt} ({NATIONAL_HOLIDAYS[dt]})"
        draw_bold_text(
            ax,
            x + 0.005,
            ry + RH - 0.004,
            full_date_str,
            ha="left",
            va="top",
            color=C_HOLI_TXT,
            fontproperties=fp(11),
        )
      else:
        draw_bold_text(
            ax,
            x + 0.005,
            ry + RH - 0.004,
            dt,
            ha="left",
            va="top",
            color="#000000",
            fontproperties=fp(11.5),
        )

      if dt in active_transport:
        draw_bold_text(
            ax,
            x + CW - 0.004,
            ry + RH - 0.004,
            active_transport[dt],
            ha="right",
            va="top",
            color="#7C3AED",
            fontproperties=fp(10.5),
        )

      # --- 【右下角】預估總工時 ---
      if d.get("hours"):
        draw_bold_text(
            ax,
            x + CW - 0.004,
            ry + 0.003,
            f"({d['hours']})",
            ha="right",
            va="bottom",
            color=(
                C_OT_TXT
                if is_overtime(d["hours"], tr, note)
                else "#000000"
            ),
            fontproperties=fp(11.5),
        )

      # --- 【左下角】DO2W / D2W / DO3W 等國定/輪休出勤標籤 ---
      do_match = next(
          (
              l
              for l in raw_cell_str.split("\n")
              if "DO" in l or "D2W" in l or "PAY" in l or "FAC" in l or "OGC" in l
          ),
          "",
      )
      if do_match and do_match != tr and not is_pure_hol:
        draw_bold_text(
            ax,
            x + 0.005,
            ry + 0.003,
            do_match,
            ha="left",
            va="bottom",
            color=C_DO_TXT,
            fontproperties=fp(11.5),
        )

      cx = x + CW / 2
      if is_pure_hol:
        do_code = next(
            (
                l
                for l in raw_cell_str.split("\n")
                if "DO" in l or "D2W" in l
            ),
            "DO",
        )
        draw_bold_text(
            ax,
            cx,
            ry + RH * 0.48,
            do_code,
            ha="center",
            va="center",
            color=C_DO_TXT,
            fontproperties=fp(18),
        )
      elif is_pay_shift and not d["start"]:
        draw_bold_text(
            ax,
            cx,
            ry + RH * 0.48,
            tr,
            ha="center",
            va="center",
            color=C_PAY_TXT,
            fontproperties=fp(18),
        )
      else:
        # 💡 關鍵點：將 "無"、"nan"、"None" 或空白處改為顯示 "--"
        display_tr = "--" if tr in ["無", "nan", "None", ""] else tr

        draw_bold_text(
            ax,
            cx,
            ry + RH * 0.65,
            d["start"],
            ha="center",
            va="center",
            color="#000000",
            fontproperties=fp(17.5),
        )
        draw_bold_text(
            ax,
            cx,
            ry + RH * 0.40,
            d["end"],
            ha="center",
            va="center",
            color="#000000",
            fontproperties=fp(17.5),
        )
        draw_bold_text(
            ax,
            cx,
            ry + RH * 0.15,
            display_tr,
            ha="center",
            va="center",
            color=C_PAY_TXT if is_pay_shift else "#000000",
            fontproperties=fp(15.5),
        )

  legend_y = MB * 0.45
  badge_w_leg, badge_h_leg = CW * 0.90, 0.022
  has_active_transport = any(d in active_transport for d in dates)
  has_active_holiday = any(d in NATIONAL_HOLIDAYS for d in dates)

  pill_legends = [
      (0, "#F1F5F9", "#475569", C_NOTE_TXT, "備註"),
      (
          1,
          C_DO_BG if has_emp_do else C_WORK_BG,
          "#E11D48" if has_emp_do else "#64748B",
          C_DO_TXT if has_emp_do else "#64748B",
          "休假日",
      ),
      (
          2,
          C_PAY_BG if has_emp_pay else C_WORK_BG,
          "#EA580C" if has_emp_pay else "#64748B",
          C_PAY_TXT if has_emp_pay else "#64748B",
          "特休",
      ),
      (
          3,
          C_WORK_BG,
          "#DC2626" if has_emp_ot else "#64748B",
          C_OT_TXT if has_emp_ot else "#64748B",
          "工時 > 8.5h",
      ),
      (
          4,
          C_WORK_BG,
          "#C2410C" if has_active_holiday else "#64748B",
          C_HOLI_TXT if has_active_holiday else "#64748B",
          "國定假日",
      ),
      (
          5,
          "#F3E8FF" if has_active_transport else C_WORK_BG,
          "#7C3AED" if has_active_transport else "#64748B",
          C_NOTE_TXT if has_active_transport else "#64748B",
          "疏運",
      ),
      (
          6,
          C_TOWN_BG if has_emp_town else C_WORK_BG,
          "#334155" if has_emp_town else "#64748B",
          C_TOWN_TXT if has_emp_town else "#64748B",
          "非正線勤務",
      ),
  ]

  for col_idx, bg_clr, border_clr, txt_clr, label in pill_legends:
    col_x = ML + col_idx * CW
    lx = col_x + (CW - badge_w_leg) / 2
    badge = FancyBboxPatch(
        (lx, legend_y),
        badge_w_leg,
        badge_h_leg,
        boxstyle="round,pad=0.002,rounding_size=0.008",
        linewidth=1.2,
        edgecolor=border_clr,
        facecolor=bg_clr,
    )
    ax.add_patch(badge)
    draw_bold_text(
        ax,
        lx + badge_w_leg / 2,
        legend_y + badge_h_leg / 2,
        label,
        ha="center",
        va="center",
        color=txt_clr,
        fontproperties=fp(9),
    )

  now_str = datetime.now(TAIWAN_TZ).strftime("%Y-%m-%d %H:%M")
  draw_bold_text(
      ax,
      ML,
      MB * 0.12,
      "DESIGNED BY: C.L.F // v4.20",
      ha="left",
      va="bottom",
      color="#0F172A",
      fontproperties=fp(12),
  )
  draw_bold_text(
      ax,
      1.0 - MR,
      MB * 0.12,
      f"GENERATED: {now_str}",
      ha="right",
      va="bottom",
      color="#0F172A",
      fontproperties=fp(12),
  )

  buf = io.BytesIO()
  plt.tight_layout(pad=0)
  plt.savefig(
      buf,
      format="png",
      dpi=300,
      bbox_inches="tight",
      facecolor="white",
      pad_inches=0.1,
  )
  buf.seek(0)
  plt.close(fig)
  return buf
