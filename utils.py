# utils.py
import os
import sys
import uuid
import json
import sqlite3
import hashlib
import base64
import pandas as pd
import arabic_reshaper
from bidi.algorithm import get_display

SECRET_SALT = "LOTUS_PHARMA_2026_SUPER_SECRET_KEY"

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def fix_arabic(text):
    if pd.isna(text): return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

def safe_label(text):
    if pd.isna(text): return ""
    return str(text).replace('$', '')

def clean_item_code(code):
    if pd.isna(code): return ""
    try:
        return str(int(float(code)))
    except:
        code_str = str(code).strip()
        if code_str.endswith('.0'): return code_str[:-2]
        return code_str

def translate_position(pos_name):
    if pd.isna(pos_name): return "Unknown"
    pos_str = str(pos_name).strip()
    if 'مساعد صيدلي' in pos_str: return 'Pharmacy Assistant'
    if 'صيدلي' in pos_str: return 'Pharmacist'
    if 'مدير' in pos_str or 'branch manager' in pos_str.lower(): return 'Branch Manager'
    if 'كاشير' in pos_str: return 'Cashier'
    if 'تجميل' in pos_str: return 'Cosmetics Specialist'
    if 'دليفري' in pos_str or 'delivery' in pos_str.lower(): return 'Delivery'
    if 'عامل' in pos_str: return 'Worker'
    if 'محاسب' in pos_str: return 'Accountant'
    return pos_str

def normalize_text(s):
    if pd.isna(s): return ""
    s = str(s).lower()
    for ch in [' ', '.', '_', '-', '/', '\\', '(', ')', '[', ']']:
        s = s.replace(ch, '')
    return s.strip()

def get_col(df, possible_names):
    df_cols_norm = {normalize_text(c): c for c in df.columns}
    for name in possible_names:
        norm_name = normalize_text(name)
        if norm_name in df_cols_norm:
            return df_cols_norm[norm_name]
    return None

def treeview_sort_column(tv, col, reverse):
    items = [(tv.set(k, col), k) for k in tv.get_children('') if 'subtotal' not in tv.item(k, 'tags')]
    
    def try_float(v):
        try:
            clean_v = str(v).replace(',', '').replace('%', '').replace(' mins', '').replace('+', '').replace('$', '').strip()
            return float(clean_v)
        except:
            return str(v).lower()

    items.sort(key=lambda t: try_float(t[0]), reverse=reverse)

    for index, (val, k) in enumerate(items):
        tv.move(k, '', index)
    
    for k in tv.get_children(''):
        if 'subtotal' in tv.item(k, 'tags'):
            tv.move(k, '', len(items))

    tv.heading(col, command=lambda: treeview_sort_column(tv, col, not reverse))

def get_mac_address():
    mac = uuid.getnode()
    return ''.join(['{:02x}'.format((mac >> ele) & 0xff) for ele in range(0,8*6,8)][::-1]).upper()

def xor_crypt(text, key):
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_local_db():
    conn = sqlite3.connect("lotus_local.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS app_license (activation_key TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS master_items (Material TEXT, Description TEXT, SubCat1 TEXT, SubCat2 TEXT, GranularCat TEXT, Price REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS security_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)''')
    
    cursor.execute("SELECT setting_value FROM security_settings WHERE setting_key='admin_password'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO security_settings VALUES ('admin_password', ?)", (hash_password("0000"),))
        cursor.execute("INSERT INTO security_settings VALUES ('security_question', 'What is your favorite color?')")
        cursor.execute("INSERT INTO security_settings VALUES ('security_answer', ?)", (hash_password("green"),))
    conn.commit()
    conn.close()

def check_password(input_pass):
    conn = sqlite3.connect("lotus_local.db")
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM security_settings WHERE setting_key='admin_password'")
    saved_hash = cursor.fetchone()[0]
    conn.close()
    return hash_password(input_pass) == saved_hash

def classify_material(mg):
    if pd.isna(mg): return 'Services'
    mg_upper = str(mg).upper().strip()
    if mg_upper in ['UNCATEGORIZED', 'UNKNOWN']: return 'Uncategorized'
    if 'D' in mg_upper or 'د' in mg_upper or 'ي' in mg_upper: return 'Drugs'
    if 'C' in mg_upper or 'ؤ' in mg_upper or 'تجميل' in mg_upper: return 'Cosmetics'
    if 'M' in mg_upper or 'م' in mg_upper or 'ة' in mg_upper: return 'Medical Accessories'
    return 'Services'

def classify_shift(time_val):
    try:
        val = str(time_val).strip()
        if ':' in val:
            parts = val.split(':')
            h, m = int(parts[0]), int(parts[1])
        else:
            h, m = int(float(time_val)), 0
        total_mins = h * 60 + m
        if 1 <= total_mins <= 480: return 'Night Shift'
        elif 481 <= total_mins <= 960: return 'Morning Shift'
        else: return 'Evening Shift'
    except: return 'Unknown'

def auto_fit_columns(tree):
    """تقوم هذه الدالة بضبط حجم كل عمود بناءً على أطول نص موجود فيه لضمان عدم تداخل النصوص"""
    for col in tree["columns"]:
        max_len = len(str(col)) + 4 
        for item in list(tree.get_children())[:200]: 
            val = str(tree.set(item, col))
            if len(val) > max_len:
                max_len = len(val)
        col_w = min(max_len * 9 + 25, 550) 
        col_w = max(col_w, 90) 
        tree.column(col, width=int(col_w))