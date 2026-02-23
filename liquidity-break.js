/**
 * 🔥 Liquidity Break Frontend Handler
 * Gerencia a visualização e interação com detecção de liquidity breaks
 */

// ============================================================
// ESTADO GLOBAL
// ============================================================

const LIQUIDITY_STATE = {
  isOpen: false,
  preset: 'xauusd_safe',
  breaks: [],
  levels: {
    supports: [],
    resistances: [],
  },
  stats: {
    total_breaks: 0,
    momentum_breaks: 0,
    vacuum_breaks: 0,
    structural_breaks: 0,
    active_supports: 0,
    active_resistances: 0,
  },
  lastBreak: null,
};

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  initLiquidityBreakHandlers();
});

function initLiquidityBreakHandlers() {
  // Toggle button
  const liquidityToggle = document.getElementById('liquidityToggle');
  if (liquidityToggle) {
    liquidityToggle.addEventListener('click', toggleLiquidityPanel);
  }

  // Preset selector
  const presetSelect = document.getElementById('liquidityPreset');
  if (presetSelect) {
    presetSelect.addEventListener('change', (e) => {
      changeLiquidityPreset(e.target.value);
    });
  }

  // WebSocket message listeners
  setupLiquidityWebSocketListeners();
}

// ============================================================
// WEBSOCKET HANDLERS
// ============================================================

function setupLiquidityWebSocketListeners() {
  // Interceptar mensagens do WebSocket para liquidity breaks
  const originalOnMessage = window.onWsMessage || (() => {});

  window.onWsMessage = function(msg) {
    // Processar liquidity breaks
    if (msg.type === 'engine_status') {
      updateLiquidityStats(msg.data?.liquidity_break);
    }

    if (msg.type === 'liquidity_levels') {
      updateActiveLevels(msg.data);
    }

    if (msg.type === 'liquidity_breaks') {
      updateBreaksTable(msg.data);
    }

    if (msg.type === 'structural_breaks') {
      updateStructuralBreaks(msg.data);
    }

    if (msg.type === 'cluster_closed' && msg.data?.liquidity_break) {
      // Novo break detectado
      addNewBreak(msg.data.liquidity_break);
      updateLiquidityStatus(true);
    }

    // Chamar handler original
    originalOnMessage.call(this, msg);
  };
}

// ============================================================
// UI UPDATES
// ============================================================

function updateLiquidityStats(stats) {
  if (!stats) return;

  LIQUIDITY_STATE.stats = {
    total_breaks: stats.total_breaks || 0,
    momentum_breaks: stats.momentum_breaks || 0,
    vacuum_breaks: stats.vacuum_breaks || 0,
    structural_breaks: stats.structural_breaks || 0,
    active_supports: stats.active_supports || 0,
    active_resistances: stats.active_resistances || 0,
  };

  // Atualizar cards de stats
  const elems = {
    'lb_total_breaks': LIQUIDITY_STATE.stats.total_breaks,
    'lb_momentum': LIQUIDITY_STATE.stats.momentum_breaks,
    'lb_vacuum': LIQUIDITY_STATE.stats.vacuum_breaks,
    'lb_structural': LIQUIDITY_STATE.stats.structural_breaks,
    'lb_supports': LIQUIDITY_STATE.stats.active_supports,
    'lb_resistances': LIQUIDITY_STATE.stats.active_resistances,
  };

  for (const [id, value] of Object.entries(elems)) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  // Atualizar último break
  if (stats.last_break) {
    LIQUIDITY_STATE.lastBreak = stats.last_break;
    renderLastBreak();
  }
}

function updateActiveLevels(data) {
  if (!data) return;

  LIQUIDITY_STATE.levels = data;

  // Atualizar resistências
  const resistancesList = document.getElementById('resistancesList');
  if (resistancesList) {
    if (data.resistances && data.resistances.length > 0) {
      resistancesList.innerHTML = data.resistances
        .map(level => renderLevelItem(level, 'resistance'))
        .join('');
    } else {
      resistancesList.innerHTML = '<div class="level-empty">Nenhuma resistência ativa</div>';
    }
  }

  // Atualizar suportes
  const supportsList = document.getElementById('supportsList');
  if (supportsList) {
    if (data.supports && data.supports.length > 0) {
      supportsList.innerHTML = data.supports
        .map(level => renderLevelItem(level, 'support'))
        .join('');
    } else {
      supportsList.innerHTML = '<div class="level-empty">Nenhum suporte ativo</div>';
    }
  }
}

function renderLevelItem(level, type) {
  const age = Date.now() / 1000 - level.time;
  const ageText = age < 60 ? `${Math.round(age)}s ago` : 
                 age < 3600 ? `${Math.round(age / 60)}m ago` : 
                 `${Math.round(age / 3600)}h ago`;

  return `
    <div class="level-item ${type}">
      <div class="level-poc">${level.poc.toFixed(2)}</div>
      <div class="level-vol">Vol: ${level.volume.toFixed(0)}</div>
      <div class="level-age">${ageText}</div>
    </div>
  `;
}

function renderLastBreak() {
  const breakCard = document.getElementById('lastBreakCard');
  if (!breakCard || !LIQUIDITY_STATE.lastBreak) return;

  const brk = LIQUIDITY_STATE.lastBreak;
  const isStructural = brk.isStructuralBreak ? '⭐ Structural' : '';
  const mechanism = brk.mechanism || 'UNDEFINED';
  const confidence = ((brk.confidence || 0) * 100).toFixed(0);

  const html = `
    <div class="break-header">
      <span class="break-type">${brk.type}</span>
      <span class="break-confidence">${confidence}%</span>
      ${isStructural ? `<span class="structural-badge">${isStructural}</span>` : ''}
    </div>
    <div class="break-details">
      <div><strong>Mecanismo:</strong> ${mechanism}</div>
      <div><strong>Delta:</strong> ${brk.delta.toFixed(4)}</div>
      <div><strong>Broken Level:</strong> ${brk.brokenLevel.poc.toFixed(2)}</div>
      <div><strong>Breaking Cluster:</strong> ${brk.breakingCluster.poc.toFixed(2)}</div>
    </div>
  `;

  breakCard.className = `last-break-card ${mechanism.toLowerCase()}`;
  breakCard.innerHTML = html;
}

function updateBreaksTable(data) {
  if (!data) return;

  LIQUIDITY_STATE.breaks = data || [];
  const tbody = document.getElementById('breaksTableBody');
  if (!tbody) return;

  if (!data || data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">Nenhum break ainda</td></tr>';
    return;
  }

  tbody.innerHTML = data
    .slice(-20)  // Últimos 20
    .reverse()   // Mais recentes primeiro
    .map((brk, idx) => renderBreakRow(brk, idx))
    .join('');
}

function renderBreakRow(brk, idx) {
  const time = new Date(brk.breakingCluster.time * 1000).toLocaleTimeString();
  const type = brk.type === 'SELLERS_REPRICED_HIGHER' ? '📈 Sellers' : '📉 Buyers';
  const mechanism = brk.mechanism || 'UNDEFINED';
  const confidence = ((brk.confidence || 0) * 100).toFixed(0);
  const structural = brk.isStructuralBreak ? '⭐' : '';

  return `
    <tr class="${mechanism.toLowerCase()}">
      <td>${time}</td>
      <td class="type-cell">${type}</td>
      <td>${mechanism}</td>
      <td>
        <div class="confidence-bar" style="--confidence: ${confidence}%">
          <span>${confidence}%</span>
        </div>
      </td>
      <td>${brk.delta.toFixed(4)}</td>
      <td>${structural}</td>
    </tr>
  `;
}

function updateStructuralBreaks(data) {
  if (!data) return;

  const list = document.getElementById('structuralBreaksList');
  if (!list) return;

  if (!data || data.length === 0) {
    list.innerHTML = '<div class="structural-empty">Nenhum break estrutural ainda</div>';
    return;
  }

  list.innerHTML = data
    .slice(-10)  // Últimos 10
    .reverse()
    .map(brk => renderStructuralBreakItem(brk))
    .join('');
}

function renderStructuralBreakItem(brk) {
  const time = new Date(brk.breakingCluster.time * 1000).toLocaleString();
  const age = brk.extra?.age ? `Age: ${(brk.extra.age / 60).toFixed(1)} min` : '';
  const confidence = ((brk.confidence || 0) * 100).toFixed(0);

  return `
    <div class="structural-break-item">
      <div class="structural-time">${time}</div>
      <div class="structural-info">
        <div><strong>${brk.mechanism}</strong> - ${confidence}%</div>
        <div>
          Nível Quebrado: ${brk.brokenLevel.poc.toFixed(2)} | 
          Delta: ${brk.delta.toFixed(4)}
        </div>
        ${age ? `<div>${age}</div>` : ''}
      </div>
    </div>
  `;
}

function addNewBreak(breakData) {
  // Adiciona novo break à tabela
  if (!LIQUIDITY_STATE.breaks) LIQUIDITY_STATE.breaks = [];

  LIQUIDITY_STATE.breaks.unshift(breakData);

  // Limita a 100 breaks em memória
  if (LIQUIDITY_STATE.breaks.length > 100) {
    LIQUIDITY_STATE.breaks = LIQUIDITY_STATE.breaks.slice(0, 100);
  }

  // Atualiza tabela
  updateBreaksTable(LIQUIDITY_STATE.breaks);

  // Mostra animação
  animateLiquidityBreakDetected(breakData);
}

function animateLiquidityBreakDetected(breakData) {
  // Pisca a badge de status
  const badge = document.getElementById('liquidityStatus');
  if (badge) {
    badge.style.animation = 'none';
    setTimeout(() => {
      badge.style.animation = 'pulse 2s infinite';
    }, 10);
  }

  // Toca notificação de som (opcional)
  playLiquidityBreakSound();
}

function playLiquidityBreakSound() {
  // Criar beep simples usando Web Audio API
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    oscillator.frequency.value = 800;
    oscillator.type = 'sine';

    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);

    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.1);
  } catch (e) {
    // Ignorar se não conseguir
  }
}

// ============================================================
// USER INTERACTIONS
// ============================================================

function toggleLiquidityPanel() {
  const panel = document.getElementById('liquidityPanel');
  if (!panel) return;

  LIQUIDITY_STATE.isOpen = !LIQUIDITY_STATE.isOpen;

  if (LIQUIDITY_STATE.isOpen) {
    panel.removeAttribute('hidden');

    // Solicitar dados ao backend
    if (window.ws && window.ws.readyState === WebSocket.OPEN) {
      window.ws.send(JSON.stringify({ type: 'get_liquidity_levels' }));
      window.ws.send(JSON.stringify({ type: 'get_liquidity_breaks', limit: 100 }));
      window.ws.send(JSON.stringify({ type: 'get_structural_breaks', limit: 20 }));
    }
  } else {
    panel.setAttribute('hidden', '');
  }

  const btn = document.getElementById('liquidityToggle');
  if (btn) {
    btn.classList.toggle('active', LIQUIDITY_STATE.isOpen);
  }
}

function changeLiquidityPreset(preset) {
  LIQUIDITY_STATE.preset = preset;

  if (window.ws && window.ws.readyState === WebSocket.OPEN) {
    window.ws.send(JSON.stringify({
      type: 'set_liquidity_preset',
      preset: preset,
    }));
  }

  console.log(`🔥 Liquidity Break Preset changed to: ${preset}`);
}

function updateLiquidityStatus(active) {
  const badge = document.getElementById('liquidityStatus');
  if (badge) {
    if (active) {
      badge.removeAttribute('hidden');
    }
  }
}

// ============================================================
// CHART INTEGRATION
// ============================================================

/**
 * Renderiza os níveis de suporte/resistência no chart
 * Deve ser chamado do app.js durante o render
 */
function renderLiquidityLevelsOnChart(ctx, canvasWidth, canvasHeight, priceScale) {
  if (!CONFIG.showLiquidityLevels) return;
  if (!LIQUIDITY_STATE.levels) return;

  const supportColor = CONFIG.liquiditySupport || '#4ecdc4';
  const resistanceColor = CONFIG.liquidityResistance || '#ff006e';

  // Desenhar resistências
  (LIQUIDITY_STATE.levels.resistances || []).forEach((level) => {
    const y = priceScale(level.poc);
    drawLiquidityLevel(ctx, y, resistanceColor, 'Resistance');
  });

  // Desenhar suportes
  (LIQUIDITY_STATE.levels.supports || []).forEach((level) => {
    const y = priceScale(level.poc);
    drawLiquidityLevel(ctx, y, supportColor, 'Support');
  });
}

function drawLiquidityLevel(ctx, y, color, label) {
  ctx.save();

  // Linha pontilhada
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 5]);
  ctx.globalAlpha = 0.6;

  ctx.beginPath();
  ctx.moveTo(0, y);
  ctx.lineTo(ctx.canvas.width, y);
  ctx.stroke();

  // Label
  ctx.globalAlpha = 1;
  ctx.fillStyle = color;
  ctx.font = 'bold 12px Arial';
  ctx.textAlign = 'right';
  ctx.fillText(label, ctx.canvas.width - 10, y - 5);

  ctx.restore();
}

/**
 * Renderiza os breaks no chart
 * Marca os pontos onde os breaks ocorreram
 */
function renderLiquidityBreaksOnChart(ctx, canvasWidth, canvasHeight, timeScale, priceScale) {
  if (!LIQUIDITY_STATE.breaks) return;

  LIQUIDITY_STATE.breaks.forEach((brk) => {
    const x = timeScale(brk.breakingCluster.time);
    const y = priceScale(brk.breakingCluster.poc);

    const color = brk.type === 'SELLERS_REPRICED_HIGHER' 
      ? (CONFIG.liquidityBuyBreak || '#4ecdc4')
      : (CONFIG.liquiditySellBreak || '#ff006e');

    drawLiquidityBreakMarker(ctx, x, y, color, brk);
  });
}

function drawLiquidityBreakMarker(ctx, x, y, color, breakData) {
  ctx.save();

  const size = 6;

  // Círculo externo
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.globalAlpha = 0.8;
  ctx.beginPath();
  ctx.arc(x, y, size, 0, Math.PI * 2);
  ctx.stroke();

  // Ponto interno
  ctx.fillStyle = color;
  ctx.globalAlpha = 1;
  ctx.beginPath();
  ctx.arc(x, y, size / 2, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();
}

// ============================================================
// EXPORTS
// ============================================================

window.toggleLiquidityPanel = toggleLiquidityPanel;
window.changeLiquidityPreset = changeLiquidityPreset;
window.renderLiquidityLevelsOnChart = renderLiquidityLevelsOnChart;
window.renderLiquidityBreaksOnChart = renderLiquidityBreaksOnChart;