# streamlit_app.py
import streamlit as st
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI
import httpx
import time

# Load environment variables
load_dotenv()

# Initialize Mistral model
model = ChatMistralAI(model="mistral-small-2506")

# Define the prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system",
     """
You are a professional Movie Information Extraction Assistant.

Your task:
Extract useful structured information from a movie paragraph and present it in a clean readable form

Rules:
- Do NOT add explanations
- Do NOT add extra commentary
- Follow the exact format
- If information is missing -> write NULL
- Keep summary short (2-3 lines max)
- Do NOT guess unknown facts

Output Format:

Movie Title:
Release Year:
Genre:
Director:
Main Cast:
Setting/Location:
Plot:
Themes:
Ratings:
Notable Features:
Short Summary:
     """),
    ("human",
     """
Extract information from this paragraph:

{paragraph}
     """)
])

# ─── Session State Init ───────────────────────────────────────────────────────
if "paragraph" not in st.session_state:
    st.session_state.paragraph = ""
if "result" not in st.session_state:
    st.session_state.result = None
if "clear_trigger" not in st.session_state:
    st.session_state.clear_trigger = False

# ─── Streamlit UI ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Movie Info Extractor", layout="centered")
st.title("🎬 Movie Information Extractor")
st.write("Enter a movie paragraph below and get structured information:")

# ─── Handle clear trigger ────────────────────────────────────────────────────
if st.session_state.clear_trigger:
    st.session_state.paragraph = ""
    st.session_state.result = None
    st.session_state.clear_trigger = False

# ─── Text area ───────────────────────────────────────────────────────────────
para = st.text_area(
    "Movie Paragraph",
    value=st.session_state.paragraph,
    height=200,
    key="paragraph"
)

# ─── 2 Equal Buttons ─────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    extract_btn = st.button("🚀 Extract Info", use_container_width=True)

with col2:
    clear_btn = st.button("🗑️ Clear", use_container_width=True)

# ─── Clear Button Logic ───────────────────────────────────────────────────────
if clear_btn:
    st.session_state.clear_trigger = True
    st.rerun()

# ─── Extract Button Logic ─────────────────────────────────────────────────────
if extract_btn:
    if para.strip() == "":
        st.warning("⚠️ Please enter a paragraph first!")
    else:
        status_box = st.empty()

        fetch_messages = [
            "🎬 Reading your paragraph...",
            "🔍 Analyzing movie details...",
            "📽️ Extracting structured info...",
            "✨ Almost done, hang tight!",
        ]

        try:
            with st.spinner(""):
                import threading
                result_holder = {}

                def fetch_result():
                    try:
                        final_prompt = prompt.invoke({"paragraph": para})
                        response = model.invoke(final_prompt)
                        result_holder["content"] = response.content
                    except Exception as e:
                        result_holder["error"] = e

                thread = threading.Thread(target=fetch_result)
                thread.start()

                i = 0
                while thread.is_alive():
                    status_box.info(fetch_messages[i % len(fetch_messages)])
                    time.sleep(1.2)
                    i += 1

                thread.join()
                status_box.empty()

            if "error" in result_holder:
                raise result_holder["error"]

            st.session_state.result = result_holder["content"]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                st.error(
                    "🚦 **API Overloaded!** Mistral ka server abhi bahut busy hai.\n\n"
                    "Kuch seconds baad dobara try karein. ☕ Ek chai pi lo tab tak!"
                )
            else:
                st.error(f"❌ HTTP Error: {e.response.status_code} — {e.response.text}")

        except Exception as e:
            err_msg = str(e).lower()
            if "rate limit" in err_msg or "429" in err_msg or "too many requests" in err_msg or "overloaded" in err_msg:
                st.error(
                    "🚦 **API Overloaded!** Mistral ka server abhi bahut busy hai.\n\n"
                    "Thoda ruko aur phir try karo — usually 10-20 seconds mein theek ho jaata hai! ⏳"
                )
            elif "unauthorized" in err_msg or "401" in err_msg:
                st.error("🔑 **API Key Invalid!** Apna `.env` file check karo aur sahi API key daalo.")
            elif "timeout" in err_msg:
                st.error("⏱️ **Request Timeout!** Server ne respond nahi kiya. Dobara try karo.")
            else:
                st.error(f"❌ **Kuch gadbad hui:** {e}")

# ─── Show Result ──────────────────────────────────────────────────────────────
if st.session_state.result:
    st.subheader("🎞️ Extracted Movie Information:")

    field_icons = {
        "Movie Title": "🎬",
        "Release Year": "📅",
        "Genre": "🎭",
        "Director": "🎥",
        "Main Cast": "🌟",
        "Setting/Location": "📍",
        "Plot": "📖",
        "Themes": "💡",
        "Ratings": "⭐",
        "Notable Features": "✨",
        "Short Summary": "📝",
    }

    # Fields always shown as bullet points (comma-split)
    bullet_fields = {"Main Cast", "Setting/Location", "Themes", "Notable Features"}

    parsed = {}
    order = []
    current_key = None

    for line in st.session_state.result.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key in field_icons:
                current_key = key
                parsed[current_key] = [value] if value else []
                order.append(current_key)
            elif current_key:
                parsed[current_key].append(line.lstrip("-• "))
        elif current_key:
            parsed[current_key].append(line.lstrip("-• ").strip())

    for key in order:
        icon = field_icons.get(key, "•")
        raw_values = [v for v in parsed[key] if v]

        if not raw_values or (len(raw_values) == 1 and raw_values[0].upper() == "NULL"):
            st.markdown(f"**{icon} {key}:** `NULL`")
            continue

        # All fields: show value(s) on same line as key
        joined = ", ".join(raw_values)
        st.markdown(f"**{icon} {key}:** {joined}")