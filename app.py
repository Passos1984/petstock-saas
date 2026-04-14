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

# --- Carrega variáveis do .env ---
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÃO SEGURA (tudo vem do .env) --- 
basedir = os.path.abspath(os.path.dirname(__file__))
db_dir = os.path.join(basedir, 'instance')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(db_dir, 'petstock.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'troque-essa-chave-no-env')
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

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

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
    plano = db.Column(db.String(50), default='pro') # gratis, pro, elite

class Funcionario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    usuario = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(255), nullable=False)
    cargo = db.Column(db.String(50), default='Caixa')
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

# CIRURGIA: Nova tabela para a Agenda de Banho e Tosa
class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False)
    nome_pet = db.Column(db.String(100), nullable=False)
    raca_porte = db.Column(db.String(100))
    servico = db.Column(db.String(100), nullable=False) # Ex: Banho, Tosa, Hidratação
    valor_servico = db.Column(db.Float, default=0.0)
    data_agendamento = db.Column(db.Date, nullable=False)
    hora_agendamento = db.Column(db.String(10), nullable=False) # Ex: 14:30
    status = db.Column(db.String(50), default='Agendado') # Agendado, Em Andamento, Concluído, Cancelado
    observacoes = db.Column(db.String(255))
    cliente = db.relationship('Cliente', backref='agendamentos')


@app.context_processor
def injetar_dados_globais():
    loja_atual = None
    if 'loja_id' in session:
        loja_atual = Loja.query.get(session['loja_id'])
    return dict(
        loja_logada=loja_atual,
        vendas_hoje="0,00",
        lucro_hoje="0,00",
        alertas_radar=0,
        cargo='Gerente',
        vendedor_atual='Dono/Gerente'
    )


# ==========================================
# --- ROTA PRINCIPAL (LANDING PAGE) ---
# ==========================================
@app.route('/')
def index():
    # Se já estiver logado, pula a landing page e vai pro painel
    if 'loja_id' in session:
        return redirect(url_for('painel'))
    return render_template('landing.html')

# ==========================================
# --- ROTA DE ASSINATURA (FREE TRIAL) ---
# ==========================================
@app.route('/assinar', methods=['POST'])
@limiter.limit("5 per minute")
def assinar():
    try:
        nome_fantasia = request.form.get('nome_fantasia')
        telefone = request.form.get('telefone')
        email = request.form.get('email')
        senha = request.form.get('senha')
        plano_escolhido = request.form.get('plano', 'pro')

        # Verifica se o email (usuário) já existe
        if Loja.query.filter_by(usuario=email).first():
            flash('❌ Este e-mail já está cadastrado. Faça login ou use outro.', 'danger')
            return redirect(url_for('index'))

        # Define valor baseado no plano
        valor = 0.0
        if plano_escolhido == 'pro':
            valor = 80.00
        elif plano_escolhido == 'elite':
            valor = 150.00

        # Cria a loja dando 15 DIAS GRÁTIS de teste!
        nova_loja = Loja(
            nome_fantasia=nome_fantasia,
            usuario=email, # O email será o login
            email=email,
            telefone=telefone,
            senha=generate_password_hash(senha),
            data_vencimento=data_brasil() + timedelta(days=15),
            valor_plano=valor,
            plano=plano_escolhido
        )
        
        db.session.add(nova_loja)
        db.session.commit()

        # Já loga o cliente automaticamente na primeira vez
        session['loja_id'] = nova_loja.id
        logger.info(f"Nova Assinatura Trial: {nome_fantasia} ({plano_escolhido})")
        
        flash('🎉 Bem-vindo ao PetStock! Seus 15 dias grátis começaram agora.', 'success')
        return redirect(url_for('painel'))
        
    except Exception as e:
        logger.error(f"Erro ao criar assinatura: {e}")
        flash('❌ Ocorreu um erro. Tente novamente.', 'danger')
        return redirect(url_for('index'))


# ==========================================
# --- ROTAS DE LOGIN DA LOJA ---
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
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
                logger.warning(f"Login bloqueado - assinatura vencida: loja_id={loja.id}")
                flash(f'⚠️ ASSINATURA VENCIDA! Sua licença expirou. <a href="{zap}" target="_blank" style="color: inherit; text-decoration: underline; font-weight: 900;">Clique aqui para renovar.</a>', 'danger')
                return render_template('login.html')
            elif dias_restantes <= 2:
                flash(f'⚠️ ATENÇÃO! Sua assinatura vence em {dias_restantes} dia(s). <a href="{zap}" target="_blank" style="color: inherit; text-decoration: underline; font-weight: 900;">Renovar.</a>', 'warning')

            logger.info(f"Login bem-sucedido: loja_id={loja.id} usuario={u}")

            if check_password_hash(loja.senha, '123456'):
                session['reset_loja_id'] = loja.id
                return redirect(url_for('mudar_senha'))

            session['loja_id'] = loja.id
            return redirect(url_for('painel'))

        logger.warning(f"Tentativa de login falhou: usuario={u} ip={request.remote_addr}")
        flash('❌ Usuário ou senha incorretos.', 'danger')

    return render_template('login.html')


@app.route('/mudar_senha', methods=['GET', 'POST'])
def mudar_senha():
    l_id = session.get('reset_loja_id') or session.get('loja_id')
    if not l_id:
        return redirect(url_for('login'))

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
    loja_id = session.get('loja_id')
    logger.info(f"Logout: loja_id={loja_id}")
    session.clear()
    return redirect(url_for('login'))


# ==========================================
# --- ROTAS DE EQUIPE (FUNCIONÁRIOS) ---
# ==========================================
@app.route('/funcionarios', methods=['GET', 'POST'])
def funcionarios():
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip().lower()
        if Funcionario.query.filter_by(usuario=usuario).first():
            flash('❌ Esse nome de usuário já está em uso. Escolha outro.', 'danger')
            return redirect(url_for('funcionarios'))

        novo_func = Funcionario(
            nome=request.form.get('nome'),
            usuario=usuario,
            senha=generate_password_hash('123456'),
            cargo=request.form.get('cargo'),
            loja_id=session['loja_id']
        )
        db.session.add(novo_func)
        db.session.commit()
        logger.info(f"Funcionário criado: {usuario} loja_id={session['loja_id']}")
        flash('✅ Funcionário cadastrado com acesso gerado!', 'success')
        return redirect(url_for('funcionarios'))

    lista_func = Funcionario.query.filter_by(loja_id=session['loja_id']).all()
    return render_template('funcionarios.html', funcionarios=lista_func)


@app.route('/excluir_funcionario/<int:id>')
def excluir_funcionario(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    func = Funcionario.query.get(id)
    if func and func.loja_id == session['loja_id']:
        db.session.delete(func)
        db.session.commit()
        flash('🗑️ Acesso do funcionário revogado.', 'warning')
    return redirect(url_for('funcionarios'))


@app.route('/resetar_senha/<int:id>')
def resetar_senha(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    func = Funcionario.query.get(id)
    if func and func.loja_id == session['loja_id']:
        func.senha = generate_password_hash('123456')
        db.session.commit()
        flash(f'🔄 A senha de {func.nome} voltou para 123456.', 'success')
    return redirect(url_for('funcionarios'))


# ==========================================
# --- ROTAS DE GESTÃO DE ESTOQUE ---
# ==========================================
@app.route('/painel')
def painel():
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)

    produtos_paginados = Produto.query.filter_by(
        loja_id=session['loja_id'], ativo=True
    ).paginate(page=page, per_page=50, error_out=False)

    total_prods = Produto.query.filter_by(loja_id=session['loja_id']).count()
    proximo_sku = str(total_prods + 1).zfill(2)

    return render_template('index.html', produtos=produtos_paginados, proximo_sku=proximo_sku)

@app.route('/cadastrar_produto', methods=['POST'])
def cadastrar_produto():
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    sku_recebido = request.form.get('sku', '').strip()
    if not sku_recebido:
        sku_recebido = f"PET-{random.randint(10000, 99999)}"

    nome_base = request.form.get('nome', '').strip()
    tipo = request.form.get('tipo_produto', '').strip()
    nome_final = f"{nome_base} - {tipo}" if tipo else nome_base

    try:
        p_custo = float(request.form.get('preco_custo', '0').replace('.', '').replace(',', '.'))
    except:
        p_custo = 0.0
    try:
        p_venda = float(request.form.get('preco', '0').replace('.', '').replace(',', '.'))
    except:
        p_venda = 0.0
    try:
        qtd = float(request.form.get('quantidade', '0').replace('.', '').replace(',', '.'))
    except:
        qtd = 0.0

    novo_produto = Produto(
        codigo_sku=sku_recebido,
        nome=nome_final,
        categoria=request.form.get('categoria'),
        preco_custo=p_custo,
        preco_venda=p_venda,
        estoque=qtd,
        loja_id=session['loja_id']
    )
    db.session.add(novo_produto)
    db.session.commit()
    flash('✅ Produto salvo no estoque com sucesso!', 'success')
    return redirect(url_for('painel'))


@app.route('/desmembrar', methods=['POST'])
def desmembrar():
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    origem_id = request.form.get('origem_id')
    destino_id = request.form.get('destino_id')
    try:
        qtd_origem = float(request.form.get('qtd_origem', '0').replace(',', '.'))
    except:
        qtd_origem = 0.0
    try:
        qtd_destino = float(request.form.get('qtd_destino', '0').replace(',', '.'))
    except:
        qtd_destino = 0.0

    prod_origem = Produto.query.get(origem_id)
    prod_destino = Produto.query.get(destino_id)

    if (prod_origem and prod_destino
            and prod_origem.loja_id == session['loja_id']
            and prod_destino.loja_id == session['loja_id']):
        if prod_origem.estoque >= qtd_origem:
            prod_origem.estoque -= qtd_origem
            prod_destino.estoque += qtd_destino
            db.session.commit()
            flash(f'⚖️ Sucesso! Transformamos {qtd_origem} saco(s) em {qtd_destino} KG a granel.', 'success')
        else:
            flash('❌ Erro: Você não tem essa quantidade no estoque!', 'danger')
    return redirect(url_for('painel'))


@app.route('/editar_produto/<int:id>', methods=['GET', 'POST'])
def editar_produto(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    prod = Produto.query.get(id)
    if not prod or prod.loja_id != session['loja_id']:
        return redirect(url_for('painel'))

    if request.method == 'POST':
        prod.codigo_sku = request.form.get('sku')
        prod.nome = request.form.get('nome')
        prod.categoria = request.form.get('categoria')
        try:
            prod.preco_custo = float(request.form.get('preco_custo', '0').replace('.', '').replace(',', '.'))
        except:
            pass
        try:
            prod.preco_venda = float(request.form.get('preco', '0').replace('.', '').replace(',', '.'))
        except:
            pass
        try:
            prod.estoque = float(request.form.get('quantidade', '0').replace('.', '').replace(',', '.'))
        except:
            pass
        db.session.commit()
        flash('✅ Produto atualizado com sucesso!', 'success')
        return redirect(url_for('painel'))

    return render_template('editar_produto.html', p=prod)


@app.route('/inativar_produto/<int:id>')
def inativar_produto(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    prod = Produto.query.get(id)
    if prod and prod.loja_id == session['loja_id']:
        prod.ativo = False
        db.session.commit()
        flash('🗑️ Produto movido para a Lixeira.', 'warning')
    return redirect(url_for('painel'))


@app.route('/inativos')
def inativos():
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    prods = Produto.query.filter_by(loja_id=session['loja_id'], ativo=False).all()
    return render_template('inativos.html', produtos=prods)


@app.route('/dar_baixa', methods=['POST'])
def baixa_estoque():
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    produto_id = request.form.get('produto_id')
    motivo = request.form.get('motivo')
    try:
        qtd = float(request.form.get('quantidade', '0').replace(',', '.'))
    except:
        qtd = 0.0

    produto = Produto.query.get(produto_id)

    if produto and produto.loja_id == session['loja_id']:
        if produto.estoque >= qtd:
            produto.estoque -= qtd
            venda_baixa = Venda(
                produto_id=produto.id,
                loja_id=session['loja_id'],
                quantidade=qtd,
                valor_total=0.0,
                forma_pagamento_1=f"Baixa: {motivo}",
                vendedor=session.get('vendedor_atual', 'Dono/Gerente')
            )
            db.session.add(venda_baixa)
            db.session.commit()
            flash(f'🔻 Baixa de {qtd}x {produto.nome} registrada como {motivo}.', 'warning')
        else:
            flash('❌ Erro: Quantidade insuficiente em estoque para dar baixa.', 'danger')

    return redirect(url_for('painel'))


@app.route('/restaurar_produto/<int:id>')
def restaurar_produto(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    prod = Produto.query.get(id)
    if prod and prod.loja_id == session['loja_id']:
        prod.ativo = True
        db.session.commit()
        flash('♻️ Produto restaurado para o estoque!', 'success')
    return redirect(url_for('inativos'))


@app.route('/importar_produtos', methods=['POST'])
def importar_produtos():
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    arquivo = request.files.get('arquivo')

    if not arquivo or arquivo.filename == '':
        flash('❌ Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('painel'))

    try:
        stream = io.StringIO(arquivo.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream, delimiter=',')
        next(csv_input, None)

        cadastrados = 0
        for row in csv_input:
            if len(row) >= 4:
                try:
                    custo = float(row[4].replace(',', '.')) if len(row) > 4 and row[4] else 0.0
                except:
                    custo = 0.0
                try:
                    estoque = float(row[5].replace(',', '.')) if len(row) > 5 and row[5] else 0.0
                except:
                    estoque = 0.0
                try:
                    venda = float(row[3].replace(',', '.'))
                except:
                    venda = 0.0

                p = Produto(
                    codigo_sku=row[0],
                    nome=row[1],
                    categoria=row[2],
                    preco_venda=venda,
                    preco_custo=custo,
                    estoque=estoque,
                    loja_id=session['loja_id']
                )
                db.session.add(p)
                cadastrados += 1

        db.session.commit()
        flash(f'✅ Importação Concluída! {cadastrados} produtos adicionados.', 'success')
    except Exception as e:
        logger.error(f"Erro na importação de produtos: {e}")
        flash(f'❌ Erro na importação. Salve sua planilha como CSV (UTF-8).', 'danger')

    return redirect(url_for('painel'))


# ==========================================
# --- ROTAS DE REPRESENTANTES ---
# ==========================================
@app.route('/representantes', methods=['GET', 'POST'])
def representantes():
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        novo_rep = Representante(
            nome_fantasia=request.form.get('nome_fantasia'),
            cnpj=request.form.get('cnpj'),
            representante_nome=request.form.get('representante_nome'),
            whatsapp=request.form.get('whatsapp'),
            pedido_minimo=request.form.get('pedido_minimo'),
            prazo_entrega=request.form.get('prazo_entrega'),
            observacoes=request.form.get('observacoes'),
            loja_id=session['loja_id']
        )
        db.session.add(novo_rep)
        db.session.commit()
        flash('✅ Fornecedor cadastrado com sucesso!', 'success')
        return redirect(url_for('representantes'))

    lista_rep = Representante.query.filter_by(loja_id=session['loja_id']).all()
    return render_template('representantes.html', representantes=lista_rep)


@app.route('/editar_representante/<int:id>', methods=['POST'])
def editar_representante(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
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


@app.route('/excluir_representante/<int:id>')
def excluir_representante(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    rep = Representante.query.get(id)
    if rep and rep.loja_id == session['loja_id']:
        db.session.delete(rep)
        db.session.commit()
        flash('🗑️ Fornecedor excluído com sucesso.', 'warning')
    return redirect(url_for('representantes'))


# ==========================================
# --- ROTA DO RADAR DE INTELIGÊNCIA ---
# ==========================================
@app.route('/radar')
def radar():
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    loja_id = session['loja_id']
    hoje = hora_brasil()
    daqui_7_dias = hoje + timedelta(days=7)

    alertas = Venda.query.filter(
        Venda.loja_id == loja_id,
        Venda.data_previsao_fim != None,
        Venda.data_previsao_fim <= daqui_7_dias
    ).order_by(Venda.data_previsao_fim.asc()).all()

    estoque_critico = Produto.query.filter(
        Produto.loja_id == loja_id,
        Produto.ativo == True,
        Produto.estoque < 5.0
    ).order_by(Produto.estoque.asc()).all()

    ranking_demanda = []
    return render_template('radar.html', alertas=alertas, estoque_critico=estoque_critico, ranking=ranking_demanda)


# ==========================================
# --- ROTAS DE CLIENTES E FIADO ---
# ==========================================
@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        pets = [
            request.form.get('nome_pet', '').strip(),
            request.form.get('nome_pet_2', '').strip(),
            request.form.get('nome_pet_3', '').strip()
        ]
        string_pets = " / ".join([p for p in pets if p])

        novo_cliente = Cliente(
            nome=request.form.get('nome'),
            telefone=request.form.get('telefone'),
            rua=request.form.get('rua'),
            numero=request.form.get('numero'),
            bairro=request.form.get('bairro'),
            nome_pet=string_pets,
            loja_id=session['loja_id']
        )
        db.session.add(novo_cliente)
        db.session.commit()
        flash('✅ Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))

    lista_clientes = Cliente.query.filter_by(loja_id=session['loja_id']).all()
    return render_template('clientes.html', clientes=lista_clientes)


@app.route('/excluir_cliente/<int:id>')
def excluir_cliente(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    cliente = Cliente.query.get(id)
    if cliente and cliente.loja_id == session['loja_id']:
        db.session.delete(cliente)
        db.session.commit()
        flash('🗑️ Cliente excluído com sucesso.', 'warning')
    return redirect(url_for('clientes'))


@app.route('/editar_cliente/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    cliente = Cliente.query.get_or_404(id)
    if cliente.loja_id != session['loja_id']:
        return redirect(url_for('clientes'))

    if request.method == 'POST':
        cliente.nome = request.form.get('nome')
        cliente.telefone = request.form.get('telefone')
        cliente.rua = request.form.get('rua')
        cliente.numero = request.form.get('numero')
        cliente.bairro = request.form.get('bairro')
        cliente.nome_pet = request.form.get('nome_pet')
        db.session.commit()
        flash('✅ Cadastro atualizado com sucesso!', 'success')
        return redirect(url_for('clientes'))

    return render_template('editar_cliente.html', c=cliente)


@app.route('/historico_cliente/<int:id>')
def historico_cliente(id):
    if 'loja_id' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401
    vendas = Venda.query.filter_by(
        cliente_id=id, loja_id=session['loja_id']
    ).order_by(Venda.data_venda.desc()).all()
    historico = []
    for v in vendas:
        nome_prod = v.produto.nome if v.produto else (
            '💰 Pagamento de Fiado' if 'Pgto' in (v.forma_pagamento_1 or '') else (
            '🛁 Serviço Banho/Tosa' if 'Banho/Tosa' in (v.forma_pagamento_1 or '') else 'Produto Excluído'
            )
        )
        historico.append({
            'data': v.data_venda.strftime('%d/%m/%Y %H:%M'),
            'produto': nome_prod,
            'qtd': v.quantidade,
            'valor': v.valor_total
        })
    return jsonify(historico)


@app.route('/api/divida_cliente/<int:id>', methods=['GET'])
def api_divida_cliente(id):
    if 'loja_id' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401
    vendas_fiado = Venda.query.filter_by(
        cliente_id=id,
        loja_id=session['loja_id'],
        forma_pagamento_1='Crediário / Fiado'
    ).all()
    total_divida = sum(v.valor_total for v in vendas_fiado if v.valor_total)
    return jsonify({'divida': total_divida})


@app.route('/api/pagar_divida/<int:id>', methods=['POST'])
def api_pagar_divida(id):
    if 'loja_id' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401

    dados = request.get_json() or {}
    forma_pagto = dados.get('forma_pagamento', 'Dinheiro')

    vendas_fiado = Venda.query.filter_by(
        cliente_id=id,
        loja_id=session['loja_id'],
        forma_pagamento_1='Crediário / Fiado'
    ).all()
    total_divida = sum(v.valor_total for v in vendas_fiado if v.valor_total)

    if total_divida <= 0:
        return jsonify({'sucesso': False, 'erro': 'Cliente não possui dívida ativa.'})

    for v in vendas_fiado:
        v.forma_pagamento_1 = 'Fiado (Pago)'

    pagamento = Venda(
        produto_id=None,
        cliente_id=id,
        loja_id=session['loja_id'],
        quantidade=0,
        valor_total=total_divida,
        forma_pagamento_1=f"{forma_pagto} (Pgto Fiado)",
        data_venda=hora_brasil(),
        vendedor=session.get('vendedor_atual', 'Dono/Gerente')
    )
    db.session.add(pagamento)
    db.session.commit()
    logger.info(f"Pagamento de fiado: cliente_id={id} valor={total_divida} loja_id={session['loja_id']}")
    return jsonify({'sucesso': True})


@app.route('/importar_clientes', methods=['POST'])
def importar_clientes():
    if 'loja_id' not in session:
        return redirect(url_for('login'))
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
                c = Cliente(
                    nome=row[0],
                    telefone=row[1],
                    rua=row[2] if len(row) > 2 else "",
                    numero=row[3] if len(row) > 3 else "",
                    bairro=row[4] if len(row) > 4 else "",
                    nome_pet=row[5] if len(row) > 5 else "",
                    loja_id=session['loja_id']
                )
                db.session.add(c)
                cadastrados += 1

        db.session.commit()
        flash(f'✅ Importação Concluída! {cadastrados} clientes adicionados.', 'success')
    except Exception as e:
        logger.error(f"Erro na importação de clientes: {e}")
        flash(f'❌ Erro na importação. Salve sua planilha como CSV (UTF-8).', 'danger')

    return redirect(url_for('clientes'))


# ==========================================
# --- ROTAS DO PDV (FRENTE DE CAIXA) ---
# ==========================================
@app.route('/pdv')
def pdv():
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    clientes_loja = Cliente.query.filter_by(
        loja_id=session['loja_id']
    ).order_by(Cliente.nome).all()
    equipe = Funcionario.query.filter_by(loja_id=session['loja_id']).all()
    return render_template('pdv.html', clientes=clientes_loja, equipe=equipe)


@app.route('/api/produtos', methods=['GET'])
def api_produtos():
    if 'loja_id' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401
    produtos = Produto.query.filter_by(loja_id=session['loja_id'], ativo=True).all()
    lista = [{
        'id': p.id,
        'sku': p.codigo_sku,
        'nome': p.nome,
        'preco': p.preco_venda,
        'custo': p.preco_custo,
        'estoque': p.estoque
    } for p in produtos]
    return jsonify(lista)


@app.route('/api/finalizar_venda', methods=['POST'])
def api_finalizar_venda():
    if 'loja_id' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401

    dados = request.get_json()
    loja_id = session['loja_id']
    nome_cliente = dados.get('cliente_nome', '').strip()
    forma_pagto = dados.get('forma_pagamento', 'Dinheiro')
    vendedor_nome = dados.get('vendedor_nome', 'Dono/Gerente')

    cliente_id = None
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

                venda = Venda(
                    produto_id=prod.id,
                    cliente_id=cliente_id,
                    loja_id=loja_id,
                    quantidade=qtd,
                    valor_total=subtotal,
                    forma_pagamento_1=forma_pagto,
                    data_previsao_fim=previsao,
                    vendedor=vendedor_nome
                )
                db.session.add(venda)

        db.session.commit()
        loja = Loja.query.get(loja_id)
        logger.info(f"Venda finalizada: loja_id={loja_id} vendedor={vendedor_nome} total=R${total_venda:.2f}")
        return jsonify({'sucesso': True, 'msg': 'Venda registrada com sucesso!', 'loja_nome': loja.nome_fantasia})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao finalizar venda: {e}")
        return jsonify({'sucesso': False, 'erro': str(e)}), 400


# ==========================================
# --- ROTAS DE RELATÓRIOS / FINANCEIRO ---
# ==========================================
@app.route('/relatorios')
def relatorios():
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    loja_id = session['loja_id']

    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    vendedor_filtro = request.args.get('vendedor')

    hoje_str = data_brasil().strftime('%Y-%m-%d')
    if not data_inicio:
        data_inicio = hoje_str
    if not data_fim:
        data_fim = hoje_str

    query = Venda.query.filter_by(loja_id=loja_id)
    inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
    fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
    query = query.filter(Venda.data_venda >= inicio, Venda.data_venda <= fim)

    if vendedor_filtro:
        query = query.filter(Venda.vendedor == vendedor_filtro)

    vendas = query.order_by(Venda.data_venda.desc()).all()

    total = custo_total = pix = credito = debito = dinheiro = fiado = 0.0

    for v in vendas:
        val = v.valor_total or 0.0
        total += val
        if v.produto:
            custo_total += (v.produto.preco_custo * v.quantidade)
        fp = (v.forma_pagamento_1 or '').lower()
        if 'pix' in fp:
            pix += val
        elif 'credito' in fp or 'crédito' in fp:
            credito += val
        elif 'debito' in fp or 'débito' in fp:
            debito += val
        elif 'dinheiro' in fp:
            dinheiro += val
        elif 'fiado' in fp or 'crediário' in fp:
            fiado += val

    vendedores_db = db.session.query(Venda.vendedor).filter_by(loja_id=loja_id).distinct().all()

    return render_template(
        'relatorios.html',
        vendas=vendas,
        total="%.2f" % total,
        lucro_total_formatado="%.2f" % (total - custo_total),
        pix="%.2f" % pix, pix_raw=pix,
        credito="%.2f" % credito, credito_raw=credito,
        debito="%.2f" % debito, debito_raw=debito,
        dinheiro="%.2f" % dinheiro, dinheiro_raw=dinheiro,
        fiado="%.2f" % fiado, fiado_raw=fiado,
        data_inicio=data_inicio,
        data_fim=data_fim,
        vendedor_filtro=vendedor_filtro,
        vendedores=[v[0] for v in vendedores_db if v[0]]
    )


@app.route('/exportar_relatorio')
def exportar_relatorio():
    if 'loja_id' not in session:
        return redirect(url_for('login'))
    loja_id = session['loja_id']

    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    vendedor_filtro = request.args.get('vendedor')

    query = Venda.query.filter_by(loja_id=loja_id)
    if data_inicio:
        query = query.filter(Venda.data_venda >= datetime.strptime(data_inicio, '%Y-%m-%d'))
    if data_fim:
        query = query.filter(Venda.data_venda <= datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1))
    if vendedor_filtro:
        query = query.filter(Venda.vendedor == vendedor_filtro)

    vendas = query.order_by(Venda.data_venda.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['DATA DA VENDA', 'VENDEDOR', 'PRODUTO', 'QUANTIDADE', 'FORMA DE PAGAMENTO', 'VALOR TOTAL (R$)'])

    for v in vendas:
        nome_prod = v.produto.nome if v.produto else (
            'Pagamento Fiado' if 'Pgto' in (v.forma_pagamento_1 or '') else (
            'Serviço Banho/Tosa' if 'Banho/Tosa' in (v.forma_pagamento_1 or '') else 'Produto Excluído'
            )
        )
        writer.writerow([
            v.data_venda.strftime('%d/%m/%Y %H:%M'),
            v.vendedor,
            nome_prod,
            v.quantidade,
            v.forma_pagamento_1,
            "%.2f" % v.valor_total
        ])

    response = Response(output.getvalue().encode('utf-8-sig'), mimetype='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename=relatorio_petstock_{data_brasil()}.csv"
    return response


# ==========================================
# --- CONFIGURAÇÕES DA LOJA ---
# ==========================================
@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    if 'loja_id' not in session:
        return redirect(url_for('login'))

    loja = Loja.query.get(session['loja_id'])

    if request.method == 'POST':
        nova_chave = request.form.get('chave_pix')
        loja.chave_pix = nova_chave
        db.session.commit()
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('configuracoes'))

    return render_template('configuracoes.html')


# ==========================================
# --- PAINEL CEO (ACESSO RESTRITO) ---
# ==========================================
@app.route('/login_ceo', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login_ceo():
    if request.method == 'POST':
        senha = request.form.get('senha_mestre', '')
        senha_correta = os.environ.get('CEO_SENHA', '')

        if senha_correta and senha == senha_correta:
            session['ceo_logado'] = True
            logger.info(f"Login CEO bem-sucedido ip={request.remote_addr}")
            return redirect(url_for('admin_guilherme'))

        logger.warning(f"Tentativa de acesso CEO falhou ip={request.remote_addr}")
        flash('❌ Acesso Negado! Senha incorreta.', 'danger')

    return render_template('login_ceo.html')


@app.route('/admin_guilherme', methods=['GET', 'POST'])
def admin_guilherme():
    if not session.get('ceo_logado'):
        return redirect(url_for('login_ceo'))

    hoje = data_brasil()

    if request.method == 'POST':
        novo_usuario = request.form.get('usuario', '').strip().lower()
        if Loja.query.filter_by(usuario=novo_usuario).first():
            flash('❌ Esse usuário já existe. Escolha outro.', 'danger')
            return redirect(url_for('admin_guilherme'))

        valor_plano = float(os.environ.get('VALOR_PLANO', '80.00'))

        db.session.add(Loja(
            nome_fantasia=request.form.get('nome_fantasia'),
            usuario=novo_usuario,
            senha=generate_password_hash('123456'),
            data_vencimento=datetime.strptime(request.form.get('data_vencimento'), '%Y-%m-%d').date(),
            valor_plano=valor_plano
        ))
        db.session.commit()
        logger.info(f"Nova loja criada: {novo_usuario}")
        flash('✅ Nova loja criada com sucesso!', 'success')
        return redirect(url_for('admin_guilherme'))

    todas_lojas = Loja.query.all()
    mrr = sum(l.valor_plano or 80.0 for l in todas_lojas if l.data_vencimento >= hoje)
    previsao_7_dias = sum(l.valor_plano or 80.0 for l in todas_lojas if hoje <= l.data_vencimento <= hoje + timedelta(days=7))

    return render_template(
        'admin.html',
        lojas=todas_lojas,
        total_clientes=len(todas_lojas),
        clientes_ativos=sum(1 for l in todas_lojas if l.data_vencimento >= hoje),
        clientes_inadimplentes=sum(1 for l in todas_lojas if l.data_vencimento < hoje),
        mrr=mrr,
        previsao_7_dias=previsao_7_dias,
        today_date=str(hoje)
    )


@app.route('/editar_loja/<int:id>', methods=['GET', 'POST'])
def editar_loja(id):
    if not session.get('ceo_logado'):
        return redirect(url_for('login_ceo'))
    loja = Loja.query.get(id)
    if not loja:
        return redirect(url_for('admin_guilherme'))

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
    if not session.get('ceo_logado'):
        return redirect(url_for('login_ceo'))
    loja = Loja.query.get(id)
    if loja:
        loja.senha = generate_password_hash('123456')
        db.session.commit()
        flash(f'🔄 Senha da loja {loja.nome_fantasia} resetada para 123456.', 'success')
    return redirect(url_for('admin_guilherme'))


@app.route('/excluir_loja/<int:id>')
def excluir_loja(id):
    if not session.get('ceo_logado'):
        return redirect(url_for('login_ceo'))
    loja = Loja.query.get(id)
    if loja:
        Produto.query.filter_by(loja_id=loja.id).delete()
        db.session.delete(loja)
        db.session.commit()
        logger.info(f"Loja excluída: id={id}")
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
    if 'loja_id' not in session:
        return redirect(url_for('login'))
        
    loja_id = session['loja_id']

    # Cadastro de um novo agendamento
    if request.method == 'POST':
        cliente_id_str = request.form.get('cliente_id')
        cliente_id = int(cliente_id_str) if cliente_id_str else None
        
        try:
            valor = float(request.form.get('valor_servico', '0').replace('.', '').replace(',', '.'))
        except:
            valor = 0.0

        novo_agendamento = Agendamento(
            cliente_id=cliente_id,
            loja_id=loja_id,
            nome_pet=request.form.get('nome_pet'),
            raca_porte=request.form.get('raca_porte'),
            servico=request.form.get('servico'),
            valor_servico=valor,
            data_agendamento=datetime.strptime(request.form.get('data_agendamento'), '%Y-%m-%d').date(),
            hora_agendamento=request.form.get('hora_agendamento'),
            observacoes=request.form.get('observacoes'),
            status='Agendado'
        )
        
        db.session.add(novo_agendamento)
        db.session.commit()
        flash('✅ Horário agendado com sucesso!', 'success')
        return redirect(url_for('agenda'))

    # Listagem para exibir na tela
    hoje = data_brasil()
    data_filtro_str = request.args.get('data_filtro', hoje.strftime('%Y-%m-%d'))
    data_filtro = datetime.strptime(data_filtro_str, '%Y-%m-%d').date()

    agendamentos = Agendamento.query.filter_by(
        loja_id=loja_id, 
        data_agendamento=data_filtro
    ).order_by(Agendamento.hora_agendamento.asc()).all()

    clientes_loja = Cliente.query.filter_by(loja_id=loja_id).order_by(Cliente.nome).all()

    return render_template(
        'agenda.html', 
        agendamentos=agendamentos, 
        data_filtro=data_filtro_str, 
        clientes=clientes_loja
    )

@app.route('/mudar_status_agenda/<int:id>/<status>')
def mudar_status_agenda(id, status):
    if 'loja_id' not in session:
        return redirect(url_for('login'))
        
    agendamento = Agendamento.query.get_or_404(id)
    
    if agendamento.loja_id == session['loja_id']:
        agendamento.status = status
        
        # CIRURGIA: Lançar venda automática no caixa ao concluir o banho
        if status == 'Concluído' and agendamento.valor_servico > 0:
            venda_servico = Venda(
                produto_id=None, # Não é um produto físico
                cliente_id=agendamento.cliente_id,
                loja_id=session['loja_id'],
                quantidade=1.0,
                valor_total=agendamento.valor_servico,
                forma_pagamento_1='Dinheiro (Banho/Tosa)', # Etiqueta especial
                data_venda=hora_brasil(),
                vendedor=session.get('vendedor_atual', 'Dono/Gerente')
            )
            db.session.add(venda_servico)
            flash(f'🚿 Serviço concluído! O valor de R$ {agendamento.valor_servico:.2f} foi lançado no caixa.', 'success')
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