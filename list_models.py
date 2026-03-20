import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv(override=True)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
    print("SUCCESS_LIST")
except Exception as e:
    print(f"ERROR: {e}")
