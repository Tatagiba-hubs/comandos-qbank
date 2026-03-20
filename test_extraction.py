import fitz
import time
import json
import traceback
import sys
import os

# Adds current directory to sys.path so we can import ai_extractor
sys.path.insert(0, os.path.dirname(__file__))
from ai_extractor import configure_api, _call_gemini_with_retry, question_schema
import google.generativeai as genai

pdf_path = r"C:\Users\joaot\Downloads\67022bd6-f1bb-43e6-952b-0d8a95e90f23.pdf"

print(f"Abrindo PDF: {pdf_path}")
try:
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"Total de paginas: {total_pages}")
    
    # Limitando teste as 5 primeiras paginas
    start_page = 0
    end_page = min(4, total_pages - 1)
    
    configure_api()
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": question_schema
        }
    )
    
    chunk_doc = fitz.open()
    chunk_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
    chunk_path = "temp_test.pdf"
    chunk_doc.save(chunk_path)
    chunk_doc.close()
    
    print(f"Enviando bloco de paginas {start_page+1} a {end_page+1} para o Gemini...")
    t0 = time.time()
    pdf_file = genai.upload_file(path=chunk_path)
    
    prompt = (
        f"Voce e um especialista em provas militares brasileiras. "
        f"Extraia TODAS as questoes das paginas {start_page + 1} a {end_page + 1} deste documento. "
        f"Forneça: pagina exata, origem, ano, materia, dificuldade, enunciado, opcoes e gabarito. "
        f"Se a questao contem alguma imagem/grafico indispensavel para resolve-la, marque has_image=true."
    )
    
    print("Aguardando resposta da IA...")
    response, err = _call_gemini_with_retry(model, [prompt, pdf_file])
    genai.delete_file(pdf_file.name)
    t1 = time.time()
    
    print(f"Tempo de resposta: {t1-t0:.2f}s")
    if err:
        print(f"Erro retornado: {err}")
    else:
        print("---")
        print("Amostra do Raw JSON (500 chars):")
        print(response.text[:500])
        print("---")
        try:
            parsed = json.loads(response.text)
            print(f">>> SUCESSO: A IA mapeou {len(parsed)} questoes nesse bloco.")
        except Exception as e:
            print(f">>> FALHA DE PARSER: O Gemini retornou um JSON invalido: {e}")
            
    if os.path.exists(chunk_path):
        os.remove(chunk_path)

except Exception as e:
    traceback.print_exc()
