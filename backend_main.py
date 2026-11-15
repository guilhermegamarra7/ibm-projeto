# arquivo: backend_main.py
# Instalar dependências:
#   pip install fastapi uvicorn pydantic langgraph langchain-core
#   pip install ibm-watsonx-ai python-dotenv
#
# Para rodar: python -m uvicorn backend_main:app --reload --port 8000

from __future__ import annotations

import sys
import os

# Garante UTF-8 em todas as saidas (Windows usa cp1252 por padrao)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
os.environ.setdefault('PYTHONUTF8', '1')

import asyncio
import functools
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="BB Camaleao — Multi-Agent Backend (LangGraph + watsonx.ai)")

_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# =============================================================================
# MODELOS PYDANTIC (contrato tipado de ponta a ponta)
# =============================================================================

class UserRequest(BaseModel):
    user_input: str
    current_screen: str = "HOME"
    image_context: Optional[str] = None   # tag de simulação: 'FOTO_CONTA_LUZ', 'FOTO_QRCODE_PIX'
    image_base64: Optional[str] = None    # imagem real capturada pelo frontend (data:image/jpeg;base64,...)
    session_id: str = "default"
    user_profile: Optional[Dict[str, Any]] = None

class SecurityGuardian(BaseModel):
    risk_level: str = "LOW"
    is_blocked: bool = False
    scam_explanation: Optional[str] = None
    trusted_contact_alert: bool = False
    trusted_contact: Optional[Dict[str, str]] = None

class VoiceAssistant(BaseModel):
    tts_message: str
    should_listen_next: bool = False

class FormState(BaseModel):
    amount: Optional[float] = None
    recipient_name: Optional[str] = None
    recipient_key: Optional[str] = None
    barcode: Optional[str] = None
    card_status: str = "ACTIVE"

class ZeroUIOption(BaseModel):
    id: str
    label: str
    action_Command: str

class ZeroUIButton(BaseModel):
    label: str
    action_Command: str

class ZeroUIComponent(BaseModel):
    title: str
    subtitle: str
    options: List[ZeroUIOption] = []
    primary_confirm_button: Optional[ZeroUIButton] = None

class UIControl(BaseModel):
    target_screen: str = "HOME"
    ui_mode: str = "STANDARD"
    form_state: FormState = Field(default_factory=FormState)
    zero_ui_Dynamic_Component: Optional[ZeroUIComponent] = None

class Metadata(BaseModel):
    active_agent: str
    intent_detected: str
    confidence_score: float = 1.0
    risk_score: Optional[int] = None

class AgentResponse(BaseModel):
    metadata: Metadata
    voice_assistant: VoiceAssistant
    ui_control: UIControl
    security_guardian: SecurityGuardian

# =============================================================================
# MEMORIA DE SESSAO (TTL 30 min)
# =============================================================================

_SESSION_TTL_SECONDS = 1800

class SessionData(TypedDict):
    history: List[Dict[str, str]]
    pending_disambiguation: Optional[str]
    last_intent: Optional[str]
    last_amount: Optional[float]
    last_access: float
    access_pattern: List[float]
    recent_unknown_call: bool

_sessions: Dict[str, SessionData] = {}

def _evict_expired_sessions() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_access"] > _SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]

def get_session(session_id: str) -> SessionData:
    _evict_expired_sessions()
    if session_id not in _sessions:
        _sessions[session_id] = {
            "history": [], "pending_disambiguation": None,
            "last_intent": None, "last_amount": None,
            "last_access": time.time(), "access_pattern": [],
            "recent_unknown_call": False,
        }
    _sessions[session_id]["last_access"] = time.time()
    return _sessions[session_id]

# =============================================================================
# PERFIS DE USUARIO
# =============================================================================

PROFILES: Dict[str, Dict[str, Any]] = {
    "dona_maria": {
        "id": "dona_maria", "name": "Dona Maria", "age": 72,
        "avg_pix_amount": 180.0,
        "known_contacts": ["Pedro Silva", "Pedro Oliveira", "Farmacia Central", "Carlos"],
        "trusted_contact": {"name": "Carlos (filho)", "phone": "+55 11 99999-0001"},
        "last_transactions": [120.0, 95.0, 200.0, 80.0],
        "usual_hours": (8, 20),
        "recent_statements": [
            {"date": "15/01", "merchant": "Farmacia Central", "amount": 47.90},
            {"date": "14/01", "merchant": "MKTPLACE XYZ LTDA", "amount": 149.00},
            {"date": "13/01", "merchant": "Pedro Silva", "amount": 100.00},
        ],
    },
    "sr_joao": {
        "id": "sr_joao", "name": "Sr. Joao", "age": 68,
        "avg_pix_amount": 350.0,
        "known_contacts": ["Ana (filha)", "Mercado Bom Preco", "Posto Shell"],
        "trusted_contact": {"name": "Ana (filha)", "phone": "+55 21 98888-0002"},
        "last_transactions": [300.0, 420.0, 180.0, 350.0],
        "usual_hours": (7, 19),
        "recent_statements": [
            {"date": "15/01", "merchant": "Mercado Bom Preco", "amount": 312.50},
            {"date": "14/01", "merchant": "Posto Shell", "amount": 220.00},
        ],
    },
    "ana": {
        "id": "ana", "name": "Ana", "age": 34,
        "avg_pix_amount": 280.0,
        "known_contacts": ["Joao (pai)", "Aluguel", "Escola Kids"],
        "trusted_contact": None,
        "last_transactions": [280.0, 150.0, 500.0, 90.0],
        "usual_hours": (7, 23),
        "recent_statements": [
            {"date": "15/01", "merchant": "Escola Kids", "amount": 890.00},
            {"date": "14/01", "merchant": "RECARGA CELULAR", "amount": 30.00},
        ],
    },
}

DEFAULT_PROFILE = PROFILES["dona_maria"]

# =============================================================================
# CAMADA LLM — watsonx.ai Granite (singleton + fallback mock)
# =============================================================================

WATSONX_API_KEY = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_URL     = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

_watsonx_model = None

def _init_watsonx_model():
    global _watsonx_model
    if not WATSONX_API_KEY:
        print("[watsonx] WATSONX_API_KEY nao configurada -- usando mock_llm_stub")
        return
    try:
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
        credentials = Credentials(url=WATSONX_URL, api_key=WATSONX_API_KEY)
        client = APIClient(credentials)
        _watsonx_model = ModelInference(
            model_id="ibm/granite-3-8b-instruct",
            api_client=client,
            project_id=WATSONX_PROJECT,
            params={"max_new_tokens": 512, "temperature": 0.1},
        )
        print("[watsonx] OK Granite 3 inicializado com sucesso")
    except Exception as exc:
        print(f"[watsonx] ERRO ao inicializar: {exc} -- usando mock_llm_stub")

@app.on_event("startup")
async def startup_event():
    _init_watsonx_model()

def call_llm(prompt: str) -> str:
    if _watsonx_model is not None:
        try:
            return _watsonx_model.generate_text(prompt=prompt)
        except Exception as exc:
            print(f"[watsonx] erro na chamada: {exc} -- usando mock_llm_stub")
    return _mock_llm_stub(prompt)

def _mock_llm_stub(prompt: str) -> str:
    text = prompt.lower()
    m = re.search(r'user_input["\s:]+(.+?)(?:\n|context|historico)', text, re.DOTALL)
    utterance = m.group(1).strip().lower() if m else text

    if any(w in utterance for w in ["conta de luz", "boleto", "camera", "foto", "qr", "qrcode"]):
        intent, entities = "PAY_BILL", {"bill_type": "boleto"}
    elif any(w in utterance for w in ["inss", "beneficio", "aposentadoria", "liberar", "previdencia"]):
        intent, entities = "SCAM_RISK", {"trigger": "previdencia_social"}
    elif any(w in utterance for w in ["urgente", "so hoje", "corre", "imediato"]):
        intent, entities = "SCAM_RISK", {"trigger": "pressao_temporal"}
    elif any(w in utterance for w in ["extrato", "esse debito", "esse gasto", "cobrado", "reconhec"]):
        intent, entities = "STATEMENT_REVIEW", {}
    elif "pix" in utterance or "transferi" in utterance or "mandar" in utterance or "manda" in utterance or "enviar" in utterance:
        val_match = re.search(r"(\d+[\.,]?\d*)\s*(?:reais?|conto|r\$)?", utterance)
        value = float(val_match.group(1).replace(",", ".")) if val_match else 0.0
        name_match = re.search(r"(?:para|pro|pra|p/)\s+(?:o |a |os |as |ao )?([a-z\u00e0-\u00fc ]+)", utterance)
        raw_name = name_match.group(1).strip().title() if name_match else None
        intent, entities = "PIX_TRANSFER", {"amount": value, "recipient_raw": raw_name}
    elif any(w in utterance for w in ["cartao", "perdi", "onibus", "roubei", "bloqueio"]):
        intent, entities = "BLOCK_CARD", {"card_last4": "4321"}
    elif any(w in utterance for w in ["pedro silva", "silva"]) and "pedro" in utterance:
        intent, entities = "PIX_CONFIRM", {"recipient": "Pedro Silva", "bank": "Itau"}
    elif any(w in utterance for w in ["pedro oliveira", "oliveira"]) and "pedro" in utterance:
        intent, entities = "PIX_CONFIRM", {"recipient": "Pedro Oliveira", "bank": "Banco do Brasil"}
    elif "pedro" in utterance:
        intent, entities = "PIX_DISAMBIGUATION", {"recipient_raw": "Pedro"}
    elif any(w in utterance for w in ["voltar", "inicio", "home", "cancelar", "sair"]):
        intent, entities = "HOME_NAVIGATION", {}
    else:
        intent, entities = "CLARIFICATION_NEEDED", {}

    return json.dumps({"intent": intent, "entities": entities, "confidence": 0.91})

# =============================================================================
# SISTEMA DE RISCO MULTISINAL
# =============================================================================

def calculate_risk_score(user_input: str, entities: Dict[str, Any], profile: Dict[str, Any], session: SessionData) -> Dict[str, Any]:
    score = 0
    signals: List[str] = []
    text = user_input.lower()

    if any(w in text for w in ["urgente", "urgencia", "imediato", "corre", "so hoje", "agora mesmo"]):
        score += 30; signals.append("Linguagem de pressao temporal detectada")
    if any(w in text for w in ["inss", "beneficio", "aposentadoria", "governo", "banco central", "receita federal", "liberar", "previdencia"]):
        score += 35; signals.append("Mencao a autoridade/beneficio social — padrao de golpe previdenciario")

    amount = entities.get("amount") or 0
    avg = profile.get("avg_pix_amount", 180.0)
    if amount > 0 and amount > avg * 3:
        score += 25; signals.append(f"Valor R$ {amount:.0f} e {amount/avg:.1f}x acima da sua media (R$ {avg:.0f})")

    recipient = entities.get("recipient_raw") or entities.get("recipient", "")
    known = profile.get("known_contacts", [])
    if recipient and not any(recipient.lower() in c.lower() for c in known):
        score += 15; signals.append(f"'{recipient}' nao esta nos seus contatos habituais")

    now_hour = datetime.now().hour
    h_start, h_end = profile.get("usual_hours", (8, 20))
    if not (h_start <= now_hour <= h_end):
        score += 10; signals.append(f"Horario incomum ({now_hour}h, fora do padrao {h_start}h-{h_end}h)")

    pattern = session.get("access_pattern", [])
    now = time.time()
    recent = [t for t in pattern if now - t < 300]
    if len(recent) >= 3:
        score += 20; signals.append(f"Padrao de acesso anomalo: {len(recent)} acessos nos ultimos 5 minutos")

    if session.get("recent_unknown_call"):
        score += 25; signals.append("Ligacao de numero desconhecido detectada antes de abrir o app")

    level = "CRITICAL" if score >= 60 else "HIGH" if score >= 35 else "MEDIUM" if score >= 20 else "LOW"
    return {"score": score, "level": level, "signals": signals}

# =============================================================================
# ESTADO DO GRAFO LANGGRAPH
# =============================================================================

class AgentState(TypedDict):
    user_input: str
    image_context: Optional[str]
    image_base64: Optional[str]   # imagem real (data URL ou base64 puro)
    session: SessionData
    profile: Dict[str, Any]
    intent: str
    entities: Dict[str, Any]
    confidence: float
    risk: Optional[Dict[str, Any]]
    response: Optional[Dict[str, Any]]

# =============================================================================
# NOS DO GRAFO
# =============================================================================

def node_orquestrador(state: AgentState) -> AgentState:
    history_text = "\n".join(f"- {m['role']}: {m['content']}" for m in state["session"]["history"][-4:]) or "Nenhum historico ainda."
    prompt = f"""Voce e o orquestrador de um assistente bancario do Banco do Brasil.
Analise o input do usuario e classifique a intencao.

user_input: "{state['user_input']}"
image_context: {state.get('image_context')}
historico recente:
{history_text}

Responda SOMENTE com JSON valido:
{{"intent": "PIX_TRANSFER|PAY_BILL|BLOCK_CARD|SCAM_RISK|PIX_DISAMBIGUATION|PIX_CONFIRM|HOME_NAVIGATION|CLARIFICATION_NEEDED|STATEMENT_REVIEW", "entities": {{}}, "confidence": 0.0}}
"""
    raw = call_llm(prompt)
    try:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(json_match.group() if json_match else raw)
    except Exception:
        parsed = {"intent": "CLARIFICATION_NEEDED", "entities": {}, "confidence": 0.5}

    state["intent"]     = parsed.get("intent", "CLARIFICATION_NEEDED")
    state["entities"]   = parsed.get("entities", {})
    state["confidence"] = parsed.get("confidence", 0.9)
    state["risk"]       = None
    return state

def _is_ambiguous_recipient(recipient_raw: Optional[str], known_contacts: List[str]) -> bool:
    if not recipient_raw:
        return False
    return sum(1 for c in known_contacts if recipient_raw.lower() in c.lower()) > 1

def node_operador_ui(state: AgentState) -> AgentState:
    intent = state["intent"]; entities = state["entities"]; profile = state["profile"]
    if intent == "PIX_TRANSFER":
        rr = entities.get("recipient_raw")
        if _is_ambiguous_recipient(rr, profile.get("known_contacts", [])):
            intent = "PIX_DISAMBIGUATION"
            if entities.get("amount"):
                state["session"]["last_amount"] = entities["amount"]

    if intent == "PIX_DISAMBIGUATION":
        amt = entities.get("amount") or state["session"].get("last_amount") or 0
        state["response"] = {
            "metadata": {"active_agent": "OPERADOR_UI", "intent_detected": "PIX_TRANSFER", "confidence_score": state["confidence"], "risk_score": None},
            "voice_assistant": {"tts_message": f"Abri o Pix com R$ {amt:.0f}. Voce tem contatos com esse nome. Para qual deles?", "should_listen_next": True},
            "ui_control": {
                "target_screen": "PIX_AREA", "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"amount": amt, "recipient_name": entities.get("recipient_raw", "?")},
                "zero_ui_Dynamic_Component": {
                    "title": "Qual contato voce quer pagar?",
                    "subtitle": f"Valor: R$ {amt:.2f}".replace(".", ","),
                    "options": [
                        {"id": "p1", "label": "👤 PEDRO SILVA (Itau)", "action_Command": "Pix para Pedro Silva"},
                        {"id": "p2", "label": "👤 PEDRO OLIVEIRA (Banco do Brasil)", "action_Command": "Pix para Pedro Oliveira"},
                    ],
                    "primary_confirm_button": None,
                },
            },
            "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
        }
    elif intent == "PIX_CONFIRM":
        recipient = entities.get("recipient", "")
        amount = state["session"].get("last_amount") or entities.get("amount", 50.0)
        state["session"]["last_amount"] = amount
        state["response"] = {
            "metadata": {"active_agent": "OPERADOR_UI", "intent_detected": "PIX_TRANSFER_READY", "confidence_score": state["confidence"], "risk_score": None},
            "voice_assistant": {"tts_message": f"Prontinho! {recipient} selecionado, valor R$ {amount:.0f}. Toque no botao verde para confirmar com digital.", "should_listen_next": False},
            "ui_control": {
                "target_screen": "PIX_AREA", "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"amount": amount, "recipient_name": recipient},
                "zero_ui_Dynamic_Component": {
                    "title": "Tudo pronto para enviar!", "subtitle": f"Para: {recipient}",
                    "options": [],
                    "primary_confirm_button": {"label": f"✅ CONFIRMAR PIX DE R$ {amount:.0f} (BIOMETRIA)", "action_Command": "Confirmar envio do Pix"},
                },
            },
            "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
        }
    elif intent == "BLOCK_CARD":
        state["response"] = {
            "metadata": {"active_agent": "OPERADOR_UI", "intent_detected": "BLOCK_CARD", "confidence_score": state["confidence"], "risk_score": None},
            "voice_assistant": {"tts_message": "Fique tranquilo! Ja abri a area do seu Ourocard final 4321. Toque no botao para bloquear agora.", "should_listen_next": False},
            "ui_control": {
                "target_screen": "CARD_AREA", "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"card_status": "PENDING_BLOCK"},
                "zero_ui_Dynamic_Component": {
                    "title": "🔒 Proteger seu Ourocard", "subtitle": "Cartao Final 4321 — Bloqueio Instantaneo",
                    "options": [],
                    "primary_confirm_button": {"label": "BLOQUEAR MEU CARTAO AGORA", "action_Command": "Confirmar bloqueio do cartao"},
                },
            },
            "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
        }
    elif intent == "HOME_NAVIGATION":
        state["response"] = _home_response()
    if state["response"] is None and state["intent"] == "PIX_TRANSFER":
        amt = entities.get("amount") or 0
        state["response"] = {
            "metadata": {"active_agent": "OPERADOR_UI", "intent_detected": "PIX_TRANSFER", "confidence_score": state["confidence"], "risk_score": None},
            "voice_assistant": {"tts_message": "Abri a area do Pix. Para quem e qual valor voce quer transferir?", "should_listen_next": True},
            "ui_control": {
                "target_screen": "PIX_AREA", "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"amount": amt or None},
                "zero_ui_Dynamic_Component": {"title": "Enviar Pix", "subtitle": "Diga o nome de quem vai receber e o valor.", "options": [], "primary_confirm_button": None},
            },
            "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
        }
    return state

# ---------------------------------------------------------------------------
# Helpers de visão
# ---------------------------------------------------------------------------
def _extract_base64_bytes(data_url: str) -> Optional[bytes]:
    """Extrai bytes puros de um data URL (data:image/jpeg;base64,...) ou string base64 crua."""
    import base64
    try:
        if data_url.startswith("data:"):
            _, encoded = data_url.split(",", 1)
        else:
            encoded = data_url
        return base64.b64decode(encoded)
    except Exception:
        return None


def _analyze_image_with_watsonx_vision(image_bytes: bytes, is_qrcode: bool) -> Optional[Dict[str, Any]]:
    """
    Chama watsonx Llama Vision (meta-llama/llama-3-2-11b-vision-instruct) para analisar a imagem.
    Retorna dict extraído ou None se falhar.
    """
    if not WATSONX_API_KEY:
        return None
    try:
        import base64
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
        credentials = Credentials(url=WATSONX_URL, api_key=WATSONX_API_KEY)
        client = APIClient(credentials)
        vision_model = ModelInference(
            model_id="meta-llama/llama-3-2-11b-vision-instruct",
            api_client=client,
            project_id=WATSONX_PROJECT,
            params={"max_new_tokens": 256, "temperature": 0.1},
        )
        b64 = base64.b64encode(image_bytes).decode()
        if is_qrcode:
            question = (
                "Esta imagem contem um QR Code Pix brasileiro. "
                "Extraia: beneficiario, valor em reais, chave pix. "
                "Responda APENAS em JSON: {\"beneficiario\": \"...\", \"valor\": 0.00, \"chave_pix\": \"...\", \"vencimento\": \"Hoje\"}"
            )
        else:
            question = (
                "Esta imagem contem um boleto ou conta a pagar brasileira. "
                "Extraia: beneficiario, valor total em reais, data de vencimento, linha digitavel se houver. "
                "Responda APENAS em JSON: {\"beneficiario\": \"...\", \"valor\": 0.00, \"vencimento\": \"DD/MM/AAAA\", \"linha_digitavel\": \"...\"}"
            )
        # Chama com imagem inline
        result = vision_model.generate_text(
            prompt=question,
            guardrails=False,
            # ibm-watsonx-ai >= 1.1 suporta messages com image_url inline
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
        )
        # Tenta parsear o JSON da resposta
        m = re.search(r'\{.*\}', result, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception as exc:
        print(f"[visao] erro Llama Vision: {exc}")
    return None


def _mock_vision_analysis(image_bytes: Optional[bytes], is_qrcode: bool) -> Dict[str, Any]:
    """
    Mock inteligente: se a imagem existir, tenta detectar características básicas.
    Sempre retorna dados plausíveis para demo.
    """
    if is_qrcode:
        return {
            "tipo": "QR Code Pix",
            "valor": 35.00,
            "beneficiario": "Farmácia São Paulo",
            "chave_pix": "farmacia@email.com",
            "vencimento": "Hoje",
            "source": "vision_mock",
        }
    return {
        "tipo": "Boleto",
        "valor": 84.90,
        "beneficiario": "Companhia de Energia Elétrica",
        "linha_digitavel": "83640000000-8 84900132026-4",
        "vencimento": "Amanhã",
        "source": "vision_mock",
    }


def node_visao_multimodal(state: AgentState) -> AgentState:
    img_ctx   = state.get("image_context") or ""
    img_b64   = state.get("image_base64")
    utterance = state["user_input"].lower()
    is_qrcode = "qr" in img_ctx.lower() or "qr" in utterance

    extracted = None

    # 1. Tenta análise real via Llama Vision se tiver imagem base64
    if img_b64:
        image_bytes = _extract_base64_bytes(img_b64)
        if image_bytes:
            extracted = _analyze_image_with_watsonx_vision(image_bytes, is_qrcode)
            if extracted:
                extracted["source"] = "llama_vision"

    # 2. Fallback: mock descritivo
    if not extracted:
        image_bytes_for_mock = _extract_base64_bytes(img_b64) if img_b64 else None
        extracted = _mock_vision_analysis(image_bytes_for_mock, is_qrcode)

    # 3. Monta resposta
    valor = float(extracted.get("valor", 0))
    beneficiario = extracted.get("beneficiario", "Beneficiário")
    vencimento   = extracted.get("vencimento", "Hoje")
    source_label = "🔍 IA Vision" if extracted.get("source") == "llama_vision" else "🎭 Simulação"

    if is_qrcode:
        tts   = f"Li o QR Code Pix. É um pagamento de R$ {valor:.0f} reais para {beneficiario}. Toque no botão verde para confirmar."
        title = f"📷 QR Code Pix — {source_label}"
        label = f"✅ PAGAR R$ {valor:.2f}".replace(".", ",")
        action = "Confirmar pagamento QR Code"
    else:
        reais = int(valor)
        centavos = int(round((valor - reais) * 100))
        tts   = f"Li a conta. O valor é {reais} reais e {centavos:02d} centavos para {beneficiario}, vencendo {vencimento}. Toque no botão verde para confirmar."
        title = f"📷 Documento Lido — {source_label}"
        label = f"✅ PAGAR R$ {valor:.2f}".replace(".", ",")
        action = "Confirmar pagamento do boleto"

    state["response"] = {
        "metadata": {"active_agent": "VISAO_MULTIMODAL", "intent_detected": "PAY_BILL", "confidence_score": 0.97, "risk_score": None},
        "voice_assistant": {"tts_message": tts, "should_listen_next": False},
        "ui_control": {
            "target_screen": "BOLETO_AREA", "ui_mode": "ZERO_UI_HIGH_CONTRAST",
            "form_state": {
                "amount": valor,
                "recipient_name": beneficiario,
                "barcode": extracted.get("linha_digitavel") or extracted.get("chave_pix") or "",
            },
            "zero_ui_Dynamic_Component": {
                "title": title,
                "subtitle": f"{beneficiario} · Vence {vencimento}",
                "options": [],
                "primary_confirm_button": {"label": label, "action_Command": action},
            },
        },
        "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
    }
    return state

def node_guardiao_antigolpe(state: AgentState) -> AgentState:
    risk    = state["risk"] or calculate_risk_score(state["user_input"], state["entities"], state["profile"], state["session"])
    trusted = state["profile"].get("trusted_contact") or {}
    signals_text = " | ".join(risk["signals"]) if risk["signals"] else "nenhum"
    name = state["profile"].get("name", "")
    if risk["level"] == "CRITICAL":
        state["response"] = {
            "metadata": {"active_agent": "GUARDIAO_ANTIGOLPE", "intent_detected": "SCAM_INTERVENTION", "confidence_score": 0.97, "risk_score": risk["score"]},
            "voice_assistant": {"tts_message": f"{name}, parei essa operacao para proteger voce. O Banco do Brasil nunca pede Pix para liberar beneficio." + (f" Estou avisando {trusted.get('name', 'seu contato de confianca')} agora." if trusted else ""), "should_listen_next": False},
            "ui_control": {
                "target_screen": "SECURITY_ALERT", "ui_mode": "ZERO_UI_EMERGENCY_LOCK",
                "form_state": {"amount": state["entities"].get("amount"), "recipient_name": state["entities"].get("recipient_raw", "Destinatario Desconhecido")},
                "zero_ui_Dynamic_Component": {
                    "title": "🛡 PROTECAO ATIVADA", "subtitle": f"Motivo: {signals_text[:130]}",
                    "options": [
                        {"id": "cancel", "label": "❌ CANCELAR OPERACAO E VOLTAR", "action_Command": "Voltar ao inicio"},
                        {"id": "trusted", "label": f"📲 AVISAR {trusted.get('name', 'CONTATO SEGURO').upper()}", "action_Command": "Avisar contato de confianca"},
                    ],
                    "primary_confirm_button": None,
                },
            },
            "security_guardian": {"risk_level": "CRITICAL", "is_blocked": True, "scam_explanation": f"Score de risco: {risk['score']}/100. Sinais: {signals_text}", "trusted_contact_alert": bool(trusted), "trusted_contact": trusted or None},
        }
    elif risk["level"] == "HIGH":
        state["response"] = {
            "metadata": {"active_agent": "GUARDIAO_ANTIGOLPE", "intent_detected": "RISK_WARNING", "confidence_score": 0.85, "risk_score": risk["score"]},
            "voice_assistant": {"tts_message": f"{name}, antes de continuar: {risk['signals'][0]}. Tem certeza que quer fazer isso agora?", "should_listen_next": True},
            "ui_control": {
                "target_screen": "SECURITY_ALERT", "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"amount": state["entities"].get("amount")},
                "zero_ui_Dynamic_Component": {
                    "title": "⚠️ Confirmacao Extra Necessaria", "subtitle": f"Atencao: {risk['signals'][0]}",
                    "options": [
                        {"id": "confirm", "label": "✅ SIM, QUERO CONTINUAR", "action_Command": state["user_input"] + " confirmado"},
                        {"id": "cancel", "label": "❌ NAO, CANCELAR", "action_Command": "Voltar ao inicio"},
                    ],
                    "primary_confirm_button": None,
                },
            },
            "security_guardian": {"risk_level": "HIGH", "is_blocked": False, "scam_explanation": f"Score: {risk['score']}/100. Sinais: {signals_text}", "trusted_contact_alert": False},
        }
    elif risk["level"] == "MEDIUM":
        state["response"] = {
            "metadata": {"active_agent": "GUARDIAO_ANTIGOLPE", "intent_detected": "RISK_NOTICE", "confidence_score": 0.75, "risk_score": risk["score"]},
            "voice_assistant": {"tts_message": f"{name}, so um aviso: {risk['signals'][0]}. Se estiver tudo certo, pode continuar normalmente.", "should_listen_next": True},
            "ui_control": {
                "target_screen": "HOME", "ui_mode": "ZERO_UI_HIGH_CONTRAST", "form_state": {},
                "zero_ui_Dynamic_Component": {
                    "title": "ℹ️ Aviso de Seguranca", "subtitle": risk["signals"][0],
                    "options": [
                        {"id": "ok", "label": "✅ ENTENDIDO, CONTINUAR", "action_Command": state["user_input"]},
                        {"id": "cancel", "label": "← VOLTAR AO INICIO", "action_Command": "Voltar ao inicio"},
                    ],
                    "primary_confirm_button": None,
                },
            },
            "security_guardian": {"risk_level": "MEDIUM", "is_blocked": False, "scam_explanation": f"Score: {risk['score']}/100. Sinais: {signals_text}", "trusted_contact_alert": False},
        }
    else:
        state["response"] = _home_response()
    return state

def node_extrato(state: AgentState) -> AgentState:
    profile = state["profile"]; statements = profile.get("recent_statements", []); name = profile.get("name", "")
    suspicious_patterns = ["mktplace", "mkt", "online", "digital", "recarg", "assinatur", "sub ", "trial"]
    suspicious = [s for s in statements if any(p in s["merchant"].lower() for p in suspicious_patterns)]
    if suspicious:
        item = suspicious[0]
        tts = f"{name}, vi um lancamento que pode precisar da sua atencao: R$ {item['amount']:.2f} cobrado por '{item['merchant']}' em {item['date']}. Voce reconhece essa compra?"
        title = "📋 Lancamento para Confirmar"; subtitle = f"{item['merchant']} - R$ {item['amount']:.2f} - {item['date']}"
        options = [{"id": "yes", "label": "✅ SIM, EU FIZ ESSA COMPRA", "action_Command": "Reconheco esse lancamento"}, {"id": "no", "label": "❌ NAO RECONHECO — CONTESTAR", "action_Command": "Contestar lancamento desconhecido"}]
    elif statements:
        item = statements[0]
        tts = f"{name}, seus ultimos lancamentos estao normais. O mais recente foi R$ {item['amount']:.2f} em {item['merchant']} no dia {item['date']}."
        title = "📋 Extrato Recente"; subtitle = f"Ultimo: {item['merchant']} - R$ {item['amount']:.2f}"
        options = [{"id": "all", "label": "📋 VER EXTRATO COMPLETO", "action_Command": "Mostrar extrato completo"}, {"id": "back", "label": "← VOLTAR AO INICIO", "action_Command": "Voltar ao inicio"}]
    else:
        tts = "Nao encontrei lancamentos recentes para revisar."
        title = "📋 Extrato"; subtitle = "Sem lancamentos recentes"; options = []
    state["response"] = {
        "metadata": {"active_agent": "EXTRATO", "intent_detected": "STATEMENT_REVIEW", "confidence_score": 0.92, "risk_score": None},
        "voice_assistant": {"tts_message": tts, "should_listen_next": bool(suspicious)},
        "ui_control": {
            "target_screen": "HOME", "ui_mode": "ZERO_UI_HIGH_CONTRAST", "form_state": {},
            "zero_ui_Dynamic_Component": {"title": title, "subtitle": subtitle, "options": options, "primary_confirm_button": None},
        },
        "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
    }
    return state

def node_esclarecimento(state: AgentState) -> AgentState:
    state["response"] = {
        "metadata": {"active_agent": "ORQUESTRADOR", "intent_detected": "CLARIFICATION_NEEDED", "confidence_score": 0.5, "risk_score": None},
        "voice_assistant": {"tts_message": "Nao entendi bem o que voce precisa. Posso ajudar com Pix, pagamento de conta, extrato ou bloqueio de cartao. O que voce gostaria?", "should_listen_next": True},
        "ui_control": {
            "target_screen": "HOME", "ui_mode": "ZERO_UI_HIGH_CONTRAST", "form_state": {},
            "zero_ui_Dynamic_Component": {
                "title": "Como posso ajudar?", "subtitle": "Escolha uma opcao ou fale comigo:",
                "options": [
                    {"id": "pix",     "label": "💸 FAZER UM PIX",        "action_Command": "Quero fazer um Pix"},
                    {"id": "boleto",  "label": "💰 PAGAR UMA CONTA",     "action_Command": "Quero pagar uma conta"},
                    {"id": "extrato", "label": "📋 VER MEU EXTRATO",     "action_Command": "Quero ver meu extrato"},
                    {"id": "cartao",  "label": "💳 BLOQUEAR MEU CARTAO", "action_Command": "Preciso bloquear meu cartao"},
                    {"id": "humano",  "label": "👤 FALAR COM ATENDENTE", "action_Command": "Falar com atendente humano"},
                ],
                "primary_confirm_button": None,
            },
        },
        "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
    }
    return state

def node_home(state: AgentState) -> AgentState:
    state["response"] = _home_response(); return state

def _home_response() -> Dict[str, Any]:
    return {
        "metadata": {"active_agent": "ORQUESTRADOR", "intent_detected": "HOME_NAVIGATION", "confidence_score": 1.0, "risk_score": None},
        "voice_assistant": {"tts_message": "Pronto! Voltamos para a tela inicial. Como posso ajudar agora?", "should_listen_next": False},
        "ui_control": {"target_screen": "HOME", "ui_mode": "STANDARD", "form_state": {"amount": None, "recipient_name": None, "card_status": "ACTIVE"}, "zero_ui_Dynamic_Component": None},
        "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
    }

def route_intent(state: AgentState) -> Literal["operador_ui", "visao_multimodal", "guardiao_antigolpe", "extrato", "esclarecimento", "home"]:
    intent = state["intent"]; image = state.get("image_context")
    if image and image.startswith("FOTO"):
        return "visao_multimodal"
    if intent in ("PIX_TRANSFER", "PIX_CONFIRM", "SCAM_RISK"):
        risk = calculate_risk_score(state["user_input"], state["entities"], state["profile"], state["session"])
        state["risk"] = risk
        if risk["level"] in ("CRITICAL", "HIGH", "MEDIUM"):
            state["intent"] = "SCAM_RISK"; return "guardiao_antigolpe"
    return {"PIX_TRANSFER": "operador_ui", "PIX_DISAMBIGUATION": "operador_ui", "PIX_CONFIRM": "operador_ui", "BLOCK_CARD": "operador_ui", "PAY_BILL": "visao_multimodal", "SCAM_RISK": "guardiao_antigolpe", "STATEMENT_REVIEW": "extrato", "HOME_NAVIGATION": "home", "CLARIFICATION_NEEDED": "esclarecimento"}.get(intent, "esclarecimento")

def build_graph():
    g = StateGraph(AgentState)
    for name, fn in [("orquestrador", node_orquestrador), ("operador_ui", node_operador_ui), ("visao_multimodal", node_visao_multimodal), ("guardiao_antigolpe", node_guardiao_antigolpe), ("extrato", node_extrato), ("esclarecimento", node_esclarecimento), ("home", node_home)]:
        g.add_node(name, fn)
    g.set_entry_point("orquestrador")
    g.add_conditional_edges("orquestrador", route_intent, {"operador_ui": "operador_ui", "visao_multimodal": "visao_multimodal", "guardiao_antigolpe": "guardiao_antigolpe", "extrato": "extrato", "esclarecimento": "esclarecimento", "home": "home"})
    for node in ("operador_ui", "visao_multimodal", "guardiao_antigolpe", "extrato", "esclarecimento", "home"):
        g.add_edge(node, END)
    return g.compile()

_graph = build_graph()

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.post("/api/agent/interact", response_model=AgentResponse)
async def interact(req: UserRequest) -> AgentResponse:
    session = get_session(req.session_id)
    profile = req.user_profile or DEFAULT_PROFILE
    session["access_pattern"].append(time.time())
    session["access_pattern"] = session["access_pattern"][-20:]
    session["history"].append({"role": "user", "content": req.user_input})
    initial: AgentState = {
        "user_input": req.user_input,
        "image_context": req.image_context,
        "image_base64": req.image_base64,
        "session": session, "profile": profile,
        "intent": "", "entities": {}, "confidence": 0.0, "risk": None, "response": None,
    }
    # run_in_executor evita bloquear o event loop do FastAPI com o graph sincrono
    loop = asyncio.get_event_loop()
    final = await loop.run_in_executor(None, functools.partial(_graph.invoke, initial))
    response = final["response"]
    session["history"].append({"role": "assistant", "content": response["voice_assistant"]["tts_message"]})
    if final["entities"].get("amount"):
        session["last_amount"] = final["entities"]["amount"]
    session["last_intent"] = final["intent"]
    return AgentResponse(**response)

@app.post("/api/session/{session_id}/flag_unknown_call")
async def flag_unknown_call(session_id: str):
    get_session(session_id)["recent_unknown_call"] = True
    return {"flagged": True}

@app.post("/api/session/{session_id}/change_profile")
async def change_profile(session_id: str, profile_id: str):
    if profile_id not in PROFILES:
        return {"error": f"Perfil '{profile_id}' nao encontrado. Disponiveis: {list(PROFILES.keys())}"}
    get_session(session_id)["profile_id"] = profile_id
    return {"changed": True, "profile": PROFILES[profile_id]["name"]}

@app.get("/api/profiles")
async def list_profiles():
    return {pid: {"name": p["name"], "age": p["age"]} for pid, p in PROFILES.items()}

@app.get("/api/session/{session_id}")
async def get_session_debug(session_id: str):
    return _sessions.get(session_id, {})

@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"cleared": True}
