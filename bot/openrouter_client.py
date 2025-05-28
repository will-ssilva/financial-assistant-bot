import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "meta-llama/llama-3-8b-instruct"

def query_openrouter(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/seu-usuario/seu-projeto",
        "X-Title": "AssistenteFinanceiroTelegram"
    }

    json_data = {
        "model": MODEL,
        "messages": messages
    }

    response = requests.post(OPENROUTER_API_URL, headers=headers, json=json_data)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()
