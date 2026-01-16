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
    
    # 1. Tabela de Usuários (Com campo de admin e aprovação)
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
    
    # Criar 3 computadores se não existirem
    c.execute('SELECT count(*) FROM computers')
    if c.fetchone()[0] == 0:
        for i in range(1, 4):
            c.execute('INSERT INTO computers (name) VALUES (?)', (f'PC-{i:02d}',))
    
    # CRIAR O USUÁRIO ADMIN PADRÃO (Se não existir)
    c.execute('SELECT count(*) FROM users WHERE matricula = "admin"')
    if c.fetchone()[0] == 0:
        admin_pass = hashlib.sha256(str.encode("admin7885")).hexdigest()
        c.execute('''
            INSERT INTO users (matricula, password, name, is_admin, approved) 
            VALUES (?, ?, ?, ?, ?)
        ''', ("admin", admin_pass, "Administrador", 1, 1))

    conn.commit()
    conn.close()

init_db()

# --- FUNÇÕES DE LÓGICA ---
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_login(matricula, password):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    pwd_hash = make_hash(password)
    # Busca usuário, se é admin e se está aprovado
    c.execute('SELECT id, name, is_admin, approved FROM users WHERE matricula = ? AND password = ?', (matricula, pwd_hash))
    data = c.fetchone()
    conn.close()
    return data

def create_user(matricula, password, name):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    try:
        # Cria usuário comum (is_admin=0, approved=0)
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

# --- FUNÇÕES EXCLUSIVAS DO ADMIN ---
def get_all_users():
    conn = sqlite3.connect('laboratorio.db')
    # Pega todos menos o admin
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

# --- INTERFACE ---

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_info'] = None # Guarda (id, nome, is_admin)

# TELA DE LOGIN / CADASTRO
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
                    st.warning("⚠️ Seu cadastro foi recebido, mas ainda não foi aprovado pelo Admin.")
            else:
                st.error("Dados incorretos.")

    with tab2:
        st.write("Preencha seus dados. O Admin precisará aprovar antes de você acessar.")
        new_mat = st.text_input("Sua Matrícula")
        new_name = st.text_input("Nome Completo")
        new_pass = st.text_input("Crie uma Senha", type="password")
        if st.button("Enviar Solicitação"):
            if create_user(new_mat, new_pass, new_name):
                st.success("Solicitação enviada! Aguarde a aprovação do administrador.")
            else:
                st.error("Essa matrícula já possui cadastro.")

# TELA LOGADA
else:
    user = st.session_state['user_info']
    
    # BARRA LATERAL
    with st.sidebar:
        st.title(f"Olá, {user['name']}")
        st.caption(f"ID: {user['id']} | {'ADMIN' if user['is_admin'] else 'ALUNO'}")
        
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- VISÃO DO ADMINISTRADOR ---
    if user['is_admin']:
        st.title("🛡️ Painel do Administrador")
        
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["Gerenciar Usuários", "Histórico de Reservas", "Laboratório"])
        
        with admin_tab1:
            st.subheader("Aprovações Pendentes e Usuários")
            all_users = get_all_users()
            
            if not all_users:
                st.info("Nenhum usuário cadastrado.")
            
            # Cabeçalho da tabela manual
            c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
            c1.markdown("**Matrícula**")
            c2.markdown("**Nome**")
            c3.markdown("**Status**")
            c4.markdown("**Ação**")
            
            for u_id, u_mat, u_name, u_approved in all_users:
                c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
                c1.write(u_mat)
                c2.write(u_name)
                
                if u_approved:
                    c3.success("Ativo")
                    if c4.button("Excluir", key=f"del_{u_id}"):
                        delete_user(u_id)
                        st.rerun()
                else:
                    c3.warning("Pendente")
                    if c4.button("✅ Aprovar", key=f"app_{u_id}"):
                        approve_user(u_id)
                        st.success(f"{u_name} aprovado!")
                        sleep(1)
                        st.rerun()
                st.markdown("---")

        with admin_tab2:
            st.subheader("Todas as Reservas")
            bookings = get_all_bookings_admin()
            if bookings:
                # Mostrando em formato de tabela simples
                data_clean = [{"Máquina": b[3], "Aluno": b[1], "Matrícula": b[2], "Início": b[4], "Fim": b[5]} for b in bookings]
                st.table(data_clean)
            else:
                st.info("Nenhuma reserva feita ainda.")
        
        with admin_tab3:
            st.subheader("Visão Geral das Máquinas")
            # Reutilizando a lógica visual, mas apenas para visualização
            st.write("Layout atual do laboratório (Apenas Visualização)")
            conn = sqlite3.connect('laboratorio.db')
            pcs = conn.cursor().execute('SELECT name FROM computers').fetchall()
            conn.close()
            st.write(f"Total de Máquinas: {len(pcs)}")
            st.write([p[0] for p in pcs])

    # --- VISÃO DO ALUNO (SISTEMA DE RESERVA) ---
    else:
        st.title("📅 Reservar Computador")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            data_reserva = st.date_input("Data", datetime.date.today(), min_value=datetime.date.today())
        with c2:
            hora_inicio = st.time_input("Início", datetime.time(8, 0))
        with c3:
            horas_uso = st.number_input("Duração (h)", 1, 4, 1)
        
        dt_inicio = datetime.datetime.combine(data_reserva, hora_inicio)
        dt_fim = dt_inicio + datetime.timedelta(hours=horas_uso)
        
        # Grid de Computadores (Igual ao anterior)
        conn = sqlite3.connect('laboratorio.db')
        computers = conn.cursor().execute('SELECT id, name FROM computers').fetchall()
        conn.close()
        
        cols = st.columns(3)
        for i, (comp_id, comp_name) in enumerate(computers):
            is_free = check_availability(comp_id, dt_inicio, dt_fim)
            with cols[i % 3]:
                color = "green" if is_free else "#ff4b4b"
                status = "LIVRE" if is_free else "OCUPADO"
                st.markdown(f'<div style="border:2px solid {color};padding:10px;border-radius:5px;text-align:center"><b>{comp_name}</b><br><span style="color:{color}">{status}</span></div>', unsafe_allow_html=True)
                
                if is_free:
                    if st.button("Reservar", key=f"btn_{comp_id}"):
                        add_booking(user['id'], comp_id, dt_inicio, dt_fim)
                        st.success("Reservado!")
                        sleep(1)
                        st.rerun()
                else:
                    st.button("Indisponível", key=f"btn_{comp_id}", disabled=True)

        st.divider()
        st.subheader("Minhas Reservas")
        conn = sqlite3.connect('laboratorio.db')
        my_books = conn.cursor().execute('SELECT c.name, b.start_time, b.end_time FROM bookings b JOIN computers c ON b.computer_id = c.id WHERE user_id = ?', (user['id'],)).fetchall()
        conn.close()
        for mb in my_books:
            st.text(f"{mb[0]} | {mb[1]} até {mb[2]}")

