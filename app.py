# -*- coding: utf-8 -*-
import sys
import streamlit as st
import json
import os
import hashlib
import base64
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# ── Fix charmap on Windows ────────────────────────────────────────────────────
if hasattr(sys.stdout, 'reconfigure'):
    try:
        getattr(sys.stdout, 'reconfigure')(encoding='utf-8')
    except Exception:
        pass

# Force loading .env variables
load_dotenv(override=True)
import pandas as pd
from database import (init_db, insert_question, get_all_questions,
                      update_resolution, is_pdf_cached, mark_pdf_cached,
                      export_to_json, export_to_csv,
                      save_performance, get_performance_stats,
                      get_user_badges, award_badge)
from ai_extractor import extract_questions_from_pdf, generate_resolution, generate_custom_questions, analyze_discursive_image, evaluate_essay
from pdf_generator import generate_simulado_pdf

st.set_page_config(page_title="COMANDOS QBANK", page_icon="🗡️", layout="wide")

# Theme state
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"

def toggle_theme():
    if st.session_state["theme"] == "dark":
        st.session_state["theme"] = "light"
    else:
        st.session_state["theme"] = "dark"

# Initialize DB
from database import get_user_rank
try:
    init_db()
    import auth
    auth.init_default_admin()
except Exception as e:
    st.error(f"Erro Crítico no Banco de Dados: As credenciais de acesso ou a conexão com o banco não estão funcionando.")
    st.error(f"Detalhe Técnico: `{str(e)}`")
    st.info("Verifique se as variáveis de ambiente em `st.secrets` ou `.env` estão corretas e se o servidor aceita a conexão. O aplicativo foi pausado para evitar falhas graves.")
    st.stop()

if "user" not in st.session_state:
    st.session_state["user"] = None

# ── Theme CSS ──────────────────────────────────────────────────────────────────
# The config.toml guarantees a dark base. If user toggles light, we force CSS overrides.
if st.session_state["theme"] == "light":
    st.markdown("""
        <style>
        .stApp { background-color: #f4f7f0 !important; }
        .stApp, .stMarkdown, p, span, div { color: #1a2a10 !important; }
        .stButton>button { background-color: #e0e6db !important; color: #1a2a10 !important; border-color: #c0ccc0 !important; }
        .stTextInput>div>div>input { background-color: #ffffff !important; color: #1a2a10 !important; }
        div[data-baseweb="select"] > div { background-color: #ffffff !important; }
        </style>
    """, unsafe_allow_html=True)

# ── Battle loading animation ───────────────────────────────────────────────────
_SOL = '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="80" viewBox="0 0 32 40"><rect x="6" y="0" width="14" height="3" rx="1" fill="#3d5228"/><rect x="5" y="2" width="16" height="5" rx="1" fill="#4a6030"/><rect x="7" y="7" width="10" height="8" rx="1" fill="#7a5a38"/><rect x="14" y="9" width="2" height="2" fill="#220d00"/><rect x="5" y="7" width="2" height="5" fill="#4a6030"/><rect x="4" y="15" width="20" height="12" rx="1" fill="#4a6030"/><rect x="22" y="19" width="5" height="5" rx="1" fill="#4a6030"/><rect x="25" y="20" width="7" height="3" fill="#1e1e1e"/><rect x="2" y="16" width="4" height="8" rx="1" fill="#4a6030"/><rect x="4" y="27" width="20" height="3" fill="#3a4a20"/><rect x="5" y="30" width="7" height="7" rx="1" fill="#3d5228"/><rect x="3" y="36" width="10" height="4" rx="1" fill="#1a1208"/><rect x="14" y="30" width="7" height="7" rx="1" fill="#3d5228"/><rect x="14" y="36" width="10" height="4" rx="1" fill="#1a1208"/></svg>'
_BCSS = '<style>.bs{width:100%;height:200px;position:relative;overflow:hidden;background:linear-gradient(to bottom,#050a05,#0a120a 60%,#111a0c);border-radius:10px;border:1px dashed #3a5a2a;margin-bottom:20px}.gnd{position:absolute;bottom:48px;left:0;right:0;height:2px;background:#2a3a1a}.sl{position:absolute;bottom:50px;left:30px;animation:bob .45s steps(2,end) infinite}.sr{position:absolute;bottom:50px;right:30px;transform:scaleX(-1);animation:bobr .45s steps(2,end) infinite;animation-delay:.22s}@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}@keyframes bobr{0%,100%{transform:scaleX(-1) translateY(0)}50%{transform:scaleX(-1) translateY(-3px)}}.fl{position:absolute;left:92px;bottom:70px;width:14px;height:10px;border-radius:50%;background:radial-gradient(circle,#fff 0%,#e8c840 40%,transparent 80%);filter:blur(1px);animation:blnk .45s steps(2,end) infinite}.fr{position:absolute;right:92px;bottom:70px;width:14px;height:10px;border-radius:50%;background:radial-gradient(circle,#fff 0%,#e8c840 40%,transparent 80%);filter:blur(1px);animation:blnk .45s steps(2,end) infinite;animation-delay:.22s}@keyframes blnk{0%,44%{opacity:1}45%,100%{opacity:0}}.b{position:absolute;height:2px;bottom:76px;border-radius:1px}.b1{width:10px;background:linear-gradient(to right,transparent,#c8a820,#fff);animation:bfr .3s linear infinite}.b2{width:10px;background:linear-gradient(to right,transparent,#c8a820,#fff);animation:bfr .3s linear infinite;animation-delay:.15s}.b3{width:10px;background:linear-gradient(to left,transparent,#c8a820,#fff);animation:bfl .3s linear infinite;animation-delay:.075s}.b4{width:10px;background:linear-gradient(to left,transparent,#c8a820,#fff);animation:bfl .3s linear infinite;animation-delay:.225s}@keyframes bfr{0%{left:102px;opacity:1}90%{opacity:1}100%{left:calc(100% - 105px);opacity:0}}@keyframes bfl{0%{right:102px;opacity:1}90%{opacity:1}100%{right:calc(100% - 105px);opacity:0}}.smk{position:absolute;width:5px;height:5px;border-radius:50%;background:rgba(140,160,100,.5);animation:puf 1s ease-out infinite}.s1{left:90px;bottom:66px;animation-delay:0s}.s2{left:96px;bottom:66px;animation-delay:.35s}.s3{right:90px;bottom:66px;animation-delay:.18s}.s4{right:96px;bottom:66px;animation-delay:.53s}@keyframes puf{0%{opacity:.6;transform:scale(1) translateY(0)}100%{opacity:0;transform:scale(3.5) translateY(-14px)}}.bt{position:absolute;bottom:10px;width:100%;text-align:center;color:#7ab050;font-family:monospace;font-size:12px;font-weight:bold;letter-spacing:2px;text-shadow:0 0 8px rgba(100,180,60,.5)}</style>'

def _battle_html(txt):
    return (_BCSS + '<div class="bs"><div class="gnd"></div>'
        + '<div class="sl">' + _SOL + '</div>'
        + '<div class="sr">' + _SOL + '</div>'
        + '<div class="fl"></div><div class="fr"></div>'
        + '<div class="b b1"></div><div class="b b2"></div>'
        + '<div class="b b3"></div><div class="b b4"></div>'
        + '<div class="smk s1"></div><div class="smk s2"></div>'
        + '<div class="smk s3"></div><div class="smk s4"></div>'
        + '<div class="bt">' + txt + '</div></div>')

# ── Hero Banner & Signature ────────────────────────────────────────────────────
_skull_path = os.path.join(os.path.dirname(__file__), "skull_logo.png")
if os.path.exists(_skull_path):
    with open(_skull_path, "rb") as _f:
        _skull_b64 = base64.b64encode(_f.read()).decode()
    _skull_img = f"data:image/png;base64,{_skull_b64}"
else:
    _skull_img = ""

_banner_path = os.path.join(os.path.dirname(__file__), "hero_banner.png")
if os.path.exists(_banner_path):
    with open(_banner_path, "rb") as _f:
        _b64 = base64.b64encode(_f.read()).decode()
    _bg_css = f"url('data:image/png;base64,{_b64}')"
else:
    _bg_css = "linear-gradient(135deg, #050a05 0%, #000000 100%)"

h_col1, h_col2 = st.columns([0.9, 0.1])
with h_col2:
    btn_text = "☀️ Claro" if st.session_state["theme"] == "dark" else "🌙 Escuro"
    st.button(btn_text, on_click=toggle_theme, use_container_width=True)

# Define gradient based on theme
if st.session_state["theme"] == "light":
    gradient = "rgba(255,255,255,0.7) 0%, rgba(240,245,235,0.9) 100%"
    title_col = "#2c4a1b"
    sub_col = "#3b5c2a"
    accent_green = "#4b5320"
else:
    gradient = "rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.85) 100%"
    title_col = "#00FF41" # Matrix Green
    sub_col = "#888"
    accent_green = "#00FF41"

st.markdown(f"""
<style>
.hero-banner {{
    width: 100%;
    min-height: 280px;
    background: linear-gradient(to bottom, {gradient}), {_bg_css};
    background-size: cover;
    background-position: center;
    border-radius: 14px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    margin-bottom: 24px;
    text-align: center;
    box-shadow: 0 10px 40px rgba(0,0,0,0.8);
    border: 1px solid rgba(0, 255, 65, 0.1);
}}
.skull-signature {{
    width: 100px;
    margin-bottom: 20px;
    filter: drop-shadow(0 0 15px rgba(255,255,255,0.4));
}}
.hero-title {{
    font-size: 3.2rem;
    font-weight: 900;
    letter-spacing: 0.15em;
    color: {title_col} !important;
    text-shadow: 0 0 20px rgba(0, 255, 65, 0.4);
    margin: 0;
    font-family: 'Outfit', sans-serif;
}}
.hero-sub {{
    font-size: 1.1rem;
    color: {sub_col} !important;
    margin-top: 15px;
    letter-spacing: 0.05em;
    text-shadow: 0 1px 6px rgba(0,0,0,0.9);
    text-transform: uppercase;
    font-weight: 300;
}}
</style>
<div class="hero-banner">
  <img src="{_skull_img}" class="skull-signature">
  <div class="hero-title">COMANDOS QBANK</div>
  <div class="hero-sub">Elite de Inteligência em Missões Operacionais</div>
</div>
""", unsafe_allow_html=True)

# ── UI MAKEOVER: PREMIUM TACTICAL BLACK & GREEN ───────────────────────────────
st.markdown(f"""
<style>
    /* Global Theme & Premium Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;700;900&family=JetBrains+Mono&display=swap');
    
    .stApp {{
        background: radial-gradient(circle at 50% 0%, #101810, #000000);
        color: #e0e0e0;
        font-family: 'Outfit', sans-serif;
    }}

    /* Vertical Navigation Simulation (Sidebar) */
    [data-testid="stSidebar"] {{
        background-color: #050505 !important;
        border-right: 2px solid {accent_green}44 !important;
        width: 300px !important;
    }}
    
    /* Sidebar Skull Header */
    .sidebar-header {{
        text-align: center;
        padding: 20px 0;
    }}
    .sidebar-skull {{
        width: 60px;
        filter: drop-shadow(0 0 10px {accent_green}66);
    }}

    /* Glassmorphism for Containers */
    [data-testid="stVerticalBlock"] > div:has(div.stExpander), 
    [data-testid="stForm"] {{
        background: rgba(10, 20, 10, 0.4);
        backdrop-filter: blur(8px);
        border: 1px solid {accent_green}33;
        border-radius: 12px;
        padding: 25px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.6);
    }}
    
    /* Headers with Tactical Green */
    h1, h2, h3 {{
        color: {accent_green} !important;
        font-family: 'Outfit', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 900 !important;
        text-shadow: 0 0 15px {accent_green}33;
        border-left: 4px solid {accent_green};
        padding-left: 15px !important;
        margin-top: 30px !important;
    }}
    
    /* Tactical Buttons (Green Theme) */
    .stButton>button {{
        background: linear-gradient(135deg, #0a1a0a 0%, #1a331a 100%) !important;
        color: {accent_green} !important;
        border: 1px solid {accent_green} !important;
        border-radius: 4px !important;
        font-weight: 900 !important;
        text-transform: uppercase !important;
        letter-spacing: 2px;
        height: 52px;
        transition: all 0.2s ease-in-out !important;
    }}
    .stButton>button:hover {{
        background: {accent_green} !important;
        color: #000 !important;
        box-shadow: 0 0 25px {accent_green}88;
        transform: scale(1.02);
    }}
    
    /* Custom Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 15px;
        padding: 12px;
        background: rgba(0,0,0,0.5);
        border-radius: 12px;
        border: 1px solid {accent_green}22;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent !important;
        border: 1px solid transparent !important;
        color: #666 !important;
        padding: 10px 20px !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: {accent_green} !important;
        background: {accent_green}15 !important;
        border: 1px solid {accent_green}44 !important;
        text-shadow: 0 0 10px {accent_green}33;
    }}

    /* Inputs & Selects */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {{
        background-color: #0c0f0c !important;
        color: #fff !important;
        border: 1px solid {accent_green}33 !important;
    }}
    
</style>
""", unsafe_allow_html=True)

# ── LOGIN WALL ────────────────────────────────────────────────────────────────
if st.session_state["user"] is None:
    st.markdown("<h2 style='text-align: center'>🛡️ Acesso Restrito ao Quartel General</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        tab_log, tab_reg = st.tabs(["Apresentar-se (Login)", "Alistamento Voluntário"])
        
        with tab_log:
            with st.form("login_form"):
                username = st.text_input("Usuario (Soldado ou Comandante)")
                password = st.text_input("Senha", type="password")
                submit = st.form_submit_button("Entrar no Quartel", use_container_width=True)
                if submit:
                    user_data = auth.authenticate_user(username, password)
                    if user_data:
                        st.session_state["user"] = user_data
                        st.rerun()
                    else:
                        st.error("Credenciais invalidas. A Sentinela bloqueou a entrada!")
                        
        with tab_reg:
            with st.form("register_form"):
                st.markdown("Bem-vindo recruta. Cadastre seu nome e senha para acessar o Simulador das Forças Especiais.")
                new_u = st.text_input("Escolha um Nome de Guerra (Usuario)")
                new_p = st.text_input("Crie uma Senha", type="password")
                reg_submit = st.form_submit_button("Jurar Bandeira (Cadastrar)", use_container_width=True)
                if reg_submit:
                    if new_u and new_p:
                        if auth.create_user(new_u, new_p, 'student'):
                            st.success(f"Recruta '{new_u}' alistado com sucesso! Volte à aba 'Login' para entrar.")
                        else:
                            st.error("Este nome já está em uso na corporação. Tente outro.")
                    else:
                        st.warning("Preencha todos os campos do formulário.")
                        
    st.stop() # Bloqueia o render do resto do app


# ── SIDEBAR (Perfil e XP) ─────────────────────────────────────────────────────
user_info = st.session_state["user"]
rank, pts = get_user_rank(user_info['id'], user_info['role'])

with st.sidebar:
    st.markdown(f"""
    <div class="sidebar-header">
        <img src="{_skull_img}" class="sidebar-skull">
        <div style="color:{accent_green}; font-weight:900; letter-spacing:2px; margin-top:10px;">COMANDOS QBANK</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"### 🎖️ {rank}")
    st.markdown(f"**NOME:** {user_info['username'].upper()}")
    if user_info['role'] != 'admin':
        st.markdown(f"**XP COMBATE:** {pts} pts")
        
        badges = get_user_badges(user_info['id'])
        if badges:
            st.markdown("🎖️ **CONDECORAÇÕES:**")
            for b in badges:
                st.caption(f"- {b['badge_name']}")
    else:
        st.markdown("👑 **COMANDO SUPREMO**")
        
    st.divider()
    if st.button("🚪 Sair do Quartel / Logout", use_container_width=True):
        st.session_state["user"] = None
        st.rerun()

# ── LOGIC FOR TABS (Premium Tactical Navigation) ──────────────────────────────
# We use tactical icons and names as requested for the Black & Green theme
common_labels = ["🗡️ Banco", "📄 Missões", "💻 Campo Treino", "🤖 Lista IA", "✍️ Redação", "⚔️ Duelo", "🏆 Elite"]
if user_info['role'] == 'admin':
    all_tabs = ["📤 Infiltração"] + common_labels + ["⚙️ Config", "👥 Tropa"]
else:
    all_tabs = common_labels

with st.sidebar:
    st.markdown("---")
    selected_tab = st.radio("NAVEGAÇÃO", all_tabs, label_visibility="collapsed")

# ── Tab 1: Upload PDF (ADMIN ONLY) ──────────────────────────────────────────────
if user_info['role'] == 'admin':
    if selected_tab == '📤 Infiltração':
        st.header("Processar Prova em PDF via Inteligência Artificial")
        uploaded_file = st.file_uploader("Envie a prova em PDF", type="pdf")

        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            file_hash = hashlib.md5(file_bytes).hexdigest()
            cached = is_pdf_cached(file_hash)

            if cached:
                st.warning(
                    f"🗄️ **PDF ja processado!** Este arquivo '{cached['file_name']}' foi adicionado em "
                    f"{cached['processed_at']} e gerou **{cached['questions_extracted']} questoes**. "
                    f"Para forçar o reprocessamento, use outro arquivo."
                )
            else:
                if st.button("Ler PDF com IA"):
                    if not os.getenv("GEMINI_API_KEY"):
                        st.error("Chave de API do Gemini nao configurada! Va na aba 'Configurações' primeiro.")
                    else:
                        loading_placeholder = st.empty()
                        progress_bar = st.progress(0, text="INFILTRANDO NO TERRITÓRIO... 0%")
                    
                        loading_placeholder.markdown(
                            _battle_html("INFILTRANDO E MAPEANDO O TERRITORIO INIMIGO... AGUARDE"),
                            unsafe_allow_html=True)

                        def update_progress(start, end, total):
                            pct = min((int(end) / int(total)) * 100, 100)
                            txt = f"TERRITORIO: PAG {start}-{end}/{total} | {pct:.0f}% CONQUISTADO"
                            loading_placeholder.markdown(_battle_html(txt), unsafe_allow_html=True)
                            progress_bar.progress(int(pct), text=txt)

                        temp_path = f"temp_{uploaded_file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(file_bytes)

                        try:
                            total_extracted = 0
                            # Iterate over the generator to get questions chunk by chunk
                            for questions_chunk in extract_questions_from_pdf(temp_path, update_progress):
                                for q in questions_chunk:
                                    exam = q.get('exam_origin', 'Desconhecido')
                                    year = q.get('year', '')
                                    subj = q.get('subject', 'Geral')
                                    diff = q.get('difficulty', 'Medio')
                                    text = q.get('question_text', '')
                                    opts = q.get('options', {})
                                    ans = q.get('correct_answer_letter', None)
                                    res1 = q.get('resolution_1', '')
                                    res2 = q.get('resolution_2', '')
                                    img_path = q.get('image_path', '')
                                    has_img = bool(q.get('has_image', False))

                                    insert_question(exam, year, subj, diff, text, opts, ans, res1, res2, img_path, has_img)
                                    total_extracted += 1
                                
                                st.toast(f"📥 {len(questions_chunk)} questões salvas no Arsenal!")

                            loading_placeholder.empty()
                            progress_bar.progress(100, text="EXTRAÇÃO CONCLUÍDA! 100%")
                        
                            # Notificação sonora de sucesso
                            success_sound = "https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3"
                            st.markdown(f'<audio src="{success_sound}" autoplay></audio>', unsafe_allow_html=True)

                            if total_extracted == 0:
                                st.warning("IA nao conseguiu extrair questoes no formato correto.")
                            else:
                                mark_pdf_cached(file_hash, uploaded_file.name, total_extracted)
                                st.success(f"Missão cumprida! {total_extracted} questões foram lidas e salvas no Arsenal.")
                                time.sleep(2)
                                st.rerun() # Refresh to clear progress UI
                        except Exception as e:
                            loading_placeholder.empty()
                            progress_bar.empty()
                            st.error(f"Erro ao processar a missao: {e}")
                        finally:
                            if os.path.exists(temp_path):
                                try:
                                    os.remove(temp_path)
                                except Exception:
                                    pass

# ── Tab 2: Banco de Questoes ──────────────────────────────────────────────────
if selected_tab == '🗡️ Banco':
    st.header("Seu Banco de Questoes")
    all_questions: List[Dict[str, Any]] = get_all_questions()
    if not all_questions:
        st.write("Nenhuma questao no banco ainda. Faca o upload de um PDF primeiro.")
    else:
        st.write(f"Total de questoes cadastradas: **{len(all_questions)}**")

        subjects = sorted(list(set([q['subject'] for q in all_questions if q.get('subject')])))
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_subj = st.selectbox("Filtrar por Materia", ["Todas"] + subjects)
        with col_f2:
            subtopics_opts = ["Todos"]
            if selected_subj != "Todas":
                subtopics_opts += sorted(list(set([q.get('subtopic', '') for q in all_questions if q.get('subject') == selected_subj and q.get('subtopic')])))
            selected_subtopic = st.selectbox("Filtrar por Subtópico", subtopics_opts)

        for q in all_questions:
            if selected_subj != "Todas" and q.get('subject') != selected_subj:
                continue
            if selected_subtopic != "Todos" and q.get('subtopic') != selected_subtopic:
                continue

            with st.expander(f"[{q['subject']}] {q['exam_origin']} {q['year']} - Dificuldade: {q['difficulty']}"):
                if q.get('has_image'):
                    st.markdown("🖼️ **Esta questao contem figura/grafico** — imagem da pagina original abaixo:")
                    img_path = q.get('image_path', '')
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, use_container_width=True)
                    else:
                        st.warning("Imagem da pagina nao encontrada (pode ter sido movida ou deletada).")
                    st.markdown("---")

                st.write(q['question_text'])
                st.markdown("---")
                sorted_letters = sorted(q['options'].keys())
                for letter in sorted_letters:
                    text = q['options'][letter]
                    if letter == q.get('correct_answer_letter'):
                        st.success(f"**{letter}) {text} - Correta**")
                    else:
                        st.markdown(f"{letter}) {text}")

                st.markdown("---")

                q_id = q['id']
                if q.get('resolution_1') or q.get('resolution_2'):
                    st.markdown("🧠 **Resolucoes da IA**")
                    if q.get('resolution_1'):
                        with st.expander("Resolucao 1 (Passo a Passo)"):
                            st.markdown(q['resolution_1'])
                    if q.get('resolution_2'):
                        with st.expander("Resolucao 2 (Metodo Rapido / Alternativo)"):
                            st.markdown(q['resolution_2'])
                else:
                    if st.button("🧠 Gerar Resolucao com IA", key=f"res_{q_id}"):
                        if not os.getenv("GEMINI_API_KEY"):
                            st.error("Chave da API nao configurada. Va em Configuracoes.")
                        else:
                            with st.spinner("Gerando resolucoes... aguarde!"):
                                try:
                                    result = generate_resolution(q['question_text'], q['options'])
                                    update_resolution(q_id, result['resolution_1'], result['resolution_2'])
                                    st.success("Resolucoes geradas e salvas!")
                                    with st.expander("Resolucao 1 (Passo a Passo)"):
                                        st.markdown(result['resolution_1'])
                                    with st.expander("Resolucao 2 (Metodo Rapido)"):
                                        st.markdown(result['resolution_2'])
                                except Exception as e:
                                    st.error(f"Erro ao gerar resolucao: {e}")

# ── Tab 3: Gerar Simulado ─────────────────────────────────────────────────────
if selected_tab == '📄 Missões':
    st.header("Gerar Simulado em PDF")
    st.markdown("Crie um PDF personalizado com as questoes do banco de dados. Um logo exclusivo será embutido no arquivo!")

    sim_questions: List[Dict[str, Any]] = get_all_questions()
    if sim_questions:
        sim_subjects = sorted(list(set([q['subject'] for q in sim_questions])))
        with st.form("simulado_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                sim_subj = st.selectbox("Materia", ["Todas"] + sim_subjects)
            with col2:
                sim_subtopics = ["Todos"]
                if sim_subj != "Todas":
                    sim_subtopics += sorted(list(set([q.get('subtopic', '') for q in sim_questions if q.get('subject') == sim_subj and q.get('subtopic')])))
                sim_subtopic = st.selectbox("Subtópico", sim_subtopics)
            with col3:
                sim_diff = st.selectbox("Dificuldade", ["Todas", "Facil", "Medio", "Dificil"])

            col_a, col_b = st.columns([1,2])
            with col_a:
                num_questions = st.number_input("Numero de questoes", min_value=1, max_value=50, value=10)
            with col_b:
                espaco_resolucao = st.checkbox("Deixar espaço em branco entre questões (para rascunho com caneta)", value=True)
            submitted = st.form_submit_button("Gerar PDF")

        if submitted:
            filtered = [q for q in sim_questions if (sim_subj == "Todas" or q.get('subject') == sim_subj)]
            filtered = [q for q in filtered if (sim_subtopic == "Todos" or q.get('subtopic') == sim_subtopic)]
            filtered = [q for q in filtered if (sim_diff == "Todas" or q.get('difficulty') == sim_diff)]

            if len(filtered) < num_questions:
                st.warning(f"Foram encontradas apenas {len(filtered)} questoes com esses filtros.")
                selected_for_simulado = filtered
            else:
                import random
                selected_for_simulado = random.sample(filtered, num_questions)

            if selected_for_simulado:
                output_file = "simulado_gerado.pdf"
                generate_simulado_pdf(selected_for_simulado, output_file, espaco_resolucao=espaco_resolucao)
                st.success("Simulado gerado com sucesso!")
                with open(output_file, "rb") as pdf_file:
                    PDFbyte = pdf_file.read()
                
                # Notificacao sonora sucesso do PDF
                st.markdown('<audio src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" autoplay></audio>', unsafe_allow_html=True)
                    
                st.download_button(label="Baixar Simulado PDF",
                                   data=PDFbyte,
                                   file_name="simulado_espcex.pdf",
                                   mime="application/pdf")
    else:
        st.info("Nenhuma questao no banco. Faca o upload de provas primeiro.")

# ── Tab 4: Campo de Treino ────────────────────────────────────────────────────
if selected_tab == '💻 Campo Treino':
    st.header("💻 Campo de Treino")
    st.markdown("Treine direto no aplicativo contra a máquina e guarde seu desempenho no banco de dados!")
    
    subtab_obj, subtab_disc = st.tabs(["🎯 Simulado Objetivo", "✍️ Treino Discursivo"])
    
    with subtab_obj:
        if "current_online_test" not in st.session_state:
            st.session_state["current_online_test"] = None

    if not st.session_state["current_online_test"]:
        sim_questions_online: List[Dict[str, Any]] = get_all_questions()
        if sim_questions_online:
            sim_subjects_online = sorted(list(set([q['subject'] for q in sim_questions_online])))
            with st.form("online_simulado_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    sim_subj_online = st.selectbox("Materia (Online)", ["Todas"] + sim_subjects_online)
                with col2:
                    sim_subtopic_opts = ["Todos"]
                    if sim_subj_online != "Todas":
                        sim_subtopic_opts += sorted(list(set([q.get('subtopic', '') for q in sim_questions_online if q.get('subject') == sim_subj_online and q.get('subtopic')])))
                    sim_subtopic_online = st.selectbox("Subtópico (Online)", sim_subtopic_opts)
                with col3:
                    sim_diff_online = st.selectbox("Dificuldade (Online)", ["Todas", "Facil", "Medio", "Dificil"])

                st.markdown("---")
                morte_subita = st.checkbox("💀 Morte Súbita (O teste acaba no seu primeiro erro!)")
                cronometrado = st.checkbox("⏱️ Missão Cronometrada (Seja rápido!)")
                tempo_minutos = 60
                if cronometrado:
                    tempo_minutos = st.number_input("Duração da Missão (Minutos)", min_value=1, max_value=300, value=60)

                num_questions_online = st.number_input("Numero de questoes", min_value=1, max_value=50, value=10, key="num_online")
                submitted_online = st.form_submit_button("Iniciar Missão!")

            if submitted_online:
                import random
                filtered_online = [q for q in sim_questions_online if (sim_subj_online == "Todas" or q.get('subject') == sim_subj_online)]
                filtered_online = [q for q in filtered_online if (sim_subtopic_online == "Todos" or q.get('subtopic') == sim_subtopic_online)]
                filtered_online = [q for q in filtered_online if (sim_diff_online == "Todas" or q.get('difficulty') == sim_diff_online)]
                
                if len(filtered_online) < num_questions_online:
                    st.warning(f"Foram encontradas apenas {len(filtered_online)} questoes com esses filtros.")
                    selected = filtered_online
                else:
                    selected = random.sample(filtered_online, num_questions_online)
                    
                if selected:
                    st.session_state["current_online_test"] = selected
                    st.session_state["morte_subita"] = morte_subita
                    st.session_state["cronometrado"] = cronometrado
                    st.session_state["start_time"] = time.time() if cronometrado else None
                    st.session_state["tempo_prova"] = tempo_minutos * 60 if cronometrado else None
                    st.rerun()
        else:
            st.info("Nenhuma questao no banco. Faça upload de provas primeiro.")
    else:
        # Render the active test
        online_test_qs = st.session_state["current_online_test"]
        total_q = len(online_test_qs)
        st.info(f"Modo Prova Ativo: {total_q} questoes. Foco total!")
        
        if st.session_state.get("cronometrado") and st.session_state.get("start_time") and st.session_state.get("tempo_prova"):
            elapsed_init = time.time() - st.session_state["start_time"]
            remaining = max(0, st.session_state["tempo_prova"] - elapsed_init)
            
            # Timer JS Injection
            timer_html = f"""
            <div style="background-color: #1a1a1a; color: #ff3333; font-family: monospace; font-size: 24px; font-weight: bold; text-align: center; padding: 10px; border-radius: 5px; border: 1px solid #ff3333; margin-bottom: 20px;" id="mission_timer">
                00:00:00
            </div>
            <script>
                var timeLeft = {remaining};
                var timerEl = document.getElementById('mission_timer');
                var timerInterval = setInterval(function() {{
                    if (timeLeft <= 0) {{
                        clearInterval(timerInterval);
                        timerEl.innerHTML = "TEMPO ESGOTADO! RECOLHER PROVA!";
                        return;
                    }}
                    timeLeft -= 1;
                    var h = Math.floor(timeLeft / 3600);
                    var m = Math.floor((timeLeft % 3600) / 60);
                    var s = Math.floor(timeLeft % 60);
                    timerEl.innerHTML = "⏱️ TEMPO RESTANTE: " + (h < 10 ? "0"+h : h) + ":" + (m < 10 ? "0"+m : m) + ":" + (s < 10 ? "0"+s : s);
                }}, 1000);
            </script>
            """
            st.components.v1.html(timer_html, height=70)

        if st.button("Cancelar Missão ❌"):
            st.session_state["current_online_test"] = None
            st.rerun()
            
        with st.form("test_execution_form"):
            for idx, q_test in enumerate(online_test_qs):
                st.markdown(f"### Questao {idx + 1} - {q_test['subject']} ({q_test['difficulty']})")
                if q_test.get('has_image') and q_test.get('image_path') and os.path.exists(q_test['image_path']):
                    st.image(q_test['image_path'], use_container_width=True)
                st.write(q_test['question_text'])
                
                opts = q_test.get('options', {})
                sorted_letters = sorted(opts.keys())
                display_opts = [f"{k}) {opts[k]}" for k in sorted_letters]
                
                # We record user choice in session state keys based on question id to avoid overlaps
                selected_opt = st.radio(f"Sua resposta para a Q{idx+1}", display_opts, index=None, key=f"ans_q_{q_test['id']}")
                st.markdown("---")
            
            finalizar = st.form_submit_button("Entregar Prova ✅")
            
            if finalizar:
                acertos = 0
                respondidas = 0
                for idx, q_test in enumerate(online_test_qs):
                    ans_str = st.session_state.get(f"ans_q_{q_test['id']}")
                    if ans_str:
                        respondidas += 1
                        letter = ans_str.split(")")[0]
                        correct = (letter == q_test['correct_answer_letter'])
                        if correct:
                            acertos += 1
                        
                        save_performance(q_test['id'], letter, correct, user_info['id'])

                        if not correct and st.session_state.get("morte_subita"):
                            st.error(f"💀 MORTE SÚBITA! Você foi abatido na Questão {idx + 1}. A missão foi abortada e as demais não contaram.")
                            break
                            
                pct = (acertos / respondidas) * 100 if respondidas > 0 else 0
                st.success(f"Prova finalizada! Sua performance foi gravada. Você acertou {acertos} de {respondidas} que respondeu ({pct:.1f}%).")
                
                # Gamificacao / Badges
                earned_badges = []
                if respondidas >= 5 and acertos == respondidas and award_badge(user_info['id'], "Atirador de Elite (100% Acertos)"):
                    earned_badges.append("Atirador de Elite (100% Acertos)")
                
                if st.session_state.get("morte_subita") and acertos >= 5 and award_badge(user_info['id'], "Sobrevivente Nato (5+ em Morte Súbita)"):
                    earned_badges.append("Sobrevivente Nato (5+ em Morte Súbita)")
                    
                if st.session_state.get("cronometrado"):
                     elapsed = time.time() - st.session_state.get("start_time", time.time())
                     minutos = int(elapsed // 60)
                     segundos = int(elapsed % 60)
                     st.info(f"⏱️ Tempo de missão concluído: {minutos}m {segundos}s")
                     # Se foi rapido (< 1min por questao) e acertou bem
                     if elapsed < (respondidas * 60) and pct >= 70 and award_badge(user_info['id'], "Veloz e Furioso (Missão Cronometrada)"):
                          earned_badges.append("Veloz e Furioso (Missão Cronometrada)")
                          
                if earned_badges:
                    st.toast(f"🎖️ Novas condecorações ganhas: {', '.join(earned_badges)}")

                if pct >= 70:
                    st.balloons()
                else:
                    st.snow()
                st.session_state["current_online_test"] = None
                time.sleep(4)
                st.rerun()

    with subtab_disc:
        st.subheader("✍️ Treinamento Discursivo")
        st.markdown("Escreva uma questão, anexe uma foto da sua resolução escrita em papel, e a Inteligência fará a avaliação do seu raciocínio.")
        
        with st.form("discursive_form"):
            disc_question = st.text_area("Enunciado da Questão Discursiva", height=150, placeholder="Digite o enunciado completo aqui...")
            disc_image = st.file_uploader("Sua resolução manuscrita (Opcional)", type=["png", "jpg", "jpeg"])
            
            disc_submit = st.form_submit_button("Submeter para Avaliação")
            
        if disc_submit:
            if not disc_question.strip():
                st.warning("O enunciado da questão é obrigatório para a avaliação.")
            elif not os.getenv("GEMINI_API_KEY"):
                st.error("Chave de API do Gemini não configurada! Vá na aba 'Configurações' primeiro.")
            else:
                with st.spinner("A Banca está avaliando seu raciocínio matemático..."):
                    img_bytes = disc_image.getvalue() if disc_image else None
                    result = analyze_discursive_image(disc_question, img_bytes)
                    
                    st.markdown("### 📋 Parecer da Banca Avaliadora")
                    st.info(result)

# ── Tab: Sala de Redação ──────────────────────────────────────────────────────
if selected_tab == '✍️ Redação':
    st.header("✍️ Sala de Redação")
    st.markdown("Submeta sua redação para correção imediata pela IA, baseada em critérios oficiais de concursos militares.")
    
    with st.form("redacao_form"):
        tema_red = st.text_input("Tema da Redação", placeholder="Ex: A importância das Forças Armadas na defesa da Amazônia")
        texto_red = st.text_area("Seu Texto", height=300, placeholder="Digite ou cole sua redação aqui...")
        imagem_red = st.file_uploader("Foto da Folha de Redação (Opcional)", type=["png", "jpg", "jpeg"])
        
        red_submit = st.form_submit_button("🔨 Enviar para Correção")
        
    if red_submit:
        if not texto_red.strip() and not imagem_red:
            st.warning("Envie o texto ou uma foto da redação.")
        elif not os.getenv("GEMINI_API_KEY"):
            st.error("Chave de API não configurada.")
        else:
            with st.spinner("O Tenente Corretor está analisando sua redação..."):
                img_bytes = imagem_red.getvalue() if imagem_red else None
                feedback = evaluate_essay(texto_red, tema_red, img_bytes)
                st.markdown("### 📝 Feedback do Corretor")
                st.info(feedback)

# ── Tab: Duelo Tático ─────────────────────────────────────────────────────────
if selected_tab == '⚔️ Duelo':
    st.header("⚔️ Duelo Tático (Rapid Fire)")
    st.markdown("Teste seus reflexos e precisão. Você tem apenas **30 segundos** por questão!")
    
    if st.button("🔥 Iniciar Duelo contra a IA"):
        # We simulate a "Duel" by giving random questions and a fast timer
        st.session_state["duel_active"] = True
        st.session_state["duel_qs"] = random.sample(get_all_questions(), 5) if get_all_questions() else []
        st.session_state["duel_start"] = time.time()
        st.rerun()
        
    if st.session_state.get("duel_active"):
        st.warning("MODO DUELO ATIVADO. SEM MISERICÓRDIA.")
        # Similar to Simulados but faster
        # (Simplified implementation for now)
        st.info("Responda o mais rápido possível no Arsenal de Questões para registrar recordes!")

# ── Tab 5: Meu Desempenho ─────────────────────────────────────────────────────
if selected_tab == '🏆 Elite':
    st.header("📊 Painel de Desempenho (Ficha Militar)")
    st.markdown("Acompanhe sua evolução e identifique seus pontos cegos no território.")
    
    stats = get_performance_stats(user_info['id'])
    if not stats:
        st.info("Você ainda não respondeu nenhuma questão nos Simulados Online. Cumpra algumas missões na aba anterior primeiro!")
    else:
        total_answered = len(stats)
        total_correct = sum(1 for s in stats if s['is_correct'])
        acc = (total_correct / total_answered) * 100
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Disparos Efetuados (Testes)", total_answered)
        col2.metric("Alvos Abatidos (Acertos)", total_correct)
        col3.metric("Aproveitamento Geral", f"{acc:.1f}%")
        
        st.divider()
        st.subheader("Desempenho Tático por Matéria")
        
        df = pd.DataFrame(stats)
        if not df.empty:
            # Aggregate stats natively through Pandas
            summary = df.groupby('subject')['is_correct'].agg(['count', 'mean']).reset_index()
            summary['Taxa de Acerto (%)'] = summary['mean'] * 100
            summary = summary.rename(columns={'count': 'Questoes Resolvidas', 'subject': 'Materia'})
            
            st.bar_chart(data=summary, x='Materia', y='Taxa de Acerto (%)', color="#7ab050", use_container_width=True)
            st.dataframe(summary[['Materia', 'Questoes Resolvidas', 'Taxa de Acerto (%)']], use_container_width=True, hide_index=True)


# ── Tab: Criar Lista Inédita ──────────────────────────────────────────────────
if selected_tab == '🤖 Lista IA':
    st.header("🤖 Forjar Missão com IA (Questões Inéditas)")
    st.markdown("A Inteligência Artificial criará uma lista de questões completamente originais com base no concurso, matéria e nível de dificuldade escolhidos.")

    with st.form("ai_list_form"):
        col1, col2 = st.columns(2)
        with col1:
            ai_exam = st.text_input("Concurso Foco (Ex: EsPCEx, ESA, EFOMM)", value="EsPCEx")
            ai_subj = st.selectbox("Matéria Geral", ["Matemática", "Física", "Química", "História", "Geografia", "Português", "Inglês"])
        with col2:
            ai_subtopic = st.text_input("Subtópico Específico (Ex: Geometria Plana, Cinemática)", value="Geometria Plana")
            ai_diff = st.selectbox("Nível de Dificuldade", ["Facil", "Medio", "Dificil"])

        ai_num_questions = st.number_input("Número de Questões", min_value=1, max_value=15, value=5)
        
        st.markdown("---")
        ai_submit = st.form_submit_button("🔨 Forjar Missão Inédita")

    if ai_submit:
        if not os.getenv("GEMINI_API_KEY"):
            st.error("Chave de API do Gemini não configurada! Vá na aba 'Configurações' primeiro.")
        else:
            loading_placeholder_ai = st.empty()
            loading_placeholder_ai.markdown(_battle_html("A MÁQUINA ESTÁ FORJANDO QUESTÕES ORIGINAIS... AGUARDE"), unsafe_allow_html=True)
            
            custom_qs = generate_custom_questions(ai_exam, ai_subj, ai_subtopic, ai_diff, ai_num_questions)
            loading_placeholder_ai.empty()

            if not custom_qs:
                st.error("Falha ao forjar as missões. Tente novamente mais tarde.")
            else:
                st.session_state["active_ai_list"] = custom_qs
                st.session_state["active_ai_list_exam"] = ai_exam
                st.session_state["active_ai_list_subj"] = ai_subj
                st.session_state["active_ai_list_subtopic"] = ai_subtopic
                st.session_state["active_ai_list_diff"] = ai_diff
                st.success(f"A Inteligência forjou {len(custom_qs)} questões inéditas! Pronta para o combate.")
                st.markdown('<audio src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" autoplay></audio>', unsafe_allow_html=True)
                st.rerun()

    if "active_ai_list" in st.session_state and st.session_state["active_ai_list"]:
        st.divider()
        st.subheader("🎯 Responda a Missão Inédita")
        
        active_qs = st.session_state["active_ai_list"]
        with st.form("solve_ai_list_form"):
            for idx, q in enumerate(active_qs):
                st.markdown(f"#### Questão {idx + 1}")
                st.write(q.get('question_text', ''))
                
                opts = q.get('options', {})
                sorted_letters = sorted(opts.keys())
                display_opts = [f"{k}) {opts[k]}" for k in sorted_letters]
                
                st.radio(f"Sua resposta para a questão {idx+1}", display_opts, index=None, key=f"ai_ans_q_{idx}")
                st.markdown("---")
            
            entregar_ai = st.form_submit_button("✅ Entregar e Avaliar Missão")
        
        if entregar_ai:
            acertos_ai = 0
            # Salvando no banco de dados DEPOIS de responder para garantir que existam IDs
            for idx, q in enumerate(active_qs):
                ans_str_ai = st.session_state.get(f"ai_ans_q_{idx}")
                letter_ai = ans_str_ai.split(")")[0] if ans_str_ai else None
                correct_ai = (letter_ai == q.get('correct_answer_letter'))
                
                q_id = insert_question(
                    exam_origin=f"Inédito AI - {st.session_state['active_ai_list_exam']}",
                    year="2026",
                    subject=st.session_state['active_ai_list_subj'],
                    difficulty=st.session_state['active_ai_list_diff'],
                    question_text=q.get('question_text', ''),
                    options=q.get('options', {}),
                    correct_answer=q.get('correct_answer_letter', 'A'),
                    resolution_1=q.get('resolution_1', ''),
                    resolution_2=q.get('resolution_2', ''),
                    image_path="",
                    has_image=False,
                    subtopic=st.session_state['active_ai_list_subtopic']
                )
                
                if letter_ai:
                    save_performance(q_id, letter_ai, correct_ai, user_info['id'])
                    if correct_ai:
                        acertos_ai += 1
            
            st.success(f"Missão Cumprida! Você acertou {acertos_ai} de {len(active_qs)}.")
            if acertos_ai == len(active_qs):
                st.balloons()
            
            st.session_state["active_ai_list"] = None
            time.sleep(3)
            st.rerun()

# ── Tab: Sala de Redação ──────────────────────────────────────────────────────
if selected_tab == '✍️ Redação':
    st.header("✍️ Sala de Redação (Recinto de Avaliação)")
    
    with st.expander("📋 Ver Critérios de Avaliação (Padrão EsPCEx/ESA)"):
        st.markdown("""
        **1. Compreensão do Tema:** O candidato deve ater-se ao tema proposto.
        **2. Estrutura Textual:** Introdução, Desenvolvimento e Conclusão.
        **3. Coesão e Coerência:** Uso de conectivos e lógica de argumentação.
        **4. Norma Culta:** Pontuação, acentuação e regência.
        ---
        *A nota varia de 0 a 100 baseada na média desses pilares.*
        """)

    st.markdown("Envie seu texto ou a foto da sua folha para análise imediata do Tenente Corretor.")
    
    with st.form("redacao_form_v4"):
        t_red = st.text_input("Tema da Redação", placeholder="Ex: O uso da tecnologia na defesa cibernética nacional")
        txt_red = st.text_area("Texto da Redação (Copie e Cole ou Digite)", height=300)
        img_red = st.file_uploader("📷 Foto da Folha de Resposta (Opcional)", type=["png", "jpg", "jpeg"])
        sub_red = st.form_submit_button("🔨 SOLICITAR PARECER DO COMANDO")
        
    if sub_red:
        if not txt_red.strip() and not img_red:
            st.warning("É necessário fornecer o texto ou a imagem da redação.")
        else:
            with st.spinner("Analisando gramática, coesão e argumentação..."):
                img_bytes = img_red.getvalue() if img_red else None
                fb = evaluate_essay(txt_red, t_red, img_bytes)
                
                st.markdown("### 📋 Feedack Detalhado")
                st.markdown(f"""
                <div style="background: rgba(212, 175, 55, 0.05); border: 1px solid #d4af37; border-radius: 10px; padding: 20px;">
                    {fb}
                </div>
                """, unsafe_allow_html=True)
                st.toast("Redação avaliada com sucesso!")

# ── Tab: Duelo Tático ─────────────────────────────────────────────────────────
if selected_tab == '⚔️ Duelo':
    st.header("⚔️ Duelo de Elite (Rapid Fire)")
    st.markdown("Teste sua velocidade sob pressão. **30 segundos** por questão. **5 rounds**.")
    
    if "duel_state" not in st.session_state:
        st.session_state["duel_state"] = "IDLE" # IDLE, ACTIVE, RESULT
        st.session_state["duel_score"] = 0
        st.session_state["duel_current_q"] = 0
        st.session_state["duel_questions"] = []

    if st.session_state["duel_state"] == "IDLE":
        st.info("Prepara-se para o combate. A IA selecionará 5 questões aleatórias do banco.")
        if st.button("🔥 INICIAR COMBATE IMEDIATO"):
            all_qs_duel = get_all_questions()
            if len(all_qs_duel) < 5:
                st.error("É necessário ter pelo menos 5 questões no banco para iniciar um duelo.")
            else:
                import random
                st.session_state["duel_questions"] = random.sample(all_qs_duel, 5)
                st.session_state["duel_state"] = "ACTIVE"
                st.session_state["duel_current_q"] = 0
                st.session_state["duel_score"] = 0
                st.session_state["duel_start_time"] = time.time()
                st.rerun()

    elif st.session_state["duel_state"] == "ACTIVE":
        curr_idx = st.session_state["duel_current_q"]
        q_duel = st.session_state["duel_questions"][curr_idx]
        
        # UI: Progress and Timer
        cols = st.columns([1, 4, 1])
        with cols[0]:
            st.markdown(f"**ROUND {curr_idx + 1}/5**")
        with cols[1]:
            st.progress((curr_idx) / 5)
        with cols[2]:
            elapsed_duel = time.time() - st.session_state.get("duel_start_time", time.time())
            remaining_duel = max(0.0, 30.0 - elapsed_duel)
            color_duel = "green" if remaining_duel > 10 else "red"
            st.markdown(f"<h3 style='color:{color_duel}; text-align:right; margin:0;'>{int(remaining_duel)}s</h3>", unsafe_allow_html=True)

        if remaining_duel <= 0:
            st.warning("TEMPO ESGOTADO! PRÓXIMA QUESTÃO.")
            st.session_state["duel_current_q"] += 1
            if st.session_state["duel_current_q"] >= 5:
                st.session_state["duel_state"] = "RESULT"
            else:
                st.session_state["duel_start_time"] = time.time()
            st.rerun()

        st.markdown("---")
        if q_duel.get('has_image') and q_duel.get('image_path') and os.path.exists(q_duel['image_path']):
            st.image(q_duel['image_path'], use_container_width=True)
        st.write(q_duel['question_text'])
        
        opts_duel = q_duel.get('options', {})
        sorted_keys = sorted(opts_duel.keys())
        
        # Use columns for options to be faster
        col_opts = st.columns(len(sorted_keys))
        for i, k in enumerate(sorted_keys):
            if col_opts[i].button(f"{k}", key=f"duel_btn_{curr_idx}_{k}", use_container_width=True):
                if k == q_duel.get('correct_answer_letter'):
                    st.session_state["duel_score"] += 1
                    st.toast("ALVO ABATIDO! 🎯")
                else:
                    st.toast("DISPARO PERDIDO! ❌")
                
                # Next Question
                st.session_state["duel_current_q"] += 1
                if st.session_state["duel_current_q"] >= 5:
                    st.session_state["duel_state"] = "RESULT"
                else:
                    st.session_state["duel_start_time"] = time.time()
                st.rerun()

    elif st.session_state["duel_state"] == "RESULT":
        st.header("🏁 RELATÓRIO DE COMBATE")
        score = st.session_state["duel_score"]
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.metric("Sua Pontuação", f"{score}/5")
        with col_res2:
            st.metric("Oponente (IA)", "4/5") # Fixed for now to feel like a "Duel"
            
        if score > 4:
            st.success("VITÓRIA ESMAGADORA! Você superou a máquina.")
            st.balloons()
            award_badge(user_info['id'], "Elite do Elite (Duelista)")
        elif score == 4:
            st.info("EMPATE TÁTICO! Ambos demonstraram alta precisão.")
        else:
            st.error("DERROTA! A máquina foi mais rápida e precisa desta vez.")
            st.snow()
            
        if st.button("🔄 Voltar ao Quartel"):
            st.session_state["duel_state"] = "IDLE"
            st.rerun()

# ── Tab 6: Configuracoes (ADMIN ONLY) ─────────────────────────────────────────
if user_info['role'] == 'admin':
    if selected_tab == '⚙️ Config':
        st.header("Configuracoes")

        # ── API Key ───────────────────────────────────────────────────────────────
        st.subheader("🔑 Chave da API Gemini")
        st.markdown("Gere sua chave gratuita em: [Google AI Studio](https://aistudio.google.com/app/apikey)")

        current_key = os.getenv("GEMINI_API_KEY", "")
        new_key = st.text_input("Cole sua Chave da API aqui", value=current_key, type="password")

        if st.button("Salvar Chave"):
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"GEMINI_API_KEY={new_key}\n")
            load_dotenv(override=True)
            st.success("Chave configurada e ativada com sucesso!")
            time.sleep(1)
            st.rerun()

        st.divider()

        # ── Export ────────────────────────────────────────────────────────────────
        st.subheader("📦 Exportar Banco de Dados")
        st.markdown("Faça backup de todas as suas questoes em formato aberto.")

        export_questions = get_all_questions()
        if export_questions:
            col_json, col_csv = st.columns(2)
            with col_json:
                json_data = export_to_json(export_questions)
                st.download_button(
                    label="⬇️ Baixar como JSON",
                    data=json_data.encode("utf-8"),
                    file_name="qbank_backup.json",
                    mime="application/json",
                    use_container_width=True
                )
            with col_csv:
                csv_data = export_to_csv(export_questions)
                st.download_button(
                    label="⬇️ Baixar como CSV",
                    data=csv_data.encode("utf-8"),
                    file_name="qbank_backup.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            st.caption(f"Total: {len(export_questions)} questoes no banco")
        else:
            st.info("Nenhuma questao para exportar ainda.")

        st.divider()

        st.divider()
        
        # ── SYSTEM RESET ──────────────────────────────────────────────────────────
        st.subheader("🚨 Missão de Autodestruição (Reset)")
        st.warning("CUIDADO: Isso apagará todas as questões, usuários e desempenhos permanentemente.")
        if st.button("🔥 Reiniciar Tudo (Wipe Database)"):
            from database import reset_db
            reset_db()
            st.success("Operação concluída. O Quartel está limpo.")
            time.sleep(2)
            st.rerun()

# ── Tab 7: Recrutamento e Controle de Tropa (ADMIN ONLY) ───────────────────
if user_info['role'] == 'admin':
    if selected_tab == '👥 Tropa':
        st.header("👥 Alto Comando (Controle de Pessoal)")
        st.markdown("Gerencie todo o seu efetivo. Acompanhe a experiência, os destaques e desligue membros inativos.")
        
        users = auth.get_all_users()
        
        # ── RANKING / LEADERBOARD ──
        st.subheader("🏆 Ranking Geral do Esquadrão")
        ranking_data = []
        for u in users:
            if u['role'] == 'admin':
                continue
            rank_name, xp = get_user_rank(u['id'], u['role'])
            ranking_data.append({
                "Nome de Guerra": u['username'].upper(),
                "Patente": rank_name,
                "XP Acumulado": xp
            })
            
        if ranking_data:
            import pandas as pd
            df_rank = pd.DataFrame(ranking_data)
            df_rank = df_rank.sort_values(by="XP Acumulado", ascending=False).reset_index(drop=True)
            df_rank.index += 1 # Index começando do 1 para indicar Posição
            st.dataframe(df_rank, use_container_width=True)
        else:
            st.info("Nenhum soldado no ranking. O pelotão está vazio.")

        st.divider()

        # ── CONTROLE / DESLIGAMENTO ──
        col_add, col_del = st.columns(2)
        with col_add:
            st.subheader("🪖 Alistar Novo Soldado")
            with st.form("add_admin_form"):
                new_u = st.text_input("Nome do Recruta")
                new_p = st.text_input("Senha Inicial", type="password")
                if st.form_submit_button("Alistar Oficialmente"):
                    if new_u and new_p:
                        if auth.create_user(new_u, new_p, 'student'):
                            st.success(f"Soldado '{new_u}' cadastrado!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Nome de Recruta já em uso.")
                            
        with col_del:
            st.subheader("🗑️ Desligar Soldado")
            with st.form("del_admin_form"):
                soldados = [u['username'] for u in users if u['role'] != 'admin']
                if soldados:
                    del_u = st.selectbox("Selecionar Soldado para Exclusão", soldados)
                    if st.form_submit_button("Expulsar da Corporação"):
                        auth.delete_user(del_u)
                        st.success(f"{del_u} foi desligado permanentemente.")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.write("Não há soldados para excluir.")
                    st.form_submit_button("Expulsar", disabled=True)
