# ============================================================
# SMARTPHONE ADVISOR
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
    page_title="Smartphone Advisor",
    page_icon="📱",
    layout="centered"
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
        <span><i class="dot dot-today"></i> Hari ini</span>
        <span><i class="dot dot-holiday"></i> Tanggal merah (hari libur nasional / Minggu)</span>
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

  function render(){{
    var key = curYear + "-" + pad(curMonth);
    document.getElementById("calMonthLabel").textContent = MONTH_NAMES[curMonth-1];
    document.getElementById("calYearLabel").innerHTML =
      String(curYear).slice(0,2) + "<br>" + String(curYear).slice(2);
    var container = document.getElementById("calDaysContainer");
    container.innerHTML = monthsData[key] ||
      "<div style='font-size:10px;color:#B9AFA0;padding:8px 0;text-align:center'>Data tidak tersedia</div>";
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
    if(!label) return;
    var popup = document.getElementById("calPopup");
    document.getElementById("calPopupText").textContent = label;
    popup.style.display = "flex";
    // posisikan dekat elemen
    var rect = el.getBoundingClientRect();
    popup.style.top  = (rect.bottom + window.scrollY + 4) + "px";
    popup.style.left = Math.max(4, rect.left + window.scrollX - 40) + "px";
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
.cal-legend{ display:flex; flex-wrap:wrap; gap:10px; font-size:9px; color:#9B9388; margin:8px 0 2px; }
.dot{ width:7px; height:7px; border-radius:50%; display:inline-block; margin-right:3px; vertical-align:middle; }
.dot-today{ background:#2A2724; }
.dot-holiday{ background:#D6402F; }

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

# ── Header ─────────────────────────────────────────────────────────────
st.title("📱 Smartphone Advisor")
st.caption(
    "Asisten AI untuk tim sales & marketing — "
    "rekomendasi dan perbandingan produk smartphone berdasarkan katalog resmi"
)

# ── Load RAG Pipeline ──────────────────────────────────────────────────
# Menggunakan st.cache_resource agar pipeline hanya dibangun sekali.
# Tanpa ini, pipeline akan dibangun ulang setiap ada interaksi pengguna.
@st.cache_resource(show_spinner=False)
def load_pipeline():
    return build_rag_pipeline()

# Tampilkan proses loading kepada pengguna
if "pipeline_loaded" not in st.session_state:
    with st.status("Memuat sistem AI...", expanded=True) as status:
        st.write("Membaca katalog produk...")
        st.write("Membangun vector store...")
        st.write("Menginisialisasi model bahasa...")
        chain, num_chunks = load_pipeline()
        st.session_state.chain = chain
        st.session_state.num_chunks = num_chunks
        st.session_state.pipeline_loaded = True
        status.update(
            label=f"Sistem siap! {num_chunks} potongan dokumen berhasil diindeks.",
            state="complete"
        )

chain = st.session_state.chain

# ── Inisialisasi Riwayat Chat ──────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Tampilkan Contoh Pertanyaan (hanya saat belum ada chat) ───────────
if not st.session_state.messages:
    st.info(
        "**Contoh pertanyaan yang bisa Anda ajukan:**\n\n"
        "- Rekomendasikan smartphone untuk fotografi dengan budget 5 juta\n"
        "- Bandingkan Samsung Galaxy S24 dengan iPhone 15\n"
        "- HP mana yang cocok untuk konten kreator video?\n"
        "- Smartphone mana yang pengisian baterainya paling cepat?\n"
        "- Produk apa yang paling cocok untuk pengguna aktif outdoor?\n"
        "- Apa perbedaan iPhone 15 dan iPhone 15 Pro Max?"
    )

# ── Tampilkan Riwayat Chat ─────────────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ── Input Pengguna ───────────────────────────────────────────────────────
# st.chat_input menampilkan SATU bar input di bagian bawah halaman dengan
# ikon panah kirim di ujung kanan. Bar tersebut adalah elemen INTERAKTIF
# (tempat user mengetik — teks yang diketik langsung tampil DI DALAM bar
# ini). Ikon panah bersifat STATIS: hanya memicu pengiriman saat diklik
# atau saat user menekan Enter, dan tidak bisa diketik/diinteraksi
# langsung seperti bar-nya.
if user_input := st.chat_input("Tanyakan sesuatu tentang produk smartphone..."):

    # Simpan dan tampilkan pesan pengguna
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate jawaban dari RAG chain
    with st.chat_message("assistant"):
        with st.spinner("Mencari informasi di katalog..."):
            result = chain.invoke({"query": user_input})
            answer = result["result"]
            source_docs = result["source_documents"]

        st.markdown(answer)

        # Tampilkan referensi dokumen sumber (bisa di-collapse)
        with st.expander("Lihat referensi dari katalog"):
            for i, doc in enumerate(source_docs, 1):
                st.markdown(f"**Referensi {i}:**")
                st.text(doc.page_content[:300] + "...")
                st.divider()

    # Simpan jawaban ke riwayat
    st.session_state.messages.append({"role": "assistant", "content": answer})


# ── Sidebar ────────────────────────────────────────────────────────────
with st.sidebar:
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

    st.subheader("📱 Produk Tersedia")
    st.markdown(
        "1. Xiaomi Redmi Note 13 Pro+ 5G\n"
        "2. Samsung Galaxy A55 5G\n"
        "3. OPPO Reno 12 Pro\n"
        "4. Samsung Galaxy S24\n"
        "5. Apple iPhone 15\n"
        "6. Apple iPhone 15 Pro Max"
    )

    st.divider()

    st.subheader("⚙️ Arsitektur Sistem")
    st.markdown(
        "```\n"
        "Katalog Produk (TXT)\n"
        "       ↓\n"
        "  Document Loader\n"
        "       ↓\n"
        "  Text Splitter\n"
        "       ↓\n"
        "HuggingFace Embeddings\n"
        "       ↓\n"
        "  FAISS Vector Store\n"
        "       ↓\n"
        "    Retriever\n"
        "       ↓\n"
        " Groq LLM (Llama 3.3)\n"
        "       ↓\n"
        "  Jawaban Final\n"
        "```"
    )

    st.divider()

    if st.button("🔄 Reset Percakapan", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
