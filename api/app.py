import os
from flask import Flask, request, jsonify, render_template, session, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "ponto-super-secret-2026")

db_url = os.getenv("DATABASE_URL")
if not db_url:
    # local fallback
    db_url = "sqlite:///local.db"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
if "postgresql" in db_url and "sslmode" not in db_url:
    db_url += "?sslmode=require" if "?" not in db_url else "&sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True}

db = SQLAlchemy(app)

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)

class Ponto(db.Model):
    __tablename__ = "pontos"
    id = db.Column(db.String(50), primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    mes = db.Column(db.String(7), nullable=False)
    dia = db.Column(db.Integer, nullable=False)
    entrada = db.Column(db.String(5))
    almocoSaida = db.Column(db.String(5))
    almocoVolta = db.Column(db.String(5))
    saida = db.Column(db.String(5))

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if 'user' not in session: return redirect('/login')
        return f(*a, **kw)
    return deco

@app.route('/login')
def login_page(): return render_template('login.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email','').lower().strip()
    senha = data.get('senha','')
    if not email or not senha: return jsonify({'error':'preencha tudo'}),400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({'error':'email já existe'}),400
    u = Usuario(email=email, senha_hash=generate_password_hash(senha))
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
    session['user'] = {'id':user.id, 'email':user.email}
    return jsonify({'ok':True})

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')

@app.route('/')
@login_required
def index():
    return render_template('app.html', user=session['user'])

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
        p = Ponto(id=doc_id, uid=int(d['uid']), mes=d['mes'], dia=int(d['dia']))
        db.session.add(p)
    p.entrada = d.get('entrada') or None
    p.almocoSaida = d.get('almocoSaida') or None
    p.almocoVolta = d.get('almocoVolta') or None
    p.saida = d.get('saida') or None
    db.session.commit()
    return jsonify({'ok':True})

@app.route('/api/pontos', methods=['DELETE'])
@login_required
def delete_ponto():
    d = request.json
    doc_id = f"{d['uid']}_{d['mes']}_{int(d['dia'])}"
    p = Ponto.query.get(doc_id)
    if p: db.session.delete(p); db.session.commit()
    return jsonify({'ok':True})
