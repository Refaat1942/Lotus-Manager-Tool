# windows.py
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, simpledialog
from PIL import Image
import os
import sqlite3
import hashlib
from utils import *

GREEN_PRIMARY = "#27ae60"
GREEN_HOVER = "#2ecc71"

class ChangePasswordDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Change Admin Password")
        self.geometry("400x350")
        self.attributes("-topmost", True)
        self.transient(parent)
        
        self.main_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        ctk.CTkLabel(self.main_frame, text="Security Settings", font=("Segoe UI", 18, "bold"), text_color="#27ae60").pack(pady=(10, 20))
        
        self.old_entry = ctk.CTkEntry(self.main_frame, show="*", placeholder_text="Old Password", justify="center", width=250)
        self.old_entry.pack(pady=5)
        
        self.new_entry = ctk.CTkEntry(self.main_frame, show="*", placeholder_text="New Password", justify="center", width=250)
        self.new_entry.pack(pady=5)
        
        self.confirm_entry = ctk.CTkEntry(self.main_frame, show="*", placeholder_text="Confirm New Password", justify="center", width=250)
        self.confirm_entry.pack(pady=5)
        
        ctk.CTkButton(self.main_frame, text="Save Changes", font=("Segoe UI", 14, "bold"), fg_color="#27ae60", hover_color="#2ecc71", command=self.save_password).pack(pady=25)
        
        self.grab_set()
        self.wait_window()
        
    def save_password(self):
        old_p = self.old_entry.get()
        new_p = self.new_entry.get()
        confirm_p = self.confirm_entry.get()
        
        if not old_p or not check_password(old_p):
            messagebox.showerror("Error", "Incorrect old password!")
            return
            
        if not new_p or len(new_p) < 4:
            messagebox.showerror("Error", "New password must be at least 4 characters!")
            return
            
        if new_p == confirm_p:
            conn = sqlite3.connect("lotus_local.db")
            conn.execute("UPDATE security_settings SET setting_value=? WHERE setting_key='admin_password'", (hash_password(new_p),))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Password changed successfully!")
            self.destroy()
        else:
            messagebox.showerror("Error", "Passwords do not match!")

class PasswordDialog(ctk.CTkToplevel):
    def __init__(self, parent, title="Authentication Required"):
        super().__init__(parent)
        self.title(title)
        self.geometry("380x250")
        self.attributes("-topmost", True)
        self.transient(parent)
        self.result = False
        
        self.main_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray15"))
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(self.main_frame, text="Enter Admin Password:", font=("Segoe UI", 16, "bold")).pack(pady=(20, 10))
        self.pwd_entry = ctk.CTkEntry(self.main_frame, show="*", justify="center", width=200, height=35)
        self.pwd_entry.pack(pady=10)
        
        ctk.CTkButton(self.main_frame, text="Login", font=("Segoe UI", 14, "bold"), fg_color="#27ae60", hover_color="#2ecc71", command=self.verify).pack(pady=15)
        ctk.CTkButton(self.main_frame, text="Forgot Password?", fg_color="transparent", text_color="#3498db", command=self.forgot_pwd).pack()
        
        self.grab_set()
        self.wait_window()
        
    def verify(self):
        if check_password(self.pwd_entry.get()):
            self.result = True
            self.destroy()
        else:
            messagebox.showerror("Error", "Incorrect Password!")
            
    def forgot_pwd(self):
        ans = simpledialog.askstring("Security Question", "What is your favorite color? (Default: green)")
        if ans and hash_password(ans.lower().strip()) == hash_password("green"): 
            messagebox.showinfo("Reset", "Password has been reset to: 0000")
            conn = sqlite3.connect("lotus_local.db")
            conn.execute("UPDATE security_settings SET setting_value=? WHERE setting_key='admin_password'", (hash_password("0000"),))
            conn.commit()
            conn.close()
        else:
            messagebox.showerror("Error", "Incorrect Answer!")

class ActivationWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Lotus App Activation")
        self.geometry("500x350")
        self.eval('tk::PlaceWindow . center')
        self.mac = get_mac_address()
        
        ctk.CTkLabel(self, text="Software Activation Required", font=("Segoe UI", 20, "bold"), text_color=GREEN_PRIMARY).pack(pady=20)
        ctk.CTkLabel(self, text="Machine ID (Send this to the developer):", font=("Segoe UI", 12)).pack()
        mac_entry = ctk.CTkEntry(self, width=300, justify="center")
        mac_entry.insert(0, self.mac)
        mac_entry.configure(state="readonly")
        mac_entry.pack(pady=5)
        
        ctk.CTkLabel(self, text="Enter Activation Key:", font=("Segoe UI", 12)).pack(pady=(20, 5))
        self.key_entry = ctk.CTkEntry(self, width=300, justify="center")
        self.key_entry.pack(pady=5)
        
        self.is_activated = False
        ctk.CTkButton(self, text="Activate", fg_color=GREEN_PRIMARY, hover_color=GREEN_HOVER, command=self.activate).pack(pady=20)

    def activate(self):
        key = self.key_entry.get().strip().upper()
        expected_key = hashlib.sha256(f"{self.mac}_{SECRET_SALT}".encode()).hexdigest()[:16].upper()
        
        if key == expected_key:
            conn = sqlite3.connect("lotus_local.db")
            conn.execute("DELETE FROM app_license")
            conn.execute("INSERT INTO app_license (activation_key) VALUES (?)", (key,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Application Activated Successfully!")
            self.is_activated = True
            self.destroy()
        else:
            messagebox.showerror("Error", "Invalid Activation Key!")

class SplashScreen(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Loading...")
        self.geometry("650x450")
        self.eval('tk::PlaceWindow . center')
        self.overrideredirect(True) 
        
        bg_color = "#ffffff" if ctk.get_appearance_mode() == "Light" else "#1e1e1e"
        self.configure(fg_color=bg_color)
        
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            image = Image.open(logo_path)
            logo_img = ctk.CTkImage(light_image=image, dark_image=image, size=(200, 200))
            self.lbl_logo = ctk.CTkLabel(self, image=logo_img, text="")
            self.lbl_logo.pack(pady=(40, 10))
        else:
            self.lbl_logo = ctk.CTkLabel(self, text="Lotus Manager Tool", font=ctk.CTkFont(family="Georgia", size=42, weight="bold", slant="italic"), text_color=GREEN_PRIMARY)
            self.lbl_logo.pack(pady=(70, 30))

        self.lbl_loading = ctk.CTkLabel(self, text="Initializing Smart Analytics System...", font=("Segoe UI", 14, "bold"), text_color="gray")
        self.lbl_loading.pack(pady=5)

        self.progress = ctk.CTkProgressBar(self, width=400, progress_color=GREEN_PRIMARY, height=15)
        self.progress.pack(pady=20)
        self.progress.set(0)
        self.update_progress(0)

    def update_progress(self, value):
        if value <= 1:
            self.progress.set(value)
            self.after(35, self.update_progress, value + 0.01)
        else:
            self.destroy()