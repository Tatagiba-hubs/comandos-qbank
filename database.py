# -*- coding: utf-8 -*-
import os
import json
import csv
import io
from typing import List, Dict, Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    """Returns a new PostgreSQL connection."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            exam_origin TEXT,
            year TEXT,
            subject TEXT,
            difficulty TEXT,
            question_text TEXT,
            correct_answer_id INTEGER,
            resolution_1 TEXT,
            resolution_2 TEXT,
            image_path TEXT,
            has_image BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS options (
            id SERIAL PRIMARY KEY,
            question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
            option_letter TEXT,
            option_text TEXT
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS performance (
            id SERIAL PRIMARY KEY,
            question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
            user_answer TEXT,
            is_correct BOOLEAN,
            user_id INTEGER DEFAULT 1,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student'
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS pdf_cache (
            id SERIAL PRIMARY KEY,
            file_hash TEXT UNIQUE NOT NULL,
            file_name TEXT,
            questions_extracted INTEGER DEFAULT 0,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Safe migrations — ADD COLUMN IF NOT EXISTS (PostgreSQL nativo)
    migrations = [
        'ALTER TABLE questions ADD COLUMN IF NOT EXISTS resolution_1 TEXT',
        'ALTER TABLE questions ADD COLUMN IF NOT EXISTS resolution_2 TEXT',
        'ALTER TABLE questions ADD COLUMN IF NOT EXISTS image_path TEXT',
        'ALTER TABLE questions ADD COLUMN IF NOT EXISTS has_image BOOLEAN DEFAULT FALSE',
        'ALTER TABLE performance ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1',
    ]
    for m in migrations:
        cur.execute(m)

    conn.commit()
    cur.close()
    conn.close()


# ── PDF Cache ─────────────────────────────────────────────────────────────────

def is_pdf_cached(file_hash: str) -> Dict[str, Any] | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM pdf_cache WHERE file_hash = %s', (file_hash,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def mark_pdf_cached(file_hash: str, file_name: str, questions_count: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO pdf_cache (file_hash, file_name, questions_extracted)
        VALUES (%s, %s, %s)
        ON CONFLICT (file_hash) DO UPDATE
            SET file_name = EXCLUDED.file_name,
                questions_extracted = EXCLUDED.questions_extracted,
                processed_at = CURRENT_TIMESTAMP
    ''', (file_hash, file_name, questions_count))
    conn.commit()
    cur.close()
    conn.close()


# ── Export ────────────────────────────────────────────────────────────────────

def export_to_json(questions: List[Dict[str, Any]]) -> str:
    exportable = []
    for q in questions:
        exportable.append({
            "id": q.get("id"),
            "exam_origin": q.get("exam_origin"),
            "year": q.get("year"),
            "subject": q.get("subject"),
            "difficulty": q.get("difficulty"),
            "question_text": q.get("question_text"),
            "options": q.get("options", {}),
            "correct_answer_letter": q.get("correct_answer_letter"),
            "resolution_1": q.get("resolution_1", ""),
            "resolution_2": q.get("resolution_2", ""),
            "has_image": bool(q.get("has_image")),
            "created_at": str(q.get("created_at", "")),
        })
    return json.dumps(exportable, ensure_ascii=False, indent=2)


def export_to_csv(questions: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    headers = ["id", "exam_origin", "year", "subject", "difficulty",
                "question_text", "A", "B", "C", "D", "E",
                "correct_answer_letter", "resolution_1", "resolution_2"]
    writer.writerow(headers)
    for q in questions:
        opts = q.get("options", {})
        writer.writerow([
            q.get("id", ""), q.get("exam_origin", ""), q.get("year", ""),
            q.get("subject", ""), q.get("difficulty", ""), q.get("question_text", ""),
            opts.get("A", ""), opts.get("B", ""), opts.get("C", ""),
            opts.get("D", ""), opts.get("E", ""),
            q.get("correct_answer_letter", ""),
            q.get("resolution_1", ""), q.get("resolution_2", ""),
        ])
    return output.getvalue()


# ── Core CRUD ─────────────────────────────────────────────────────────────────

def insert_question(exam_origin: str, year: str, subject: str, difficulty: str,
                    question_text: str, options: Dict[str, str], correct_answer: str,
                    resolution_1: str = "", resolution_2: str = "",
                    image_path: str = "", has_image: bool = False) -> int:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute('''
        INSERT INTO questions (exam_origin, year, subject, difficulty, question_text,
                               resolution_1, resolution_2, image_path, has_image)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    ''', (exam_origin, year, subject, difficulty, question_text,
          resolution_1, resolution_2, image_path, has_image))

    question_id = cur.fetchone()["id"]

    correct_option_id = None
    for letter, text in options.items():
        cur.execute('''
            INSERT INTO options (question_id, option_letter, option_text)
            VALUES (%s, %s, %s)
            RETURNING id
        ''', (question_id, letter, text))
        option_id = cur.fetchone()["id"]
        if letter == correct_answer:
            correct_option_id = option_id

    if correct_option_id is not None:
        cur.execute('UPDATE questions SET correct_answer_id = %s WHERE id = %s',
                    (correct_option_id, question_id))

    conn.commit()
    cur.close()
    conn.close()
    return question_id


def get_all_questions() -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute('SELECT * FROM questions ORDER BY created_at DESC')
    rows = cur.fetchall()

    questions = []
    for row in rows:
        q_dict: Dict[str, Any] = dict(row)

        cur.execute(
            'SELECT option_letter, option_text FROM options WHERE question_id = %s ORDER BY option_letter',
            (row['id'],))
        opts = cur.fetchall()
        q_dict['options'] = {opt['option_letter']: opt['option_text'] for opt in opts}

        correct_letter = None
        if row['correct_answer_id']:
            cur.execute('SELECT option_letter FROM options WHERE id = %s',
                        (row['correct_answer_id'],))
            res = cur.fetchone()
            if res:
                correct_letter = res['option_letter']

        q_dict['correct_answer_letter'] = correct_letter
        questions.append(q_dict)

    cur.close()
    conn.close()
    return questions


def update_resolution(question_id: int, resolution_1: str, resolution_2: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        'UPDATE questions SET resolution_1 = %s, resolution_2 = %s WHERE id = %s',
        (resolution_1, resolution_2, question_id)
    )
    conn.commit()
    cur.close()
    conn.close()


def save_performance(question_id: int, user_answer: str, is_correct: bool, user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO performance (question_id, user_answer, is_correct, user_id)
        VALUES (%s, %s, %s, %s)
    ''', (question_id, user_answer, is_correct, user_id))
    conn.commit()
    cur.close()
    conn.close()


def get_performance_stats(user_id: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT p.is_correct, q.subject, q.difficulty, p.timestamp
        FROM performance p
        JOIN questions q ON p.question_id = q.id
        WHERE p.user_id = %s
        ORDER BY p.timestamp DESC
    ''', (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_user_rank(user_id: int, role: str) -> tuple[str, int]:
    if role == 'admin':
        return ("Comandante do EB", 999999)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT q.difficulty
        FROM performance p
        JOIN questions q ON p.question_id = q.id
        WHERE p.user_id = %s AND p.is_correct = TRUE
    ''', (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    points = 0
    for r in rows:
        d = (r['difficulty'] or '').lower()
        if 'facil' in d or 'fácil' in d:
            points += 1
        elif 'medio' in d or 'médio' in d:
            points += 2
        elif 'dificil' in d or 'difícil' in d:
            points += 3
        else:
            points += 1

    if points < 5:    rank = "Recruta"
    elif points < 15:  rank = "Soldado"
    elif points < 30:  rank = "Cabo"
    elif points < 50:  rank = "3º Sargento"
    elif points < 80:  rank = "2º Sargento"
    elif points < 120: rank = "1º Sargento"
    elif points < 180: rank = "Subtenente"
    elif points < 250: rank = "Aspirante a Oficial"
    elif points < 350: rank = "1º Tenente"
    elif points < 500: rank = "Capitão"
    elif points < 750: rank = "Major"
    elif points < 1200:rank = "Tenente-Coronel"
    elif points < 2000:rank = "Coronel"
    else:              rank = "General"

    return rank, points


def get_question_by_id(question_id: int) -> Dict[str, Any] | None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM questions WHERE id = %s', (question_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None

    q_dict = dict(row)
    cur.execute(
        'SELECT option_letter, option_text FROM options WHERE question_id = %s ORDER BY option_letter',
        (question_id,))
    opts = cur.fetchall()
    q_dict['options'] = {opt['option_letter']: opt['option_text'] for opt in opts}

    correct_letter = None
    if row['correct_answer_id']:
        cur.execute('SELECT option_letter FROM options WHERE id = %s', (row['correct_answer_id'],))
        res = cur.fetchone()
        if res:
            correct_letter = res['option_letter']

    q_dict['correct_answer_letter'] = correct_letter
    cur.close()
    conn.close()
    return q_dict


if __name__ == "__main__":
    init_db()
    print("Database PostgreSQL inicializado.")
