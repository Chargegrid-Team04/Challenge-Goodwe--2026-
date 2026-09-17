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

### 7. Acesse a API

API:

```text
http://127.0.0.1:8000
```

### Observações

O arquivo `.env` contém credenciais e configurações locais e **não deve ser enviado ao Git**.

O `.env.example` deve ser versionado apenas com exemplos das variáveis necessárias.
