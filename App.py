import streamlit as st
import sqlite3
import datetime
import hashlib
from time import sleep

# --- CONFIGURAÇÃO INICIAL DA PÁGINA ---
st.set_page_config(page_title="Lab Manager SaaS", layout="wide")

# --- BANCO DE DADOS (SQLite) ---
def init_db():
    """Cria as tabelas e computadores se não existirem."""
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    
    # 1. Tabela de Usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT
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
    
    # Criar 10 computadores automaticamente se a tabela estiver vazia
    c.execute('SELECT count(*) FROM computers')
    if c.fetchone()[0] == 0:
        for i in range(1, 4):  # <--- MUDANÇA AQUI (de 11 para 4)
            c.execute('INSERT INTO computers (name) VALUES (?)', (f'PC-{i:02d}',))
            
    conn.commit()
    conn.close()

# Inicializa o banco ao abrir o app
init_db()

# --- FUNÇÕES DE SEGURANÇA E LÓGICA ---
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_login(matricula, password):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    pwd_hash = make_hash(password)
    c.execute('SELECT id, name FROM users WHERE matricula = ? AND password = ?', (matricula, pwd_hash))
    data = c.fetchone()
    conn.close()
    return data

def create_user(matricula, password, name):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (matricula, password, name) VALUES (?, ?, ?)', 
                  (matricula, make_hash(password), name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def check_availability(computer_id, start_dt, end_dt):
    """
    A LÓGICA DE OURO: Verifica se existe sobreposição de horários.
    Retorna True se estiver livre, False se estiver ocupado.
    """
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    
    query = """
        SELECT count(*) FROM bookings 
        WHERE computer_id = ? 
        AND ( ? < end_time AND ? > start_time )
    """
    c.execute(query, (computer_id, start_dt, end_dt))
    count = c.fetchone()[0]
    conn.close()
    return count == 0

def add_booking(user_id, computer_id, start_dt, end_dt):
    conn = sqlite3.connect('laboratorio.db')
    c = conn.cursor()
    c.execute('INSERT INTO bookings (user_id, computer_id, start_time, end_time) VALUES (?, ?, ?, ?)',
              (user_id, computer_id, start_dt, end_dt))
    conn.commit()
    conn.close()

# --- INTERFACE DO USUÁRIO (FRONTEND) ---

# Gerenciamento de Sessão (Login)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_name'] = ''
    st.session_state['user_id'] = None

# TELA 1: LOGIN E CADASTRO
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1,2,1])
    
    with col2:
        st.title("🔐 Acesso ao Laboratório")
        tab1, tab2 = st.tabs(["Login", "Criar Conta"])
        
        with tab1:
            matricula = st.text_input("Matrícula")
            password = st.text_input("Senha", type="password")
            if st.button("Entrar"):
                user = check_login(matricula, password)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = user[0]
                    st.session_state['user_name'] = user[1]
                    st.rerun()
                else:
                    st.error("Matrícula ou senha incorretos.")
        
        with tab2:
            new_matricula = st.text_input("Nova Matrícula")
            new_name = st.text_input("Seu Nome Completo")
            new_pass = st.text_input("Criar Senha", type="password")
            if st.button("Cadastrar"):
                if create_user(new_matricula, new_pass, new_name):
                    st.success("Conta criada! Vá para a aba de Login.")
                else:
                    st.error("Erro: Matrícula já cadastrada.")

# TELA 2: SISTEMA PRINCIPAL (DASHBOARD)
else:
    # Barra Lateral
    with st.sidebar:
        st.write(f"Olá, **{st.session_state['user_name']}**")
        st.write(f"Matrícula: {st.session_state['user_id']}")
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()
    
    st.title("🖥️ Gerenciamento de Laboratório")
    
    # Área de Nova Reserva
    st.subheader("Nova Reserva")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        data_reserva = st.date_input("Data", datetime.date.today(), min_value=datetime.date.today())
    with c2:
        hora_inicio = st.time_input("Horário de Início", datetime.time(8, 0))
    with c3:
        horas_uso = st.number_input("Duração (Horas)", min_value=1, max_value=4, value=1)
    
    # Cálculo automático do fim
    dt_inicio = datetime.datetime.combine(data_reserva, hora_inicio)
    dt_fim = dt_inicio + datetime.timedelta(hours=horas_uso)
    
    with c4:
        st.write("Horário Final:")
        st.info(f"{dt_fim.strftime('%H:%M')}")

    st.markdown("---")
    
    # MAPA VISUAL DOS COMPUTADORES
    st.subheader("Escolha um Computador")
    
    # Buscar computadores no banco
    conn = sqlite3.connect('laboratorio.db')
    computers = conn.cursor().execute('SELECT id, name FROM computers').fetchall()
    conn.close()
    
    # Criar um grid visual
    cols = st.columns(3) # <--- MUDANÇA AQUI (de 5 para 3 colunas)
    
    for i, (comp_id, comp_name) in enumerate(computers):
        # Para cada computador, verifica se está livre NAQUELA data/hora selecionada acima
        is_free = check_availability(comp_id, dt_inicio, dt_fim)
        
        with cols[i % 3]:
            # Desenha o "Cartão" do computador
            status_color = "green" if is_free else "red"
            status_text = "LIVRE" if is_free else "OCUPADO"
            
            st.markdown(f"""
            <div style="
                border: 2px solid {status_color};
                border-radius: 10px;
                padding: 10px;
                text-align: center;
                margin-bottom: 10px;">
                <strong>{comp_name}</strong><br>
                <span style="color: {status_color};">{status_text}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Botão de reservar (só aparece se estiver livre)
            if is_free:
                if st.button(f"Reservar {comp_name}", key=f"btn_{comp_id}"):
                    add_booking(st.session_state['user_id'], comp_id, dt_inicio, dt_fim)
                    st.success(f"Reserva feita para {comp_name}!")
                    sleep(1)
                    st.rerun() # Recarrega a página para atualizar o status
            else:
                st.button(f"Indisponível", disabled=True, key=f"btn_{comp_id}")

    # EXIBIR MINHAS RESERVAS
    st.markdown("---")
    st.subheader("📅 Minhas Reservas Futuras")
    
    conn = sqlite3.connect('laboratorio.db')
    minhas_reservas = conn.cursor().execute('''
        SELECT c.name, b.start_time, b.end_time 
        FROM bookings b
        JOIN computers c ON b.computer_id = c.id
        WHERE b.user_id = ? AND b.start_time >= ?
        ORDER BY b.start_time
    ''', (st.session_state['user_id'], datetime.datetime.now())).fetchall()
    conn.close()
    
    if minhas_reservas:
        for res in minhas_reservas:
            start = datetime.datetime.strptime(res[1], '%Y-%m-%d %H:%M:%S')
            end = datetime.datetime.strptime(res[2], '%Y-%m-%d %H:%M:%S')
            st.info(f"🖥️ **{res[0]}** | 🗓️ {start.strftime('%d/%m/%Y')} | ⏰ {start.strftime('%H:%M')} às {end.strftime('%H:%M')}")
    else:
        st.write("Você não tem reservas futuras.")