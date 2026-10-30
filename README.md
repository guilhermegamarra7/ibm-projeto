# BB Camaleão — Assistente Multiagente do Banco do Brasil

Protótipo de assistente bancário com voz, visão multimodal e proteção contra golpes, construído para o desafio IBM.

---

## Estrutura do projeto

```
ibm-projeto/
├── backend_main.py      # API FastAPI (Python)
└── frontend/            # Interface React + Vite + Tailwind
    ├── src/
    │   ├── App.jsx
    │   ├── MascoteAvatar.jsx
    │   └── assets/sprites/
    └── package.json
```

---

## Pré-requisitos

| Ferramenta | Versão mínima |
|------------|---------------|
| Python     | 3.10+         |
| Node.js    | 18+           |
| npm        | 9+            |

---

## 1 — Backend (FastAPI)

### Instalar dependências

```bash
pip install fastapi uvicorn pydantic
```

### Rodar o servidor

```bash
uvicorn backend_main:app --reload --port 8000
```

A API ficará disponível em **http://localhost:8000**.

> Documentação interativa automática: http://localhost:8000/docs

### Endpoint principal

| Método | Rota                  | Descrição                              |
|--------|-----------------------|----------------------------------------|
| POST   | `/api/agent/interact` | Recebe input do usuário, retorna JSON de controle da UI |

**Exemplo de body:**
```json
{
  "user_input": "Quero fazer um Pix de 50 reais pro Pedro",
  "current_screen": "HOME",
  "image_context": null
}
```

---

## 2 — Frontend (React + Vite)

### Instalar dependências

```bash
cd frontend
npm install
```

### Rodar em desenvolvimento

```bash
npm run dev
```

A interface ficará disponível em **http://localhost:5173**.

### Build para produção

```bash
npm run build
```

Os arquivos gerados ficam em `frontend/dist/`.

---

## Rodando tudo junto

Abra dois terminais na raiz do projeto:

**Terminal 1 — Backend:**
```bash
uvicorn backend_main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Acesse **http://localhost:5173** no navegador.

---

## Agentes disponíveis

| Agente                  | Gatilho de exemplo                        | O que faz                                      |
|-------------------------|-------------------------------------------|------------------------------------------------|
| `VISAO_MULTIMODAL`      | "conta de luz", "boleto" ou foto da câmera | Lê boleto pela câmera e pré-preenche o pagamento |
| `GUARDIAO_ANTIGOLPE`    | "INSS", "benefício bloqueado", "urgente"  | Bloqueia a tela e alerta sobre possível golpe  |
| `OPERADOR_UI`           | "Pix de 50 pro Pedro"                     | Navega pela interface e desambigua contatos    |
| `OPERADOR_UI`           | "Perdi meu cartão no ônibus"              | Abre o bloqueio temporário do cartão           |
| `ORQUESTRADOR`          | Qualquer outro input                      | Retorna à tela inicial com mensagem de sucesso |
