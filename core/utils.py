import hashlib
import base64
import pandas as pd
import arabic_reshaper
from bidi.algorithm import get_display

SECRET_SALT = "LOTUS_PHARMA_2026_SUPER_SECRET_KEY"


def fix_arabic(text):
    """For desktop/tkinter — reshapes and applies bidi."""
    if pd.isna(text):
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)


def web_text(text):
    """For web/HTML — return raw UTF-8; browser handles Arabic shaping & RTL."""
    if pd.isna(text):
        return ""
    return str(text).strip()


def safe_label(text):
    if pd.isna(text):
        return ""
    return str(text).replace("$", "")


def clean_item_code(code):
    if pd.isna(code):
        return ""
    try:
        return str(int(float(code)))
    except Exception:
        code_str = str(code).strip()
        if code_str.endswith(".0"):
            return code_str[:-2]
        return code_str


def translate_position(pos_name):
    if pd.isna(pos_name):
        return "Unknown"
    pos_str = str(pos_name).strip()
    if "مساعد صيدلي" in pos_str:
        return "Pharmacy Assistant"
    if "صيدلي" in pos_str:
        return "Pharmacist"
    if "مدير" in pos_str or "branch manager" in pos_str.lower():
        return "Branch Manager"
    if "كاشير" in pos_str:
        return "Cashier"
    if "تجميل" in pos_str:
        return "Cosmetics Specialist"
    if "دليفري" in pos_str or "delivery" in pos_str.lower():
        return "Delivery"
    if "عامل" in pos_str:
        return "Worker"
    if "محاسب" in pos_str:
        return "Accountant"
    return pos_str


def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).lower()
    for ch in [" ", ".", "_", "-", "/", "\\", "(", ")", "[", "]"]:
        s = s.replace(ch, "")
    return s.strip()


def get_col(df, possible_names):
    df_cols_norm = {normalize_text(c): c for c in df.columns}
    for name in possible_names:
        norm_name = normalize_text(name)
        if norm_name in df_cols_norm:
            return df_cols_norm[norm_name]
    return None


def xor_crypt(text, key):
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def classify_material(mg):
    if pd.isna(mg):
        return "Services"
    mg_upper = str(mg).upper().strip()
    if mg_upper in ["UNCATEGORIZED", "UNKNOWN"]:
        return "Uncategorized"
    if "D" in mg_upper or "د" in mg_upper or "ي" in mg_upper:
        return "Drugs"
    if "C" in mg_upper or "ؤ" in mg_upper or "تجميل" in mg_upper:
        return "Cosmetics"
    if "M" in mg_upper or "م" in mg_upper or "ة" in mg_upper:
        return "Medical Accessories"
    return "Services"


def classify_shift(time_val):
    try:
        val = str(time_val).strip()
        if ":" in val:
            parts = val.split(":")
            h, m = int(parts[0]), int(parts[1])
        else:
            h, m = int(float(time_val)), 0
        total_mins = h * 60 + m
        if 1 <= total_mins <= 480:
            return "Night Shift"
        if 481 <= total_mins <= 960:
            return "Morning Shift"
        return "Evening Shift"
    except Exception:
        return "Unknown"


def decrypt_master_file(content: str) -> list:
    decrypted_json = xor_crypt(base64.b64decode(content).decode("utf-8"), SECRET_SALT)
    return __import__("json").loads(decrypted_json)
