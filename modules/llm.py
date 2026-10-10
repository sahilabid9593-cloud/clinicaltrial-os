"""
ClinicalTrial OS - shared AI helper.

Order of providers:
  1. Groq cloud API  (if GROQ_API_KEY is set in Streamlit secrets or .env)
  2. Local Ollama    (if running on http://localhost:11434)
  3. None            -> callers fall back to non-AI output, nothing crashes
"""
import os
import json
import requests

GROQ_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _secret(name, default=None):
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


def provider():
    """Name of the AI provider that will be used, or None."""
    if _secret("GROQ_API_KEY"):
        return "Groq"
    try:
        requests.get("http://localhost:11434", timeout=0.5)
        return "Ollama (local)"
    except Exception:
        return None


def ask_llm(prompt, max_tokens=1200):
    """Return the model's text answer, or None if no AI provider is available."""
    key = _secret("GROQ_API_KEY")
    if key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key, base_url=GROQ_URL)
            resp = client.chat.completions.create(
                model=_secret("GROQ_MODEL", DEFAULT_GROQ_MODEL),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"Groq error: {e}")
    try:
        r = requests.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": prompt,
                                            "stream": False}, timeout=120)
        return r.json()["response"]
    except Exception:
        return None


def ask_llm_json(prompt):
    """Ask for JSON and parse it. Returns a dict or None."""
    text = ask_llm(prompt)
    if not text:
        return None
    try:
        start, end = text.find("{"), text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None
