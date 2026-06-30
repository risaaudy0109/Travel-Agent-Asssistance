# 🏝️ Marissa Tour and Travel — AI Trip Assistant

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Deployed-red)
![LangChain](https://img.shields.io/badge/LangChain-RAG-green)
![FAISS](https://img.shields.io/badge/FAISS-VectorDB-orange)
![Groq](https://img.shields.io/badge/LLM-Groq-purple)

An AI-powered chatbot that helps customers pick the right trip package without waiting around for an admin to reply. Built with **Retrieval-Augmented Generation (RAG)**, so it answers straight from the real trip catalog instead of making stuff up. Think of it as a 24/7 sales rep who's read the whole catalog and never forgets a price.

---

## 🚀 Live Demo

Not deployed yet — run it locally for now (see [Installation](#-installation) below).

---

## 📖 Project Overview

Booking a trip usually means scrolling through a long catalog or waiting for an admin to reply on WhatsApp. This project fixes that by letting customers just ask, in plain language, and get an answer grounded in the actual trip catalog using RAG.

The assistant combines **Retrieval-Augmented Generation (RAG)** with **Groq Llama 3.3 70B**, so every answer is backed by real catalog data — not the model's imagination.

The current version covers:

- Open Trip Dieng Culture Festival
- Explore Situ Gunung
- Explore Pulau Pari
- Explore Pulau Tidung
- Explore Pulau Harapan
- Open Trip Bali & Nusa Penida

---

## ✨ Features

- 💬 AI-powered trip chatbot with a customer-service style chat UI
- 📚 Retrieval-Augmented Generation (RAG) grounded in the official catalog
- 🔍 Semantic document retrieval (FAISS similarity search)
- 📄 Trip catalog knowledge base (prices, itineraries, facilities, terms)
- ⚡ Fast inference using Groq
- 🧠 Conversation memory (handles follow-up questions like "how much is it" correctly)
- 📑 Retrieved source display (see which catalog chunk the answer came from)
- 📅 Live calendar widget with Indonesian national holidays
- 🎯 Smart handling of out-of-scope, absurd, or edge-case questions
- 📲 WhatsApp handoff to a human admin when the bot can't help

---

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit |
| LLM | Groq Llama 3.3 70B Versatile |
| Framework | LangChain |
| Embedding Model | sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 |
| Vector Database | FAISS |
| Document Loader | TextLoader |
| Language | Python |

---

## 🏗 System Architecture

```
The system combines document retrieval and a Large Language Model to keep
every answer grounded in the official trip catalog.

                    User
                      │
                      ▼
              Streamlit Interface
                      │
                      ▼
              FAISS Retrieval
                      │
                      ▼
              Relevant Chunks
                      │
                      ▼
            Prompt Construction
           (with edge-case rules:
        no fake trips, no fake discounts,
         stays on-topic, checks chat history)
                      │
                      ▼
            Groq Llama 3.3 70B
                      │
                      ▼
              Final Response
                      │
              ┌───────┴────────┐
              │                │
      Answer found      Answer not found
              │                │
              ▼                ▼
       Show answer +    Offer WhatsApp
       source chunks    admin handoff
```

---

## 🔄 RAG Pipeline

```text
trip_catalog.txt (official catalog)
          │
          ▼
   TextLoader
          │
          ▼
      Chunking (RecursiveCharacterTextSplitter)
          │
          ▼
     Embedding (HuggingFace, multilingual)
          │
          ▼
 FAISS Vector Store
          │
          ▼
 Similarity Retrieval (top-5 chunks)
          │
          ▼
 Prompt Construction
          │
          ▼
   Groq LLM (Llama 3.3 70B)
          │
          ▼
 Final Answer
```

---

## 📂 Project Structure

```text
.
├── app.py                  <- Streamlit UI (entry point, chat + calendar)
├── rag_pipeline.py         <- RAG pipeline logic (LangChain)
├── system_prompt.txt       <- Assistant's behavior rules
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
└── data/
    └── trip_catalog.txt    <- Trip package knowledge base
```

---

## ⚙ Installation

Clone the repository:

```bash
git clone https://github.com/your-username/marissa-tour-and-travel.git

cd marissa-tour-and-travel
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🔑 Environment Variables

Create a `.env` file in the project root (you can copy `.env.example`):

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=your_groq_api_key
```

Getting a key takes 2 minutes:
1. Go to https://console.groq.com
2. Sign up or log in
3. Click "Create API Key"
4. Paste it into `.env`

---

## ▶ Running the Application

```bash
streamlit run app.py
```

Then open http://localhost:8501 in your browser. The vector store is built automatically on first run (no separate ingest step needed).

---

## 💡 Example Questions

- Recommend a trip this month
- Does the Dieng Culture Festival ticket price include everything?
- What's the price difference between Pulau Tidung and Pulau Harapan?
- What's included in the Bali & Nusa Penida package?
- Got any trips to Mount Bromo? *(it'll honestly say no instead of making one up)*
- Can I do Dieng and Bali on the same day? *(it'll explain why that's not possible)*
- Can I get a 90% discount? *(it'll point you to the real discount policy + admin instead)*

---

## 📊 Evaluation

Formal evaluation hasn't been done yet — this is on the roadmap. Planned approach:

| Evaluation Item | Status |
|-----------------|--------|
| Test Questions | TBD |
| Knowledge Base | Official Trip Catalog (`trip_catalog.txt`) |
| Retrieval Method | Similarity Search |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 |
| Vector Store | FAISS |
| LLM | Llama 3.3 70B |

The system is designed to answer **only using retrieved context**, reducing hallucinations and keeping pricing/itinerary info factually consistent with the catalog.

---

## 🚀 Future Improvements

- Deploy to Streamlit Community Cloud
- Add proper evaluation suite with sample questions
- Expand the trip catalog with more destinations
- Add booking/payment integration
- Improve multi-turn conversation memory
- Add reranking for better retrieval accuracy
- Add multilingual support (English-speaking customers)

---

## 📚 Knowledge Source

The chatbot only answers questions within the supported scope, using the official trip catalog as its primary source of truth.

- Trip packages, pricing, and itineraries
- Facilities included/excluded per package
- Payment, cancellation, and discount policies
- Meeting points and trip schedules

---

## 📄 License

This project was developed for educational purposes as a Final Project for the Data Science Bootcamp at Hacktiv8.
