import io
import pandas as pd
from core.data_processor import DataProcessor
from core.analytics import AnalyticsService

_user_sessions = {}


def get_user_state(user_id: int):
    if user_id not in _user_sessions:
        proc = DataProcessor()
        _user_sessions[user_id] = {
            "processor": proc,
            "analytics": AnalyticsService(proc),
            "filters": {},
            "daily_avg": False,
            "filter_options": {},
        }
    return _user_sessions[user_id]


def load_file(user_id: int, content: bytes, filename: str):
    state = get_user_state(user_id)
    if filename.lower().endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), encoding="windows-1256")
    else:
        df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    opts = state["processor"].load_dataframe(df)
    state["filter_options"] = opts
    state["filters"] = {
        "start_date": opts.get("period", {}).get("start"),
        "end_date": opts.get("period", {}).get("end"),
        "employees": opts.get("employees", []),
        "branches": opts.get("branches", []),
        "shifts": opts.get("shifts", []),
        "categories": opts.get("categories", []),
        "materials": opts.get("materials", []),
    }
    state["analytics"] = AnalyticsService(state["processor"])
    apply_user_filters(user_id, state["filters"], state["daily_avg"])
    return opts


def apply_user_filters(user_id: int, filters: dict, daily_avg: bool = False):
    state = get_user_state(user_id)
    state["filters"] = filters
    state["daily_avg"] = daily_avg
    state["processor"].apply_filters(
        start_date=filters.get("start_date"),
        end_date=filters.get("end_date"),
        employees=filters.get("employees"),
        branches=filters.get("branches"),
        shifts=filters.get("shifts"),
        categories=filters.get("categories"),
        materials=filters.get("materials"),
    )
    state["analytics"].set_divisor(daily_avg)


def get_dashboard_data(user_id: int):
    state = get_user_state(user_id)
    proc = state["processor"]
    ana = state["analytics"]
    if proc.df is None or proc.df.empty:
        return {"has_data": False}
    kpis = proc.get_kpis(state["daily_avg"])
    emp_overview = ana.employee_performance("overview")
    emp_ai = ana.employee_performance("ai")
    emp_sales = ana.employee_performance("sales_types")
    emp_eff = ana.employee_performance("efficiency")
    dates = state["filter_options"].get("dates", [])
    return {
        "has_data": True,
        "kpis": kpis,
        "branch_name": proc.branch_name,
        "material_chart": ana.chart_material_groups(),
        "hourly_chart": ana.chart_hourly_sales(),
        "shift_chart": ana.chart_shift_sales(),
        "category_chart": ana.chart_category_pie(),
        "top_products_chart": ana.chart_top_products_qty(),
        "top_employees": ana.top_employees(),
        "top_products": ana.top_products(150),
        "employee_overview": emp_overview,
        "employee_ai": emp_ai,
        "employee_sales_types": emp_sales,
        "employee_efficiency": emp_eff,
        "executive": ana.executive_summary(),
        "filter_options": state["filter_options"],
        "filters": state["filters"],
        "daily_avg": state["daily_avg"],
        "valid_dates": dates,
    }
