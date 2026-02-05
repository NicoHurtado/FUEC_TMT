"""
Router de Autenticación - Login por Código Único
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import secrets
import string

from database import get_session
from models.user import User
from config import SECRET_KEY

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Serializer para sesiones
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Nombre de la cookie de sesión
SESSION_COOKIE = "fuec_session"


def generate_access_code(length: int = 6) -> str:
    """Generar código de acceso único alfanumérico"""
    characters = string.ascii_uppercase + string.digits
    # Evitar caracteres confusos (0, O, I, 1, L)
    characters = characters.replace('0', '').replace('O', '').replace('I', '').replace('1', '').replace('L', '')
    return ''.join(secrets.choice(characters) for _ in range(length))


def create_session_token(user_id: int, role: str) -> str:
    """Crear token de sesión"""
    return serializer.dumps({"user_id": user_id, "role": role})


def verify_session_token(token: str) -> dict | None:
    """Verificar token de sesión"""
    try:
        data = serializer.loads(token, max_age=86400)  # 24 horas
        return data
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request, db: Session = Depends(get_session)) -> User | None:
    """Obtener usuario actual desde la sesión"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    
    data = verify_session_token(token)
    if not data:
        return None
    
    user = db.get(User, data["user_id"])
    if not user or not user.is_active:
        return None
    
    return user


def require_auth(request: Request, db: Session = Depends(get_session)) -> User:
    """Requerir autenticación"""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")
    return user


def require_admin(request: Request, db: Session = Depends(get_session)) -> User:
    """Requerir rol de administrador"""
    user = require_auth(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user


def require_conductor(request: Request, db: Session = Depends(get_session)) -> User:
    """Requerir rol de conductor"""
    user = require_auth(request, db)
    if user.role != "conductor":
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return user


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, db: Session = Depends(get_session)):
    """Página de login unificada"""
    # Si ya está autenticado, redirigir
    user = get_current_user(request, db)
    if user:
        if user.role == "admin":
            return RedirectResponse(url="/admin", status_code=302)
        else:
            return RedirectResponse(url="/app", status_code=302)
    
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error}
    )


@router.post("/login")
async def login(
    request: Request,
    codigo: str = Form(...),
    db: Session = Depends(get_session)
):
    """
    Login por Código Único.
    
    El código es único para cada usuario (admin o conductor).
    No requiere contraseña.
    """
    # Normalizar código (mayúsculas, sin espacios)
    codigo = codigo.strip().upper()
    
    # Buscar usuario por código de acceso
    statement = select(User).where(User.access_code == codigo)
    user = db.exec(statement).first()
    
    # Validar que existe
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Código de acceso inválido"
            },
            status_code=401
        )
    
    # Verificar si está activo
    if not user.is_active:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Su cuenta ha sido desactivada. Contacte al administrador."
            },
            status_code=403
        )
    
    # Crear sesión
    token = create_session_token(user.id, user.role)
    
    # Redirigir según rol
    if user.role == "admin":
        response = RedirectResponse(url="/admin", status_code=302)
    else:
        response = RedirectResponse(url="/app", status_code=302)
    
    # Establecer cookie de sesión
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        max_age=86400,  # 24 horas
        samesite="lax"
    )
    
    return response


@router.get("/logout")
async def logout(request: Request):
    """Cerrar sesión"""
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response
