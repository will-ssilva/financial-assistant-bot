from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from bot.handlers import telegram_webhook
from db import init_db

from fastapi.middleware.cors import CORSMiddleware
from db import get_summary_by_period, get_total_by_category
from datetime import datetime
from collections import defaultdict
from datetime import date

load_dotenv()
init_db()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/")
async def handle_webhook(request: Request):
    data = await request.body()
    await telegram_webhook(data.decode("utf-8"))
    return {"ok": True}

@app.get("/check")
async def check():
    return {"status": "✅ Bot financeiro rodando com FastAPI!"}

@app.get("/relatorio", response_class=HTMLResponse)
async def relatorios(request: Request, user: int = 1586721273):  # ← permite trocar user pela URL
    hoje = date.today()
    dados = get_summary_by_period(user, "2025-01-01", hoje.isoformat())
    return templates.TemplateResponse("relatorio.html", {
        "request": request,
        "transacoes": dados,
        "user_id": user
    })

@app.get("/api/relatorio/{user_id}")
async def api_relatorio(user_id: int = 1586721273, inicio: str = None, fim: str = None):
    inicio = inicio or "2000-01-01"
    fim = fim or datetime.today().strftime("%Y-%m-%d")
    dados = get_summary_by_period(user_id, inicio, fim)

    total_receitas = 0
    total_despesas = 0
    por_categoria = defaultdict(float)
    por_dia = defaultdict(float)

    for tipo, descricao, categoria, valor, data in dados:
        tipo = tipo.lower()
        if tipo == "receita":
            total_receitas += valor
        elif tipo == "despesa":
            total_despesas += valor
            por_categoria[categoria] += valor
            data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m")
            por_dia[data_formatada] += valor

    saldo = total_receitas - total_despesas

    return JSONResponse({
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "saldo": saldo,
        "por_categoria": dict(por_categoria),
        "por_dia": [{"data": d, "valor": v} for d, v in sorted(por_dia.items())]
    })


# Para rodar localmente: python -m uvicorn app:app --host 0.0.0.0 --port 8443
# ngrok http 8443