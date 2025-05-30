import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from .openrouter_client import query_openrouter
from db import (
    save_message, get_user_history, save_transaction, parse_transaction,
    get_summary_by_period, get_total_by_category, clear_user_data,
    set_budget, get_budgets_with_spending, search_transactions, get_transactions_by_category
)
from utils.formatters import format_resumo, format_total_by_category
from dotenv import load_dotenv
from datetime import date, datetime, timedelta

load_dotenv()

BASE_URL = os.environ.get("WEBHOOK_URL")

# Prompt inicial
SYSTEM_PROMPT = """
Você é Finno, um assistente financeiro pessoal inteligente, proativo e gente boa. Seu papel é ajudar o usuário a registrar, entender e melhorar suas finanças com linguagem simples, clara, divertida e visual.
Sempre apresente-se primeiro em saudações.

Quando o usuário enviar uma mensagem que seja uma transação de receita ou despesa (tenha certeza que seja uma transação para enviar essa resposta):
1. Se parecer uma movimentação financeira (ex: "Mercado 120", "Recebi 1000"), extraia e retorne:
  - Valor (R$ x,xx)
  - Descrição
  - Categoria (ex: Alimentação, Transporte, Lazer, etc.)
  - Tipo: Despesa ou Receita
  - Data (assuma hoje, no formato dd/mm/yyyy)

Formato da resposta:
✅ Nova movimentação **registrada**!

💸 Tipo: ...
🧾 Item: ...
🗂️ Categoria: ...
💰 Valor: ...
📅 Data: ...

💡 Dica do Finno: Uma dica inteligente, divertida ou educativa sobre finanças pessoais. Use exemplos e emojis.

2. Se for uma pergunta sobre finanças (ex: “Como economizar no mercado?” ou “Como funciona o CDI?”), responda como um consultor financeiro simpático, didático e confiável. Use linguagem leve e divertida, com exemplos práticos e emojis para facilitar o entendimento.

3. Se não entender a mensagem, peça para o usuário reformular, de forma educada e divertida. Exemplo: "Eita! 😅 Não entendi muito bem... tenta mandar de outro jeito? Finno tá ligado, mas não faz milagre! 💡"

5. Para definir a categoria de uma movimentação, use este mapeamento como referência:

Alimentação: mercado, restaurante, comida, lanche, pizza, padaria
Transporte: uber, gasolina, ônibus, metrô, combustível
Saúde: remédio, consulta, psicólogo, dentista, farmácia
Beleza: cabelereiro, manicure, barbearia, salão, maquiagem
Moradia: aluguel, luz, água, energia, condomínio, internet
Lazer: cinema, show, netflix, viagem, festa, jogo
Educação: faculdade, curso, livro, apostila
Vestuário: roupa, tênis, calçado, camisa, vestuário

- Se não encontrar correspondência, use o bom senso com base na descrição e evite categorizações genéricas como "Lazer".
- Se ainda estiver incerto, escolha "Outros" como categoria segura.

6. Caso, mas somente caso, seja perguntado sobre comando(s), diga para digitar /start para visualizar os comandos e instruções disponíveis.

Regras:
- Seja breve, visual e leve.
- Use linguagem informal mas respeitosa.
- Sempre use emojis apropriados para facilitar leitura.
- Nunca diga que é uma IA — você é o Finno, ponto.
- Nunca responda de forma robótica ou seca.
- Procure ser o mais breve possível em suas respostas.
"""
MAX_HISTORY = 10

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! 👋 Sou o Finno, seu assistente financeiro pessoal.\n"
        "Me envie uma movimentação como \"Mercado 120\" ou \"Ganhei 500\", ou pergunte algo sobre finanças!\n"
        "Use /resumo para um resumo das suas movimentações\n"
        "Use /relatorio para acessar um relatorio completo de suas finanças"
        "Use /orcamento para visualizar saldo disponível por categoria ou /orcamento categoria valor para definir um limite "
        "Use /buscar para pesquisar um item ou categoria"
        "Use /limpar para zerar sua base de dados (Cuidado)"
        "Use /total para visualizar o total de gastos por categoria"
    )

async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_message = update.message.text.strip()
    
    data_hoje = date.today().strftime('%d-%m-%Y')

    save_message(user_id, "user", user_message)
    history = get_user_history(user_id, MAX_HISTORY)
    history.insert(0, {"role": "system", "content": f"Hoje é dia {data_hoje}.{SYSTEM_PROMPT}"})

    try:
        reply = query_openrouter(history)
        save_message(user_id, "assistant", reply)

        extracted = parse_transaction(reply)
        if extracted:
            save_transaction(user_id, **extracted)

            # Verifica se atingiu/ultrapassou orçamento
            from db import check_budget_warnings
            avisos = check_budget_warnings(user_id)
            for aviso in avisos:
                await update.message.reply_text(aviso, parse_mode=ParseMode.MARKDOWN)

        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await update.message.reply_text(f"❌ Ocorreu um erro: {e}")

async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    if not args:
        await update.message.reply_text("❓ Use /resumo hoje | semana | mes | ou informe datas: /resumo dd/mm/yyyy a dd/mm/yyyy")
        return

    texto = " ".join(args).lower()
    hoje = datetime.now().date()

    try:
        if texto == "hoje":
            inicio = fim = hoje
        elif texto == "semana":
            inicio = hoje - timedelta(days=7)
            fim = hoje
        elif texto == "mes":
            inicio = hoje.replace(day=1)
            fim = hoje
        elif " a " in texto:
            try:
                partes = texto.split(" a ")
                inicio = datetime.strptime(partes[0], "%d/%m/%Y").date()
                fim = datetime.strptime(partes[1], "%d/%m/%Y").date()
            except:
                await update.message.reply_text("⚠️ Datas inválidas. Use o formato: /resumo 01/05/2025 a 15/05/2025")
                return
        else:
            await update.message.reply_text("❓ Período não reconhecido. Use hoje, semana, mes ou datas personalizadas.")
            return
    except:
        await update.message.reply_text("🤔 Período não reconhecido. Use datas personalizadas.")
        return

    resumo = get_summary_by_period(user_id, inicio, fim)
    await update.message.reply_text(format_resumo(resumo), parse_mode=ParseMode.MARKDOWN)

async def total_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    total = get_total_by_category(user_id)
    await update.message.reply_text(format_total_by_category(total), parse_mode=ParseMode.MARKDOWN)

async def limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if context.args and context.args[0].lower() == "confirmar":
        clear_user_data(user_id)
        await update.message.reply_text("📉 Histórico apagado com sucesso!")
    else:
        await update.message.reply_text("⚠️ Confirme com: /limpar confirmar")

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = f"{BASE_URL}/relatorio?user={user_id}"
    keyboard = [
        [InlineKeyboardButton("📊 Acessar Relatório", url=url)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Clique no botão abaixo para acessar seu relatório financeiro:",
        reply_markup=reply_markup
    )
    
async def orcamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args

    if len(args) == 2:
        categoria = args[0].capitalize()
        try:
            limite = float(args[1].replace(",", "."))
            set_budget(user_id, categoria, limite)
            await update.message.reply_text(
                f"📌 Limite de R$ {limite:.2f} definido para *{categoria}*".replace(".", ","),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            await update.message.reply_text("⚠️ Valor inválido. Use: /orcamento Alimentação 800")
        return
    elif len(args) == 1:
        await update.message.reply_text("⚠️ Valor inválido. Use: /orcamento Alimentação 800")
        return

    # Listar orçamentos e gastos do mês
    rows = get_budgets_with_spending(user_id)
    if not rows:
        await update.message.reply_text("📋 Nenhum orçamento definido ainda. Use: /orcamento Categoria Limite")
        return

    resposta = "📊 *Orçamentos do mês:*\n\n"
    for categoria, limite, gasto in rows:
        perc = gasto / limite * 100 if limite > 0 else 0
        emoji = "🟢"
        if perc >= 100:
            emoji = "🔴"
        elif perc >= 80:
            emoji = "🟠"
        resposta += f"{emoji} *{categoria}*: R$ {gasto:.2f} / R$ {limite:.2f} ({perc:.0f}%)\n".replace(".", ",")

    await update.message.reply_text(resposta, parse_mode=ParseMode.MARKDOWN)
    
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    if not args:
        await update.message.reply_text("❓ Use:\n- /buscar mercado\n- /buscar categoria Alimentação")
        return

    termo = " ".join(args).strip()

    # Se for uma busca por categoria
    if termo.lower().startswith("categoria "):
        categoria = termo[10:].strip()
        transacoes = get_transactions_by_category(user_id, categoria)

        if not transacoes:
            await update.message.reply_text(f"📂 Nenhuma transação encontrada para a categoria: *{categoria}*", parse_mode=ParseMode.MARKDOWN)
            return

        total = sum([t[2] for t in transacoes if t[0].lower() == "despesa"])
        resposta = f"📊 *Resumo da categoria:* _{categoria}_ (mês atual)\n"
        resposta += f"💸 Total gasto: R$ {total:.2f}\n\n".replace(".", ",")

        for tipo, descricao, valor, data in transacoes:
            emoji = "💰" if tipo.lower() == "receita" else "💸"
            resposta += f"{emoji} {descricao} - R$ {valor:.2f} em {data}\n".replace(".", ",")

        await update.message.reply_text(resposta.strip(), parse_mode=ParseMode.MARKDOWN)
        return

    # Busca padrão por palavra-chave
    termo = termo.lower()
    resultados = search_transactions(user_id, termo)

    if not resultados:
        await update.message.reply_text(f"🔍 Nada encontrado para: *{termo}*", parse_mode=ParseMode.MARKDOWN)
        return

    resposta = f"🔎 Resultados para: *{termo}*\n\n"
    for tipo, descricao, categoria, valor, data in resultados:
        emoji = "💰" if tipo.lower() == "receita" else "💸"
        resposta += (
            f"{emoji} *{descricao}* - R$ {valor:.2f}\n"
            f"📅 {data} | 🗂️ {categoria} | {tipo}\n\n"
        ).replace(".", ",")

    await update.message.reply_text(resposta.strip(), parse_mode=ParseMode.MARKDOWN)
