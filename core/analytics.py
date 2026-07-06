import pandas as pd
import numpy as np
from core.utils import web_text, clean_item_code, format_number, format_int


class AnalyticsService:
    def __init__(self, processor):
        self.p = processor
        self._daily = False
        self.div = 1
        self._emp_stats_cache = None

    def set_divisor(self, daily_avg):
        self._daily = daily_avg
        self.div = max(1, self.p.period_info.get("days", 1)) if daily_avg else 1

    def _fmt_rec(self, x):
        return round(x / self.div, 1) if self._daily else int(x)

    def _d0(self, val):
        return format_int(val)

    def _d1(self, val):
        return format_number(val, 1)

    def _d2(self, val):
        return format_number(val, 2)

    def _d_rec(self, val):
        v = self._fmt_rec(val)
        return self._d1(v) if self._daily else self._d0(v)

    def _emp_metrics(self):
        df = self.p.df
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
        time_diff_series = pd.Series(index=emp_sales.index, data=0.0)
        if "DateTime" in df.columns and "True_Receipt_ID" in df.columns:
            sort_keys = [self.p.c_name]
            if self.p.c_pos:
                sort_keys.append(self.p.c_pos)
            sort_keys.append("DateTime")
            df_s = df.dropna(subset=["DateTime"]).sort_values(by=sort_keys)
            r_times = df_s.groupby([self.p.c_name, "True_Receipt_ID"])["DateTime"].min().reset_index().sort_values(by=[self.p.c_name, "DateTime"])
            r_times["Diff"] = r_times.groupby(self.p.c_name)["DateTime"].diff().dt.total_seconds() / 60
            r_times.loc[r_times["Diff"] > 480, "Diff"] = np.nan
            time_diff_series = r_times.groupby(self.p.c_name)["Diff"].mean().fillna(0).round(1)
        working_days = pd.Series(0, index=emp_sales.index, dtype=int)
        date_col = "Parsed_Date" if "Parsed_Date" in df.columns else self.p.c_date
        if date_col and date_col in df.columns:
            day_df = df[[self.p.c_name, date_col]].dropna(subset=[self.p.c_name])
            if date_col == "Parsed_Date":
                day_vals = day_df["Parsed_Date"].dt.normalize()
            else:
                day_vals = pd.to_datetime(day_df[date_col], errors="coerce").dt.normalize()
            day_df = day_df.assign(_work_day=day_vals).dropna(subset=["_work_day"])
            working_days = day_df.groupby(self.p.c_name)["_work_day"].nunique().reindex(emp_sales.index, fill_value=0).astype(int)
        self._emp_stats_cache = pd.DataFrame({
            "Employee Name": emp_sales.index,
            "Total Sales": emp_sales.values,
            "Total Receipts": emp_rec.values,
            "Avg Receipt": avg_rec.values,
        })
        return {
            "emp_sales": emp_sales, "items_sold": items_sold, "emp_rec": emp_rec,
            "avg_rec": avg_rec, "items_per_rec": items_per_rec, "main_shift": main_shift,
            "time_diff_series": time_diff_series, "working_days": working_days,
            "sys_avg_rec": emp_sales.sum() / emp_rec.sum() if emp_rec.sum() else 0,
            "sys_avg_mat": items_sold.sum() / emp_rec.sum() if emp_rec.sum() else 0,
        }

    def get_emp_stats_snapshot(self):
        if self._emp_stats_cache is None:
            self._emp_metrics()
        return self._emp_stats_cache

    def get_global_stats(self):
        df = self.p.df
        if df is None:
            return {}
        t_sales = float(df[self.p.c_price].sum())
        t_pcs = float(df[self.p.c_qty].sum())
        t_rec = int(df["True_Receipt_ID"].nunique()) if "True_Receipt_ID" in df.columns else len(df)
        return {
            "Total Sales": t_sales, "Total Receipts": t_rec,
            "Total Pieces": t_pcs, "Avg Receipt": t_sales / t_rec if t_rec else 0,
        }

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

    def chart_top_products_qty(self):
        df = self.p.df
        if df is None or not self.p.c_desc:
            return {"labels": [], "values": []}
        data = df.groupby(self.p.c_desc)[self.p.c_qty].sum().sort_values(ascending=True).tail(10) / self.div
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
                "sales": round(float(val) / self.div, 2),
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
                "qty": self._d2(row[self.p.c_qty] / self.div),
                "sales": self._d2(row[self.p.c_price] / self.div),
            })
        return rows

    def employee_performance(self, mode="overview", master_df=None):
        df = self.p.df
        if df is None or not self.p.c_name:
            return {"columns": [], "rows": []}
        m = self._emp_metrics()
        emp_sales, emp_rec = m["emp_sales"], m["emp_rec"]
        avg_rec, items_per_rec = m["avg_rec"], m["items_per_rec"]
        main_shift, time_diff_series = m["main_shift"], m["time_diff_series"]
        items_sold = m["items_sold"]
        working_days = m["working_days"]

        if mode == "overview":
            rows = []
            for emp, row in emp_sales.items():
                pos = "Unknown"
                if "Translated_Position" in df.columns:
                    pos = df[df[self.p.c_name] == emp]["Translated_Position"].iloc[0]
                rows.append({
                    "employee": web_text(emp), "position": pos,
                    "shift": web_text(main_shift.get(emp, "")),
                    "working_days": self._d0(working_days.get(emp, 0)),
                    "sales": self._d2(row / self.div),
                    "receipts": self._d_rec(emp_rec.get(emp, 0)),
                    "avg_receipt": self._d2(avg_rec.get(emp, 0)),
                    "materials_per_receipt": self._d2(items_per_rec.get(emp, 0)),
                })
            return {"columns": ["employee", "position", "shift", "working_days", "sales", "receipts", "avg_receipt", "materials_per_receipt"], "rows": rows}

        if mode == "sales_types":
            cat_sales = pd.DataFrame()
            sale_types = []
            if self.p.c_cat:
                cat_sales = df.groupby([self.p.c_name, self.p.c_cat])[self.p.c_price].sum().unstack(fill_value=0)
                sale_types = [web_text(c) for c in cat_sales.columns]
            combined = pd.DataFrame({"Sales": emp_sales, "Recs": emp_rec, "MatPerRec": items_per_rec, "Shift": main_shift, "WorkingDays": working_days}).join(cat_sales).sort_values("Sales", ascending=False)
            rows = []
            for emp, row in combined.iterrows():
                r = {
                    "employee": web_text(emp), "shift": web_text(row["Shift"]),
                    "working_days": self._d0(row["WorkingDays"]),
                    "receipts": self._d_rec(row["Recs"]),
                    "sales": self._d2(row["Sales"] / self.div),
                    "materials_per_receipt": self._d2(row["MatPerRec"]),
                }
                for i, c in enumerate(cat_sales.columns):
                    r[f"cat_{i}"] = self._d2(row[c] / self.div)
                rows.append(r)
            cols = ["employee", "shift", "working_days", "receipts", "sales", "materials_per_receipt"] + [f"cat_{i}" for i in range(len(sale_types))]
            base_labels = ["employee", "shift", "working_days", "receipts", "sales", "materials_per_receipt"]
            return {"columns": cols, "column_labels": base_labels + sale_types, "rows": rows}

        if mode == "subcategories":
            temp_df = df.copy()
            if master_df is not None and not master_df.empty and self.p.c_desc:
                master_sub = master_df[["Description", "SubCat1", "SubCat2"]].copy()
                master_sub["Description"] = master_sub["Description"].astype(str).str.strip()
                temp_df[self.p.c_desc] = temp_df[self.p.c_desc].astype(str).str.strip()
                temp_df = temp_df.merge(master_sub, left_on=self.p.c_desc, right_on="Description", how="left")
                temp_df["SubCat1"] = temp_df["SubCat1"].fillna("Uncategorized")
                temp_df["SubCat2"] = temp_df["SubCat2"].fillna("Uncategorized")
            else:
                temp_df["SubCat1"] = temp_df["Item_Type"] if "Item_Type" in temp_df.columns else "Uncategorized"
                temp_df["SubCat2"] = "N/A"
            rec_col = "True_Receipt_ID" if "True_Receipt_ID" in temp_df.columns else self.p.c_rec
            agg = {self.p.c_price: "sum", self.p.c_qty: "sum"}
            if rec_col:
                agg[rec_col] = "nunique"
            sub_grp = temp_df.groupby([self.p.c_name, "SubCat1", "SubCat2"]).agg(agg).reset_index()
            sub_grp = sub_grp[sub_grp[self.p.c_price] > 0].sort_values(by=[self.p.c_name, self.p.c_price], ascending=[True, False])
            rows = []
            for _, row in sub_grp.iterrows():
                e_tot = emp_sales.get(row[self.p.c_name], 1)
                pct = (row[self.p.c_price] / e_tot * 100) if e_tot > 0 else 0
                rows.append({
                    "employee": web_text(row[self.p.c_name]),
                    "subcat1": web_text(row["SubCat1"]),
                    "subcat2": web_text(row["SubCat2"]),
                    "sales": self._d2(row[self.p.c_price] / self.div),
                    "sales_pct": f"{pct:.1f} %",
                    "materials": self._d1(row[self.p.c_qty] / self.div) if self._daily else self._d0(row[self.p.c_qty]),
                    "receipts": self._d_rec(row[rec_col]) if rec_col and rec_col in row.index else "N/A",
                })
            return {"columns": ["employee", "subcat1", "subcat2", "sales", "sales_pct", "materials", "receipts"], "rows": rows}

        if mode == "efficiency":
            combined = pd.DataFrame({
                "Recs": emp_rec, "Avg": avg_rec, "MatPerRec": items_per_rec,
                "Items": items_sold, "Time": time_diff_series, "Shift": main_shift,
                "WorkingDays": working_days,
            }).sort_values("Recs", ascending=False)
            avg_time_global = time_diff_series[time_diff_series > 0].mean() if not time_diff_series.empty else 0
            rows = []
            for emp, row in combined.iterrows():
                rows.append({
                    "employee": web_text(emp), "shift": web_text(row["Shift"]),
                    "working_days": self._d0(row["WorkingDays"]),
                    "receipts": self._d_rec(row["Recs"]),
                    "avg_receipt": self._d2(row["Avg"]),
                    "materials_per_receipt": self._d2(row["MatPerRec"]),
                    "total_materials": self._d2(row["Items"] / self.div),
                    "avg_mins": f"{row['Time']} mins" if row["Time"] > 0 else "N/A",
                })
            rows.append({
                "employee": "📊 SUBTOTAL / AVG", "shift": "---", "working_days": "---",
                "receipts": self._d_rec(emp_rec.sum()),
                "avg_receipt": self._d2(m["sys_avg_rec"]),
                "materials_per_receipt": self._d2(m["sys_avg_mat"]),
                "total_materials": self._d2(items_sold.sum() / self.div),
                "avg_mins": f"{avg_time_global:.1f} mins" if avg_time_global > 0 else "N/A",
                "is_subtotal": True,
            })
            return {"columns": ["employee", "shift", "working_days", "receipts", "avg_receipt", "materials_per_receipt", "total_materials", "avg_mins"], "rows": rows}

        if mode == "ai":
            avg_global = avg_rec.mean() if not avg_rec.empty else 0
            time_global = time_diff_series[time_diff_series > 0].mean() if not time_diff_series.empty else 0
            cat_sales = df.groupby([self.p.c_name, self.p.c_cat])[self.p.c_price].sum().unstack(fill_value=0) if self.p.c_cat else pd.DataFrame()
            combined = pd.DataFrame({
                "Sales": emp_sales, "Avg": avg_rec, "Time": time_diff_series,
                "MatPerRec": items_per_rec, "Shift": main_shift, "WorkingDays": working_days,
            }).sort_values("Sales", ascending=False)
            combined["SalesPerDay"] = combined["Sales"] / combined["WorkingDays"].clip(lower=1)
            team_avg_spd = combined["SalesPerDay"].mean() if not combined.empty else 0
            avg_wd = combined["WorkingDays"].mean() if not combined.empty else 0
            period_days = max(1, self.p.period_info.get("days", 1))
            spd_rank = combined["SalesPerDay"].rank(ascending=False, method="min")
            rows = []
            for i, (emp, row) in enumerate(combined.iterrows()):
                tier = "Star Performer" if i < 3 else ("Solid Contributor" if i < len(combined) / 2 else "Needs Improvement")
                efficiency, shift_ins, attendance, skills = [], [], [], []
                spd = row["SalesPerDay"]
                wd = int(row["WorkingDays"])
                shift = row["Shift"]
                spd_val = round(spd / self.div, 0)
                team_spd_val = round(team_avg_spd / self.div, 0)

                if spd >= team_avg_spd * 1.15:
                    efficiency.append(f"Sales/day: {format_int(spd_val)} — above team avg ({format_int(team_spd_val)})")
                elif spd < team_avg_spd * 0.8:
                    efficiency.append(f"Sales/day: {format_int(spd_val)} — below team avg ({format_int(team_spd_val)})")

                shift_peers = combined[combined["Shift"] == shift]
                if len(shift_peers) > 1:
                    best_emp = shift_peers["SalesPerDay"].idxmax()
                    if emp == best_emp:
                        shift_ins.append(f"Best performer on {shift} shift")
                    else:
                        best_spd = shift_peers.loc[best_emp, "SalesPerDay"]
                        if best_spd > 0:
                            pct_behind = (1 - spd / best_spd) * 100
                            if pct_behind >= 10:
                                shift_ins.append(f"{pct_behind:.0f}% behind {web_text(best_emp)} on {shift}")

                rank_pos = int(spd_rank.get(emp, len(combined)))
                if rank_pos == 1 and len(combined) > 1 and not shift_ins:
                    efficiency.append("Highest sales efficiency in team")

                if wd < avg_wd * 0.75:
                    if spd >= team_avg_spd:
                        attendance.append(f"{format_int(wd)} working days — strong output when present")
                    else:
                        attendance.append(f"Only {format_int(wd)} working days (team avg {format_int(round(avg_wd))}) — low attendance")
                elif wd >= period_days * 0.85 and spd < team_avg_spd * 0.85:
                    attendance.append(f"{format_int(wd)} working days but weak daily sales")

                if row["Avg"] >= avg_global * 1.1:
                    skills.append("Strong upselling — high avg receipt")
                elif row["Avg"] < avg_global * 0.8:
                    skills.append("Low avg receipt — coach cross-selling")
                if row["MatPerRec"] > m["sys_avg_mat"] * 1.2:
                    skills.append("Excellent multi-item sales")
                elif row["MatPerRec"] < 1.5:
                    skills.append("Low items per receipt")
                if row["Time"] > 0 and row["Time"] > time_global * 1.3:
                    skills.append("Slow between receipts")
                if not cat_sales.empty and emp in cat_sales.index:
                    e_cats = {str(k).lower(): v for k, v in cat_sales.loc[emp].items()}
                    cash = sum(v for k, v in e_cats.items() if "cash" in k or "نقدي" in k)
                    digital = sum(v for k, v in e_cats.items() if "digital" in k or "visa" in k or "فيزا" in k)
                    if digital == 0 and cash > 0:
                        skills.append("No digital/visa sales")

                recs = (efficiency[:1] + shift_ins[:1] + attendance[:1] + skills[:2])[:4]
                if not recs:
                    recs = ["Steady performance — maintain consistency"]
                rows.append({
                    "employee": web_text(emp), "shift": web_text(row["Shift"]),
                    "working_days": self._d0(wd),
                    "tier": tier, "materials_per_receipt": self._d2(row["MatPerRec"]),
                    "recommendations": recs,
                    "recommendation": " | ".join(recs),
                })
            return {"columns": ["employee", "shift", "working_days", "tier", "materials_per_receipt", "recommendation"], "rows": rows}
        return {"columns": [], "rows": []}

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
        if "Shift_Name" in df.columns:
            if self.p.c_branch in df.columns:
                shift_grp = df.groupby([self.p.c_branch, "Shift_Name"]).agg({self.p.c_price: "sum", rec_col: "nunique"}).reset_index()
            else:
                shift_grp = df.groupby("Shift_Name").agg({self.p.c_price: "sum", rec_col: "nunique"}).reset_index()
                shift_grp[self.p.c_branch] = "N/A"
            for _, row in shift_grp.iterrows():
                recs = row[rec_col] if row[rec_col] > 0 else 1
                result["shifts_by_branch"].append({
                    "branch": web_text(row[self.p.c_branch]),
                    "shift": web_text(row["Shift_Name"]),
                    "sales": self._d2(row[self.p.c_price] / self.div),
                    "receipts": self._d_rec(row[rec_col]),
                    "avg_receipt": self._d2(row[self.p.c_price] / recs),
                })
        emp_grp = df.groupby(self.p.c_name).agg({self.p.c_price: "sum", rec_col: "nunique"})
        emp_grp["AvgRec"] = emp_grp[self.p.c_price] / emp_grp[rec_col].replace(0, 1)
        emp_grp = emp_grp.sort_values(by=self.p.c_price, ascending=False)
        mean_sales = emp_grp[self.p.c_price].mean()
        mean_avg_rec = emp_grp["AvgRec"].mean()

        def get_top_col(target_col):
            if target_col not in df.columns:
                return pd.Series("N/A", index=emp_grp.index)
            return df.groupby([self.p.c_name, target_col])[self.p.c_price].sum().reset_index().sort_values(self.p.c_price, ascending=False).drop_duplicates(self.p.c_name).set_index(self.p.c_name)[target_col]

        top_sales_type = get_top_col(self.p.c_cat)
        top_item_type = get_top_col("Item_Type")
        emp_branch = df.groupby(self.p.c_name)[self.p.c_branch].agg(lambda x: x.mode()[0] if not x.mode().empty else "Unknown") if self.p.c_branch in df.columns else pd.Series("Unknown", index=emp_grp.index)
        emp_shift = df.groupby(self.p.c_name)["Shift_Name"].agg(lambda x: x.mode()[0] if not x.mode().empty else "Unknown") if "Shift_Name" in df.columns else pd.Series("Unknown", index=emp_grp.index)

        for emp, row in emp_grp.iterrows():
            s, r, a = row[self.p.c_price], row[rec_col], row["AvgRec"]
            if s >= mean_sales and a >= mean_avg_rec:
                ev = "⭐ Excellent: High Volume & High Basket"
            elif s >= mean_sales and a < mean_avg_rec:
                ev = "📈 Volume Driven: Needs Cross-selling"
            elif s < mean_sales and a >= mean_avg_rec:
                ev = "🎯 Quality over Qty: Good Upselling"
            else:
                ev = "⚠️ Needs Training: Low Volume & Low Basket"
            result["pharmacists"].append({
                "name": web_text(emp), "branch": web_text(emp_branch.get(emp, "Unknown")),
                "shift": web_text(emp_shift.get(emp, "Unknown")),
                "sales": self._d2(s / self.div), "receipts": self._d_rec(r),
                "avg_receipt": self._d2(a),
                "top_sales_type": web_text(top_sales_type.get(emp, "N/A")),
                "top_category": web_text(top_item_type.get(emp, "N/A")),
                "evaluation": ev,
            })
        return result

    def date_compare(self, s1, e1, s2, e2, mode="hourly"):
        df = self.p.df
        if df is None or not self.p.c_date:
            return {"error": "No date column"}
        df = df.copy()
        df["Temp_Date"] = pd.to_datetime(df[self.p.c_date], errors="coerce").dt.strftime("%Y-%m-%d")
        df1 = df[(df["Temp_Date"] >= s1) & (df["Temp_Date"] <= e1)]
        df2 = df[(df["Temp_Date"] >= s2) & (df["Temp_Date"] <= e2)]
        d1 = max(1, (pd.to_datetime(e1) - pd.to_datetime(s1)).days + 1) if self._daily else 1
        d2 = max(1, (pd.to_datetime(e2) - pd.to_datetime(s2)).days + 1) if self._daily else 1
        rec_col = "True_Receipt_ID" if "True_Receipt_ID" in df.columns else self.p.c_rec

        if mode == "totals":
            return {
                "mode": "totals",
                "p1": {"start": s1, "end": e1, "sales": round(df1[self.p.c_price].sum() / d1, 2),
                       "receipts": round((df1[rec_col].nunique() if not df1.empty else 0) / d1, 2)},
                "p2": {"start": s2, "end": e2, "sales": round(df2[self.p.c_price].sum() / d2, 2),
                       "receipts": round((df2[rec_col].nunique() if not df2.empty else 0) / d2, 2)},
            }

        if "Sale_Hour" not in df.columns:
            return {"error": "Hourly data not available"}
        h1 = (df1.groupby("Sale_Hour")[self.p.c_price].sum().reindex(range(24), fill_value=0)) / d1
        h2 = (df2.groupby("Sale_Hour")[self.p.c_price].sum().reindex(range(24), fill_value=0)) / d2
        rows = []
        chart_labels, chart_p1, chart_p2 = [], [], []
        for hour in range(24):
            v1, v2 = float(h1.get(hour, 0)), float(h2.get(hour, 0))
            if v1 == 0 and v2 == 0:
                continue
            diff_pct = ((v2 - v1) / v1 * 100) if v1 > 0 else (100 if v2 > 0 else 0)
            rows.append({
                "hour": f"{hour:02d}:00 - {hour+1:02d}:00",
                "p1_sales": self._d2(v1), "p2_sales": self._d2(v2),
                "variance": f"{'+' if diff_pct > 0 else ''}{diff_pct:.1f}%",
            })
            chart_labels.append(f"{hour:02d}:00")
            chart_p1.append(round(v1, 2))
            chart_p2.append(round(v2, 2))
        return {"mode": "hourly", "rows": rows, "chart": {"labels": chart_labels, "p1": chart_p1, "p2": chart_p2}}

    def trend_compare(self, history_emp_df, history_meta_df):
        gs = self.get_global_stats()
        prev = history_meta_df.iloc[0]
        curr_sales = gs.get("Total Sales", 0)
        p_sales = float(prev.get("Global Sales", 0))
        curr_recs = gs.get("Total Receipts", 0)
        p_recs = float(prev.get("Global Receipts", 0))
        curr_avg = gs.get("Avg Receipt", 0)
        p_avg = float(prev.get("Global Avg Receipt", 0))
        curr_pcs = gs.get("Total Pieces", 0)
        p_pcs = float(prev.get("Global Pcs", 0))

        def pct(n, o):
            return ((n - o) / o * 100) if o else 0

        kpis = [
            {"title": "Total Sales", "old": p_sales, "new": curr_sales, "pct": pct(curr_sales, p_sales)},
            {"title": "Total Receipts", "old": p_recs, "new": curr_recs, "pct": pct(curr_recs, p_recs)},
            {"title": "Average Receipt", "old": p_avg, "new": curr_avg, "pct": pct(curr_avg, p_avg)},
            {"title": "Total Pieces Sold", "old": p_pcs, "new": curr_pcs, "pct": pct(curr_pcs, p_pcs)},
        ]
        self._emp_metrics()
        curr_emp = self._emp_stats_cache
        merged = pd.merge(history_emp_df, curr_emp, on="Employee Name", how="inner", suffixes=("_prev", "_curr"))
        rows = []
        for _, row in merged.iterrows():
            emp = row["Employee Name"]
            s_prev, s_curr = float(row["Total Sales_prev"]), float(row["Total Sales_curr"])
            r_prev = float(row.get("Total Receipts_prev", 0))
            r_curr = float(row.get("Total Receipts_curr", 0))
            a_prev, a_curr = float(row["Avg Receipt_prev"]), float(row["Avg Receipt_curr"])
            sales_pct = ((s_curr - s_prev) / s_prev * 100) if s_prev > 0 else 0
            avg_pct = ((a_curr - a_prev) / a_prev * 100) if a_prev > 0 else 0
            if sales_pct > 10 and avg_pct > 5:
                insight = "🟢 Outstanding Growth: Both volume and basket size improved."
            elif sales_pct > 5 and avg_pct <= 0:
                insight = "🟡 Volume Driven: Sales went up, but average receipt dropped."
            elif sales_pct < -5 and avg_pct > 5:
                insight = "🟡 Quality over Quantity: Lost some traffic but maximized value per patient."
            elif sales_pct < -10 and avg_pct < -5:
                insight = "🔴 Critical Decline: Both sales and basket size dropped significantly."
            else:
                insight = "⚪ Stable Performance."
            rows.append({
                "employee": web_text(emp),
                "prev_sales": self._d0(s_prev), "curr_sales": self._d0(s_curr),
                "sales_delta": f"{sales_pct:.1f}%",
                "prev_recs": self._d0(r_prev), "curr_recs": self._d0(r_curr),
                "prev_avg": self._d0(a_prev), "curr_avg": self._d0(a_curr),
                "avg_delta": f"{avg_pct:.1f}%", "insight": insight,
            })
        return {
            "header": {
                "prev_start": str(prev.get("Start Date", "N/A"))[:10],
                "prev_end": str(prev.get("End Date", "N/A"))[:10],
                "prev_days": prev.get("Days Count", "N/A"),
                "curr_start": self.p.period_info.get("start"),
                "curr_end": self.p.period_info.get("end"),
                "curr_days": self.p.period_info.get("days"),
            },
            "kpis": kpis, "rows": rows,
        }

    _DELIVERY_KEYWORDS = (
        "instashop", "insta shop", "talabat", "طلبات", "hunger", "delivery", "deliver",
        "digital", "online", "visa", "carriage", "noon", "fizzy", "app", "ecommerce",
        "normal delivery", "ديليفري", "انستا", "chefaa", "شفاء",
    )

    _SUB_CHANNEL_RULES = (
        ("Instashop", ("instashop", "insta shop", "insta-shop", "انستا", "انستا شوب")),
        ("Talabat", ("talabat", "طلبات")),
        ("Chefaa", ("chefaa", "شفاء")),
        ("HungerStation", ("hungerstation", "hunger station", "هنقر")),
        ("Carriage", ("carriage", "كرriage")),
        ("Noon", ("noon", "نون")),
        ("Fizzy", ("fizzy",)),
        ("Normal Delivery", ("normal delivery", "ديليفري")),
    )

    def _prepare_master_merged(self, master_df):
        df = self.p.df
        if df is None or df.empty or master_df is None or master_df.empty or not self.p.c_desc:
            return None
        temp = df.copy()
        master_sub = master_df[["Material", "Description", "SubCat1", "SubCat2", "GranularCat"]].copy()
        master_sub["Description"] = master_sub["Description"].astype(str).str.strip()
        master_sub["Material"] = master_sub["Material"].astype(str).str.strip()
        by_desc = master_sub.drop_duplicates("Description").set_index("Description")
        by_code = master_sub.drop_duplicates("Material").set_index("Material")

        desc_key = temp[self.p.c_desc].astype(str).str.strip()
        temp["SubCat1"] = desc_key.map(by_desc["SubCat1"])
        temp["SubCat2"] = desc_key.map(by_desc["SubCat2"])
        temp["GranularCat"] = desc_key.map(by_desc["GranularCat"])

        if self.p.c_item_code:
            code_key = temp[self.p.c_item_code].astype(str).str.strip()
            missing = temp["SubCat1"].isna()
            if missing.any():
                temp.loc[missing, "SubCat1"] = code_key[missing].map(by_code["SubCat1"])
                temp.loc[missing, "SubCat2"] = code_key[missing].map(by_code["SubCat2"])
                temp.loc[missing, "GranularCat"] = code_key[missing].map(by_code["GranularCat"])

        temp["SubCat1"] = temp["SubCat1"].fillna("Uncategorized").astype(str).str.strip()
        temp["SubCat2"] = temp["SubCat2"].fillna("Uncategorized").astype(str).str.strip()
        temp["SalesType"] = (
            temp[self.p.c_cat].astype(str).str.strip() if self.p.c_cat else "All Sales"
        )
        temp["SubChannel"] = self._assign_sub_channels(temp)
        temp = temp[temp[self.p.c_price] > 0]
        return temp if not temp.empty else None

    def _is_delivery_type(self, sales_type):
        s = str(sales_type).lower()
        return any(k in s for k in self._DELIVERY_KEYWORDS)

    def _assign_sub_channels(self, df):
        customer = (
            df[self.p.c_customer].astype(str).str.strip()
            if self.p.c_customer and self.p.c_customer in df.columns
            else pd.Series("", index=df.index)
        )
        sales_type = df["SalesType"].astype(str).str.strip()
        combined = (customer + " " + sales_type).str.lower()
        channels = pd.Series("", index=df.index, dtype=str)
        for label, keys in self._SUB_CHANNEL_RULES:
            mask = pd.Series(False, index=df.index)
            for key in keys:
                mask |= combined.str.contains(key, regex=False, na=False)
            channels = channels.mask(mask & (channels == ""), label)
        digital_mask = sales_type.apply(self._is_delivery_type) & (channels == "")
        channels = channels.mask(digital_mask, sales_type[digital_mask].map(web_text))
        if self.p.c_customer:
            valid_cust = customer.str.len() > 0 & ~customer.str.lower().isin(["nan", "none", ""])
            named = sales_type.apply(self._is_delivery_type) & (channels == "") & valid_cust
            channels = channels.mask(named, customer[named].map(lambda x: web_text(str(x)[:80])))
        return channels

    def deep_sales_analysis(self, master_df):
        merged = self._prepare_master_merged(master_df)
        if merged is None:
            return {"ok": False, "error": "Upload master data (.lotusdb) and sales file with item descriptions."}

        price, qty, desc = self.p.c_price, self.p.c_qty, self.p.c_desc

        g1 = merged.groupby(["SalesType", "SubCat1"], as_index=False).agg(
            **{"sales_raw": (price, "sum"), "qty_raw": (qty, "sum")}
        )
        g1["type_total"] = g1.groupby("SalesType")["sales_raw"].transform("sum")
        g1 = g1[g1["sales_raw"] > 0].sort_values(["SalesType", "sales_raw"], ascending=[True, False])
        g1["rank"] = g1.groupby("SalesType").cumcount() + 1
        rows_type_cat = []
        for _, r in g1[g1["rank"] <= 25].iterrows():
            pct = (r["sales_raw"] / r["type_total"] * 100) if r["type_total"] > 0 else 0
            rows_type_cat.append({
                "sales_type": web_text(r["SalesType"]),
                "category": web_text(r["SubCat1"]),
                "rank_in_group": int(r["rank"]),
                "sales": self._d2(r["sales_raw"] / self.div),
                "qty": self._d2(r["qty_raw"] / self.div),
                "sales_pct": f"{pct:.1f}%",
            })

        g2 = merged.groupby(["SubCat1", "SubCat2"], as_index=False).agg(
            **{"sales_raw": (price, "sum"), "qty_raw": (qty, "sum")}
        )
        g2["cat_total"] = g2.groupby("SubCat1")["sales_raw"].transform("sum")
        g2 = g2[g2["sales_raw"] > 0].sort_values(["SubCat1", "sales_raw"], ascending=[True, False])
        g2["rank"] = g2.groupby("SubCat1").cumcount() + 1
        rows_cat_sub = []
        for _, r in g2[g2["rank"] <= 25].iterrows():
            pct = (r["sales_raw"] / r["cat_total"] * 100) if r["cat_total"] > 0 else 0
            rows_cat_sub.append({
                "category": web_text(r["SubCat1"]),
                "subcategory": web_text(r["SubCat2"]),
                "rank_in_group": int(r["rank"]),
                "sales": self._d2(r["sales_raw"] / self.div),
                "qty": self._d2(r["qty_raw"] / self.div),
                "sales_pct": f"{pct:.1f}%",
            })

        item_grp = merged.groupby(["SubCat1", "SubCat2", desc], as_index=False).agg(
            **{"sales_raw": (price, "sum"), "qty_raw": (qty, "sum")}
        )
        item_grp = item_grp.sort_values(["SubCat1", "SubCat2", "sales_raw"], ascending=[True, True, False])
        item_grp["rank"] = item_grp.groupby(["SubCat1", "SubCat2"]).cumcount() + 1
        rows_top_items = []
        for _, r in item_grp[item_grp["rank"] <= 5].iterrows():
            rows_top_items.append({
                "category": web_text(r["SubCat1"]),
                "subcategory": web_text(r["SubCat2"]),
                "rank_in_group": int(r["rank"]),
                "item": web_text(r[desc]),
                "sales": self._d2(r["sales_raw"] / self.div),
                "qty": self._d2(r["qty_raw"] / self.div),
            })

        delivery_types = sorted({t for t in merged["SalesType"].unique() if self._is_delivery_type(t)})
        deliv = merged[merged["SalesType"].isin(delivery_types)] if delivery_types else merged.iloc[0:0]
        rows_delivery = []
        chart_labels, chart_values = [], []
        if not deliv.empty:
            g4 = deliv.groupby(["SalesType", "SubCat1"], as_index=False).agg(
                **{"sales_raw": (price, "sum"), "qty_raw": (qty, "sum")}
            )
            g4["channel_total"] = g4.groupby("SalesType")["sales_raw"].transform("sum")
            g4 = g4[g4["sales_raw"] > 0].sort_values(["SalesType", "sales_raw"], ascending=[True, False])
            g4["rank"] = g4.groupby("SalesType").cumcount() + 1
            for _, r in g4[g4["rank"] <= 25].iterrows():
                pct = (r["sales_raw"] / r["channel_total"] * 100) if r["channel_total"] > 0 else 0
                rows_delivery.append({
                    "sales_type": web_text(r["SalesType"]),
                    "category": web_text(r["SubCat1"]),
                    "rank_in_group": int(r["rank"]),
                    "sales": self._d2(r["sales_raw"] / self.div),
                    "qty": self._d2(r["qty_raw"] / self.div),
                    "sales_pct": f"{pct:.1f}%",
                })
            top_deliv_cats = (
                deliv.groupby("SubCat1")[price].sum().sort_values(ascending=False).head(8)
            )
            chart_labels = [web_text(x) for x in top_deliv_cats.index]
            chart_values = [round(v / self.div, 2) for v in top_deliv_cats.values]

        digital = merged[
            merged["SalesType"].apply(self._is_delivery_type) | merged["SubChannel"].astype(str).str.strip().ne("")
        ].copy()
        digital = digital[digital["SubChannel"].astype(str).str.strip().ne("")]
        rows_digital_summary = []
        rows_digital_cats = []
        rows_digital_items = []
        digital_chart_labels, digital_chart_values = [], []
        digital_subchannels = []

        if not digital.empty:
            dig_total = float(digital[price].sum())
            sc_totals = digital.groupby("SubChannel")[price].sum().sort_values(ascending=False)
            digital_subchannels = [web_text(x) for x in sc_totals.index]

            top_cat_map = (
                digital.groupby(["SubChannel", "SubCat1"])[price].sum()
                .reset_index(name="cat_sales")
                .sort_values(["SubChannel", "cat_sales"], ascending=[True, False])
                .drop_duplicates("SubChannel", keep="first")
                .set_index("SubChannel")["SubCat1"]
            )
            item_counts = digital.groupby("SubChannel")[desc].nunique()

            for sc, sc_sales in sc_totals.items():
                sc_qty = float(digital.loc[digital["SubChannel"] == sc, qty].sum())
                pct = (sc_sales / dig_total * 100) if dig_total > 0 else 0
                rows_digital_summary.append({
                    "sub_channel": web_text(sc),
                    "sales": self._d2(sc_sales / self.div),
                    "qty": self._d2(sc_qty / self.div),
                    "unique_items": self._d0(item_counts.get(sc, 0)),
                    "top_category": web_text(top_cat_map.get(sc, "N/A")),
                    "sales_pct": f"{pct:.1f}%",
                })
            digital_chart_labels = [r["sub_channel"] for r in rows_digital_summary[:10]]
            digital_chart_values = [round(v / self.div, 2) for v in sc_totals.head(10).values]

            g_sc = digital.groupby(["SubChannel", "SubCat1"], as_index=False).agg(
                **{"sales_raw": (price, "sum"), "qty_raw": (qty, "sum")}
            )
            g_sc["sc_total"] = g_sc.groupby("SubChannel")["sales_raw"].transform("sum")
            g_sc = g_sc[g_sc["sales_raw"] > 0].sort_values(["SubChannel", "sales_raw"], ascending=[True, False])
            g_sc["rank"] = g_sc.groupby("SubChannel").cumcount() + 1
            for _, r in g_sc[g_sc["rank"] <= 25].iterrows():
                pct = (r["sales_raw"] / r["sc_total"] * 100) if r["sc_total"] > 0 else 0
                rows_digital_cats.append({
                    "sub_channel": web_text(r["SubChannel"]),
                    "category": web_text(r["SubCat1"]),
                    "rank_in_group": int(r["rank"]),
                    "sales": self._d2(r["sales_raw"] / self.div),
                    "qty": self._d2(r["qty_raw"] / self.div),
                    "sales_pct": f"{pct:.1f}%",
                })

            dig_items = digital.groupby(["SubChannel", desc, "SubCat1", "SubCat2"], as_index=False).agg(
                **{"sales_raw": (price, "sum"), "qty_raw": (qty, "sum")}
            )
            dig_items = dig_items.sort_values(["SubChannel", "sales_raw"], ascending=[True, False])
            dig_items["rank"] = dig_items.groupby("SubChannel").cumcount() + 1
            for _, r in dig_items[dig_items["rank"] <= 10].iterrows():
                rows_digital_items.append({
                    "sub_channel": web_text(r["SubChannel"]),
                    "rank_in_group": int(r["rank"]),
                    "item": web_text(r[desc]),
                    "category": web_text(r["SubCat1"]),
                    "subcategory": web_text(r["SubCat2"]),
                    "sales": self._d2(r["sales_raw"] / self.div),
                    "qty": self._d2(r["qty_raw"] / self.div),
                })

        insights = []
        if rows_type_cat:
            top = rows_type_cat[0]
            for st in sorted({r["sales_type"] for r in rows_type_cat}):
                st_rows = [r for r in rows_type_cat if r["sales_type"] == st and r["rank_in_group"] == 1]
                if st_rows:
                    insights.append(f"{st}: top category is {st_rows[0]['category']} ({st_rows[0]['sales_pct']} of type sales)")
        if delivery_types:
            insights.append(f"Delivery/Digital channels detected: {', '.join(web_text(t) for t in delivery_types)}")
        if digital_subchannels:
            insights.append(f"Digital sub-channels (Customer Name): {', '.join(digital_subchannels)}")
            if rows_digital_summary:
                top_sc = rows_digital_summary[0]
                insights.append(
                    f"Top digital sub-channel: {top_sc['sub_channel']} ({top_sc['sales_pct']} of digital sales)"
                )

        return {
            "ok": True,
            "insights": insights,
            "delivery_channels": [web_text(t) for t in delivery_types],
            "digital_subchannels": digital_subchannels,
            "has_customer_col": bool(self.p.c_customer),
            "sales_type_category": {
                "columns": ["sales_type", "category", "rank_in_group", "sales", "qty", "sales_pct"],
                "rows": rows_type_cat,
            },
            "category_subcategory": {
                "columns": ["category", "subcategory", "rank_in_group", "sales", "qty", "sales_pct"],
                "rows": rows_cat_sub,
            },
            "top_items_subcategory": {
                "columns": ["category", "subcategory", "rank_in_group", "item", "sales", "qty"],
                "rows": rows_top_items,
            },
            "delivery_categories": {
                "columns": ["sales_type", "category", "rank_in_group", "sales", "qty", "sales_pct"],
                "rows": rows_delivery,
            },
            "digital_subchannel_summary": {
                "columns": ["sub_channel", "sales", "qty", "unique_items", "top_category", "sales_pct"],
                "rows": rows_digital_summary,
            },
            "digital_subchannel_categories": {
                "columns": ["sub_channel", "category", "rank_in_group", "sales", "qty", "sales_pct"],
                "rows": rows_digital_cats,
            },
            "digital_subchannel_items": {
                "columns": ["sub_channel", "rank_in_group", "item", "category", "subcategory", "sales", "qty"],
                "rows": rows_digital_items,
            },
            "chart": {"labels": chart_labels, "values": chart_values},
            "digital_chart": {"labels": digital_chart_labels, "values": digital_chart_values},
        }

    def stagnant_analysis(self, master_df):
        df = self.p.df
        if df is None or master_df is None or master_df.empty:
            return []
        sales_grp = df.groupby(self.p.c_desc)[self.p.c_qty].sum().reset_index()
        sales_grp.columns = ["Description", "Qty_Sold"]
        merged = pd.merge(master_df, sales_grp, on="Description", how="left")
        merged["Qty_Sold"] = merged["Qty_Sold"].fillna(0)
        rows = []
        for (cat1, cat2, granular), group in merged.groupby(["SubCat1", "SubCat2", "GranularCat"]):
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
                    "alt_qty": self._d0(top_seller["Qty_Sold"]),
                    "group_match": web_text(f"{cat1} -> {granular}"),
                })
        return rows

    def build_snapshot_excel(self):
        import io
        gs = self.get_global_stats()
        self._emp_metrics()
        meta_df = pd.DataFrame([{
            "Branch": str(self.p.branch_name),
            "Start Date": self.p.period_info.get("start", "N/A"),
            "End Date": self.p.period_info.get("end", "N/A"),
            "Days Count": self.p.period_info.get("days", 1),
            "Global Sales": gs.get("Total Sales", 0),
            "Global Receipts": gs.get("Total Receipts", 0),
            "Global Avg Receipt": gs.get("Avg Receipt", 0),
            "Global Pcs": gs.get("Total Pieces", 0),
        }])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            meta_df.to_excel(writer, sheet_name="Global_Metadata", index=False)
            self._emp_stats_cache.to_excel(writer, sheet_name="Employees_Data", index=False)
        buf.seek(0)
        return buf
