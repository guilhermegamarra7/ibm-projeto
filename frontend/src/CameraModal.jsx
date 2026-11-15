// arquivo: src/CameraModal.jsx
// Modal de câmera real: abre getUserMedia, exibe preview ao vivo,
// captura frame como base64 e retorna para o App via onCapture().
import React, { useRef, useState, useEffect, useCallback } from 'react';

/**
 * Props:
 *   open         — boolean
 *   onClose      — () => void
 *   onCapture    — (base64DataURL: string, mode: 'boleto'|'qrcode') => void
 *   defaultMode  — 'boleto' | 'qrcode'   (opcional, default 'boleto')
 */
export default function CameraModal({ open, onClose, onCapture, defaultMode = 'boleto' }) {
  const videoRef   = useRef(null);
  const canvasRef  = useRef(null);
  const streamRef  = useRef(null);

  const [mode, setMode]           = useState(defaultMode);
  const [camError, setCamError]   = useState(null);
  const [captured, setCaptured]   = useState(null); // base64 do preview da captura
  const [facingMode, setFacingMode] = useState('environment'); // traseira por padrão

  // -------------------------------------------------------------------------
  // Inicia câmera ao abrir o modal
  // -------------------------------------------------------------------------
  const startCamera = useCallback(async (facing) => {
    setCamError(null);
    // Para a stream anterior se existir
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err) {
      setCamError(`Não foi possível acessar a câmera: ${err.message}`);
    }
  }, []);

  useEffect(() => {
    if (open) {
      setCaptured(null);
      setMode(defaultMode);
      startCamera(facingMode);
    } else {
      // Libera câmera ao fechar
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const flipCamera = () => {
    const next = facingMode === 'environment' ? 'user' : 'environment';
    setFacingMode(next);
    startCamera(next);
  };

  // -------------------------------------------------------------------------
  // Captura frame do vídeo → base64
  // -------------------------------------------------------------------------
  const captureFrame = () => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // JPEG a 85% de qualidade — bom balanço tamanho/fidelidade
    const dataURL = canvas.toDataURL('image/jpeg', 0.85);
    setCaptured(dataURL);

    // Para a câmera após captura (economiza bateria)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
  };

  const confirmCapture = () => {
    if (captured) {
      onCapture(captured, mode);
      onClose();
    }
  };

  const retake = () => {
    setCaptured(null);
    startCamera(facingMode);
  };

  if (!open) return null;

  return (
    // Overlay escuro sobre tudo
    <div
      className="fixed inset-0 z-50 bg-black/90 flex flex-col items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-label="Câmera do assistente"
    >
      {/* Header */}
      <div className="w-full max-w-sm flex items-center justify-between px-4 py-3 bg-[#0038A8]">
        <span className="text-white font-extrabold text-sm">
          📷 {mode === 'qrcode' ? 'Leitura de QR Code Pix' : 'Leitura de Boleto / Conta'}
        </span>
        <button
          onClick={onClose}
          className="text-white text-xl font-black leading-none"
          aria-label="Fechar câmera"
        >
          ✕
        </button>
      </div>

      {/* Seletor de modo */}
      <div className="flex gap-2 mt-3">
        <button
          onClick={() => setMode('boleto')}
          className={`px-4 py-2 rounded-full text-xs font-bold transition ${
            mode === 'boleto'
              ? 'bg-[#F8D117] text-slate-950'
              : 'bg-slate-700 text-slate-200'
          }`}
        >
          📄 Boleto / Conta
        </button>
        <button
          onClick={() => setMode('qrcode')}
          className={`px-4 py-2 rounded-full text-xs font-bold transition ${
            mode === 'qrcode'
              ? 'bg-[#F8D117] text-slate-950'
              : 'bg-slate-700 text-slate-200'
          }`}
        >
          ◼ QR Code Pix
        </button>
      </div>

      {/* Área de vídeo / preview capturado */}
      <div className="relative mt-3 w-full max-w-sm aspect-video bg-black rounded-2xl overflow-hidden border-4 border-slate-700">

        {/* Erro de câmera */}
        {camError && (
          <div className="absolute inset-0 flex items-center justify-center p-4 text-center">
            <div className="bg-red-900 text-red-100 rounded-xl p-4 text-sm">
              <p className="font-bold mb-1">⚠️ Câmera indisponível</p>
              <p className="text-xs">{camError}</p>
              <p className="text-xs mt-2 text-red-300">
                Verifique as permissões de câmera no navegador ou use o botão de simulação abaixo.
              </p>
            </div>
          </div>
        )}

        {/* Preview de captura */}
        {captured && (
          <img
            src={captured}
            alt="Foto capturada"
            className="absolute inset-0 w-full h-full object-cover"
          />
        )}

        {/* Vídeo ao vivo */}
        {!captured && !camError && (
          <video
            ref={videoRef}
            className="w-full h-full object-cover"
            playsInline
            muted
            aria-hidden="true"
          />
        )}

        {/* Guia visual: linha de mira */}
        {!captured && !camError && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className={`border-2 border-dashed rounded-lg opacity-70 ${
              mode === 'qrcode'
                ? 'w-40 h-40 border-[#F8D117]'
                : 'w-64 h-32 border-white'
            }`} />
          </div>
        )}

        {/* Botão virar câmera */}
        {!captured && !camError && (
          <button
            onClick={flipCamera}
            className="absolute top-2 right-2 bg-black/50 text-white rounded-full w-9 h-9 flex items-center justify-center text-lg"
            aria-label="Virar câmera"
          >
            🔄
          </button>
        )}
      </div>

      {/* Canvas oculto para captura */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Legenda do guia */}
      {!captured && !camError && (
        <p className="text-slate-400 text-xs mt-2 text-center px-4">
          {mode === 'qrcode'
            ? 'Centralize o QR Code dentro do quadrado amarelo'
            : 'Enquadre o boleto ou conta dentro do retângulo branco'}
        </p>
      )}

      {/* Botões de ação */}
      <div className="flex gap-3 mt-4 w-full max-w-sm px-4">
        {!captured ? (
          <>
            {/* Capturar — disponível mesmo sem câmera (simula) */}
            <button
              onClick={camError ? () => onCapture(null, mode) || onClose() : captureFrame}
              className="flex-1 py-4 bg-[#F8D117] text-slate-950 font-black text-base rounded-2xl shadow-lg active:scale-95 transition"
              aria-label="Capturar foto"
            >
              {camError ? '🎭 Simular Captura' : '📸 Capturar'}
            </button>
            <button
              onClick={onClose}
              className="px-5 py-4 bg-slate-700 text-white font-bold text-sm rounded-2xl"
            >
              Cancelar
            </button>
          </>
        ) : (
          <>
            <button
              onClick={confirmCapture}
              className="flex-1 py-4 bg-emerald-500 text-white font-black text-base rounded-2xl shadow-lg active:scale-95 transition"
              aria-label="Analisar imagem capturada"
            >
              ✅ Analisar com IA
            </button>
            <button
              onClick={retake}
              className="px-5 py-4 bg-slate-700 text-white font-bold text-sm rounded-2xl"
            >
              🔁 Tirar outra
            </button>
          </>
        )}
      </div>

      <p className="text-slate-500 text-[11px] mt-3 pb-4">
        A imagem é analisada localmente pelo watsonx e não é armazenada.
      </p>
    </div>
  );
}
