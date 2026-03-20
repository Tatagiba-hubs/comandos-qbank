import os
import urllib.request
from fpdf import FPDF
from typing import List, Dict, Any

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONT_REGULAR = os.path.join(_FONT_DIR, "Roboto-Regular.ttf")
_FONT_BOLD    = os.path.join(_FONT_DIR, "Roboto-Bold.ttf")
_FONT_ITALIC  = os.path.join(_FONT_DIR, "Roboto-Italic.ttf")

_FONT_URLS = {
    _FONT_REGULAR: "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf",
    _FONT_BOLD:    "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf",
    _FONT_ITALIC:  "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Italic.ttf",
}

def _ensure_fonts():
    """Download Roboto fonts if they are not cached locally."""
    os.makedirs(_FONT_DIR, exist_ok=True)
    for path, url in _FONT_URLS.items():
        if not os.path.exists(path):
            print(f"[pdf_generator] Baixando fonte: {os.path.basename(path)} ...")
            urllib.request.urlretrieve(url, path)

class SimuladoPDF(FPDF):
    def header(self):
        banner_path = os.path.join(os.path.dirname(__file__), "hero_banner.png")
        watermark_path = os.path.join(os.path.dirname(__file__), "watermark.png")

        # ── Marca d'Água (Caveira) ──
        if os.path.exists(watermark_path):
            with self.local_context(fill_opacity=0.15, stroke_opacity=0.15):
                self.image(watermark_path, x=45, y=70, w=120)

        # ── Logo do Cabeçalho Padrão ──
        if os.path.exists(banner_path):
            self.image(banner_path, 10, 8, 20)
            self.set_x(35)
        
        self.set_font('Roboto', 'B', 16)
        self.cell(0, 10, 'COMANDOS QBANK', new_x="LMARGIN", new_y="NEXT", align='L')
        
        if os.path.exists(banner_path):
            self.set_x(35)
        self.set_font('Roboto', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'Simulado de Elite Focado', new_x="LMARGIN", new_y="NEXT", align='L')
        
        self.set_text_color(0, 0, 0)
        self.ln(10)
        
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Roboto', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Página {self.page_no()}', align='C')
        self.set_text_color(0, 0, 0)


def generate_simulado_pdf(questions: List[Dict[str, Any]], output_path: str, espaco_resolucao: bool = True):
    _ensure_fonts()

    # instanciar com margens seguras
    pdf = SimuladoPDF()
    pdf.set_margins(left=15, top=15, right=15)
    
    pdf.add_font('Roboto', '',  _FONT_REGULAR)
    pdf.add_font('Roboto', 'B', _FONT_BOLD)
    pdf.add_font('Roboto', 'I', _FONT_ITALIC)

    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    for i, q in enumerate(questions):
        # Header da questão (materia, origem, dificuldade) num fundo leve
        pdf.set_fill_color(240, 245, 240)
        pdf.set_font('Roboto', 'B', 11)
        
        # Adiciona um pequeno espaço antes da questão (exceto a primeira)
        if i > 0:
            pdf.ln(5)
            
        header_text = (
            f"Questão {i+1} | {q.get('subject', 'Geral').upper()} "
            f"[{q.get('exam_origin', 'N/A')} {q.get('year', '')} - {q.get('difficulty', 'Medio')}]"
        )
        pdf.multi_cell(0, 8, txt=header_text, fill=True, new_x="LMARGIN", new_y="NEXT", border=1)
        pdf.ln(2)

        # Enunciado da questão
        pdf.set_font('Roboto', '', 11)
        q_text = q.get('question_text', '')
        pdf.multi_cell(0, 6, txt=q_text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Alternativas com espaçamento adequado
        opts = q.get('options', {})
        if isinstance(opts, dict):
            for letter in sorted(opts.keys()):
                pdf.set_font('Roboto', 'B', 11)
                pdf.cell(8, 6, txt=f"{letter})", new_x="RIGHT", new_y="TOP")
                pdf.set_font('Roboto', '', 11)
                pdf.multi_cell(0, 6, txt=f"{opts[letter]}", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)

        # Adicionar o espaço em branco exigido pelo comandante para rascunho
        if espaco_resolucao:
            pdf.ln(60) # 6 centímetros lineares de vácuo puro para resolução
        else:
            pdf.ln(4)

    # ── Página de Gabarito ──
    pdf.add_page()
    pdf.set_font('Roboto', 'B', 16)
    pdf.cell(0, 15, 'Gabarito Oficial do Simulado', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(5)
    
    pdf.set_font('Roboto', '', 12)
    
    # Criar tabela de gabarito para ficar mais bonito
    col_width = 40
    line_height = 8
    
    # max colunas por linha (ex: 4 colunas)
    max_cols = 4
    col_count = 0
    
    for i, q in enumerate(questions):
        ans = str(q.get('correct_answer_letter') or 'N/A')
        # Alterna cor do texto para o Certo ficar discreto e elegante
        pdf.set_font('Roboto', 'B', 12)
        pdf.cell(15, line_height, f"{i+1}.", align="R")
        pdf.set_font('Roboto', '', 12)
        
        if col_count == max_cols - 1:
            pdf.cell(25, line_height, f"  {ans}", new_x="LMARGIN", new_y="NEXT", align="L")
            col_count = 0
        else:
            pdf.cell(25, line_height, f"  {ans}", align="L")
            col_count += 1
            
    # Caso sobrou colunas na última linha
    if col_count != 0:
        pdf.ln(line_height)

    pdf.output(output_path)

if __name__ == "__main__":
    pass
