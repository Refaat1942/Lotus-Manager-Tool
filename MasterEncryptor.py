import pandas as pd
import base64
import json

SECRET_SALT = "LOTUS_PHARMA_2026_SUPER_SECRET_KEY"

def xor_crypt(text, key):
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(text))

def encrypt_master_data(excel_path):
    try:
        # قراءة الشيت
        df = pd.read_excel(excel_path)
        # تحويل الداتا إلى JSON نصي
        json_data = df.to_json(orient='records')
        
        # التشفير
        encrypted_data = xor_crypt(json_data, SECRET_SALT)
        encoded_bytes = base64.b64encode(encrypted_data.encode('utf-8')).decode('utf-8')
        
        # حفظ الملف المشفر
        output_name = "MasterData.lotusdb"
        with open(output_name, "w", encoding='utf-8') as f:
            f.write(encoded_bytes)
        print(f"تم التشفير بنجاح! أعط الملف {output_name} للصيدلي.")
    except Exception as e:
        print(f"حدث خطأ: {e}")

# ضع مسار شيت الأصناف هنا وشغل السكربت
encrypt_master_data("Items_Master.xlsx")