import streamlit as st
import sqlite3
import datetime
import hashlib
from time import sleep

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Lab Manager Pro", layout="wide")

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    
    # 1. Tabela de Usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            is_admin BOOLEAN DEFAULT 0,
            approved BOOLEAN DEFAULT 0
        )
    ''')
    
    # 2. Tabela de Computadores
    c.execute('''
        CREATE TABLE IF NOT EXISTS computers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    
    # 3. Tabela de Reservas
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            computer_id INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(computer_id) REFERENCES computers(id)
        )
    ''')
    
    # Criar APENAS 3 computadores se não existirem
    c.execute('SELECT count(*) FROM computers')
    if c.fetchone()[0] == 0:
        for i in range(1, 4): # Cria PC-01, PC-02, PC-03
            c.execute('INSERT INTO computers (name) VALUES (?)', (f'PC-{i:02d}',))
    
    # CRIAR O USUÁRIO ADMIN PADRÃO (Se não existir)
    c.execute('SELECT count(*) FROM users WHERE matricula = "admin"')
    if c.fetchone()[0] == 0:
        admin_pass = hashlib.sha256(str.encode("admin123")).hexdigest()
        c.execute('''
            INSERT INTO users (matricula, password, name, is_admin, approved) 
            VALUES (?, ?, ?, ?, ?)
        ''', ("admin", admin_pass, "Administrador", 1, 1))

    conn.commit()
    conn.close()

# Inicializa o banco ao abrir
init_db()

# --- FUNÇÕES DE AJUDA (BACKEND) ---
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_login(matricula, password):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    pwd_hash = make_hash(password)
    c.execute('SELECT id, name, is_admin, approved FROM users WHERE matricula = ? AND password = ?', (matricula, pwd_hash))
    data = c.fetchone()
    conn.close()
    return data

def create_user(matricula, password, name):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    try:
        # Cria usuário com approved = 0 (Pendente)
        c.execute('INSERT INTO users (matricula, password, name, is_admin, approved) VALUES (?, ?, ?, 0, 0)', 
                  (matricula, make_hash(password), name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def check_availability(computer_id, start_dt, end_dt):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    c.execute("SELECT count(*) FROM bookings WHERE computer_id = ? AND (? < end_time AND ? > start_time)", (computer_id, start_dt, end_dt))
    count = c.fetchone()[0]
    conn.close()
    return count == 0

def add_booking(user_id, computer_id, start_dt, end_dt):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    c.execute('INSERT INTO bookings (user_id, computer_id, start_time, end_time) VALUES (?, ?, ?, ?)', (user_id, computer_id, start_dt, end_dt))
    conn.commit()
    conn.close()

# --- FUNÇÕES DE ADMINISTRAÇÃO ---
def get_all_users():
    conn = sqlite3.connect('laboratorio.db')
    users = conn.cursor().execute('SELECT id, matricula, name, approved FROM users WHERE matricula != "admin"').fetchall()
    conn.close()
    return users

def approve_user(user_id):
    conn = sqlite3.connect('laboratorio.db')
    conn.cursor().execute('UPDATE users SET approved = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = sqlite3.connect('laboratorio.db')
    conn.cursor().execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_all_bookings_admin():
    conn = sqlite3.connect('laboratorio.db')
    query = '''
        SELECT b.id, u.name, u.matricula, c.name, b.start_time, b.end_time 
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN computers c ON b.computer_id = c.id
        ORDER BY b.start_time DESC
    '''
    data = conn.cursor().execute(query).fetchall()
    conn.close()
    return data

# --- COMPONENTES EM TEMPO REAL (FRAGMENTS) ---

@st.fragment(run_every=5) # Atualiza a cada 5 segundos automaticamente
def render_admin_users():
    st.subheader("👥 Gestão de Usuários (Tempo Real)")
    
    users = get_all_users()
    
    if not users:
        st.info("Nenhum usuário cadastrado.")
        return

    # Cabeçalho
    c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
    c1.markdown("**Matrícula**")
    c2.markdown("**Nome**")
    c3.markdown("**Status**")
    c4.markdown("**Ação**")
    st.divider()
    
    for u_id, u_mat, u_name, u_approved in users:
        c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
        c1.write(u_mat)
        c2.write(u_name)
        
        if u_approved:
            c3.success("Ativo")
            if c4.button("🗑️ Excluir", key=f"del_{u_id}"):
                delete_user(u_id)
                st.rerun()
        else:
            c3.error("🔴 PENDENTE")
            if c4.button("✅ Aprovar", key=f"app_{u_id}"):
                approve_user(u_id)
                st.toast(f"{u_name} aprovado com sucesso!")
                st.rerun()
        st.markdown("---")

@st.fragment(run_every=10) # Atualiza reservas a cada 10 segundos
def render_admin_bookings():
    st.subheader("📅 Todas as Reservas (Tempo Real)")
    bookings = get_all_bookings_admin()
    
    if bookings:
        # Tabela formatada
        table_data = []
        for b in bookings:
            start = datetime.datetime.strptime(b[4], '%Y-%m-%d %H:%M:%S').strftime('%d/%m %H:%M')
            end = datetime.datetime.strptime(b[5], '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
            table_data.append({
                "Máquina": b[3],
                "Aluno": f"{b[1]} ({b[2]})",
                "Horário": f"{start} até {end}"
            })
        st.table(table_data)
    else:
        st.info("Nenhuma reserva encontrada.")


# --- INTERFACE PRINCIPAL ---

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_info'] = None

# 1. TELA DE LOGIN / CADASTRO
if not st.session_state['logged_in']:
    st.title("🔒 Laboratório - Acesso Restrito")
    
    tab1, tab2 = st.tabs(["Fazer Login", "Solicitar Cadastro"])
    
    with tab1:
        matricula = st.text_input("Matrícula")
        password = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            user = check_login(matricula, password)
            if user:
                user_id, user_name, is_admin, is_approved = user
                
                if is_approved:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = {'id': user_id, 'name': user_name, 'is_admin': is_admin}
                    st.rerun()
                else:
                    st.warning("⏳ Sua conta ainda está pendente de aprovação pelo Admin.")
            else:
                st.error("Matrícula ou senha incorretos.")

    with tab2:
        st.write("Crie sua conta. O Admin precisará aprovar antes de você acessar.")
        new_mat = st.text_input("Sua Matrícula")
        new_name = st.text_input("Nome Completo")
        new_pass = st.text_input("Crie uma Senha", type="password")
        if st.button("Enviar Solicitação"):
            if create_user(new_mat, new_pass, new_name):
                st.success("✅ Solicitação enviada! Aguarde a aprovação.")
            else:
                st.error("Erro: Matrícula já cadastrada.")

# 2. TELA DO SISTEMA (LOGADO)
else:
    user = st.session_state['user_info']
    
    # Barra Lateral
    with st.sidebar:
        st.title(f"Olá, {user['name']}")
        role = "ADMINISTRADOR" if user['is_admin'] else "ESTUDANTE"
        st.caption(f"Perfil: {role}")
        
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()

    # === VISÃO DO ADMIN ===
    if user['is_admin']:
        st.title("🛡️ Painel de Controle")
        admin_tab1, admin_tab2 = st.tabs(["Gerenciar Usuários", "Reservas"])
        
        with admin_tab1:
            # Chama o fragmento que se atualiza sozinho
            render_admin_users()
            
        with admin_tab2:
            # Chama o fragmento de reservas
            render_admin_bookings()

    # === VISÃO DO ALUNO ===
    else:
        st.title("📅 Reservar Computador")
        
        # Inputs de Reserva
        c1, c2, c3 = st.columns(3)
        with c1:
            data_reserva = st.date_input("Data", datetime.date.today(), min_value=datetime.date.today())
        with c2:
            hora_inicio = st.time_input("Início", datetime.time(8, 0))
        with c3:
            horas_uso = st.number_input("Duração (h)", 1, 4, 1)
        
        dt_inicio = datetime.datetime.combine(data_reserva, hora_inicio)
        dt_fim = dt_inicio + datetime.timedelta(hours=horas_uso)
        
        st.markdown("---")
        st.subheader("Disponibilidade")

        # Grid de Computadores (3 Colunas)
        conn = sqlite3.connect('laboratorio.db')
        computers = conn.cursor().execute('SELECT id, name FROM computers').fetchall()
        conn.close()
        
        cols = st.columns(3) # Apenas 3 colunas para as 3 máquinas
        
        for i, (comp_id, comp_name) in enumerate(computers):
            is_free = check_availability(comp_id, dt_inicio, dt_fim)
            
            with cols[i]:
                # Estilo Visual do Cartão
                color = "#28a745" if is_free else "#dc3545" # Verde ou Vermelho
                status_icon = "✅ LIVRE" if is_free else "⛔ OCUPADO"
                
                st.markdown(f"""
                <div style="
                    border: 2px solid {color};
                    border-radius: 8px;
                    padding: 15px;
                    text-align: center;
                    margin-bottom: 10px;
                    background-color: rgba(255,255,255,0.05);">
                    <h3 style="margin:0">{comp_name}</h3>
                    <p style="color:{color}; font-weight:bold; margin:0">{status_icon}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if is_free:
                    if st.button(f"Reservar {comp_name}", key=f"btn_{comp_id}", use_container_width=True):
                        add_booking(user['id'], comp_id, dt_inicio, dt_fim)
                        st.success("Reserva confirmada!")
                        sleep(1)
                        st.rerun()
                else:
                    st.button("Indisponível", key=f"btn_{comp_id}", disabled=True, use_container_width=True)

        # Minhas Reservas
        st.markdown("---")
        st.subheader("Minhas Reservas Ativas")
        conn = sqlite3.connect('laboratorio.db')
        my_books = conn.cursor().execute('''
            SELECT c.name, b.start_time, b.end_time 
            FROM bookings b 
            JOIN computers c ON b.computer_id = c.id 
            WHERE user_id = ? AND b.start_time >= ?
            ORDER BY b.start_time
        ''', (user['id'], datetime.datetime.now())).fetchall()
        conn.close()
        
        if my_books:
            for mb in my_books:
                s = datetime.datetime.strptime(mb[1], '%Y-%m-%d %H:%M:%S').strftime('%d/%m às %H:%M')
                e = datetime.datetime.strptime(mb[2], '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
                st.info(f"🖥️ **{mb[0]}** | 🗓️ {s} até {e}")
        else:
            st.write("Você não tem reservas futuras.")
