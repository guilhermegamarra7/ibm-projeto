// arquivo: src/App.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import MascoteAvatar from './MascoteAvatar';
import CameraModal from './CameraModal';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ID de sessão único por aba — persiste no localStorage para sobreviver a reloads
const SESSION_ID = (() => {
  const key = 'bb_camalao_session_id';
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const id = `session_${Date.now()}`;
  localStorage.setItem(key, id);
  return id;
})();

// Perfis disponíveis para demo (espelha o backend)
const DEMO_PROFILES = [
  { id: 'dona_maria', label: 'Dona Maria, 72a', emoji: '👵', description: 'Aposentada, baixa familiaridade digital' },
  { id: 'sr_joao',   label: 'Sr. João, 68a',   emoji: '👴', description: 'Autônomo, contatos conhecidos' },
  { id: 'ana',       label: 'Ana, 34a',          emoji: '👩', description: 'Jovem, sem contato de confiança' },
];

// Saudação inicial personalizada com o nome do perfil ativo
function makeInitialState(profileLabel) {
  const firstName = profileLabel ? profileLabel.split(',')[0] : 'você';
  return {
    metadata: { active_agent: "ORQUESTRADOR", intent_detected: "IDLE", confidence_score: 1.0 },
    voice_assistant: {
      tts_message: `Olá, ${firstName}! Sou o Assistente Caramelo do Banco do Brasil. Você pode falar comigo ou mostrar uma conta pela câmera.`,
      should_listen_next: false,
    },
    ui_control: {
      target_screen: "HOME",
      ui_mode: "STANDARD",
      form_state: { amount: null, recipient_name: null, recipient_key: null, barcode: null, card_status: "ACTIVE" },
      zero_ui_Dynamic_Component: null,
    },
    security_guardian: { risk_level: "LOW", is_blocked: false, scam_explanation: null, trusted_contact_alert: false },
  };
}

const RISK_LABELS = {
  LOW:      'Baixo',
  MEDIUM:   'Médio',
  HIGH:     'Alto',
  CRITICAL: 'Crítico',
};

// Nomes amigáveis para exibição ao usuário
const AGENT_LABELS = {
  ORQUESTRADOR:       'Assistente Caramelo',
  OPERADOR_UI:        'Assistente Caramelo',
  VISAO_MULTIMODAL:   'Assistente Caramelo — Visão',
  GUARDIAO_ANTIGOLPE: 'Guardião Antigolpe BB',
  EXTRATO:            'Assistente Caramelo',
  HOME:               'Assistente Caramelo',
  ESCLARECIMENTO:     'Assistente Caramelo',
};

function agentLabel(active_agent) {
  return AGENT_LABELS[active_agent] ?? 'Assistente Caramelo';
}

export default function AssistenteCarameloApp() {
  const [agentState, setAgentState]       = useState(() => makeInitialState(DEMO_PROFILES[0].label));
  const [userInput, setUserInput]         = useState("");
  const [isListening, setIsListening]     = useState(false);
  const [isLoading, setIsLoading]         = useState(false);
  const [ttsEnabled, setTtsEnabled]       = useState(true);
  // Legenda do TTS — acessibilidade auditiva
  const [ttsCaption, setTtsCaption]       = useState("");
  // Erro de conectividade
  const [apiError, setApiError]           = useState(null);
  // Perfil ativo na demo
  const [activeProfile, setActiveProfile] = useState(DEMO_PROFILES[0]);
  // Câmera
  const [cameraOpen, setCameraOpen]       = useState(false);
  const [cameraMode, setCameraMode]       = useState('boleto'); // 'boleto' | 'qrcode'
  // Histórico de chat exibido no celular mock
  const [chatHistory, setChatHistory]     = useState([
    { role: 'assistant', text: `Olá, ${DEMO_PROFILES[0].label.split(',')[0]}! Sou o Assistente Caramelo. Digite ou fale o que você precisa fazer.` }
  ]);

  const inputRef    = useRef(null);
  const chatEndRef  = useRef(null); // âncora para auto-scroll

  // =========================================================================
  // TTS — fala e exibe legenda ao mesmo tempo
  // =========================================================================
  useEffect(() => {
    const msg = agentState.voice_assistant.tts_message;
    if (!msg) return;
    setTtsCaption(msg);

    if (ttsEnabled && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(msg);
      utterance.lang = 'pt-BR';
      utterance.rate = 0.95;
      window.speechSynthesis.speak(utterance);
    }
  }, [agentState.voice_assistant.tts_message, ttsEnabled]);

  // Auto-scroll do chat para a mensagem mais recente
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  // =========================================================================
  // RESET DE SESSÃO
  // =========================================================================
  const resetSession = useCallback(async (clearStorage = true) => {
    try {
      await fetch(`${API_URL}/api/session/${SESSION_ID}`, { method: 'DELETE' });
    } catch (_) { /* ok, sessão pode não existir */ }
    if (clearStorage) {
      localStorage.removeItem('bb_camalao_session_id');
    }
    const firstName = activeProfile.label.split(',')[0];
    setAgentState(makeInitialState(activeProfile.label));
    setChatHistory([{ role: 'assistant', text: `Olá, ${firstName}! Sou o Assistente Caramelo. Digite ou fale o que você precisa fazer.` }]);
    setApiError(null);
    setTtsCaption("");
  }, [activeProfile]);

  // =========================================================================
  // TROCA DE PERSONA (demo)
  // =========================================================================
  const switchProfile = useCallback(async (profile) => {
    setActiveProfile(profile);
    try {
      await fetch(`${API_URL}/api/session/${SESSION_ID}/change_profile?profile_id=${profile.id}`, { method: 'POST' });
    } catch (_) {}
    try {
      await fetch(`${API_URL}/api/session/${SESSION_ID}`, { method: 'DELETE' });
    } catch (_) {}
    const firstName = profile.label.split(',')[0];
    setAgentState(makeInitialState(profile.label));
    setChatHistory([{ role: 'assistant', text: `Olá, ${firstName}! Sou o Assistente Caramelo. Digite ou fale o que você precisa fazer.` }]);
    setApiError(null);
    setTtsCaption("");
  }, []);

  // =========================================================================
  // CHAMADA AO BACKEND (fonte única de verdade — sem lógica duplicada)
  // Aceita image_base64 (câmera real) além de image_context (simulação)
  // =========================================================================
  const callBackend = useCallback(async (commandText, imageContext = null, imageBase64 = null) => {
    setIsLoading(true);
    setApiError(null);

    // Adiciona mensagem do usuário imediatamente no chat (só se for texto real, não comandos internos)
    if (!imageContext) {
      setChatHistory(h => [...h, { role: 'user', text: commandText }]);
    } else {
      const label = imageContext === 'FOTO_QRCODE_PIX' ? '📷 Leitura de QR Code Pix' : '📷 Leitura de Boleto / Conta';
      setChatHistory(h => [...h, { role: 'user', text: label }]);
    }

    try {
      const res = await fetch(`${API_URL}/api/agent/interact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_input: commandText,
          current_screen: agentState.ui_control.target_screen,
          image_context: imageContext,
          image_base64: imageBase64,
          session_id: SESSION_ID,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAgentState(data);
      // Adiciona resposta do assistente no chat
      setChatHistory(h => [...h, { role: 'assistant', text: data.voice_assistant.tts_message }]);
    } catch (err) {
      setApiError(`Sem conexão com o servidor (${err.message}). Verifique se o backend está rodando.`);
      setChatHistory(h => [...h, { role: 'assistant', text: '⚠️ Não consegui conectar ao servidor. Tente novamente.' }]);
    } finally {
      setIsLoading(false);
      setUserInput("");
    }
  }, [agentState.ui_control.target_screen]);

  // =========================================================================
  // CALLBACK DA CÂMERA REAL
  // =========================================================================
  const handleCameraCapture = useCallback((base64DataURL, mode) => {
    // Se não houver imagem (câmera bloqueada), cai no mock
    if (!base64DataURL) {
      const ctx  = mode === 'qrcode' ? 'FOTO_QRCODE_PIX' : 'FOTO_CONTA_LUZ';
      const text = mode === 'qrcode' ? 'Ler QR Code Pix' : 'Ler conta de luz';
      callBackend(text, ctx, null);
      return;
    }
    const text = mode === 'qrcode' ? 'Analise o QR Code Pix nesta imagem' : 'Analise o boleto ou conta nesta imagem';
    // Passa base64 completo (data:image/jpeg;base64,...)
    callBackend(text, mode === 'qrcode' ? 'FOTO_QRCODE_PIX' : 'FOTO_CONTA_LUZ', base64DataURL);
  }, [callBackend]);

  // =========================================================================
  // RECONHECIMENTO DE VOZ (Web Speech API nativa)
  // =========================================================================
  const startVoiceCapture = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Seu navegador não suporta Web Speech API nativa. Use o campo de texto.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    setIsListening(true);
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setUserInput(transcript);
      setIsListening(false);
      callBackend(transcript);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend   = () => setIsListening(false);
    recognition.start();
  };

  const { ui_control, voice_assistant, metadata, security_guardian } = agentState;

  // Mood do mascote derivado do estado do agente
  const mascoteMood = (() => {
    if (isLoading)   return 'loading';
    if (isListening) return 'listening';
    const { active_agent: agent, intent_detected: intent } = metadata;
    if (agent  === 'GUARDIAO_ANTIGOLPE')  return 'GUARDIAO_ANTIGOLPE';
    if (agent  === 'VISAO_MULTIMODAL')    return 'VISAO_MULTIMODAL';
    if (intent === 'PIX_TRANSFER_READY')  return 'PIX_TRANSFER_READY';
    if (intent === 'COMPLETED_OR_HOME')   return 'COMPLETED_OR_HOME';
    if (intent === 'PIX_TRANSFER')        return 'PIX_TRANSFER';
    if (intent === 'BLOCK_CARD')          return 'BLOCK_CARD';
    if (intent === 'SCAM_INTERVENTION')   return 'SCAM_INTERVENTION';
    if (intent === 'RISK_WARNING')        return 'GUARDIAO_ANTIGOLPE';
    if (intent === 'RISK_NOTICE')         return 'GUARDIAO_ANTIGOLPE';
    if (intent === 'PAY_BILL')            return 'PAY_BILL';
    if (intent === 'STATEMENT_REVIEW')    return 'dando_dica';
    if (agent  === 'OPERADOR_UI')         return 'OPERADOR_UI';
    return 'idle';
  })();

  const isEmergency = ui_control.ui_mode === "ZERO_UI_EMERGENCY_LOCK";
  const isZeroUI    = ui_control.ui_mode !== "STANDARD";

  return (
    <div className="min-h-screen bg-slate-900 text-white p-4 md:p-8 flex flex-col lg:flex-row gap-8 items-center justify-center font-sans">

      {/* ==================================================================
          COLUNA 1 — CELULAR MOCK DO BANCO DO BRASIL
          ================================================================== */}
      <div
        className="w-[380px] h-[760px] bg-white text-slate-900 rounded-[42px] border-[10px] border-slate-800 shadow-2xl overflow-hidden flex flex-col relative"
        role="main"
        aria-label="Interface do aplicativo Banco do Brasil"
      >
        {/* Topo */}
        <div className="bg-[#F8D117] text-[#0038A8] px-5 pt-6 pb-4 flex items-center justify-between font-bold shadow-sm">
          <div>
            <p className="text-xs uppercase tracking-wider opacity-80">Banco do Brasil</p>
            <h1 className="text-lg font-extrabold">Olá, {activeProfile.label.split(',')[0]}</h1>
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${isZeroUI ? 'bg-[#0038A8] text-white' : 'bg-black/10 text-[#0038A8]'}`}>
            {isZeroUI ? '♿ Zero-UI Ativa' : 'UI Padrão'}
          </span>
        </div>

        {/* Barra do assistente + legenda TTS */}
        <div
          className={`px-4 py-3 border-b flex flex-col gap-2 transition-colors duration-300 ${isEmergency ? "bg-red-900 text-white" : "bg-[#0038A8] text-white"}`}
          aria-live="polite"
          aria-label="Mensagem do assistente"
        >
          <div className="flex items-start gap-3">
            <MascoteAvatar
              mood={mascoteMood}
              size={40}
              className={isEmergency ? 'mascote-alert' : ''}
            />
            <div className="text-xs leading-relaxed">
              <span className="font-bold text-[#F8D117] block mb-0.5">
                {agentLabel(metadata.active_agent)}
                {isLoading && <span className="ml-2 opacity-70 animate-pulse">· processando…</span>}
              </span>
              {/* Legenda visível do que foi falado — acessibilidade auditiva */}
              <span className="italic">{ttsCaption}</span>
            </div>
          </div>

          {/* Indicador de risco (visível sempre que não for LOW) */}
          {security_guardian.risk_level !== "LOW" && (
            <div className={`text-xs font-bold px-2 py-1 rounded-lg ${security_guardian.risk_level === "CRITICAL" ? "bg-red-700" : "bg-yellow-600 text-black"}`}>
              Risco {RISK_LABELS[security_guardian.risk_level] ?? security_guardian.risk_level} · {security_guardian.scam_explanation?.split('.')[0]}
            </div>
          )}
        </div>

        {/* Aviso de erro de API */}
        {apiError && (
          <div className="bg-orange-100 border-l-4 border-orange-500 text-orange-900 px-4 py-2 text-xs" role="alert">
            ⚠️ {apiError}
          </div>
        )}

        {/* CORPO PRINCIPAL */}
        <div className="flex-1 overflow-y-auto flex flex-col justify-between min-h-0">

          {/* MODO PADRÃO — chat + grade de serviços mini */}
          {ui_control.ui_mode === "STANDARD" && (
            <div className="flex flex-col h-full">
              {/* Saldo mini */}
              <div className="mx-3 mt-3 bg-slate-100 px-4 py-2.5 rounded-xl border border-slate-200 flex items-center justify-between shrink-0">
                <p className="text-xs text-slate-500">Saldo disponível</p>
                <p className="text-lg font-extrabold text-[#0038A8]">R$ 1.450,00</p>
              </div>

              {/* Grade de serviços — compacta, apenas atalhos visuais */}
              <div className="grid grid-cols-5 gap-1.5 px-3 pt-2 shrink-0">
                {[
                  { icon: "💸", name: "Pix" },
                  { icon: "📄", name: "Boleto" },
                  { icon: "💳", name: "Cartão" },
                  { icon: "📋", name: "Extrato" },
                  { icon: "⚙️", name: "Mais" },
                ].map((item, idx) => (
                  <div key={idx} className="bg-slate-50 border border-slate-200 p-2 rounded-xl flex flex-col items-center gap-0.5">
                    <span className="text-base" aria-hidden="true">{item.icon}</span>
                    <span className="text-[9px] font-medium text-slate-600">{item.name}</span>
                  </div>
                ))}
              </div>

              {/* ── CHAT HISTÓRICO ── */}
              <div
                className="flex-1 overflow-y-auto px-3 py-2 space-y-2 min-h-0"
                aria-live="polite"
                aria-label="Histórico de conversa com o assistente"
              >
                {chatHistory.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div className={`max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-snug shadow-sm ${
                      msg.role === 'user'
                        ? 'bg-[#0038A8] text-white rounded-br-sm'
                        : 'bg-slate-100 text-slate-900 rounded-bl-sm border border-slate-200'
                    }`}>
                      {msg.text}
                    </div>
                  </div>
                ))}
                {/* Indicador de digitação */}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className="bg-slate-100 border border-slate-200 px-4 py-2.5 rounded-2xl rounded-bl-sm flex gap-1 items-center">
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{animationDelay:'0ms'}} />
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{animationDelay:'150ms'}} />
                      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{animationDelay:'300ms'}} />
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            </div>
          )}

          {/* MODO ZERO-UI ALTO CONTRASTE */}
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

                {ui_control.form_state.amount && (
                  <div className="mt-4 bg-slate-900 border-2 border-[#F8D117] rounded-2xl p-4">
                    <p className="text-xs text-slate-300 uppercase">Valor preenchido pela IA:</p>
                    <p className="text-3xl font-black text-white">
                      R$ {ui_control.form_state.amount.toFixed(2).replace('.', ',')}
                    </p>
                  </div>
                )}
              </div>

              <div className="space-y-3 my-4">
                {ui_control.zero_ui_Dynamic_Component.options.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => callBackend(opt.action_Command)}
                    disabled={isLoading}
                    className="w-full py-5 px-4 bg-[#F8D117] hover:bg-yellow-300 text-slate-950 font-black text-lg rounded-2xl shadow-lg text-left flex items-center justify-between transition transform active:scale-95 disabled:opacity-50"
                    aria-label={opt.label}
                  >
                    <span>{opt.label}</span>
                    <span className="text-2xl" aria-hidden="true">→</span>
                  </button>
                ))}

                {ui_control.zero_ui_Dynamic_Component.primary_confirm_button && (
                  <button
                    onClick={() => callBackend(ui_control.zero_ui_Dynamic_Component.primary_confirm_button.action_Command)}
                    disabled={isLoading}
                    className="w-full py-6 px-4 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xl rounded-2xl shadow-xl text-center transition transform active:scale-95 disabled:opacity-50"
                    aria-label={ui_control.zero_ui_Dynamic_Component.primary_confirm_button.label}
                  >
                    {ui_control.zero_ui_Dynamic_Component.primary_confirm_button.label}
                  </button>
                )}

                {/* Saída de emergência — sempre visível */}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => callBackend("Voltar ao início")}
                    className="flex-1 py-3 bg-slate-800 text-slate-200 font-bold text-sm rounded-xl border border-slate-700"
                  >
                    ← Cancelar e Voltar
                  </button>
                  <button
                    onClick={() => callBackend("Falar com atendente humano")}
                    className="flex-1 py-3 bg-slate-700 text-white font-bold text-sm rounded-xl border border-slate-600"
                    aria-label="Falar com atendente humano do Banco do Brasil"
                  >
                    👤 Atendente
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* MODO BLOQUEIO ANTIGOLPE */}
          {isEmergency && ui_control.zero_ui_Dynamic_Component && (
            <div className="flex-1 bg-red-950 text-white p-5 flex flex-col justify-between border-4 border-red-500" role="alertdialog" aria-label="Alerta de segurança">
              <div>
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

                {/* Exibe sinais de risco detectados */}
                {security_guardian.scam_explanation && (
                  <p className="text-xs text-red-200 mt-2 italic">
                    {security_guardian.scam_explanation}
                  </p>
                )}
              </div>

              <div className="space-y-3 my-4">
                {ui_control.zero_ui_Dynamic_Component.options.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => callBackend(opt.action_Command)}
                    disabled={isLoading}
                    className="w-full py-5 px-4 bg-yellow-400 hover:bg-yellow-300 text-slate-950 font-black text-base rounded-2xl shadow-lg text-center disabled:opacity-50"
                  >
                    {opt.label}
                  </button>
                ))}

                {/* Saída sempre visível no modo emergência */}
                <button
                  onClick={() => callBackend("Falar com atendente humano")}
                  className="w-full py-3 bg-white/10 text-white font-bold text-sm rounded-xl border border-white/20"
                >
                  👤 Falar com Atendente do BB
                </button>
              </div>
            </div>
          )}

          {/* Mascote flutuante — só no modo padrão e não emergência */}
          {!isEmergency && ui_control.ui_mode === "STANDARD" && (
            <div className="absolute bottom-[72px] right-3 pointer-events-none" aria-hidden="true">
              <MascoteAvatar mood={mascoteMood} size={52} />
            </div>
          )}

          {/* ── BARRA DE ENTRADA: texto inline + voz + câmera ── */}
          <div className="shrink-0 px-2 py-2 bg-white border-t border-slate-200 flex flex-col gap-1.5">
            {/* Campo de texto + enviar */}
            <div className="flex gap-1.5 items-center">
              <input
                ref={inputRef}
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && userInput.trim() && !isLoading) {
                    callBackend(userInput.trim());
                  }
                }}
                placeholder="Digite o que precisa…"
                disabled={isLoading}
                aria-label="Digite sua mensagem para o assistente"
                className="flex-1 bg-slate-100 border border-slate-300 rounded-full px-4 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#0038A8] disabled:opacity-50"
              />
              <button
                onClick={() => userInput.trim() && !isLoading && callBackend(userInput.trim())}
                disabled={isLoading || !userInput.trim()}
                aria-label="Enviar mensagem"
                className="w-9 h-9 rounded-full bg-[#0038A8] text-white flex items-center justify-center disabled:opacity-40 shrink-0"
              >
                ➤
              </button>
            </div>
            {/* Linha de ações rápidas: voz + câmera */}
            <div className="flex gap-1.5">
              <button
                onClick={startVoiceCapture}
                disabled={isLoading}
                aria-label={isListening ? "Ouvindo…" : "Falar com o assistente"}
                className={`flex-1 py-2 rounded-xl font-bold text-xs flex items-center justify-center gap-1.5 transition ${
                  isListening ? "bg-red-600 text-white animate-pulse" :
                  isLoading   ? "bg-slate-300 text-slate-500 cursor-wait" :
                                "bg-[#0038A8] text-white"
                }`}
              >
                🎙️ {isListening ? "Ouvindo…" : "Voz"}
              </button>
              <button
                onClick={() => { setCameraMode('boleto'); setCameraOpen(true); }}
                disabled={isLoading}
                className="px-4 py-2 bg-[#F8D117] text-[#0038A8] rounded-xl font-bold text-xs disabled:opacity-50"
                title="Câmera — Boleto"
              >
                📷 Boleto
              </button>
              <button
                onClick={() => { setCameraMode('qrcode'); setCameraOpen(true); }}
                disabled={isLoading}
                className="px-4 py-2 bg-slate-100 text-slate-700 border border-slate-300 rounded-xl font-bold text-xs disabled:opacity-50"
                title="Câmera — QR Pix"
              >
                ◼ Pix QR
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ==================================================================
          COLUNA 2 — PAINEL DE TELEMETRIA (VISÃO DA BANCA IBM)
          ================================================================== */}
      <div className="flex-1 max-w-xl w-full bg-slate-800 border border-slate-700 rounded-3xl p-6 space-y-5 shadow-xl">

        {/* Mascote + balão de fala */}
        <div className="flex items-start gap-4 border-b border-slate-700 pb-4">
          <div className="shrink-0 flex flex-col items-center gap-1">
            <MascoteAvatar mood={mascoteMood} size={96} className={isEmergency ? 'mascote-alert' : ''} />
            <span className="text-[10px] text-slate-400 font-mono capitalize">{mascoteMood}</span>
          </div>
          <div className="flex-1">
            <div className="relative bg-white text-slate-900 rounded-2xl rounded-tl-none px-4 py-3 text-sm font-medium leading-snug shadow-lg">
              <span className="absolute -left-2 top-3 w-0 h-0 border-t-8 border-t-transparent border-r-8 border-r-white border-b-0" aria-hidden="true" />
              <p className="font-bold text-[#0038A8] text-xs mb-1 uppercase tracking-wide">
                {agentLabel(metadata.active_agent)}
                <span className="ml-2 text-emerald-600 font-mono normal-case">
                  {(metadata.confidence_score * 100).toFixed(0)}% confiança
                </span>
              </p>
              <p>"{voice_assistant.tts_message}"</p>
            </div>
            <div className="flex gap-2 mt-2">
              <label className="flex items-center gap-2 text-xs bg-slate-700 px-3 py-1.5 rounded-lg cursor-pointer">
                <input type="checkbox" checked={ttsEnabled} onChange={(e) => setTtsEnabled(e.target.checked)} />
                🔊 Voz (TTS)
              </label>
              <button
                onClick={resetSession}
                className="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg text-slate-300"
                title="Limpa a sessão e reinicia a conversa"
              >
                🔄 Resetar sessão
              </button>
            </div>
          </div>
        </div>

        <div className="border-b border-slate-700 pb-2 -mt-1">
          <span className="text-xs font-bold uppercase tracking-wider text-yellow-400">
            Painel de Demonstração — IBM / BB
          </span>
          <h2 className="text-xl font-bold text-white mt-0.5">Orquestrador Multiagente (LangGraph)</h2>
        </div>

        {/* 6 Atos do Pitch */}
        <div className="space-y-2">
          <p className="text-xs font-bold text-slate-300 uppercase">🎬 Cenários do Pitch:</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <button
              onClick={() => callBackend("Faz um Pix de 50 reais para o Pedro")}
              disabled={isLoading}
              className="p-3 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-400/40 rounded-xl text-left transition disabled:opacity-50"
            >
              <span className="text-xs font-bold text-blue-300 block">Ato 1: Navegação + Desambiguação</span>
              <span className="text-sm font-semibold text-white">"Pix de 50 pro Pedro"</span>
            </button>

            <button
              onClick={() => callBackend("Pagar conta pela câmera", "FOTO_CONTA_LUZ")}
              disabled={isLoading}
              className="p-3 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-400/40 rounded-xl text-left transition disabled:opacity-50"
            >
              <span className="text-xs font-bold text-emerald-300 block">Ato 2: Visão Multimodal</span>
              <span className="text-sm font-semibold text-white">📷 Câmera → Conta de Luz</span>
            </button>

            <button
              onClick={() => callBackend("Perdi meu cartão no ônibus, me ajuda!")}
              disabled={isLoading}
              className="p-3 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-400/40 rounded-xl text-left transition disabled:opacity-50"
            >
              <span className="text-xs font-bold text-amber-300 block">Ato 3: Intenção Leiga</span>
              <span className="text-sm font-semibold text-white">"Perdi meu cartão no ônibus!"</span>
            </button>

            <button
              onClick={() => callBackend("Preciso transferir 2 mil urgente para liberar meu benefício do INSS bloqueado")}
              disabled={isLoading}
              className="p-3 bg-red-600/20 hover:bg-red-600/30 border border-red-400/40 rounded-xl text-left transition disabled:opacity-50"
            >
              <span className="text-xs font-bold text-red-300 block">Ato 4: Guardião Antigolpe</span>
              <span className="text-sm font-semibold text-white">"Pix p/ liberar INSS bloqueado"</span>
            </button>

            <button
              onClick={() => callBackend("Quero ver meu extrato, tem um débito que não reconheço")}
              disabled={isLoading}
              className="p-3 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-400/40 rounded-xl text-left transition disabled:opacity-50"
            >
              <span className="text-xs font-bold text-purple-300 block">Ato 5: Assistente de Extrato</span>
              <span className="text-sm font-semibold text-white">"Esse débito, eu reconheço?"</span>
            </button>

            <button
              onClick={() => callBackend("Ler QR Code Pix", "FOTO_QRCODE_PIX")}
              disabled={isLoading}
              className="p-3 bg-teal-600/20 hover:bg-teal-600/30 border border-teal-400/40 rounded-xl text-left transition disabled:opacity-50"
            >
              <span className="text-xs font-bold text-teal-300 block">Ato 6: Visão — QR Code Pix</span>
              <span className="text-sm font-semibold text-white">📷 Câmera → QR Code Pix</span>
            </button>

            <button
              onClick={() => callBackend("Quero fazer um Pix de 120 reais para a chave CPF 123.456.789-00")}
              disabled={isLoading}
              className="p-3 bg-orange-600/20 hover:bg-orange-600/30 border border-orange-400/40 rounded-xl text-left transition disabled:opacity-50"
            >
              <span className="text-xs font-bold text-orange-300 block">Ato 7: Pix por Chave Desconhecida</span>
              <span className="text-sm font-semibold text-white">"Pix R$120 para CPF desconhecido"</span>
            </button>
          </div>
        </div>

        {/* Seletor de Personas */}
        <div className="space-y-2">
          <p className="text-xs font-bold text-slate-300 uppercase">👤 Trocar Persona (Demo):</p>
          <div className="flex gap-2">
            {DEMO_PROFILES.map((p) => (
              <button
                key={p.id}
                onClick={() => switchProfile(p)}
                disabled={isLoading}
                title={p.description}
                className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition disabled:opacity-50 ${
                  activeProfile.id === p.id
                    ? 'bg-yellow-400 text-slate-950 ring-2 ring-yellow-300'
                    : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
                }`}
              >
                {p.emoji} {p.label}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-slate-500 italic">{activeProfile.description}</p>
        </div>

        {/* Input livre */}
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && userInput.trim() && callBackend(userInput)}
            placeholder="Ou digite uma fala livre aqui…"
            disabled={isLoading}
            aria-label="Campo de texto para input do usuário"
            className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white disabled:opacity-50"
          />
          <button
            onClick={() => userInput.trim() && callBackend(userInput)}
            disabled={isLoading || !userInput.trim()}
            className="bg-[#F8D117] text-slate-950 font-bold px-4 py-2.5 rounded-xl text-sm disabled:opacity-50"
          >
            Enviar
          </button>
        </div>

        {/* Visualizador do Contrato JSON */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-xs font-bold text-slate-400 uppercase">
              Contrato JSON — {agentLabel(metadata.active_agent)}
            </span>
            <div className="flex items-center gap-2">
              {metadata.risk_score != null && (
                <span className="text-xs font-mono text-slate-400">
                  score: <span style={{ color: security_guardian.risk_level === 'CRITICAL' ? '#f87171' : security_guardian.risk_level === 'HIGH' ? '#fbbf24' : security_guardian.risk_level === 'MEDIUM' ? '#fb923c' : '#34d399' }}>
                    {metadata.risk_score}/100
                  </span>
                </span>
              )}
              <span className="text-xs font-mono" style={{ color: security_guardian.risk_level === 'CRITICAL' ? '#f87171' : security_guardian.risk_level === 'HIGH' ? '#fbbf24' : security_guardian.risk_level === 'MEDIUM' ? '#fb923c' : '#34d399' }}>
                risco: {RISK_LABELS[security_guardian.risk_level] ?? security_guardian.risk_level}
              </span>
            </div>
          </div>
          <pre className="bg-slate-950 text-emerald-400 p-4 rounded-xl text-xs font-mono overflow-x-auto max-h-60 border border-slate-800">
            {JSON.stringify(agentState, null, 2)}
          </pre>
        </div>

      </div>

      {/* Modal de câmera real */}
      <CameraModal
        open={cameraOpen}
        onClose={() => setCameraOpen(false)}
        onCapture={handleCameraCapture}
        defaultMode={cameraMode}
      />
    </div>
  );
}
