// arquivo: src/App.jsx
import React, { useState, useEffect } from 'react';
import MascoteAvatar from './MascoteAvatar';

export default function AssistenteCarameloApp() {
  // Estado global controlado pelo JSON dos Agentes
  const [agentState, setAgentState] = useState({
    metadata: {
      active_agent: "ORQUESTRADOR",
      intent_detected: "IDLE",
      confidence_score: 1.0
    },
    voice_assistant: {
      tts_message: "Olá, Dona Maria! Sou o Assistente Caramelo do Banco do Brasil. Você pode falar comigo ou mostrar uma conta pela câmera.",
      should_listen_next: false
    },
    ui_control: {
      target_screen: "HOME",
      ui_mode: "STANDARD", // STANDARD | ZERO_UI_HIGH_CONTRAST | ZERO_UI_EMERGENCY_LOCK
      form_state: {
        amount: null,
        recipient_name: null,
        recipient_key: null,
        barcode: null,
        card_status: "ACTIVE"
      },
      zero_ui_Dynamic_Component: null
    },
    security_guardian: {
      risk_level: "LOW",
      is_blocked: false,
      scam_explanation: null,
      trusted_contact_alert: false
    }
  });

  const [userInput, setUserInput] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(true);

  // Dispara Síntese de Voz (Text-to-Speech) nativa do navegador sempre que a mensagem mudar
  useEffect(() => {
    if (ttsEnabled && 'speechSynthesis' in window && agentState.voice_assistant.tts_message) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(agentState.voice_assistant.tts_message);
      utterance.lang = 'pt-BR';
      utterance.rate = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  }, [agentState.voice_assistant.tts_message, ttsEnabled]);

  // Motor local de resposta (Espelha o backend Python para rodar standalone se necessário)
  const triggerAgentOrchestrator = (commandText, imageContext = null) => {
    const text = commandText.toLowerCase();
    let newState = null;

    if (imageContext === "FOTO_CONTA_LUZ" || text.includes("conta de luz") || text.includes("câmera")) {
      newState = {
        metadata: { active_agent: "VISAO_MULTIMODAL", intent_detected: "PAY_BILL", confidence_score: 0.99 },
        voice_assistant: {
          tts_message: "Li a sua conta de luz pela câmera. O valor é 84 reais e 90 centavos para a Companhia de Energia. Já deixei tudo preenchido. Toque no botão verde gigante para confirmar.",
          should_listen_next: false
        },
        ui_control: {
          target_screen: "BOLETO_AREA",
          ui_mode: "ZERO_UI_HIGH_CONTRAST",
          form_state: { amount: 84.90, recipient_name: "Companhia de Energia Elétrica", barcode: "83640000000-8 84900132026-4" },
          zero_ui_Dynamic_Component: {
            title: "📷 Conta de Luz Identificada",
            subtitle: "Companhia de Energia • Vencimento Hoje",
            options: [],
            primary_confirm_button: {
              label: "✅ PAGAR R$ 84,90 AGORA",
              action_Command: "Confirmar pagamento"
            }
          }
        },
        security_guardian: { risk_level: "LOW", is_blocked: false, scam_explanation: null }
      };
    } else if (text.includes("inss") || text.includes("benefício") || text.includes("2 mil") || text.includes("bloqueado")) {
      newState = {
        metadata: { active_agent: "GUARDIAO_ANTIGOLPE", intent_detected: "SCAM_INTERVENTION", confidence_score: 0.99 },
        voice_assistant: {
          tts_message: "Atenção, Dona Maria! Parei essa transferência para proteger a senhora. O INSS e o Banco do Brasil nunca pedem Pix para liberar benefício bloqueado. Isso parece um golpe.",
          should_listen_next: false
        },
        ui_control: {
          target_screen: "SECURITY_ALERT",
          ui_mode: "ZERO_UI_EMERGENCY_LOCK",
          form_state: { amount: 2000.00, recipient_name: "Chave Desconhecida (Suspeita)" },
          zero_ui_Dynamic_Component: {
            title: "🛑 ALERTA DE GOLPE DETECTADO",
            subtitle: "O INSS e o Banco do Brasil NUNCA pedem dinheiro ou Pix para desbloquear aposentadoria.",
            options: [
              { id: "1", label: "❌ CANCELAR OPERAÇÃO E SAIR", action_Command: "Voltar ao início" },
              { id: "2", label: "📞 LIGAR PARA MEU FILHO (CONTATO SEGURO)", action_Command: "Voltar ao início" }
            ],
            primary_confirm_button: null
          }
        },
        security_guardian: {
          risk_level: "CRITICAL",
          is_blocked: true,
          scam_explanation: "Padrão de Engenharia Social: Urgência falsa + menção a bloqueio de benefício + valor alto atípico."
        }
      };
    } else if (text.includes("pedro") && !text.includes("silva") && !text.includes("oliveira")) {
      newState = {
        metadata: { active_agent: "OPERADOR_UI", intent_detected: "PIX_TRANSFER", confidence_score: 0.96 },
        voice_assistant: {
          tts_message: "Abri o Pix e já preenchi 50 reais. Mas você tem dois Pedros nos seus contatos: Pedro Silva e Pedro Oliveira. Para qual deles você quer mandar?",
          should_listen_next: true
        },
        ui_control: {
          target_screen: "PIX_AREA",
          ui_mode: "ZERO_UI_HIGH_CONTRAST",
          form_state: { amount: 50.00, recipient_name: "Pedro (Escolher contato)" },
          zero_ui_Dynamic_Component: {
            title: "Qual é o Pedro correto?",
            subtitle: "Valor já preenchido: R$ 50,00",
            options: [
              { id: "p1", label: "👤 PEDRO SILVA (Banco Itaú)", action_Command: "Faz o Pix de 50 reais para o Pedro Silva" },
              { id: "p2", label: "👤 PEDRO OLIVEIRA (Banco do Brasil)", action_Command: "Faz o Pix de 50 reais para o Pedro Oliveira" }
            ],
            primary_confirm_button: null
          }
        },
        security_guardian: { risk_level: "LOW", is_blocked: false, scam_explanation: null }
      };
    } else if (text.includes("pedro silva") || text.includes("pedro oliveira")) {
      const chosen = text.includes("silva") ? "Pedro Silva (Itaú)" : "Pedro Oliveira (BB)";
      newState = {
        metadata: { active_agent: "OPERADOR_UI", intent_detected: "PIX_TRANSFER_READY", confidence_score: 0.99 },
        voice_assistant: {
          tts_message: `Prontinho! Selecionado ${chosen}, no valor de 50 reais. Toque no botão verde gigante para confirmar com sua digital.`,
          should_listen_next: false
        },
        ui_control: {
          target_screen: "PIX_AREA",
          ui_mode: "ZERO_UI_HIGH_CONTRAST",
          form_state: { amount: 50.00, recipient_name: chosen },
          zero_ui_Dynamic_Component: {
            title: "Tudo pronto para enviar!",
            subtitle: `Para: ${chosen}`,
            options: [],
            primary_confirm_button: {
              label: "✅ CONFIRMAR PIX DE R$ 50,00",
              action_Command: "Confirmar envio"
            }
          }
        },
        security_guardian: { risk_level: "LOW", is_blocked: false, scam_explanation: null }
      };
    } else if (text.includes("cartão") || text.includes("perdi") || text.includes("ônibus")) {
      newState = {
        metadata: { active_agent: "OPERADOR_UI", intent_detected: "BLOCK_CARD", confidence_score: 0.98 },
        voice_assistant: {
          tts_message: "Fique tranquila! Já fui direto para a área do seu cartão Ourocard final 4321. Toque no botão gigante abaixo para bloquear ele agora mesmo.",
          should_listen_next: false
        },
        ui_control: {
          target_screen: "CARD_AREA",
          ui_mode: "ZERO_UI_HIGH_CONTRAST",
          form_state: { card_status: "PENDING_BLOCK" },
          zero_ui_Dynamic_Component: {
            title: "🔒 Bloqueio Rápido de Cartão",
            subtitle: "Ourocard Final 4321 • Proteção imediata",
            options: [],
            primary_confirm_button: {
              label: "BLOQUEAR MEU CARTÃO AGORA",
              action_Command: "Confirmar bloqueio"
            }
          }
        },
        security_guardian: { risk_level: "LOW", is_blocked: false, scam_explanation: null }
      };
    } else {
      newState = {
        metadata: { active_agent: "ORQUESTRADOR", intent_detected: "COMPLETED_OR_HOME", confidence_score: 1.0 },
        voice_assistant: {
          tts_message: "Pronto, operação realizada com sucesso! Voltamos para a tela inicial do aplicativo.",
          should_listen_next: false
        },
        ui_control: {
          target_screen: "HOME",
          ui_mode: "STANDARD",
          form_state: { amount: null, recipient_name: null },
          zero_ui_Dynamic_Component: null
        },
        security_guardian: { risk_level: "LOW", is_blocked: false, scam_explanation: null }
      };
    }

    setAgentState(newState);
    setUserInput("");
  };

  // Reconhecimento de Voz Nativo (Web Speech API)
  const startVoiceCapture = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Seu navegador não suporta Web Speech API nativa. Use os botões de simulação ao lado ou o campo de texto!");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    setIsListening(true);
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setUserInput(transcript);
      setIsListening(false);
      triggerAgentOrchestrator(transcript);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.start();
  };

  const { ui_control, voice_assistant, metadata, security_guardian } = agentState;

  // Deriva o mood do mascote a partir do estado atual
  const mascoteMood = (() => {
    if (isListening) return 'listening';
    const agent = metadata.active_agent;
    const intent = metadata.intent_detected;
    if (agent === 'GUARDIAO_ANTIGOLPE')  return 'GUARDIAO_ANTIGOLPE';
    if (agent === 'VISAO_MULTIMODAL')    return 'VISAO_MULTIMODAL';
    if (intent === 'PIX_TRANSFER_READY') return 'PIX_TRANSFER_READY';
    if (intent === 'COMPLETED_OR_HOME')  return 'COMPLETED_OR_HOME';
    if (intent === 'PIX_TRANSFER')       return 'PIX_TRANSFER';
    if (intent === 'BLOCK_CARD')         return 'BLOCK_CARD';
    if (intent === 'SCAM_INTERVENTION')  return 'SCAM_INTERVENTION';
    if (intent === 'PAY_BILL')           return 'PAY_BILL';
    if (agent === 'OPERADOR_UI')         return 'OPERADOR_UI';
    return 'idle';
  })();

  return (
    <div className="min-h-screen bg-slate-900 text-white p-4 md:p-8 flex flex-col lg:flex-row gap-8 items-center justify-center font-sans">
      
      {/* ===================================================================
          COLUNA 1: CELULAR MOCK DO BANCO DO BRASIL (INTERFACE CAMALEÃO)
          =================================================================== */}
      <div className="w-[380px] h-[760px] bg-white text-slate-900 rounded-[42px] border-[10px] border-slate-800 shadow-2xl overflow-hidden flex flex-col relative">
        
        {/* Topo do App BB */}
        <div className="bg-[#F8D117] text-[#0038A8] px-5 pt-6 pb-4 flex items-center justify-between font-bold shadow-sm">
          <div>
            <p className="text-xs uppercase tracking-wider opacity-80">Banco do Brasil</p>
            <h1 className="text-lg font-extrabold">Olá, Dona Maria</h1>
          </div>
          <span className="text-xs px-2.5 py-1 rounded-full bg-[#0038A8] text-white font-semibold">
            {ui_control.ui_mode === "STANDARD" ? "UI Padrão" : "🦎 Zero-UI Ativa"}
          </span>
        </div>

        {/* Barra do Assistente de Voz (Sempre visível para guiar) */}
        <div className={`px-4 py-3 border-b flex items-start gap-3 transition-colors duration-300 ${
          security_guardian.is_blocked ? "bg-red-900 text-white" : "bg-[#0038A8] text-white"
        }`}>
          {/* ZONA 1: mascote pequeno (40px) substitui o avatar "BB" */}
          <MascoteAvatar
            mood={mascoteMood}
            size={40}
            className={security_guardian.is_blocked
              ? 'mascote-alert'
              : (mascoteMood === 'parado' || mascoteMood === 'feliz') ? 'mascote-bounce' : ''}
          />
          <div className="text-xs leading-relaxed">
            <span className="font-bold text-[#F8D117] block mb-0.5">
              Agente Ativo: {metadata.active_agent}
            </span>
            "{voice_assistant.tts_message}"
          </div>
        </div>

        {/* CORPO PRINCIPAL DO APLICATIVO (ALTERNA ENTRE PADRÃO E CAMALEÃO ZERO-UI) */}
        <div className="flex-1 overflow-y-auto flex flex-col justify-between">
          
          {/* MODO 1: INTERFACE PADRÃO DO BANCO DO BRASIL (Cheia de menus tradicionais) */}
          {ui_control.ui_mode === "STANDARD" && (
            <div className="p-4 space-y-4">
              {/* Card de Saldo */}
              <div className="bg-slate-100 p-4 rounded-xl border border-slate-200">
                <p className="text-xs text-slate-500">Saldo disponível em conta</p>
                <p className="text-2xl font-extrabold text-[#0038A8] mt-1">R$ 1.450,00</p>
              </div>

              {/* Grade de Ícones Tradicionais (Difícil para baixa visão/idosos) */}
              <div>
                <p className="text-xs font-bold text-slate-400 uppercase mb-2">Serviços do Aplicativo</p>
                <div className="grid grid-cols-3 gap-2.5 text-center">
                  {[
                    { icon: "💠", name: "Área Pix" },
                    { icon: "📄", name: "Pagar Boleto" },
                    { icon: "💳", name: "Cartões" },
                    { icon: "📊", name: "Extrato" },
                    { icon: "💰", name: "Empréstimo" },
                    { icon: "📈", name: "Investir" },
                    { icon: "🛡️", name: "Seguros" },
                    { icon: "👵", name: "INSS" },
                    { icon: "⚙️", name: "Ajustes" }
                  ].map((item, idx) => (
                    <div key={idx} className="bg-slate-50 border border-slate-200 p-3 rounded-xl flex flex-col items-center justify-center gap-1 opacity-85">
                      <span className="text-xl">{item.icon}</span>
                      <span className="text-[11px] font-medium text-slate-700">{item.name}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 p-3 rounded-xl text-xs text-blue-900">
                💡 <strong>Dica:</strong> Em vez de procurar nos botões acima, aperte o microfone abaixo e diga o que precisa!
              </div>
            </div>
          )}

          {/* MODO 2: INTERFACE CAMALEÃO ZERO-UI (Alto Contraste, Foco Único, Sem Poluição) */}
          {ui_control.ui_mode === "ZERO_UI_HIGH_CONTRAST" && ui_control.zero_ui_Dynamic_Component && (
            <div className="flex-1 bg-slate-950 text-white p-5 flex flex-col justify-between">
              <div>
                <span className="inline-block bg-[#F8D117] text-black text-xs font-extrabold px-3 py-1 rounded-full uppercase mb-3">
                  Modo Acessibilidade Caramelo
                </span>
                <h2 className="text-2xl font-extrabold text-[#F8D117] leading-tight">
                  {ui_control.zero_ui_Dynamic_Component.title}
                </h2>
                <p className="text-base text-slate-200 mt-1 font-medium">
                  {ui_control.zero_ui_Dynamic_Component.subtitle}
                </p>

                {/* Resumo dos dados preenchidos automaticamente pelo Agente */}
                {ui_control.form_state.amount && (
                  <div className="mt-4 bg-slate-900 border-2 border-[#F8D117] rounded-2xl p-4">
                    <p className="text-xs text-slate-300 uppercase">Valor Preenchido pela IA:</p>
                    <p className="text-3xl font-black text-white">
                      R$ {ui_control.form_state.amount.toFixed(2).replace('.', ',')}
                    </p>
                  </div>
                )}
              </div>

              {/* Botões Gigantes de Desambiguação ou Confirmação */}
              <div className="space-y-3 my-4">
                {ui_control.zero_ui_Dynamic_Component.options.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => triggerAgentOrchestrator(opt.action_Command)}
                    className="w-full py-5 px-4 bg-[#F8D117] hover:bg-yellow-300 text-slate-950 font-black text-lg rounded-2xl shadow-lg text-left flex items-center justify-between transition transform active:scale-95"
                  >
                    <span>{opt.label}</span>
                    <span className="text-2xl">➔</span>
                  </button>
                ))}

                {ui_control.zero_ui_Dynamic_Component.primary_confirm_button && (
                  <button
                    onClick={() => triggerAgentOrchestrator(ui_control.zero_ui_Dynamic_Component.primary_confirm_button.action_Command)}
                    className="w-full py-6 px-4 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xl rounded-2xl shadow-xl text-center transition transform active:scale-95"
                  >
                    {ui_control.zero_ui_Dynamic_Component.primary_confirm_button.label}
                  </button>
                )}

                <button
                  onClick={() => triggerAgentOrchestrator("Voltar ao início")}
                  className="w-full py-3 bg-slate-800 text-slate-200 font-bold text-sm rounded-xl border border-slate-700"
                >
                  Cancelar e Voltar ao Início
                </button>
              </div>
            </div>
          )}

          {/* MODO 3: BLOQUEIO PREVENTIVO ANTIGOLPE (Guardião Cognitivo) */}
          {ui_control.ui_mode === "ZERO_UI_EMERGENCY_LOCK" && ui_control.zero_ui_Dynamic_Component && (
            <div className="flex-1 bg-red-950 text-white p-5 flex flex-col justify-between border-4 border-red-500">
              <div>
                {/* Mascote pulsando no modo alerta */}
                <div className="flex justify-center mb-3">
                  <MascoteAvatar mood="GUARDIAO_ANTIGOLPE" size={90} className="mascote-alert" />
                </div>
                <span className="inline-block bg-red-500 text-white text-xs font-black px-3 py-1 rounded-full uppercase mb-3">
                  🛡️ Guardião Antigolpe BB
                </span>
                <h2 className="text-2xl font-black text-yellow-300 leading-tight">
                  {ui_control.zero_ui_Dynamic_Component.title}
                </h2>
                <p className="text-base text-white mt-3 bg-red-900/80 p-3 rounded-xl border border-red-400 leading-relaxed">
                  {ui_control.zero_ui_Dynamic_Component.subtitle}
                </p>
              </div>

              <div className="space-y-3 my-4">
                {ui_control.zero_ui_Dynamic_Component.options.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => triggerAgentOrchestrator(opt.action_Command)}
                    className="w-full py-5 px-4 bg-yellow-400 hover:bg-yellow-300 text-slate-950 font-black text-base rounded-2xl shadow-lg text-center"
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ZONA 2: mascote flutuante no canto inferior direito (apenas em STANDARD e ZERO_UI_HIGH_CONTRAST) */}
          {ui_control.ui_mode !== "ZERO_UI_EMERGENCY_LOCK" && (
            <div className="absolute bottom-20 right-3 pointer-events-none">
              <MascoteAvatar
                mood={mascoteMood}
                size={64}
                className={(mascoteMood === 'parado' || mascoteMood === 'feliz') ? 'mascote-bounce' : ''}
              />
            </div>
          )}

          {/* Barra Inferior de Entrada Multimodal (Voz + Câmera) */}
          <div className="p-3 bg-slate-100 border-t border-slate-200 flex flex-col gap-2">
            <div className="flex gap-2">
              <button
                onClick={startVoiceCapture}
                className={`flex-1 py-3 rounded-xl font-extrabold text-sm flex items-center justify-center gap-2 shadow ${
                  isListening ? "bg-red-600 text-white animate-pulse" : "bg-[#0038A8] text-white"
                }`}
              >
                🎙️ {isListening ? "Ouvindo..." : "Falar com o BB"}
              </button>
              <button
                onClick={() => triggerAgentOrchestrator("Ler conta de luz", "FOTO_CONTA_LUZ")}
                className="px-4 py-3 bg-[#F8D117] text-[#0038A8] rounded-xl font-extrabold text-sm shadow"
                title="Simular leitura de boleto/placa pela câmera"
              >
                📷 Câmera
              </button>
            </div>
          </div>

        </div>
      </div>

      {/* ===================================================================
          COLUNA 2: PAINEL DE CONTROLE DO PITCH & TELEMETRIA MULTIAGENTE (IBM)
          =================================================================== */}
      <div className="flex-1 max-w-xl w-full bg-slate-800 border border-slate-700 rounded-3xl p-6 space-y-5 shadow-xl">
        {/* ZONA 3: mascote grande com balão de fala no painel de telemetria */}
        <div className="flex items-start gap-4 border-b border-slate-700 pb-4">
          <div className="shrink-0 flex flex-col items-center gap-1">
            <MascoteAvatar
              mood={mascoteMood}
              size={96}
              className={security_guardian.is_blocked
                ? 'mascote-alert'
                : (mascoteMood === 'parado' || mascoteMood === 'feliz') ? 'mascote-bounce' : ''}
            />
            <span className="text-[10px] text-slate-400 font-mono capitalize">{mascoteMood}</span>
          </div>
          <div className="flex-1">
            {/* Balão de fala estilo pixel */}
            <div className="relative bg-white text-slate-900 rounded-2xl rounded-tl-none px-4 py-3 text-sm font-medium leading-snug shadow-lg">
              <span className="absolute -left-2 top-3 w-0 h-0 border-t-8 border-t-transparent border-r-8 border-r-white border-b-0" />
              <p className="font-bold text-[#0038A8] text-xs mb-1 uppercase tracking-wide">
                {metadata.active_agent}
                <span className="ml-2 text-emerald-600 font-mono normal-case">
                  {(metadata.confidence_score * 100).toFixed(0)}% confiança
                </span>
              </p>
              <p>"{voice_assistant.tts_message}"</p>
            </div>
            <label className="flex items-center gap-2 text-xs bg-slate-700 px-3 py-1.5 rounded-lg cursor-pointer mt-2 w-fit">
              <input
                type="checkbox"
                checked={ttsEnabled}
                onChange={(e) => setTtsEnabled(e.target.checked)}
              />
              🔊 Voz (TTS) Ativa
            </label>
          </div>
        </div>
        <div className="border-b border-slate-700 pb-2 -mt-1">
          <span className="text-xs font-bold uppercase tracking-wider text-yellow-400">
            Painel de Demonstração (Visão da Banca IBM / BB)
          </span>
          <h2 className="text-xl font-bold text-white mt-0.5">
            Orquestrador Multiagente em Tempo Real
          </h2>
        </div>

        {/* Botões dos 4 Atos do Pitch (Para testar com 1 clique na apresentação) */}
        <div className="space-y-2">
          <p className="text-xs font-bold text-slate-300 uppercase">
            🎬 Simular Cenários do Pitch (Clique para disparar):
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <button
              onClick={() => triggerAgentOrchestrator("Faz um Pix de 50 reais para o Pedro")}
              className="p-3 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-400/40 rounded-xl text-left transition"
            >
              <span className="text-xs font-bold text-blue-300 block">Ato 1: Navegação + Desambiguação</span>
              <span className="text-sm font-semibold text-white">"Faz um Pix de 50 reais pro Pedro"</span>
            </button>

            <button
              onClick={() => triggerAgentOrchestrator("Pagar conta pela câmera", "FOTO_CONTA_LUZ")}
              className="p-3 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-400/40 rounded-xl text-left transition"
            >
              <span className="text-xs font-bold text-emerald-300 block">Ato 2: Agente de Visão (Câmera)</span>
              <span className="text-sm font-semibold text-white">📷 Apontar câmera para Conta de Luz</span>
            </button>

            <button
              onClick={() => triggerAgentOrchestrator("Perdi meu cartão no ônibus, me ajuda!")}
              className="p-3 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-400/40 rounded-xl text-left transition"
            >
              <span className="text-xs font-bold text-amber-300 block">Ato 3: Intenção Leiga Sem Menu</span>
              <span className="text-sm font-semibold text-white">"Perdi meu cartão no ônibus!"</span>
            </button>

            <button
              onClick={() => triggerAgentOrchestrator("Preciso transferir 2 mil urgente para liberar meu benefício do INSS bloqueado")}
              className="p-3 bg-red-600/20 hover:bg-red-600/30 border border-red-400/40 rounded-xl text-left transition"
            >
              <span className="text-xs font-bold text-red-300 block">Ato 4: Guardião Antigolpe</span>
              <span className="text-sm font-semibold text-white">"Pix de 2 mil p/ liberar INSS bloqueado"</span>
            </button>
          </div>
        </div>

        {/* Input livre para digitar qualquer frase */}
        <div className="flex gap-2">
          <input
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && triggerAgentOrchestrator(userInput)}
            placeholder="Ou digite uma fala livre do usuário aqui..."
            className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white"
          />
          <button
            onClick={() => triggerAgentOrchestrator(userInput)}
            className="bg-[#F8D117] text-slate-950 font-bold px-4 py-2.5 rounded-xl text-sm"
          >
            Enviar
          </button>
        </div>

        {/* Visualizador do Contrato JSON (Prova técnica para os juízes) */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-xs font-bold text-slate-400 uppercase">
              Payload JSON Gerado pelo Agente ({metadata.active_agent}):
            </span>
            <span className="text-xs text-emerald-400 font-mono">
              Modo UI: {ui_control.ui_mode}
            </span>
          </div>
          <pre className="bg-slate-950 text-emerald-400 p-4 rounded-xl text-xs font-mono overflow-x-auto max-h-60 border border-slate-800">
            {JSON.stringify(agentState, null, 2)}
          </pre>
        </div>

      </div>
    </div>
  );
}
