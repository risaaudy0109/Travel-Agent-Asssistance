# ============================================================
# RAG PIPELINE — Smartphone Advisor
# ============================================================
#
# Modul ini membangun seluruh pipeline RAG menggunakan LangChain:
#
# ALUR KERJA RAG:
#   1. LOAD     → Baca file katalog produk
#   2. CHUNK    → Potong dokumen jadi bagian-bagian kecil
#   3. EMBED    → Ubah setiap potongan jadi vektor angka
#   4. STORE    → Simpan vektor ke FAISS untuk pencarian cepat
#   5. RETRIEVE → Saat ada pertanyaan, ambil potongan paling relevan
#   6. GENERATE → LLM merangkai jawaban dari potongan yang diambil
#
# ============================================================

import os
from dotenv import load_dotenv          # Untuk membaca file .env ambil API nya

from langchain_community.document_loaders import TextLoader             # Untuk mengubah knowledge document jadi format yang bisa diproses LangChain
from langchain_text_splitters import RecursiveCharacterTextSplitter     # Untuk chunking
from langchain_huggingface import HuggingFaceEmbeddings                 # Untuk embedding 
# langchain_huggingface karena gratis, tapi bisa juga bayar, misal geminiai, claude
from langchain_community.vectorstores import FAISS                      # Vector database
# buat nyimpan database, bisa juga pake chromadb
from langchain_groq import ChatGroq                                     # Connect ke Groq API
from langchain.chains import RetrievalQA                                # Orkestrator
from langchain.prompts import PromptTemplate                            # Untuk membaca dan memformat file system_prompt.txt

load_dotenv()

# ── Konfigurasi ────────────────────────────────────────────────────────

# Lokasi file katalog produk
DATA_PATH = "data/katalog_smartphone.txt"

# Lokasi file system prompt
SYSTEM_PROMPT_PATH = "system_prompt.txt"

# Model embedding: mengubah teks jadi vektor angka
# Menggunakan model multilingual agar paham Bahasa Indonesia
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Model LLM yang akan menjawab pertanyaan
LLM_MODEL = "llama-3.3-70b-versatile"

# Ukuran setiap potongan teks (dalam karakter)
CHUNK_SIZE = 800 # 800 karakter/huruf

# Tumpang tindih antar potongan agar konteks tidak terputus
CHUNK_OVERLAP = 100

# Berapa potongan yang diambil untuk setiap pertanyaan
TOP_K_RESULTS = 4 #kalo semakin banyak maka semakin banyak token yg dibutuhn/ boncos


# ── Load System Prompt dari File ───────────────────────────────────────

def load_system_prompt(path: str) -> str:
    """
    Membaca file system_prompt.txt dan mengembalikannya sebagai string.

    System prompt disimpan di file terpisah agar:
    - Mudah dimodifikasi tanpa menyentuh kode Python
    - Lebih aman: instruksi sistem terpisah dari logika program
    - Lebih bersih: kode Python fokus pada logika, bukan teks panjang

    File menggunakan XML-style delimiter untuk:
    - Kejelasan struktur (tiap bagian punya tag pembuka dan penutup)
    - Keamanan: LLM dilatih menghormati XML tags sebagai batas struktural
    - Keterbacaan: siapapun yang buka file langsung paham bagian mana itu apa
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT_TEMPLATE = load_system_prompt(SYSTEM_PROMPT_PATH)


# ── Fungsi Build Pipeline ──────────────────────────────────────────────

def build_rag_pipeline():
    """
    Membangun RAG pipeline lengkap dari nol.

    Mengembalikan:
    - chain: objek RetrievalQA yang siap menerima pertanyaan
    - num_chunks: jumlah potongan teks yang berhasil diindeks
    """

    # ------------------------------------------------------------------
    # LANGKAH 1: LOAD — Membaca file katalog produk
    # ------------------------------------------------------------------
    # TextLoader membaca file teks biasa dan mengubahnya jadi objek
    # Document yang bisa diproses LangChain.
    loader = TextLoader(DATA_PATH, encoding="utf-8")
    documents = loader.load()

    # ------------------------------------------------------------------
    # LANGKAH 2: CHUNK — Memotong dokumen jadi bagian-bagian kecil
    # ------------------------------------------------------------------
    # Kenapa perlu di-chunk?
    # LLM punya batas panjang teks yang bisa diproses sekaligus.
    # Dengan memotong, kita bisa memilih HANYA bagian yang relevan
    # untuk dikirim ke LLM — lebih efisien dan akurat.
    #
    # separators: urutan prioritas pemisah saat memotong
    # "\n---\n" = garis pemisah antar produk di katalog kita
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n---\n", "\n\n", "\n", " "] # buat overlap, kalo nemu --- maka dia ikut keambil juga
    )
    chunks = splitter.split_documents(documents)

    # ------------------------------------------------------------------
    # LANGKAH 3: EMBED — Mengubah teks jadi vektor angka
    # ------------------------------------------------------------------
    # Embedding adalah proses mengubah teks jadi deretan angka (vektor)
    # yang merepresentasikan "makna" teks tersebut.
    # Teks dengan makna serupa akan menghasilkan vektor yang berdekatan.
    #
    # Catatan: Model akan diunduh otomatis pertama kali (~400MB).
    # Setelah itu tersimpan di cache lokal.
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True} 
    )

    # ------------------------------------------------------------------
    # LANGKAH 4: STORE — Menyimpan vektor ke FAISS
    # ------------------------------------------------------------------
    # FAISS (Facebook AI Similarity Search) adalah database vektor
    # yang sangat cepat untuk mencari kemiripan antar teks.
    # Semua chunk + vektornya disimpan di sini di memory lokal.
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # ------------------------------------------------------------------
    # LANGKAH 5: RETRIEVER — Menyiapkan mekanisme pencarian
    # ------------------------------------------------------------------
    # Retriever adalah komponen yang menerima pertanyaan pengguna,
    # mengubahnya jadi vektor, lalu mencari chunk paling mirip
    # di dalam FAISS vectorstore.
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": TOP_K_RESULTS}
    )

    # ------------------------------------------------------------------
    # LANGKAH 6: LLM — Inisialisasi model bahasa via Groq
    # ------------------------------------------------------------------
    # Groq adalah platform yang menyediakan akses ke LLM dengan
    # kecepatan inferensi sangat tinggi.
    # Temperature 0.3 = jawaban relatif konsisten dan faktual
    llm = ChatGroq(
        model=LLM_MODEL,
        temperature=0.3, #buat kalo kalimatnya harus sama persis, kalo makin tinggi makin kreatif
        api_key=os.getenv("GROQ_API_KEY")
    )

    # ------------------------------------------------------------------
    # LANGKAH 7: PROMPT — Template instruksi untuk LLM
    # ------------------------------------------------------------------
    prompt = PromptTemplate(
        template=SYSTEM_PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )

    # ------------------------------------------------------------------
    # LANGKAH 8: CHAIN — Menggabungkan semua komponen
    # ------------------------------------------------------------------
    # RetrievalQA menggabungkan Retriever + LLM + Prompt menjadi
    # satu pipeline yang bisa langsung menerima pertanyaan.
    #
    # chain_type="stuff" = semua chunk yang diambil langsung
    # dimasukkan ke dalam satu prompt (cocok untuk chunk sedikit)
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff", #semua dipake
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )

    return chain, len(chunks)
