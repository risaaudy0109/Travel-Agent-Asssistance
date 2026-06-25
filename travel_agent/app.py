# ============================================================
# Travel ADVISOR
# Chatbot Perbandingan Produk untuk Tim Sales & Marketing
# Powered by LangChain + Groq + FAISS
#
# Kalender mini (gaya Travel Advisor) ditampilkan di SIDEBAR, lengkap
# dengan tombol navigasi bulan (◀ ▶) dan tombol "•" untuk kembali ke
# bulan ini. Tanggal merah Indonesia diambil LANGSUNG dari Google
# Calendar (kalender publik resmi Google "Holidays in Indonesia" via
# feed ICS) — tidak ada data libur yang ditulis manual di kode.
#
# INPUT CHAT: menggunakan st.chat_input bawaan Streamlit. Ini berarti
# bar/kotak ketik adalah elemen yang INTERAKTIF (tempat user mengetik
# dan teks yang diketik tampil di dalam bar tersebut, di ATAS area
# chat), sedangkan ikon panah kirim bersifat STATIS — hanya berfungsi
# memicu pengiriman saat ditekan/Enter, bukan tempat mengetik.
#
# CARA MENJALANKAN:
#   pip install streamlit requests
#   streamlit run app.py
# ============================================================

import calendar
import re
from datetime import date
from textwrap import dedent

import requests
import streamlit as st
import streamlit.components.v1 as components

from rag_pipeline import build_rag_pipeline

# ── Konfigurasi Halaman ────────────────────────────────────────────────
st.set_page_config(
    page_title="Bingah Travel",
    page_icon="📱",
    layout="wide"
)

today = date.today()

# ============================================================
# ── KALENDER (gaya Travel Advisor) — diambil dari Google Calendar ──
# ============================================================

MONTH_NAMES_SHORT = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG",
                      "SEP", "OCT", "NOV", "DEC"]
DOW_SHORT = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]  # Minggu di kolom pertama

# Kalender publik resmi Google untuk hari libur Indonesia (feed ICS, tidak
# perlu API key, bisa diakses publik oleh siapa saja).
GOOGLE_HOLIDAY_ICS_URL = (
    "https://calendar.google.com/calendar/ical/"
    "en.indonesian%23holiday%40group.v.calendar.google.com/public/basic.ics"
)


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def fetch_indonesian_holidays_all_years() -> dict:
    """Ambil & parse feed ICS publik Google Calendar 'Holidays in Indonesia'.
    Mengembalikan dict {'YYYY-MM-DD': 'Nama Libur'} untuk semua tahun yang
    ada di feed. Jika gagal mengambil/parsing, mengembalikan dict kosong
    (kalender tetap tampil tanpa highlight merah, tidak ada crash)."""
    try:
        resp = requests.get(GOOGLE_HOLIDAY_ICS_URL, timeout=8)
        resp.raise_for_status()
        ics_text = resp.text
        ics_text = re.sub(r"\r\n[ \t]", "", ics_text)  # gabungkan baris "folded"

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
    """Filter hasil fetch Google Calendar untuk tahun tertentu saja."""
    all_holidays = fetch_indonesian_holidays_all_years()
    prefix = f"{year:04d}-"
    return {k: v for k, v in all_holidays.items() if k.startswith(prefix)}


def build_calendar_widget_html(year: int, month: int, holidays: dict) -> str:
    """Bangun HTML kalender STATIS lengkap dengan:
    - Tombol navigasi ◀ • ▶ di dalam cal-box (murni JavaScript, tidak memicu rerun)
    - Tooltip popup penjelasan nama hari libur saat klik tanggal merah
    - Semua data 12 bulan di-embed sekaligus; navigasi cukup toggle visibilitas
    """
    today_iso = today.strftime("%Y-%m-%d")

    # ── Bangun data semua bulan sebagai blok JSON untuk JavaScript ──────
    # Kita render semua 12 bulan tahun berjalan + tahun sebelum/sesudah
    # agar navigasi terasa mulus tanpa batas.
    # Untuk menjaga ukuran HTML tetap kecil, render ±2 tahun dari tahun aktif.
    all_months_html = {}  # key: "YYYY-MM"

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
                    # data-label untuk popup tooltip
                    label_attr = f' data-label="{holiday_name}"' if holiday_name else ""
                    cells += (
                        f"<span class='{cls}'{label_attr} "
                        f"onclick=\"calCellClick(this)\">{day}</span>"
                    )
                rows_html += f"<div class='bc-row'>{cells}</div>"
            all_months_html[key] = rows_html

    # Serialisasi ke JS-safe JSON (escape hanya karakter kritis)
    import json
    months_json = json.dumps(all_months_html, ensure_ascii=False)

    head_cells = "".join(
        f"<span class='bc-cell bc-head'>{d}</span>" for d in DOW_SHORT
    )

    init_key = f"{year:04d}-{month:02d}"

    html = f"""
<div class="cal-wrap">
  <div class="cal-box" id="calBox">

    <!-- Baris navigasi di dalam cal-box -->
    <div class="cal-nav-inner">
      <button class="cal-nav-btn" onclick="calNav(-1)" title="Bulan sebelumnya">&#9664;</button>
      <button class="cal-nav-btn cal-nav-dot" onclick="calNav(0)" title="Kembali ke bulan ini">&#9679;</button>
      <button class="cal-nav-btn" onclick="calNav(1)" title="Bulan selanjutnya">&#9654;</button>
    </div>

    <div class="cal-big">
      <div class="big-head">
        <div class="big-title" id="calMonthLabel"></div>
        <div class="big-year" id="calYearLabel"></div>
      </div>
      <div class="bc-row bc-row-head">{head_cells}</div>
      <div id="calDaysContainer"></div>
      <div class="cal-legend">
        <div class="legend-title"><i class="dot dot-today"></i> 
        <i class="dot dot-holiday"></i> Libur Bulan Ini:</div>
        <div id="calHolidayList" class="legend-holiday-list">
          <span style="color:#B9AFA0;font-style:italic;font-size:9.5px">Memuat…</span>
        </div>
        <div id="calSelectedInfo" class="legend-selected" style="display:none;"></div>
      </div>
    </div>

  </div>
</div>

<!-- Popup tooltip penjelasan tanggal merah -->
<div id="calPopup" class="cal-popup" style="display:none;">
  <span id="calPopupText"></span>
  <button class="cal-popup-close" onclick="document.getElementById('calPopup').style.display='none'">&#10005;</button>
</div>

<script>
(function(){{
  var MONTH_NAMES = ["JAN","FEB","MAR","APR","MEI","JUN","JUL","AGU","SEP","OKT","NOV","DES"];
  var monthsData = {months_json};
  var todayYear  = {today.year};
  var todayMonth = {today.month};
  var curYear  = {year};
  var curMonth = {month};

  function pad(n){{ return String(n).padStart(2,"0"); }}

  // Nama bulan panjang untuk panel legend
  var MONTH_NAMES_LONG = ["Januari","Februari","Maret","April","Mei","Juni",
                          "Juli","Agustus","September","Oktober","November","Desember"];
  var DAY_NAMES = ["Minggu","Senin","Selasa","Rabu","Kamis","Jumat","Sabtu"];

  function renderHolidayList(){{
    var list = document.getElementById("calHolidayList");
    if(!list) return;
    // Kumpulkan semua tanggal merah (libur) bulan ini dari DOM
    var cells = document.querySelectorAll(".bc-holiday");
    if(cells.length === 0){{
      list.innerHTML = "<span style='color:#B9AFA0;font-style:italic;font-size:9.5px'>Tidak ada libur nasional bulan ini</span>";
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
    list.innerHTML = html || "<span style='color:#B9AFA0;font-style:italic;font-size:9.5px'>Tidak ada libur nasional bulan ini</span>";
  }}

  function render(){{
    var key = curYear + "-" + pad(curMonth);
    document.getElementById("calMonthLabel").textContent = MONTH_NAMES[curMonth-1];
    document.getElementById("calYearLabel").innerHTML =
      String(curYear).slice(0,2) + "<br>" + String(curYear).slice(2);
    var container = document.getElementById("calDaysContainer");
    container.innerHTML = monthsData[key] ||
      "<div style='font-size:10px;color:#B9AFA0;padding:8px 0;text-align:center'>Data tidak tersedia</div>";
    // Sembunyikan info tanggal terpilih saat ganti bulan
    var sel = document.getElementById("calSelectedInfo");
    if(sel) sel.style.display = "none";
    // Render daftar libur
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
    // Sembunyikan popup lama jika ada
    var popup = document.getElementById("calPopup");
    if(popup) popup.style.display = "none";
  }};

  // tutup popup saat klik di luar
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
/* ── Wrapper & Box ── */
.cal-wrap{ font-family:'Helvetica Neue',Arial,sans-serif; max-width:280px; margin:0 auto; }
.cal-box{ background:#EFE9E1; border-radius:16px; padding:10px 12px 12px; }

/* ── Baris navigasi di dalam cal-box ── */
.cal-nav-inner{
  display:flex; justify-content:flex-end; align-items:center;
  gap:4px; margin-bottom:6px;
}
.cal-nav-btn{
  border-radius:50%; width:26px; height:26px; padding:0; font-size:10px;
  font-weight:700; border:1px solid #D8D0C4; background:#FBF7F1;
  color:#2A2724; cursor:pointer; display:inline-flex;
  align-items:center; justify-content:center; transition:all .15s;
  line-height:1;
}
.cal-nav-btn:hover{ background:#2A2724; color:#FBF7F1; border-color:#2A2724; }
.cal-nav-dot{ font-size:8px; }

/* ── Kalender besar ── */
.cal-big{ background:#FBF7F1; border-radius:12px; padding:14px 14px 8px; }
.big-head{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px; }
.big-title{ font-size:28px; font-weight:300; letter-spacing:2px; color:#2A2724; line-height:1; }
.big-year{ font-size:12px; color:#9B9388; text-align:right; line-height:1.3; }

/* ── Grid hari ── */
.bc-row{ display:grid; grid-template-columns:repeat(7,1fr); margin-bottom:4px; }
.bc-cell{
  text-align:center; font-size:11.5px; padding:4px 0; color:#2A2724;
  cursor:default; border-radius:50%; transition:background .1s;
}
.bc-row-head .bc-cell{ font-size:10px; color:#B9AFA0; font-weight:600; cursor:default; }
.bc-sunday{ color:#D9785A; }
.bc-holiday{
  color:#D6402F !important; font-weight:700; position:relative; cursor:pointer;
}
.bc-holiday::after{
  content:""; display:block; width:4px; height:4px; border-radius:50%;
  background:#D6402F; margin:1px auto 0;
}
.bc-holiday:hover{ background:#FDECEA; border-radius:50%; }
.bc-today{ background:#2A2724; color:#FBF7F1 !important; border-radius:50%; font-weight:700; }
.bc-empty{ visibility:hidden; }

/* ── Legend ── */
.cal-legend{
  margin:10px 0 2px;
  background:#F3EDE5; border-radius:10px; padding:9px 10px;
}
.legend-title{
  font-size:9.5px; color:#9B9388; font-weight:600;
  margin-bottom:6px; display:flex; align-items:center; gap:4px;
}
.dot{ width:7px; height:7px; border-radius:50%; display:inline-block; margin-right:2px; vertical-align:middle; }
.dot-today{ background:#2A2724; }
.dot-holiday{ background:#D6402F; }

.legend-holiday-list{
  display:flex; flex-direction:column; gap:4px; max-height:120px;
  overflow-y:auto;
}
.legend-item{
  display:flex; align-items:flex-start; gap:6px;
  font-size:9.5px; color:#2A2724; line-height:1.4;
}
.legend-item-date{
  background:#D6402F; color:#fff; font-weight:700;
  border-radius:5px; font-size:9.5px;
  width:22px; height:22px;
  display:inline-flex; align-items:center; justify-content:center;
  flex-shrink:0; margin-top:1px;
}
.legend-item-name{ color:#4A3F35; }

.legend-selected{
  margin-top:7px; padding:7px 9px;
  background:#2A2724; color:#FBF7F1;
  border-radius:8px; font-size:9.5px; line-height:1.5;
  display:flex; align-items:flex-start; gap:6px;
}
.legend-selected-icon{ font-size:13px; flex-shrink:0; }

/* ── Popup penjelasan tanggal merah ── */
.cal-popup{
  position:fixed; z-index:9999;
  background:#2A2724; color:#FBF7F1;
  font-family:'Helvetica Neue',Arial,sans-serif;
  font-size:11px; padding:6px 10px 6px 12px;
  border-radius:8px; box-shadow:0 4px 14px rgba(0,0,0,.25);
  display:flex; align-items:center; gap:8px; max-width:220px;
  line-height:1.4;
}
.cal-popup-close{
  background:none; border:none; color:#FBF7F1; cursor:pointer;
  font-size:10px; padding:0; opacity:.7; flex-shrink:0;
}
.cal-popup-close:hover{ opacity:1; }
</style>
"""

st.markdown(dedent(CALENDAR_CSS), unsafe_allow_html=True)

# ── CSS Tampilan Chat Bergaya ChatEase ─────────────────────────────────
CHAT_UI_CSS = """
<style>

/* ── Panel tengah ── */
.ce-main {
    flex: 1; display: flex; flex-direction: column;
    background: #f7f8fc; min-width: 0;
}
.ce-main-header {
    padding: 18px 24px 14px;
    font-size: 18px; font-weight: 700; color: #1a1a2e;
    border-bottom: 1px solid #eef0f5;
    background: #fff;
    display: flex; align-items: center; justify-content: space-between;
}
.ce-header-actions { display: flex; gap: 8px; }
.ce-header-btn {
    background: none; border: 1px solid #e8eaf0; border-radius: 8px;
    padding: 5px 13px; font-size: 12px; color: #667; cursor: pointer;
    display: flex; align-items: center; gap: 5px; transition: background .15s;
}
.ce-header-btn:hover { background: #f0f4ff; border-color: #c0c8f0; }

/* ── Area pesan ── */
.ce-messages {
    flex: 1; overflow-y: auto; padding: 24px 28px 16px;
    display: flex; flex-direction: column; gap: 18px;
}

/* ── Bubble ── */
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
    background: #fff; color: #1a1a2e;
    border-radius: 4px 18px 18px 18px;
}
.ce-user-bubble {
    background: linear-gradient(135deg, #4f7ef7, #7c3aed);
    color: #fff;
    border-radius: 18px 18px 4px 18px;
}
.ce-sender {
    font-size: 10.5px; color: #9aa3b2; font-weight: 600;
    margin-bottom: 3px; padding: 0 3px;
}
.ce-user-row .ce-sender { text-align: right; }
.ce-time { font-size: 10px; color: #b0bac8; margin-top: 4px; padding: 0 3px; }
.ce-user-row .ce-time { text-align: right; }

/* ── Panel riwayat kanan ── */
.ce-history {
    width: 220px; min-width: 220px;
    background: #f7f8fc; border-left: 1px solid #eef0f5;
    display: flex; flex-direction: column;
    padding: 20px 0 16px;
}
.ce-history-title {
    font-size: 14px; font-weight: 800; color: #1a1a2e;
    padding: 0 18px 14px;
    border-bottom: 1px solid #eef0f5;
    margin-bottom: 6px;
}
.ce-history-list { flex: 1; overflow-y: auto; }
.ce-history-item {
    padding: 9px 18px; cursor: pointer;
    transition: background .12s;
    border-left: 3px solid transparent;
}
.ce-history-item:hover { background: #eef1fb; border-left-color: #4f7ef7; }
.ce-history-item-title {
    font-size: 12px; font-weight: 600; color: #2a2e40;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.ce-history-item-sub {
    font-size: 10.5px; color: #9aa3b2; margin-top: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ── Tombol New Chat di bawah History ── */

/* ── Tombol pertanyaan cepat ── */
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

/* ── Placeholder kosong ── */
.ce-empty {
    flex: 1; display: flex; align-items: center; justify-content: center;
    flex-direction: column; gap: 10px; color: #a0aabb;
}
.ce-empty-icon { font-size: 40px; }
.ce-empty-text { font-size: 13px; font-weight: 600; color: #667; }
.ce-empty-sub { font-size: 12px; color: #a0aabb; }

/* ============================================================
   TEMA "ChatEase" — background gradient lavender + restyle sidebar
   ============================================================ */
html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #c9c6e8 0%, #cdd6ee 45%, #e7d9e8 100%) !important;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stAppViewContainer"] > .main { padding-top: 6px; }
.block-container { padding-top: 1rem !important; max-width: 1100px; }

/* ── Sidebar putih membulat ala ChatEase ── */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-radius: 0 22px 22px 0;
    padding-top: 6px;
}
[data-testid="stSidebar"] > div { padding: 14px 6px 18px; }

/* Brand row: logo bulat hitam "X" + nama app */
.ce-brand-row {
    display: flex; align-items: center; gap: 10px;
    padding: 6px 10px 18px;
}
.ce-brand-logo {
    width: 34px; height: 34px; border-radius: 50%;
    background: #15151f; color: #fff; display: flex;
    align-items: center; justify-content: center; font-weight: 800; font-size: 15px;
    flex-shrink: 0;
}
.ce-brand-name { font-size: 17px; font-weight: 800; color: #15151f; }

/* Menu navigasi statis */
.ce-nav { display: flex; flex-direction: column; gap: 2px; padding: 6px 6px 16px; }
.ce-nav-item {
    display: flex; align-items: center; gap: 11px;
    padding: 9px 12px; border-radius: 10px; font-size: 13.5px;
    color: #4b4f63; font-weight: 600; cursor: pointer; transition: background .12s;
}
.ce-nav-item:hover { background: #f1f2fb; }
.ce-nav-icon { font-size: 15px; width: 18px; text-align: center; }

/* Kartu promo (Premium Plan) */
.ce-promo-card {
    margin: 10px 8px; padding: 16px 16px 18px;
    background: linear-gradient(160deg, #6f7bf7 0%, #4f7ef7 60%, #3f6df0 100%);
    border-radius: 16px; color: #fff;
}
.ce-promo-title { font-size: 14.5px; font-weight: 800; margin-bottom: 6px; }
.ce-promo-sub { font-size: 11.5px; line-height: 1.5; opacity: .92; margin-bottom: 12px; }

/* Tombol logout statis di paling bawah sidebar */
.ce-logout-row {
    display: flex; align-items: center; gap: 11px;
    padding: 9px 18px; margin-top: 4px; font-size: 13px;
    color: #6b7080; font-weight: 600;
}

/* ── Header utama (kartu putih di atas area chat) ── */

.ce-page-title { font-size: 18px; font-weight: 800; color: #15151f; }
.ce-page-actions { display: flex; gap: 8px; }
.ce-page-btn {
    border: 1px solid #e7e8f2; background: #fafafe; border-radius: 9px;
    padding: 6px 13px; font-size: 12px; font-weight: 600; color: #4b4f63;
    display: flex; align-items: center; gap: 6px;
}

/* ── Chip aksi di atas kotak input chat ── */
.ce-action-chips { display: flex; gap: 8px; margin: 10px 0 8px; flex-wrap: wrap; }
.ce-chip {
    border: 1px solid #e7e8f2; background: #fff; border-radius: 999px;
    padding: 6px 14px; font-size: 12px; font-weight: 600; color: #4b4f63;
}

/* ── Bungkus chat_input bawaan Streamlit agar mirip pill ChatEase ── */
[data-testid="stChatInput"] {
    background: #fff; border-radius: 16px;
    box-shadow: 0 2px 10px rgba(30,30,60,0.06);
    border: 1px solid #eef0f5;
}

/* ── Styling tombol Streamlit agar mirip quick-btn ── */
div[data-testid="stButton"] > button[kind="secondary"] {
    background: #fff !important;
    border: 1px solid #e2e6f3 !important;
    border-radius: 12px !important;
    color: #2a2e40 !important;
    font-size: 12px !important;
    text-align: left !important;
    padding: 9px 14px !important;
    transition: background .12s, border-color .12s !important;
}
div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: #f0f4ff !important;
    border-color: #4f7ef7 !important;
}
/* New Chat button distinct style */
button[data-testid="baseButton-secondary"][aria-label*="New Chat"],
div[data-testid="stButton"]:has(> button p:contains("New Chat")) > button {
    background: linear-gradient(135deg, #4f7ef7, #7c3aed) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
}
</style>

"""
st.markdown(CHAT_UI_CSS, unsafe_allow_html=True)

# ── ChatEase wrapper dibuka di sini, ditutup setelah input ─────────────

# ── Load RAG Pipeline ──────────────────────────────────────────────────
# Menggunakan st.cache_resource agar pipeline hanya dibangun sekali.
# Tanpa ini, pipeline akan dibangun ulang setiap ada interaksi pengguna.
@st.cache_resource(show_spinner=False)
def load_pipeline():
    return build_rag_pipeline()

# Tampilkan proses loading kepada pengguna
if "pipeline_loaded" not in st.session_state:
    with st.spinner("Silakan tunggu..."):
        chain, num_chunks = load_pipeline()

    st.session_state.chain = chain
    st.session_state.num_chunks = num_chunks
    st.session_state.pipeline_loaded = True

chain = st.session_state.chain

# ── Inisialisasi Riwayat Chat ──────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Header utama (kartu putih) ala ChatEase ───────────────────────────


# ── Tampilkan Contoh Pertanyaan (hanya saat belum ada chat) ───────────
# ── Tampilkan Contoh Pertanyaan sebagai tombol yang dapat diklik ────────
QUICK_QUESTIONS = [
    "Rekomendasikan trip bulan ini",
    "Harga tiket Dieng Culture Festival sudah termasuk apa saja?",
]

if not st.session_state.messages:
    st.markdown("""
<div class="ce-quick-questions">
  <div class="ce-quick-label">💡 Pertanyaan Cepat</div>
</div>
""", unsafe_allow_html=True)
    cols = st.columns(2)
    for idx, q in enumerate(QUICK_QUESTIONS):
        with cols[idx % 2]:
            if st.button(q, key=f"quick_{idx}", use_container_width=True):
                st.session_state["_quick_input"] = q
                st.rerun()


# ── Tampilkan Riwayat Chat (gaya ChatEase) ────────────────────────────
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
    <div class="ce-sender">Anda</div>
    <div class="ce-bubble ce-user-bubble">{content}</div>
    <div class="ce-time">{ts}</div>
  </div>
</div>""")
        else:
            parts.append(f"""
<div class="ce-row">
  <div class="ce-bubble-wrap">
    <div class="ce-sender">Admin · Smartphone Advisor</div>
    <div class="ce-bubble ce-admin-bubble">{content}</div>
    <div class="ce-time">{ts}</div>
  </div>
</div>""")
    parts.append("</div>")
    return "".join(parts)

# Tampilkan pesan atau placeholder kosong
if st.session_state.messages:
    st.markdown(render_chat_bubbles(st.session_state.messages), unsafe_allow_html=True)
else:
    st.markdown("""
<div class="ce-messages ce-empty">
  <div class="ce-empty-icon">💬</div>
  <div class="ce-empty-text">Mulai percakapan!</div>
  <div class="ce-empty-sub">Tanyakan tentang produk smartphone kepada admin.</div>
</div>
""", unsafe_allow_html=True)

# Action chips + input bar dekoratif
st.markdown("""

""", unsafe_allow_html=True)

# Riwayat panel kanan
history_items = ""
for msg in reversed(st.session_state.messages[-10:]):
    if msg["role"] == "user":
        snippet = msg["content"][:40] + ("…" if len(msg["content"]) > 40 else "")
        history_items += f"""
<div class="ce-history-item">
  <div class="ce-history-item-title">🗂 {snippet}</div>
  <div class="ce-history-item-sub">{msg.get('ts','')}</div>
</div>"""

if not history_items:
    history_items = "<div style='padding:16px 18px;font-size:11px;color:#b0bac8;font-style:italic'>Belum ada riwayat</div>"

st.markdown(f"""
  <!-- Panel riwayat kanan -->
  <div class="ce-history">
    <div class="ce-history-title">History</div>
    <div class="ce-history-list">{history_items}</div>
    <div class="ce-history-footer">
  </div>

</div>
<!-- /chatease-wrap -->
""", unsafe_allow_html=True)

# ── Tombol New Chat (bawah panel History via Streamlit) ───────────────
# Ditempatkan di luar HTML agar bisa memicu st.rerun
col_nc, _ = st.columns([1, 3])
with col_nc:
    if st.button("➕ New Chat", key="new_chat_btn", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("_quick_input", None)
        st.rerun()

# ── Proses pertanyaan cepat jika dipilih ─────────────────────────────
_auto_input = st.session_state.pop("_quick_input", None)

if _auto_input:
    ts = _now_str()
    st.session_state.messages.append({"role": "user", "content": _auto_input, "ts": ts})
    with st.spinner("Admin sedang mengetik..."):
        result = chain.invoke({"query": _auto_input})
        answer = result["result"]
        source_docs = result["source_documents"]
    st.session_state.messages.append({"role": "assistant", "content": answer, "ts": _now_str()})
    with st.expander("📎 Lihat referensi dari katalog"):
        for i, doc in enumerate(source_docs, 1):
            st.markdown(f"**Referensi {i}:**")
            st.text(doc.page_content[:300] + "...")
            st.divider()
    st.rerun()

# Chip aksi dekoratif di atas input chat


if user_input := st.chat_input("weekend ini enaknya ke mana ya..."):
    ts = _now_str()

    # Simpan pesan user
    st.session_state.messages.append({"role": "user", "content": user_input, "ts": ts})

    # Generate jawaban dari RAG chain
    with st.spinner("Admin sedang mengetik..."):
        result = chain.invoke({"query": user_input})
        answer = result["result"]
        source_docs = result["source_documents"]

    st.session_state.messages.append({"role": "assistant", "content": answer, "ts": _now_str()})

    # Tampilkan referensi dokumen sumber (bisa di-collapse)
    with st.expander("📎 Lihat referensi dari katalog"):
        for i, doc in enumerate(source_docs, 1):
            st.markdown(f"**Referensi {i}:**")
            st.text(doc.page_content[:300] + "...")
            st.divider()

    st.rerun()


# ── Sidebar ────────────────────────────────────────────────────────────
with st.sidebar:
    # ── Brand row, menu navigasi & kartu promo ala ChatEase ─────────────


    # ── Kalender mini — navigasi murni JavaScript (tidak memicu st.rerun) ──
    # Tombol ◀ • ▶ berada di dalam cal-box dan dikontrol lewat JS.
    # Semua data bulan (±1 tahun) di-embed langsung ke HTML sehingga
    # perpindahan bulan instan tanpa komunikasi ke server Streamlit.
    st.subheader("📅 Kalender")

    # Ambil semua hari libur dari feed ICS Google Calendar sekali saja
    holidays_all = fetch_indonesian_holidays_all_years()

    # st.components.v1.html() dipakai (bukan st.markdown) karena
    # st.markdown membuang tag <script> demi keamanan, sehingga
    # JavaScript navigasi tidak pernah berjalan.
    cal_html = CALENDAR_CSS + dedent(
        build_calendar_widget_html(today.year, today.month, holidays_all)
    )
    components.html(cal_html, height=400, scrolling=False)
    if not holidays_all:
        st.caption("⚠️ Data tanggal merah dari Google Calendar tidak bisa diambil saat ini.")

    st.divider()

    st.header("📋 Tentang Aplikasi")
    st.markdown(
        "Aplikasi ini menggunakan teknologi **RAG** "
        "_(Retrieval-Augmented Generation)_ untuk menjawab "
        "pertanyaan berdasarkan katalog produk resmi.\n\n"
        "Jawaban didasarkan **hanya** pada dokumen katalog, "
        "bukan pengetahuan umum AI."
    )

    st.divider()


    if st.button("🔄 Reset Percakapan", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("""
<div class="ce-logout-row">⚙️ Log out</div>
""", unsafe_allow_html=True)
