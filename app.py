import os
import secrets
import csv
import io
import random

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pytz
from sqlalchemy import func

load_dotenv()

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
db_dir = os.path.join(basedir, 'instance')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(db_dir, 'petstock.db'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# ✅ Blindagem nível bancário: Se não achar o .env, gera uma chave caótica impossível de adivinhar
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

db = SQLAlchemy(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")

TZ_BRASIL = pytz.timezone('America/Sao_Paulo')

def hora_brasil(): return datetime.now(TZ_BRASIL).replace(tzinfo=None)
def data_brasil(): return hora_brasil().date()

# ==========================================
# --- MODELOS ---
# ==========================================
class Loja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_fantasia = db.Column(db.String(150), nullable=False)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    chave_pix = db.Column(db.String(100))
    email = db.Column(db.String(150))
    valor_plano = db.Column(db.Float, default=80.00)
    telefone = db.Column(db.String(20))
    plano = db.Column(db.String(50), default='pro')
    percentual_cashback = db.Column(db.Float, default=3.0) # NOVO CAMPO

class Funcionario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    usuario = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    cargo = db.Column(db.String(50), default='Caixa')
    comissao_servicos = db.Column(db.Float, default=0.0)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False)

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_sku = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    preco_venda = db.Column(db.Float, nullable=False)
    preco_custo = db.Column(db.Float, default=0.0)
    estoque = db.Column(db.Float, default=0.0)
    ativo = db.Column(db.Boolean, default=True)
    descricao = db.Column(db.String(200))
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    rua = db.Column(db.String(100))
    numero = db.Column(db.String(10))
    bairro = db.Column(db.String(50))
    nome_pet = db.Column(db.String(50))
    saldo_cashback = db.Column(db.Float, default=0.0)
    data_proxima_vacina = db.Column(db.Date)
    observacoes_saude = db.Column(db.Text)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False)

class Representante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_fantasia = db.Column(db.String(100), nullable=False)
    cnpj = db.Column(db.String(20))
    representante_nome = db.Column(db.String(100))
    whatsapp = db.Column(db.String(20))
    pedido_minimo = db.Column(db.String(20))
    prazo_entrega = db.Column(db.String(50))
    observacoes = db.Column(db.String(200))
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False)

class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'))
    quantidade = db.Column(db.Float)
    valor_total = db.Column(db.Float)
    forma_pagamento_1 = db.Column(db.String(100)) # ✅ ALTERADO PARA 100
    data_venda = db.Column(db.DateTime, default=hora_brasil)
    data_previsao_fim = db.Column(db.DateTime)
    vendedor = db.Column(db.String(50), default='Dono/Gerente')
    produto = db.relationship('Produto', backref='vendas_list')
    compras = db.relationship('Cliente', backref='compras_list')

class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey('funcionario.id'), nullable=True)
    nome_pet = db.Column(db.String(100), nullable=False)
    raca_porte = db.Column(db.String(100))
    servico = db.Column(db.String(100), nullable=False)
    valor_servico = db.Column(db.Float, default=0.0)
    valor_comissao = db.Column(db.Float, default=0.0)
    data_agendamento = db.Column(db.Date, nullable=False)
    hora_agendamento = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(50), default='Agendado')
    observacoes = db.Column(db.String(255))
    cliente = db.relationship('Cliente', backref='agendamentos')
    profissional = db.relationship('Funcionario', backref='servicos_realizados')

# ==========================================
# --- CONTEXTO GLOBAL ---
# ==========================================
@app.context_processor
def injetar_dados_globais():
    loja_atual = None
    if 'loja_id' in session:
        loja_atual = db.session.get(Loja, session['loja_id'])

    # TOTALMENTE DEPENDENTE DA SESSÃO AGORA
    return dict(
        loja_logada=loja_atual,
        cargo=session.get('cargo', 'Gerente'),
        vendedor_atual=session.get('nome_usuario', 'Dono/Gerente')
    )

# ==========================================
# --- ROTA PRINCIPAL E LOGINS ---
# ==========================================
@app.route('/')
def index():
    if 'loja_id' in session: return redirect(url_for('painel'))
    return render_template('landing.html')

@app.route('/assinar', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def assinar():
    try:
        nome_fantasia = request.form.get('nome_fantasia')
        telefone = request.form.get('telefone')
        email = request.form.get('email')
        senha = request.form.get('senha')
        plano_escolhido = request.form.get('plano', 'pro')

        if Loja.query.filter_by(usuario=email).first():
            flash('❌ Este e-mail já está cadastrado. Faça login ou use outro.', 'danger')
            return redirect(url_for('index'))

        valor = 80.00 if plano_escolhido == 'pro' else 150.00
        nova_loja = Loja(nome_fantasia=nome_fantasia, usuario=email, email=email, telefone=telefone, senha=generate_password_hash(senha), data_vencimento=data_brasil() + timedelta(days=15), valor_plano=valor, plano=plano_escolhido)
        db.session.add(nova_loja)
        db.session.commit()
        session['loja_id'] = nova_loja.id
        flash('🎉 Bem-vindo ao PetStock! Seus 15 dias grátis começaram agora.', 'success')
        return redirect(url_for('painel'))
    except Exception as e:
        flash('❌ Ocorreu um erro. Tente novamente.', 'danger')
        return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST':
        u = request.form.get('login', '').strip().lower()
        s = request.form.get('senha', '').strip()
        loja = Loja.query.filter_by(usuario=u).first()

        if loja and check_password_hash(loja.senha, s):
            session.clear()
            hoje = data_brasil()
            dias_restantes = (loja.data_vencimento - hoje).days
            zap = "https://api.whatsapp.com/send?phone=5551981962819&text=Ol%C3%A1!%20Preciso%20renovar%20minha%20assinatura%20do%20PetStock."

            if dias_restantes < 0:
                flash(f'⚠️ ASSINATURA VENCIDA! <a href="{zap}" target="_blank" style="color: inherit; text-decoration: underline; font-weight: 900;">Clique aqui para renovar.</a>', 'danger')
                return render_template('login.html')
            elif dias_restantes <= 2:
                flash(f'⚠️ ATENÇÃO! Sua assinatura vence em {dias_restantes} dia(s). <a href="{zap}" target="_blank" style="color: inherit; text-decoration: underline; font-weight: 900;">Renovar.</a>', 'warning')

            if check_password_hash(loja.senha, '123456'):
                session['reset_loja_id'] = loja.id
                return redirect(url_for('mudar_senha'))

            session['loja_id'] = loja.id
            session['nome_usuario'] = 'Dono/Gerente' # Default
            session['cargo'] = 'Gerente'
            return redirect(url_for('painel'))

        flash('❌ Usuário ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/mudar_senha', methods=['GET', 'POST'])
@csrf.exempt
def mudar_senha():
    l_id = session.get('reset_loja_id') or session.get('loja_id')
    if not l_id: return redirect(url_for('login'))
    if request.method == 'POST':
        n = request.form.get('nova_senha', '')
        if len(n) < 6:
            flash('❌ A senha precisa ter pelo menos 6 caracteres.', 'danger')
            return render_template('mudar_senha.html')
        if n == request.form.get('confirma_senha'):
            loja = db.session.get(Loja, l_id)
            loja.senha = generate_password_hash(n)
            db.session.commit()
            session.clear()
            session['loja_id'] = loja.id
            flash('✅ Senha alterada com sucesso!', 'success')
            return redirect(url_for('painel'))
        flash('❌ As senhas não conferem.', 'danger')
    return render_template('mudar_senha.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# --- PAINEL ---
# ==========================================
@app.route('/painel')
def painel():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']
    hoje = data_brasil()
    inicio_dia = datetime.combine(hoje, datetime.min.time())
    fim_dia = datetime.combine(hoje, datetime.max.time())
    total_vendas_hoje = db.session.query(func.sum(Venda.valor_total)).filter(Venda.loja_id == loja_id, Venda.data_venda >= inicio_dia, Venda.data_venda <= fim_dia).scalar() or 0.0
    banhos_hoje = Agendamento.query.filter_by(loja_id=loja_id, data_agendamento=hoje, status='Agendado').count()
    vencimento_vacina = hoje + timedelta(days=7)
    alertas_vacina = Cliente.query.filter(Cliente.loja_id == loja_id, Cliente.data_proxima_vacina <= vencimento_vacina, Cliente.data_proxima_vacina >= hoje).all()
    estoque_baixo = Produto.query.filter(Produto.loja_id == loja_id, Produto.estoque < 5, Produto.ativo == True).count()

    return render_template('dashboard.html', vendas_total=total_vendas_hoje, banhos_count=banhos_hoje, vacinas=alertas_vacina, estoque_alerta=estoque_baixo)

# ==========================================
# --- ESTOQUE ---
# ==========================================
@app.route('/estoque')
def estoque():
    if 'loja_id' not in session: return redirect(url_for('login'))
    page = request.args.get('page', 1, type=int)
    produtos_paginados = Produto.query.filter_by(loja_id=session['loja_id'], ativo=True).paginate(page=page, per_page=50, error_out=False)
    total_prods = Produto.query.filter_by(loja_id=session['loja_id']).count()
    return render_template('index.html', produtos=produtos_paginados, proximo_sku=str(total_prods + 1).zfill(2))

@app.route('/cadastrar_produto', methods=['POST'])
def cadastrar_produto():
    if 'loja_id' not in session: return redirect(url_for('login'))
    sku = request.form.get('sku', '').strip() or f"PET-{random.randint(10000, 99999)}"
    tipo = request.form.get('tipo_produto', '').strip()
    nome_final = f"{request.form.get('nome', '').strip()} - {tipo}" if tipo else request.form.get('nome', '').strip()
    try: p_custo = float(request.form.get('preco_custo', '0').replace('.', '').replace(',', '.'))
    except: p_custo = 0.0
    try: p_venda = float(request.form.get('preco', '0').replace('.', '').replace(',', '.'))
    except: p_venda = 0.0
    try: qtd = float(request.form.get('quantidade', '0').replace('.', '').replace(',', '.'))
    except: qtd = 0.0
    db.session.add(Produto(codigo_sku=sku, nome=nome_final, categoria=request.form.get('categoria'), preco_custo=p_custo, preco_venda=p_venda, estoque=qtd, loja_id=session['loja_id']))
    db.session.commit()
    flash('✅ Produto salvo no estoque!', 'success')
    return redirect(url_for('estoque'))

@app.route('/desmembrar', methods=['POST'])
def desmembrar():
    if 'loja_id' not in session: return redirect(url_for('login'))
    try: qtd_origem = float(request.form.get('qtd_origem', '0').replace(',', '.'))
    except: qtd_origem = 0.0
    try: qtd_destino = float(request.form.get('qtd_destino', '0').replace(',', '.'))
    except: qtd_destino = 0.0
    prod_origem = db.session.get(Produto, request.form.get('origem_id'))
    prod_destino = db.session.get(Produto, request.form.get('destino_id'))
    if prod_origem and prod_destino and prod_origem.loja_id == session['loja_id'] and prod_destino.loja_id == session['loja_id']:
        if prod_origem.estoque >= qtd_origem:
            prod_origem.estoque -= qtd_origem
            prod_destino.estoque += qtd_destino
            db.session.commit()
            flash(f'⚖️ Sucesso! Transformamos {qtd_origem} em {qtd_destino}.', 'success')
        else: flash('❌ Erro: Quantidade insuficiente.', 'danger')
    return redirect(url_for('estoque'))

@app.route('/editar_produto/<int:id>', methods=['GET', 'POST'])
def editar_produto(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    prod = db.session.get(Produto, id)
    if not prod or prod.loja_id != session['loja_id']: return redirect(url_for('estoque'))
    if request.method == 'POST':
        prod.codigo_sku = request.form.get('sku')
        prod.nome = request.form.get('nome')
        prod.categoria = request.form.get('categoria')
        try: prod.preco_custo = float(request.form.get('preco_custo', '0').replace('.', '').replace(',', '.'))
        except: pass
        try: prod.preco_venda = float(request.form.get('preco', '0').replace('.', '').replace(',', '.'))
        except: pass
        try: prod.estoque = float(request.form.get('quantidade', '0').replace('.', '').replace(',', '.'))
        except: pass
        db.session.commit()
        flash('✅ Produto atualizado!', 'success')
        return redirect(url_for('estoque'))
    return render_template('editar_produto.html', p=prod)

@app.route('/inativar_produto/<int:id>')
def inativar_produto(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    prod = db.session.get(Produto, id)
    if prod and prod.loja_id == session['loja_id']:
        prod.ativo = False
        db.session.commit()
        flash('🗑️ Produto movido para Lixeira.', 'warning')
    return redirect(url_for('estoque'))

@app.route('/inativos')
def inativos():
    if 'loja_id' not in session: return redirect(url_for('login'))
    return render_template('inativos.html', produtos=Produto.query.filter_by(loja_id=session['loja_id'], ativo=False).all())

@app.route('/restaurar_produto/<int:id>')
def restaurar_produto(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    prod = db.session.get(Produto, id)
    if prod and prod.loja_id == session['loja_id']:
        prod.ativo = True
        db.session.commit()
        flash('♻️ Produto restaurado!', 'success')
    return redirect(url_for('inativos'))

@app.route('/dar_baixa', methods=['POST'])
def baixa_estoque():
    if 'loja_id' not in session: return redirect(url_for('login'))
    produto_id = request.form.get('produto_id')
    motivo = request.form.get('motivo')
    try: qtd = float(request.form.get('quantidade', '0').replace(',', '.'))
    except: qtd = 0.0
    produto = db.session.get(Produto, produto_id)
    if produto and produto.loja_id == session['loja_id']:
        if produto.estoque >= qtd:
            produto.estoque -= qtd
            db.session.add(Venda(produto_id=produto.id, loja_id=session['loja_id'], quantidade=qtd, valor_total=0.0, forma_pagamento_1=f"Baixa: {motivo}", vendedor=session.get('nome_usuario', 'Dono/Gerente')))
            db.session.commit()
            flash(f'🔻 Baixa registrada.', 'warning')
        else: flash('❌ Quantidade insuficiente.', 'danger')
    return redirect(url_for('estoque'))

@app.route('/importar_produtos', methods=['POST'])
def importar_produtos():
    if 'loja_id' not in session: return redirect(url_for('login'))
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '': return redirect(url_for('estoque'))
    try:
        stream = io.StringIO(arquivo.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream, delimiter=',')
        next(csv_input, None)
        cadastrados = 0
        for row in csv_input:
            if len(row) >= 4:
                try: custo = float(row[4].replace(',', '.')) if len(row) > 4 and row[4] else 0.0
                except: custo = 0.0
                try: estoque = float(row[5].replace(',', '.')) if len(row) > 5 and row[5] else 0.0
                except: estoque = 0.0
                try: venda = float(row[3].replace(',', '.'))
                except: venda = 0.0
                db.session.add(Produto(codigo_sku=row[0], nome=row[1], categoria=row[2], preco_venda=venda, preco_custo=custo, estoque=estoque, loja_id=session['loja_id']))
                cadastrados += 1
        db.session.commit()
        flash(f'✅ {cadastrados} produtos importados.', 'success')
    except: flash('❌ Erro na importação.', 'danger')
    return redirect(url_for('estoque'))

# ==========================================
# --- CLIENTES ---
# ==========================================
@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'loja_id' not in session: return redirect(url_for('login'))

    if request.method == 'POST':
        pets = [request.form.get('nome_pet', '').strip(), request.form.get('nome_pet_2', '').strip(), request.form.get('nome_pet_3', '').strip()]
        db.session.add(Cliente(nome=request.form.get('nome'), telefone=request.form.get('telefone'), rua=request.form.get('rua'), numero=request.form.get('numero'), bairro=request.form.get('bairro'), nome_pet=" / ".join([p for p in pets if p]), loja_id=session['loja_id']))
        db.session.commit()
        flash('✅ Cliente cadastrado!', 'success')
        return redirect(url_for('clientes'))

    # --- A MÁGICA DA ESCALA ACONTECE AQUI ---
    page = request.args.get('page', 1, type=int)
    clientes_paginados = Cliente.query.filter_by(loja_id=session['loja_id']).order_by(Cliente.nome.asc()).paginate(page=page, per_page=50, error_out=False)

    return render_template('clientes.html', clientes=clientes_paginados)

@app.route('/editar_cliente/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    cliente = db.get_or_404(Cliente, id)
    if cliente.loja_id != session['loja_id']: return redirect(url_for('clientes'))
    if request.method == 'POST':
        cliente.nome = request.form.get('nome')
        cliente.telefone = request.form.get('telefone')
        cliente.rua = request.form.get('rua')
        cliente.numero = request.form.get('numero')
        cliente.bairro = request.form.get('bairro')
        cliente.nome_pet = request.form.get('nome_pet')
        cliente.observacoes_saude = request.form.get('observacoes_saude')
        data_v = request.form.get('data_proxima_vacina')
        if data_v: cliente.data_proxima_vacina = datetime.strptime(data_v, '%Y-%m-%d').date()
        db.session.commit()
        flash('✅ Cliente atualizado!', 'success')
        return redirect(url_for('clientes'))
    return render_template('editar_cliente.html', c=cliente)

@app.route('/excluir_cliente/<int:id>')
def excluir_cliente(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    cliente = db.session.get(Cliente, id)
    if cliente and cliente.loja_id == session['loja_id']:
        db.session.delete(cliente)
        db.session.commit()
        flash('🗑️ Cliente excluído.', 'warning')
    return redirect(url_for('clientes'))

@app.route('/importar_clientes', methods=['POST'])
def importar_clientes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '': return redirect(url_for('clientes'))
    try:
        stream = io.StringIO(arquivo.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream, delimiter=',')
        next(csv_input, None)
        cads = 0
        for row in csv_input:
            if len(row) >= 2:
                db.session.add(Cliente(nome=row[0], telefone=row[1], rua=row[2] if len(row)>2 else "", numero=row[3] if len(row)>3 else "", bairro=row[4] if len(row)>4 else "", nome_pet=row[5] if len(row)>5 else "", loja_id=session['loja_id']))
                cads += 1
        db.session.commit()
        flash(f'✅ {cads} clientes importados.', 'success')
    except: flash('❌ Erro na importação.', 'danger')
    return redirect(url_for('clientes'))

@app.route('/historico_cliente/<int:id>')
def historico_cliente(id):
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    vendas = Venda.query.filter_by(cliente_id=id, loja_id=session['loja_id']).order_by(Venda.data_venda.desc()).all()
    hist = []
    for v in vendas:
        n = v.produto.nome if v.produto else ('💰 Pgto Fiado' if 'Pgto' in (v.forma_pagamento_1 or '') else ('🛁 Banho/Tosa' if 'Banho/Tosa' in (v.forma_pagamento_1 or '') else 'Excluído'))
        hist.append({'data': v.data_venda.strftime('%d/%m/%Y %H:%M'), 'produto': n, 'qtd': v.quantidade, 'valor': v.valor_total})
    return jsonify(hist)

@app.route('/api/divida_cliente/<int:id>', methods=['GET'])
def api_divida_cliente(id):
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    divida = sum(v.valor_total for v in Venda.query.filter_by(cliente_id=id, loja_id=session['loja_id'], forma_pagamento_1='Crediário / Fiado').all() if v.valor_total)
    cli = db.session.get(Cliente, id)
    return jsonify({'divida': divida, 'cashback': cli.saldo_cashback if cli else 0.0})

@app.route('/api/pagar_divida/<int:id>', methods=['POST'])
def api_pagar_divida(id):
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    fp = (request.get_json() or {}).get('forma_pagamento', 'Dinheiro')
    vendas = Venda.query.filter_by(cliente_id=id, loja_id=session['loja_id'], forma_pagamento_1='Crediário / Fiado').all()
    total = sum(v.valor_total for v in vendas if v.valor_total)
    if total <= 0: return jsonify({'sucesso': False, 'erro': 'Sem dívida.'})
    for v in vendas: v.forma_pagamento_1 = 'Fiado (Pago)'
    db.session.add(Venda(produto_id=None, cliente_id=id, loja_id=session['loja_id'], quantidade=0, valor_total=total, forma_pagamento_1=f"{fp} (Pgto Fiado)", vendedor=session.get('nome_usuario', 'Dono/Gerente')))
    db.session.commit()
    return jsonify({'sucesso': True})

# ==========================================
# --- PDV ---
# ==========================================
@app.route('/pdv')
def pdv():
    if 'loja_id' not in session: return redirect(url_for('login'))
    return render_template('pdv.html', clientes=Cliente.query.filter_by(loja_id=session['loja_id']).order_by(Cliente.nome).all(), equipe=Funcionario.query.filter_by(loja_id=session['loja_id']).all())

@app.route('/api/produtos', methods=['GET'])
def api_produtos():
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    return jsonify([{'id': p.id, 'sku': p.codigo_sku, 'nome': p.nome, 'preco': p.preco_venda, 'custo': p.preco_custo, 'estoque': p.estoque} for p in Produto.query.filter_by(loja_id=session['loja_id'], ativo=True).all()])

@app.route('/api/finalizar_venda', methods=['POST'])
def api_finalizar_venda():
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    dados = request.get_json()
    loja_id = session['loja_id']
    cliente_nome = dados.get('cliente_nome', '').strip()
    forma_pagto = dados.get('forma_pagamento', 'Dinheiro')
    vendedor_nome = dados.get('vendedor_nome', session.get('nome_usuario', 'Dono/Gerente'))
    cashback_usado = float(dados.get('cashback_usado', 0.0))

    cli_id = None
    cli = None
    if cliente_nome:
        cli = Cliente.query.filter_by(nome=cliente_nome, loja_id=loja_id).first()
        if not cli:
            cli = Cliente(nome=cliente_nome, telefone="Não informado", loja_id=loja_id)
            db.session.add(cli)
            db.session.flush()
        cli_id = cli.id

    try:
        total_venda = 0.0
        for item in dados.get('itens', []):
            prod = db.session.get(Produto, item['id'])
            if prod and prod.loja_id == loja_id:
                qtd = float(item['qtd'])
                prod.estoque -= qtd
                dias = int(item.get('dias_duracao') or 0)
                subtotal = float(item.get('subtotal_final', item.get('subtotal', 0)))
                total_venda += subtotal
                db.session.add(Venda(
                    produto_id=prod.id, cliente_id=cli_id, loja_id=loja_id, quantidade=qtd, valor_total=subtotal,
                    forma_pagamento_1=forma_pagto,
                    data_previsao_fim=hora_brasil() + timedelta(days=dias) if dias > 0 else None,
                    vendedor=vendedor_nome
                ))

        if cli and total_venda > 0:
            if cashback_usado > 0:
                if cli.saldo_cashback >= cashback_usado: cli.saldo_cashback -= cashback_usado
                else: return jsonify({'sucesso': False, 'erro': 'Cashback insuficiente!'}), 400

            valor_pago = total_venda - cashback_usado
            if valor_pago > 0 and "Fiado" not in forma_pagto:
                loja = db.session.get(Loja, loja_id)
                pct = (loja.percentual_cashback or 3.0) / 100.0 # CASHBACK DINÂMICO
                if cli.saldo_cashback is None: cli.saldo_cashback = 0.0
                cli.saldo_cashback += (valor_pago * pct)

        db.session.commit()
        return jsonify({'sucesso': True, 'msg': 'Venda ok!', 'loja_nome': db.session.get(Loja, loja_id).nome_fantasia})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 400

# ==========================================
# --- AGENDA ---
# ==========================================
@app.route('/agenda', methods=['GET', 'POST'])
def agenda():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']
    if request.method == 'POST':
        c_id = request.form.get('cliente_id')
        f_id = request.form.get('funcionario_id')
        try: v = float(request.form.get('valor_servico', '0').replace('.', '').replace(',', '.'))
        except: v = 0.0
        db.session.add(Agendamento(
            cliente_id=int(c_id) if c_id else None, loja_id=loja_id, funcionario_id=int(f_id) if f_id else None,
            nome_pet=request.form.get('nome_pet'), raca_porte=request.form.get('raca_porte'),
            servico=request.form.get('servico'), valor_servico=v,
            data_agendamento=datetime.strptime(request.form.get('data_agendamento'), '%Y-%m-%d').date(),
            hora_agendamento=request.form.get('hora_agendamento'), observacoes=request.form.get('observacoes')
        ))
        db.session.commit()
        flash('✅ Horário agendado!', 'success')
        return redirect(url_for('agenda'))

    df_str = request.args.get('data_filtro', data_brasil().strftime('%Y-%m-%d'))
    return render_template('agenda.html',
                           agendamentos=Agendamento.query.filter_by(loja_id=loja_id, data_agendamento=datetime.strptime(df_str, '%Y-%m-%d').date()).order_by(Agendamento.hora_agendamento.asc()).all(),
                           data_filtro=df_str,
                           clientes=Cliente.query.filter_by(loja_id=loja_id).order_by(Cliente.nome).all(),
                           equipe=Funcionario.query.filter_by(loja_id=loja_id).all())

@app.route('/editar_agendamento', methods=['POST'])
def editar_agendamento():
    if 'loja_id' not in session: return redirect(url_for('login'))
    a = db.session.get(Agendamento, request.form.get('agendamento_id'))
    if a and a.loja_id == session['loja_id']:
        a.nome_pet = request.form.get('nome_pet')
        a.raca_porte = request.form.get('raca_porte')
        a.servico = request.form.get('servico')
        a.data_agendamento = datetime.strptime(request.form.get('data_agendamento'), '%Y-%m-%d').date()
        a.hora_agendamento = request.form.get('hora_agendamento')
        a.observacoes = request.form.get('observacoes')
        try: a.valor_servico = float(request.form.get('valor_servico', '0').replace('.', '').replace(',', '.'))
        except: a.valor_servico = 0.0
        fid = request.form.get('funcionario_id')
        a.funcionario_id = int(fid) if fid else None

        if a.status == 'Concluído' and a.funcionario_id:
            f = db.session.get(Funcionario, a.funcionario_id)
            a.valor_comissao = a.valor_servico * (f.comissao_servicos / 100.0) if (f and f.comissao_servicos > 0) else 0.0

        db.session.commit()
        flash('✅ Agendamento atualizado!', 'success')
    return redirect(request.referrer or url_for('agenda'))

@app.route('/concluir_servico', methods=['POST'])
def concluir_servico():
    if 'loja_id' not in session: return redirect(url_for('login'))
    a = db.get_or_404(Agendamento, request.form.get('agendamento_id'))
    fp = request.form.get('forma_pagamento', 'Dinheiro')
    if a.loja_id == session['loja_id']:
        a.status = 'Concluído'
        if a.valor_servico > 0 and a.funcionario_id:
            f = db.session.get(Funcionario, a.funcionario_id)
            if f and f.comissao_servicos > 0: a.valor_comissao = a.valor_servico * (f.comissao_servicos / 100.0)
        db.session.add(Venda(produto_id=None, cliente_id=a.cliente_id, loja_id=session['loja_id'], quantidade=1.0, valor_total=a.valor_servico, forma_pagamento_1=f"{fp} (Banho/Tosa)", vendedor=session.get('nome_usuario', 'Dono/Gerente')))
        db.session.commit()
        flash(f'🚿 Serviço concluído como {fp}.', 'success')
    return redirect(url_for('agenda'))

@app.route('/mudar_status_agenda/<int:id>/<status>')
def mudar_status_agenda(id, status):
    if 'loja_id' not in session: return redirect(url_for('login'))

    # ✅ TRAVA DE SEGURANÇA: Proíbe concluir serviço sem passar pelo caixa (POST)
    if status == 'Concluído':
        flash('⚠️ Para concluir um serviço, clique no botão de "Concluir e Pagar" para registrar no caixa.', 'warning')
        return redirect(url_for('agenda'))

    a = db.get_or_404(Agendamento, id)
    if a.loja_id == session['loja_id']:
        a.status = status
        db.session.commit()
        flash(f'🚿 Status alterado para {status}.', 'success')
    return redirect(url_for('agenda'))
# ==========================================
# --- MARKETING & RADAR ---
# ==========================================
@app.route('/marketing')
def marketing():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']
    ausentes = Cliente.query.filter(Cliente.loja_id == loja_id, ~Cliente.id.in_(db.session.query(Venda.cliente_id).filter(Venda.data_venda >= datetime.now() - timedelta(days=30)))).all()
    return render_template('marketing.html', ausentes=ausentes)

@app.route('/radar')
def radar():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']
    alertas = Venda.query.filter(Venda.loja_id == loja_id, Venda.data_previsao_fim != None, Venda.data_previsao_fim <= hora_brasil() + timedelta(days=7)).order_by(Venda.data_previsao_fim.asc()).all()
    estoque_critico = Produto.query.filter(Produto.loja_id == loja_id, Produto.ativo == True, Produto.estoque < 5.0).order_by(Produto.estoque.asc()).all()
    return render_template('radar.html', alertas=alertas, estoque_critico=estoque_critico, ranking=[])

# ==========================================
# --- RELATÓRIOS & COMISSÕES ---
# ==========================================
@app.route('/relatorios')
def relatorios():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']
    di, df, vend = request.args.get('data_inicio'), request.args.get('data_fim'), request.args.get('vendedor')
    hoje = data_brasil().strftime('%Y-%m-%d')
    di, df = di or hoje, df or hoje

    q = Venda.query.filter(Venda.loja_id == loja_id, Venda.data_venda >= datetime.strptime(di, '%Y-%m-%d'), Venda.data_venda <= datetime.strptime(df, '%Y-%m-%d') + timedelta(days=1, seconds=-1))
    if vend: q = q.filter(Venda.vendedor == vend)

    vendas = q.order_by(Venda.data_venda.desc()).all()
    tot = custo = pix = cred = deb = din = fiad = 0.0
    for v in vendas:
        val = v.valor_total or 0.0
        tot += val
        if v.produto: custo += (v.produto.preco_custo * v.quantidade)
        fp = (v.forma_pagamento_1 or '').lower()
        if 'pix' in fp: pix += val
        elif 'credito' in fp or 'crédito' in fp: cred += val
        elif 'debito' in fp or 'débito' in fp: deb += val
        elif 'dinheiro' in fp: din += val
        elif 'fiado' in fp or 'crediário' in fp: fiad += val

    vends_db = db.session.query(Venda.vendedor).filter_by(loja_id=loja_id).distinct().all()
    return render_template('relatorios.html', vendas=vendas, total="%.2f"%tot, lucro_total_formatado="%.2f"%(tot-custo), pix="%.2f"%pix, credito="%.2f"%cred, debito="%.2f"%deb, dinheiro="%.2f"%din, fiado="%.2f"%fiad, data_inicio=di, data_fim=df, vendedor_filtro=vend, vendedores=[v[0] for v in vends_db if v[0]])

@app.route('/exportar_relatorio')
def exportar_relatorio():
    if 'loja_id' not in session: return redirect(url_for('login'))
    di, df, vend = request.args.get('data_inicio'), request.args.get('data_fim'), request.args.get('vendedor')
    q = Venda.query.filter_by(loja_id=session['loja_id'])
    if di: q = q.filter(Venda.data_venda >= datetime.strptime(di, '%Y-%m-%d'))
    if df: q = q.filter(Venda.data_venda <= datetime.strptime(df, '%Y-%m-%d') + timedelta(days=1, seconds=-1))
    if vend: q = q.filter(Venda.vendedor == vend)

    out = io.StringIO()
    w = csv.writer(out, delimiter=';')
    w.writerow(['DATA DA VENDA', 'VENDEDOR', 'PRODUTO', 'QUANTIDADE', 'FORMA DE PAGAMENTO', 'VALOR TOTAL (R$)'])
    for v in q.order_by(Venda.data_venda.desc()).all():
        n = v.produto.nome if v.produto else ('Pgto Fiado' if 'Pgto' in (v.forma_pagamento_1 or '') else ('Serviço Banho/Tosa' if 'Banho/Tosa' in (v.forma_pagamento_1 or '') else 'Excluído'))
        w.writerow([v.data_venda.strftime('%d/%m/%Y %H:%M'), v.vendedor, n, v.quantidade, v.forma_pagamento_1, "%.2f" % v.valor_total])
    res = Response(out.getvalue().encode('utf-8-sig'), mimetype='text/csv')
    res.headers["Content-Disposition"] = f"attachment; filename=relatorio_{data_brasil()}.csv"
    return res

@app.route('/comissoes')
def comissoes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    di, df = request.args.get('data_inicio'), request.args.get('data_fim')
    hoje = data_brasil().strftime('%Y-%m-%d')
    di, df = di or hoje, df or hoje

    servs = Agendamento.query.filter(Agendamento.loja_id == session['loja_id'], Agendamento.status == 'Concluído', Agendamento.data_agendamento >= datetime.strptime(di, '%Y-%m-%d').date(), Agendamento.data_agendamento <= datetime.strptime(df, '%Y-%m-%d').date(), Agendamento.funcionario_id != None).order_by(Agendamento.data_agendamento.desc()).all()

    resumo = {}
    for s in servs:
        if not s.profissional: continue
        n = s.profissional.nome
        if n not in resumo: resumo[n] = {'total_servicos': 0, 'valor_gerado': 0.0, 'comissao_devida': 0.0}
        resumo[n]['total_servicos'] += 1
        resumo[n]['valor_gerado'] += s.valor_servico
        resumo[n]['comissao_devida'] += s.valor_comissao

    return render_template('comissoes.html', servicos=servs, resumo=resumo, data_inicio=di, data_fim=df)

@app.route('/editar_comissao', methods=['POST'])
def editar_comissao():
    if 'loja_id' not in session: return redirect(url_for('login'))
    a = db.session.get(Agendamento, request.form.get('agendamento_id'))
    if a and a.loja_id == session['loja_id']:
        try: a.valor_comissao = float(request.form.get('novo_valor', '0').replace('.', '').replace(',', '.'))
        except: pass
        db.session.commit()
        flash('✏️ Comissão atualizada!', 'success')
    return redirect(request.referrer or url_for('comissoes'))

# ==========================================
# --- EQUIPE & FORNECEDORES ---
# ==========================================
@app.route('/funcionarios', methods=['GET', 'POST'])
def funcionarios():
    if 'loja_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        u = request.form.get('usuario', '').strip().lower()
        if Funcionario.query.filter_by(usuario=u).first():
            flash('❌ Usuário já em uso.', 'danger')
            return redirect(url_for('funcionarios'))
        try: c = float(request.form.get('comissao', '0').replace('.', '').replace(',', '.'))
        except: c = 0.0
        db.session.add(Funcionario(nome=request.form.get('nome'), usuario=u, senha=generate_password_hash('123456'), cargo=request.form.get('cargo'), comissao_servicos=c, loja_id=session['loja_id']))
        db.session.commit()
        flash('✅ Acesso gerado!', 'success')
        return redirect(url_for('funcionarios'))
    return render_template('funcionarios.html', funcionarios=Funcionario.query.filter_by(loja_id=session['loja_id']).all())

@app.route('/editar_funcionario', methods=['POST'])
def editar_funcionario():
    if 'loja_id' not in session: return redirect(url_for('login'))
    f = db.session.get(Funcionario, request.form.get('func_id'))
    if f and f.loja_id == session['loja_id']:
        f.nome, f.cargo = request.form.get('nome'), request.form.get('cargo')
        try: f.comissao_servicos = float(request.form.get('comissao', '0').replace('.', '').replace(',', '.'))
        except: pass
        db.session.commit()
        flash('✅ Profissional atualizado!', 'success')
    return redirect(url_for('funcionarios'))

@app.route('/excluir_funcionario/<int:id>')
def excluir_funcionario(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    f = db.session.get(Funcionario, id)
    if f and f.loja_id == session['loja_id']:
        db.session.delete(f)
        db.session.commit()
        flash('🗑️ Acesso revogado.', 'warning')
    return redirect(url_for('funcionarios'))

@app.route('/resetar_senha/<int:id>')
def resetar_senha(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    f = db.session.get(Funcionario, id)
    if f and f.loja_id == session['loja_id']:
        f.senha = generate_password_hash('123456')
        db.session.commit()
        flash(f'🔄 Senha resetada para 123456.', 'success')
    return redirect(url_for('funcionarios'))

@app.route('/representantes', methods=['GET', 'POST'])
def representantes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        db.session.add(Representante(nome_fantasia=request.form.get('nome_fantasia'), cnpj=request.form.get('cnpj'), representante_nome=request.form.get('representante_nome'), whatsapp=request.form.get('whatsapp'), pedido_minimo=request.form.get('pedido_minimo'), prazo_entrega=request.form.get('prazo_entrega'), observacoes=request.form.get('observacoes'), loja_id=session['loja_id']))
        db.session.commit()
        flash('✅ Fornecedor cadastrado!', 'success')
        return redirect(url_for('representantes'))
    return render_template('representantes.html', representantes=Representante.query.filter_by(loja_id=session['loja_id']).all())

@app.route('/excluir_representante/<int:id>')
def excluir_representante(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    r = db.session.get(Representante, id)
    if r and r.loja_id == session['loja_id']:
        db.session.delete(r)
        db.session.commit()
        flash('🗑️ Fornecedor excluído.', 'warning')
    return redirect(url_for('representantes'))

@app.route('/editar_representante/<int:id>', methods=['POST'])
def editar_representante(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    r = db.session.get(Representante, id)
    if r and r.loja_id == session['loja_id']:
        r.nome_fantasia, r.cnpj, r.representante_nome, r.whatsapp, r.pedido_minimo, r.prazo_entrega, r.observacoes = request.form.get('nome_fantasia'), request.form.get('cnpj'), request.form.get('representante_nome'), request.form.get('whatsapp'), request.form.get('pedido_minimo'), request.form.get('prazo_entrega'), request.form.get('observacoes')
        db.session.commit()
        flash('✅ Fornecedor atualizado!', 'success')
    return redirect(url_for('representantes'))

# ==========================================
# --- CONFIGURAÇÕES ---
# ==========================================
@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja = db.session.get(Loja, session['loja_id'])
    if request.method == 'POST':
        loja.chave_pix = request.form.get('chave_pix')
        try: loja.percentual_cashback = float(request.form.get('percentual_cashback', '3').replace(',', '.'))
        except: pass
        db.session.commit()
        flash('Configurações salvas!', 'success')
        return redirect(url_for('configuracoes'))
    return render_template('configuracoes.html')

# ==========================================
# --- PAINEL CEO ---
# ==========================================
@app.route('/login_ceo', methods=['GET', 'POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def login_ceo():
    if request.method == 'POST':
        s = request.form.get('senha_mestre', '')
        sc = os.environ.get('CEO_SENHA', '')
        if sc and s == sc:
            session['ceo_logado'] = True
            return redirect(url_for('admin_guilherme'))
        flash('❌ Senha incorreta.', 'danger')
    return render_template('login_ceo.html')

@app.route('/admin_guilherme', methods=['GET', 'POST'])
def admin_guilherme():
    if not session.get('ceo_logado'): return redirect(url_for('login_ceo'))
    hoje = data_brasil()
    if request.method == 'POST':
        u = request.form.get('usuario', '').strip().lower()
        if Loja.query.filter_by(usuario=u).first():
            flash('❌ Usuário já existe.', 'danger')
            return redirect(url_for('admin_guilherme'))
        db.session.add(Loja(nome_fantasia=request.form.get('nome_fantasia'), usuario=u, senha=generate_password_hash('123456'), data_vencimento=datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date(), valor_plano=float(os.environ.get('VALOR_PLANO', '80.00'))))
        db.session.commit()
        flash('✅ Loja criada!', 'success')
        return redirect(url_for('admin_guilherme'))

    lojas = Loja.query.all()
    mrr = sum(l.valor_plano or 80.0 for l in lojas if l.data_vencimento >= hoje)
    prev = sum(l.valor_plano or 80.0 for l in lojas if hoje <= l.data_vencimento <= hoje + timedelta(days=7))
    return render_template('admin.html', lojas=lojas, total_clientes=len(lojas), clientes_ativos=sum(1 for l in lojas if l.data_vencimento >= hoje), clientes_inadimplentes=sum(1 for l in lojas if l.data_vencimento < hoje), mrr=mrr, previsao_7_dias=prev, today_date=str(hoje))

@app.route('/editar_loja/<int:id>', methods=['GET', 'POST'])
def editar_loja(id):
    if not session.get('ceo_logado'): return redirect(url_for('login_ceo'))
    l = db.session.get(Loja, id)
    if not l: return redirect(url_for('admin_guilherme'))
    if request.method == 'POST':
        l.nome_fantasia, l.usuario, l.data_vencimento = request.form.get('nome_fantasia'), request.form.get('usuario').strip().lower(), datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date()
        db.session.commit()
        flash('✅ Loja atualizada!', 'success')
        return redirect(url_for('admin_guilherme'))
    return render_template('editar_loja.html', loja=l)

@app.route('/resetar_senha_loja/<int:id>')
def resetar_senha_loja(id):
    if not session.get('ceo_logado'): return redirect(url_for('login_ceo'))
    l = db.session.get(Loja, id)
    if l:
        l.senha = generate_password_hash('123456')
        db.session.commit()
        flash(f'🔄 Senha resetada para 123456.', 'success')
    return redirect(url_for('admin_guilherme'))

@app.route('/excluir_loja/<int:id>')
def excluir_loja(id):
    if not session.get('ceo_logado'): return redirect(url_for('login_ceo'))
    l = db.session.get(Loja, id)
    if l:
        for m in [Venda, Agendamento, Funcionario, Representante, Cliente, Produto]: m.query.filter_by(loja_id=l.id).delete()
        db.session.delete(l)
        db.session.commit()
        flash('🗑️ Loja excluída.', 'warning')
    return redirect(url_for('admin_guilherme'))

@app.route('/logout_ceo')
def logout_ceo():
    session.pop('ceo_logado', None)
    return redirect(url_for('login_ceo'))

with app.app_context(): db.create_all()

if __name__ == '__main__': app.run(debug=False)