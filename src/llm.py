import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


def _get_secret(key: str, default: str = None) -> str:
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


def query_nrp(prompt: str, system_prompt: str = "You are a concise academic assistant.") -> str:
    """Single wrapper function for all model calls to NRP."""
    base_url = _get_secret("NRP_BASE_URL")
    api_key = _get_secret("NRP_API_KEY")
    model_name = _get_secret("NRP_MODEL", "gpt-oss")

    if not base_url or not api_key:
        raise EnvironmentError("Missing NRP_BASE_URL or NRP_API_KEY in .env or Streamlit Secrets.")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()