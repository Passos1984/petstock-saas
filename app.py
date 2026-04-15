import os
import csv
import io
import random
import logging
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

# --- Carrega variáveis do .env ---
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÃO SEGURA ---
basedir = os.path.abspath(os.path.dirname(__file__))
db_dir = os.path.join(basedir, 'instance')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(db_dir, 'petstock.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-mestra-petstock-segura')
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

# --- EXTENSÕES ---
db = SQLAlchemy(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

# --- FUSO HORÁRIO BRASIL ---
TZ_BRASIL = pytz.timezone('America/Sao_Paulo')

def hora_brasil():
    return datetime.now(TZ_BRASIL).replace(tzinfo=None)

def data_brasil():
    return hora_brasil().date()


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
    forma_pagamento_1 = db.Column(db.String(50))
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


@app.context_processor
def injetar_dados_globais():
    loja_atual = None
    if 'loja_id' in session:
        loja_atual = Loja.query.get(session['loja_id'])
    return dict(loja_logada=loja_atual, cargo='Gerente', vendedor_atual='Dono/Gerente')


# ==========================================
# --- ROTA PRINCIPAL E LOGINS (ISENTOS DE CSRF) ---
# ==========================================
@app.route('/')
def index():
    if 'loja_id' in session:
        return redirect(url_for('painel'))
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

        valor = 0.0
        if plano_escolhido == 'pro': valor = 80.00
        elif plano_escolhido == 'elite': valor = 150.00

        nova_loja = Loja(
            nome_fantasia=nome_fantasia, usuario=email, email=email, telefone=telefone,
            senha=generate_password_hash(senha), data_vencimento=data_brasil() + timedelta(days=15),
            valor_plano=valor, plano=plano_escolhido
        )
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
                flash(f'⚠️ ASSINATURA VENCIDA! Sua licença expirou. <a href="{zap}" target="_blank" style="color: inherit; text-decoration: underline; font-weight: 900;">Clique aqui para renovar.</a>', 'danger')
                return render_template('login.html')
            elif dias_restantes <= 2:
                flash(f'⚠️ ATENÇÃO! Sua assinatura vence em {dias_restantes} dia(s). <a href="{zap}" target="_blank" style="color: inherit; text-decoration: underline; font-weight: 900;">Renovar.</a>', 'warning')

            if check_password_hash(loja.senha, '123456'):
                session['reset_loja_id'] = loja.id
                return redirect(url_for('mudar_senha'))

            session['loja_id'] = loja.id
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
            loja = Loja.query.get(l_id)
            loja.senha = generate_password_hash(n)
            db.session.commit()
            session.clear()
            session['loja_id'] = loja.id
            flash('✅ Senha alterada com sucesso! Bem-vindo(a).', 'success')
            return redirect(url_for('painel'))
        else:
            flash('❌ As senhas digitadas não conferem. Tente novamente.', 'danger')
    return render_template('mudar_senha.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ==========================================
# --- NOVO PAINEL (CENTRO DE COMANDO) ---
# ==========================================
@app.route('/painel')
def painel():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']
    hoje = data_brasil()

    # Busca vendas do dia
    inicio_dia = datetime.combine(hoje, datetime.min.time())
    fim_dia = datetime.combine(hoje, datetime.max.time())

    total_vendas_hoje = db.session.query(func.sum(Venda.valor_total)).filter(
        Venda.loja_id == loja_id,
        Venda.data_venda >= inicio_dia,
        Venda.data_venda <= fim_dia
    ).scalar() or 0.0

    # Próximos Banhos (Hoje)
    banhos_hoje = Agendamento.query.filter_by(loja_id=loja_id, data_agendamento=hoje, status='Agendado').count()

    # Alertas de Vacina (Vencendo em 7 dias)
    vencimento_vacina = hoje + timedelta(days=7)
    alertas_vacina = Cliente.query.filter(
        Cliente.loja_id == loja_id,
        Cliente.data_proxima_vacina <= vencimento_vacina,
        Cliente.data_proxima_vacina >= hoje
    ).all()

    # Produtos Acabando (Estoque < 5)
    estoque_baixo = Produto.query.filter(Produto.loja_id == loja_id, Produto.estoque < 5, Produto.ativo == True).count()

    return render_template('dashboard.html',
                         vendas_total=total_vendas_hoje,
                         banhos_count=banhos_hoje,
                         vacinas=alertas_vacina,
                         estoque_alerta=estoque_baixo)


# ==========================================
# --- ESTOQUE (ANTIGO PAINEL) ---
# ==========================================
@app.route('/estoque')
def estoque():
    if 'loja_id' not in session: return redirect(url_for('login'))
    page = request.args.get('page', 1, type=int)
    produtos_paginados = Produto.query.filter_by(loja_id=session['loja_id'], ativo=True).paginate(page=page, per_page=50, error_out=False)
    total_prods = Produto.query.filter_by(loja_id=session['loja_id']).count()
    proximo_sku = str(total_prods + 1).zfill(2)
    return render_template('index.html', produtos=produtos_paginados, proximo_sku=proximo_sku)

@app.route('/cadastrar_produto', methods=['POST'])
def cadastrar_produto():
    if 'loja_id' not in session: return redirect(url_for('login'))
    sku_recebido = request.form.get('sku', '').strip()
    if not sku_recebido: sku_recebido = f"PET-{random.randint(10000, 99999)}"
    nome_base = request.form.get('nome', '').strip()
    tipo = request.form.get('tipo_produto', '').strip()
    nome_final = f"{nome_base} - {tipo}" if tipo else nome_base
    try: p_custo = float(request.form.get('preco_custo', '0').replace('.', '').replace(',', '.'))
    except: p_custo = 0.0
    try: p_venda = float(request.form.get('preco', '0').replace('.', '').replace(',', '.'))
    except: p_venda = 0.0
    try: qtd = float(request.form.get('quantidade', '0').replace('.', '').replace(',', '.'))
    except: qtd = 0.0
    db.session.add(Produto(codigo_sku=sku_recebido, nome=nome_final, categoria=request.form.get('categoria'), preco_custo=p_custo, preco_venda=p_venda, estoque=qtd, loja_id=session['loja_id']))
    db.session.commit()
    flash('✅ Produto salvo no estoque!', 'success')
    return redirect(url_for('estoque'))

@app.route('/desmembrar', methods=['POST'])
def desmembrar():
    if 'loja_id' not in session: return redirect(url_for('login'))
    origem_id = request.form.get('origem_id')
    destino_id = request.form.get('destino_id')
    try: qtd_origem = float(request.form.get('qtd_origem', '0').replace(',', '.'))
    except: qtd_origem = 0.0
    try: qtd_destino = float(request.form.get('qtd_destino', '0').replace(',', '.'))
    except: qtd_destino = 0.0
    prod_origem = Produto.query.get(origem_id)
    prod_destino = Produto.query.get(destino_id)
    if (prod_origem and prod_destino and prod_origem.loja_id == session['loja_id'] and prod_destino.loja_id == session['loja_id']):
        if prod_origem.estoque >= qtd_origem:
            prod_origem.estoque -= qtd_origem
            prod_destino.estoque += qtd_destino
            db.session.commit()
            flash(f'⚖️ Sucesso! Transformamos {qtd_origem} saco(s) em {qtd_destino} KG a granel.', 'success')
        else: flash('❌ Erro: Quantidade insuficiente.', 'danger')
    return redirect(url_for('estoque'))

@app.route('/editar_produto/<int:id>', methods=['GET', 'POST'])
def editar_produto(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    prod = Produto.query.get(id)
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
        flash('✅ Produto atualizado com sucesso!', 'success')
        return redirect(url_for('estoque'))
    return render_template('editar_produto.html', p=prod)

@app.route('/inativar_produto/<int:id>')
def inativar_produto(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    prod = Produto.query.get(id)
    if prod and prod.loja_id == session['loja_id']:
        prod.ativo = False
        db.session.commit()
        flash('🗑️ Produto movido para a Lixeira.', 'warning')
    return redirect(url_for('estoque'))

@app.route('/inativos')
def inativos():
    if 'loja_id' not in session: return redirect(url_for('login'))
    prods = Produto.query.filter_by(loja_id=session['loja_id'], ativo=False).all()
    return render_template('inativos.html', produtos=prods)

@app.route('/dar_baixa', methods=['POST'])
def baixa_estoque():
    if 'loja_id' not in session: return redirect(url_for('login'))
    produto_id = request.form.get('produto_id')
    motivo = request.form.get('motivo')
    try: qtd = float(request.form.get('quantidade', '0').replace(',', '.'))
    except: qtd = 0.0
    produto = Produto.query.get(produto_id)
    if produto and produto.loja_id == session['loja_id']:
        if produto.estoque >= qtd:
            produto.estoque -= qtd
            venda_baixa = Venda(produto_id=produto.id, loja_id=session['loja_id'], quantidade=qtd, valor_total=0.0, forma_pagamento_1=f"Baixa: {motivo}", vendedor=session.get('vendedor_atual', 'Dono/Gerente'))
            db.session.add(venda_baixa)
            db.session.commit()
            flash(f'🔻 Baixa de {qtd}x {produto.nome} registrada como {motivo}.', 'warning')
        else: flash('❌ Erro: Quantidade insuficiente.', 'danger')
    return redirect(url_for('estoque'))

@app.route('/restaurar_produto/<int:id>')
def restaurar_produto(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    prod = Produto.query.get(id)
    if prod and prod.loja_id == session['loja_id']:
        prod.ativo = True
        db.session.commit()
        flash('♻️ Produto restaurado para o estoque!', 'success')
    return redirect(url_for('inativos'))

@app.route('/importar_produtos', methods=['POST'])
def importar_produtos():
    if 'loja_id' not in session: return redirect(url_for('login'))
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '':
        flash('❌ Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('estoque'))
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
                p = Produto(codigo_sku=row[0], nome=row[1], categoria=row[2], preco_venda=venda, preco_custo=custo, estoque=estoque, loja_id=session['loja_id'])
                db.session.add(p)
                cadastrados += 1
        db.session.commit()
        flash(f'✅ Importação Concluída! {cadastrados} produtos adicionados.', 'success')
    except Exception as e:
        flash(f'❌ Erro na importação.', 'danger')
    return redirect(url_for('estoque'))

# ==========================================
# --- MARKETING & CRM ---
# ==========================================
@app.route('/marketing')
def marketing():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']

    # Filtro: Clientes que não compram há mais de 30 dias
    um_mes_atras = datetime.now() - timedelta(days=30)
    clientes_ausentes = Cliente.query.filter(
        Cliente.loja_id == loja_id,
        ~Cliente.id.in_(db.session.query(Venda.cliente_id).filter(Venda.data_venda >= um_mes_atras))
    ).all()

    return render_template('marketing.html', ausentes=clientes_ausentes)

# ==========================================
# --- ROTAS DE EQUIPE (FUNCIONÁRIOS) ---
# ==========================================
@app.route('/funcionarios', methods=['GET', 'POST'])
def funcionarios():
    if 'loja_id' not in session: return redirect(url_for('login'))

    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip().lower()
        if Funcionario.query.filter_by(usuario=usuario).first():
            flash('❌ Esse nome de usuário já está em uso. Escolha outro.', 'danger')
            return redirect(url_for('funcionarios'))

        try: comissao = float(request.form.get('comissao', '0').replace('.', '').replace(',', '.'))
        except: comissao = 0.0

        novo_func = Funcionario(
            nome=request.form.get('nome'), usuario=usuario, senha=generate_password_hash('123456'),
            cargo=request.form.get('cargo'), comissao_servicos=comissao, loja_id=session['loja_id']
        )
        db.session.add(novo_func)
        db.session.commit()
        flash('✅ Funcionário cadastrado com acesso gerado!', 'success')
        return redirect(url_for('funcionarios'))

    lista_func = Funcionario.query.filter_by(loja_id=session['loja_id']).all()
    return render_template('funcionarios.html', funcionarios=lista_func)

@app.route('/editar_funcionario', methods=['POST'])
def editar_funcionario():
    if 'loja_id' not in session: return redirect(url_for('login'))

    func_id = request.form.get('func_id')
    func = Funcionario.query.get(func_id)

    if func and func.loja_id == session['loja_id']:
        func.nome = request.form.get('nome')
        func.cargo = request.form.get('cargo')

        try: comissao = float(request.form.get('comissao', '0').replace('.', '').replace(',', '.'))
        except: comissao = 0.0

        func.comissao_servicos = comissao
        db.session.commit()
        flash('✅ Dados do profissional atualizados com sucesso!', 'success')
    else:
        flash('❌ Erro ao atualizar profissional.', 'danger')

    return redirect(url_for('funcionarios'))

@app.route('/excluir_funcionario/<int:id>')
def excluir_funcionario(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    func = Funcionario.query.get(id)
    if func and func.loja_id == session['loja_id']:
        db.session.delete(func)
        db.session.commit()
        flash('🗑️ Acesso do funcionário revogado.', 'warning')
    return redirect(url_for('funcionarios'))

@app.route('/resetar_senha/<int:id>')
def resetar_senha(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    func = Funcionario.query.get(id)
    if func and func.loja_id == session['loja_id']:
        func.senha = generate_password_hash('123456')
        db.session.commit()
        flash(f'🔄 A senha de {func.nome} voltou para 123456.', 'success')
    return redirect(url_for('funcionarios'))

# ==========================================
# --- ROTAS DE REPRESENTANTES ---
# ==========================================
@app.route('/representantes', methods=['GET', 'POST'])
def representantes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        novo_rep = Representante(nome_fantasia=request.form.get('nome_fantasia'), cnpj=request.form.get('cnpj'), representante_nome=request.form.get('representante_nome'), whatsapp=request.form.get('whatsapp'), pedido_minimo=request.form.get('pedido_minimo'), prazo_entrega=request.form.get('prazo_entrega'), observacoes=request.form.get('observacoes'), loja_id=session['loja_id'])
        db.session.add(novo_rep)
        db.session.commit()
        flash('✅ Fornecedor cadastrado com sucesso!', 'success')
        return redirect(url_for('representantes'))
    lista_rep = Representante.query.filter_by(loja_id=session['loja_id']).all()
    return render_template('representantes.html', representantes=lista_rep)

@app.route('/excluir_representante/<int:id>')
def excluir_representante(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    rep = Representante.query.get(id)
    if rep and rep.loja_id == session['loja_id']:
        db.session.delete(rep)
        db.session.commit()
        flash('🗑️ Fornecedor excluído com sucesso.', 'warning')
    return redirect(url_for('representantes'))

@app.route('/editar_representante/<int:id>', methods=['POST'])
def editar_representante(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    rep = Representante.query.get(id)
    if rep and rep.loja_id == session['loja_id']:
        rep.nome_fantasia = request.form.get('nome_fantasia')
        rep.cnpj = request.form.get('cnpj')
        rep.representante_nome = request.form.get('representante_nome')
        rep.whatsapp = request.form.get('whatsapp')
        rep.pedido_minimo = request.form.get('pedido_minimo')
        rep.prazo_entrega = request.form.get('prazo_entrega')
        rep.observacoes = request.form.get('observacoes')
        db.session.commit()
        flash('✅ Fornecedor atualizado com sucesso!', 'success')
    return redirect(url_for('representantes'))

# ==========================================
# --- ROTA DO RADAR DE INTELIGÊNCIA ---
# ==========================================
@app.route('/radar')
def radar():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']
    daqui_7_dias = hora_brasil() + timedelta(days=7)
    alertas = Venda.query.filter(Venda.loja_id == loja_id, Venda.data_previsao_fim != None, Venda.data_previsao_fim <= daqui_7_dias).order_by(Venda.data_previsao_fim.asc()).all()
    estoque_critico = Produto.query.filter(Produto.loja_id == loja_id, Produto.ativo == True, Produto.estoque < 5.0).order_by(Produto.estoque.asc()).all()
    return render_template('radar.html', alertas=alertas, estoque_critico=estoque_critico, ranking=[])

# ==========================================
# --- ROTAS DE CLIENTES E FIADO ---
# ==========================================
@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        pets = [request.form.get('nome_pet', '').strip(), request.form.get('nome_pet_2', '').strip(), request.form.get('nome_pet_3', '').strip()]
        string_pets = " / ".join([p for p in pets if p])
        novo_cliente = Cliente(nome=request.form.get('nome'), telefone=request.form.get('telefone'), rua=request.form.get('rua'), numero=request.form.get('numero'), bairro=request.form.get('bairro'), nome_pet=string_pets, loja_id=session['loja_id'])
        db.session.add(novo_cliente)
        db.session.commit()
        flash('✅ Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))
    lista_clientes = Cliente.query.filter_by(loja_id=session['loja_id']).all()
    return render_template('clientes.html', clientes=lista_clientes)

@app.route('/excluir_cliente/<int:id>')
def excluir_cliente(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    cliente = Cliente.query.get(id)
    if cliente and cliente.loja_id == session['loja_id']:
        db.session.delete(cliente)
        db.session.commit()
        flash('🗑️ Cliente excluído com sucesso.', 'warning')
    return redirect(url_for('clientes'))

@app.route('/editar_cliente/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'loja_id' not in session: return redirect(url_for('login'))
    cliente = Cliente.query.get_or_404(id)
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
        if data_v:
            cliente.data_proxima_vacina = datetime.strptime(data_v, '%Y-%m-%d').date()

        db.session.commit()
        flash('✅ Cadastro e Saúde atualizados com sucesso!', 'success')
        return redirect(url_for('clientes'))
    return render_template('editar_cliente.html', c=cliente)

@app.route('/historico_cliente/<int:id>')
def historico_cliente(id):
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    vendas = Venda.query.filter_by(cliente_id=id, loja_id=session['loja_id']).order_by(Venda.data_venda.desc()).all()
    historico = []
    for v in vendas:
        nome_prod = v.produto.nome if v.produto else ('💰 Pagamento de Fiado' if 'Pgto' in (v.forma_pagamento_1 or '') else ('🛁 Serviço Banho/Tosa' if 'Banho/Tosa' in (v.forma_pagamento_1 or '') else 'Produto Excluído'))
        historico.append({'data': v.data_venda.strftime('%d/%m/%Y %H:%M'), 'produto': nome_prod, 'qtd': v.quantidade, 'valor': v.valor_total})
    return jsonify(historico)

@app.route('/api/divida_cliente/<int:id>', methods=['GET'])
def api_divida_cliente(id):
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    vendas_fiado = Venda.query.filter_by(cliente_id=id, loja_id=session['loja_id'], forma_pagamento_1='Crediário / Fiado').all()
    total_divida = sum(v.valor_total for v in vendas_fiado if v.valor_total)
    cliente = Cliente.query.get(id)
    saldo = cliente.saldo_cashback if cliente else 0.0
    return jsonify({'divida': total_divida, 'cashback': saldo})

@app.route('/api/pagar_divida/<int:id>', methods=['POST'])
def api_pagar_divida(id):
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    dados = request.get_json() or {}
    forma_pagto = dados.get('forma_pagamento', 'Dinheiro')
    vendas_fiado = Venda.query.filter_by(cliente_id=id, loja_id=session['loja_id'], forma_pagamento_1='Crediário / Fiado').all()
    total_divida = sum(v.valor_total for v in vendas_fiado if v.valor_total)
    if total_divida <= 0: return jsonify({'sucesso': False, 'erro': 'Cliente não possui dívida ativa.'})
    for v in vendas_fiado: v.forma_pagamento_1 = 'Fiado (Pago)'
    pagamento = Venda(produto_id=None, cliente_id=id, loja_id=session['loja_id'], quantidade=0, valor_total=total_divida, forma_pagamento_1=f"{forma_pagto} (Pgto Fiado)", data_venda=hora_brasil(), vendedor=session.get('vendedor_atual', 'Dono/Gerente'))
    db.session.add(pagamento)
    db.session.commit()
    return jsonify({'sucesso': True})

@app.route('/importar_clientes', methods=['POST'])
def importar_clientes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '':
        flash('❌ Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('clientes'))
    try:
        stream = io.StringIO(arquivo.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream, delimiter=',')
        next(csv_input, None)
        cadastrados = 0
        for row in csv_input:
            if len(row) >= 2:
                c = Cliente(nome=row[0], telefone=row[1], rua=row[2] if len(row)>2 else "", numero=row[3] if len(row)>3 else "", bairro=row[4] if len(row)>4 else "", nome_pet=row[5] if len(row)>5 else "", loja_id=session['loja_id'])
                db.session.add(c)
                cadastrados += 1
        db.session.commit()
        flash(f'✅ Importação Concluída! {cadastrados} clientes adicionados.', 'success')
    except Exception as e:
        flash(f'❌ Erro na importação.', 'danger')
    return redirect(url_for('clientes'))

# ==========================================
# --- ROTAS DO PDV (FRENTE DE CAIXA) ---
# ==========================================
@app.route('/pdv')
def pdv():
    if 'loja_id' not in session: return redirect(url_for('login'))
    clientes_loja = Cliente.query.filter_by(loja_id=session['loja_id']).order_by(Cliente.nome).all()
    equipe = Funcionario.query.filter_by(loja_id=session['loja_id']).all()
    return render_template('pdv.html', clientes=clientes_loja, equipe=equipe)

@app.route('/api/produtos', methods=['GET'])
def api_produtos():
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    produtos = Produto.query.filter_by(loja_id=session['loja_id'], ativo=True).all()
    lista = [{'id': p.id, 'sku': p.codigo_sku, 'nome': p.nome, 'preco': p.preco_venda, 'custo': p.preco_custo, 'estoque': p.estoque} for p in produtos]
    return jsonify(lista)

@app.route('/api/finalizar_venda', methods=['POST'])
def api_finalizar_venda():
    if 'loja_id' not in session: return jsonify({'erro': 'Não autorizado'}), 401
    dados = request.get_json()
    loja_id = session['loja_id']
    nome_cliente = dados.get('cliente_nome', '').strip()
    forma_pagto = dados.get('forma_pagamento', 'Dinheiro')
    vendedor_nome = dados.get('vendedor_nome', 'Dono/Gerente')
    cashback_usado = float(dados.get('cashback_usado', 0.0))

    cliente_id = None
    cli = None
    if nome_cliente:
        cli = Cliente.query.filter_by(nome=nome_cliente, loja_id=loja_id).first()
        if not cli:
            cli = Cliente(nome=nome_cliente, telefone="Não informado", loja_id=loja_id)
            db.session.add(cli)
            db.session.flush()
        cliente_id = cli.id

    try:
        total_venda = 0.0
        for item in dados.get('itens', []):
            prod = Produto.query.get(item['id'])
            if prod and prod.loja_id == loja_id:
                qtd = float(item['qtd'])
                prod.estoque -= qtd
                dias = int(item.get('dias_duracao') or 0)
                previsao = hora_brasil() + timedelta(days=dias) if dias > 0 else None
                subtotal = float(item.get('subtotal_final', item.get('subtotal', 0)))
                total_venda += subtotal

                # Salva o nome da forma de pagamento na venda (ex: "Cashback + Cartão de Crédito")
                # Cortamos em 50 caracteres para não estourar o limite do banco de dados
                fp_curta = forma_pagto[:50]

                venda = Venda(produto_id=prod.id, cliente_id=cliente_id, loja_id=loja_id, quantidade=qtd, valor_total=subtotal, forma_pagamento_1=fp_curta, data_previsao_fim=previsao, vendedor=vendedor_nome)
                db.session.add(venda)

        if cli and total_venda > 0:
            # 1. Abater o Cashback usado no pagamento misto
            if cashback_usado > 0:
                if cli.saldo_cashback >= cashback_usado:
                    cli.saldo_cashback -= cashback_usado
                else:
                    return jsonify({'sucesso': False, 'erro': 'Saldo de Cashback insuficiente!'}), 400

            # 2. Gerar Cashback NOVO apenas sobre o valor pago em dinheiro/cartão/pix
            valor_pago_normal = total_venda - cashback_usado
            if valor_pago_normal > 0 and "Fiado" not in forma_pagto:
                cashback_gerado = valor_pago_normal * 0.03
                if cli.saldo_cashback is None: cli.saldo_cashback = 0.0
                cli.saldo_cashback += cashback_gerado

        db.session.commit()
        loja = Loja.query.get(loja_id)
        return jsonify({'sucesso': True, 'msg': 'Venda registrada com sucesso!', 'loja_nome': loja.nome_fantasia})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 400


# ==========================================
# --- ROTAS DE RELATÓRIOS E COMISSÕES ---
# ==========================================
@app.route('/relatorios')
def relatorios():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']

    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    vendedor_filtro = request.args.get('vendedor')

    hoje_str = data_brasil().strftime('%Y-%m-%d')
    if not data_inicio: data_inicio = hoje_str
    if not data_fim: data_fim = hoje_str

    query = Venda.query.filter_by(loja_id=loja_id)
    inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
    fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
    query = query.filter(Venda.data_venda >= inicio, Venda.data_venda <= fim)

    if vendedor_filtro: query = query.filter(Venda.vendedor == vendedor_filtro)

    vendas = query.order_by(Venda.data_venda.desc()).all()
    total = custo_total = pix = credito = debito = dinheiro = fiado = 0.0

    for v in vendas:
        val = v.valor_total or 0.0
        total += val
        if v.produto: custo_total += (v.produto.preco_custo * v.quantidade)
        fp = (v.forma_pagamento_1 or '').lower()
        if 'pix' in fp: pix += val
        elif 'credito' in fp or 'crédito' in fp: credito += val
        elif 'debito' in fp or 'débito' in fp: debito += val
        elif 'dinheiro' in fp: dinheiro += val
        elif 'fiado' in fp or 'crediário' in fp: fiado += val

    vendedores_db = db.session.query(Venda.vendedor).filter_by(loja_id=loja_id).distinct().all()
    return render_template(
        'relatorios.html', vendas=vendas, total="%.2f" % total, lucro_total_formatado="%.2f" % (total - custo_total),
        pix="%.2f" % pix, pix_raw=pix, credito="%.2f" % credito, credito_raw=credito, debito="%.2f" % debito, debito_raw=debito,
        dinheiro="%.2f" % dinheiro, dinheiro_raw=dinheiro, fiado="%.2f" % fiado, fiado_raw=fiado,
        data_inicio=data_inicio, data_fim=data_fim, vendedor_filtro=vendedor_filtro, vendedores=[v[0] for v in vendedores_db if v[0]]
    )

@app.route('/exportar_relatorio')
def exportar_relatorio():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    vendedor_filtro = request.args.get('vendedor')

    query = Venda.query.filter_by(loja_id=loja_id)
    if data_inicio: query = query.filter(Venda.data_venda >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim: query = query.filter(Venda.data_venda <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1))
    if vendedor_filtro: query = query.filter(Venda.vendedor == vendedor_filtro)

    vendas = query.order_by(Venda.data_venda.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['DATA DA VENDA', 'VENDEDOR', 'PRODUTO', 'QUANTIDADE', 'FORMA DE PAGAMENTO', 'VALOR TOTAL (R$)'])
    for v in vendas:
        nome_prod = v.produto.nome if v.produto else ('Pagamento Fiado' if 'Pgto' in (v.forma_pagamento_1 or '') else ('Serviço Banho/Tosa' if 'Banho/Tosa' in (v.forma_pagamento_1 or '') else 'Produto Excluído'))
        writer.writerow([v.data_venda.strftime('%d/%m/%Y %H:%M'), v.vendedor, nome_prod, v.quantidade, v.forma_pagamento_1, "%.2f" % v.valor_total])
    response = Response(output.getvalue().encode('utf-8-sig'), mimetype='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename=relatorio_petstock_{data_brasil()}.csv"
    return response

@app.route('/comissoes')
def comissoes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']

    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    hoje_str = data_brasil().strftime('%Y-%m-%d')
    if not data_inicio: data_inicio = hoje_str
    if not data_fim: data_fim = hoje_str

    inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    fim = datetime.strptime(data_fim, '%Y-%m-%d').date()

    servicos_comissionados = Agendamento.query.filter(
        Agendamento.loja_id == loja_id,
        Agendamento.status == 'Concluído',
        Agendamento.data_agendamento >= inicio,
        Agendamento.data_agendamento <= fim,
        Agendamento.funcionario_id != None
    ).order_by(Agendamento.data_agendamento.desc()).all()

    resumo_profissionais = {}
    for s in servicos_comissionados:
        if not s.profissional: continue
        nome = s.profissional.nome
        if nome not in resumo_profissionais:
            resumo_profissionais[nome] = {'total_servicos': 0, 'valor_gerado': 0.0, 'comissao_devida': 0.0}
        resumo_profissionais[nome]['total_servicos'] += 1
        resumo_profissionais[nome]['valor_gerado'] += s.valor_servico
        resumo_profissionais[nome]['comissao_devida'] += s.valor_comissao

    return render_template('comissoes.html', servicos=servicos_comissionados, resumo=resumo_profissionais, data_inicio=data_inicio, data_fim=data_fim)

@app.route('/editar_comissao', methods=['POST'])
def editar_comissao():
    if 'loja_id' not in session: return redirect(url_for('login'))

    agendamento_id = request.form.get('agendamento_id')
    novo_valor_str = request.form.get('novo_valor', '0').replace('.', '').replace(',', '.')

    try: novo_valor = float(novo_valor_str)
    except: novo_valor = 0.0

    agendamento = Agendamento.query.get(agendamento_id)
    if agendamento and agendamento.loja_id == session['loja_id']:
        agendamento.valor_comissao = novo_valor
        db.session.commit()
        flash('✏️ Valor da comissão atualizado com sucesso!', 'success')

    return redirect(request.referrer or url_for('comissoes'))

# ==========================================
# --- CONFIGURAÇÕES DA LOJA ---
# ==========================================
@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja = Loja.query.get(session['loja_id'])
    if request.method == 'POST':
        loja.chave_pix = request.form.get('chave_pix')
        db.session.commit()
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('configuracoes'))
    return render_template('configuracoes.html')

# ==========================================
# --- PAINEL CEO (ACESSO RESTRITO) ---
# ==========================================
@app.route('/login_ceo', methods=['GET', 'POST'])
@csrf.exempt
@limiter.limit("5 per minute")
def login_ceo():
    if request.method == 'POST':
        senha = request.form.get('senha_mestre', '')
        senha_correta = os.environ.get('CEO_SENHA', '')
        if senha_correta and senha == senha_correta:
            session['ceo_logado'] = True
            return redirect(url_for('admin_guilherme'))
        flash('❌ Acesso Negado! Senha incorreta.', 'danger')
    return render_template('login_ceo.html')

@app.route('/admin_guilherme', methods=['GET', 'POST'])
def admin_guilherme():
    if not session.get('ceo_logado'): return redirect(url_for('login_ceo'))
    hoje = data_brasil()
    if request.method == 'POST':
        novo_usuario = request.form.get('usuario', '').strip().lower()
        if Loja.query.filter_by(usuario=novo_usuario).first():
            flash('❌ Esse usuário já existe. Escolha outro.', 'danger')
            return redirect(url_for('admin_guilherme'))
        valor_plano = float(os.environ.get('VALOR_PLANO', '80.00'))
        db.session.add(Loja(nome_fantasia=request.form.get('nome_fantasia'), usuario=novo_usuario, senha=generate_password_hash('123456'), data_vencimento=datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date(), valor_plano=valor_plano))
        db.session.commit()
        flash('✅ Nova loja criada com sucesso!', 'success')
        return redirect(url_for('admin_guilherme'))

    todas_lojas = Loja.query.all()
    mrr = sum(l.valor_plano or 80.0 for l in todas_lojas if l.data_vencimento >= hoje)
    previsao_7_dias = sum(l.valor_plano or 80.0 for l in todas_lojas if hoje <= l.data_vencimento <= hoje + timedelta(days=7))
    return render_template('admin.html', lojas=todas_lojas, total_clientes=len(todas_lojas), clientes_ativos=sum(1 for l in todas_lojas if l.data_vencimento >= hoje), clientes_inadimplentes=sum(1 for l in todas_lojas if l.data_vencimento < hoje), mrr=mrr, previsao_7_dias=previsao_7_dias, today_date=str(hoje))

@app.route('/editar_loja/<int:id>', methods=['GET', 'POST'])
def editar_loja(id):
    if not session.get('ceo_logado'): return redirect(url_for('login_ceo'))
    loja = Loja.query.get(id)
    if not loja: return redirect(url_for('admin_guilherme'))
    if request.method == 'POST':
        loja.nome_fantasia = request.form.get('nome_fantasia')
        loja.usuario = request.form.get('usuario').strip().lower()
        loja.data_vencimento = datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date()
        db.session.commit()
        flash('✅ Loja atualizada com sucesso!', 'success')
        return redirect(url_for('admin_guilherme'))
    return render_template('editar_loja.html', loja=loja)

@app.route('/resetar_senha_loja/<int:id>')
def resetar_senha_loja(id):
    if not session.get('ceo_logado'): return redirect(url_for('login_ceo'))
    loja = Loja.query.get(id)
    if loja:
        loja.senha = generate_password_hash('123456')
        db.session.commit()
        flash(f'🔄 Senha da loja {loja.nome_fantasia} resetada para 123456.', 'success')
    return redirect(url_for('admin_guilherme'))

@app.route('/excluir_loja/<int:id>')
def excluir_loja(id):
    if not session.get('ceo_logado'): return redirect(url_for('login_ceo'))
    loja = Loja.query.get(id)
    if loja:
        Produto.query.filter_by(loja_id=loja.id).delete()
        db.session.delete(loja)
        db.session.commit()
        flash('🗑️ Loja excluída com sucesso.', 'warning')
    return redirect(url_for('admin_guilherme'))

@app.route('/logout_ceo')
def logout_ceo():
    session.pop('ceo_logado', None)
    return redirect(url_for('login_ceo'))

# ==========================================
# --- ROTAS DA AGENDA DE SERVIÇOS (BANHO E TOSA) ---
# ==========================================
@app.route('/agenda', methods=['GET', 'POST'])
def agenda():
    if 'loja_id' not in session: return redirect(url_for('login'))
    loja_id = session['loja_id']

    if request.method == 'POST':
        cliente_id_str = request.form.get('cliente_id')
        cliente_id = int(cliente_id_str) if cliente_id_str else None

        func_id_str = request.form.get('funcionario_id')
        func_id = int(func_id_str) if func_id_str else None

        try: valor = float(request.form.get('valor_servico', '0').replace('.', '').replace(',', '.'))
        except: valor = 0.0

        novo_agendamento = Agendamento(
            cliente_id=cliente_id, loja_id=loja_id, funcionario_id=func_id,
            nome_pet=request.form.get('nome_pet'), raca_porte=request.form.get('raca_porte'),
            servico=request.form.get('servico'), valor_servico=valor,
            data_agendamento=datetime.strptime(request.form.get('data_agendamento'), '%Y-%m-%d').date(),
            hora_agendamento=request.form.get('hora_agendamento'), observacoes=request.form.get('observacoes'), status='Agendado'
        )
        db.session.add(novo_agendamento)
        db.session.commit()
        flash('✅ Horário agendado com sucesso!', 'success')
        return redirect(url_for('agenda'))

    hoje = data_brasil()
    data_filtro_str = request.args.get('data_filtro', hoje.strftime('%Y-%m-%d'))
    data_filtro = datetime.strptime(data_filtro_str, '%Y-%m-%d').date()

    agendamentos = Agendamento.query.filter_by(loja_id=loja_id, data_agendamento=data_filtro).order_by(Agendamento.hora_agendamento.asc()).all()
    clientes_loja = Cliente.query.filter_by(loja_id=loja_id).order_by(Cliente.nome).all()
    equipe_loja = Funcionario.query.filter_by(loja_id=loja_id).all()

    return render_template('agenda.html', agendamentos=agendamentos, data_filtro=data_filtro_str, clientes=clientes_loja, equipe=equipe_loja)

@app.route('/editar_agendamento', methods=['POST'])
def editar_agendamento():
    if 'loja_id' not in session: return redirect(url_for('login'))

    agendamento_id = request.form.get('agendamento_id')
    agendamento = Agendamento.query.get(agendamento_id)

    if agendamento and agendamento.loja_id == session['loja_id']:
        agendamento.nome_pet = request.form.get('nome_pet')
        agendamento.raca_porte = request.form.get('raca_porte')
        agendamento.servico = request.form.get('servico')
        agendamento.data_agendamento = datetime.strptime(request.form.get('data_agendamento'), '%Y-%m-%d').date()
        agendamento.hora_agendamento = request.form.get('hora_agendamento')
        agendamento.observacoes = request.form.get('observacoes')

        try: valor = float(request.form.get('valor_servico', '0').replace('.', '').replace(',', '.'))
        except: valor = 0.0
        agendamento.valor_servico = valor

        func_id_str = request.form.get('funcionario_id')
        agendamento.funcionario_id = int(func_id_str) if func_id_str else None

        if agendamento.status == 'Concluído' and agendamento.funcionario_id:
            func = Funcionario.query.get(agendamento.funcionario_id)
            if func and func.comissao_servicos > 0:
                agendamento.valor_comissao = agendamento.valor_servico * (func.comissao_servicos / 100.0)
            else:
                agendamento.valor_comissao = 0.0

        db.session.commit()
        flash('✅ Agendamento atualizado com sucesso!', 'success')
    else:
        flash('❌ Erro ao atualizar o agendamento.', 'danger')

    return redirect(request.referrer or url_for('agenda'))

@app.route('/mudar_status_agenda/<int:id>/<status>')
def mudar_status_agenda(id, status):
    if 'loja_id' not in session: return redirect(url_for('login'))
    agendamento = Agendamento.query.get_or_404(id)

    if agendamento.loja_id == session['loja_id']:
        agendamento.status = status

        if status == 'Concluído' and agendamento.valor_servico > 0:
            if agendamento.funcionario_id:
                func = Funcionario.query.get(agendamento.funcionario_id)
                if func and func.comissao_servicos > 0:
                    agendamento.valor_comissao = agendamento.valor_servico * (func.comissao_servicos / 100.0)

            venda_servico = Venda(
                produto_id=None, cliente_id=agendamento.cliente_id, loja_id=session['loja_id'],
                quantidade=1.0, valor_total=agendamento.valor_servico, forma_pagamento_1='Dinheiro (Banho/Tosa)',
                data_venda=hora_brasil(), vendedor=session.get('vendedor_atual', 'Dono/Gerente')
            )
            db.session.add(venda_servico)
            flash(f'🚿 Serviço concluído! O valor foi lançado no caixa e comissão registrada.', 'success')
        elif status == 'Cancelado':
            flash('🚫 Agendamento cancelado.', 'warning')
        else:
            flash('🚿 Status do serviço atualizado.', 'success')

        db.session.commit()
    return redirect(url_for('agenda'))


# --- Inicialização ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False)