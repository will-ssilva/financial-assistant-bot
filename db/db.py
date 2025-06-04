import os
import mysql.connector
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_USER = os.environ.get("DATABASE_USER")
DATABASE_PASS = os.environ.get("DATABASE_PASS")

# Conexão com o banco MySQL
def get_connection():
    return mysql.connector.connect(
        host="mysql.bluefeather.com.br",
        user=DATABASE_USER,
        password=DATABASE_PASS,
        database="bluefeather"
    )

# Inicializa as tabelas
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            role VARCHAR(20),
            content TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            tipo VARCHAR(20),
            descricao TEXT,
            categoria VARCHAR(50),
            valor DECIMAL(10,2),
            data DATE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            user_id INT,
            categoria VARCHAR(50),
            limite DECIMAL(10,2),
            PRIMARY KEY (user_id, categoria)
        )
    """)

    conn.commit()
    conn.close()

# Salvar mensagens (histórico)
def save_message(user_id, role, content):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (user_id, role, content) VALUES (%s, %s, %s)", (user_id, role, content))
    conn.commit()
    conn.close()

# Obter histórico do usuário
def get_user_history(user_id, max_messages=10):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM messages
        WHERE user_id = %s
        ORDER BY id DESC LIMIT %s
    """, (user_id, max_messages))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": role, "content": content} for role, content in reversed(rows)]

# Salvar transação
def save_transaction(user_id, tipo, descricao, categoria, valor, data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, tipo, descricao, categoria, valor, data)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, tipo, descricao, categoria, valor, data))
    conn.commit()
    conn.close()

# Interpretar texto de transação
def parse_transaction(response_text):
    try:
        tipo = re.search(r"Tipo: (.+)", response_text).group(1).strip()
        descricao = re.search(r"Item: (.+)", response_text).group(1).strip()
        categoria = re.search(r"Categoria: (.+)", response_text).group(1).strip()
        valor_str = re.search(r"Valor: R\$ ([\d\.,]+)", response_text).group(1).replace('.', '').replace(",", ".")
        valor = float(valor_str)
        data = datetime.now().strftime("%Y-%m-%d")
        return {
            "tipo": tipo,
            "descricao": descricao,
            "categoria": categoria,
            "valor": valor,
            "data": data
        }
    except:
        return None

# Resumo por período
def get_summary_by_period(user_id, start_date, end_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tipo, descricao, categoria, CAST(valor AS CHAR) as valor, CAST(data AS CHAR) as data, id
        FROM transactions
        WHERE user_id = %s AND data BETWEEN %s AND %s
        ORDER BY data DESC
    """, (user_id, start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Total por categoria
def get_total_by_category(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT categoria, SUM(valor)
        FROM transactions
        WHERE user_id = %s
        GROUP BY categoria
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Limpar histórico e transações
def clear_user_data(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM transactions WHERE user_id = %s", (user_id,))
    conn.commit()
    conn.close()

# Definir orçamento por categoria
def set_budget(user_id, categoria, limite):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO budget (user_id, categoria, limite)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE limite = VALUES(limite)
    """, (user_id, categoria, limite))
    conn.commit()
    conn.close()

# Buscar orçamento e gasto mensal atual
def get_budgets_with_spending(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.categoria, b.limite,
            IFNULL(SUM(t.valor), 0)
        FROM budget b
        LEFT JOIN transactions t
            ON b.user_id = t.user_id AND b.categoria = t.categoria
            AND DATE_FORMAT(t.data, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')
        WHERE b.user_id = %s
        GROUP BY b.categoria, b.limite
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Verificar orçamentos ultrapassados
def check_budget_warnings(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.categoria, b.limite,
            IFNULL(SUM(t.valor), 0)
        FROM budget b
        LEFT JOIN transactions t
            ON b.user_id = t.user_id AND b.categoria = t.categoria
            AND DATE_FORMAT(t.data, '%Y-%m') = DATE_FORMAT(CURDATE(), '%Y-%m')
        WHERE b.user_id = %s
        GROUP BY b.categoria, b.limite
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    avisos = []
    for categoria, limite, gasto in rows:
        if limite > 0:
            perc = gasto / limite * 100
            if perc > 100:
                avisos.append(f"🚨 Você ultrapassou o orçamento de *{categoria}*! (R$ {gasto:.2f} de R$ {limite:.2f})".replace(".", ","))
    return avisos

# Buscar transações por palavra-chave
def search_transactions(user_id, keyword):
    conn = get_connection()
    cursor = conn.cursor()
    like_keyword = f"%{keyword}%"
    cursor.execute("""
        SELECT tipo, descricao, categoria, valor, CAST(data AS CHAR) as data
        FROM transactions
        WHERE user_id = %s AND descricao LIKE %s
        ORDER BY data DESC
        LIMIT 10
    """, (user_id, like_keyword))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Buscar transações por categoria no mês atual
def get_transactions_by_category(user_id, categoria):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tipo, descricao, valor, DATE_FORMAT(data, '%%d/%%m/%%Y')
        FROM transactions
        WHERE user_id = %s AND categoria = %s
        AND DATE_FORMAT(data, '%%Y-%%m') = DATE_FORMAT(CURDATE(), '%%Y-%%m')
        ORDER BY data DESC
    """, (user_id, categoria))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Editar transações
def editar_transacao(id, tipo, descricao, categoria, valor, data):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE transactions
            SET tipo = %s,
                descricao = %s,
                categoria = %s,
                valor = %s,
                data = %s
            WHERE id = %s
        """, (tipo, descricao, categoria, valor, data, id))

        conn.commit()
        return cursor.rowcount  # Retorna o número de linhas afetadas

    finally:
        cursor.close()
        conn.close()

# Executar qualquer Query
def execute_query(query):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows
