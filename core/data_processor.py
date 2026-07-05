import pandas as pd
import numpy as np
from core.utils import (
    get_col, clean_item_code, translate_position, classify_material, classify_shift
)


class DataProcessor:
    def __init__(self):
        self.raw_df = None
        self.df = None
        self.branch_name = "Branch"
        self.period_info = {"start": "N/A", "end": "N/A", "days": 1}
        self.columns = {}

    def load_dataframe(self, df: pd.DataFrame):
        self.columns = {}
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

        self.columns = {
            "price": self.c_price, "qty": self.c_qty, "name": self.c_name,
            "cat": self.c_cat, "rec": self.c_rec, "mat": self.c_mat,
            "desc": self.c_desc, "time": self.c_time, "date": self.c_date,
            "branch": self.c_branch, "item_code": self.c_item_code,
        }

        if not self.c_price or not self.c_name:
            raise ValueError("Missing essential columns (price / employee name).")

        if self.c_date:
            df = df.dropna(subset=[self.c_date])
        if self.c_rec:
            df = df.dropna(subset=[self.c_rec])

        df[self.c_price] = pd.to_numeric(df[self.c_price].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
        if self.c_qty:
            df[self.c_qty] = pd.to_numeric(df[self.c_qty].astype(str).str.replace(",", ""), errors="coerce").fillna(0.0)
        else:
            df["Quantity"] = 1.0
            self.c_qty = "Quantity"

        if self.c_item_code:
            df[self.c_item_code] = df[self.c_item_code].apply(clean_item_code)
        if self.c_pos_name:
            df["Translated_Position"] = df[self.c_pos_name].apply(translate_position)

        if self.c_mat:
            df["Item_Type"] = df[self.c_mat].apply(classify_material)
        else:
            df["Item_Type"] = "Uncategorized"

        if self.c_time:
            df["Shift_Name"] = df[self.c_time].apply(classify_shift)

        if self.c_branch and not df[self.c_branch].dropna().empty:
            self.branch_name = str(df[self.c_branch].dropna().iloc[0])
        else:
            self.branch_name = "Lotus_Plant"

        if self.c_date and not df[self.c_date].dropna().empty:
            df["Parsed_Date"] = pd.to_datetime(df[self.c_date], errors="coerce")
            dates = df["Parsed_Date"].dropna()
            if not dates.empty:
                min_date, max_date = dates.min(), dates.max()
                self.period_info = {
                    "start": min_date.strftime("%Y-%m-%d"),
                    "end": max_date.strftime("%Y-%m-%d"),
                    "days": (max_date - min_date).days + 1,
                }
            else:
                self.period_info = {"start": "N/A", "end": "N/A", "days": 1}
        else:
            self.period_info = {"start": "N/A", "end": "N/A", "days": 1}

        if self.c_date and self.c_time:
            try:
                df["DateTime"] = pd.to_datetime(
                    df[self.c_date].astype(str) + " " + df[self.c_time].astype(str), errors="coerce"
                )
                df["Sale_Hour"] = df["DateTime"].dt.hour
            except Exception:
                pass

        if self.c_rec:
            cols_to_join = [self.c_name, self.c_rec]
            if self.c_date:
                cols_to_join.append(self.c_date)
            if self.c_pos:
                cols_to_join.append(self.c_pos)
            if self.c_branch:
                cols_to_join.append(self.c_branch)
            df["True_Receipt_ID"] = df[cols_to_join].astype(str).agg("_".join, axis=1)

        self.raw_df = df
        self.df = df.copy()
        return self.get_filter_options()

    def get_filter_options(self):
        if self.raw_df is None:
            return {}
        df = self.raw_df
        opts = {}
        if self.c_name:
            opts["employees"] = sorted([str(x) for x in df[self.c_name].dropna().unique()])
        if self.c_branch:
            opts["branches"] = sorted([str(x) for x in df[self.c_branch].dropna().unique()])
        if "Shift_Name" in df.columns:
            opts["shifts"] = sorted([str(x) for x in df["Shift_Name"].dropna().unique()])
        if self.c_cat:
            opts["categories"] = sorted([str(x) for x in df[self.c_cat].dropna().unique()])
        if "Item_Type" in df.columns:
            requested = ["Drugs", "Cosmetics", "Medical Accessories", "Services"]
            found = [str(x) for x in df["Item_Type"].dropna().unique()]
            opts["materials"] = [m for m in requested if m in found] + [m for m in sorted(found) if m not in requested]
        opts["period"] = self.period_info
        if self.c_date:
            dates = pd.to_datetime(df[self.c_date], errors="coerce").dropna()
            opts["dates"] = sorted(dates.dt.strftime("%Y-%m-%d").unique().tolist())
        return opts

    def apply_filters(self, start_date=None, end_date=None, employees=None, branches=None,
                      shifts=None, categories=None, materials=None):
        if self.raw_df is None:
            return
        df = self.raw_df.copy()

        if start_date and end_date and "Parsed_Date" in df.columns:
            s_date = pd.to_datetime(start_date)
            e_date = pd.to_datetime(end_date)
            df = df[(df["Parsed_Date"] >= s_date) & (df["Parsed_Date"] <= e_date)]
            calc_days = (e_date - s_date).days + 1
            self.period_info = {
                "start": start_date, "end": end_date,
                "days": calc_days if calc_days > 0 else 1,
            }

        def _filter(col, selected):
            nonlocal df
            if col and col in df.columns and selected:
                df = df[df[col].astype(str).isin(selected)]

        _filter(self.c_name, employees)
        _filter(self.c_branch, branches)
        _filter("Shift_Name", shifts)
        _filter(self.c_cat, categories)
        _filter("Item_Type", materials)
        self.df = df

    def get_kpis(self, daily_avg=False):
        if self.df is None or self.df.empty:
            return {}
        div = max(1, self.period_info.get("days", 1)) if daily_avg else 1
        t_sales = float(self.df[self.c_price].sum())
        t_pcs = float(self.df[self.c_qty].sum())
        if self.c_rec and "True_Receipt_ID" in self.df.columns:
            t_rec = int(self.df["True_Receipt_ID"].nunique())
        else:
            t_rec = len(self.df)
        t_avg = t_sales / t_rec if t_rec > 0 else 0
        return {
            "total_sales": round(t_sales / div, 2),
            "total_receipts": round(t_rec / div, 2) if daily_avg else t_rec,
            "total_pieces": round(t_pcs / div, 2),
            "avg_receipt": round(t_avg, 2),
            "period": self.period_info,
            "daily_avg": daily_avg,
        }

    def get_receipts_series(self, df=None):
        df = df if df is not None else self.df
        if not self.c_rec:
            return df.groupby(self.c_name).size()
        if "True_Receipt_ID" in df.columns:
            return df.groupby(self.c_name)["True_Receipt_ID"].nunique()
        group_keys = [self.c_name]
        if self.c_date:
            group_keys.append(self.c_date)
        if self.c_pos:
            group_keys.append(self.c_pos)
        if self.c_branch:
            group_keys.append(self.c_branch)
        group_keys.append(self.c_rec)
        return df.groupby(group_keys).size().groupby(level=0).size()
