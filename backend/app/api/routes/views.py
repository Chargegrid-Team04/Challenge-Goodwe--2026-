from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "paginas"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={}
    )

@router.get("/mapa", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="mapa.html", 
        context={}
    )

@router.get("/carregando", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="carregando.html", 
        context={}
    )

@router.get("/pagamento", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="pagamento.html", 
        context={}
    )

@router.get("/posto", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="posto.html", 
        context={}
    )

@router.get("/perfil", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="perfil.html", 
        context={}
    )

@router.get("/recarga", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="recarga.html", 
        context={}
    )