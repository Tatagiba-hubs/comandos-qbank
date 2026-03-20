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
                      save_performance, get_performance_stats)
from ai_extractor import extract_questions_from_pdf, generate_resolution
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
init_db()
import auth
auth.init_default_admin()

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

# ── Hero Banner ────────────────────────────────────────────────────────────────
_banner_path = os.path.join(os.path.dirname(__file__), "hero_banner.png")
if os.path.exists(_banner_path):
    with open(_banner_path, "rb") as _f:
        _b64 = base64.b64encode(_f.read()).decode()
    _bg_css = f"url('data:image/png;base64,{_b64}')"
else:
    _bg_css = "linear-gradient(135deg, #1a2a1a 0%, #0d1a0d 100%)"

h_col1, h_col2 = st.columns([0.9, 0.1])
with h_col2:
    btn_text = "☀️ Claro" if st.session_state["theme"] == "dark" else "🌙 Escuro"
    st.button(btn_text, on_click=toggle_theme, use_container_width=True)

# Define gradient based on theme
if st.session_state["theme"] == "light":
    gradient = "rgba(255,255,255,0.7) 0%, rgba(240,245,235,0.9) 100%"
    title_col = "#2c4a1b"
    sub_col = "#3b5c2a"
else:
    gradient = "rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.75) 100%"
    title_col = "#FFD600"
    sub_col = "#d4e8d0"

st.markdown(f"""
<style>
.hero-banner {{
    width: 100%;
    min-height: 260px;
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
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}}
.hero-title {{
    font-size: 2.8rem;
    font-weight: 900;
    letter-spacing: 0.12em;
    color: {title_col} !important;
    text-shadow: 0 2px 12px rgba(0,0,0,0.8);
    margin: 0;
    font-family: 'Georgia', serif;
}}
.hero-sub {{
    font-size: 1.05rem;
    color: {sub_col} !important;
    margin-top: 10px;
    letter-spacing: 0.04em;
    text-shadow: 0 1px 6px rgba(0,0,0,0.9);
}}
</style>
<div class="hero-banner">
  <div class="hero-title">🗡️ &nbsp; COMANDOS QBANK</div>
  <div class="hero-sub">O sistema definitivo de inteligência para missões e provas operacionais</div>
</div>
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
    st.markdown(f"## {rank}")
    st.markdown(f"**NOME:** {user_info['username'].upper()}")
    if user_info['role'] != 'admin':
        st.markdown(f"**XP COMBATE:** {pts} pts")
    else:
        st.markdown("👑 **COMANDO SUPREMO**")
        
    st.divider()
    if st.button("Sair do Quartel / Logout", use_container_width=True):
        st.session_state["user"] = None
        st.rerun()

# ── LOGIC FOR ROLE TABS ───────────────────────────────────────────────────────
if user_info['role'] == 'admin':
    tabs = st.tabs(["📤 Infiltração (Add PDF)", "🔍 Arsenal de Questões", "📄 Gerar Operação", "💻 Campo de Treino", "📊 Inteligência", "⚙️ Sala de Guerra", "👥 Recrutamento"])
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = tabs
else:
    tabs = st.tabs(["🔍 Arsenal de Questões", "📄 Gerar Missão", "💻 Campo de Treino", "📊 Minha Ficha"])
    tab2, tab3, tab4, tab5 = tabs

# ── Tab 1: Upload PDF (ADMIN ONLY) ──────────────────────────────────────────────
if user_info['role'] == 'admin':
    with tab1:
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
                            questions_data: List[Dict[str, Any]] = extract_questions_from_pdf(temp_path, update_progress)
                            loading_placeholder.empty()
                            progress_bar.progress(100, text="EXTRAÇÃO CONCLUÍDA! 100%")
                        
                            # Notificação sonora de sucesso
                            success_sound = "https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3"
                            st.markdown(f'<audio src="{success_sound}" autoplay></audio>', unsafe_allow_html=True)

                            if not questions_data:
                                st.warning("IA nao conseguiu extrair questoes no formato correto.")
                            else:
                                st.success(f"{len(questions_data)} questoes extraidas e lidas!")

                                for q in questions_data:
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

                                mark_pdf_cached(file_hash, uploaded_file.name, len(questions_data))
                                st.info("Missao cumprida! As questoes foram salvas no Banco de Dados.")
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
with tab2:
    st.header("Seu Banco de Questoes")
    all_questions: List[Dict[str, Any]] = get_all_questions()
    if not all_questions:
        st.write("Nenhuma questao no banco ainda. Faca o upload de um PDF primeiro.")
    else:
        st.write(f"Total de questoes cadastradas: **{len(all_questions)}**")

        subjects = sorted(list(set([q['subject'] for q in all_questions])))
        selected_subj = st.selectbox("Filtrar por Materia", ["Todas"] + subjects)

        for q in all_questions:
            if selected_subj != "Todas" and q['subject'] != selected_subj:
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
with tab3:
    st.header("Gerar Simulado em PDF")
    st.markdown("Crie um PDF personalizado com as questoes do banco de dados. Um logo exclusivo será embutido no arquivo!")

    sim_questions: List[Dict[str, Any]] = get_all_questions()
    if sim_questions:
        sim_subjects = sorted(list(set([q['subject'] for q in sim_questions])))
        with st.form("simulado_form"):
            col1, col2 = st.columns(2)
            with col1:
                sim_subj = st.selectbox("Materia", ["Todas"] + sim_subjects)
            with col2:
                sim_diff = st.selectbox("Dificuldade", ["Todas", "Facil", "Medio", "Dificil"])

            num_questions = st.number_input("Numero de questoes", min_value=1, max_value=50, value=10)
            espaco_resolucao = st.checkbox("Deixar espaço em branco entre questões (para rascunho com caneta)", value=True)
            submitted = st.form_submit_button("Gerar PDF")

        if submitted:
            filtered = [q for q in sim_questions if (sim_subj == "Todas" or q['subject'] == sim_subj)]
            filtered = [q for q in filtered if (sim_diff == "Todas" or q['difficulty'] == sim_diff)]

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

# ── Tab 4: Simulado Online ────────────────────────────────────────────────────
with tab4:
    st.header("Simulado Online")
    st.markdown("Treine direto no aplicativo contra a máquina e guarde seu desempenho no banco de dados!")
    
    if "current_online_test" not in st.session_state:
        st.session_state["current_online_test"] = None

    if not st.session_state["current_online_test"]:
        sim_questions_online: List[Dict[str, Any]] = get_all_questions()
        if sim_questions_online:
            sim_subjects_online = sorted(list(set([q['subject'] for q in sim_questions_online])))
            with st.form("online_simulado_form"):
                col1, col2 = st.columns(2)
                with col1:
                    sim_subj_online = st.selectbox("Materia (Online)", ["Todas"] + sim_subjects_online)
                with col2:
                    sim_diff_online = st.selectbox("Dificuldade (Online)", ["Todas", "Facil", "Medio", "Dificil"])

                num_questions_online = st.number_input("Numero de questoes", min_value=1, max_value=50, value=10, key="num_online")
                submitted_online = st.form_submit_button("Iniciar Missão!")

            if submitted_online:
                import random
                filtered_online = [q for q in sim_questions_online if (sim_subj_online == "Todas" or q['subject'] == sim_subj_online)]
                filtered_online = [q for q in filtered_online if (sim_diff_online == "Todas" or q['difficulty'] == sim_diff_online)]
                
                if len(filtered_online) < num_questions_online:
                    st.warning(f"Foram encontradas apenas {len(filtered_online)} questoes com esses filtros.")
                    selected = filtered_online
                else:
                    selected = random.sample(filtered_online, num_questions_online)
                    
                if selected:
                    st.session_state["current_online_test"] = selected
                    st.rerun()
        else:
            st.info("Nenhuma questao no banco. Faça upload de provas primeiro.")
    else:
        # Render the active test
        online_test_qs = st.session_state["current_online_test"]
        total_q = len(online_test_qs)
        st.info(f"Modo Prova Ativo: {total_q} questoes. Foco total!")
        
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
                for idx, q_test in enumerate(online_test_qs):
                    ans_str = st.session_state.get(f"ans_q_{q_test['id']}")
                    if ans_str:
                        letter = ans_str.split(")")[0]
                        correct = (letter == q_test['correct_answer_letter'])
                        if correct:
                            acertos += 1
                        # Save performance securely to the database (linked to user_id)
                        save_performance(q_test['id'], letter, correct, user_info['id'])
                
                pct = (acertos / total_q) * 100
                st.success(f"Prova finalizada! Sua performance foi gravada. Você acertou {acertos} de {total_q} questoes ({pct:.1f}%).")
                if pct >= 70:
                    st.balloons()
                else:
                    st.snow()
                st.session_state["current_online_test"] = None
                time.sleep(3)
                st.rerun()

# ── Tab 5: Meu Desempenho ─────────────────────────────────────────────────────
with tab5:
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


# ── Tab 6: Configuracoes (ADMIN ONLY) ─────────────────────────────────────────
if user_info['role'] == 'admin':
    with tab6:
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

        # ── Cache Info ────────────────────────────────────────────────────────────
        st.subheader("🗄️ Cache de PDFs Processados")
        st.markdown("PDFs ja processados sao detectados automaticamente para evitar duplicatas.")
        st.info("O cache e verificado automaticamente ao fazer upload de um PDF na aba 'Adicionar PDF'.")

# ── Tab 7: Recrutamento e Controle de Tropa (ADMIN ONLY) ───────────────────
if user_info['role'] == 'admin':
    with tab7:
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
