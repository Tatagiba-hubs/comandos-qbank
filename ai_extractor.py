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
        "required": ["page_number", "exam_origin", "subject", "difficulty", "question_text", "options", "has_image"]
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
    CHUNK_SIZE = 15
    all_questions = []

    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": question_schema
        }
    )

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

        # Add a small mandatory delay between chunks to stay under RPM (reduzido)
        if start_page > 0:
            time.sleep(1)

        try:
            pdf_file = genai.upload_file(path=chunk_path)

            prompt = (
                f"Voce e um especialista em provas militares brasileiras. "
                f"Extraia TODAS as questoes das paginas {start_page + 1} a {end_page + 1} deste documento.\n"
                f"Para cada questao forneca:\n- page_number (exata de 1 a N)\n- origin, year, subject, difficulty\n"
                f"- question_text: TRASCREVA TODO O TEXTO DA QUESTAO NA INTEGRA.\n"
                f"- Se a questao tiver figura indispensavel, marque has_image=true E forneça a image_bbox [ymin, ymax, xmin, xmax] em PORCENTAGEM (0 a 100) exata da figura.\n"
                f"🚨 ALERTA CRITICO: A bbox DEVE SER UM RECORTE CIRURGICO! Nao inclua logos de cursinhos (como 'Estrategia'), cabecalhos ou rodape do PDF. Nao inclua o texto do enunciado na bbox da imagem, senao vc cortara a questao seguinte!"
            )

            response, err = _call_gemini_with_retry(model, [prompt, pdf_file])
            genai.delete_file(pdf_file.name)

            if err:
                print(f"[ERRO] Chunk pag {start_page + 1}-{end_page + 1}: {err}")
                continue

            parsed = json.loads(response.text)

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
    return all_questions


def generate_resolution(question_text: str, options: dict) -> dict:
    configure_api()
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": resolution_schema
        }
    )

    opts_text = "\n".join(f"{k}) {v}" for k, v in sorted(options.items()))
    prompt = f"Resolva didaticamente:\nENUNCIADO:\n{question_text}\nALTERNATIVAS:\n{opts_text}"

    response, err = _call_gemini_with_retry(model, prompt, max_retries=3)
    if err:
        return {"resolution_1": f"Erro: {err}", "resolution_2": "Tente novamente mais tarde."}
    return json.loads(response.text)


if __name__ == "__main__":
    pass
