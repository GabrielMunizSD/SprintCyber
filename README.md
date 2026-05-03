# SprintCyber

# Totem Concierge — Sprint Cybersecurity

> Aplicação Flask com controles de segurança aplicados sobre um sistema embarcado (Raspberry Pi 3) com sensor PIR e LEDs.

---

## Sobre o Projeto

O **Totem Concierge** é um sistema de atendimento automatizado desenvolvido para o **Entregável 3 — Proteção da Aplicação Web**. A aplicação roda em um Raspberry Pi 3 e implementa:

- Tela pública de exibição do totem
- Área administrativa protegida por login
- Leitura de sensor de proximidade PIR (GPIO 17)
- Controle de LEDs coloridos (GPIOs 22, 23, 24, 25)
- Registro em log de todos os eventos de segurança
- Controle automático de sessão por tempo de ausência

---

## Estrutura do Projeto

```
totem-flask/
├── app.py                  # Aplicação principal Flask
├── requirements.txt        # Dependências Python
├── .env.example            # Modelo de configuração (versionado)
├── .env                    # Credenciais reais (NÃO versionado)
├── .gitignore
├── logs/
│   └── totem.log           # Gerado automaticamente
└── templates/
    ├── base.html           # Layout base
    ├── totem.html          # Tela pública do totem
    ├── login.html          # Página de login
    ├── admin.html          # Painel administrativo
    └── logs.html           # Visualizador de logs
```

---

## Pré-requisitos

- Python 3.9 ou superior
- pip
- Raspberry Pi 3 (para uso com hardware) **ou** qualquer computador (modo simulado)

---

## Como executar

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/totem-flask.git
cd totem-flask
```

### 2. Instale as dependências

**No computador (Windows/Mac/Linux) — modo simulado:**
```bash
pip install flask python-dotenv
```

**No Raspberry Pi — com hardware:**
```bash
pip install -r requirements.txt
```

> O `RPi.GPIO` só instala corretamente no Raspberry Pi. No computador, o sistema detecta automaticamente que não há hardware e entra em **modo simulado**, exibindo botões para testar o sensor manualmente.

---

### 3. Configure as credenciais

**Windows:**
```cmd
copy .env.example .env
```

**Linux / macOS / Raspberry Pi:**
```bash
cp .env.example .env
```

Abra o arquivo `.env` e edite com suas configurações:

```env
# Gere uma chave segura com:
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=sua-chave-secreta-aqui

# Credenciais do administrador
ADMIN_USER=admin
ADMIN_PASS=SuaSenhaForte

# Tempo sem presença para encerrar sessão (segundos)
IDLE_TIMEOUT=10

# Pinos GPIO (Raspberry Pi)
PINO_PIR=17
PINO_LED=22
```

> O arquivo `.env` **nunca** deve ser enviado ao repositório. Ele já está listado no `.gitignore`.

---

### 4. Execute a aplicação

```bash
python app.py
```

Você verá no terminal:

```
# Modo simulado (sem Raspberry Pi):
[AVISO] RPi.GPIO não encontrado — rodando em modo simulado.
Modo simulado — use os botões na tela do totem
* Running on http://0.0.0.0:5000

# Modo real (no Raspberry Pi):
GPIO configurado  PIR=GPIO17  LED=GPIO22
Thread PIR iniciada  GPIO17
* Running on http://0.0.0.0:5000
```

---

### 5. Acesse no navegador

```
http://localhost:5000
```

Para acessar de outro dispositivo na mesma rede (ex: celular), descubra o IP:

```bash
# Linux / Raspberry Pi
hostname -I

# Windows
ipconfig
```

E acesse `http://SEU-IP:5000`.

---

## Rotas da Aplicação

| Rota | Nível | Descrição |
|---|---|---|
| `/` | Público | Tela do totem com sensor de proximidade |
| `/login` | Público | Formulário de autenticação |
| `/logout` | Admin | Encerra a sessão administrativa |
| `/admin` | Admin | Painel de controle (exige login) |
| `/admin/led` | Admin | Aciona o LED físico no GPIO |
| `/admin/logs` | Admin | Visualiza os registros de eventos |
| `/api/estado` | Público | Retorna estado atual do sensor (polling) |
| `/api/presenca` | Público | Simulação de presença (modo sem hardware) |

**Credenciais padrão do admin:** `admin` / `Totem@2025`

---

## Controles de Segurança

### Controle de acesso
Rotas administrativas protegidas pelo decorador `@login_required`. Qualquer acesso sem sessão ativa é redirecionado para o login e registrado no log.

### Proteção de credenciais
Nenhuma senha está escrita no código. Todas as configurações sensíveis ficam no arquivo `.env`, que está no `.gitignore` e nunca é enviado ao repositório. O arquivo `.env.example` serve de modelo sem dados reais.

### Validação de entradas
O formulário de login valida campos obrigatórios, limite de tamanho (usuário: 80 chars, senha: 128 chars) e sanitização antes de qualquer verificação.

### Debug desativado
```python
app.config["DEBUG"] = False
```

### Registro em log
Todos os eventos são gravados em `logs/totem.log`:

```
2026-05-10 14:22:01 [INFO]    SESSÃO INICIADA  sensor=PIR GPIO17
2026-05-10 14:22:15 [INFO]    LOGIN OK  usuario=admin  ip=192.168.1.10
2026-05-10 14:22:31 [INFO]    LED ACIONADO  cor=verde  pino=GPIO22
2026-05-10 14:23:05 [WARNING] ACESSO NEGADO  rota=/admin  ip=192.168.1.55
2026-05-10 14:23:09 [WARNING] LOGIN FALHOU  usuario=admin  ip=192.168.1.55
2026-05-10 14:23:47 [INFO]    SESSÃO ENCERRADA  motivo=ausencia  tempo=10s
```

---

## Esquema de ligação — Raspberry Pi 3

### Sensor PIR (HC-SR501)

| Pino do sensor | Pino físico do Raspberry Pi |
|---|---|
| VCC | Pino 2 (5V) |
| OUT | Pino 11 (GPIO 17) |
| GND | Pino 6 (GND) |

### LEDs

| Cor | GPIO | Pino físico | Resistor |
|---|---|---|---|
| Verde | GPIO 22 | Pino 15 | 330Ω |
| Amarelo | GPIO 23 | Pino 16 | 330Ω |
| Vermelho | GPIO 24 | Pino 18 | 330Ω |
| Azul | GPIO 25 | Pino 22 | 330Ω |

> O catodo (−) de cada LED vai ao GND (pino 9 ou qualquer GND disponível).

---

## Controle de Sessão

1. Sensor PIR detecta presença → sessão do visitante iniciada automaticamente
2. Timer regressivo exibido na tela (padrão: 10 segundos)
3. Ausência por `IDLE_TIMEOUT` segundos → sessão encerrada, totem volta ao modo inicial
4. Configurável via variável `IDLE_TIMEOUT` no `.env`

---

## Dependências

| Pacote | Versão | Uso |
|---|---|---|
| flask | 3.1.1 | Servidor web |
| python-dotenv | 1.0.1 | Leitura do `.env` |
| RPi.GPIO | 0.7.1 | Controle do GPIO (somente no Raspberry Pi) |

---

## Arquivos importantes

| Arquivo | Versionado? | Descrição |
|---|---|---|
| `.env.example` | Sim | Modelo de configuração sem dados reais |
| `.env` | Não | Credenciais reais — apenas local |
| `logs/totem.log` | Não | Gerado em tempo de execução |

---

*Projeto desenvolvido para a disciplina de Cyber Security — FIAP · 2026*
