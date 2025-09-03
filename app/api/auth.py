# app/api/auth.py
from fastapi import APIRouter, Request, Form, status, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import timedelta
from starlette.responses import StreamingResponse
import sqlite3, io, qrcode

from app import auth_utils
from app.config import settings

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory=settings.TEMPLATES_PATH)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await auth_utils.get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    # return templates.TemplateResponse("login.html", {"request": request})
    response = templates.TemplateResponse("login.html", {"request": request})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@router.post("/login", response_class=HTMLResponse)
async def login_form_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = auth_utils.get_user(username)
    if not user or not auth_utils.verify_password(password, user["hashed_password"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Incorrect username or password"})

    if user.get("is_two_factor_enabled"):
        temp_token = auth_utils.create_access_token(
            data={"sub": user["username"], "type": "pre-2fa"}, 
            expires_delta=timedelta(minutes=5)
        )
        response = RedirectResponse(url="/login/verify-2fa", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="temp_token", value=f"Bearer {temp_token}", httponly=True, samesite="strict", path="/")
        return response
    else:
        access_token = auth_utils.create_access_token(data={"sub": user["username"]}, expires_delta=timedelta(minutes=auth_utils.settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, samesite="strict", path="/")
        return response

@router.get("/login/verify-2fa", response_class=HTMLResponse)
async def get_verify_2fa_page(request: Request):
    response = templates.TemplateResponse("verify_2fa.html", {"request": request})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@router.post("/login/verify-2fa", response_class=HTMLResponse)
async def post_verify_2fa_page(request: Request, code: str = Form(...)):
    temp_token = request.cookies.get("temp_token")
    if not temp_token:
        return RedirectResponse(url="/login")
    
    try:
        payload = jwt.decode(temp_token.split(" ")[1], auth_utils.settings.SECRET_KEY, algorithms=[auth_utils.settings.ALGORITHM])
        if payload.get("type") != "pre-2fa": raise JWTError
        username = payload.get("sub")
        if not isinstance(username, str) or not username:
            return RedirectResponse(url="/login")
        user = auth_utils.get_user(username)
    except JWTError:
        return RedirectResponse(url="/login")

    if not user or not user.get("two_factor_secret") or not auth_utils.verify_2fa_code(user["two_factor_secret"], code):
        return templates.TemplateResponse("verify_2fa.html", {"request": request, "error": "Invalid code. Please try again."})

    access_token = auth_utils.create_access_token(data={"sub": user["username"]}, expires_delta=timedelta(minutes=auth_utils.settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, samesite="strict", path="/")
    response.delete_cookie(key="temp_token", path="/")
    return response

@router.get("/security", response_class=HTMLResponse)
async def security_page(request: Request):
    user = await auth_utils.get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    
    context = {"request": request, "user": user}
    if not user.get("is_two_factor_enabled"):
        secret = auth_utils.generate_2fa_secret()
        request.session['2fa_secret'] = secret
        context["secret_key"] = secret
    response = templates.TemplateResponse("security.html", context)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@router.get("/security/2fa/qr-code", response_class=StreamingResponse)
async def get_2fa_qr_code(request: Request):
    secret = request.session.get('2fa_secret')
    user = await auth_utils.get_current_user(request)
    if not secret or not user:
        raise HTTPException(status_code=400, detail="Could not generate QR code.")

    uri = auth_utils.get_2fa_provisioning_uri(user["username"], secret)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@router.post("/security/2fa/enable")
async def enable_2fa(request: Request, code: str = Form(...)):
    user = await auth_utils.get_current_user(request)
    secret_key = request.session.get('2fa_secret')
    if not user or not secret_key:
        return RedirectResponse(url="/login")

    if auth_utils.verify_2fa_code(secret_key, code):
        conn = sqlite3.connect(settings.DATABASE_URL, timeout=10)
        conn.execute("UPDATE users SET two_factor_secret = ?, is_two_factor_enabled = 1 WHERE id = ?", (secret_key, user["id"]))
        conn.commit()
        conn.close()
        return RedirectResponse(url="/security", status_code=status.HTTP_303_SEE_OTHER)
    else:
        context = {"request": request, "user": user, "secret_key": secret_key, "error": "Invalid code. Please try again."}
        # return templates.TemplateResponse("security.html", context)
        response = templates.TemplateResponse("security.html", context)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

@router.post("/security/2fa/disable")
async def disable_2fa(request: Request):
    user = await auth_utils.get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
        
    conn = sqlite3.connect(settings.DATABASE_URL, timeout=10)
    conn.execute("UPDATE users SET two_factor_secret = NULL, is_two_factor_enabled = 0 WHERE id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/security", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="temp_token", path="/")
    return response
