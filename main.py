import os, random, datetime
import subprocess
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify

# --- Porté de msgError.py ---
def printE(msg, msgtype):
    time = datetime.datetime.now().strftime("%H:%M:%S")
    if msgtype == 1:
        print(f"{time}\033[32m SUCCESS {msg}\033[0m")
    elif msgtype == 2:
        print(f"{time}\033[33m INFO {msg}\033[0m")
    else:
        print(f"{time}\033[31m ERROR {msg}\033[0m")


# --- Configuration App ---
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///webmail.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', allow_unsafe_werkzeug=True)


# --- Modèles (Inspirés de la structure SQL) ---
class User(db.Model):
    __tablename__ = 'mlg_user'
    id = db.Column('user_id', db.Integer, primary_key=True)
    username = db.Column('user_name', db.String(64), unique=True)
    pw = db.Column('user_password', db.String(256))
    def set_password(self, p): self.pw = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.pw, p)

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    pin = db.Column('groups_pin', db.String(5), unique=True)
    creation = db.Column('groups_creation', db.String(10), default=lambda: datetime.date.today().isoformat())
    last_use = db.Column('groups_lastUse', db.String(10), default=lambda: datetime.date.today().isoformat())

class GroupUser(db.Model):
    __tablename__ = 'groups_user'
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column('user_id', db.Integer, db.ForeignKey('mlg_user.user_id'))
    pin = db.Column('groups_pin', db.String(5), db.ForeignKey('groups.groups_pin'))
    user = db.relationship('User', backref='memberships')
    group = db.relationship('Group', backref='members', primaryjoin="GroupUser.pin == Group.pin")

class Msg(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    c = db.Column('message_content', db.Text)
    uid = db.Column('user_id', db.Integer, db.ForeignKey('mlg_user.user_id'))
    pin = db.Column('groups_pin', db.String(5), db.ForeignKey('groups.groups_pin'))
    t = db.Column('message_sendtime', db.Integer, default=lambda: int(datetime.datetime.now().timestamp()))
    user = db.relationship('User')

# --- Logique métier fusionnée (Classes POO) ---
class Groupe:
    @staticmethod
    def create(creator_id):
        pin = str(random.randint(10000, 99999))
        while Group.query.filter_by(pin=pin).first():
            pin = str(random.randint(10000, 99999))
        g = Group(pin=pin)
        db.session.add(g)
        db.session.flush()
        gu = GroupUser(uid=creator_id, pin=pin)
        db.session.add(gu)
        db.session.commit()
        printE(f"Groupe {pin} créé", 1)
        return g

class Messaging:
    @staticmethod
    def send(sender_id, group_pin, content):
        m = Msg(c=content, uid=sender_id, pin=group_pin)
        db.session.add(m)
        db.session.commit()
        return m

with app.app_context():
    db.create_all()
    printE("Base de données initialisée", 1)

# --- Templates ---
LAYOUT_START = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script><script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script></head><body class="bg-gray-100">"""
LAYOUT_END = """</body></html>"""
T = {
    'a': LAYOUT_START + """<div class="min-h-screen flex items-center justify-center"><form method="POST" class="bg-white p-8 rounded shadow-md w-80"><h1 class="text-xl mb-4 text-center">{{t}}</h1>{% with m=get_flashed_messages() %}{% if m %}<p class="text-red-500 text-xs mb-2">{{m[0]}}</p>{% endif %}{% endwith %}<input name="u" placeholder="Nom" class="w-full mb-2 p-2 border rounded" required><input name="p" type="password" placeholder="Pass" class="w-full mb-4 p-2 border rounded" required><button class="w-full bg-blue-600 text-white p-2 rounded">{{t}}</button><a href="{{url_for('reg' if t=='Login' else 'log')}}" class="block text-center text-xs mt-4 text-blue-600 underline">{{ 'S inscrire' if t=='Login' else 'Se connecter' }}</a></form></div>""" + LAYOUT_END,
    'ch': LAYOUT_START + """<div class="h-screen flex"><div class="w-64 bg-white border-r flex flex-col"><div class="p-4 border-b flex justify-between items-center"><b>{{un}}</b><a href="{{url_for('out')}}" class="text-red-500 text-xs font-bold border border-red-500 rounded px-2 py-1">Sortie</a></div><div class="flex-1 overflow-y-auto p-2">{% for g in gs %}<div onclick="L('{{g.pin}}')" class="p-2 hover:bg-gray-100 cursor-pointer rounded mb-1 border-l-4 border-transparent" data-p="{{g.pin}}">Groupe {{g.pin}}</div>{% endfor %}</div><div class="p-4 border-t space-y-2"><button onclick="C()" class="w-full bg-blue-600 text-white p-2 rounded text-sm font-bold">Nouveau Groupe</button><button onclick="J()" class="w-full border border-gray-300 p-2 rounded text-sm font-bold">Rejoindre</button></div></div><div class="flex-1 flex flex-col"><div id="none" class="flex-1 flex items-center justify-center text-gray-400">Sélectionnez un groupe</div><div id="chat" class="hidden flex-1 flex flex-col"><div class="p-4 border-b bg-white flex justify-between items-center"><span id="t" class="font-bold"></span><span id="pin" class="font-mono text-gray-400 text-xs cursor-pointer" onclick="navigator.clipboard.writeText(this.innerText.split(': ')[1]);alert('PIN copié')"></span></div><div id="m" class="flex-1 overflow-y-auto p-4 space-y-2 bg-gray-50"></div><div class="p-4 bg-white border-t flex items-center gap-2"><input id="i" class="flex-1 p-2 border rounded-full outline-none px-4" placeholder="Votre message..."><button onclick="S()" class="bg-blue-600 text-white w-10 h-10 rounded-full flex items-center justify-center font-bold">></button></div></div></div></div><script>const s=io();let cur=null;function C(){fetch('/cg',{method:'POST'}).then(r=>r.json()).then(d=>d.s && location.reload())}function J(){let p=prompt('PIN:');if(p){let f=new FormData();f.append('p',p);fetch('/jg',{method:'POST',body:f}).then(r=>r.json()).then(d=>d.s?location.reload():alert(d.e))}}function L(p){if(cur)s.emit('leave',{p:cur});cur=p;s.emit('join',{p});document.getElementById('none').classList.add('hidden');document.getElementById('chat').classList.remove('hidden');document.getElementById('t').innerText='Groupe '+p;document.getElementById('pin').innerText='PIN: '+p;document.querySelectorAll('[data-p]').forEach(e=>e.style.borderColor=e.dataset.p===p?'#2563eb':'transparent');fetch('/ms/'+p).then(r=>r.json()).then(d=>{const c=document.getElementById('m');c.innerHTML='';d.forEach(m=>A(m));c.scrollTop=c.scrollHeight})}function S(){let v=document.getElementById('i').value.trim();if(v&&cur){s.emit('msg',{p:cur,c:v});document.getElementById('i').value=''}}function A(d){const c=document.getElementById('m');const div=document.createElement('div');div.className='flex '+(d.s?'justify-end':'justify-start');div.innerHTML=`<div class="max-w-xs p-2 rounded-lg ${d.s?'bg-blue-500 text-white rounded-br-none':'bg-white border rounded-bl-none shadow-sm'}"><div class="text-sm">${d.c}</div><div class="text-[8px] mt-1 ${d.s?'text-blue-100':'text-gray-400'}">${d.u}</div></div>`;c.appendChild(div);c.scrollTop=c.scrollHeight}s.on('n',d=>A(d));s.on('st',d=>A(d));document.getElementById('i')?.addEventListener('keypress',e=>e.key==='Enter'&&S());</script>""" + LAYOUT_END
}

# --- Routes ---
@app.route('/')
def home():
    return redirect(url_for('ch')) if 'uid' in session else redirect(url_for('log'))

@app.route('/reg', methods=['GET','POST'])
def reg():
    if request.method=='POST':
        u, p = request.form.get('u'), request.form.get('p')
        if u and p and not User.query.filter_by(username=u).first():
            user = User(username=u); user.set_password(p)
            db.session.add(user); db.session.commit()
            session.update({'uid':user.id, 'un':u}); return redirect(url_for('ch'))
        flash("Erreur d'inscription")
    return render_template_string(T['a'], t="Register")

@app.route('/log', methods=['GET','POST'])
def log():
    if request.method=='POST':
        u, p = request.form.get('u'), request.form.get('p')
        user = User.query.filter_by(username=u).first()
        if user and check_password_hash(user.pw, p):
            session.update({'uid':user.id, 'un':u}); return redirect(url_for('ch'))
        flash("Identifiants incorrects")
    return render_template_string(T['a'], t="Login")

@app.route('/out')
def out():
    session.clear(); return redirect(url_for('log'))

@app.route('/ch')
def ch():
    if 'uid' not in session: return redirect(url_for('log'))
    gs = [gu.group for gu in GroupUser.query.filter_by(uid=session['uid']).all()]
    return render_template_string(T['ch'], gs=gs, un=session['un'])

@app.route('/cg', methods=['POST'])
def cg():
    g = Groupe.create(session['uid'])
    return jsonify({'s':True})

@app.route('/jg', methods=['POST'])
def jg():
    p = request.form.get('p'); g = Group.query.filter_by(pin=p).first()
    if g:
        if not GroupUser.query.filter_by(uid=session['uid'], pin=p).first():
            db.session.add(GroupUser(uid=session['uid'], pin=p)); db.session.commit()
        return jsonify({'s':True})
    return jsonify({'s':False, 'e':'Introuvable'})

@app.route('/ms/<p>')
def ms(p):
    g = Group.query.filter_by(pin=p).first()
    if not g: return jsonify([])
    msgs = Msg.query.filter_by(pin=p).order_by(Msg.t.asc()).all()
    return jsonify([{'c':m.c, 'u':m.user.username, 's':m.uid==session['uid']} for m in msgs])

@socketio.on('join')
def on_j(d): join_room(d['p'])
@socketio.on('leave')
def on_l(d): leave_room(d['p'])
@socketio.on('msg')
def on_m(d):
    if 'uid' in session:
        m = Messaging.send(session['uid'], d['p'], d['c'])
        p = {'c':m.c, 'u':session['un'], 's':False}
        emit('n', p, room=d['p'], include_self=False)
        emit('st', {**p, 's':True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port)


