import pandas as pd
import numpy as np
from core.utils import web_text, clean_item_code


class AnalyticsService:
    def __init__(self, processor):
        self.p = processor
        self._daily = False
        self.div = 1

    def set_divisor(self, daily_avg):
        self._daily = daily_avg
        self.div = max(1, self.p.period_info.get("days", 1)) if daily_avg else 1

    def chart_material_groups(self):
        df = self.p.df
        if df is None or "Item_Type" not in df.columns:
            return {"labels": [], "values": []}
        data = df.groupby("Item_Type")[self.p.c_price].sum().sort_values(ascending=False).head(5) / self.div
        return {"labels": [web_text(x) for x in data.index], "values": [round(v, 2) for v in data.values]}

    def chart_hourly_sales(self):
        df = self.p.df
        if df is None or "Sale_Hour" not in df.columns:
            return {"labels": [], "values": []}
        data = df.groupby("Sale_Hour")[self.p.c_price].sum() / self.div
        return {"labels": [f"{int(h):02d}:00" for h in data.index], "values": [round(v, 2) for v in data.values]}

    def chart_shift_sales(self):
        df = self.p.df
        if df is None or "Shift_Name" not in df.columns:
            return {"labels": [], "values": []}
        data = df.groupby("Shift_Name")[self.p.c_price].sum() / self.div
        return {"labels": [web_text(x) for x in data.index], "values": [round(v, 2) for v in data.values]}

    def chart_category_pie(self):
        df = self.p.df
        if df is None or not self.p.c_cat:
            return {"labels": [], "values": []}
        data = df.groupby(self.p.c_cat)[self.p.c_price].sum()
        return {"labels": [web_text(x) for x in data.index], "values": [round(v, 2) for v in data.values]}

    def top_employees(self, limit=10):
        df = self.p.df
        if df is None or not self.p.c_name:
            return []
        e_data = df.groupby(self.p.c_name)[self.p.c_price].sum().sort_values(ascending=False).head(limit)
        rows = []
        for emp, val in e_data.items():
            emp_df = df[df[self.p.c_name] == emp]
            branch = emp_df[self.p.c_branch].mode()[0] if self.p.c_branch and not emp_df[self.p.c_branch].empty else "N/A"
            shift = emp_df["Shift_Name"].mode()[0] if "Shift_Name" in emp_df.columns and not emp_df["Shift_Name"].empty else "N/A"
            top_cat = emp_df[self.p.c_cat].mode()[0] if self.p.c_cat and not emp_df[self.p.c_cat].empty else "N/A"
            rows.append({
                "name": web_text(emp), "branch": web_text(branch),
                "shift": web_text(shift), "top_type": web_text(top_cat),
                "sales": round(val / self.div, 2),
            })
        return rows

    def top_products(self, limit=150):
        df = self.p.df
        if df is None or not self.p.c_desc:
            return []
        grp_cols = [self.p.c_desc]
        if self.p.c_item_code:
            grp_cols.insert(0, self.p.c_item_code)
        if self.p.c_cat:
            grp_cols.append(self.p.c_cat)
        if "Item_Type" in df.columns:
            grp_cols.append("Item_Type")
        prod_grp = df.groupby(grp_cols).agg({self.p.c_qty: "sum", self.p.c_price: "sum"}).reset_index()
        prod_grp = prod_grp.sort_values(self.p.c_qty, ascending=False).head(limit)
        rows = []
        for _, row in prod_grp.iterrows():
            rows.append({
                "code": clean_item_code(row[self.p.c_item_code]) if self.p.c_item_code else "",
                "description": web_text(row[self.p.c_desc]),
                "category": web_text(row[self.p.c_cat]) if self.p.c_cat else "N/A",
                "material_group": web_text(row["Item_Type"]) if "Item_Type" in row else "N/A",
                "qty": round(row[self.p.c_qty] / self.div, 2),
                "sales": round(row[self.p.c_price] / self.div, 2),
            })
        return rows

    def employee_performance(self, mode="overview"):
        df = self.p.df
        if df is None or not self.p.c_name:
            return []
        grp = df.groupby(self.p.c_name)
        emp_sales = grp[self.p.c_price].sum()
        items_sold = grp[self.p.c_qty].sum()
        emp_rec = self.p.get_receipts_series(df).reindex(emp_sales.index, fill_value=1).replace(0, 1)
        avg_rec = (emp_sales / emp_rec).round(2)
        items_per_rec = (items_sold / emp_rec).round(2)
        main_shift = (
            df.groupby(self.p.c_name)["Shift_Name"].agg(lambda x: x.mode()[0] if not x.mode().empty else "Unknown")
            if "Shift_Name" in df.columns
            else pd.Series("Unknown", index=emp_sales.index)
        )
        rows = []
        fmt_rec = lambda x: round(x / self.div, 1) if self._daily else int(x)

        if mode == "overview":
            for emp, row in emp_sales.items():
                pos = "Unknown"
                if "Translated_Position" in df.columns:
                    pos = df[df[self.p.c_name] == emp]["Translated_Position"].iloc[0]
                rows.append({
                    "employee": web_text(emp), "position": pos,
                    "shift": web_text(main_shift.get(emp, "")),
                    "sales": round(row / self.div, 2),
                    "receipts": fmt_rec(emp_rec.get(emp, 0)),
                    "avg_receipt": round(avg_rec.get(emp, 0), 2),
                    "materials_per_receipt": round(items_per_rec.get(emp, 0), 2),
                })
        elif mode == "ai":
            avg_global = avg_rec.mean() if not avg_rec.empty else 0
            combined = pd.DataFrame({"Sales": emp_sales, "Avg": avg_rec, "MatPerRec": items_per_rec, "Shift": main_shift}).sort_values("Sales", ascending=False)
            for i, (emp, row) in enumerate(combined.iterrows()):
                tier = "Star Performer" if i < 3 else ("Solid Contributor" if i < len(combined) / 2 else "Needs Improvement")
                recs = []
                if row["Avg"] >= avg_global * 1.1:
                    recs.append("Excellent basket value.")
                elif row["Avg"] < avg_global * 0.8:
                    recs.append("Low avg receipt - needs cross-selling coaching.")
                if row["MatPerRec"] < 1.5:
                    recs.append("Low materials/receipt.")
                if not recs:
                    recs.append("Steady performance.")
                rows.append({
                    "employee": web_text(emp), "shift": web_text(row["Shift"]),
                    "tier": tier, "materials_per_receipt": round(row["MatPerRec"], 2),
                    "recommendation": " | ".join(recs),
                })
        return rows

    def executive_summary(self):
        df = self.p.df
        if df is None:
            return {}
        result = {"best_shift": "N/A", "peak_hours": [], "shifts_by_branch": [], "pharmacists": []}
        if "Shift_Name" in df.columns:
            try:
                result["best_shift"] = web_text(df.groupby("Shift_Name")[self.p.c_price].sum().idxmax())
            except Exception:
                pass
        if "Sale_Hour" in df.columns:
            try:
                top_hours = df.groupby("Sale_Hour")[self.p.c_price].sum().nlargest(2).index.tolist()
                result["peak_hours"] = [f"{int(h):02d}:00 - {int(h)+1:02d}:00" for h in top_hours]
            except Exception:
                pass
        rec_col = "True_Receipt_ID" if "True_Receipt_ID" in df.columns else self.p.c_rec
        if "Shift_Name" in df.columns and self.p.c_branch in df.columns:
            shift_grp = df.groupby([self.p.c_branch, "Shift_Name"]).agg({self.p.c_price: "sum", rec_col: "nunique"}).reset_index()
            for _, row in shift_grp.iterrows():
                recs = row[rec_col] if row[rec_col] > 0 else 1
                result["shifts_by_branch"].append({
                    "branch": web_text(row[self.p.c_branch]),
                    "shift": web_text(row["Shift_Name"]),
                    "sales": round(row[self.p.c_price] / self.div, 2),
                    "receipts": round(row[rec_col] / self.div, 1) if self._daily else int(row[rec_col]),
                    "avg_receipt": round(row[self.p.c_price] / recs, 2),
                })
        return result

    def stagnant_analysis(self, master_df):
        df = self.p.df
        if df is None or master_df is None or master_df.empty:
            return []
        sales_grp = df.groupby(self.p.c_desc)[self.p.c_qty].sum().reset_index()
        sales_grp.columns = ["Description", "Qty_Sold"]
        merged = pd.merge(master_df, sales_grp, on="Description", how="left")
        merged["Qty_Sold"] = merged["Qty_Sold"].fillna(0)
        rows = []
        for (_, _, granular), group in merged.groupby(["SubCat1", "SubCat2", "GranularCat"]):
            if str(granular).strip().lower() in ["", "nan", "none", "general", "other"]:
                continue
            top_seller = group.sort_values(by="Qty_Sold", ascending=False).iloc[0]
            if top_seller["Qty_Sold"] <= 2:
                continue
            stagnant_items = group[group["Qty_Sold"] == 0]
            for _, row in stagnant_items.iterrows():
                rows.append({
                    "stagnant_code": clean_item_code(row["Material"]),
                    "stagnant_drug": web_text(row["Description"]),
                    "alt_code": clean_item_code(top_seller["Material"]),
                    "alt_drug": web_text(top_seller["Description"]),
                    "alt_qty": int(top_seller["Qty_Sold"]),
                })
        return rows
