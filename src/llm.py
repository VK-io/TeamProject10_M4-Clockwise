import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("NRP_BASE_URL")
API_KEY = os.getenv("NRP_API_KEY")
MODEL_NAME = os.getenv("NRP_MODEL", "gpt-oss")

def query_nrp(prompt: str, system_prompt: str = "You are a concise academic assistant.") -> str:
    """Single wrapper function for all model calls to NRP."""
    if not BASE_URL or not API_KEY:
        raise EnvironmentError("Missing NRP_BASE_URL or NRP_API_KEY in .env file.")
    
    client = OpenAI(
        base_url=BASE_URL,
        api_key=API_KEY
    )
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()