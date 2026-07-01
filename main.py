# main.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import numpy as np
from datetime import datetime
import sqlite3
import win32com.client as win32
import os
import re
import json
import base64
from tkcalendar import DateEntry  

from utils import *
from windows import *
import extra_tabs 

ctk.set_appearance_mode("Light") 
ctk.set_default_color_theme("green") 

GREEN_PRIMARY = "#27ae60"
GREEN_HOVER = "#2ecc71"
DARK_GREEN = "#1e8449"

class DashboardWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Lotus Manager Tool - Analytics ERP")
        self.state('zoomed')
        
        self.df = None
        self.raw_df = None
        self.current_emp_stats = None 
        self.global_stats = {}
        self.branch_name = "Branch"
        self.period_info = {}
        
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        
        self.navbar = ctk.CTkFrame(self, height=55, corner_radius=0, fg_color=(GREEN_PRIMARY, DARK_GREEN))
        self.navbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        nav_font = ctk.CTkFont(family="Georgia", size=22, weight="bold", slant="italic")
        ctk.CTkLabel(self.navbar, text="Lotus Manager Tool", font=nav_font, text_color="white").pack(side="left", padx=20, pady=10)
        
        self.calc_mode = ctk.StringVar(value="Total")
        self.mode_switch = ctk.CTkSegmentedButton(self.navbar, variable=self.calc_mode, values=["Total", "Daily Average"], command=self.on_mode_change, selected_color="#3498db")
        self.mode_switch.pack(side="right", padx=(10, 20), pady=10)
        
        self.appearance_switch = ctk.CTkSwitch(self.navbar, text="Dark Mode", text_color="white", font=("Segoe UI", 12, "bold"), command=self.toggle_mode)
        self.appearance_switch.pack(side="right", padx=10, pady=10)

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="Menu & Filters", font=("Segoe UI", 18, "bold")).pack(pady=10)
        
        self.btn_load = ctk.CTkButton(self.sidebar, text="Load Data (XLSX / CSV)", font=("Segoe UI", 14, "bold"), fg_color="#3498db", command=self.load_data, height=40)
        self.btn_load.pack(pady=(0, 5), padx=20, fill="x")

        self.loading_label = ctk.CTkLabel(self.sidebar, text="Ready", font=("Segoe UI", 11), text_color="gray")
        self.loading_label.pack(pady=(0, 0))
        
        self.progress_bar = ctk.CTkProgressBar(self.sidebar, height=10, progress_color=GREEN_PRIMARY)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(0, 10), padx=25, fill="x")

        self.btn_load_master = ctk.CTkButton(self.sidebar, text="Upload Master Data (.lotusdb)", fg_color="#8e44ad", hover_color="#9b59b6", command=self.load_encrypted_master, height=35)
        self.btn_load_master.pack(pady=(0, 10), padx=20, fill="x")

        ctk.CTkButton(self.sidebar, text="Change Password Settings", fg_color="gray30", command=self.change_admin_password, height=30).pack(pady=5, padx=20, fill="x")
        
        self.date_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.date_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(self.date_frame, text="Date Range Filter:", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        
        date_inputs = ctk.CTkFrame(self.date_frame, fg_color="transparent")
        date_inputs.pack(fill="x", pady=5)
        
        ctk.CTkLabel(date_inputs, text="From:", font=("Segoe UI", 10)).grid(row=0, column=0, padx=2)
        self.start_date_picker = DateEntry(date_inputs, width=10, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.start_date_picker.grid(row=0, column=1, padx=2)
        
        ctk.CTkLabel(date_inputs, text="To:", font=("Segoe UI", 10)).grid(row=0, column=2, padx=2)
        self.end_date_picker = DateEntry(date_inputs, width=10, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.end_date_picker.grid(row=0, column=3, padx=2)

        self.filters_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.filters_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.emp_container, self.emp_checkboxes = self.create_filter_section("Employees Filter:", self.toggle_emps)
        self.branch_container, self.branch_checkboxes = self.create_filter_section("Branches Filter:", self.toggle_branches)
        self.shift_container, self.shift_checkboxes = self.create_filter_section("Shifts Filter:", self.toggle_shifts) # إضافتك هنا
        self.cat_container, self.cat_checkboxes = self.create_filter_section("Categories Filter:", self.toggle_cats)
        self.mat_container, self.mat_checkboxes = self.create_filter_section("Material Group Filter:", self.toggle_mats)

        self.btn_apply = ctk.CTkButton(self.sidebar, text="Apply Filters", font=("Segoe UI", 14, "bold"), fg_color=GREEN_PRIMARY, hover_color=GREEN_HOVER, command=self.apply_filters, height=45)
        self.btn_apply.pack(side="bottom", pady=(10, 20), padx=20, fill="x")

        # --- Tabs ---
        self.tabs = ctk.CTkTabview(self, corner_radius=10)
        self.tabs.grid(row=1, column=1, sticky="nsew", padx=15, pady=15)
        
        self.tab_overview = self.tabs.add("Overview & Charts")
        self.tab_advanced_charts = self.tabs.add("Advanced Charts")
        self.tab_exec_summary = self.tabs.add("Executive Summary")
        self.tab_employees = self.tabs.add("Employees Analysis")
        self.tab_products = self.tabs.add("Top Products")
        self.tab_custom_compare = self.tabs.add("Date Compare")
        self.tab_compare = self.tabs.add("Trend Comparison (History)")
        self.tab_stagnant = self.tabs.add("Stagnant Alternatives")
        
        self.setup_overview_tab()
        self.setup_advanced_charts_tab()
        self.setup_employees_tab()
        self.setup_products_tab()
        self.setup_compare_tab()
        self.setup_stagnant_tab()

        self.apply_tree_styles()

    @property
    def current_divisor(self):
        if self.calc_mode.get() == "Daily Average":
            return max(1, self.period_info.get('days', 1))
        return 1

    def on_mode_change(self, *args):
        if self.df is not None:
            self.update_kpis_and_charts()
            self.build_employee_views()
            self.build_products_table()
            extra_tabs.setup_executive_summary_tab(self.tab_exec_summary, self)
            extra_tabs.setup_custom_compare_tab(self.tab_custom_compare, self)

    def add_export_context_menu(self, tree, name):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f"Export {name} to Excel", command=lambda: self.export_treeview_to_excel(tree, name))
        def show_menu(event): menu.post(event.x_root, event.y_root)
        tree.bind("<Button-3>", show_menu) 

    def change_admin_password(self):
        try:
            ChangePasswordDialog(self)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open password dialog: {e}")

    def update_status(self, text, progress):
        self.loading_label.configure(text=text)
        self.progress_bar.set(progress)
        self.update_idletasks()

    def create_filter_section(self, title, toggle_cmd):
        frame = ctk.CTkFrame(self.filters_scroll, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=(15,0))
        ctk.CTkLabel(frame, text=title, font=("Segoe UI", 12, "bold")).pack(side="left")
        ctk.CTkButton(frame, text="None", width=40, height=22, font=("Segoe UI", 10), command=lambda: toggle_cmd(False)).pack(side="right", padx=2)
        ctk.CTkButton(frame, text="All", width=40, height=22, font=("Segoe UI", 10), command=lambda: toggle_cmd(True)).pack(side="right")
        container = ctk.CTkFrame(self.filters_scroll, fg_color="transparent")
        container.pack(fill="x", padx=10, pady=2)
        return container, {}

    def setup_overview_tab(self):
        self.lbl_date_range = ctk.CTkLabel(self.tab_overview, text="Showing Data For: N/A", font=("Segoe UI", 14, "bold"), text_color="#3498db")
        self.lbl_date_range.pack(pady=5)
        
        self.kpi_frame = ctk.CTkFrame(self.tab_overview, fg_color="transparent")
        self.kpi_frame.pack(fill="x", pady=5)
        self.kpi_sales = self.create_kpi(self.kpi_frame, "Total Sales", "#3498db")
        self.kpi_receipts = self.create_kpi(self.kpi_frame, "Total Receipts", "#f1c40f")
        self.kpi_avg = self.create_kpi(self.kpi_frame, "Avg Receipt Value", GREEN_PRIMARY)
        self.kpi_pcs = self.create_kpi(self.kpi_frame, "Total Pieces Sold", "#e74c3c")
        
        self.charts_frame = ctk.CTkFrame(self.tab_overview, fg_color="transparent")
        self.charts_frame.pack(fill="both", expand=True, pady=10)
        
        self.charts_left = ctk.CTkFrame(self.charts_frame, fg_color="transparent")
        self.charts_left.pack(side="left", fill="both", expand=True, padx=5)
        
        self.charts_right = ctk.CTkFrame(self.charts_frame, fg_color="transparent")
        self.charts_right.pack(side="right", fill="both", expand=True, padx=5)

    def setup_advanced_charts_tab(self):
        self.adv_charts_frame = ctk.CTkFrame(self.tab_advanced_charts, fg_color="transparent")
        self.adv_charts_frame.pack(fill="both", expand=True, pady=10, padx=10)

    def setup_employees_tab(self):
        top_frame = ctk.CTkFrame(self.tab_employees, fg_color="transparent")
        top_frame.pack(fill="x", pady=10, padx=10)
        self.emp_mode = ctk.StringVar(value="Performance Overview")
        self.seg_btn = ctk.CTkSegmentedButton(top_frame, variable=self.emp_mode, values=["Performance Overview", "Sales Types Breakdown", "Subcategories Analysis", "Efficiency & Time", "AI Recommendations"], command=self.build_employee_views, font=("Segoe UI", 12, "bold"))
        self.seg_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(top_frame, text="Export to Excel 📊", font=("Segoe UI", 12, "bold"), fg_color=GREEN_PRIMARY, hover_color=GREEN_HOVER, command=lambda: self.export_treeview_to_excel(self.tree_emp, "Employees")).pack(side="right")
        self.tree_emp_frame = ctk.CTkFrame(self.tab_employees)
        self.tree_emp_frame.pack(fill="both", expand=True, pady=5)
        self.tree_emp = ttk.Treeview(self.tree_emp_frame)
        scroll_y = ttk.Scrollbar(self.tree_emp_frame, orient="vertical", command=self.tree_emp.yview)
        scroll_x = ttk.Scrollbar(self.tree_emp_frame, orient="horizontal", command=self.tree_emp.xview)
        self.tree_emp.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side="right", fill="y"); scroll_x.pack(side="bottom", fill="x"); self.tree_emp.pack(fill="both", expand=True)

    def setup_products_tab(self):
        top_frame = ctk.CTkFrame(self.tab_products, fg_color="transparent")
        top_frame.pack(fill="x", pady=10, padx=10)
        ctk.CTkLabel(top_frame, text="Top Products Overview", font=("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkButton(top_frame, text="Export to Excel 📊", font=("Segoe UI", 12, "bold"), fg_color=GREEN_PRIMARY, hover_color=GREEN_HOVER, command=lambda: self.export_treeview_to_excel(self.tree_prod, "Products")).pack(side="right")
        self.tree_prod_frame = ctk.CTkFrame(self.tab_products)
        self.tree_prod_frame.pack(fill="both", expand=True, pady=5)
        self.tree_prod = ttk.Treeview(self.tree_prod_frame)
        scroll_y2 = ttk.Scrollbar(self.tree_prod_frame, orient="vertical", command=self.tree_prod.yview)
        scroll_x2 = ttk.Scrollbar(self.tree_prod_frame, orient="horizontal", command=self.tree_prod.xview)
        self.tree_prod.configure(yscrollcommand=scroll_y2.set, xscrollcommand=scroll_x2.set)
        scroll_y2.pack(side="right", fill="y"); scroll_x2.pack(side="bottom", fill="x"); self.tree_prod.pack(fill="both", expand=True)

    def setup_compare_tab(self):
        top_frame = ctk.CTkFrame(self.tab_compare, fg_color="transparent")
        top_frame.pack(fill="x", pady=10, padx=10)
        ctk.CTkButton(top_frame, text="1. Export Current Snapshot", font=("Segoe UI", 12, "bold"), fg_color="#3498db", command=self.export_snapshot).pack(side="left", padx=10)
        ctk.CTkButton(top_frame, text="2. Load History & Compare", font=("Segoe UI", 12, "bold"), fg_color="#9b59b6", command=self.load_snapshot).pack(side="left", padx=10)
        self.global_comp_frame = ctk.CTkFrame(self.tab_compare, corner_radius=10, border_width=1, border_color="gray")
        self.global_comp_frame.pack(fill="x", padx=20, pady=10)
        self.lbl_comp_meta = ctk.CTkLabel(self.global_comp_frame, text="Load historical data to see branch-level and employee-level comparison.", font=("Segoe UI", 14), text_color="gray")
        self.lbl_comp_meta.pack(pady=20)
        self.tree_comp_frame = ctk.CTkFrame(self.tab_compare)
        self.tree_comp_frame.pack(fill="both", expand=True, pady=5, padx=20)
        self.tree_comp = ttk.Treeview(self.tree_comp_frame)
        scroll_y3 = ttk.Scrollbar(self.tree_comp_frame, orient="vertical", command=self.tree_comp.yview)
        scroll_x3 = ttk.Scrollbar(self.tree_comp_frame, orient="horizontal", command=self.tree_comp.xview)
        self.tree_comp.configure(yscrollcommand=scroll_y3.set, xscrollcommand=scroll_x3.set)
        scroll_y3.pack(side="right", fill="y"); scroll_x3.pack(side="bottom", fill="x"); self.tree_comp.pack(fill="both", expand=True)

    def setup_stagnant_tab(self):
        top_frame = ctk.CTkFrame(self.tab_stagnant, fg_color="transparent")
        top_frame.pack(fill="x", pady=10, padx=10)
        ctk.CTkButton(top_frame, text="Analyze Stagnant Drugs", font=("Segoe UI", 12, "bold"), fg_color="#e74c3c", command=self.analyze_stagnant).pack(side="left", padx=10)
        ctk.CTkButton(top_frame, text="Export to Excel 📊", font=("Segoe UI", 12, "bold"), fg_color=GREEN_PRIMARY, hover_color=GREEN_HOVER, command=lambda: self.export_treeview_to_excel(self.tree_stag, "Stagnant_Drugs")).pack(side="right")
        self.tree_stag_frame = ctk.CTkFrame(self.tab_stagnant)
        self.tree_stag_frame.pack(fill="both", expand=True, pady=5, padx=10)
        self.tree_stag = ttk.Treeview(self.tree_stag_frame)
        scroll_y = ttk.Scrollbar(self.tree_stag_frame, orient="vertical", command=self.tree_stag.yview)
        scroll_x = ttk.Scrollbar(self.tree_stag_frame, orient="horizontal", command=self.tree_stag.xview)
        self.tree_stag.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.pack(side="right", fill="y"); scroll_x.pack(side="bottom", fill="x"); self.tree_stag.pack(fill="both", expand=True)

    def load_encrypted_master(self):
        file_path = filedialog.askopenfilename(filetypes=[("Lotus Database", "*.lotusdb")])
        if not file_path: return
        try:
            with open(file_path, "r", encoding='utf-8') as f: encoded_data = f.read()
            decrypted_json = xor_crypt(base64.b64decode(encoded_data).decode('utf-8'), SECRET_SALT)
            data_list = json.loads(decrypted_json)
            conn = sqlite3.connect("lotus_local.db")
            conn.execute("DELETE FROM master_items") 
            for item in data_list:
                mat = clean_item_code(item.get('Material', ''))
                desc = str(item.get('Material description', ''))
                cat1, cat2, cat3 = str(item.get('SubCategory 1', '')).strip(), str(item.get('SubCategory 2', '')).strip(), str(item.get('SubCategory 3', '')).strip()
                granular_cat = cat3 if cat3 else (cat2 if cat2 else cat1)
                price = item.get('Sales Price', 0)
                conn.execute("INSERT INTO master_items VALUES (?, ?, ?, ?, ?, ?)", (mat, desc, cat1, cat2, granular_cat, price))
            conn.commit(); conn.close()
            messagebox.showinfo("Success", "Master data updated successfully in database!")
        except Exception as e: messagebox.showerror("Error", f"Failed to load master data.\n{e}")

    def create_kpi(self, parent, title, color):
        card = ctk.CTkFrame(parent, border_width=2, border_color=color, height=90)
        card.pack(side="left", fill="both", expand=True, padx=8)
        ctk.CTkLabel(card, text=title, font=("Segoe UI", 14, "bold"), text_color="gray").pack(pady=(15, 0))
        lbl = ctk.CTkLabel(card, text="0", font=("Segoe UI", 24, "bold"))
        lbl.pack(pady=(5, 15))
        return lbl

    def toggle_mode(self):
        ctk.set_appearance_mode("Dark" if self.appearance_switch.get() == 1 else "Light")
        self.apply_tree_styles()
        if self.df is not None: self.draw_charts()

    def toggle_emps(self, state):
        for var in self.emp_checkboxes.values(): var.set(state)
    def toggle_branches(self, state):
        for var in self.branch_checkboxes.values(): var.set(state)
    def toggle_shifts(self, state):
        for var in self.shift_checkboxes.values(): var.set(state)
    def toggle_cats(self, state):
        for var in self.cat_checkboxes.values(): var.set(state)
    def toggle_mats(self, state):
        for var in self.mat_checkboxes.values(): var.set(state)

    def apply_tree_styles(self):
        style = ttk.Style()
        style.theme_use("default")
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg = "#2b2b2b" if is_dark else "white"
        fg = "white" if is_dark else "black"
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, rowheight=32, font=("Segoe UI", 10))
        style.map('Treeview', background=[('selected', GREEN_PRIMARY)])
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"), background=DARK_GREEN, foreground="white")
        style_color = "#34495e" if is_dark else "#dff9fb"
        style_text = "white" if is_dark else "#2c3e50"
        for tv in [self.tree_emp, self.tree_prod, self.tree_stag, self.tree_comp]:
            if hasattr(self, 'tree_emp'): tv.tag_configure('subtotal', background=style_color, foreground=style_text, font=('Segoe UI', 11, 'bold'))

    def load_data(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel and CSV Files", "*.xlsx *.xls *.csv")])
        if not file_path: return
        try:
            self.update_status("Reading file...", 0.1)
            if file_path.lower().endswith('.csv'):
                try: df = pd.read_csv(file_path, encoding='utf-8-sig')
                except UnicodeDecodeError: df = pd.read_csv(file_path, encoding='windows-1256')
            else:
                df = pd.read_excel(file_path, engine="openpyxl")
            
            self.update_status("File loaded, processing...", 0.3)
            self.prepare_data(df)
        except Exception as e: 
            self.update_status("Error occurred", 0)
            messagebox.showerror("Error", f"Could not process data:\n{e}")

    def prepare_data(self, df):
        self.update_status("Mapping columns...", 0.4)
        self.c_price = get_col(df, ["Sales Price", "Price", "Gross Sales", "Net Sales"])
        self.c_qty = get_col(df, ["Quantity Dimenions", "Quantity Dimensions", "Quantity", "Qty", "Total Qty"])
        self.c_name = get_col(df, ["Full Name", "Employee Name", "Name", "Salespers."])
        self.c_cat = get_col(df, ["Z Customer Group", "Sales Type", "Customer Group"])
        self.c_rec = get_col(df, ["Reciept.No", "Receipt Number", "Trans.", "Invoice"])
        self.c_mat = get_col(df, ["Mat.Group", "Material Group", "Mat Group", "MatGrp", "Category", "مجموعة الأصناف", "المجموعة", "التصنيف", "Item_Type"])
        self.c_desc = get_col(df, ["Material Description", "Material", "Item", "Description", "الصنف"])
        self.c_time = get_col(df, ["Time", "Hour of sale"])
        self.c_date = get_col(df, ["Date"])
        self.c_bun = get_col(df, ["BUn", "Unit", "SU"])
        self.c_pos = get_col(df, ["POS no.", "POS"])
        self.c_branch = get_col(df, ["Branch Name", "Branch", "Site", "Plant"])
        self.c_item_code = get_col(df, ["Item Code", "Material", "Code", "رقم الصنف"])
        self.c_pos_name = get_col(df, ["Position Name", "الوظيفة"])

        if not self.c_price or not self.c_name:
            self.update_status("Essential columns missing", 0)
            messagebox.showerror("Data Error", "Missing essential columns.")
            return

        self.update_status("Cleaning data...", 0.5)
        if self.c_date: df = df.dropna(subset=[self.c_date])
        if self.c_rec: df = df.dropna(subset=[self.c_rec])

        df[self.c_price] = pd.to_numeric(df[self.c_price].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        if self.c_qty: df[self.c_qty] = pd.to_numeric(df[self.c_qty].astype(str).str.replace(',', ''), errors='coerce').fillna(0.0)
        else: df['Quantity'] = 1.0; self.c_qty = 'Quantity'

        if self.c_item_code: df[self.c_item_code] = df[self.c_item_code].apply(clean_item_code)
        if self.c_pos_name: df['Translated_Position'] = df[self.c_pos_name].apply(translate_position)

        self.update_status("Classifying items & shifts...", 0.7)
        if self.c_mat: df['Item_Type'] = df[self.c_mat].apply(classify_material)
        else: df['Item_Type'] = "Uncategorized"

        if self.c_time: df['Shift_Name'] = df[self.c_time].apply(classify_shift)

        if self.c_branch and not df[self.c_branch].dropna().empty: self.branch_name = str(df[self.c_branch].dropna().iloc[0])
        else: self.branch_name = "Lotus_Plant"

        if self.c_date and not df[self.c_date].dropna().empty:
            df['Parsed_Date'] = pd.to_datetime(df[self.c_date], errors='coerce')
            dates = df['Parsed_Date'].dropna()
            if not dates.empty:
                min_date = dates.min()
                max_date = dates.max()
                self.period_info['start'] = min_date.strftime('%Y-%m-%d')
                self.period_info['end'] = max_date.strftime('%Y-%m-%d')
                self.period_info['days'] = (max_date - min_date).days + 1
                
                self.start_date_picker.set_date(min_date)
                self.end_date_picker.set_date(max_date)
            else: self.period_info = {'start': 'N/A', 'end': 'N/A', 'days': 1}
        else: self.period_info = {'start': 'N/A', 'end': 'N/A', 'days': 1}

        if self.c_date and self.c_time:
            try:
                df['DateTime'] = pd.to_datetime(df[self.c_date].astype(str) + ' ' + df[self.c_time].astype(str), errors='coerce')
                df['Sale_Hour'] = df['DateTime'].dt.hour
            except: pass

        # التعديل تم إضافته هنا لتجميع بيانات الريسيت
        if self.c_rec:
            cols_to_join = [self.c_name, self.c_rec]
            if self.c_date: cols_to_join.append(self.c_date)
            if self.c_pos: cols_to_join.append(self.c_pos)
            if self.c_branch: cols_to_join.append(self.c_branch)  # تم إضافة الفرع لضمان حساب الريسيت بشكل دقيق
            df['True_Receipt_ID'] = df[cols_to_join].astype(str).agg('_'.join, axis=1)

        self.raw_df = df
        self.update_status("Updating filters & charts...", 0.9)
        self.populate_filters()
        self.apply_filters()
        self.update_status("Success: Data Loaded", 1.0)

    def populate_filters(self):
        for c, _ in [(self.emp_container, self.emp_checkboxes), (self.branch_container, self.branch_checkboxes), (self.shift_container, self.shift_checkboxes), (self.cat_container, self.cat_checkboxes), (self.mat_container, self.mat_checkboxes)]:
            for w in c.winfo_children(): w.destroy()
        self.emp_checkboxes.clear(); self.branch_checkboxes.clear(); self.shift_checkboxes.clear(); self.cat_checkboxes.clear(); self.mat_checkboxes.clear()

        def add_checks(col_name, container, dict_ref, default_list=None):
            if col_name and col_name in self.raw_df.columns:
                vals = default_list if default_list else sorted([str(x) for x in self.raw_df[col_name].dropna().unique()])
                for v in vals:
                    var = ctk.BooleanVar(value=True)
                    cb = ctk.CTkCheckBox(container, text=fix_arabic(v), variable=var, font=("Segoe UI", 12))
                    cb.pack(anchor="w", pady=4)
                    dict_ref[v] = var

        add_checks(self.c_name, self.emp_container, self.emp_checkboxes)
        add_checks(self.c_branch, self.branch_container, self.branch_checkboxes)
        add_checks('Shift_Name', self.shift_container, self.shift_checkboxes)
        add_checks(self.c_cat, self.cat_container, self.cat_checkboxes)
        
        if 'Item_Type' in self.raw_df.columns:
            requested_mats = ['Drugs', 'Cosmetics', 'Medical Accessories', 'Services']
            found_mats = [str(x) for x in self.raw_df['Item_Type'].dropna().unique()]
            combined = [m for m in requested_mats if m in found_mats] + [m for m in sorted(found_mats) if m not in requested_mats]
            for m in combined:
                var = ctk.BooleanVar(value=True)
                cb = ctk.CTkCheckBox(self.mat_container, text=fix_arabic(m), variable=var, font=("Segoe UI", 12))
                cb.pack(anchor="w", pady=4)
                self.mat_checkboxes[m] = var

    def apply_filters(self):
        if self.raw_df is None: return
        df = self.raw_df.copy()

        if 'Parsed_Date' in df.columns:
            s_date = pd.to_datetime(self.start_date_picker.get_date())
            e_date = pd.to_datetime(self.end_date_picker.get_date())
            df = df[(df['Parsed_Date'] >= s_date) & (df['Parsed_Date'] <= e_date)]
            
            self.period_info['start'] = s_date.strftime('%Y-%m-%d')
            self.period_info['end'] = e_date.strftime('%Y-%m-%d')
            calc_days = (e_date - s_date).days + 1
            self.period_info['days'] = calc_days if calc_days > 0 else 1

        self.lbl_date_range.configure(text=f"Showing Data For: {self.period_info['start']} to {self.period_info['end']} ({self.period_info['days']} Days)")

        def apply_check(col_name, dict_ref):
            nonlocal df
            if col_name and col_name in df.columns:
                selected = [k for k, v in dict_ref.items() if v.get()]
                df = df[df[col_name].astype(str).isin(selected)]

        apply_check(self.c_name, self.emp_checkboxes)
        apply_check(self.c_branch, self.branch_checkboxes)
        apply_check('Shift_Name', self.shift_checkboxes)
        apply_check(self.c_cat, self.cat_checkboxes)
        apply_check('Item_Type', self.mat_checkboxes)

        self.df = df
        self.on_mode_change()

    def get_receipts_series(self, df):
        if not self.c_rec: return df.groupby(self.c_name).size()
        if 'True_Receipt_ID' in df.columns: return df.groupby(self.c_name)['True_Receipt_ID'].nunique()
        group_keys = [self.c_name]
        if self.c_date: group_keys.append(self.c_date)
        if self.c_pos: group_keys.append(self.c_pos)
        if self.c_branch: group_keys.append(self.c_branch)
        group_keys.append(self.c_rec)
        return df.groupby(group_keys).size().groupby(level=0).size()

    def update_kpis_and_charts(self, *args):
        if self.df is None: return
        
        t_sales = self.df[self.c_price].sum()
        t_pcs = self.df[self.c_qty].sum()
        t_rec = self.df['True_Receipt_ID'].nunique() if (self.c_rec and 'True_Receipt_ID' in self.df.columns) else len(self.df)
        t_avg = t_sales / t_rec if t_rec > 0 else 0
        
        self.global_stats = {'Total Sales': t_sales, 'Total Receipts': t_rec, 'Total Pieces': t_pcs, 'Avg Receipt': t_avg}
        
        div = self.current_divisor
        suffix = " /day" if self.calc_mode.get() == "Daily Average" else ""
        
        self.kpi_sales.configure(text=f"{t_sales/div:,.0f}{suffix}")
        self.kpi_receipts.configure(text=f"{t_rec/div:,.1f}{suffix}" if div > 1 else f"{t_rec/div:,.0f}{suffix}")
        self.kpi_pcs.configure(text=f"{t_pcs/div:,.2f}{suffix}") 
        self.kpi_avg.configure(text=f"{t_avg:,.2f}") 
            
        self.draw_charts()

    def draw_charts(self):
        for w in self.charts_left.winfo_children(): w.destroy()
        for w in self.charts_right.winfo_children(): w.destroy()
        for w in self.adv_charts_frame.winfo_children(): w.destroy()
        
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg = "#2b2b2b" if is_dark else "#fcfcfc"
        text_col = "white" if is_dark else "black"
        
        div = self.current_divisor

        fig1 = Figure(figsize=(7, 4), dpi=100)
        fig1.patch.set_facecolor(bg)
        if 'Item_Type' in self.df.columns:
            ax1 = fig1.add_subplot(111, facecolor=bg)
            t_data = self.df.groupby('Item_Type')[self.c_price].sum().sort_values(ascending=False).head(5) / div
            
            ax1.bar([safe_label(fix_arabic(x)) for x in t_data.index], t_data.values, color=['#3498db', '#e74c3c', GREEN_PRIMARY, '#f1c40f'])
            title_suffix = " (Daily Avg)" if self.calc_mode.get() == "Daily Average" else ""
            ax1.set_title(f"Sales by Material Group{title_suffix}", color=text_col)
            ax1.tick_params(colors=text_col)
        fig1.tight_layout()
        FigureCanvasTkAgg(fig1, master=self.charts_left).get_tk_widget().pack(fill="both", expand=True)

        ctk.CTkLabel(self.charts_right, text="Top 10 Employees", font=("Segoe UI", 14, "bold")).pack(pady=5)
        tree_top10 = ttk.Treeview(self.charts_right, columns=("Name", "Branch", "Shift", "Top Type", "Sales"), show="headings", height=10)
        for c in ("Name", "Branch", "Shift", "Top Type", "Sales"):
            tree_top10.heading(c, text=c)
            if c == "Name": tree_top10.column(c, width=150, anchor="w")
            else: tree_top10.column(c, width=100, anchor="center")
        tree_top10.pack(fill="both", expand=True, padx=5, pady=5)
        
        if self.c_name:
            e_data = self.df.groupby(self.c_name)[self.c_price].sum().sort_values(ascending=False).head(10)
            for emp, val in e_data.items():
                emp_df = self.df[self.df[self.c_name] == emp]
                branch = emp_df[self.c_branch].mode()[0] if self.c_branch and not emp_df[self.c_branch].empty else "N/A"
                shift = emp_df['Shift_Name'].mode()[0] if 'Shift_Name' in emp_df.columns and not emp_df['Shift_Name'].empty else "N/A"
                top_cat = emp_df[self.c_cat].mode()[0] if self.c_cat and not emp_df[self.c_cat].empty else "N/A"
                tree_top10.insert("", "end", values=[fix_arabic(emp), fix_arabic(branch), fix_arabic(shift), fix_arabic(top_cat), f"{val/div:,.0f}"])

        fig2 = Figure(figsize=(14, 8), dpi=100)
        fig2.patch.set_facecolor(bg)
        
        if 'Sale_Hour' in self.df.columns:
            ax3 = fig2.add_subplot(221, facecolor=bg)
            h_data = self.df.groupby('Sale_Hour')[self.c_price].sum() / div
            ax3.bar(h_data.index, h_data.values, color=DARK_GREEN)
            ax3.set_title("Hourly Sales Breakdown", color=text_col)
            ax3.set_xticks(h_data.index)
            ax3.tick_params(colors=text_col)
        elif self.c_cat:
            ax3 = fig2.add_subplot(221, facecolor=bg)
            cat_data = self.df.groupby(self.c_cat)[self.c_price].sum()
            ax3.pie(cat_data.values, labels=[safe_label(fix_arabic(x)) for x in cat_data.index], autopct='%1.1f%%', textprops={'color': text_col})
            ax3.set_title("Sales by Category", color=text_col)

        if self.c_desc:
            ax4 = fig2.add_subplot(222, facecolor=bg)
            prod_data = self.df.groupby(self.c_desc)[self.c_qty].sum().sort_values(ascending=True).tail(10) / div
            ax4.barh([safe_label(fix_arabic(x)) for x in prod_data.index], prod_data.values, color=GREEN_PRIMARY)
            ax4.set_title("Top 10 Products by Qty", color=text_col)
            ax4.tick_params(colors=text_col, labelsize=8)

        if 'Shift_Name' in self.df.columns:
            ax5 = fig2.add_subplot(212, facecolor=bg)
            shift_data = self.df.groupby('Shift_Name')[self.c_price].sum() / div
            ax5.bar([safe_label(fix_arabic(x)) for x in shift_data.index], shift_data.values, color=['#9b59b6', '#34495e', '#e67e22'])
            ax5.set_title("Sales by Shift", color=text_col)
            ax5.tick_params(colors=text_col)

        fig2.tight_layout(); FigureCanvasTkAgg(fig2, master=self.adv_charts_frame).get_tk_widget().pack(fill="both", expand=True)

    def build_employee_views(self, *args):
        for item in self.tree_emp.get_children(): self.tree_emp.delete(item)
        if not self.c_name: return
        mode = self.emp_mode.get()
        
        if mode == "Subcategories Analysis":
            pwd_dialog = PasswordDialog(self)
            if not pwd_dialog.result:
                self.emp_mode.set("Performance Overview")
                return

        grp = self.df.groupby(self.c_name)
        emp_sales = grp[self.c_price].sum()
        items_sold = grp[self.c_qty].sum()
        emp_rec = self.get_receipts_series(self.df).reindex(emp_sales.index, fill_value=1).replace(0, 1)
        avg_rec = (emp_sales / emp_rec).round(2)
        items_per_rec = (items_sold / emp_rec).round(2)
        
        if 'Shift_Name' in self.df.columns: main_shift = self.df.groupby(self.c_name)['Shift_Name'].agg(lambda x: x.mode()[0] if not x.mode().empty else 'Unknown')
        else: main_shift = pd.Series('Unknown', index=emp_sales.index)

        self.current_emp_stats = pd.DataFrame({'Employee Name': emp_sales.index, 'Total Sales': emp_sales.values, 'Total Receipts': emp_rec.values, 'Avg Receipt': avg_rec.values})
        
        time_diff_series = pd.Series(index=emp_sales.index, data=0.0)
        if 'DateTime' in self.df.columns and 'True_Receipt_ID' in self.df.columns:
            sort_keys = [self.c_name]
            if self.c_pos: sort_keys.append(self.c_pos)
            sort_keys.append('DateTime')
            df_s = self.df.dropna(subset=['DateTime']).sort_values(by=sort_keys)
            r_times = df_s.groupby([self.c_name, 'True_Receipt_ID'])['DateTime'].min().reset_index().sort_values(by=[self.c_name, 'DateTime'])
            r_times['Diff'] = r_times.groupby(self.c_name)['DateTime'].diff().dt.total_seconds() / 60
            r_times.loc[r_times['Diff'] > 480, 'Diff'] = np.nan 
            time_diff_series = r_times.groupby(self.c_name)['Diff'].mean().fillna(0).round(1)

        total_sys_sales = emp_sales.sum()
        total_sys_recs = emp_rec.sum()
        total_sys_items = items_sold.sum()
        sys_avg_rec = total_sys_sales / total_sys_recs if total_sys_recs else 0
        sys_avg_mat = total_sys_items / total_sys_recs if total_sys_recs else 0

        div = self.current_divisor
        fmt_rec = lambda x: f"{x/div:,.1f}" if self.calc_mode.get() == "Daily Average" else f"{int(x):,.0f}"

        if mode == "Performance Overview":
            cols = ["Employee Name", "Position", "Main Shift", "Total Sales", "Total Receipts", "Avg Receipt Value", "Materials/Receipt"]
            self.setup_treeview(self.tree_emp, cols)
            for emp, row in emp_sales.items():
                pos = self.df[self.df[self.c_name] == emp]['Translated_Position'].iloc[0] if 'Translated_Position' in self.df.columns else "Unknown"
                vals = [fix_arabic(emp), pos, main_shift.get(emp, ''), f"{row/div:,.2f}", fmt_rec(emp_rec.get(emp, 0)), f"{avg_rec.get(emp, 0):,.2f}", f"{items_per_rec.get(emp, 0):,.2f}"]
                self.tree_emp.insert("", "end", values=vals)

        elif mode == "Sales Types Breakdown":
            cols = ["Employee Name", "Main Shift", "Total Receipts", "Total Sales", "Materials/Receipt"]
            if self.c_cat:
                cat_sales = self.df.groupby([self.c_name, self.c_cat])[self.c_price].sum().unstack(fill_value=0)
                sale_types = list(cat_sales.columns)
                cols += [f"{fix_arabic(c)} Sales" for c in sale_types]
            else:
                cat_sales, sale_types = pd.DataFrame(), []

            combined = pd.DataFrame({'Sales': emp_sales, 'Recs': emp_rec, 'MatPerRec': items_per_rec, 'Shift': main_shift}).join(cat_sales).sort_values('Sales', ascending=False)
            self.setup_treeview(self.tree_emp, cols)
            
            for emp, row in combined.iterrows():
                vals = [fix_arabic(emp), row['Shift'], fmt_rec(row['Recs']), f"{row['Sales']/div:,.2f}", f"{row['MatPerRec']:,.2f}"]
                vals += [f"{row[c]/div:,.2f}" for c in sale_types]
                self.tree_emp.insert("", "end", values=vals)

        elif mode == "Subcategories Analysis":
            cols = ["Employee Name", "SubCategory 1", "SubCategory 2", "Total Sales", "Sales %", "Total Materials", "Unique Receipts"]
            self.setup_treeview(self.tree_emp, cols)
            temp_df = self.df.copy()
            conn = sqlite3.connect("lotus_local.db")
            master_df = pd.read_sql_query("SELECT Description, SubCat1, SubCat2 FROM master_items", conn)
            conn.close()
            
            if not master_df.empty and self.c_desc:
                master_df['Description'] = master_df['Description'].astype(str).str.strip()
                temp_df[self.c_desc] = temp_df[self.c_desc].astype(str).str.strip()
                temp_df = temp_df.merge(master_df, left_on=self.c_desc, right_on='Description', how='left')
                temp_df['SubCat1'] = temp_df['SubCat1'].fillna('Uncategorized')
                temp_df['SubCat2'] = temp_df['SubCat2'].fillna('Uncategorized')
            else:
                temp_df['SubCat1'] = temp_df['Item_Type'] if 'Item_Type' in temp_df.columns else 'Uncategorized'
                temp_df['SubCat2'] = 'N/A'

            sub_grp = temp_df.groupby([self.c_name, 'SubCat1', 'SubCat2']).agg({self.c_price: 'sum', self.c_qty: 'sum', 'True_Receipt_ID': 'nunique'}).reset_index()
            sub_grp = sub_grp[sub_grp[self.c_price] > 0].sort_values(by=[self.c_name, self.c_price], ascending=[True, False])
            
            for _, row in sub_grp.iterrows():
                e_tot = emp_sales.get(row[self.c_name], 1)
                pct = (row[self.c_price] / e_tot * 100) if e_tot > 0 else 0
                qty_str = f"{row[self.c_qty]/div:,.1f}" if self.calc_mode.get() == "Daily Average" else f"{row[self.c_qty]:,.0f}"
                self.tree_emp.insert("", "end", values=[fix_arabic(row[self.c_name]), fix_arabic(row['SubCat1']), fix_arabic(row['SubCat2']), f"{row[self.c_price]/div:,.2f}", f"{pct:.1f} %", qty_str, fmt_rec(row['True_Receipt_ID'])])

        elif mode == "Efficiency & Time":
            cols = ["Employee Name", "Main Shift", "Total Receipts", "Avg Receipt Value", "Materials/Receipt", "Total Materials Sold", "Avg Mins Between Receipts"]
            combined = pd.DataFrame({'Recs': emp_rec, 'Avg': avg_rec, 'MatPerRec': items_per_rec, 'Items': items_sold, 'Time': time_diff_series, 'Shift': main_shift}).sort_values('Recs', ascending=False)
            self.setup_treeview(self.tree_emp, cols)
            avg_time_global = time_diff_series[time_diff_series > 0].mean() if not time_diff_series.empty else 0
            
            for emp, row in combined.iterrows():
                time_str = f"{row['Time']} mins" if row['Time'] > 0 else "N/A"
                self.tree_emp.insert("", "end", values=[fix_arabic(emp), row['Shift'], fmt_rec(row['Recs']), f"{row['Avg']:,.2f}", f"{row['MatPerRec']:,.2f}", f"{row['Items']/div:,.2f}", time_str])
            
            time_tot_str = f"{avg_time_global:.1f} mins" if avg_time_global > 0 else "N/A"
            self.tree_emp.insert("", "end", values=["📊 SUBTOTAL / AVG", "---", fmt_rec(emp_rec.sum()), f"{sys_avg_rec:,.2f}", f"{sys_avg_mat:,.2f}", f"{items_sold.sum()/div:,.2f}", time_tot_str], tags=('subtotal',))

        elif mode == "AI Recommendations":
            cols = ["Employee Name", "Main Shift", "Performance Tier", "Materials/Rec", "AI Actionable Recommendation"]
            self.setup_treeview(self.tree_emp, cols)
            
            avg_global = avg_rec.mean() if not avg_rec.empty else 0
            time_global = time_diff_series[time_diff_series > 0].mean() if not time_diff_series.empty else 0
            has_cats = False
            if self.c_cat:
                cat_sales = self.df.groupby([self.c_name, self.c_cat])[self.c_price].sum().unstack(fill_value=0)
                has_cats = True
            else: cat_sales = pd.DataFrame()

            combined = pd.DataFrame({'Sales': emp_sales, 'Avg': avg_rec, 'Time': time_diff_series, 'MatPerRec': items_per_rec, 'Shift': main_shift}).sort_values('Sales', ascending=False)
            
            for i, (emp, row) in enumerate(combined.iterrows()):
                tier = "Star Performer" if i < 3 else ("Solid Contributor" if i < len(combined)/2 else "Needs Improvement")
                emp_avg, emp_speed, emp_mat_rec, emp_shift = row['Avg'], row['Time'], row['MatPerRec'], row['Shift']
                
                recs = []
                if emp_avg >= avg_global * 1.1: recs.append("Excellent basket value (Upselling effective).")
                elif emp_avg < avg_global * 0.8: recs.append("Low avg receipt. Needs coaching on cross-selling.")
                if emp_mat_rec < 1.5: recs.append("Low Materials/receipt. Suggest related items.")
                elif emp_mat_rec > sys_avg_mat * 1.2: recs.append("Great at multi-item sales.")
                if emp_shift == "Night Shift" and emp_speed > time_global * 1.5: recs.append("High idle time on Night Shift.")
                elif emp_speed > 0 and emp_speed > time_global * 1.3: recs.append("Processing is slow between receipts.")
                if has_cats and emp in cat_sales.index:
                    e_cats_lower = {str(k).lower(): v for k, v in cat_sales.loc[emp].items()}
                    cash_sales = sum(v for k, v in e_cats_lower.items() if 'cash' in k or 'نقدي' in k)
                    digital_sales = sum(v for k, v in e_cats_lower.items() if 'digital' in k or 'visa' in k or 'فيزا' in k)
                    if digital_sales == 0 and cash_sales > 0: recs.append("Zero Digital/Visa sales.")

                if not recs: recs.append("Steady performance. Maintain consistent numbers.")
                self.tree_emp.insert("", "end", values=[fix_arabic(emp), emp_shift, tier, f"{emp_mat_rec:,.2f}", " | ".join(recs)])

        auto_fit_columns(self.tree_emp)

    def build_products_table(self):
        for item in self.tree_prod.get_children(): self.tree_prod.delete(item)
        if not self.c_desc: return
        grp_cols = [self.c_desc]
        if self.c_item_code: grp_cols.insert(0, self.c_item_code)
        if self.c_cat: grp_cols.append(self.c_cat)
        if 'Item_Type' in self.df.columns: grp_cols.append('Item_Type')
        
        prod_grp = self.df.groupby(grp_cols).agg({self.c_qty: 'sum', self.c_price: 'sum'}).reset_index()
        prod_grp = prod_grp.sort_values(self.c_qty, ascending=False).head(150) 
        
        cols = ["Item Code", "Product Description", "Category", "Material Group", "Total Qty", "Total Sales Value"] if self.c_item_code else ["Product Description", "Category", "Material Group", "Total Qty", "Total Sales Value"]
        self.setup_treeview(self.tree_prod, cols)
            
        div = self.current_divisor
        for _, row in prod_grp.iterrows():
            c_val = fix_arabic(row[self.c_cat]) if self.c_cat else "N/A"
            m_val = fix_arabic(row['Item_Type']) if 'Item_Type' in row else "N/A"
            qty_str = f"{row[self.c_qty]/div:,.2f}"
            price_str = f"{row[self.c_price]/div:,.2f}"
            if self.c_item_code:
                vals = [clean_item_code(row[self.c_item_code]), fix_arabic(row[self.c_desc]), c_val, m_val, qty_str, price_str]
            else:
                vals = [fix_arabic(row[self.c_desc]), c_val, m_val, qty_str, price_str]
            self.tree_prod.insert("", "end", values=vals)
            
        auto_fit_columns(self.tree_prod)

    def analyze_stagnant(self):
        if self.df is None: return messagebox.showwarning("Warning", "Load sales data first.")
        for item in self.tree_stag.get_children(): self.tree_stag.delete(item)
        conn = sqlite3.connect("lotus_local.db")
        master_df = pd.read_sql_query("SELECT * FROM master_items", conn)
        conn.close()
        if master_df.empty: return messagebox.showwarning("No Master Data", "Upload encrypted master data first.")
        
        cols = ["Stagnant Code", "Stagnant Drug", "Alternative Code", "Top Selling Alternative", "Alternative Sold Qty", "Group Match"]
        self.setup_treeview(self.tree_stag, cols)

        sales_grp = self.df.groupby(self.c_desc)[self.c_qty].sum().reset_index()
        sales_grp.columns = ['Description', 'Qty_Sold']
        merged = pd.merge(master_df, sales_grp, on='Description', how='left')
        merged['Qty_Sold'] = merged['Qty_Sold'].fillna(0)
        
        for (cat1, cat2, granular), group in merged.groupby(['SubCat1', 'SubCat2', 'GranularCat']):
            if str(granular).strip().lower() in ["", "nan", "none", "general", "other"]: continue
            
            top_seller = group.sort_values(by='Qty_Sold', ascending=False).iloc[0]
            if top_seller['Qty_Sold'] <= 2: continue 
            
            stagnant_items = group[group['Qty_Sold'] == 0]
            for _, row in stagnant_items.iterrows():
                vals = [
                    clean_item_code(row['Material']), 
                    fix_arabic(row['Description']), 
                    clean_item_code(top_seller['Material']), 
                    fix_arabic(top_seller['Description']), 
                    f"{top_seller['Qty_Sold']:.0f}",
                    fix_arabic(f"{cat1} -> {granular}")
                ]
                self.tree_stag.insert("", "end", values=vals)
                
        auto_fit_columns(self.tree_stag)

    def setup_treeview(self, tv, columns, main_col=None, main_width=300):
        tv["columns"] = columns; tv["show"] = "headings"
        for c in columns:
            tv.heading(c, text=c, command=lambda _c=c: treeview_sort_column(tv, _c, False))
            tv.column(c, anchor="center") 
            
        self.add_export_context_menu(tv, columns[0] if columns else "Data")

    def export_treeview_to_excel(self, tree, sheet_name="Data"):
        if not tree.get_children(): return messagebox.showwarning("No Data", "Table is empty.")
        cols = tree["columns"]; data = [tree.item(item)["values"] for item in tree.get_children()]
        df_export = pd.DataFrame(data, columns=cols)
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"{sheet_name}_{datetime.now().strftime('%Y%m%d')}.xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if file_path:
            pwd = simpledialog.askstring("Password Protection", "Enter password (Leave blank for no password):", show='*')
            try:
                df_export.to_excel(file_path, index=False, sheet_name=sheet_name)
                if pwd: 
                    excel = win32.Dispatch("Excel.Application"); excel.DisplayAlerts = False
                    abs_path = os.path.abspath(file_path); wb = excel.Workbooks.Open(abs_path)
                    wb.SaveAs(abs_path, Password=pwd); wb.Close(); excel.Quit()
                messagebox.showinfo("Success", "Data exported successfully!")
            except Exception as e: messagebox.showerror("Export Error", f"Failed:\n{e}")

    def export_snapshot(self):
        if self.current_emp_stats is None: return
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"Snapshot_{datetime.now().strftime('%Y%m%d')}.xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if file_path:
            meta_df = pd.DataFrame([{
                'Branch': str(self.branch_name),
                'Start Date': self.period_info.get('start', 'N/A'),
                'End Date': self.period_info.get('end', 'N/A'),
                'Days Count': self.period_info.get('days', 1),
                'Global Sales': self.global_stats.get('Total Sales', 0), 
                'Global Receipts': self.global_stats.get('Total Receipts', 0), 
                'Global Avg Receipt': self.global_stats.get('Avg Receipt', 0),
                'Global Pcs': self.global_stats.get('Total Pieces', 0)
            }])
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                meta_df.to_excel(writer, sheet_name='Global_Metadata', index=False)
                self.current_emp_stats.to_excel(writer, sheet_name='Employees_Data', index=False)
            messagebox.showinfo("Success", "Snapshot exported!")

    def load_snapshot(self):
        if self.current_emp_stats is None: return messagebox.showwarning("Data Needed", "Load CURRENT data first.")
        file_path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if not file_path: return
        try:
            history_emp_df = pd.read_excel(file_path, sheet_name='Employees_Data')
            history_meta_df = pd.read_excel(file_path, sheet_name='Global_Metadata')
            self.compare_and_render(history_emp_df, history_meta_df)
        except Exception as e: messagebox.showerror("Error Loading", str(e))

    def compare_and_render(self, history_emp, history_meta):
        for item in self.tree_comp.get_children(): self.tree_comp.delete(item)
        for w in self.global_comp_frame.winfo_children(): w.destroy()
        
        prev_meta = history_meta.iloc[0]
        curr_sales, p_sales = self.global_stats.get('Total Sales', 0), float(prev_meta['Global Sales'])
        curr_recs, p_recs = self.global_stats.get('Total Receipts', 0), float(prev_meta['Global Receipts'])
        curr_avg, p_avg = self.global_stats.get('Avg Receipt', 0), float(prev_meta['Global Avg Receipt'])
        curr_pcs, p_pcs = self.global_stats.get('Total Pieces', 0), float(prev_meta.get('Global Pcs', 0))
        
        header_frame = ctk.CTkFrame(self.global_comp_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(15, 10))
        
        start_prev = str(prev_meta.get('Start Date', 'N/A'))[:10]
        end_prev = str(prev_meta.get('End Date', 'N/A'))[:10]
        start_curr = str(self.period_info.get('start', 'N/A'))[:10]
        end_curr = str(self.period_info.get('end', 'N/A'))[:10]

        header_text = f"🔄 Comparison: History ({prev_meta.get('Days Count', 'N/A')} days: {start_prev} to {end_prev}) VS Current ({self.period_info.get('days', 'N/A')} days: {start_curr} to {end_curr})"
        ctk.CTkLabel(header_frame, text=header_text, font=("Segoe UI", 14, "bold"), text_color="#3498db").pack(side="top")
        
        kpi_row = ctk.CTkFrame(self.global_comp_frame, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 15), padx=20)
        
        def make_stat_box(parent, title, old_v, new_v, pct):
            box = ctk.CTkFrame(parent, border_color="#bdc3c7", border_width=1)
            box.pack(side="left", fill="x", expand=True, padx=5)
            ctk.CTkLabel(box, text=title, font=("Segoe UI", 12, "bold"), text_color="gray").pack(pady=(5,0))
            ctk.CTkLabel(box, text=f"Old: {old_v:,.0f} | New: {new_v:,.0f}", font=("Segoe UI", 14)).pack(pady=2)
            color = "#2ecc71" if pct > 0 else ("#e74c3c" if pct < 0 else "gray")
            sign = "+" if pct > 0 else ""
            ctk.CTkLabel(box, text=f"{sign}{pct:.1f}%", font=("Segoe UI", 16, "bold"), text_color=color).pack(pady=(0,5))
            
        sales_chg = ((curr_sales - p_sales)/p_sales * 100) if p_sales else 0
        recs_chg = ((curr_recs - p_recs)/p_recs * 100) if p_recs else 0
        avg_chg = ((curr_avg - p_avg)/p_avg * 100) if p_avg else 0
        pcs_chg = ((curr_pcs - p_pcs)/p_pcs * 100) if p_pcs else 0
        
        make_stat_box(kpi_row, "Total Sales", p_sales, curr_sales, sales_chg)
        make_stat_box(kpi_row, "Total Receipts", p_recs, curr_recs, recs_chg)
        make_stat_box(kpi_row, "Average Receipt", p_avg, curr_avg, avg_chg)
        make_stat_box(kpi_row, "Total Pieces Sold", p_pcs, curr_pcs, pcs_chg)

        cols = ["Employee Name", "Prev Sales", "Curr Sales", "Sales \u0394 %", "Prev Recs", "Curr Recs", "Prev Avg", "Curr Avg", "Avg \u0394 %", "AI Trend Insight"]
        self.setup_treeview(self.tree_comp, cols)
        
        merged = pd.merge(history_emp, self.current_emp_stats, on='Employee Name', how='inner', suffixes=('_prev', '_curr'))
        for _, row in merged.iterrows():
            emp = row['Employee Name']
            s_prev, s_curr = float(row['Total Sales_prev']), float(row['Total Sales_curr'])
            r_prev, r_curr = float(row.get('Total Receipts_prev', 0)), float(row.get('Total Receipts_curr', 0))
            a_prev, a_curr = float(row['Avg Receipt_prev']), float(row['Avg Receipt_curr'])
            
            sales_pct = ((s_curr - s_prev) / s_prev * 100) if s_prev > 0 else 0
            avg_pct = ((a_curr - a_prev) / a_prev * 100) if a_prev > 0 else 0
            
            insight = ""
            if sales_pct > 10 and avg_pct > 5: insight = "🟢 Outstanding Growth: Both volume and basket size improved."
            elif sales_pct > 5 and avg_pct <= 0: insight = "🟡 Volume Driven: Sales went up, but average receipt dropped."
            elif sales_pct < -5 and avg_pct > 5: insight = "🟡 Quality over Quantity: Lost some traffic but maximized value per patient."
            elif sales_pct < -10 and avg_pct < -5: insight = "🔴 Critical Decline: Both sales and basket size dropped significantly."
            else: insight = "⚪ Stable Performance."

            self.tree_comp.insert("", "end", values=[
                fix_arabic(emp), f"{s_prev:,.0f}", f"{s_curr:,.0f}", f"{sales_pct:.1f}%", 
                f"{r_prev:,.0f}", f"{r_curr:,.0f}",
                f"{a_prev:,.0f}", f"{a_curr:,.0f}", f"{avg_pct:.1f}%", insight
            ])

        auto_fit_columns(self.tree_comp)

if __name__ == "__main__":
    init_local_db()
    conn = sqlite3.connect("lotus_local.db")
    cursor = conn.cursor()
    cursor.execute("SELECT activation_key FROM app_license")
    row = cursor.fetchone()
    conn.close()
    
    mac = get_mac_address()
    expected_key = hashlib.sha256(f"{mac}_{SECRET_SALT}".encode()).hexdigest()[:16].upper()
    
    if row and row[0] == expected_key:
        splash = SplashScreen()
        splash.mainloop()
        
        app = DashboardWindow()
        app.mainloop()
    else:
        app = ActivationWindow()
        app.mainloop()