# arquivo: backend_main.py
# Instalar dependências: pip install fastapi uvicorn pydantic
# Executar com: uvicorn backend_main:app --reload --port 8000

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

app = FastAPI(title="Assistente Caramelo BB - Multi-Agent Backend")

# Permite conexão com o Frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserRequest(BaseModel):
    user_input: str
    current_screen: str = "HOME"
    image_context: Optional[str] = None  # Ex: "FOTO_CONTA_LUZ" ou "FOTO_PLACA_FEIRA"

@app.post("/api/agent/interact")
async def interact_with_agents(req: UserRequest) -> Dict[str, Any]:
    """
    Endpoint central que recebe a fala/ação do usuário ou imagem da câmera
    e retorna o Contrato JSON que transforma a interface React.
    """
    text = req.user_input.lower()

    # =========================================================================
    # CASO 1: AGENTE DE VISÃO MULTIMODAL (Leitura de Imagem / Câmera)
    # =========================================================================
    if req.image_context == "FOTO_CONTA_LUZ" or "conta de luz" in text or "boleto" in text:
        return {
            "metadata": {
                "active_agent": "VISAO_MULTIMODAL",
                "intent_detected": "PAY_BILL",
                "confidence_score": 0.99
            },
            "voice_assistant": {
                "tts_message": "Li a sua conta de luz pela câmera. O valor é 84 reais e 90 centavos para a Companhia de Energia, vencendo hoje. Já deixei tudo pronto na tela. Toque no botão verde gigante para confirmar.",
                "should_listen_next": False
            },
            "ui_control": {
                "target_screen": "BOLETO_AREA",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {
                    "amount": 84.90,
                    "recipient_name": "Companhia de Energia Elétrica",
                    "recipient_key": None,
                    "barcode": "83640000000-8 84900132026-4",
                    "card_status": "ACTIVE"
                },
                "zero_ui_Dynamic_Component": {
                    "title": "Conta de Luz Lida pela Câmera",
                    "subtitle": "Companhia de Energia • Vence Hoje",
                    "options": [],
                    "primary_confirm_button": {
                        "label": "CONFIRMAR PAGAMENTO DE R$ 84,90",
                        "action_Command": "Confirmar pagamento da conta"
                    }
                }
            },
            "security_guardian": {
                "risk_level": "LOW",
                "is_blocked": False,
                "scam_explanation": None,
                "trusted_contact_alert": False
            }
        }

    # =========================================================================
    # CASO 2: AGENTE GUARDIÃO COGNITIVO (Detecção de Golpe / Engenharia Social)
    # =========================================================================
    scam_keywords = ["inss", "benefício bloqueado", "liberar benefício", "urgente", "falso funcionário", "2000", "dois mil"]
    if any(k in text for k in scam_keywords):
        return {
            "metadata": {
                "active_agent": "GUARDIAO_ANTIGOLPE",
                "intent_detected": "SCAM_INTERVENTION",
                "confidence_score": 0.99
            },
            "voice_assistant": {
                "tts_message": "Dona Maria, parei essa transferência para proteger a senhora. O INSS e o Banco do Brasil nunca pedem Pix para liberar benefício bloqueado. Isso tem características de um golpe. Eu travei a tela por segurança.",
                "should_listen_next": False
            },
            "ui_control": {
                "target_screen": "SECURITY_ALERT",
                "ui_mode": "ZERO_UI_EMERGENCY_LOCK",
                "form_state": {
                    "amount": 2000.00,
                    "recipient_name": "Chave Desconhecida (Suspeita)",
                    "recipient_key": "000.111.222-33",
                    "barcode": None,
                    "card_status": "ACTIVE"
                },
                "zero_ui_Dynamic_Component": {
                    "title": "⚠️ PROTEÇÃO ATIVADA: POSSÍVEL GOLPE",
                    "subtitle": "O INSS e o Banco do Brasil NUNCA cobram taxas via Pix para liberar aposentadoria ou benefícios.",
                    "options": [
                        {
                            "id": "cancel_op",
                            "label": "❌ CANCELAR TUDO E VOLTAR EM SEGURANÇA",
                            "action_Command": "Voltar para o início"
                        },
                        {
                            "id": "call_family",
                            "label": "📞 AVISAR MEU FILHO (CONTATO DE CONFIANÇA)",
                            "action_Command": "Avisar contato de confiança"
                        }
                    ],
                    "primary_confirm_button": None
                }
            },
            "security_guardian": {
                "risk_level": "CRITICAL",
                "is_blocked": True,
                "scam_explanation": "Padrão de Engenharia Social detectado: Falsa urgência previdenciária + Destinatário fora da lista habitual + Valor atípico.",
                "trusted_contact_alert": True
            }
        }

    # =========================================================================
    # CASO 3: NAVEGAÇÃO AUTÔNOMA PIX COM DESAMBIGUAÇÃO ("Pix de 50 pro Pedro")
    # =========================================================================
    if "pedro" in text and "silva" not in text and "oliveira" not in text:
        return {
            "metadata": {
                "active_agent": "OPERADOR_UI",
                "intent_detected": "PIX_TRANSFER",
                "confidence_score": 0.96
            },
            "voice_assistant": {
                "tts_message": "Abri a área do Pix e já preenchi 50 reais. Mas vi que você tem dois Pedros na sua agenda: Pedro Silva e Pedro Oliveira. Qual dos dois você quer escolher?",
                "should_listen_next": True
            },
            "ui_control": {
                "target_screen": "PIX_AREA",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {
                    "amount": 50.00,
                    "recipient_name": "Pedro (Ambíguo)",
                    "recipient_key": None,
                    "barcode": None,
                    "card_status": "ACTIVE"
                },
                "zero_ui_Dynamic_Component": {
                    "title": "Enviar R$ 50,00 para qual Pedro?",
                    "subtitle": "Simplificamos a tela para você escolher com facilidade:",
                    "options": [
                        {
                            "id": "pedro_1",
                            "label": "👤 PEDRO SILVA (Banco Itaú)",
                            "action_Command": "Faz o Pix de 50 reais para o Pedro Silva"
                        },
                        {
                            "id": "pedro_2",
                            "label": "👤 PEDRO OLIVEIRA (Banco do Brasil)",
                            "action_Command": "Faz o Pix de 50 reais para o Pedro Oliveira"
                        }
                    ],
                    "primary_confirm_button": None
                }
            },
            "security_guardian": {
                "risk_level": "LOW",
                "is_blocked": False,
                "scam_explanation": None,
                "trusted_contact_alert": False
            }
        }

    # =========================================================================
    # CASO 4: RESOLUÇÃO DO PIX ("Pedro Silva")
    # =========================================================================
    if "pedro silva" in text:
        return {
            "metadata": {
                "active_agent": "OPERADOR_UI",
                "intent_detected": "PIX_TRANSFER",
                "confidence_score": 0.99
            },
            "voice_assistant": {
                "tts_message": "Perfeito! Selecionado Pedro Silva do banco Itaú, valor de 50 reais. Agora é só tocar no botão verde gigante na tela para enviar o Pix.",
                "should_listen_next": False
            },
            "ui_control": {
                "target_screen": "PIX_AREA",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {
                    "amount": 50.00,
                    "recipient_name": "Pedro Silva (Itaú)",
                    "recipient_key": "pedro.silva@email.com",
                    "barcode": None,
                    "card_status": "ACTIVE"
                },
                "zero_ui_Dynamic_Component": {
                    "title": "Revisão do seu Pix",
                    "subtitle": "Destinatário: Pedro Silva (Itaú)",
                    "options": [],
                    "primary_confirm_button": {
                        "label": "✅ ENVIAR R$ 50,00 AGORA (BIOMETRIA)",
                        "action_Command": "Confirmar envio do Pix"
                    }
                }
            },
            "security_guardian": {
                "risk_level": "LOW",
                "is_blocked": False,
                "scam_explanation": None,
                "trusted_contact_alert": False
            }
        }

    # =========================================================================
    # CASO 5: INTENÇÃO LEIGA ("Perdi meu cartão no ônibus")
    # =========================================================================
    if "cartão" in text or "perdi" in text or "ônibus" in text:
        return {
            "metadata": {
                "active_agent": "OPERADOR_UI",
                "intent_detected": "BLOCK_CARD",
                "confidence_score": 0.97
            },
            "voice_assistant": {
                "tts_message": "Não se preocupe, Dona Maria! Já abri a tela de segurança do seu cartão Ourocard final 4321. Toque no botão amarelo gigante para bloquear ele temporariamente agora mesmo.",
                "should_listen_next": False
            },
            "ui_control": {
                "target_screen": "CARD_AREA",
                "ui_mode": "ZERO_UI_HIGH_CONTRAST",
                "form_state": {
                    "amount": None,
                    "recipient_name": None,
                    "recipient_key": None,
                    "barcode": None,
                    "card_status": "PENDING_BLOCK"
                },
                "zero_ui_Dynamic_Component": {
                    "title": "Proteger seu Cartão Ourocard",
                    "subtitle": "Cartão Final 4321 • Bloqueio Temporário Instantâneo",
                    "options": [],
                    "primary_confirm_button": {
                        "label": "🔒 BLOQUEAR MEU CARTÃO AGORA",
                        "action_Command": "Confirmar bloqueio do cartão"
                    }
                }
            },
            "security_guardian": {
                "risk_level": "LOW",
                "is_blocked": False,
                "scam_explanation": None,
                "trusted_contact_alert": False
            }
        }

    # =========================================================================
    # RETORNO AO INÍCIO / CONFIRMAÇÃO DE SUCESSO
    # =========================================================================
    return {
        "metadata": {
            "active_agent": "ORQUESTRADOR",
            "intent_detected": "HOME_NAVIGATION",
            "confidence_score": 1.0
        },
        "voice_assistant": {
            "tts_message": "Operação concluída com sucesso! Voltamos para a tela inicial do Banco do Brasil. Como posso ajudar você agora?",
            "should_listen_next": False
        },
        "ui_control": {
            "target_screen": "HOME",
            "ui_mode": "STANDARD",
            "form_state": {
                "amount": None,
                "recipient_name": None,
                "recipient_key": None,
                "barcode": None,
                "card_status": "ACTIVE"
            },
            "zero_ui_Dynamic_Component": None
        },
        "security_guardian": {
            "risk_level": "LOW",
            "is_blocked": False,
            "scam_explanation": None,
            "trusted_contact_alert": False
        }
    }
