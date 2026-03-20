# -*- coding: utf-8 -*-
import hashlib
import psycopg2
import psycopg2.extras
import psycopg2.errors
from database import get_conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_default_admin():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        pwd_hash = hash_password('comandos')
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES ('admin', %s, 'admin')",
            (pwd_hash,)
        )
        conn.commit()
    cur.close()
    conn.close()


def create_user(username: str, password: str, role: str = 'student'):
    conn = get_conn()
    cur = conn.cursor()
    pwd_hash = hash_password(password)
    try:
        cur.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)',
            (username, pwd_hash, role)
        )
        conn.commit()
        return True
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def authenticate_user(username: str, password: str) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    pwd_hash = hash_password(password)
    cur.execute(
        'SELECT id, username, role FROM users WHERE username = %s AND password_hash = %s',
        (username, pwd_hash)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()
    return dict(user) if user else None


def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, username, role FROM users ORDER BY id')
    users = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(u) for u in users]


def delete_user(username: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = %s AND role != 'admin'", (username,))
    conn.commit()
    cur.close()
    conn.close()
