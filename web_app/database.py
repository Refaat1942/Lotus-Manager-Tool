import os
import sqlite3
from pathlib import Path
from core.utils import hash_password

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "web_app" / "data"
UPLOAD_DIR = BASE_DIR / "web_app" / "static" / "uploads"
DB_PATH = DATA_DIR / "lotus_web.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            full_name TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS branding (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            app_name_en TEXT DEFAULT 'Lotus Manager Tool',
            app_name_ar TEXT DEFAULT 'أداة لوتس للإدارة',
            tagline_en TEXT DEFAULT 'Smart Analytics ERP',
            tagline_ar TEXT DEFAULT 'نظام تحليلات ذكي',
            primary_color TEXT DEFAULT '#27ae60',
            secondary_color TEXT DEFAULT '#1e8449',
            accent_color TEXT DEFAULT '#3498db',
            logo_path TEXT DEFAULT '/static/logo.png'
        );
        CREATE TABLE IF NOT EXISTS master_items (
            Material TEXT, Description TEXT, SubCat1 TEXT,
            SubCat2 TEXT, GranularCat TEXT, Price REAL
        );
        CREATE TABLE IF NOT EXISTS security_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        );
    """)
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
            ("admin", hash_password("admin"), "admin", "Administrator"),
        )
    c.execute("SELECT COUNT(*) FROM branding")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO branding (id, logo_path) VALUES (1, '/static/logo.png')")
    else:
        c.execute("UPDATE branding SET logo_path='/static/logo.png' WHERE id=1 AND (logo_path IS NULL OR logo_path='')")
    c.execute("SELECT setting_value FROM security_settings WHERE setting_key='admin_password'")
    if not c.fetchone():
        c.execute("INSERT INTO security_settings VALUES ('admin_password', ?)", (hash_password("admin"),))
    conn.commit()
    conn.close()


def verify_user(username: str, password: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
    ).fetchone()
    conn.close()
    if row and row["password_hash"] == hash_password(password):
        return dict(row)
    return None


def get_user_by_id(user_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def change_user_password(user_id: int, old_password: str, new_password: str):
    user = get_user_by_id(user_id)
    if not user or user["password_hash"] != hash_password(old_password):
        return False, "Incorrect old password"
    if len(new_password) < 4:
        return False, "Password must be at least 4 characters"
    update_user(user_id, password=new_password)
    return True, "Password changed"


def list_users():
    conn = get_conn()
    rows = conn.execute("SELECT id, username, role, full_name, is_active, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(username, password, role, full_name):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), role, full_name),
        )
        conn.commit()
        return True, "User created"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    finally:
        conn.close()


def update_user(user_id, role=None, full_name=None, is_active=None, password=None):
    conn = get_conn()
    if password:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), user_id))
    if role is not None:
        conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    if full_name is not None:
        conn.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, user_id))
    if is_active is not None:
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (is_active, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id=? AND username!='admin'", (user_id,))
    conn.commit()
    conn.close()


def get_branding():
    conn = get_conn()
    row = conn.execute("SELECT * FROM branding WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}


def update_branding(**kwargs):
    allowed = ["app_name_en", "app_name_ar", "tagline_en", "tagline_ar",
               "primary_color", "secondary_color", "accent_color", "logo_path"]
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return
    conn = get_conn()
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE branding SET {sets} WHERE id=1", list(fields.values()))
    conn.commit()
    conn.close()


def import_master_items(data_list):
    conn = get_conn()
    from core.utils import clean_item_code
    conn.execute("DELETE FROM master_items")
    for item in data_list:
        mat = clean_item_code(item.get("Material", ""))
        desc = str(item.get("Material description", ""))
        cat1 = str(item.get("SubCategory 1", "")).strip()
        cat2 = str(item.get("SubCategory 2", "")).strip()
        cat3 = str(item.get("SubCategory 3", "")).strip()
        granular = cat3 if cat3 else (cat2 if cat2 else cat1)
        price = item.get("Sales Price", 0)
        conn.execute(
            "INSERT INTO master_items VALUES (?, ?, ?, ?, ?, ?)",
            (mat, desc, cat1, cat2, granular, price),
        )
    conn.commit()
    conn.close()


def get_master_df():
    import pandas as pd
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM master_items", conn)
    conn.close()
    return df
