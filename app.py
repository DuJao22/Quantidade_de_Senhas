from flask import Flask, render_template, request
import sqlite3
from datetime import datetime
import os
import sqlitecloud
#sqlitecloud://cmq6frwshz.g4.sqlite.cloud:8860/savi_dados_unificado.db?apikey=Dor8OwUECYmrbcS5vWfsdGpjCpdm9ecSDJtywgvRw8k

app = Flask(__name__)

def get_db_connection():
    """Conecta ao banco de dados SQLite"""
    conn = sqlitecloud.connect("sqlitecloud://cmq6frwshz.g4.sqlite.cloud:8860/savi_dados_unificado.db?apikey=Dor8OwUECYmrbcS5vWfsdGpjCpdm9ecSDJtywgvRw8k")

    conn.row_factory = sqlitecloud.Row
    return conn

def parse_date(date_str):
    """Converte data do formato dd/mm/aaaa para aaaa-mm-dd"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
    except ValueError:
        return None

def format_date_for_display(date_str):
    """Converte data do formato aaaa-mm-dd para dd/mm/aaaa"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return date_str

@app.route('/')
def index():
    # Obter parâmetros de filtro
    data_inicial = request.args.get('data_inicial', '')
    data_final = request.args.get('data_final', '')
    nome_paciente = request.args.get('nome_paciente', '')
    
    conn = get_db_connection()
    
    # Query base para dados agrupados por usuário
    base_query = """
    SELECT usuario_nome, COUNT(senha) as total_senhas
    FROM producao
    WHERE usuario_nome IS NOT NULL AND usuario_nome != ''
    """
    
    # Query para total geral
    total_query = """
    SELECT COUNT(senha) as total_geral
    FROM producao
    WHERE senha IS NOT NULL
    """
    
    # Query para contar pacientes com exatamente 12 senhas
    pacientes_12_query = """
    SELECT COUNT(*) as total_pacientes_12
    FROM (
        SELECT usuario_nome, COUNT(senha) as total_senhas
        FROM producao
        WHERE usuario_nome IS NOT NULL AND usuario_nome != ''
    """
    
    params = []
    params_12 = []
    
    # Adicionar filtros de data se fornecidos
    if data_inicial:
        data_inicial_sql = parse_date(data_inicial)
        if data_inicial_sql:
            base_query += " AND date(data_autorizacao) >= ?"
            total_query += " AND date(data_autorizacao) >= ?"
            pacientes_12_query += " AND date(data_autorizacao) >= ?"
            params.append(data_inicial_sql)
            params_12.append(data_inicial_sql)
    
    if data_final:
        data_final_sql = parse_date(data_final)
        if data_final_sql:
            base_query += " AND date(data_autorizacao) <= ?"
            total_query += " AND date(data_autorizacao) <= ?"
            pacientes_12_query += " AND date(data_autorizacao) <= ?"
            params.append(data_final_sql)
            params_12.append(data_final_sql)
    
    # Adicionar filtro por nome de paciente se fornecido
    if nome_paciente:
        base_query += " AND usuario_nome LIKE ?"
        total_query += " AND usuario_nome LIKE ?"
        pacientes_12_query += " AND usuario_nome LIKE ?"
        nome_param = f"%{nome_paciente}%"
        params.append(nome_param)
        params_12.append(nome_param)
    
    # Completar queries
    base_query += " GROUP BY usuario_nome ORDER BY total_senhas DESC"
    pacientes_12_query += " GROUP BY usuario_nome HAVING COUNT(senha) = 12) as subquery"
    
    # Executar queries
    try:
        # Obter dados agrupados por usuário
        cursor = conn.execute(base_query, params)
        dados_usuarios = cursor.fetchall()
        
        # Obter total geral
        cursor = conn.execute(total_query, params)
        total_geral = cursor.fetchone()['total_geral']
        
        # Obter total de pacientes com 12 senhas
        cursor = conn.execute(pacientes_12_query, params_12)
        total_pacientes_12 = cursor.fetchone()['total_pacientes_12']
        
        # Obter informações sobre período filtrado
        periodo_info = ""
        filtros_aplicados = []
        
        if data_inicial or data_final:
            if data_inicial and data_final:
                filtros_aplicados.append(f"Período: {data_inicial} até {data_final}")
            elif data_inicial:
                filtros_aplicados.append(f"A partir de: {data_inicial}")
            elif data_final:
                filtros_aplicados.append(f"Até: {data_final}")
        
        if nome_paciente:
            filtros_aplicados.append(f"Nome contém: '{nome_paciente}'")
        
        if filtros_aplicados:
            periodo_info = " | ".join(filtros_aplicados)
        
    except sqlite3.Error as e:
        print(f"Erro no banco de dados: {e}")
        dados_usuarios = []
        total_geral = 0
        total_pacientes_12 = 0
        periodo_info = "Erro ao consultar o banco de dados"
    
    finally:
        conn.close()
    
    return render_template('index.html', 
                         dados_usuarios=dados_usuarios,
                         total_geral=total_geral,
                         total_pacientes_12=total_pacientes_12,
                         data_inicial=data_inicial,
                         data_final=data_final,
                         nome_paciente=nome_paciente,
                         periodo_info=periodo_info)

@app.route('/test-db')
def test_db():
    """Rota para testar a conexão com o banco de dados"""
    try:
        conn = get_db_connection()
        
        # Verificar se a tabela existe
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='producao'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            return "Tabela 'producao' não encontrada no banco de dados"
        
        # Obter estrutura da tabela
        cursor = conn.execute("PRAGMA table_info(producao)")
        columns = cursor.fetchall()
        
        # Obter uma amostra de dados
        cursor = conn.execute("SELECT * FROM producao LIMIT 5")
        sample_data = cursor.fetchall()
        
        # Obter estatísticas básicas
        cursor = conn.execute("SELECT COUNT(*) as total_registros FROM producao")
        total_registros = cursor.fetchone()['total_registros']
        
        cursor = conn.execute("SELECT COUNT(DISTINCT usuario_nome) as total_usuarios FROM producao WHERE usuario_nome IS NOT NULL AND usuario_nome != ''")
        total_usuarios = cursor.fetchone()['total_usuarios']
        
        conn.close()
        
        result = f"<h2>Estrutura da tabela 'producao':</h2><ul>"
        for col in columns:
            result += f"<li>{col['name']} ({col['type']})</li>"
        result += "</ul>"
        
        result += f"<h2>Estatísticas:</h2>"
        result += f"<p>Total de registros: {total_registros}</p>"
        result += f"<p>Total de usuários únicos: {total_usuarios}</p>"
        
        result += f"<h2>Amostra de dados ({len(sample_data)} registros):</h2><pre>"
        for row in sample_data:
            result += f"{dict(row)}\n"
        result += "</pre>"
        
        return result
        
    except sqlite3.Error as e:
        return f"Erro ao conectar ao banco de dados: {e}"

if __name__ == '__main__':
 
    app.run(debug=True, host='0.0.0.0', port=5000)
