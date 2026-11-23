# BB Camaleão — Assistente Multiagente do Banco do Brasil

Protótipo de assistente bancário com voz, visão multimodal e proteção contra golpes, construído para o desafio IBM.

---

## Arquitetura

```
Usuário (voz / texto / câmera)
        │
        ▼
[ Frontend React ]  ──POST /api/agent/interact──▶  [ FastAPI ]
        │                                                │
        │◀──────── Contrato JSON ──────────────────────  │
        │                                         ┌──────┴──────┐
        │                              [ LangGraph StateGraph ]  │
        │                                         │             │
        │                              ┌──────────▼──────────┐  │
        │                              │  Orquestrador       │  │
        │                              │  (LLM Granite 3)    │  │
        │                              │  classifica intenção│  │
        │                              └──────┬──────────────┘  │
        │                             route_intent()            │
        │                      ┌──────┬───────┼────────┬──────┐ │
        │                      ▼      ▼       ▼        ▼      ▼ │
        │               Operador  Visão  Guardião  Esclare- Home │
        │                 UI    Multimodal Antigolpe cimento      │
        └──────────────────────────────────────────────────────┘
```

**Grafo de agentes (LangGraph):**

| Agente | Responsabilidade |
|--------|-----------------|
| `Orquestrador` | Chama o LLM (Granite 3 / mock) para classificar intenção e extrair entidades. Nunca executa ações. |
| `OperadorUI` | Navega a interface, preenche formulários, desambigua contatos ambíguos |
| `VisiãoMultimodal` | Lê imagem de boleto (OCR + LLM de visão). Mock retorna dados fixos. |
| `GuardiãoAntigolpe` | Pontuação de risco multisinal. Atrito proporcional: aviso → pausa → bloqueio + contato de confiança |
| `Esclarecimento` | Em vez de voltar à HOME em silêncio, pergunta o que o usuário queria |

**Pontuação de risco (GuardiãoAntigolpe):**

| Sinal | Pontos |
|-------|--------|
| Linguagem de pressão temporal ("urgente", "só hoje") | +30 |
| Menção a autoridade/benefício social (INSS, governo) | +35 |
| Valor > 3× a média histórica do cliente | +25 |
| Destinatário fora da lista de contatos habituais | +15 |
| Horário incomum de acesso | +10 |
| **Score ≥ 60** → CRITICAL: bloqueia + notifica contato de confiança | |
| **Score ≥ 35** → HIGH: pausa + confirmação extra (sem bloquear) | |

---

## Estrutura do projeto

```
ibm-projeto/
├── backend_main.py      # FastAPI + LangGraph (5 agentes)
└── frontend/            # React + Vite + Tailwind
    ├── src/
    │   ├── App.jsx          # UI com chamada ao backend (fonte única de verdade)
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

## 1 — Backend (FastAPI + LangGraph)

### Instalar dependências

```bash
pip install fastapi uvicorn pydantic langgraph langchain-core
```

### Rodar o servidor

```bash
uvicorn backend_main:app --reload --port 8000
```

A API ficará disponível em **http://localhost:8000**.

> Documentação interativa: http://localhost:8000/docs

### Ativar o LLM real (IBM watsonx.ai)

Por padrão o backend roda com um mock determinístico. Para ativar o **Granite 3** real:

1. Crie conta em [cloud.ibm.com](https://cloud.ibm.com) → watsonx.ai
2. Exporte as variáveis de ambiente:

```bash
# Windows (PowerShell)
$env:WATSONX_API_KEY    = "sua-api-key"
$env:WATSONX_PROJECT_ID = "seu-project-id"
# URL padrão: https://us-south.ml.cloud.ibm.com (não precisa mudar)
```

3. Reinicie o servidor — nenhuma outra mudança necessária.

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/agent/interact` | Input do usuário → Contrato JSON |
| GET  | `/api/session/{id}`   | Debug: estado da sessão |
| DELETE | `/api/session/{id}` | Limpa sessão (demo) |

**Exemplo de body:**
```json
{
  "user_input": "Preciso transferir 2 mil urgente para liberar meu INSS bloqueado",
  "current_screen": "HOME",
  "image_context": null,
  "session_id": "demo_01"
}
```

---

## 2 — Frontend (React + Vite)

### Instalar dependências

```bash
cd frontend
npm install
```

### Variável de ambiente (opcional)

Por padrão aponta para `http://localhost:8000`. Para mudar:

```bash
# frontend/.env.local
VITE_API_URL=http://seu-backend:8000
```

### Rodar em desenvolvimento

```bash
npm run dev
```

A interface ficará disponível em **http://localhost:5173**.

---

## Rodando tudo junto

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

## Cenários de demonstração (4 Atos do Pitch)

| Ato | Input | Agente acionado | O que acontece |
|-----|-------|-----------------|----------------|
| 1 | "Faz um Pix de 50 reais pro Pedro" | `OperadorUI` | Desambigua: Pedro Silva (Itaú) ou Pedro Oliveira (BB)? |
| 2 | Botão 📷 Câmera | `VisiãoMultimodal` | Lê conta de luz, preenche valor/beneficiário automaticamente |
| 3 | "Perdi meu cartão no ônibus" | `OperadorUI` | Vai direto ao bloqueio do Ourocard |
| 4 | "Transferir 2 mil urgente liberar INSS bloqueado" | `GuardiãoAntigolpe` | Score CRITICAL → bloqueia + exibe sinais de risco + aciona contato de confiança |

---

## Notas de LGPD / Segurança

- A Web Speech API do Chrome envia áudio a servidores do Google. Em produção, substituir por **IBM Watson Speech to Text** (processamento on-premise disponível).
- Voz nunca autoriza transação financeira sozinha — confirmar com biometria/PIN.
- O agente de visão propõe ações de uma lista permitida (`allow_list`); não executa comandos livres da imagem (proteção contra prompt injection em boletos).
