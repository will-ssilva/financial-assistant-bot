import locale
from datetime import datetime, date

def format_total_by_category(data):
    if not data:
        return "📂 Nenhuma transação encontrada por categoria."

    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
    except:
        locale.setlocale(locale.LC_ALL, '')  # fallback para local padrão

    mensagem = "📊 *Total por categoria:*\n\n"
    for categoria, total in data:
        valor_formatado = locale.currency(total, grouping=True, symbol=False)
        mensagem += f"• {categoria}: R$ {valor_formatado}\n"

    return mensagem


def format_resumo(transacoes):
    if not transacoes:
        return "📭 Nenhuma movimentação encontrada no período."

    receitas = []
    despesas = []
    total_receitas = 0
    total_despesas = 0

    for tipo, descricao, categoria, valor, data in transacoes:
        data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
        valor_formatado = f"{valor:,.2f}".replace(".", ",")
        linha = f"• {descricao} ({categoria})\n  💰 R$ {valor_formatado} | 📅 {data_formatada}"

        if tipo.lower() == "receita":
            receitas.append(linha)
            total_receitas += valor
        else:
            despesas.append(linha)
            total_despesas += valor

    resumo = "📋 *Resumo de transações:*\n\n"

    if receitas:
        resumo += "🟢 *Receitas:*\n" + "\n\n".join(receitas)
        resumo += f"\n\n💵 *Total de receitas:* R$ {total_receitas:,.2f}".replace(".", ",")
    if despesas:
        if receitas:
            resumo += "\n\n"
        resumo += "🔴 *Despesas:*\n" + "\n\n".join(despesas)
        resumo += f"\n\n💸 *Total de despesas:* R$ {total_despesas:,.2f}".replace(".", ",")

    return resumo
