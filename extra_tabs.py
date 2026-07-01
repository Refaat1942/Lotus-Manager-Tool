# extra_tabs.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from utils import fix_arabic, treeview_sort_column, auto_fit_columns

GREEN_PRIMARY = "#27ae60"

def setup_executive_summary_tab(parent, app):
    for w in parent.winfo_children(): w.destroy()
    if app.df is None or app.df.empty:
        ctk.CTkLabel(parent, text="Please load data first.").pack(pady=20)
        return

    brief_frame = ctk.CTkFrame(parent, border_width=1, border_color="#3498db")
    brief_frame.pack(fill="x", pady=(10, 5), padx=20)
    
    ctk.CTkLabel(brief_frame, text="Branch Activity Brief", font=("Segoe UI", 16, "bold"), text_color="#3498db").pack(anchor="w", padx=10, pady=(5,0))
    
    best_shift = "N/A"
    peak_hours = []
    
    if 'Shift_Name' in app.df.columns:
        try: best_shift = app.df.groupby('Shift_Name')[app.c_price].sum().idxmax()
        except: pass
        
    if 'Sale_Hour' in app.df.columns:
        try: 
            top_hours = app.df.groupby('Sale_Hour')[app.c_price].sum().nlargest(2).index.tolist()
            peak_hours = [f"{int(h):02d}:00 to {int(h)+1:02d}:00" for h in top_hours]
        except: pass
        
    val_peaks = ' & '.join(peak_hours) if peak_hours else 'N/A'
    
    brief_text = f"⭐ Top Shift: {best_shift}\n🔥 Peak Hours: {val_peaks}"
    ctk.CTkLabel(brief_frame, text=brief_text, font=("Segoe UI", 14), justify="left").pack(anchor="w", padx=10, pady=(5, 10))

    f1 = ctk.CTkFrame(parent, fg_color="transparent")
    f1.pack(fill="x", pady=5, padx=20)
    
    ctk.CTkLabel(f1, text="Shifts Performance by Branch", font=("Segoe UI", 14, "bold")).pack(anchor="w")

    tree_shift = ttk.Treeview(f1, columns=("Branch", "Shift", "Sales", "Receipts", "AvgRec"), show="headings", height=5)
    tree_shift.heading("Branch", text="Branch Name", command=lambda: treeview_sort_column(tree_shift, "Branch", False))
    tree_shift.heading("Shift", text="Shift Name", command=lambda: treeview_sort_column(tree_shift, "Shift", False))
    tree_shift.heading("Sales", text="Total Sales", command=lambda: treeview_sort_column(tree_shift, "Sales", False))
    tree_shift.heading("Receipts", text="Total Receipts", command=lambda: treeview_sort_column(tree_shift, "Receipts", False))
    tree_shift.heading("AvgRec", text="Average Receipt", command=lambda: treeview_sort_column(tree_shift, "AvgRec", False))
    
    scroll_s = ttk.Scrollbar(f1, orient="vertical", command=tree_shift.yview)
    tree_shift.configure(yscrollcommand=scroll_s.set)
    scroll_s.pack(side="right", fill="y")
    tree_shift.pack(fill="x", pady=2)

    if hasattr(app, 'add_export_context_menu'):
        app.add_export_context_menu(tree_shift, "Shifts_Performance")

    rec_col = 'True_Receipt_ID' if 'True_Receipt_ID' in app.df.columns else app.c_rec
    div = app.current_divisor
    fmt_rec = lambda x: f"{x/div:,.1f}" if app.calc_mode.get() == "Daily Average" else f"{int(x):,.0f}"

    if 'Shift_Name' in app.df.columns:
        if app.c_branch in app.df.columns:
            shift_grp = app.df.groupby([app.c_branch, 'Shift_Name']).agg({app.c_price: 'sum', rec_col: 'nunique'}).reset_index()
            shift_grp = shift_grp.sort_values(by=[app.c_branch, app.c_price], ascending=[True, False])
            
            for _, row in shift_grp.iterrows():
                recs = row[rec_col] if row[rec_col] > 0 else 1
                avg = row[app.c_price] / recs
                tree_shift.insert("", "end", values=[fix_arabic(row[app.c_branch]), fix_arabic(row['Shift_Name']), f"{row[app.c_price]/div:,.2f}", fmt_rec(row[rec_col]), f"{avg:,.2f}"])
        else:
            shift_grp = app.df.groupby('Shift_Name').agg({app.c_price: 'sum', rec_col: 'nunique'}).sort_values(by=app.c_price, ascending=False)
            for shift, row in shift_grp.iterrows():
                recs = row[rec_col] if row[rec_col] > 0 else 1
                avg = row[app.c_price] / recs
                tree_shift.insert("", "end", values=["N/A", fix_arabic(shift), f"{row[app.c_price]/div:,.2f}", fmt_rec(row[rec_col]), f"{avg:,.2f}"])
                
    auto_fit_columns(tree_shift)

    f2 = ctk.CTkFrame(parent, fg_color="transparent")
    f2.pack(fill="both", expand=True, pady=(5, 10), padx=20)
    
    ctk.CTkLabel(f2, text="Smart Pharmacists Evaluation", font=("Segoe UI", 14, "bold"), text_color="#e74c3c").pack(anchor="w")

    cols = ("Name", "Branch", "Shift", "Sales", "Receipts", "AvgRec", "Top Sales Type", "Top Category", "Eval")
    tree_phar = ttk.Treeview(f2, columns=cols, show="headings")
    tree_phar.heading("Name", text="Pharmacist Name", command=lambda: treeview_sort_column(tree_phar, "Name", False))
    tree_phar.heading("Branch", text="Branch", command=lambda: treeview_sort_column(tree_phar, "Branch", False))
    tree_phar.heading("Shift", text="Main Shift", command=lambda: treeview_sort_column(tree_phar, "Shift", False))
    tree_phar.heading("Sales", text="Total Sales", command=lambda: treeview_sort_column(tree_phar, "Sales", False))
    tree_phar.heading("Receipts", text="Receipts", command=lambda: treeview_sort_column(tree_phar, "Receipts", False))
    tree_phar.heading("AvgRec", text="Avg Receipt", command=lambda: treeview_sort_column(tree_phar, "AvgRec", False))
    tree_phar.heading("Top Sales Type", text="Top Sales Type", command=lambda: treeview_sort_column(tree_phar, "Top Sales Type", False))
    tree_phar.heading("Top Category", text="Top Category", command=lambda: treeview_sort_column(tree_phar, "Top Category", False))
    tree_phar.heading("Eval", text="AI Evaluation", command=lambda: treeview_sort_column(tree_phar, "Eval", False))
    
    scroll_y = ttk.Scrollbar(f2, orient="vertical", command=tree_phar.yview)
    scroll_x = ttk.Scrollbar(f2, orient="horizontal", command=tree_phar.xview)
    tree_phar.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    tree_phar.pack(fill="both", expand=True, pady=2)

    if hasattr(app, 'add_export_context_menu'):
        app.add_export_context_menu(tree_phar, "Pharmacists_Evaluation")

    emp_grp = app.df.groupby(app.c_name).agg({app.c_price: 'sum', rec_col: 'nunique'})
    emp_grp['AvgRec'] = emp_grp[app.c_price] / emp_grp[rec_col].replace(0, 1)
    emp_grp = emp_grp.sort_values(by=app.c_price, ascending=False)
    
    mean_sales = emp_grp[app.c_price].mean()
    mean_avg_rec = emp_grp['AvgRec'].mean()
    
    def get_top_col(df, group_col, target_col, value_col):
        if target_col not in df.columns: return pd.Series("N/A", index=df[group_col].unique())
        return df.groupby([group_col, target_col])[value_col].sum().reset_index().sort_values(value_col, ascending=False).drop_duplicates(group_col).set_index(group_col)[target_col]

    top_sales_type = get_top_col(app.df, app.c_name, app.c_cat, app.c_price) if app.c_cat else pd.Series("N/A", index=emp_grp.index)
    top_item_type = get_top_col(app.df, app.c_name, 'Item_Type', app.c_price) if 'Item_Type' in app.df.columns else pd.Series("N/A", index=emp_grp.index)
    emp_branch = app.df.groupby(app.c_name)[app.c_branch].agg(lambda x: x.mode()[0] if not x.mode().empty else 'Unknown') if app.c_branch in app.df.columns else pd.Series("Unknown", index=emp_grp.index)
    emp_shift = app.df.groupby(app.c_name)['Shift_Name'].agg(lambda x: x.mode()[0] if not x.mode().empty else 'Unknown') if 'Shift_Name' in app.df.columns else pd.Series("Unknown", index=emp_grp.index)

    for emp, row in emp_grp.iterrows():
        s = row[app.c_price]
        r = row[rec_col]
        a = row['AvgRec']
        
        if s >= mean_sales and a >= mean_avg_rec: ev = "⭐ Excellent: High Volume & High Basket"
        elif s >= mean_sales and a < mean_avg_rec: ev = "📈 Volume Driven: Needs Cross-selling"
        elif s < mean_sales and a >= mean_avg_rec: ev = "🎯 Quality over Qty: Good Upselling"
        else: ev = "⚠️ Needs Training: Low Volume & Low Basket"
        
        b_val = emp_branch.get(emp, "Unknown")
        sh_val = emp_shift.get(emp, "Unknown")
        tc_val = top_sales_type.get(emp, "N/A")
        ti_val = top_item_type.get(emp, "N/A")
            
        tree_phar.insert("", "end", values=[fix_arabic(emp), fix_arabic(b_val), fix_arabic(sh_val), f"{s/div:,.2f}", fmt_rec(r), f"{a:,.2f}", fix_arabic(tc_val), fix_arabic(ti_val), ev])

    auto_fit_columns(tree_phar)

def setup_custom_compare_tab(parent, app):
    for w in parent.winfo_children(): w.destroy()
    if app.df is None or app.df.empty:
        ctk.CTkLabel(parent, text="Please load data first.").pack(pady=20)
        return
        
    if not app.c_date or app.c_date not in app.df.columns:
        ctk.CTkLabel(parent, text="No Date column found in the loaded data.").pack(pady=20)
        return

    dates_series = pd.to_datetime(app.raw_df[app.c_date], errors='coerce').dropna().dt.strftime('%Y-%m-%d')
    valid_dates = sorted(dates_series.unique().tolist())
    
    if not valid_dates:
        ctk.CTkLabel(parent, text="No valid dates found.").pack()
        return

    top_frame = ctk.CTkFrame(parent, fg_color="transparent")
    top_frame.pack(fill="x", pady=10, padx=20)
    
    f_p1 = ctk.CTkFrame(top_frame)
    f_p1.pack(side="left", padx=10, fill="x", expand=True)
    ctk.CTkLabel(f_p1, text="Period 1", font=("Segoe UI", 12, "bold")).pack(pady=5)
    cb_start1 = ctk.CTkComboBox(f_p1, values=valid_dates)
    cb_start1.set(valid_dates[0])
    cb_start1.pack(padx=10, pady=5, side="left")
    cb_end1 = ctk.CTkComboBox(f_p1, values=valid_dates)
    cb_end1.set(valid_dates[min(len(valid_dates)-1, 6)]) 
    cb_end1.pack(padx=10, pady=5, side="right")

    f_p2 = ctk.CTkFrame(top_frame)
    f_p2.pack(side="left", padx=10, fill="x", expand=True)
    ctk.CTkLabel(f_p2, text="Period 2", font=("Segoe UI", 12, "bold")).pack(pady=5)
    cb_start2 = ctk.CTkComboBox(f_p2, values=valid_dates)
    cb_start2.set(valid_dates[min(len(valid_dates)-1, 7)])
    cb_start2.pack(padx=10, pady=5, side="left")
    cb_end2 = ctk.CTkComboBox(f_p2, values=valid_dates)
    cb_end2.set(valid_dates[-1])
    cb_end2.pack(padx=10, pady=5, side="right")

    f_opt = ctk.CTkFrame(top_frame, fg_color="transparent")
    f_opt.pack(side="left", padx=10)
    ctk.CTkLabel(f_opt, text="Compare By:", font=("Segoe UI", 12, "bold")).pack()
    cb_groupby = ctk.CTkComboBox(f_opt, values=["Totals", "Hourly"])
    cb_groupby.set("Hourly") 
    cb_groupby.pack(pady=5)

    view_frame = ctk.CTkFrame(parent, fg_color="transparent")
    view_frame.pack(fill="both", expand=True, pady=5, padx=20)

    def do_compare():
        for w in view_frame.winfo_children(): w.destroy()
        
        s1, e1 = cb_start1.get(), cb_end1.get()
        s2, e2 = cb_start2.get(), cb_end2.get()
        
        df = app.df.copy()
        df['Temp_Date'] = pd.to_datetime(df[app.c_date], errors='coerce').dt.strftime('%Y-%m-%d')
        
        df1 = df[(df['Temp_Date'] >= s1) & (df['Temp_Date'] <= e1)]
        df2 = df[(df['Temp_Date'] >= s2) & (df['Temp_Date'] <= e2)]
        
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg = "#2b2b2b" if is_dark else "white"
        text_col = "white" if is_dark else "black"
        
        mode = cb_groupby.get()
        is_avg = app.calc_mode.get() == "Daily Average"
        
        d1 = max(1, (pd.to_datetime(e1) - pd.to_datetime(s1)).days + 1) if is_avg else 1
        d2 = max(1, (pd.to_datetime(e2) - pd.to_datetime(s2)).days + 1) if is_avg else 1
        
        if "Totals" in mode:
            chart_container = ctk.CTkFrame(view_frame, fg_color="transparent")
            chart_container.pack(fill="both", expand=True)
            
            fig = Figure(figsize=(10, 4), dpi=100)
            fig.patch.set_facecolor(bg)
            
            sales1, sales2 = df1[app.c_price].sum() / d1, df2[app.c_price].sum() / d2
            rec_col = 'True_Receipt_ID' if 'True_Receipt_ID' in df.columns else app.c_rec
            rec1 = (df1[rec_col].nunique() if not df1.empty else 0) / d1
            rec2 = (df2[rec_col].nunique() if not df2.empty else 0) / d2
            
            title_suffix = " (Daily Avg)" if is_avg else " (Totals)"
            
            ax1 = fig.add_subplot(121, facecolor=bg)
            bars1 = ax1.bar([f"P1\n({s1})", f"P2\n({s2})"], [sales1, sales2], color=['gray', GREEN_PRIMARY], width=0.5)
            ax1.set_title(f"Sales Comparison{title_suffix}", color=text_col)
            ax1.tick_params(colors=text_col)
            ax1.bar_label(bars1, fmt='{:,.0f}', padding=3, color=text_col)

            ax2 = fig.add_subplot(122, facecolor=bg)
            bars2 = ax2.bar([f"P1\n({s1})", f"P2\n({s2})"], [rec1, rec2], color=['gray', '#f1c40f'], width=0.5)
            ax2.set_title(f"Receipts Comparison{title_suffix}", color=text_col)
            ax2.tick_params(colors=text_col)
            ax2.bar_label(bars2, fmt='{:,.0f}', padding=3, color=text_col)
            
            fig.tight_layout()
            FigureCanvasTkAgg(fig, master=chart_container).get_tk_widget().pack(fill="both", expand=True)

        elif "Hourly" in mode:
            if 'Sale_Hour' not in df.columns:
                ctk.CTkLabel(view_frame, text="Hourly data not available in dataset.").pack()
                return
                
            chart_container = ctk.CTkFrame(view_frame, fg_color="transparent", height=300)
            chart_container.pack(fill="both", expand=True, pady=(0, 5))
            
            table_container = ctk.CTkFrame(view_frame)
            table_container.pack(fill="both", expand=True)
            
            fig = Figure(figsize=(10, 3), dpi=100)
            fig.patch.set_facecolor(bg)
            ax = fig.add_subplot(111, facecolor=bg)
            
            h1 = (df1.groupby('Sale_Hour')[app.c_price].sum().reindex(range(24), fill_value=0)) / d1
            h2 = (df2.groupby('Sale_Hour')[app.c_price].sum().reindex(range(24), fill_value=0)) / d2
            
            x = np.arange(24)
            width = 0.35
            
            ax.bar(x - width/2, h1.values, width, label=f'Period 1', color='gray')
            ax.bar(x + width/2, h2.values, width, label=f'Period 2', color=GREEN_PRIMARY)
            
            title_suffix = " (Daily Avg)" if is_avg else ""
            ax.set_title(f"Hourly Sales Comparison{title_suffix}", color=text_col)
            ax.set_xticks(x)
            ax.tick_params(colors=text_col)
            ax.legend()
            
            fig.tight_layout()
            FigureCanvasTkAgg(fig, master=chart_container).get_tk_widget().pack(fill="both", expand=True)
            
            tree_hourly = ttk.Treeview(table_container, columns=("Hour", "P1_Sales", "P2_Sales", "Diff"), show="headings")
            tree_hourly.heading("Hour", text="Hour", command=lambda: treeview_sort_column(tree_hourly, "Hour", False))
            tree_hourly.heading("P1_Sales", text="Period 1 Sales", command=lambda: treeview_sort_column(tree_hourly, "P1_Sales", False))
            tree_hourly.heading("P2_Sales", text="Period 2 Sales", command=lambda: treeview_sort_column(tree_hourly, "P2_Sales", False))
            tree_hourly.heading("Diff", text="Variance Δ %", command=lambda: treeview_sort_column(tree_hourly, "Diff", False))
            
            scroll_y = ttk.Scrollbar(table_container, orient="vertical", command=tree_hourly.yview)
            tree_hourly.configure(yscrollcommand=scroll_y.set)
            scroll_y.pack(side="right", fill="y")
            tree_hourly.pack(fill="both", expand=True)

            if hasattr(app, 'add_export_context_menu'):
                app.add_export_context_menu(tree_hourly, "Hourly_Comparison")
            
            for hour in range(24):
                val1 = h1.get(hour, 0)
                val2 = h2.get(hour, 0)
                
                if val1 == 0 and val2 == 0: continue
                
                diff_pct = ((val2 - val1) / val1 * 100) if val1 > 0 else 100 if val2 > 0 else 0
                sign = "+" if diff_pct > 0 else ""
                
                hour_str = f"{hour:02d}:00 - {hour+1:02d}:00"
                tree_hourly.insert("", "end", values=[hour_str, f"{val1:,.2f}", f"{val2:,.2f}", f"{sign}{diff_pct:.1f}%"])
                
            auto_fit_columns(tree_hourly)

    ctk.CTkButton(top_frame, text="Compare", font=("Segoe UI", 12, "bold"), fg_color=GREEN_PRIMARY, command=do_compare).pack(side="left", padx=20, pady=25)