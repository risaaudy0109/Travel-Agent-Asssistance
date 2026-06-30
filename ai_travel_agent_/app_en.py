import calendar
import re
from datetime import date
from textwrap import dedent

import requests
import streamlit as st
import streamlit.components.v1 as components

from rag_pipeline import build_rag_pipeline

# ── Page Setup ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Marissa Tour and Travel",
    page_icon="🏝️",
    layout="wide"
)

today = date.today()


# ── Calendar pulled from Google Calendar ──


MONTH_NAMES_SHORT = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG",
                      "SEP", "OCT", "NOV", "DEC"]
DOW_SHORT = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]

GOOGLE_HOLIDAY_ICS_URL = (
    "https://calendar.google.com/calendar/ical/"
    "en.indonesian%23holiday%40group.v.calendar.google.com/public/basic.ics"
)


# ADMIN CONFIG (CHANGE WHATSAPP NUMBER BELOW)

WHATSAPP_ADMIN_URL = "https://wa.me/6285884902785"


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def fetch_indonesian_holidays_all_years() -> dict:
    # Grab all Indonesian holidays from Google Calendar
    try:
        resp = requests.get(GOOGLE_HOLIDAY_ICS_URL, timeout=8)
        resp.raise_for_status()
        ics_text = resp.text
        ics_text = re.sub(r"\r\n[ \t]", "", ics_text)

        holidays = {}
        for block in ics_text.split("BEGIN:VEVENT")[1:]:
            block = block.split("END:VEVENT")[0]
            dt_match = re.search(r"DTSTART(?:;VALUE=DATE)?:(\d{8})", block)
            summary_match = re.search(r"SUMMARY:(.+)", block)
            if not (dt_match and summary_match):
                continue
            dt_str = dt_match.group(1)
            y, m, d = int(dt_str[:4]), int(dt_str[4:6]), int(dt_str[6:8])
            iso = f"{y:04d}-{m:02d}-{d:02d}"
            holidays[iso] = summary_match.group(1).strip()
        return holidays
    except Exception:
        return {}


def get_indonesian_holidays(year: int) -> dict:
    # Filter holidays for a specific year
    all_holidays = fetch_indonesian_holidays_all_years()
    prefix = f"{year:04d}-"
    return {k: v for k, v in all_holidays.items() if k.startswith(prefix)}


def build_calendar_widget_html(year: int, month: int, holidays: dict) -> str:
    # Build the interactive calendar widget HTML
    today_iso = today.strftime("%Y-%m-%d")
    all_months_html = {}

    years_to_render = [year - 1, year, year + 1]
    for yr in years_to_render:
        yr_holidays = {k: v for k, v in holidays.items() if k.startswith(f"{yr:04d}-")}
        cal_obj = calendar.Calendar(firstweekday=6)
        for mo in range(1, 13):
            key = f"{yr:04d}-{mo:02d}"
            weeks = cal_obj.monthdayscalendar(yr, mo)
            rows_html = ""
            for week in weeks:
                cells = ""
                for i, day in enumerate(week):
                    if day == 0:
                        cells += "<span class='bc-cell bc-empty'></span>"
                        continue
                    iso = f"{yr:04d}-{mo:02d}-{day:02d}"
                    cls = "bc-cell"
                    if i == 0:
                        cls += " bc-sunday"
                    holiday_name = yr_holidays.get(iso, "")
                    if holiday_name:
                        cls += " bc-holiday"
                    if iso == today_iso:
                        cls += " bc-today"
                    label_attr = f' data-label="{holiday_name}"' if holiday_name else ""
                    cells += (
                        f"<span class='{cls}'{label_attr} "
                        f"onclick=\"calCellClick(this)\">{day}</span>"
                    )
                rows_html += f"<div class='bc-row'>{cells}</div>"
            all_months_html[key] = rows_html

    import json
    months_json = json.dumps(all_months_html, ensure_ascii=False)

    head_cells = "".join(
        f"<span class='bc-cell bc-head'>{d}</span>" for d in DOW_SHORT
    )

    init_key = f"{year:04d}-{month:02d}"

    html = f"""
<div class="cal-wrap">
  <div class="cal-box" id="calBox">

    <div class="cal-top-row">
      <div class="big-head">
        <div class="big-title" id="calMonthLabel"></div>
        <div class="big-year" id="calYearLabel"></div>
      </div>
      <div class="cal-nav-inner">
        <button class="cal-nav-btn" onclick="calNav(-1)" title="Previous month">&#8249;</button>
        <button class="cal-nav-btn" onclick="calNav(1)" title="Next month">&#8250;</button>
        <button class="cal-nav-btn cal-nav-close" onclick="calNav(0)" title="Jump to today">📍</button>
      </div>
    </div>

    <div class="cal-big">
      <div class="bc-row bc-row-head">{head_cells}</div>
      <div id="calDaysContainer"></div>
      <div class="cal-legend">
        <div class="legend-title">
          <span class="legend-flag"><i class="dot dot-today"></i> Today</span>
          <span class="legend-flag"><i class="dot dot-holiday"></i> Holiday</span>
        </div>
        <div class="legend-title" style="margin-top:14px;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px;font-size:11px;color:#9098A8;">HOLIDAYS THIS MONTH</div>
        <div id="calHolidayList" class="legend-holiday-list">
          <span style="color:#B9AFA0;font-style:italic;font-size:9.5px">Loading…</span>
        </div>
        <div id="calSelectedInfo" class="legend-selected" style="display:none;"></div>
      </div>
    </div>

  </div>
</div>

<!-- Popup tooltip for holiday explanation -->
<div id="calPopup" class="cal-popup" style="display:none;">
  <span id="calPopupText"></span>
  <button class="cal-popup-close" onclick="document.getElementById('calPopup').style.display='none'">&#10005;</button>
</div>

<script>
(function(){{
  var MONTH_NAMES = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];
  var monthsData = {months_json};
  var todayYear  = {today.year};
  var todayMonth = {today.month};
  var curYear  = {year};
  var curMonth = {month};

  function pad(n){{ return String(n).padStart(2,"0"); }}

  var MONTH_NAMES_LONG = ["January","February","March","April","May","June",
                          "July","August","September","October","November","December"];
  var DAY_NAMES = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];

  function renderHolidayList(){{
    var list = document.getElementById("calHolidayList");
    if(!list) return;
    var cells = document.querySelectorAll(".bc-holiday");
    if(cells.length === 0){{
      list.innerHTML = "<span style='color:#B9AFA0;font-style:italic;font-size:9.5px'>No holidays this month</span>";
      return;
    }}
    var html = "";
    cells.forEach(function(el){{
      var label = el.getAttribute("data-label");
      if(!label) return;
      var day = el.textContent.trim();
      html += "<div class='legend-item'>"
            + "<span class='legend-item-date'>" + day + "</span>"
            + "<span class='legend-item-name'>" + label + "</span>"
            + "</div>";
    }});
    list.innerHTML = html || "<span style='color:#B9AFA0;font-style:italic;font-size:9.5px'>No holidays this month</span>";
  }}

  function render(){{
    var key = curYear + "-" + pad(curMonth);
    document.getElementById("calMonthLabel").textContent = "CALENDAR";
    document.getElementById("calYearLabel").textContent =
      MONTH_NAMES_LONG[curMonth-1] + " " + curYear;
    var container = document.getElementById("calDaysContainer");
    container.innerHTML = monthsData[key] ||
      "<div style='font-size:10px;color:#B9AFA0;padding:8px 0;text-align:center'>Data not available</div>";
    var sel = document.getElementById("calSelectedInfo");
    if(sel) sel.style.display = "none";
    renderHolidayList();
  }}

  window.calNav = function(dir){{
    if(dir === 0){{ curYear = todayYear; curMonth = todayMonth; }}
    else{{
      curMonth += dir;
      if(curMonth > 12){{ curMonth = 1; curYear++; }}
      if(curMonth < 1){{ curMonth = 12; curYear--; }}
    }}
    render();
  }};

  window.calCellClick = function(el){{
    var label = el.getAttribute("data-label");
    var sel = document.getElementById("calSelectedInfo");
    if(!label){{
      if(sel) sel.style.display = "none";
      return;
    }}
    var day = el.textContent.trim();
    var d = new Date(curYear, curMonth-1, parseInt(day));
    var dayName = DAY_NAMES[d.getDay()];
    var dateLabel = dayName + ", " + day + " " + MONTH_NAMES_LONG[curMonth-1] + " " + curYear;
    sel.innerHTML = "<span class='legend-selected-icon'>📌</span>"
      + "<div><b>" + dateLabel + "</b><br>" + label + "</div>";
    sel.style.display = "flex";
    var popup = document.getElementById("calPopup");
    if(popup) popup.style.display = "none";
  }};

  document.addEventListener("click", function(e){{
    var popup = document.getElementById("calPopup");
    if(popup && !popup.contains(e.target) && !e.target.hasAttribute("data-label")){{
      popup.style.display = "none";
    }}
  }});

  render();
}})();
</script>
"""
    return html


CALENDAR_CSS = """
<style>
.cal-wrap{
    font-family:'Helvetica Neue',Arial,sans-serif;
    width:100%;
    max-width:100%;

}

.cal-box{
    background:#FFFFFF;
    border-radius:22px;
    padding:22px 24px 18px;
    box-shadow:0 8px 24px rgba(20,20,40,.07);
    border:1px solid #F0F1F5;
    width:100%;
    max-width:380px;
    box-sizing:border-box;
}
.cal-nav-inner{
  display:flex; align-items:center;
  gap:2px;
}
.cal-top-row{
  display:flex; justify-content:space-between; align-items:flex-start;
  margin-bottom:16px;
}
.cal-nav-btn{
  border-radius:8px; width:26px; height:26px; padding:0; font-size:16px;
  font-weight:600; border:none; background:transparent;
  color:#1F2430; cursor:pointer; display:inline-flex;
  align-items:center; justify-content:center; transition:all .15s;
  line-height:1;
}
.cal-nav-btn:hover{ background:#F1F2F6; }
.cal-nav-close{ font-size:12px; color:#6A7281; }
.cal-big{ background:#FFFFFF; border-radius:12px; padding:0; }
.big-head{ display:flex; flex-direction:column; align-items:flex-start; }
.big-title{
  font-size:11px; font-weight:700; letter-spacing:1.5px; color:#9098A8;
  text-transform:uppercase; margin-bottom:1px;
}
.big-year{
  font-size:22px; font-weight:800; color:#161A23; line-height:1.2;
  text-align:left;
}
.bc-row{ display:grid; grid-template-columns:repeat(7,1fr); margin-bottom:4px; }
.bc-cell{
  text-align:center; font-size:14.5px; padding:8px 0; color:#1F2430;
  cursor:default; border-radius:50%; transition:background .1s;
  font-weight:600;
}
.bc-row-head .bc-cell{
  font-size:12px; color:#1F2430; font-weight:700; cursor:default;
  text-transform:capitalize; padding-bottom:10px;
}
.bc-row-head .bc-cell:first-child{ color:#E14B4B; }
.bc-sunday{ color:#E14B4B; font-weight:700; }
.bc-holiday{
  color:#E14B4B !important; font-weight:700; cursor:pointer;
  position:relative;
}
.bc-holiday::after{
  content:""; display:block; width:4px; height:4px; border-radius:50%;
  background:#E14B4B; margin:1px auto 0;
}
.bc-holiday:hover{ background:#FDECEA; border-radius:50%; }
.bc-today{
  background:#161A23 !important; color:#FFFFFF !important;
  border-radius:50%; font-weight:700;
}
.bc-today::after{ display:none; }
.bc-empty{ visibility:hidden; }
.cal-legend{
  margin:14px 0 2px;
  background:transparent; border-radius:0; padding:0;
}
.legend-title{
  font-size:12px; color:#1F2430; font-weight:600;
  margin-bottom:10px; display:flex; align-items:center; gap:14px;
}
.legend-flag{ display:flex; align-items:center; gap:6px; }

.legend-holiday-list::-webkit-scrollbar{
    width:5px;
}

.legend-holiday-list::-webkit-scrollbar-thumb{
    background:#e2e4ea;
    border-radius:20px;
}
.dot{ width:7px; height:7px; border-radius:50%; display:inline-block; margin-right:4px; vertical-align:middle; }
.dot-today{ background:#161A23; }
.dot-holiday{ background:#E14B4B; }
.legend-holiday-list{
  display:flex; flex-direction:column; gap:11px;
  max-height:118px; /* ≈ 3 items, scroll kicks in after 3+ */
  overflow-y:auto; overflow-x:hidden; padding-top:10px; padding-right:4px;
  border-top:1px solid #EEF0F4;
}
.legend-item{
  display:flex; align-items:center; gap:10px;
  font-size:12.5px; color:#1F2430; line-height:1.4;
}
.legend-item-date{
  background:#FDECEA; color:#E14B4B; font-weight:700;
  border-radius:50%; font-size:11px;
  width:22px; height:22px;
  display:inline-flex; align-items:center; justify-content:center;
  flex-shrink:0;
}
.legend-item-name{ color:#3A4150; }
.legend-selected{
  margin-top:10px; padding:9px 11px;
  background:#161A23; color:#FFFFFF;
  border-radius:10px; font-size:11px; line-height:1.5;
  display:flex; align-items:flex-start; gap:6px;
}
.legend-selected-icon{ font-size:13px; flex-shrink:0; }
.cal-popup{
  position:fixed; z-index:9999;
  background:#161A23; color:#FFFFFF;
  font-family:'Helvetica Neue',Arial,sans-serif;
  font-size:11px; padding:6px 10px 6px 12px;
  border-radius:8px; box-shadow:0 4px 14px rgba(0,0,0,.25);
  display:flex; align-items:center; gap:8px; max-width:220px;
  line-height:1.4;
}
.cal-popup-close{
  background:none; border:none; color:#FFFFFF; cursor:pointer;
  font-size:10px; padding:0; opacity:.7; flex-shrink:0;
}
.cal-popup-close:hover{ opacity:1; }
</style>
"""

st.markdown(dedent(CALENDAR_CSS), unsafe_allow_html=True)

# ── Chat UI Styling (ChatEase-inspired) ─────────────────────────────
CHAT_UI_CSS = """
<style>
/* ── Back / New chat button (arrow icon) ── */
.ce-back-wrap{ display:flex; align-items:center; height:100%; }
.ce-back-wrap div[data-testid="stButton"] > button{
    width: 40px !important; height: 40px !important;
    border-radius: 50% !important;
    background: #161A23 !important;
    color: #fff !important;
    border: none !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    padding: 0 !important;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    transition: background .15s;
}
.ce-back-wrap div[data-testid="stButton"] > button:hover{
    background: #2E86C1 !important;
}

/* ── Chat header (Customer Service style) ── */
.ce-cs-header{
    background: linear-gradient(135deg, #1B4E8C 0%, #2E86C1 100%);
    border-radius: 22px 22px 0 0;
    padding: 18px 24px;
    display: flex; align-items: center; gap: 14px;
    color: #fff;
    box-shadow: 0 4px 14px rgba(27,78,140,0.18);
}
.ce-cs-avatar{
    width: 44px; height: 44px; border-radius: 50%;
    background: rgba(255,255,255,0.18);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 15px; flex-shrink: 0;
    position: relative;
}
.ce-cs-avatar .online-dot{
    position: absolute; bottom: -1px; right: -1px;
    width: 12px; height: 12px; border-radius: 50%;
    background: #2ECC71; border: 2px solid #1B4E8C;
}
.ce-cs-title{ font-size: 17px; font-weight: 800; line-height: 1.3; }
.ce-cs-sub{ font-size: 12.5px; color: #cfe4fb; display:flex; align-items:center; gap:5px; }
.ce-cs-sub .dot-online{ width:6px; height:6px; border-radius:50%; background:#2ECC71; display:inline-block; }

/* ── Main panel ── */
.ce-main {
    flex: 1; display: flex; flex-direction: column;
    background: #f7f8fc; min-width: 0;
}

.ce-header-actions { display: flex; gap: 8px; }
.ce-header-btn {
    background: none; border: 1px solid #e8eaf0; border-radius: 8px;
    padding: 5px 13px; font-size: 12px; color: #667; cursor: pointer;
    display: flex; align-items: center; gap: 5px; transition: background .15s;
}
.ce-header-btn:hover { background: #f0f4ff; border-color: #c0c8f0; }

/* ── Messages area ── */
.ce-messages {
    height: calc(100vh - 340px);
    min-height: 260px;
    max-height: 480px;
    overflow-y:auto; padding:24px 28px 16px;
    display: flex; flex-direction: column; gap: 18px;
    background: #fff; border-radius: 0 0 22px 22px;
    box-shadow: 0 8px 24px rgba(20,20,40,.06);
}

/* ── Chat bubbles ── */
.ce-row { display: flex; align-items: flex-end; gap: 10px; }
.ce-row.ce-user-row { flex-direction: row-reverse; }
.ce-bubble-wrap { max-width: 68%; display: flex; flex-direction: column; }
.ce-user-row .ce-bubble-wrap { align-items: flex-end; }

.ce-bubble {
    padding: 12px 16px; border-radius: 18px;
    font-size: 13.5px; line-height: 1.6;
    word-break: break-word;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.ce-admin-bubble {
    background: #F4F5F8; color: #1A1D24;
    border-radius: 4px 18px 18px 18px;
}
.ce-user-bubble {
    background: #161A23;
    color: #fff;
    border-radius: 18px 18px 4px 18px;
}
.ce-sender {
    font-size: 11px; color: #9aa3b2; font-weight: 700;
    margin-bottom: 4px; padding: 0 3px;
}
.ce-user-row .ce-sender { text-align: right; }
.ce-time { font-size: 11px; color: #B3B9C4; margin-top: 4px; padding: 0 3px; }
.ce-user-row .ce-time { text-align: right; }




/* ── New Chat button ── */
.ce-new-chat-btn {
    margin: 10px 18px 0;
}
div[data-testid="stButton"] > button:has(> p:contains("New Chat")) {
    background: linear-gradient(135deg, #4f7ef7, #7c3aed) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    width: 100%;
}

/* ── Quick questions buttons ── */
.ce-quick-questions {
    padding: 14px 28px 6px;
    display: flex; flex-direction: column; gap: 8px;
}
.ce-quick-label {
    font-size: 11px; font-weight: 700; color: #9aa3b2;
    text-transform: uppercase; letter-spacing: .6px;
    margin-bottom: 2px;
}
.ce-quick-btn {
    background: #fff; border: 1px solid #e2e6f3;
    border-radius: 12px; padding: 9px 14px;
    font-size: 12px; color: #2a2e40; cursor: pointer;
    text-align: left; line-height: 1.4;
    transition: background .12s, border-color .12s, box-shadow .12s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.ce-quick-btn:hover {
    background: #f0f4ff; border-color: #4f7ef7;
    box-shadow: 0 2px 8px rgba(79,126,247,0.12);
}

/* ── Empty state (same size as chat bubble box) ── */
.ce-empty {
    flex: 1; display: flex; align-items: center; justify-content: center;
    flex-direction: column; gap: 10px; color: #a0aabb;
    height: calc(100vh - 340px);
    min-height: 260px;
    max-height: 480px;
    border-radius: 22px !important;
}
.ce-empty-icon { font-size: 40px; }
.ce-empty-text { font-size: 16px; font-weight: 700; color: #2A2E40; }
.ce-empty-sub { font-size: 13.5px; color: #9aa3b2; text-align:center; max-width:280px; }

/* ── Quick question buttons (native st.button) ── */
div[data-testid="column"] div[data-testid="stButton"] > button[kind="secondary"]:not(.ce-back-wrap *){
    background: #fff !important;
    border: 1px solid #e2e6f3 !important;
    border-radius: 14px !important;
    padding: 12px 16px !important;
    font-size: 13px !important;
    color: #2a2e40 !important;
    font-weight: 500 !important;
    text-align: left !important;
    box-shadow: 0 2px 8px rgba(20,20,40,0.05) !important;
    transition: background .12s, border-color .12s, box-shadow .12s !important;
    width: 100% !important;
    white-space: normal !important;
    height: auto !important;
}
div[data-testid="column"] div[data-testid="stButton"] > button[kind="secondary"]:hover{
    background: #f0f4ff !important;
    border-color: #4f7ef7 !important;
    box-shadow: 0 2px 10px rgba(79,126,247,0.14) !important;
}

/* ============================================================
   "ChatEase" theme — lavender gradient background + sidebar restyling
   ============================================================ */
html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #c9c6e8 0%, #cdd6ee 45%, #e7d9e8 100%) !important;
    height: 100vh;
    overflow: hidden;
}
[data-testid="stHeader"] { background: transparent !important; height: 0; }
[data-testid="stAppViewContainer"] > .main { padding-top: 6px; height: 100vh; overflow: hidden; }
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 0.5rem !important;
    max-width: 100% !important;
    height: calc(100vh - 10px);
    overflow: hidden;
}

/* ── All columns: cap height & scroll internally if needed ── */
[data-testid="column"] {
    max-height: calc(100vh - 30px);
    overflow-y: auto;
}
[data-testid="column"]::-webkit-scrollbar { width: 6px; }
[data-testid="column"]::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.15); border-radius: 20px; }

/* ── Left column (calendar) ── */
[data-testid="column"]:first-of-type {
    background: #ffffff;
    border-radius: 22px;
    padding: 16px 14px 16px 18px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
    overflow-x: hidden;
    overflow-y: auto;
}

</style>
"""
st.markdown(CHAT_UI_CSS, unsafe_allow_html=True)
st.markdown("""
<style>

/* Big white bottom box - fixed position via JS to align with chat panel */
div[data-testid="stBottom"],
div[data-testid="stBottomBlockContainer"],
.stBottom{
    position: fixed !important;
    bottom: 14px !important;
    z-index: 999 !important;
    margin: 0 !important;
    transition: none !important;
}

/* Input inside - fixed size, no stretching */
[data-testid="stChatInput"]{
    width: 100% !important;
    background: transparent;
}
[data-testid="stChatInputTextArea"],
[data-testid="stChatInput"] textarea{
    min-height: 44px !important;
    max-height: 44px !important;
    height: 44px !important;
    overflow-y: auto !important;
    resize: none !important;
}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBTAA7"
     style="display:none"
     onload="
        (function(){
            var align = function(){
                var cols = document.querySelectorAll('[data-testid=\\'column\\']');
                var bottom = document.querySelector('div[data-testid=\\'stBottom\\']') ||
                             document.querySelector('div[data-testid=\\'stBottomBlockContainer\\']');
                if(!bottom || cols.length < 2) return;
                var chatCol = cols[cols.length - 1];
                var rect = chatCol.getBoundingClientRect();
                bottom.style.left = rect.left + 'px';
                bottom.style.width = rect.width + 'px';
                bottom.style.right = 'auto';
                bottom.style.transform = 'none';
            };
            align();
            setTimeout(align, 80);
            setTimeout(align, 250);
            setTimeout(align, 600);
            window.addEventListener('resize', align);
        })();
     ">
""", unsafe_allow_html=True)

# ── Load RAG Pipeline ────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_pipeline():
    return build_rag_pipeline()

if "pipeline_loaded" not in st.session_state:
    with st.spinner("Please wait..."):
        chain, num_chunks = load_pipeline()
    st.session_state.chain = chain
    st.session_state.num_chunks = num_chunks
    st.session_state.pipeline_loaded = True

chain = st.session_state.chain


# HELPER: Detect unsatisfying answers + offer admin contact

def get_rag_response(query: str):
    """
    Run RAG chain and add an option to contact admin if the answer is unsatisfying.
    """
    result = chain.invoke({"query": query})
    answer = result["result"]
    source_docs = result["source_documents"]

    # Keywords that suggest inability to answer
    unable_keywords = [
        "sorry", "don't have information", "don't know", "not available",
        "not yet", "no data", "can't", "not found", "apologies",
        "i don't have", "i am not sure", "unfortunately"
    ]
    # If no source docs or keywords appear in the answer
    if (not source_docs) or any(kw in answer.lower() for kw in unable_keywords):
        additional = f"""

---
⚠️ **Need more help?**

Feel free to reach out to our admin directly via [WhatsApp]({WHATSAPP_ADMIN_URL}) or wait for the admin to respond here (we'll connect you shortly).
"""
        answer += additional

    return answer, source_docs

# ── Chat History Initialization ──────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Helper ────────────────────────────────────────────────────────────
import datetime as _dt
def _now_str():
    return _dt.datetime.now().strftime("%H:%M")

def render_chat_bubbles(messages):
    if not messages:
        return ""
    parts = ['<div class="ce-messages">']
    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "").replace("<", "&lt;").replace(">", "&gt;")
        ts = msg.get("ts", "")
        if role == "user":
            parts.append(f"""
<div class="ce-row ce-user-row">
  <div class="ce-bubble-wrap">
    <div class="ce-sender">You</div>
    <div class="ce-bubble ce-user-bubble">{content}</div>
    <div class="ce-time">{ts}</div>
  </div>
</div>""")
        else:
            parts.append(f"""
<div class="ce-row">
  <div class="ce-bubble-wrap">
    <div class="ce-sender">Smart Admin</div>
    <div class="ce-bubble ce-admin-bubble">{content}</div>
    <div class="ce-time">{ts}</div>
  </div>
</div>""")
    parts.append("</div>")
    return "".join(parts)


# ── 2-COLUMN LAYOUT ────────────────────────────────────────

col1, col2 = st.columns([1.3, 2.7], gap='large')

# ── COLUMN 1: CALENDAR + INFO ─────────────────────────────
with col1:
    holidays_all = fetch_indonesian_holidays_all_years()
    cal_html = CALENDAR_CSS + dedent(
        build_calendar_widget_html(today.year, today.month, holidays_all)
    )
    components.html(
        cal_html,
        height=880,
        scrolling=True
    )
    if not holidays_all:
        st.caption("⚠️ Holiday data from Google Calendar is currently unavailable.")

# ── COLUMN 2: MAIN CHAT ────────────────────────────────────
with col2:
    # Customer Service-style header (with New Chat arrow button on the left)
    head_col1, head_col2 = st.columns([0.09, 0.91])
    with head_col1:
        st.markdown('<div class="ce-back-wrap">', unsafe_allow_html=True)
        if st.button("➕", key="new_chat_btn", help="Start a new chat"):
            st.session_state.messages = []
            st.session_state.pop("_quick_input", None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with head_col2:
        st.markdown("""
        <div class="ce-cs-header">
            <div class="ce-cs-avatar">CS<span class="online-dot"></span></div>
            <div>
                <div class="ce-cs-title">Smart Admin</div>
                <div class="ce-cs-sub"><span class="dot-online"></span>Online</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Quick Questions (only show if no messages yet) ──
    QUICK_QUESTIONS = [
        "Recommend trips this month",
        "What's included in the Dieng Culture Festival ticket price?",
    ]

    if not st.session_state.messages:
        st.markdown("""
    <div class="ce-quick-questions">
      <div class="ce-quick-label">💡 Quick Questions</div>
    </div>
    """, unsafe_allow_html=True)
        cols_q = st.columns(2)
        for idx, q in enumerate(QUICK_QUESTIONS):
            with cols_q[idx % 2]:
                if st.button(q, key=f"quick_{idx}", use_container_width=True):
                    st.session_state["_quick_input"] = q
                    st.rerun()

    # ── Display Chat History ─────────────────────────────
    if st.session_state.messages:
        st.markdown(render_chat_bubbles(st.session_state.messages), unsafe_allow_html=True)

        # ── Auto-scroll to latest message (reliable via components.html) ──
        # components.html always creates a fresh iframe on each render, so the
        # script inside always runs (not relying on image onload which might
        # not fire again). .ce-messages lives in the parent document, not in
        # this iframe, so we access it via window.parent.document.
        components.html(
            f"""
            <script>
            (function(){{
                function tryScroll(){{
                    try {{
                        var doc = window.parent.document;
                        var els = doc.querySelectorAll('.ce-messages');
                        if(els.length){{
                            var box = els[els.length - 1];
                            box.scrollTop = box.scrollHeight + 1000;
                        }}
                    }} catch(e) {{}}
                }}
                tryScroll();
                setTimeout(tryScroll, 60);
                setTimeout(tryScroll, 200);
                setTimeout(tryScroll, 500);
            }})();
            </script>
            <!-- key: {len(st.session_state.messages)} -->
            """,
            height=0,
        )
    else:
        st.markdown("""
    <div class="ce-messages ce-empty">
      <div class="ce-empty-text">Hey there! 👋</div>
      <div class="ce-empty-sub">Got any travel plans? I'm here to help!</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Chat Input ──────────────────────────────────────────
    # Handle quick question if any
    _auto_input = st.session_state.pop("_quick_input", None)
    if _auto_input:
        ts = _now_str()
        st.session_state.messages.append({"role": "user", "content": _auto_input, "ts": ts})
        with st.spinner("Admin is typing..."):
            answer, source_docs = get_rag_response(_auto_input)
        st.session_state.messages.append({"role": "assistant", "content": answer, "ts": _now_str()})
        with st.expander("📎 View references from the catalog"):
            for i, doc in enumerate(source_docs, 1):
                st.markdown(f"**Reference {i}:**")
                st.text(doc.page_content[:300] + "...")
                st.divider()
        st.rerun()

    # Native Streamlit chat input
with col2:
    user_input = st.chat_input("Where should I go this weekend...")
if user_input:
    ts = _now_str()

    # Save user message
    st.session_state.messages.append({"role": "user", "content": user_input, "ts": ts})

    # Generate response from RAG chain
    with st.spinner("Admin is typing..."):
        answer, source_docs = get_rag_response(user_input)

    st.session_state.messages.append({"role": "assistant", "content": answer, "ts": _now_str()})

    # Show source documents (collapsible)
    with st.expander("📎 View references from the catalog"):
        for i, doc in enumerate(source_docs, 1):
            st.markdown(f"**Reference {i}:**")
            st.text(doc.page_content[:300] + "...")
            st.divider()

    st.rerun()