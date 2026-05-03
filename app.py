import os
import time
import threading
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)
from dotenv import load_dotenv

# ── Tenta importar RPi.GPIO (só funciona no Raspberry Pi) ────────────────────
try:
    import RPi.GPIO as GPIO
    RASPBERRY = True
except ImportError:
    RASPBERRY = False
    print("[AVISO] RPi.GPIO não encontrado — rodando em modo simulado (sem hardware).")

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave-padrao-insegura")
app.config["DEBUG"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

ADMIN_USER   = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS   = os.getenv("ADMIN_PASS", "admin123")
IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "10"))
PINO_PIR     = int(os.getenv("PINO_PIR", "17"))
PINO_LED     = int(os.getenv("PINO_LED", "22"))

# ── Estado global (lido pela thread PIR e pelas rotas Flask) ──────────────────
estado = {"presente": False, "sessao_ativa": False, "ultima_presenca": None}
estado_lock = threading.Lock()

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("logs/totem.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  GPIO
# ═══════════════════════════════════════════════════════════════════════════════

def gpio_setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PINO_PIR, GPIO.IN)
    GPIO.setup(PINO_LED, GPIO.OUT)
    GPIO.output(PINO_LED, GPIO.LOW)
    logger.info("GPIO configurado  PIR=GPIO%d  LED=GPIO%d", PINO_PIR, PINO_LED)


def pir_loop():
    """Thread que lê o PIR a cada 300ms e gerencia a sessão automaticamente."""
    while True:
        leitura = bool(GPIO.input(PINO_PIR)) if RASPBERRY else False
        with estado_lock:
            agora = datetime.utcnow()
            if leitura:
                estado["presente"] = True
                estado["ultima_presenca"] = agora
                if not estado["sessao_ativa"]:
                    estado["sessao_ativa"] = True
                    logger.info("SESSÃO INICIADA  sensor=PIR GPIO%d", PINO_PIR)
            else:
                estado["presente"] = False
                if estado["sessao_ativa"] and estado["ultima_presenca"]:
                    ausente = (agora - estado["ultima_presenca"]).total_seconds()
                    if ausente >= IDLE_TIMEOUT:
                        estado["sessao_ativa"] = False
                        estado["ultima_presenca"] = None
                        logger.info("SESSÃO ENCERRADA  motivo=ausencia  tempo=%.0fs", ausente)
        time.sleep(0.3)


def piscar_led(duracao=2):
    def _run():
        if RASPBERRY:
            GPIO.output(PINO_LED, GPIO.HIGH)
            time.sleep(duracao)
            GPIO.output(PINO_LED, GPIO.LOW)
        else:
            logger.info("LED simulado  duracao=%ds (sem hardware)", duracao)
    threading.Thread(target=_run, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
#  Decorador
# ═══════════════════════════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            logger.warning("ACESSO NEGADO  rota=%-20s ip=%s", request.path, request.remote_addr)
            flash("Faça login para acessar esta área.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════════════
#  ROTAS PÚBLICAS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def totem():
    return render_template("totem.html", idle_timeout=IDLE_TIMEOUT)


@app.route("/api/estado")
def api_estado():
    """Polling do JS a cada 1s — retorna estado atual do sensor."""
    with estado_lock:
        presente     = estado["presente"]
        sessao_ativa = estado["sessao_ativa"]
        ultima       = estado["ultima_presenca"]
    segundos_restantes = IDLE_TIMEOUT
    if sessao_ativa and ultima:
        decorrido = (datetime.utcnow() - ultima).total_seconds()
        segundos_restantes = max(0, IDLE_TIMEOUT - int(decorrido))
    return jsonify({
        "presente": presente,
        "sessao_ativa": sessao_ativa,
        "segundos_restantes": segundos_restantes,
        "idle_timeout": IDLE_TIMEOUT,
    })


@app.route("/api/presenca", methods=["POST"])
def presenca():
    """Endpoint de simulação (quando não há hardware PIR conectado)."""
    data      = request.get_json(silent=True) or {}
    detectado = bool(data.get("presente", False))
    with estado_lock:
        estado["presente"] = detectado
        if detectado:
            estado["ultima_presenca"] = datetime.utcnow()
            if not estado["sessao_ativa"]:
                estado["sessao_ativa"] = True
                logger.info("SESSÃO INICIADA  sensor=simulado ip=%s", request.remote_addr)
        else:
            estado["sessao_ativa"] = False
            estado["ultima_presenca"] = None
            logger.info("SESSÃO ENCERRADA  sensor=simulado ip=%s", request.remote_addr)
    return jsonify({"status": "ok", "sessao_ativa": estado["sessao_ativa"]})


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTENTICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha   = request.form.get("senha",   "").strip()
        ip      = request.remote_addr
        erros = []
        if not usuario:          erros.append("O campo usuário é obrigatório.")
        if not senha:            erros.append("O campo senha é obrigatório.")
        if len(usuario) > 80:   erros.append("Usuário inválido.")
        if len(senha)   > 128:  erros.append("Senha inválida.")
        if erros:
            for e in erros: flash(e, "error")
            logger.warning("TENTATIVA LOGIN  resultado=entrada_invalida ip=%s", ip)
            return render_template("login.html")
        if usuario == ADMIN_USER and senha == ADMIN_PASS:
            session["admin_logged_in"] = True
            session.permanent = True
            logger.info("LOGIN OK  usuario=%s ip=%s", usuario, ip)
            return redirect(url_for("admin"))
        else:
            logger.warning("LOGIN FALHOU  usuario=%s ip=%s", usuario, ip)
            flash("Usuário ou senha incorretos.", "error")
            return render_template("login.html")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logger.info("LOGOUT  usuario=%s ip=%s", ADMIN_USER, request.remote_addr)
    session.clear()
    return redirect(url_for("totem"))


# ═══════════════════════════════════════════════════════════════════════════════
#  ÁREA ADMINISTRATIVA
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html", raspberry=RASPBERRY, pino_pir=PINO_PIR, pino_led=PINO_LED)


@app.route("/admin/led", methods=["POST"])
@login_required
def acionar_led():
    cor = request.form.get("cor", "led").strip()[:20]
    piscar_led(duracao=2)
    logger.info("LED ACIONADO  cor=%s pino=GPIO%d usuario=%s ip=%s",
                cor, PINO_LED, ADMIN_USER, request.remote_addr)
    flash(f"✅ LED acionado! (GPIO {PINO_LED} ligado por 2s)", "success")
    return redirect(url_for("admin"))


@app.route("/admin/logs")
@login_required
def ver_logs():
    logger.info("LOGS ACESSADOS  ip=%s", request.remote_addr)
    try:
        with open("logs/totem.log", "r") as f:
            linhas = f.readlines()[-50:]
    except FileNotFoundError:
        linhas = ["(nenhum log ainda)"]
    return render_template("logs.html", linhas=linhas)


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if RASPBERRY:
        gpio_setup()
        threading.Thread(target=pir_loop, daemon=True).start()
        logger.info("Thread PIR iniciada  GPIO%d", PINO_PIR)
    else:
        logger.info("Modo simulado — use os botões na tela do totem")
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        if RASPBERRY:
            GPIO.cleanup()
            logger.info("GPIO liberado")
