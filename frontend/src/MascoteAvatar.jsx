// MascoteAvatar.jsx
// 5 sprites oficiais do mascote BB com fundo transparente

import React from 'react';

import esperando_acao from './assets/sprites/esperando_acao.png';
import feliz_acao     from './assets/sprites/feliz_acao.png';
import dando_dica     from './assets/sprites/dando_dica.png';
import pergunta_algo  from './assets/sprites/pergunta_algo.png';
import pergunta_ajuda from './assets/sprites/pergunta_ajuda.png';

// Mapeamento estado agêntico → sprite
// esperando_acao : idle, aguardando, home, orquestrador
// feliz_acao     : operação concluída, Pix confirmado, cartão bloqueado com sucesso
// dando_dica     : desambiguação (dois Pedros), visão/câmera, dando instrução
// pergunta_algo  : ouvindo voz, processando, carregando
// pergunta_ajuda : alerta de golpe (guardião antigolpe)
const MOOD_MAP = {
  // estados internos do app
  idle:              esperando_acao,
  listening:         pergunta_algo,
  loading:           pergunta_algo,
  completed:         feliz_acao,
  disambiguation:    dando_dica,
  alert:             pergunta_ajuda,

  // agentes do backend
  ORQUESTRADOR:       esperando_acao,
  OPERADOR_UI:        feliz_acao,
  VISAO_MULTIMODAL:   dando_dica,
  GUARDIAO_ANTIGOLPE: pergunta_ajuda,

  // intenções
  PIX_TRANSFER:       dando_dica,
  PIX_TRANSFER_READY: feliz_acao,
  BLOCK_CARD:         feliz_acao,
  SCAM_INTERVENTION:  pergunta_ajuda,
  PAY_BILL:           dando_dica,
  COMPLETED_OR_HOME:  feliz_acao,
  IDLE:               esperando_acao,
};

/**
 * Props:
 *  mood      – chave de MOOD_MAP (agente, intenção ou estado interno). Default: 'idle'
 *  size      – largura em px (height automático). Default: 80
 *  className – classes CSS extras (ex: 'mascote-bounce', 'mascote-alert')
 */
export default function MascoteAvatar({ mood = 'idle', size = 80, className = '' }) {
  const src = MOOD_MAP[mood] ?? esperando_acao;

  return (
    <img
      src={src}
      alt="Assistente Caramelo BB"
      width={size}
      style={{ height: 'auto', display: 'block' }}
      className={className}
    />
  );
}
