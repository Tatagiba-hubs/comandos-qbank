# -*- coding: utf-8 -*-
"""
migrate_to_supabase.py
======================
Script de migracao ONE-SHOT: SQLite local -> Supabase PostgreSQL.

Execute UMA UNICA VEZ. Rodar duas vezes pode duplicar dados.

Uso:
    python migrate_to_supabase.py
"""
import os
import sys
import sqlite3
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

SQLITE_FILE = "espcex_qbank.db"
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERRO: DATABASE_URL não encontrada no .env")
    sys.exit(1)

if not os.path.exists(SQLITE_FILE):
    print(f"ERRO: Arquivo SQLite '{SQLITE_FILE}' não encontrado.")
    sys.exit(1)


def migrate():
    print("=" * 55)
    print("  COMANDO QBANK — Migração SQLite → Supabase")
    print("=" * 55)

    # Conexão SQLite (origem)
    sq = sqlite3.connect(SQLITE_FILE)
    sq.row_factory = sqlite3.Row

    # Conexão PostgreSQL (destino)
    pg = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    pg_cur = pg.cursor()

    # ── 1. USERS ──────────────────────────────────────────────────────────────
    print("\n[1/5] Migrando users...")
    users = sq.execute("SELECT * FROM users").fetchall()
    count = 0
    for u in users:
        try:
            pg_cur.execute('''
                INSERT INTO users (id, username, password_hash, role)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
            ''', (u["id"], u["username"], u["password_hash"], u["role"]))
            count += 1
        except Exception as e:
            print(f"  AVISO user {u['username']}: {e}")
            pg.rollback()
    pg.commit()
    print(f"  ✓ {count}/{len(users)} users migrados")

    # ── 2. QUESTIONS ──────────────────────────────────────────────────────────
    print("\n[2/5] Migrando questions...")
    questions = sq.execute("SELECT * FROM questions").fetchall()
    count = 0
    for q in questions:
        try:
            pg_cur.execute('''
                INSERT INTO questions (
                    id, exam_origin, year, subject, difficulty, question_text,
                    correct_answer_id, resolution_1, resolution_2,
                    image_path, has_image, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', (
                q["id"], q["exam_origin"], q["year"], q["subject"],
                q["difficulty"], q["question_text"], q["correct_answer_id"],
                q["resolution_1"], q["resolution_2"],
                q["image_path"], bool(q["has_image"]),
                q["created_at"]
            ))
            count += 1
        except Exception as e:
            print(f"  AVISO question id={q['id']}: {e}")
            pg.rollback()
    pg.commit()
    print(f"  ✓ {count}/{len(questions)} questions migradas")

    # ── 3. OPTIONS ────────────────────────────────────────────────────────────
    print("\n[3/5] Migrando options...")
    options = sq.execute("SELECT * FROM options").fetchall()
    count = 0
    for o in options:
        try:
            pg_cur.execute('''
                INSERT INTO options (id, question_id, option_letter, option_text)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', (o["id"], o["question_id"], o["option_letter"], o["option_text"]))
            count += 1
        except Exception as e:
            print(f"  AVISO option id={o['id']}: {e}")
            pg.rollback()
    pg.commit()
    print(f"  ✓ {count}/{len(options)} options migradas")

    # ── 4. PERFORMANCE ────────────────────────────────────────────────────────
    print("\n[4/5] Migrando performance...")
    perf = sq.execute("SELECT * FROM performance").fetchall()
    count = 0
    for p in perf:
        try:
            pg_cur.execute('''
                INSERT INTO performance (id, question_id, user_answer, is_correct, user_id, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', (p["id"], p["question_id"], p["user_answer"],
                  bool(p["is_correct"]), p["user_id"] or 1, p["timestamp"]))
            count += 1
        except Exception as e:
            print(f"  AVISO perf id={p['id']}: {e}")
            pg.rollback()
    pg.commit()
    print(f"  ✓ {count}/{len(perf)} registros de performance migrados")

    # ── 5. PDF_CACHE ──────────────────────────────────────────────────────────
    print("\n[5/5] Migrando pdf_cache...")
    cache = sq.execute("SELECT * FROM pdf_cache").fetchall()
    count = 0
    for c in cache:
        try:
            pg_cur.execute('''
                INSERT INTO pdf_cache (id, file_hash, file_name, questions_extracted, processed_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (file_hash) DO NOTHING
            ''', (c["id"], c["file_hash"], c["file_name"],
                  c["questions_extracted"], c["processed_at"]))
            count += 1
        except Exception as e:
            print(f"  AVISO cache id={c['id']}: {e}")
            pg.rollback()
    pg.commit()
    print(f"  ✓ {count}/{len(cache)} entradas de cache migradas")

    # ── Resetar sequences (SERIAL) para continuar após IDs migrados ───────────
    print("\n[Extra] Atualizando sequences PostgreSQL...")
    for table in ["users", "questions", "options", "performance", "pdf_cache"]:
        pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}")
    pg.commit()
    print("  ✓ Sequences atualizadas")

    sq.close()
    pg_cur.close()
    pg.close()

    print("\n" + "=" * 55)
    print("  MISSAO CUMPRIDA! Dados migrados para o Supabase.")
    print("=" * 55)


if __name__ == "__main__":
    migrate()
