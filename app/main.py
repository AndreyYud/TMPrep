from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.core.config import settings
from app.api.v1 import router as api_router
from app.core.database import engine, Base

app = FastAPI(title="ОСВ-Анализ")
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)

# Добавляем фильтр для форматирования чисел
def number_format(value, decimals=2):
    """Форматирует число с разделением разрядов пробелами и заданным количеством знаков после запятой."""
    if value is None:
        return "0,00"
    try:
        # Округляем до decimals знаков
        formatted = f"{value:,.{decimals}f}"
        # Заменяем запятые на пробелы (для разделения тысяч)
        formatted = formatted.replace(",", " ")
        # Заменяем десятичную точку на запятую (для русского формата)
        formatted = formatted.replace(".", ",")
        return formatted
    except (TypeError, ValueError):
        return str(value)

templates.env.filters['number_format'] = number_format

if settings.STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

app.include_router(api_router, prefix="/api")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.get("/periods", response_class=HTMLResponse)
async def periods_page(request: Request):
    return templates.TemplateResponse("periods.html", {"request": request})

@app.get("/report/{org_inn}/{period_date}", response_class=HTMLResponse)
async def report_page(request: Request, org_inn: str, period_date: str):
    return templates.TemplateResponse(
        "report_detail.html",
        {"request": request, "org_inn": org_inn, "period_date": period_date}
    )

@app.get("/organizations", response_class=HTMLResponse)
async def organizations_page(request: Request):
    return templates.TemplateResponse("organizations.html", {"request": request})

@app.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    return templates.TemplateResponse("accounts.html", {"request": request})

@app.get("/org-types", response_class=HTMLResponse)
async def org_types_page(request: Request):
    return templates.TemplateResponse("org_types.html", {"request": request})

@app.get("/balance", response_class=HTMLResponse)
async def balance_page(request: Request):
    return templates.TemplateResponse("balance.html", {"request": request})

@app.get("/balance-rules", response_class=HTMLResponse)
async def balance_rules_page(request: Request):
    return templates.TemplateResponse("balance_rules.html", {"request": request})

@app.get("/balance-sections", response_class=HTMLResponse)
async def balance_sections_page(request: Request):
    return templates.TemplateResponse("balance_sections.html", {"request": request})

@app.get("/balance-subsections", response_class=HTMLResponse)
async def balance_subsections_page(request: Request):
    return templates.TemplateResponse("balance_subsections.html", {"request": request})

@app.get("/consolidated-balance", response_class=HTMLResponse)
async def consolidated_balance_page(request: Request):
    return templates.TemplateResponse("consolidated_balance.html", {"request": request})

@app.get("/internal-balance", response_class=HTMLResponse)
async def internal_balance_page(request: Request):
    return templates.TemplateResponse("internal_balance.html", {"request": request})
