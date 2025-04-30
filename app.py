from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Database configuration
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                salario REAL DEFAULT 0
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                valor REAL NOT NULL,
                categoria TEXT NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT,
                data TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
            )
        ''')  # tipo: 'necessario' ou 'desnecessario'
        db.commit()

# Helper function to generate animated chart
# Helper function to generate animated chart without dark background
def generate_animated_chart(gastos):
    plt.figure(figsize=(8, 6), facecolor='#2d2d2d')  # Cor de fundo do gráfico atualizada para #2d2d2d
    
    categorias = [g['categoria'] for g in gastos]
    valores = [g['total'] for g in gastos]
    cores = ['#9c27b0', '#7e57c2', '#673ab7', '#5e35b1', '#512da8', '#4527a0']
    
    # Explode the largest slice
    max_index = valores.index(max(valores))
    explode = [0.1 if i == max_index else 0 for i in range(len(valores))]
    
    wedges, texts, autotexts = plt.pie(
        valores, 
        labels=categorias, 
        autopct='%1.1f%%', 
        colors=cores, 
        startangle=90,
        explode=explode,
        shadow=True,
        wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
        textprops={'color': 'white', 'fontsize': 10}  # Alterando a cor do texto para branco
    )
    
    plt.title('Distribuição de Gastos', color='white', pad=20)  # Alterando a cor do título para branco
    plt.setp(autotexts, size=12, weight="bold", color='white')  # Texto das porcentagens em branco
    
    # Add animation by rotating the chart
    for i, wedge in enumerate(wedges):
        wedge.set_alpha(0.7)
        if i == max_index:
            wedge.set_alpha(1)
    
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight', facecolor='#2d2d2d')  # Salvando com fundo #2d2d2d
    img.seek(0)
    plt.close()
    return base64.b64encode(img.getvalue()).decode('utf-8')


# Routes
@app.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('painel'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario_id' in session:
        return redirect(url_for('painel'))

    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        db = get_db()
        usuario = db.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()

        if usuario and check_password_hash(usuario['senha'], senha):
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('painel'))

        flash('E-mail ou senha incorretos', 'error')

    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = generate_password_hash(request.form['senha'])
        salario = float(request.form['salario'])

        db = get_db()
        try:
            db.execute('INSERT INTO usuarios (nome, email, senha, salario) VALUES (?, ?, ?, ?)', 
                      (nome, email, senha, salario))
            db.commit()
            flash('Cadastro realizado com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('E-mail já cadastrado', 'error')

    return render_template('cadastro.html')

@app.route('/painel')
def painel():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    usuario_id = session['usuario_id']

    # Get user data
    usuario = db.execute('SELECT salario FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    salario = usuario['salario']

    # Get expenses
    gastos = db.execute('''
        SELECT categoria, tipo, SUM(valor) as total 
        FROM gastos 
        WHERE usuario_id = ? 
        GROUP BY categoria, tipo
    ''', (usuario_id,)).fetchall()

    # Totals
    total_gastos = db.execute('''
        SELECT COALESCE(SUM(valor), 0) as total 
        FROM gastos 
        WHERE usuario_id = ?
    ''', (usuario_id,)).fetchone()['total']

    saldo_atual = salario - total_gastos

    # Last 5 expenses
    ultimos = db.execute('''
        SELECT * FROM gastos 
        WHERE usuario_id = ? 
        ORDER BY data DESC LIMIT 5
    ''', (usuario_id,)).fetchall()

    # Generate chart if there are expenses
    grafico = generate_animated_chart(gastos) if gastos else None

    return render_template(
        'painel.html',
        nome=session['usuario_nome'],
        salario=salario,
        gastos=gastos,
        total_gastos=total_gastos,
        saldo_atual=saldo_atual,
        ultimos=ultimos,
        grafico=grafico
    )

@app.route('/adicionar-gasto', methods=['GET', 'POST'])
def adicionar_gasto():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            valor = float(request.form['valor'])
            categoria = request.form['categoria']
            tipo = request.form['tipo']
            descricao = request.form.get('descricao', '')

            db = get_db()
            db.execute('''
                INSERT INTO gastos (usuario_id, valor, categoria, tipo, descricao, data) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session['usuario_id'], 
                valor, 
                categoria, 
                tipo, 
                descricao, 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            db.commit()
            flash('Gasto adicionado com sucesso!', 'success')
            return redirect(url_for('painel'))
        except ValueError:
            flash('Valor inválido para o gasto', 'error')

    categorias = ['Moradia', 'Alimentação', 'Transporte', 'Lazer', 'Saúde', 'Educação', 'Ração', 'Assinaturas', 'Combustivel', 'Internet', 'Cartão de Credito',
                  'Energia elétrica', 'Parcelamentos', 'Água e esgoto', 'Gás', 'Plano Celular' ]
    return render_template('adicionar_gasto.html', categorias=categorias)

# Rota para confirmar a remoção de um gasto
@app.route('/remover-gasto/<int:id>', methods=['GET', 'POST'])
def remover_gasto(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    gasto = db.execute('SELECT * FROM gastos WHERE id = ? AND usuario_id = ?', (id, session['usuario_id'])).fetchone()

    if not gasto:
        flash('Gasto não encontrado ou não pertence ao usuário.', 'error')
        return redirect(url_for('painel'))

    if request.method == 'POST':
        # Se o formulário for enviado, remove o gasto
        db.execute('DELETE FROM gastos WHERE id = ?', (id,))
        db.commit()
        flash('Gasto removido com sucesso!', 'success')
        return redirect(url_for('painel'))

    # Exibe o formulário de remoção para confirmação
    return render_template('remover_gasto.html', gasto=gasto)


@app.route('/atualizar-salario', methods=['GET', 'POST'])
def atualizar_salario():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    usuario_id = session['usuario_id']
    usuario = db.execute('SELECT salario FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()

    if request.method == 'POST':
        try:
            novo_salario = float(request.form['salario'])
            db.execute('UPDATE usuarios SET salario = ? WHERE id = ?', 
                      (novo_salario, usuario_id))
            db.commit()
            flash('Salário atualizado com sucesso!', 'success')
            return redirect(url_for('painel'))
        except ValueError:
            flash('Por favor, insira um valor numérico válido', 'error')

    return render_template('atualizar_salario.html', salario_atual=usuario['salario'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)