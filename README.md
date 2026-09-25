-- Active: 1790308813037@@127.0.0.1@5432
## Backend — Execução local

O backend utiliza **Python + FastAPI + PostgreSQL**.

### 1. Entre na pasta do backend

```bash
cd backend
```

### 2. Crie o ambiente virtual

**Linux:**

```bash
python3 -m venv .venv
```

**Windows:**

```powershell
py -m venv .venv
```

### 3. Ative o ambiente virtual

**Linux:**

```bash
source .venv/bin/activate
```

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

Caso o PowerShell bloqueie a execução:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 4. Instale as dependências

```bash
pip install -r requirements.txt
```

### 5. Crie o arquivo `.env`

**Linux:**

```bash
cp .env.example .env
```

**Windows:**

```powershell
Copy-Item .env.example .env
```

Configure a conexão com o PostgreSQL:

```env
DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@HOST:5432/db_goodwe?sslmode=require
```

> Para conexão local com o PostgreSQL do Render, utilize a **External Database URL**.

### 6. Execute o backend

```bash
uvicorn main:app --reload
```
<br>

## Banco de Dados - Execução Local

### 1. Trocar para a branch

```bash
git checkout feat/db-compose
```

### 2. Abrir o Docker Desktop

Abra o **Docker Desktop** e espere a engine iniciar.

### 3. Configurar o `.env`

Entre no backend:

```bash
cd backend
```

Copie o `.env.example`:

```bash
cp .env.example .env
```

Preencha o `.env` com os valores do `.env.example`.

### 4. Subir o banco

Ainda dentro de `backend`:

```bash
docker compose up -d
```

### 5. Conectar no banco

No VS Code, abra a extensão **Database Client** e crie uma conexão usando **as mesmas credenciais do `.env`**.

<p italic>Senha: postgres</p>

### 6. Rodar o script

Copie o script do **Teams** e rode pelo Database Client.

### 7. Rodar o backend

Dentro de `backend`:

```bash
uvicorn main:app --reload
```

<br>

## API e ChatBot

### 1. Acesse a API

API:

```text
http://127.0.0.1:8000
```

### 2. Interface de chat IA com Gradio

A interface da IA agora roda junto com o FastAPI principal da aplicação, na mesma porta do projeto.

Configure a chave da API do Gemini no ambiente:

```powershell
$env:GEMINI_API_KEY="sua_chave_aqui"
```

Inicie o backend principal:

```bash
cd backend
uvicorn main:app --reload
```

A interface ficará disponível em:

```text
http://localhost:8000/ia
```

### 3. RAG com documentos e busca web opcional

Coloque documentos autorizados (`.pdf`, `.txt`, `.md`, `.csv` ou `.json`) em:

```text
backend/data/documents/
```

O chat recupera localmente apenas trechos relacionados à pergunta. Essa pasta é ignorada pelo Git e não deve conter credenciais, dados pessoais ou documentos que o usuário não possa enviar para a API Gemini.

Para incluir contexto público de estações cadastradas no PostgreSQL, habilite explicitamente:

```env
RAG_ENABLE_DATABASE=true
```

Essa integração executa somente uma consulta fixa de leitura sobre `estacoes`, usando `nome`, `endereco` e `preco_base_kwh` de estações ativas, limitada a 20 registros. O usuário não pode fornecer SQL, e nenhuma tabela de usuários, pagamentos, veículos ou autenticação é consultada. Se o banco estiver indisponível, o chat continua com documentos locais e contexto padrão.

Por padrão, a busca web fica desligada. Para ativá-la no `.env`:

```env
RAG_ENABLE_WEB_SEARCH=true
```

Sem configuração adicional, o sistema usa DuckDuckGo como alternativa gratuita. Para usar Google Programmable Search, configure também:

```env
GOOGLE_SEARCH_API_KEY=sua_chave
GOOGLE_SEARCH_CX=seu_search_engine_id
```

As perguntas enviadas à busca web podem sair da aplicação. Por isso, mantenha a busca desligada para consultas privadas e nunca envie segredos, tokens, senhas ou dados pessoais ao modelo.

### 4. Controle de demanda e tarifação

O endpoint `POST /api/recargas/controle-demanda` calcula a demanda agregada das recargas ativas de uma estação, compara com o limite seguro informado, distribui a potência disponível e calcula o preço dinâmico por kWh considerando pico, utilização e fator externo.

Por segurança, o endpoint começa em modo simulação. Para persistir a potência alocada nas recargas ativas, envie explicitamente:

```json
{
	"estacao_id": 1,
	"station_capacity_kw": 60,
	"external_price_multiplier": 1.0,
	"minimum_power_kw": 1.4,
	"aplicar_ajuste": true
}
```

O limite `station_capacity_kw` deve vir da capacidade elétrica homologada da instalação, e não ser inventado pela IA. A IA pode futuramente explicar ou prever a demanda, mas as regras de proteção e tarifação permanecem determinísticas no backend.

### Observações

O arquivo `.env` contém credenciais e configurações locais e **não deve ser enviado ao Git**.

O `.env.example` deve ser versionado apenas com exemplos das variáveis necessárias.

<br>

## OCPP e Conexão com Carregadores

O sistema implementa comunicação real entre a API e os carregadores elétricos utilizando OCPP 1.6J via WebSocket. Ao iniciar uma recarga pelo site, a API envia o comando ao carregador, acompanha o consumo em tempo real e, ao final, calcula auto maticamente o valor com base na energia efetivamente entregue.
 
A integração também possui um simulador de carregador, permitindo testar todo o fluxo sem hardware físico. Os dados da recarga — status, energia consumida e valor final — são registrados no banco de dados.

> [!NOTE]
> Atualmente, a integração foi validada com o simulador; o hardware físico ainda está em desenvolvimento.

<br>

<p align="center">
	<img width="650" src="https://github.com/user-attachments/assets/1aa209d3-7b31-4a84-bb21-765dfd4bc0bf" alt="fluxograma"/>
</p>
