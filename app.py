from flask import Flask, render_template, request
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

def get_db_connection():
    """Conecta ao banco de dados SQLite"""
    conn = sqlite3.connect('savi_dados_unificado.db')
    conn.row_factory = sqlite3.Row
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
    # Verificar se o banco de dados existe
    if not os.path.exists('savi_dados_unificado.db'):
        print("AVISO: Banco de dados 'savi_dados_unificado.db' não encontrado!")
        print("Criando banco de dados de exemplo para teste...")
        
        # Criar banco de dados de exemplo
        conn = sqlite3.connect('savi_dados_unificado.db')
        cursor = conn.cursor()
        
        # Criar tabela de exemplo
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS producao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_nome TEXT,
            senha TEXT,
            data_autorizacao TEXT
        )
        ''')
        
        # Inserir dados de exemplo com alguns pacientes tendo 12 senhas
        dados_exemplo = [
            # João Silva - 12 senhas (para teste do contador)
            ('João Silva', 'PWD001', '2024-01-15'),
            ('João Silva', 'PWD002', '2024-01-16'),
            ('João Silva', 'PWD003', '2024-01-17'),
            ('João Silva', 'PWD004', '2024-01-18'),
            ('João Silva', 'PWD005', '2024-01-19'),
            ('João Silva', 'PWD006', '2024-01-20'),
            ('João Silva', 'PWD007', '2024-01-21'),
            ('João Silva', 'PWD008', '2024-01-22'),
            ('João Silva', 'PWD009', '2024-01-23'),
            ('João Silva', 'PWD010', '2024-01-24'),
            ('João Silva', 'PWD011', '2024-01-25'),
            ('João Silva', 'PWD012', '2024-01-26'),
            
            # Maria Santos - 12 senhas (para teste do contador)
            ('Maria Santos', 'PWD013', '2024-01-15'),
            ('Maria Santos', 'PWD014', '2024-01-16'),
            ('Maria Santos', 'PWD015', '2024-01-17'),
            ('Maria Santos', 'PWD016', '2024-01-18'),
            ('Maria Santos', 'PWD017', '2024-01-19'),
            ('Maria Santos', 'PWD018', '2024-01-20'),
            ('Maria Santos', 'PWD019', '2024-01-21'),
            ('Maria Santos', 'PWD020', '2024-01-22'),
            ('Maria Santos', 'PWD021', '2024-01-23'),
            ('Maria Santos', 'PWD022', '2024-01-24'),
            ('Maria Santos', 'PWD023', '2024-01-25'),
            ('Maria Santos', 'PWD024', '2024-01-26'),
            
            # Ana Costa - 8 senhas
            ('Ana Costa', 'PWD025', '2024-01-18'),
            ('Ana Costa', 'PWD026', '2024-01-19'),
            ('Ana Costa', 'PWD027', '2024-01-20'),
            ('Ana Costa', 'PWD028', '2024-01-21'),
            ('Ana Costa', 'PWD029', '2024-01-22'),
            ('Ana Costa', 'PWD030', '2024-01-23'),
            ('Ana Costa', 'PWD031', '2024-01-24'),
            ('Ana Costa', 'PWD032', '2024-01-25'),
            
            # Pedro Oliveira - 5 senhas
            ('Pedro Oliveira', 'PWD033', '2024-01-21'),
            ('Pedro Oliveira', 'PWD034', '2024-01-22'),
            ('Pedro Oliveira', 'PWD035', '2024-01-23'),
            ('Pedro Oliveira', 'PWD036', '2024-01-24'),
            ('Pedro Oliveira', 'PWD037', '2024-01-25'),
            
            # Carlos Ferreira - 12 senhas (para teste do contador)
            ('Carlos Ferreira', 'PWD038', '2024-02-01'),
            ('Carlos Ferreira', 'PWD039', '2024-02-02'),
            ('Carlos Ferreira', 'PWD040', '2024-02-03'),
            ('Carlos Ferreira', 'PWD041', '2024-02-04'),
            ('Carlos Ferreira', 'PWD042', '2024-02-05'),
            ('Carlos Ferreira', 'PWD043', '2024-02-06'),
            ('Carlos Ferreira', 'PWD044', '2024-02-07'),
            ('Carlos Ferreira', 'PWD045', '2024-02-08'),
            ('Carlos Ferreira', 'PWD046', '2024-02-09'),
            ('Carlos Ferreira', 'PWD047', '2024-02-10'),
            ('Carlos Ferreira', 'PWD048', '2024-02-11'),
            ('Carlos Ferreira', 'PWD049', '2024-02-12'),
        ]
        
        cursor.executemany(
            'INSERT INTO producao (usuario_nome, senha, data_autorizacao) VALUES (?, ?, ?)',
            dados_exemplo
        )
        
        conn.commit()
        conn.close()
        print("Banco de dados de exemplo criado com sucesso!")
        print("3 pacientes com exatamente 12 senhas foram criados para teste.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)