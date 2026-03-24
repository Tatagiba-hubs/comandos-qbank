# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import random
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv

# ── Fix charmap error on Windows terminal ────────────────────────────────────
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "question_images")

def configure_api():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing in .env file.")
    genai.configure(api_key=api_key)

# ── Extraction schema ──────────────────────────────────────────────────────────
question_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "page_number": {"type": "integer", "description": "Numero da pagina (1-indexed base do arquivo) exata onde a questao comecou."},
            "exam_origin":           {"type": "string"},
            "year":                  {"type": "string"},
            "subject":               {"type": "string"},
            "subtopic":              {"type": "string", "description": "Categoria especifica da materia, ex: 'Geometria Plana' se for Matematica."},
            "difficulty":            {"type": "string", "enum": ["Facil", "Medio", "Dificil"]},
            "question_text":         {"type": "string"},
            "has_image": {
                "type": "boolean",
                "description": "True se a questao depende de figura, grafico ou imagem na pagina."
            },
            "image_bbox": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Se has_image=true, forneca exatamente 4 inteiros [ymin, ymax, xmin, xmax] em porcentagem (0 a 100) delimitando CIRURGICAMENTE apenas a figura. EXCLUA marcas d'agua (ex: Estrategia, logotipos) e exclua o texto do enunciado."
            },
            "options": {
                "type": "object",
                "properties": {
                    "A": {"type": "string"}, "B": {"type": "string"},
                    "C": {"type": "string"}, "D": {"type": "string"},
                    "E": {"type": "string"}
                }
            },
            "correct_answer_letter": {"type": "string"},
        },
        "required": ["page_number", "exam_origin", "subject", "subtopic", "difficulty", "question_text", "options", "has_image"]
    }
}

resolution_schema = {
    "type": "object",
    "properties": {
        "resolution_1": {"type": "string"},
        "resolution_2": {"type": "string"}
    },
    "required": ["resolution_1", "resolution_2"]
}

def _render_pages_to_images(doc, start_page: int, end_page: int) -> list:
    import fitz
    os.makedirs(IMAGES_DIR, exist_ok=True)
    paths = []
    for page_num in range(start_page, end_page + 1):
        page = doc[page_num]
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_path = os.path.join(IMAGES_DIR, f"page_{page_num}.png")
        pix.save(img_path)
        paths.append(img_path)
    return paths

# ── Intelligent retry helper ──────────────────────────────────────────────────
def _call_gemini_with_retry(model, content, max_retries: int = 5):
    """
    Call Gemini with exponential backoff + jitter.
    Returns (response, None) on success or (None, error_message) on final failure.
    """
    base_delay = 4
    for attempt in range(max_retries):
        try:
            response = model.generate_content(content)
            return response, None
        except exceptions.ResourceExhausted:
            if attempt == max_retries - 1:
                return None, "Limite de cota atingido apos todas as tentativas."
            # Exponential backoff with jitter
            delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
            print(f"[AVISO] Rate limit hit (tentativa {attempt + 1}/{max_retries}). "
                  f"Aguardando {delay:.1f}s...")
            time.sleep(delay)
        except Exception as e:
            return None, str(e)
    return None, "Numero maximo de tentativas atingido."

def extract_questions_from_pdf(pdf_path: str, progress_callback=None):
    """Reliable extraction with intelligent Rate Limit handling."""
    configure_api()
    import fitz

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    CHUNK_SIZE = 10
    all_questions = []

    model = genai.GenerativeModel(
        model_name='gemini-flash-latest',
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": question_schema
        }
    )

    def _clean_json(text):
        """Removes Markdown code blocks and extra whitespace."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    for start_page in range(0, total_pages, CHUNK_SIZE):
        end_page = min(start_page + CHUNK_SIZE - 1, total_pages - 1)

        if progress_callback:
            progress_callback(start_page + 1, end_page + 1, total_pages)

        page_image_paths = _render_pages_to_images(doc, start_page, end_page)

        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
        chunk_path = f"{pdf_path}_chunk_{start_page}.pdf"
        chunk_doc.save(chunk_path)
        chunk_doc.close()

        # Add a mandatory delay between chunks to stay under RPM
        if start_page > 0:
            time.sleep(2)

        try:
            pdf_file = genai.upload_file(path=chunk_path)

            prompt = (
                f"Voce e um especialista em provas militares brasileiras. "
                f"Extraia TODAS as questoes das paginas {start_page + 1} a {end_page + 1} deste documento.\n"
                f"Para cada questao forneca:\n- page_number (exata de 1 a N)\n- exam_origin, year, subject, subtopic, difficulty\n"
                f"- subtopic: subtópico específico dentro do subject (ex: Trigonometria, Cinemática).\n"
                f"- question_text: TRASCREVA TODO O TEXTO DA QUESTAO NA INTEGRA.\n"
                f"- Se a questao tiver figura indispensavel, marque has_image=true E forneça a image_bbox [ymin, ymax, xmin, xmax] em PORCENTAGEM (0 a 100) exata da figura.\n"
                f"🚨 ALERTA CRITICO: A bbox DEVE SER UM RECORTE CIRURGICO! Nao inclua logos de cursinhos (como 'Estrategia'), cabecalhos ou rodape do PDF. Nao inclua o texto do enunciado na bbox da imagem."
            )

            response, err = _call_gemini_with_retry(model, [prompt, pdf_file])
            genai.delete_file(pdf_file.name)

            if err:
                print(f"[ERRO] Chunk pag {start_page + 1}-{end_page + 1}: {err}")
                continue

            cleaned_text = _clean_json(response.text)
            parsed = json.loads(cleaned_text)

            # Normalize difficulty to match DB expectations
            diff_map = {"Facil": "Facil", "Medio": "Medio", "Dificil": "Dificil",
                        "Fácil": "Facil", "Médio": "Medio", "Difícil": "Dificil"}

            if isinstance(parsed, list):
                for q in parsed:
                    # Resolve reliable image padding
                    p_num = q.get("page_number", start_page + 1)
                    idx = p_num - (start_page + 1)
                    
                    if 0 <= idx < len(page_image_paths):
                        if q.get("has_image"):
                            bbox = q.get("image_bbox")
                            base_img_path = page_image_paths[idx]
                            
                            # Realizar o recorte cirurgico da imagem com o Pillow (PIL)
                            if bbox and len(bbox) == 4:
                                try:
                                    from PIL import Image
                                    with Image.open(base_img_path) as img:
                                        w, h = img.size
                                        ymin, ymax, xmin, xmax = bbox
                                        # Clamp limits to 0-100 to prevent out of bounds
                                        ymin, ymax = max(0, min(100, ymin)), max(0, min(100, ymax))
                                        xmin, xmax = max(0, min(100, xmin)), max(0, min(100, xmax))
                                        
                                        crop_box = (
                                            int((xmin / 100.0) * w),
                                            int((ymin / 100.0) * h),
                                            int((xmax / 100.0) * w),
                                            int((ymax / 100.0) * h)
                                        )
                                        # Fix inverted coordinates if any
                                        if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
                                            cropped = img.crop(crop_box)
                                            crop_path = base_img_path.replace(".png", f"_crop_q{len(all_questions)+1}.png")
                                            cropped.save(crop_path)
                                            q["image_path"] = crop_path
                                        else:
                                            q["image_path"] = base_img_path
                                except Exception as e:
                                    print(f"Erro ao recortar imagem: {e}")
                                    q["image_path"] = base_img_path
                            else:
                                q["image_path"] = base_img_path
                        else:
                            q["image_path"] = ""
                    else:
                        q["image_path"] = ""
                        
                    q["resolution_1"] = ""
                    q["resolution_2"] = ""
                    
                    # Normalize difficulty
                    raw_diff = q.get("difficulty", "Medio")
                    q["difficulty"] = diff_map.get(raw_diff, raw_diff)
                
                # yield the chunk of questions
                yield parsed
                all_questions.extend(parsed)

        except Exception as e:
            print(f"[ERRO] Pag {start_page + 1}-{end_page + 1}: {e}")
        finally:
            if os.path.exists(chunk_path):
                try:
                    os.remove(chunk_path)
                except Exception:
                    pass

    doc.close()
    return


def generate_resolution(question_text: str, options: dict) -> dict:
    configure_api()
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash-exp',
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": resolution_schema
        }
    )

    opts_text = "\n".join(f"{k}) {v}" for k, v in sorted(options.items()))
    prompt = (f"Você é um professor pardal rigorosíssimo de exatas. "
              f"Resolva de forma ALGEBRICA, PASSO A PASSO e MATEMATICA. Se for humana/linguagens, focar na técnica interpretativa em passos lógicos.\n"
              f"ENUNCIADO:\n{question_text}\nALTERNATIVAS:\n{opts_text}\n"
              f"Instruções:\n"
              f"- resolution_1: Mostre a prova algébrica/lógica completa, linha por linha, detalhando todas as equações e leis utilizadas.\n"
              f"- resolution_2: Mostre um bizu ou método alternativo rápido caso exista, senão resuma os macetes da questão.")

    response, err = _call_gemini_with_retry(model, prompt, max_retries=3)
    if err:
        return {"resolution_1": f"Erro: {err}", "resolution_2": "Tente novamente mais tarde."}
    return json.loads(response.text)


def generate_custom_questions(exam_origin: str, subject: str, subtopic: str, difficulty: str, num_questions: int) -> list:
    configure_api()
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash-exp',
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": question_schema
        }
    )

    prompt = (f"Crie uma lista INÉDITA (autoral) de {num_questions} questões para concursos no estilo '{exam_origin}'.\n"
              f"Matéria: {subject}\nSubtópico: {subtopic}\nDificuldade: {difficulty}.\n"
              f"As questões não devem requerer imagens (has_image=false).\n"
              f"Forneça com muito capricho, criando enredos interessantes operacionais militares se for o caso.")

    response, err = _call_gemini_with_retry(model, prompt, max_retries=3)
    if err:
        print(f"[ERRO] Falha ao gerar questoes: {err}")
        return []
    
    try:
        parsed = json.loads(response.text)
        if isinstance(parsed, list):
            for q in parsed:
                # Normaliza campos
                q["page_number"] = 1
                q["has_image"] = False
                q["image_path"] = ""
                q["resolution_1"] = ""
                q["resolution_2"] = ""
            return parsed
        return []
    except Exception as e:
        print(f"[ERRO] Parse failed: {e}")
        return []

def analyze_discursive_image(question_text: str, image_bytes: bytes = None) -> str:
    configure_api()
    model = genai.GenerativeModel(model_name='gemini-1.5-flash')
    
    if image_bytes:
        prompt = (f"Avalie a resolução manuscrita/enviada da seguinte questão discursiva.\n"
                  f"QUESTÃO: {question_text}\n"
                  f"Instruções:\n"
                  f"1. Se o aluno acertou de forma matemática e coerente, elogie e detalhe por que está correto.\n"
                  f"2. Se ele errou ou pulou passos, aponte exatamente onde foi a falha no raciocínio (linha a linha) e deduza o que ele tentou fazer.\n"
                  f"3. Mostre a resolução passo a passo ideal e correta da banca.\n"
                  f"4. Dê uma nota ou pontuação no padrão militar rigoroso.")
        
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}
        try:
            response = model.generate_content([prompt, image_part])
            return response.text
        except Exception as e:
            return f"Erro na análise: {str(e)}"
    else:
        prompt = (f"Esta é uma questão discursiva e o aluno não enviou foto da resolução.\n"
                  f"QUESTÃO: {question_text}\n"
                  f"Por favor, apresente o padrão de resposta (gabarito) detalhado, passo a passo, mostrando toda a dedução lógica e algébrica esperada por uma banca militar rigorosa.")
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Erro na formatação do padrão de resposta: {str(e)}"

def evaluate_essay(essay_text: str, theme: str = "Tema livre", image_bytes: bytes = None) -> str:
    configure_api()
    model = genai.GenerativeModel(model_name='gemini-1.5-pro')
    
    prompt = (f"Você é um corretor de redação de um concurso militar de alto nível (EsPCEx/ESA).\n"
              f"TEMA: {theme}\n"
              f"Instruções:\n"
              f"1. Analise o texto quanto à Gramática (Norma Culta), Coesão/Coerência, Argumentação e Proposta de Intervenção.\n"
              f"2. Se houver imagem, considere a caligrafia e a estrutura visual da folha.\n"
              f"3. Dê uma nota de 0 a 100.\n"
              f"4. Forneça um feedback detalhado dividindo por tópicos, apontando erros específicos e como melhorar.")
    
    parts = [prompt]
    if essay_text:
        parts.append(essay_text)
    if image_bytes:
        parts.append({"mime_type": "image/jpeg", "data": image_bytes})
        
    try:
        response = model.generate_content(parts)
        return response.text
    except Exception as e:
        return f"Erro na correção da redação: {str(e)}"

if __name__ == "__main__":
    pass
