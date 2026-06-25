# Smartphone Advisor

Chatbot AI untuk tim sales dan marketing yang membantu membandingkan dan
merekomendasikan produk smartphone. Dibangun menggunakan teknologi
RAG (Retrieval-Augmented Generation) dengan LangChain.

## Arsitektur Sistem

```
Katalog Produk (TXT)
       |
  Document Loader        <- Membaca file katalog
       |
  Text Splitter          <- Memotong dokumen jadi chunk kecil
       |
HuggingFace Embeddings   <- Mengubah teks jadi vektor angka
       |
  FAISS Vector Store     <- Menyimpan vektor untuk pencarian cepat
       |
    Retriever            <- Mencari chunk paling relevan saat ada query
       |
 Groq LLM (Llama 3.3)   <- Merangkai jawaban dari chunk yang diambil
       |
  Jawaban Final
```

## Tech Stack

- LLM: Groq API + Llama 3.3 70B Versatile
- RAG Framework: LangChain
- Embeddings: HuggingFace (paraphrase-multilingual-MiniLM-L12-v2)
- Vector Store: FAISS (lokal, tidak perlu server)
- UI: Streamlit

## Cara Setup dan Menjalankan

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Buat file .env

Salin file `.env.example` dan rename menjadi `.env`:

```bash
cp .env.example .env
```

Lalu isi API key Groq di file `.env`:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

Cara mendapatkan API key:
1. Buka https://console.groq.com
2. Daftar atau login
3. Klik "Create API Key"
4. Salin dan tempelkan ke file .env

### 3. Jalankan aplikasi

```bash
streamlit run app.py
```

Buka browser dan akses http://localhost:8501

## Struktur Project

```
smartphone-advisor/
├── app.py                  <- Antarmuka Streamlit (entry point)
├── rag_pipeline.py         <- Logika RAG LangChain
├── requirements.txt        <- Daftar library yang dibutuhkan
├── .env.example            <- Template konfigurasi API key
├── .env                    <- API key (JANGAN di-commit ke GitHub)
├── .gitignore
├── README.md
└── data/
    └── katalog_smartphone.txt  <- Knowledge base produk
```

## Produk yang Tersedia

1. Xiaomi Redmi Note 13 Pro+ 5G (Rp 4.299.000)
2. Samsung Galaxy A55 5G (Rp 5.499.000)
3. OPPO Reno 12 Pro (Rp 6.999.000)
4. Samsung Galaxy S24 (Rp 13.499.000)
5. Apple iPhone 15 (Rp 13.999.000)
6. Apple iPhone 15 Pro Max (Rp 21.999.000)

## Contoh Pertanyaan

- "Rekomendasikan smartphone untuk fotografi dengan budget 5 juta"
- "Bandingkan Samsung Galaxy S24 dengan iPhone 15"
- "HP mana yang pengisian baterainya paling cepat?"
- "Smartphone apa yang cocok untuk konten kreator video?"
- "Produk mana yang memiliki garansi software terlama?"

## Deployment ke Streamlit Community Cloud

1. Upload project ke GitHub (pastikan .env tidak ikut ter-commit)
2. Buka https://share.streamlit.io
3. Hubungkan dengan repository GitHub
4. Tambahkan GROQ_API_KEY di bagian Secrets:
   ```
   GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxx"
   ```
5. Deploy

Catatan: File .env tidak digunakan di Streamlit Cloud.
API key dibaca dari Secrets yang dikonfigurasi di dashboard.
