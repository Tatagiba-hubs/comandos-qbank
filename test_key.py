import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(override=True)
api_key = os.getenv("GEMINI_API_KEY")
print(f"Loaded Key: {api_key[:5]}...{api_key[-5:]}" if api_key else "NO KEY FOUND")

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

try:
    print("Enviando ping para o Gemini...")
    response = model.generate_content("Responda com 'OK' se voce consegue me ouvir.")
    print("Resposta recebida:")
    print(response.text)
    print(">> SUCESSO: A chave esta funcionando e o modelo gemini-2.0-flash responde.")
except Exception as e:
    print(f">> ERRO DA API REPORTADO: {e}")
