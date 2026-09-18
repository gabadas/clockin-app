import os
from flask import Flask, request, jsonify, render_template, session, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "ponto-super-secret-2026")
# Supabase URL - Vercel vai injetar
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or "sqlite:///local.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

MASTER_EMAIL = "gaasbrel@gmail.com"

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), default="comum")

class Ponto(db.Model):
    __tablename__ = "pontos"
    id = db.Column(db.String(50), primary_key=True) # formato: uid_mes_dia
    uid = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    email = db.Column(db.String(120))
    mes = db.Column(db.String(7), nullable=False) # YYYY-MM
    dia = db.Column(db.Integer, nullable=False)
    entrada = db.Column(db.String(5))
    almocoSaida = db.Column(db.String(5))
    almocoVolta = db.Column(db.String(5))
    saida = db.Column(db.String(5))

class Bloqueio(db.Model):
    __tablename__ = "bloqueios"
    data = db.Column(db.String(10), primary_key=True) # YYYY-MM-DD
    bloqueado = db.Column(db.Boolean, default=False)
    motivo = db.Column(db.String(255))

with app.app_context():
    db.create_all()
    # Cria super user se não existir
    if not Usuario.query.filter_by(email=MASTER_EMAIL).first():
        print(f"Criando super user {MASTER_EMAIL}")
        # senha inicial: admin123 - troca depois
        u = Usuario(email=MASTER_EMAIL, senha_hash=generate_password_hash("admin123"), tipo="super")
        db.session.add(u); db.session.commit()

def login_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if 'user' not in session: return redirect('/login')
        return f(*a, **kw)
    return deco

def is_master(email):
    return email and email.lower() == MASTER_EMAIL.lower()

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email','').lower().strip()
    senha = data.get('senha','')
    if not email or not senha: return jsonify({'error':'preencha tudo'}),400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({'error':'email já existe'}),400
    tipo = 'super' if is_master(email) else 'comum'
    u = Usuario(email=email, senha_hash=generate_password_hash(senha), tipo=tipo)
    db.session.add(u); db.session.commit()
    return jsonify({'ok':True})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email','').lower().strip()
    senha = data.get('senha','')
    user = Usuario.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.senha_hash, senha):
        return jsonify({'error':'email ou senha inválidos'}),401
    session['user'] = {'id':user.id, 'email':user.email, 'tipo':user.tipo}
    return jsonify({'ok':True})

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')

@app.route('/')
@login_required
def index():
    return render_template('app.html', user=session['user'], is_master=is_master(session['user']['email']))

@app.route('/api/pontos', methods=['GET'])
@login_required
def get_pontos():
    uid = int(request.args.get('uid')); mes = request.args.get('mes')
    pontos = Ponto.query.filter_by(uid=uid, mes=mes).all()
    result = {str(p.dia): {'entrada':p.entrada,'almocoSaida':p.almocoSaida,'almocoVolta':p.almocoVolta,'saida':p.saida,'dia':p.dia,'mes':p.mes,'uid':p.uid} for p in pontos}
    return jsonify(result)

@app.route('/api/pontos', methods=['POST'])
@login_required
def save_ponto():
    d = request.json
    doc_id = f"{d['uid']}_{d['mes']}_{int(d['dia'])}"
    p = Ponto.query.get(doc_id)
    if not p:
        p = Ponto(id=doc_id, uid=int(d['uid']), email=d.get('email','').lower(), mes=d['mes'], dia=int(d['dia']))
        db.session.add(p)
    p.entrada = d.get('entrada') or None
    p.almocoSaida = d.get('almocoSaida') or None
    p.almocoVolta = d.get('almocoVolta') or None
    p.saida = d.get('saida') or None
    db.session.commit()
    return jsonify({'ok':True})

@app.route('/api/usuarios')
@login_required
def list_usuarios():
    if not is_master(session['user']['email']): return jsonify([]),403
    users = Usuario.query.all()
    return jsonify([{'uid':u.id,'id':u.id,'email':u.email,'tipo':u.tipo} for u in users])

@app.route('/api/bloqueios', methods=['GET','POST'])
@login_required
def bloqueios():
    if request.method == 'GET':
        return jsonify({b.data:{'bloqueado':b.bloqueado,'motivo':b.motivo} for b in Bloqueio.query.all()})
    if not is_master(session['user']['email']): return jsonify({'error':'so super'}),403
    d = request.json
    b = Bloqueio.query.get(d['data']) or Bloqueio(data=d['data'])
    b.bloqueado = d['bloqueado']; b.motivo = d.get('motivo','')
    db.session.add(b); db.session.commit()
    return jsonify({'ok':True})