from collections import defaultdict
from datetime import date, datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from bot.handlers import telegram_webhook
from db.db import init_db, get_summary_by_period, execute_query, editar_transacao

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
    inicio = inicio or "2025-01-01"
    fim = fim or datetime.today().strftime("%Y-%m-%d")
    dados = get_summary_by_period(user_id, inicio, fim)

    total_receitas = 0
    total_despesas = 0
    por_categoria = defaultdict(float)
    por_dia = defaultdict(float)

    for tipo, descricao, categoria, valor, data, id in dados:
        if not isinstance(valor, float):
            valor = float(valor)
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
    
@app.get("/admin/sql", response_class=HTMLResponse)
async def form_sql(request: Request, msg: str = "", error: str = ""):
    return templates.TemplateResponse("sql_console.html", {
        "request": request,
        "msg": msg,
        "error": error
    })

@app.post("/admin/sql", response_class=HTMLResponse)
async def execute_sql(request: Request, query: str = Form(...)):
    try:
        results = execute_query(query)
        msg = f"✅ Query executada com sucesso. {len(results)} resultado(s)." if results else "✅ Query executada com sucesso."
        if results:
            msg += "<br><pre>" + "\n".join(str(r) for r in results) + "</pre>"
        return templates.TemplateResponse("sql_console.html", {
            "request": request,
            "msg": msg,
            "error": ""
        })
    except Exception as e:
        return templates.TemplateResponse("sql_console.html", {
            "request": request,
            "msg": "",
            "error": f"❌ Erro ao executar a query: {str(e)}"
        })

@app.put("/api/editar_transacao/{id}")
async def editar_transacao_endpoint(id: int, request: Request):
    try:
        data = await request.json()
        tipo = data.get("tipo")
        descricao = data.get("descricao")
        categoria = data.get("categoria")
        valor = data.get("valor")
        data_transacao = data.get("data")

        if not all([tipo, descricao, categoria, valor, data_transacao]):
            raise HTTPException(status_code=400, detail="Campos obrigatórios ausentes.")

        linhas_afetadas = editar_transacao(id, tipo, descricao, categoria, valor, data_transacao)

        if linhas_afetadas == 0:
            return {"mensagem": "Nenhuma alteração detectada. Transação permanece igual."}
            # raise HTTPException(status_code=404, detail="Transação não encontrada.")

        return {"mensagem": "Transação atualizada com sucesso."}

    except Exception as e:
        print("Erro:", e)
        raise HTTPException(status_code=500, detail="Erro ao atualizar transação.")
    

# Para rodar localmente: python -m uvicorn app:app --host 0.0.0.0 --port 8443
# ngrok http 8443