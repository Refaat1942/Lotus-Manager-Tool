import os
import io
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from web_app.database import (
    init_db, verify_user, get_branding, update_branding,
    list_users, create_user, update_user, delete_user, import_master_items,
    get_master_df, change_user_password, UPLOAD_DIR,
)
from web_app.auth import create_session, get_session, require_login, require_role
from web_app.i18n import t
from web_app.session_store import load_file, apply_user_filters, get_dashboard_data, get_user_state
from core.utils import decrypt_master_file
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = os.environ.get("APP_VERSION", "20260706.8")
app = FastAPI(title="Lotus Manager Tool Web")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "lotus-web-secret-change-me-2026"))

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

init_db()


def ctx(request: Request, **extra):
    lang = request.cookies.get("lang", "en")
    branding = get_branding()
    session = get_session(request)
    return {
        "request": request,
        "lang": lang,
        "rtl": lang == "ar",
        "branding": branding,
        "session": session,
        "t": lambda k: t(lang, k, branding),
        "app_version": APP_VERSION,
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if get_session(request):
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_session(request):
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("login.html", ctx(request))


@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    user = verify_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", ctx(request, error="Invalid credentials"))
    sid = create_session(user)
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.set_cookie("session_id", sid, httponly=True, max_age=86400 * 7)
    return resp


@app.get("/logout")
async def logout(request: Request):
    sid = request.cookies.get("session_id")
    from web_app.auth import SESSIONS
    if sid and sid in SESSIONS:
        del SESSIONS[sid]
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session_id")
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
@require_login
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", ctx(request))


@app.get("/admin", response_class=HTMLResponse)
@require_login
@require_role("admin")
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", ctx(request, users=list_users()))


@app.post("/api/upload-data")
@require_login
async def upload_data(request: Request, file: UploadFile = File(...)):
    session = get_session(request)
    content = await file.read()
    try:
        opts = load_file(session["id"], content, file.filename)
        return JSONResponse({"ok": True, "options": opts})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/upload-master")
@require_login
@require_role("admin", "manager")
async def upload_master(request: Request, file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    try:
        data_list = decrypt_master_file(content)
        import_master_items(data_list)
        return JSONResponse({"ok": True, "count": len(data_list)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/filters")
@require_login
async def set_filters(request: Request):
    session = get_session(request)
    body = await request.json()
    apply_user_filters(session["id"], body.get("filters", {}), body.get("daily_avg", False))
    return JSONResponse({"ok": True, "data": get_dashboard_data(session["id"])})


@app.get("/api/dashboard-data")
@require_login
async def dashboard_data(request: Request):
    session = get_session(request)
    return JSONResponse(get_dashboard_data(session["id"]))


@app.get("/api/deep-sales")
@require_login
async def deep_sales_data(request: Request):
    session = get_session(request)
    state = get_user_state(session["id"])
    proc = state["processor"]
    if proc.df is None or proc.df.empty:
        return JSONResponse({"ok": False, "error": "Load sales data first."})
    master_df = get_master_df()
    if master_df is None or master_df.empty:
        return JSONResponse({"ok": False, "error": "Upload master data (.lotusdb) first."})
    try:
        state["analytics"].set_divisor(state["daily_avg"])
        result = state["analytics"].deep_sales_analysis(master_df)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/stagnant")
@require_login
async def stagnant_data(request: Request):
    session = get_session(request)
    state = get_user_state(session["id"])
    master_df = get_master_df()
    state["analytics"].set_divisor(state["daily_avg"])
    rows = state["analytics"].stagnant_analysis(master_df)
    return JSONResponse({"rows": rows})


@app.post("/api/employee/{mode}")
@require_login
async def employee_mode(mode: str, request: Request):
    session = get_session(request)
    state = get_user_state(session["id"])
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    if mode == "subcategories":
        pwd = body.get("password", "")
        user = verify_user(session["username"], pwd)
        if not user:
            return JSONResponse({"ok": False, "error": "Password required for subcategories analysis"}, status_code=403)
    state["analytics"].set_divisor(state["daily_avg"])
    master_df = get_master_df() if mode == "subcategories" else None
    try:
        data = state["analytics"].employee_performance(mode, master_df)
        return JSONResponse({"ok": True, "data": data})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/date-compare")
@require_login
async def date_compare(request: Request):
    session = get_session(request)
    state = get_user_state(session["id"])
    body = await request.json()
    state["analytics"].set_divisor(state["daily_avg"])
    result = state["analytics"].date_compare(
        body.get("p1_start"), body.get("p1_end"),
        body.get("p2_start"), body.get("p2_end"),
        body.get("mode", "hourly"),
    )
    return JSONResponse(result)


@app.post("/api/trend-compare")
@require_login
async def trend_compare(request: Request, file: UploadFile = File(...)):
    session = get_session(request)
    state = get_user_state(session["id"])
    if state["processor"].df is None:
        return JSONResponse({"ok": False, "error": "Load current data first"}, status_code=400)
    try:
        content = await file.read()
        history_emp = pd.read_excel(io.BytesIO(content), sheet_name="Employees_Data")
        history_meta = pd.read_excel(io.BytesIO(content), sheet_name="Global_Metadata")
        state["analytics"].set_divisor(state["daily_avg"])
        result = state["analytics"].trend_compare(history_emp, history_meta)
        return JSONResponse({"ok": True, "data": result})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.get("/api/export/snapshot")
@require_login
async def export_snapshot(request: Request):
    session = get_session(request)
    state = get_user_state(session["id"])
    if state["processor"].df is None:
        raise HTTPException(400, "No data loaded")
    state["analytics"].set_divisor(state["daily_avg"])
    buf = state["analytics"].build_snapshot_excel()
    fname = f"Snapshot_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/api/export/table")
@require_login
async def export_table(request: Request):
    import pandas as pd
    body = await request.json()
    headers = body.get("headers", [])
    rows = body.get("rows", [])
    sheet = body.get("sheet_name", "Data")
    df = pd.DataFrame(rows, columns=headers)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name=sheet[:31])
    buf.seek(0)
    fname = f"{sheet}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/api/change-password")
@require_login
async def change_password(request: Request):
    session = get_session(request)
    body = await request.json()
    ok, msg = change_user_password(session["id"], body.get("old_password", ""), body.get("new_password", ""))
    if not ok:
        return JSONResponse({"ok": False, "error": msg}, status_code=400)
    return JSONResponse({"ok": True, "message": msg})


@app.post("/api/users")
@require_login
@require_role("admin")
async def add_user(request: Request):
    body = await request.json()
    ok, msg = create_user(body["username"], body["password"], body.get("role", "viewer"), body.get("full_name", ""))
    if not ok:
        raise HTTPException(400, msg)
    return JSONResponse({"ok": True})


@app.put("/api/users/{user_id}")
@require_login
@require_role("admin")
async def edit_user(user_id: int, request: Request):
    body = await request.json()
    update_user(user_id, role=body.get("role"), full_name=body.get("full_name"),
                is_active=body.get("is_active"), password=body.get("password"))
    return JSONResponse({"ok": True})


@app.delete("/api/users/{user_id}")
@require_login
@require_role("admin")
async def remove_user(user_id: int, request: Request):
    delete_user(user_id)
    return JSONResponse({"ok": True})


@app.post("/api/branding")
@require_login
@require_role("admin")
async def save_branding(request: Request):
    form = await request.form()
    data = {k: form.get(k) for k in form.keys() if k != "logo"}
    update_branding(**data)
    logo = form.get("logo")
    if logo and hasattr(logo, "filename") and logo.filename:
        ext = Path(logo.filename).suffix or ".png"
        dest = UPLOAD_DIR / f"logo{ext}"
        with open(dest, "wb") as f:
            f.write(await logo.read())
        update_branding(logo_path=f"/static/uploads/logo{ext}")
    return RedirectResponse("/admin?saved=1", status_code=303)


@app.get("/api/set-lang/{lang}")
async def set_lang(lang: str, request: Request):
    if lang not in ("en", "ar"):
        lang = "en"
    referer = request.headers.get("referer", "/dashboard")
    resp = RedirectResponse(referer, status_code=303)
    resp.set_cookie("lang", lang, max_age=86400 * 365)
    return resp
