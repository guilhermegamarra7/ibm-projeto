# arquivo: backend_main.py
# Instalar dependências:
#   pip install fastapi uvicorn pydantic langgraph langchain-core
#   pip install ibm-watsonx-ai  # quando tiver a API key
#
# Para rodar: uvicorn backend_main:app --reload --port 8000

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

app = FastAPI(title="BB Camaleão — Multi-Agent Backend (LangGraph)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# MODELOS DE REQUEST / RESPONSE
# =============================================================================

class UserRequest(BaseModel):
    user_input: str
    current_screen: str = "HOME"
    image_context: Optional[str] = None
    session_id: str = "default"
    # Perfil do cliente (virá do banco real; aqui é fixo para demo)
    user_profile: Optional[Dict[str, Any]] = None


# =============================================================================
# MEMÓRIA DE SESSÃO (em produção: Redis ou watsonx Assistant context)
# =============================================================================

_sessions: Dict[str, Dict[str, Any]] = {}

def get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "history": [],
            "pending_disambiguation": None,
            "last_intent": None,
            "last_amount": None,
        }
    return _sessions[session_id]


# =============================================================================
# PERFIL DE USUÁRIO PADRÃO (mock — em produção vem do core bancário)
# =============================================================================

DEFAULT_PROFILE = {
    "name": "Dona Maria",
    "avg_pix_amount": 180.0,          # média histórica de Pix
    "known_contacts": ["Pedro Silva", "Pedro Oliveira", "Farmácia Central"],
    "trusted_contact": {"name": "Carlos (filho)", "phone": "+55 11 99999-0001"},
    "last_transactions": [120.0, 95.0, 200.0, 80.0],  # últimas transferências
    "usual_hours": (8, 20),            # horário típico de uso
}


# =============================================================================
# CAMADA LLM — watsonx.ai Granite (com fallback mock para demo sem API key)
# =============================================================================

WATSONX_API_KEY  = os.getenv("WATSONX_API_KEY", "")
WATSONX_PROJECT  = os.getenv("WATSONX_PROJECT_ID", "")
WATSONX_URL      = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

def call_llm(prompt: str, json_mode: bool = True) -> str:
    """
    Chama o IBM watsonx.ai (Granite 3).
    Se WATSONX_API_KEY não estiver configurada, usa o mock local.

    Para ativar a IA real:
      1. Crie conta em cloud.ibm.com → watsonx.ai
      2. Exporte as variáveis de ambiente:
           export WATSONX_API_KEY="sua-key"
           export WATSONX_PROJECT_ID="seu-project-id"
      3. Reinicie o servidor — nenhuma outra mudança necessária.
    """
    if WATSONX_API_KEY:
        try:
            from ibm_watsonx_ai import APIClient, Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference
            credentials = Credentials(url=WATSONX_URL, api_key=WATSONX_API_KEY)
            client = APIClient(credentials)
            model = ModelInference(
                model_id="ibm/granite-3-8b-instruct",
                api_client=client,
                project_id=WATSONX_PROJECT,
                params={"max_new_tokens": 512, "temperature": 0.1},
            )
            return model.generate_text(prompt=prompt)
        except Exception as exc:
            print(f"[watsonx] erro: {exc} — usando mock local")

    return _mock_llm(prompt)


def _mock_llm(prompt: str) -> str:
    """
    Mock determinístico do LLM para demo offline.
    Replica a lógica de classificação que o Granite faria,
    mas de forma transparente e documentada como mock.
    Mantém o mesmo contrato de saída JSON que o LLM real retornaria.
    """
    text = prompt.lower()

    # Extrai o user_input do prompt (está entre aspas no template abaixo)
    m = re.search(r'user_input["\s:]+(.+?)(?:\n|context|histórico)', text, re.DOTALL)
    utterance = m.group(1).strip().lower() if m else text

    # Classificação de intenção
    if any(w in utterance for w in ["conta de luz", "boleto", "câmera", "foto"]):
        intent, entities = "PAY_BILL", {"bill_type": "energia"}
    elif any(w in utterance for w in ["inss", "benefício", "aposentadoria", "liberar"]):
        intent, entities = "SCAM_RISK", {"trigger": "previdencia_social"}
    elif any(w in utterance for w in ["urgente", "bloqueado", "só hoje", "corre"]):
        intent, entities = "SCAM_RISK", {"trigger": "pressao_temporal"}
    elif "pix" in utterance or "transferi" in utterance or "mandar" in utterance or "manda" in utterance:
        # Extrai valor
        val_match = re.search(r"(\d+[\.,]?\d*)\s*(?:reais?|conto|r\$)?", utterance)
        value = float(val_match.group(1).replace(",", ".")) if val_match else 0.0
        # Extrai nome — ignora artigos/preposições iniciais (o, a, os, as, ao, à)
        name_match = re.search(r"(?:para|pro|pra|p/)\s+(?:o |a |os |as |ao |à )?([a-záéíóúãõçâêô ]+)", utterance)
        raw_name = name_match.group(1).strip().title() if name_match else None
        intent = "PIX_TRANSFER"
        entities = {"amount": value, "recipient_raw": raw_name}
    elif any(w in utterance for w in ["cartão", "perdi", "ônibus", "roubei", "bloqueio"]):
        intent, entities = "BLOCK_CARD", {"card_last4": "4321"}
    elif any(w in utterance for w in ["pedro silva", "silva"]) and "pedro" in utterance:
        intent, entities = "PIX_CONFIRM", {"recipient": "Pedro Silva", "bank": "Itaú"}
    elif any(w in utterance for w in ["pedro oliveira", "oliveira"]) and "pedro" in utterance:
        intent, entities = "PIX_CONFIRM", {"recipient": "Pedro Oliveira", "bank": "Banco do Brasil"}
    elif "pedro" in utterance:
        intent, entities = "PIX_DISAMBIGUATION", {"recipient_raw": "Pedro"}
    elif any(w in utterance for w in ["voltar", "início", "home", "cancelar"]):
        intent, entities = "HOME_NAVIGATION", {}
    else:
        intent, entities = "CLARIFICATION_NEEDED", {}

    return json.dumps({"intent": intent, "entities": entities, "confidence": 0.91})


# =============================================================================
# SISTEMA DE PONTUAÇÃO DE RISCO (Antigolpe multisinal)
# =============================================================================

def calculate_risk_score(
    user_input: str,
    entities: Dict[str, Any],
    profile: Dict[str, Any],
    session: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Pontuação de risco baseada em múltiplos sinais independentes.
    Cada sinal contribui com pontos; o total determina o nível de atrito.

    Retorna: {"score": 0-100, "level": LOW|MEDIUM|HIGH|CRITICAL, "signals": [...]}
    """
    score = 0
    signals = []
    text = user_input.lower()

    # Sinal 1: Pressão temporal / linguagem de urgência
    urgency_words = ["urgente", "urgência", "hoje", "agora", "imediato", "corre", "rápido", "só hoje"]
    if any(w in text for w in urgency_words):
        score += 30
        signals.append("Linguagem de pressão temporal detectada")

    # Sinal 2: Menção a autoridades ou benefícios sociais (padrão de engenharia social)
    authority_words = ["inss", "benefício", "aposentadoria", "governo", "banco central",
                       "receita federal", "funcionário", "atendente do banco", "liberar"]
    if any(w in text for w in authority_words):
        score += 35
        signals.append("Menção a autoridade/benefício social — padrão de golpe previdenciário")

    # Sinal 3: Valor muito acima da média histórica do cliente
    amount = entities.get("amount", 0) or 0
    avg = profile.get("avg_pix_amount", 180.0)
    if amount > 0 and amount > avg * 3:
        score += 25
        signals.append(f"Valor R$ {amount:.0f} é {amount/avg:.1f}x acima da sua média (R$ {avg:.0f})")

    # Sinal 4: Destinatário desconhecido
    recipient = entities.get("recipient_raw") or entities.get("recipient", "")
    known = profile.get("known_contacts", [])
    if recipient and not any(recipient.lower() in c.lower() for c in known):
        score += 15
        signals.append(f"Destinatário '{recipient}' não está na lista de contatos habituais")

    # Sinal 5: Horário incomum
    now_hour = datetime.now().hour
    usual_start, usual_end = profile.get("usual_hours", (8, 20))
    if not (usual_start <= now_hour <= usual_end):
        score += 10
        signals.append(f"Horário incomum de acesso ({now_hour}h, fora do padrão {usual_start}h–{usual_end}h)")

    # Nível de risco e atrito proporcional
    if score >= 60:
        level = "CRITICAL"   # Bloqueia + notifica contato de confiança
    elif score >= 35:
        level = "HIGH"       # Pausa de 2 min + confirmação extra
    elif score >= 20:
        level = "MEDIUM"     # Aviso + pede confirmação oral
    else:
        level = "LOW"

    return {"score": score, "level": level, "signals": signals}


# =============================================================================
# ESTADO DO GRAFO LANGGRAPH
# =============================================================================

class AgentState(TypedDict):
    # Input
    user_input: str
    image_context: Optional[str]
    session: Dict[str, Any]
    profile: Dict[str, Any]
    # Resultado do Orquestrador
    intent: str
    entities: Dict[str, Any]
    confidence: float
    # Resultado do agente especialista
    response: Optional[Dict[str, Any]]


# =============================================================================
# NÓS DO GRAFO (cada nó = um agente)
# =============================================================================

def node_orquestrador(state: AgentState) -> AgentState:
    """
    Agente Orquestrador: usa o LLM para classificar intenção e extrair entidades.
    Não executa nenhuma ação — apenas decide quem age.
    """
    history_text = "\n".join(
        f"- {m['role']}: {m['content']}"
        for m in state["session"]["history"][-4:]  # últimas 4 trocas
    ) or "Nenhum histórico ainda."

    prompt = f"""Você é o orquestrador de um assistente bancário do Banco do Brasil.
Analise o input do usuário e classifique a intenção.

user_input: "{state['user_input']}"
image_context: {state.get('image_context')}
histórico recente:
{history_text}

Responda SOMENTE com JSON válido no formato:
{{"intent": "PIX_TRANSFER|PAY_BILL|BLOCK_CARD|SCAM_RISK|PIX_DISAMBIGUATION|PIX_CONFIRM|HOME_NAVIGATION|CLARIFICATION_NEEDED", "entities": {{}}, "confidence": 0.0}}

Entidades relevantes por intenção:
- PIX_TRANSFER: amount (float), recipient_raw (string)
- PIX_CONFIRM: recipient (string), bank (string)
- PAY_BILL: bill_type (string)
- BLOCK_CARD: card_last4 (string)
- SCAM_RISK: trigger (string)
"""
    raw = call_llm(prompt)
    try:
        # Extrai o JSON mesmo que o LLM envolva com texto
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(json_match.group() if json_match else raw)
    except Exception:
        parsed = {"intent": "CLARIFICATION_NEEDED", "entities": {}, "confidence": 0.5}

    state["intent"] = parsed.get("intent", "CLARIFICATION_NEEDED")
    state["entities"] = parsed.get("entities", {})
    state["confidence"] = parsed.get("confidence", 0.9)
    return state


def _is_ambiguous_recipient(recipient_raw: Optional[str], known_contacts: List[str]) -> bool:
    """Retorna True se o destinatário bate com mais de um contato conhecido."""
    if not recipient_raw:
        return False
    matches = [c for c in known_contacts if recipient_raw.lower() in c.lower()]
    return len(matches) > 1


def node_operador_ui(state: AgentState) -> AgentState:
    """
    Agente OperadorUI: navega a interface, preenche formulários, desambigua contatos.
    """
    intent   = state["intent"]
    entities = state["entities"]
    profile  = state["profile"]

    # PIX_TRANSFER com destinatário ambíguo → trata como PIX_DISAMBIGUATION
    if intent == "PIX_TRANSFER":
        recipient_raw = entities.get("recipient_raw")
        known = profile.get("known_contacts", [])
        if _is_ambiguous_recipient(recipient_raw, known):
            intent = "PIX_DISAMBIGUATION"
            # Salva o valor para quando a desambiguação resolver
            if entities.get("amount"):
                state["session"]["last_amount"] = entities["amount"]

    if intent == "PIX_DISAMBIGUATION":
        # LLM identificou 'Pedro' mas sem sobrenome — desambigua
        state["response"] = {
            "metadata": {
                "active_agent": "OPERADOR_UI",
                "intent_detected": "PIX_TRANSFER",
                "confidence_score": state["confidence"],
            },
            "voice_assistant": {
                "tts_message": f"Abri o Pix e preenchi o valor. Mas você tem dois Pedros na agenda: Pedro Silva e Pedro Oliveira. Para qual deles?",
                "should_listen_next": True,
            },
            "ui_control": {
                "target_screen": "PIX_AREA",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"amount": entities.get("amount", 0), "recipient_name": "Pedro (qual?)"},
                "zero_ui_Dynamic_Component": {
                    "title": f"Qual Pedro você quer pagar?",
                    "subtitle": f"Valor: R$ {entities.get('amount', 0):.2f}".replace(".", ","),
                    "options": [
                        {"id": "p1", "label": "👤 PEDRO SILVA (Itaú)", "action_Command": "Pix para Pedro Silva"},
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
            "metadata": {"active_agent": "OPERADOR_UI", "intent_detected": "PIX_TRANSFER_READY", "confidence_score": state["confidence"]},
            "voice_assistant": {
                "tts_message": f"Prontinho! {recipient} selecionado, valor de R$ {amount:.0f}. Toque no botão verde para confirmar com digital.",
                "should_listen_next": False,
            },
            "ui_control": {
                "target_screen": "PIX_AREA",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"amount": amount, "recipient_name": recipient},
                "zero_ui_Dynamic_Component": {
                    "title": "Tudo pronto para enviar!",
                    "subtitle": f"Para: {recipient}",
                    "options": [],
                    "primary_confirm_button": {"label": f"✅ CONFIRMAR PIX DE R$ {amount:.0f} (BIOMETRIA)", "action_Command": "Confirmar envio do Pix"},
                },
            },
            "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
        }

    elif intent == "BLOCK_CARD":
        state["response"] = {
            "metadata": {"active_agent": "OPERADOR_UI", "intent_detected": "BLOCK_CARD", "confidence_score": state["confidence"]},
            "voice_assistant": {
                "tts_message": "Fique tranquila! Já abri a área do seu Ourocard final 4321. Toque no botão para bloquear agora.",
                "should_listen_next": False,
            },
            "ui_control": {
                "target_screen": "CARD_AREA",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"card_status": "PENDING_BLOCK"},
                "zero_ui_Dynamic_Component": {
                    "title": "🔒 Proteger seu Ourocard",
                    "subtitle": "Cartão Final 4321 — Bloqueio Instantâneo",
                    "options": [],
                    "primary_confirm_button": {"label": "BLOQUEAR MEU CARTÃO AGORA", "action_Command": "Confirmar bloqueio do cartão"},
                },
            },
            "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
        }

    elif intent == "HOME_NAVIGATION":
        state["response"] = _home_response()

    # Fallback: PIX_TRANSFER sem destinatário ou destinatário único claro
    if state["response"] is None and state["intent"] == "PIX_TRANSFER":
        recipient = entities.get("recipient_raw") or "destinatário"
        amount = entities.get("amount", 0.0) or 0.0
        state["response"] = {
            "metadata": {"active_agent": "OPERADOR_UI", "intent_detected": "PIX_TRANSFER", "confidence_score": state["confidence"]},
            "voice_assistant": {
                "tts_message": f"Abri a área do Pix. Para quem e qual valor você quer transferir?",
                "should_listen_next": True,
            },
            "ui_control": {
                "target_screen": "PIX_AREA",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"amount": amount or None, "recipient_name": recipient},
                "zero_ui_Dynamic_Component": {
                    "title": "Enviar Pix",
                    "subtitle": "Diga o nome de quem vai receber e o valor.",
                    "options": [],
                    "primary_confirm_button": None,
                },
            },
            "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
        }

    return state


def node_visao_multimodal(state: AgentState) -> AgentState:
    """
    Agente VisiãoMultimodal: recebe imagem (base64 ou flag) e extrai dados do boleto.
    Integração real: ibm/granite-vision ou gpt-4o-mini com a imagem em base64.
    Mock: retorna dados fixos do boleto de demo.
    """
    # TODO (produção): decodificar state["image_context"] de base64, enviar ao modelo de visão,
    # extrair {"valor": float, "beneficiario": str, "vencimento": str, "linha_digitavel": str}
    extracted = {
        "valor": 84.90,
        "beneficiario": "Companhia de Energia Elétrica",
        "vencimento": "Hoje",
        "linha_digitavel": "83640000000-8 84900132026-4",
        "source": "mock"  # muda para "granite-vision" quando integrado
    }

    state["response"] = {
        "metadata": {"active_agent": "VISAO_MULTIMODAL", "intent_detected": "PAY_BILL", "confidence_score": 0.97},
        "voice_assistant": {
            "tts_message": f"Li a conta de luz pela câmera. O valor é {extracted['valor']:.0f} reais e {int(extracted['valor'] % 1 * 100):02d} centavos para a {extracted['beneficiario']}, vencendo {extracted['vencimento']}. Toque no botão verde para confirmar.",
            "should_listen_next": False,
        },
        "ui_control": {
            "target_screen": "BOLETO_AREA",
            "ui_mode": "ZERO_UI_HIGH_CONTRAST",
            "form_state": {
                "amount": extracted["valor"],
                "recipient_name": extracted["beneficiario"],
                "barcode": extracted["linha_digitavel"],
            },
            "zero_ui_Dynamic_Component": {
                "title": "📷 Conta de Luz Lida",
                "subtitle": f"{extracted['beneficiario']} • Vence {extracted['vencimento']}",
                "options": [],
                "primary_confirm_button": {
                    "label": f"✅ PAGAR R$ {extracted['valor']:.2f}".replace(".", ","),
                    "action_Command": "Confirmar pagamento do boleto",
                },
            },
        },
        "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
    }
    return state


def node_guardiao_antigolpe(state: AgentState) -> AgentState:
    """
    Agente GuardiãoAntigolpe: avalia pontuação de risco multisinal.
    Aplica atrito PROPORCIONAL ao risco — não bloqueia tudo de forma paternalista.
    """
    risk = calculate_risk_score(
        state["user_input"],
        state["entities"],
        state["profile"],
        state["session"],
    )
    trusted = state["profile"].get("trusted_contact", {})
    signals_text = " | ".join(risk["signals"]) if risk["signals"] else "nenhum"

    if risk["level"] == "CRITICAL":
        state["response"] = {
            "metadata": {"active_agent": "GUARDIAO_ANTIGOLPE", "intent_detected": "SCAM_INTERVENTION", "confidence_score": 0.97},
            "voice_assistant": {
                "tts_message": f"Dona Maria, parei essa operação para proteger a senhora. Detectei {len(risk['signals'])} sinais de alerta: {', '.join(risk['signals'][:2])}. O Banco do Brasil nunca pede Pix para liberar benefício. Estou avisando o {trusted.get('name', 'seu contato de confiança')} agora.",
                "should_listen_next": False,
            },
            "ui_control": {
                "target_screen": "SECURITY_ALERT",
                "ui_mode": "ZERO_UI_EMERGENCY_LOCK",
                "form_state": {"amount": state["entities"].get("amount"), "recipient_name": state["entities"].get("recipient_raw", "Destinatário Desconhecido")},
                "zero_ui_Dynamic_Component": {
                    "title": "🛑 PROTEÇÃO ATIVADA",
                    "subtitle": f"Motivo: {signals_text[:120]}",
                    "options": [
                        {"id": "cancel", "label": "❌ CANCELAR OPERAÇÃO E VOLTAR", "action_Command": "Voltar ao início"},
                        {"id": "trusted", "label": f"📞 AVISAR {trusted.get('name', 'CONTATO SEGURO').upper()}", "action_Command": "Avisar contato de confiança"},
                    ],
                    "primary_confirm_button": None,
                },
            },
            "security_guardian": {
                "risk_level": "CRITICAL",
                "is_blocked": True,
                "scam_explanation": f"Score de risco: {risk['score']}/100. Sinais: {signals_text}",
                "trusted_contact_alert": True,
                "trusted_contact": trusted,
            },
        }

    elif risk["level"] == "HIGH":
        # Atrito gradual: avisa mas não bloqueia totalmente
        state["response"] = {
            "metadata": {"active_agent": "GUARDIAO_ANTIGOLPE", "intent_detected": "RISK_WARNING", "confidence_score": 0.85},
            "voice_assistant": {
                "tts_message": f"Dona Maria, antes de continuar: {risk['signals'][0]}. Tem certeza que quer fazer isso agora?",
                "should_listen_next": True,
            },
            "ui_control": {
                "target_screen": "SECURITY_ALERT",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {"amount": state["entities"].get("amount")},
                "zero_ui_Dynamic_Component": {
                    "title": "⚠️ Confirmação Extra",
                    "subtitle": f"Atenção: {risk['signals'][0]}",
                    "options": [
                        {"id": "confirm", "label": "✅ SIM, QUERO CONTINUAR", "action_Command": state["user_input"] + " confirmado"},
                        {"id": "cancel", "label": "❌ NÃO, CANCELAR", "action_Command": "Voltar ao início"},
                    ],
                    "primary_confirm_button": None,
                },
            },
            "security_guardian": {
                "risk_level": "HIGH",
                "is_blocked": False,
                "scam_explanation": f"Score: {risk['score']}/100. Sinais: {signals_text}",
                "trusted_contact_alert": False,
            },
        }

    return state


def node_esclarecimento(state: AgentState) -> AgentState:
    """
    Agente de Esclarecimento: em vez de voltar para HOME silenciosamente,
    pergunta o que o usuário queria dizer.
    """
    state["response"] = {
        "metadata": {"active_agent": "ORQUESTRADOR", "intent_detected": "CLARIFICATION_NEEDED", "confidence_score": 0.5},
        "voice_assistant": {
            "tts_message": "Não entendi bem o que a senhora precisa. Posso ajudar com Pix, pagamento de conta, bloqueio de cartão ou outras dúvidas. O que você gostaria?",
            "should_listen_next": True,
        },
        "ui_control": {
            "target_screen": "HOME",
            "ui_mode": "ZERO_UI_HIGH_CONTRAST",
            "form_state": {},
            "zero_ui_Dynamic_Component": {
                "title": "Como posso ajudar?",
                "subtitle": "Escolha uma opção ou fale comigo:",
                "options": [
                    {"id": "pix",    "label": "💠 FAZER UM PIX",           "action_Command": "Quero fazer um Pix"},
                    {"id": "boleto", "label": "📄 PAGAR UMA CONTA",        "action_Command": "Quero pagar uma conta"},
                    {"id": "cartao", "label": "💳 BLOQUEAR MEU CARTÃO",    "action_Command": "Preciso bloquear meu cartão"},
                    {"id": "humano", "label": "👤 FALAR COM ATENDENTE",    "action_Command": "Falar com atendente humano"},
                ],
                "primary_confirm_button": None,
            },
        },
        "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
    }
    return state


def node_home(state: AgentState) -> AgentState:
    state["response"] = _home_response()
    return state


def _home_response() -> Dict[str, Any]:
    return {
        "metadata": {"active_agent": "ORQUESTRADOR", "intent_detected": "HOME_NAVIGATION", "confidence_score": 1.0},
        "voice_assistant": {
            "tts_message": "Pronto! Voltamos para a tela inicial. Como posso ajudar agora?",
            "should_listen_next": False,
        },
        "ui_control": {
            "target_screen": "HOME",
            "ui_mode": "STANDARD",
            "form_state": {"amount": None, "recipient_name": None, "card_status": "ACTIVE"},
            "zero_ui_Dynamic_Component": None,
        },
        "security_guardian": {"risk_level": "LOW", "is_blocked": False, "scam_explanation": None, "trusted_contact_alert": False},
    }


# =============================================================================
# ROTEADOR: o Orquestrador decide qual agente especialista aciona
# =============================================================================

def route_intent(state: AgentState) -> Literal[
    "operador_ui", "visao_multimodal", "guardiao_antigolpe", "esclarecimento", "home"
]:
    intent = state["intent"]
    image  = state.get("image_context")

    # Imagem sempre vai para visão multimodal
    if image and image.startswith("FOTO"):
        return "visao_multimodal"

    # Avalia risco antes de deixar o operador agir em operações financeiras
    if intent in ("PIX_TRANSFER", "PIX_CONFIRM"):
        risk = calculate_risk_score(state["user_input"], state["entities"], state["profile"], state["session"])
        if risk["level"] in ("CRITICAL", "HIGH"):
            state["intent"] = "SCAM_RISK"  # redireciona para o guardião
            return "guardiao_antigolpe"

    routing = {
        "PIX_TRANSFER":        "operador_ui",
        "PIX_DISAMBIGUATION":  "operador_ui",
        "PIX_CONFIRM":         "operador_ui",
        "BLOCK_CARD":          "operador_ui",
        "PAY_BILL":            "visao_multimodal",
        "SCAM_RISK":           "guardiao_antigolpe",
        "HOME_NAVIGATION":     "home",
        "CLARIFICATION_NEEDED": "esclarecimento",
    }
    return routing.get(intent, "esclarecimento")


# =============================================================================
# CONSTRUÇÃO DO GRAFO LANGGRAPH
# =============================================================================

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("orquestrador",      node_orquestrador)
    g.add_node("operador_ui",       node_operador_ui)
    g.add_node("visao_multimodal",  node_visao_multimodal)
    g.add_node("guardiao_antigolpe",node_guardiao_antigolpe)
    g.add_node("esclarecimento",    node_esclarecimento)
    g.add_node("home",              node_home)

    g.set_entry_point("orquestrador")

    g.add_conditional_edges(
        "orquestrador",
        route_intent,
        {
            "operador_ui":        "operador_ui",
            "visao_multimodal":   "visao_multimodal",
            "guardiao_antigolpe": "guardiao_antigolpe",
            "esclarecimento":     "esclarecimento",
            "home":               "home",
        },
    )

    for node in ("operador_ui", "visao_multimodal", "guardiao_antigolpe", "esclarecimento", "home"):
        g.add_edge(node, END)

    return g.compile()


_graph = build_graph()


# =============================================================================
# ENDPOINT PRINCIPAL
# =============================================================================

@app.post("/api/agent/interact")
async def interact(req: UserRequest) -> Dict[str, Any]:
    session = get_session(req.session_id)
    profile = req.user_profile or DEFAULT_PROFILE

    # Atualiza histórico
    session["history"].append({"role": "user", "content": req.user_input})

    initial_state: AgentState = {
        "user_input":    req.user_input,
        "image_context": req.image_context,
        "session":       session,
        "profile":       profile,
        "intent":        "",
        "entities":      {},
        "confidence":    0.0,
        "response":      None,
    }

    final_state = _graph.invoke(initial_state)

    response = final_state["response"]

    # Atualiza histórico com resposta do agente
    session["history"].append({
        "role": "assistant",
        "content": response["voice_assistant"]["tts_message"],
    })
    # Persiste último valor para desambiguações encadeadas
    if final_state["entities"].get("amount"):
        session["last_amount"] = final_state["entities"]["amount"]
    session["last_intent"] = final_state["intent"]

    return response


@app.get("/api/session/{session_id}")
async def get_session_debug(session_id: str):
    """Endpoint de debug — mostra o estado da sessão (remove em produção)."""
    return _sessions.get(session_id, {})


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    """Limpa a sessão (útil para demo resetar o estado)."""
    _sessions.pop(session_id, None)
    return {"cleared": True}
