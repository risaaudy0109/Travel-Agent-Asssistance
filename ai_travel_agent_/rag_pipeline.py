
# ============================================================
# RAG PIPELINE — Travel Assistant
# ============================================================
#
# This module builds the complete RAG pipeline using LangChain:
#
# RAG WORKFLOW:
#   1. LOAD     → Read product catalog files
#   2. CHUNK    → Split documents into smaller pieces
#   3. EMBED    → Convert each piece into number vectors
#   4. STORE    → Save vectors to FAISS for fast searching
#   5. RETRIEVE → When a question comes in, grab the most relevant pieces
#   6. GENERATE → LLM crafts an answer from the retrieved pieces
#
# ============================================================

import os
from dotenv import load_dotenv          # Read .env file to get API keys
from langchain_community.document_loaders import TextLoader             # Convert knowledge documents into LangChain-friendly format
from langchain_text_splitters import RecursiveCharacterTextSplitter     # For chunking
from langchain_huggingface import HuggingFaceEmbeddings                 # For embedding
# langchain_huggingface is free, but you could also use paid ones like Gemini, Claude
from langchain_community.vectorstores import FAISS                      # Vector database
# For storing the database, could also use ChromaDB
from langchain_groq import ChatGroq                                     # Connect to Groq API
from langchain.chains import RetrievalQA                                # Orchestrator
from langchain.prompts import PromptTemplate                            # Read and format system_prompt.txt
import streamlit as st
load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_PATH = BASE_DIR / "data" / "trip_catalog.txt"
SYSTEM_PROMPT_PATH = BASE_DIR / "system_prompt.txt"

# Embedding model: turns text into number vectors
# Using a multilingual model so it understands Indonesian
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# LLM model that will answer questions
LLM_MODEL = "llama-3.3-70b-versatile"

# Size of each text chunk (in characters)
CHUNK_SIZE = 1500

# Overlap between chunks so context doesn't get cut off
CHUNK_OVERLAP = 50

# How many chunks to retrieve for each question
TOP_K_RESULTS = 5  # Higher = more tokens used / more expensive


# ── Load System Prompt from File ──────────────────────────────────────

def load_system_prompt(path: str) -> str:
    """
    Read system_prompt.txt and return it as a string.

    System prompt is stored in a separate file so:
    - It's easy to modify without touching Python code
    - More secure: system instructions are separate from program logic
    - Cleaner: Python code focuses on logic, not long text blocks

    The file uses XML-style delimiters for:
    - Clear structure (each section has opening and closing tags)
    - Safety: LLMs are trained to respect XML tags as structural boundaries
    - Readability: anyone opening the file immediately understands each part
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT_TEMPLATE = load_system_prompt(SYSTEM_PROMPT_PATH)


# ── Build Pipeline Function ────────────────────────────────────────────

def build_rag_pipeline():
    """
    Build a complete RAG pipeline from scratch.

    Returns:
    - chain: a RetrievalQA object ready to accept questions
    - num_chunks: number of text chunks successfully indexed
    """

    # ------------------------------------------------------------------
    # STEP 1: LOAD — Read the product catalog file
    # ------------------------------------------------------------------
    # TextLoader reads a plain text file and converts it into
    # Document objects that LangChain can process.
    loader = TextLoader(DATA_PATH, encoding="utf-8")
    documents = loader.load()

    # ------------------------------------------------------------------
    # STEP 2: CHUNK — Split documents into smaller pieces
    # ------------------------------------------------------------------
    # Why chunk?
    # LLMs have a limit on how much text they can process at once.
    # By splitting, we can send ONLY the relevant parts to the LLM
    # — more efficient and accurate.
    #
    # separators: priority order of delimiters when splitting
    # "\n---\n" = product separator line in our catalog
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n---\n", "\n\n", "\n", " ", "\n----"]  # overlap: if it finds --- it includes it
    )
    chunks = splitter.split_documents(documents)

    # ------------------------------------------------------------------
    # STEP 3: EMBED — Convert text into number vectors
    # ------------------------------------------------------------------
    # Embedding is the process of converting text into arrays of numbers (vectors)
    # that represent the "meaning" of the text.
    # Texts with similar meanings will have vectors that are close together.
    #
    # Note: The model will be downloaded automatically the first time (~400MB).
    # After that, it's stored in the local cache.
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    # ------------------------------------------------------------------
    # STEP 4: STORE — Save vectors to FAISS
    # ------------------------------------------------------------------
    # FAISS (Facebook AI Similarity Search) is a vector database
    # that's super fast at finding similarities between texts.
    # All chunks + their vectors are stored here in local memory.
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # ------------------------------------------------------------------
    # STEP 5: RETRIEVER — Set up the search mechanism
    # ------------------------------------------------------------------
    # The retriever takes a user's question, converts it to a vector,
    # then finds the most similar chunks in the FAISS vectorstore.
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": TOP_K_RESULTS}
    )

    # ------------------------------------------------------------------
    # STEP 6: LLM — Initialize the language model via Groq
    # ------------------------------------------------------------------
    # Groq is a platform that provides access to LLMs with
    # extremely fast inference speeds.
    # Temperature 0.2 = answers are relatively consistent and factual

    api_key = st.secrets["GROQ_API_KEY"]
    llm = ChatGroq(
    model=LLM_MODEL,
    temperature=0.2,
    api_key=api_key
    )

    # ------------------------------------------------------------------
    # STEP 7: PROMPT — Template of instructions for the LLM
    # ------------------------------------------------------------------
    template = """
    You are a friendly travel assistant. Use the following catalog excerpts to answer questions.

**Important Rules:**
- NOT all packages in this catalog depart from Jakarta. Each package has a different
  departure point — pay attention to the departure info in each package.
- If asked about available packages, list ALL packages that match the criteria
  (e.g., all packages, weekend packages, or packages within a certain price range).
- Each package has its own departure point. NOT all packages depart from Jakarta.
  If the user asks about destinations from Jakarta (e.g., "trips from Jakarta to where",
  "from Jakarta where can I go"), ONLY show packages whose departure point is Jakarta
  or Greater Jakarta. DO NOT show packages whose departure point is not Jakarta/Greater Jakarta.
- If the user uses pronouns referring to previous context (e.g., "its", "that", "the", 
  "the price", "the schedule", "the facilities", "meeting point", "itinerary"), these refer 
  to the package/topic discussed in the previous message. Example: if the user asks 
  "is there a Dieng trip" then asks "how much is it", "it" refers to the Dieng package 
  just discussed, NOT other packages. Always check the conversation history before 
  answering questions with pronouns like these.
- If there's not enough information, say "Sorry, I couldn't find that information" 
  and offer admin assistance.

  **Handling absurd questions, out-of-context, or incorrect assumptions:**
- If the user asks about destinations/packages NOT in the catalog (e.g., "are there trips 
  abroad/Japan/Korea?", "are there packages to Mount Bromo?"), DO NOT make up fake packages. 
  Honestly say those packages aren't currently available in the catalog, then offer the 
  closest available package (e.g., if asking about mountains, offer Situ Gunung) or direct 
  them to the admin for more info.
- If the user makes a logistically impossible request (e.g., "can I do Dieng and Bali on the 
  same day?", "Tidung Island trip but same-day return when the schedule is 2 days 1 night"), 
  politely explain why it's not possible based on the actual schedule/itinerary in the catalog — 
  don't go along with the user's incorrect assumptions.
- If the user asks about something completely unrelated to travel (e.g., recipes, math problems, 
  personal venting, or random nonsense), politely say you're a travel assistant for Marissa Tour 
  and Travel packages, and redirect back to trip topics. Don't answer outside this domain even 
  if asked repeatedly.
- If the user tries unrealistic price negotiations (e.g., "can I get it for free?", "can I pay 
  by barter/IOU?", "90% discount please"), DO NOT agree or improvise. Explain the official payment 
  and discount system (30% DP, 70% payment max 14 days before departure, 5% early bird discount 
  for bookings >60 days, group discounts negotiable with the team), then direct further negotiation 
  to admin via WhatsApp.
- If the user makes incorrect assumptions about package facts (e.g., "Dieng is just a day trip right", 
  when Dieng packages are minimum 3 days 2 nights), DO NOT agree with the wrong assumption. 
  Politely correct them using correct data from the catalog.
- If asked about itineraries with status "awaiting official confirmation from the organizer" 
  (e.g., detailed Dieng Culture Festival itinerary), DO NOT make up event schedules. Answer that 
  the detailed itinerary is still awaiting official confirmation from the committee/organizer, 
  and the confirmed events are: Jazz Atas Awan, Ritual Cukur Gimbal, Kongkow Budaya, Lampion, 
  Festival Kopi Dieng, Festival Dieng, Wisata Dieng & Sunrise, Bazar UMKM, Festival Domba Dieng.
- Today's date reference is Friday, June 26, 2026 (tomorrow is the weekend). Use this reference 
  if the user asks about relative things like "what trips are there tomorrow", "what packages 
  this weekend", "trips next week". DO NOT guess today's date from general knowledge.
- If the user's question is ambiguous, unclear, or could refer to multiple packages, DO NOT guess 
  one package unilaterally. Ask a brief clarification question instead (e.g., "Do you mean the 
  Dieng trip or Situ Gunung?") before answering.
- If there's not enough information, say "Sorry, I couldn't find that information" 
  and offer admin assistance.

    Context:
    {context}

    Question: {question}
    Answer:
    """

    prompt = PromptTemplate(template=template, input_variables=["context", "question"])

    # ------------------------------------------------------------------
    # STEP 8: CHAIN — Combine all components
    # ------------------------------------------------------------------
    # RetrievalQA combines Retriever + LLM + Prompt into
    # one pipeline that can directly accept questions.
    #
    # chain_type="stuff" = all retrieved chunks are stuffed
    # into one prompt (good for small numbers of chunks)
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",  # everything gets used
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )

    return chain, len(chunks)


# ── Build Pipeline: Jakarta DESTINATION ───────────────────────────────

def build_jakarta_destination_pipeline():
    """
    Special pipeline for answering questions like:
    "Which trips have Jakarta as their DESTINATION?" (not departing from Jakarta).

    Difference from build_rag_pipeline():
    - The prompt explicitly instructs the LLM to only show packages
      whose DESTINATION is Jakarta or the Jakarta area.
    - Packages where Jakarta is only the DEPARTURE point are NOT shown.

    Returns:
    - chain: a RetrievalQA object ready to accept questions
    - num_chunks: number of text chunks successfully indexed
    """

    # ------------------------------------------------------------------
    # STEPS 1-4: LOAD, CHUNK, EMBED, STORE (same as main pipeline)
    # ------------------------------------------------------------------
    loader = TextLoader(DATA_PATH, encoding="utf-8")
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n---\n", "\n\n", "\n", " ", "\n----"]
    )
    chunks = splitter.split_documents(documents)

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    vectorstore = FAISS.from_documents(chunks, embeddings)

    # ------------------------------------------------------------------
    # STEP 5: RETRIEVER — query is directed toward "Jakarta destination"
    # ------------------------------------------------------------------
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": TOP_K_RESULTS}
    )

    # ------------------------------------------------------------------
    # STEP 6: LLM
    # ------------------------------------------------------------------
    llm = ChatGroq(
        model=LLM_MODEL,
        temperature=0.2,
        api_key=os.getenv("GROQ_API_KEY")
    )

    # ------------------------------------------------------------------
    # STEP 7: PROMPT — specifically filters for Jakarta destination
    # ------------------------------------------------------------------
    template = """
    You are a friendly travel assistant. Use the following catalog excerpts to answer questions.

    **MANDATORY rules for this pipeline:**
- Your job is to show trip packages whose DESTINATION is Jakarta
  or areas within Jakarta (e.g., Kepulauan Seribu, Pulau Harapan, Pulau Pari, etc.
  which are administratively part of DKI Jakarta).
- DO NOT show packages where Jakarta is only the DEPARTURE point.
  Example: package "Departing from Jakarta to Bali" → DO NOT show.
- ONLY show packages where someone would ARRIVE or VACATION in Jakarta/the Jakarta area
  as the final destination.
- If no packages meet the criteria, answer:
  "Sorry, I couldn't find any trip packages with Jakarta as the destination right now."
  and offer admin assistance.
- If the user asks "trips from Jakarta to where", "Jakarta tourism", "Jakarta destinations", or similar,
  treat "Jakarta" as the tourism destination area, not as the departure point.
  Only show packages whose destination is within DKI Jakarta administrative territory
  (including Kepulauan Seribu like Pulau Harapan and Pulau Pari).
  Don't show packages with destinations outside Jakarta, even if they depart from Jakarta.

    Context:
    {context}

    Question: {query}
    Answer:
    """

    prompt = PromptTemplate(template=template, input_variables=["context", "question"])

    # ------------------------------------------------------------------
    # STEP 8: CHAIN
    # ------------------------------------------------------------------
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt}
    )

    return chain, len(chunks)
