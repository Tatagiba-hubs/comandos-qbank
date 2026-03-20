# 🚀 COMANDOS QBANK — Guia de Deploy

## Deploy no Streamlit Cloud (Gratuito)

### 1. Pré-requisitos
- Conta no [GitHub](https://github.com)
- Conta no [Streamlit Cloud](https://streamlit.io/cloud)

### 2. Prepare o repositório

```bash
# No diretório espcex_qbank:
git init
git add .
git commit -m "Initial commit - COMANDOS QBANK"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/comandos-qbank.git
git push -u origin main
```

### 3. Configure Secrets no Streamlit Cloud

No painel do Streamlit Cloud → **Settings → Secrets**, adicione:
```toml
GEMINI_API_KEY = "sua-chave-aqui"
```

### 4. Deploy

- Acesse [share.streamlit.io](https://share.streamlit.io)
- Clique em **New app**
- Selecione seu repositório e branch `main`
- Main file: `app.py`
- Clique em **Deploy!**

> **Nota:** O banco de dados SQLite não persiste entre deploys no Streamlit Cloud.
> Para persistência, considere usar o Railway (abaixo) ou Supabase.

---

## Deploy no Railway (Com Persistência)

### 1. Pré-requisitos
- Conta no [Railway](https://railway.app)
- Repositório no GitHub

### 2. Criar Procfile

Crie o arquivo `Procfile` na raiz do projeto:
```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

### 3. Deploy

- Acesse [railway.app](https://railway.app) → **New Project**
- Selecione **Deploy from GitHub repo**
- Adicione a variável de ambiente: `GEMINI_API_KEY=sua-chave`
- O Railway detecta o `Procfile` automaticamente e faz deploy

### 4. Volume para persistência do banco

No Railway, adicione um **Volume** montado em `/app` para que o `espcex_qbank.db` persista entre deploys.

---

## Variáveis de Ambiente Necessárias

| Variável | Descrição |
|---|---|
| `GEMINI_API_KEY` | Chave da API do Google Gemini (obrigatória) |
| `PYTHONIOENCODING` | Defina como `utf-8` para evitar erros de encoding |

---

## Dicas Importantes

- O banco `espcex_qbank.db` é criado automaticamente na primeira execução
- As fontes DejaVu são baixadas automaticamente na primeira geração de simulado
- Para rodar localmente: `streamlit run app.py`
