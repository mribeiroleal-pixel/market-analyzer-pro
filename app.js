// ====================================================================
// MARKET ANALYST PRO — 6 ANALISTAS COM TODAS AS MELHORIAS
// (extraído do HTML antigo e ajustado para arquivo separado)
// ====================================================================

// ---------- CONFIG ----------
let CONFIG = {
  bg: '#0a0e17',
  bgPanel: '#111827',
  bull: '#00e676',
  bear: '#ff1744',
  bullDark: '#004d40',
  bearDark: '#4a0000',
  bullBody: '#00c853',
  bearBody: '#d50000',
  highlight: '#ffd740',
  accent: '#ff6b35',
  aggressive: '#ff6b35',
  passive: '#4ecdc4',
  grid: '#1a2332',
  gridStrong: '#2a3a4d',
  text: '#8899aa',
  textStrong: '#e2e8f0',
  crosshair: '#546e7a',
  absorptionBuy: '#00e676',
  absorptionSell: '#ff5252',
  clusterGap: 4,
  histogramBullColor: '#00e676',
  histogramBearColor: '#ff1744',
  histogramOpacity: 85,
  wickWarningThreshold: 50,
  pocColor: '#ffd740',
  currentPriceColor: '#00bcd4',
  clusterOpacity: 70,
  clusterBorderWidth: 1.5,
  clusterBorderColor: '#ffffff',
  showClusterBorder: true,
  wickColor: '#556677',
  wickWidth: 1,
  pocLineWidth: 3,
  showPOC: true,
  showCurrentPrice: true,
  showVolumeLabels: true,
  showWickWarning: true,
  showAbsorptionLevels: true,
  showImbalanceLevels: true,
  absorptionMarkerColor: '#ffff00',
  imbalanceMarkerColor: '#ff00ff',
  drawColor: '#ffd740',
  drawOpacity: 80,
  drawLineWidth: 1.5
};

const WS_URL = 'ws://localhost:8766';
const PRICE_WIDTH = 80;
let HISTOGRAM_RATIO = 0.25;
let HIST_SPLIT = 0.55;

// ---------- STATE ----------
let ws = null;
let isLive = false;
let clusters = [];
let threshold = 100;
let priceStep = 0.50;
let viewMode = 'hybrid';
let showEnginePanel = true;
let showCalibration = false;
let lastPrice = 0;
let lastSide = 'buy';
let totalTicks = 0;
let engineState = {};
let dataSource = 'searching';
let currentSymbol = 'XAUUSD';
let weightMode = 'price_weighted';

let selectedClusters = [];
let regionStartTime = 0;
let regionEndTime = 0;

// Symbol configurations
const SYMBOLS = {
  BTCUSD: { label: 'BTC/USD', dig: 2, delta_th: 200, step: 10.0 },
  XAUUSD: { label: 'XAU/USD', dig: 2, delta_th: 100, step: 0.50 },
  EURUSD: { label: 'EUR/USD', dig: 5, delta_th: 50, step: 0.0001 },
  GBPUSD: { label: 'GBP/USD', dig: 5, delta_th: 60, step: 0.0001 },
  USTEC:  { label: 'USTEC',   dig: 2, delta_th: 150, step: 1.0 }
};

// Clusters
let closedClusters = [];
let formingCluster = null;
let formingTicks = [];
let masterTicks = [];

// View state
let viewState = {
  offsetX: 0,
  offsetY: 0,
  scaleX: 1,
  scaleY: 1,
  isDragging: false,
  lastX: 0,
  lastY: 0
};

// Crosshair
let crosshair = { x: 0, y: 0, visible: false };

// Drawing tools
let drawTool = 'none';
let drawings = [];
let currentDrawing = null;
let selectedDrawing = null;
let nextDrawId = 1;

// Canvas
let canvas, ctx;
let chartW, chartH, histH, totalH;

// ===== MARKET ANALYST MARKER STATE =====
let activeMarker = null;
let markerPoints = [];
let isMarkerDrag = false;
let markerDragStart = null;

const MARKER_COLORS = {
  liquidity_break: '#FF6B35',
  absorption_zone: '#4ECDC4',
  imbalance_zone: '#FFD93D',
  entry_point: '#45B7D1',
  question: '#C084FC',
  region: '#3b82f6'
};

const MARKER_EMOJIS = {
  liquidity_break: '💥',
  absorption_zone: '🛡️',
  imbalance_zone: '🔥',
  entry_point: '🎯',
  question: '❓',
  region: '📊'
};
// render() está definida abaixo na seção RENDERING — não duplicar aqui

// ---------- MT5 STATUS BADGE ----------
/**
 * Atualiza o badge de status do MT5 (independente do WS).
 * source: 'MT5_LIVE' | 'MT5_SIMULATED' | null
 * mt5Connected: bool (opcional — passado pelo backend quando disponível)
 */
function updateMT5Badge(source, mt5Connected) {
  const badge = document.getElementById('mt5Status');
  if (!badge) return;

  badge.style.display = 'inline-flex';

  const isLiveSource = source === 'MT5_LIVE' || source === 'mt5';
  const isSimulated  = source === 'MT5_SIMULATED' || source === 'simulated';

  // mt5Connected pode vir explicitamente do backend
  const connected = (typeof mt5Connected === 'boolean') ? mt5Connected : isLiveSource;

  if (connected) {
    badge.className  = 'status-badge mt5-live';
    badge.textContent = '📡 MT5 CONECTADO';
  } else if (isSimulated) {
    badge.className  = 'status-badge mt5-sim';
    badge.textContent = '🔵 MT5 SIMULAÇÃO';
  } else {
    badge.className  = 'status-badge mt5-off';
    badge.textContent = '📡 MT5 OFFLINE';
  }
}

function hideMT5Badge() {
  const badge = document.getElementById('mt5Status');
  if (badge) badge.style.display = 'none';
}

// ---------- FUNÇÃO PARA CONTROLAR O PAINEL E A GRID ----------
function adjustGridForPanel(show) {
  const container = document.getElementById('chartContainer');
  if (!container) return;
  if (show) container.classList.add('with-panel');
  else container.classList.remove('with-panel');
  setTimeout(resize, 50);
}

// ---------- INITIALIZATION ----------
function init() {
  console.log('🚀 Inicializando Market Analyst Pro...');
  canvas = document.getElementById('chart');
  if (!canvas) {
    console.error('Canvas #chart não encontrado');
    return;
  }
  ctx = canvas.getContext('2d');
  resize();
  window.addEventListener('resize', resize);
  setupCanvasEvents();
  setupMarkerEvents();
  setupControls();
  render();
  toggleLive();
}

function resize() {
  if (!canvas || !ctx) return;
  const container = document.getElementById('chartContainer');
  if (!container) return;

  const w = container.clientWidth;
  const h = container.clientHeight;
  const dpr = window.devicePixelRatio || 1;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  totalH = h;
  histH = Math.floor(h * HISTOGRAM_RATIO);
  chartH = h - histH;
  chartW = w - PRICE_WIDTH;

  render();
}

// ---------- WEBSOCKET ----------
function connectWS() {
  console.log('🔌 Conectando WebSocket para:', WS_URL);

  if (ws && ws.readyState <= 1) {
    console.log('⚠️ WebSocket já existe, fechando...');
    ws.close();
  }

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('✅ WebSocket CONECTADO!');
    const wsStatus = document.getElementById('wsStatus');
    if (wsStatus) {
      wsStatus.className = 'status-badge connected';
      wsStatus.textContent = '⬤ WS CONECTADO';
    }

    // Envia switch_symbol primeiro; depois pede histórico com pequeno delay
    // para o backend ter tempo de acumular ticks antes de responder get_history
    ws.send(JSON.stringify({ type: 'switch_symbol', symbol: currentSymbol }));
    setTimeout(() => {
      if (ws && ws.readyState === 1) {
        ws.send(JSON.stringify({ type: 'get_history', symbol: currentSymbol, hours: 24 }));
      }
    }, 800);
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);

      if (msg.type === 'tick') {
        processTick(msg.data);
      } else if (msg.type === 'connected') {
        const src = msg.data?.source || 'unknown';
        dataSource = src;

        // Atualiza badge MT5 dedicado
        updateMT5Badge(src, msg.data?.mt5_connected);

        // Mantém compatibilidade com badge legado (binanceStatus) se existir
        const badge = document.getElementById('binanceStatus');
        if (badge) {
          badge.style.display = 'inline-flex';
          if (src === 'MT5_LIVE' || src === 'mt5') {
            badge.textContent = '⬤ MT5 EXNESS';
            badge.className = 'status-badge connected';
          } else {
            badge.textContent = '⬤ SIMULAÇÃO';
            badge.className = 'status-badge mt5-sim';
          }
        }

        const sourceLabel = document.getElementById('sourceLabel');
        if (sourceLabel) sourceLabel.textContent = src.toUpperCase();

        if (msg.data?.price_step) {
          priceStep = msg.data.price_step;
          syncStepSlider();
        }

        if (msg.data?.delta_th) {
          threshold = msg.data.delta_th;
          const thSlider = document.getElementById('thresholdSlider');
          const thValue = document.getElementById('thresholdValue');
          if (thSlider) thSlider.value = threshold;
          if (thValue) thValue.textContent = threshold >= 1000 ? `${threshold / 1000}k` : `${threshold}`;
        }
      } else if (msg.type === 'history') {
        const sym = msg.symbol || currentSymbol;
        const cfg = SYMBOLS[sym];
        if (cfg) {
          currentSymbol = sym;
          // NÃO sobrescreve threshold aqui — o usuário pode ter ajustado manualmente
          // priceStep pode ser sincronizado com o símbolo
          priceStep = cfg.step;
          syncStepSlider();
        }

        if (msg.ticks && msg.ticks.length > 0) {
          // ── Modo ticks brutos: reconstrói clusters com o threshold atual ──────
          const histTicks = msg.ticks.map((t) => ({
            price:               t.price,
            volume:              t.volume_synthetic || t.volume || 1,
            side:                t.side || 'buy',
            timestamp:           t.timestamp != null ? t.timestamp : Date.now() / 1000,
            bid:                 t.bid || t.price,
            ask:                 t.ask || t.price,
            is_absorption:       false,
            absorption_type:     null,
            absorption_strength: 0,
            composite_signal:    0,
            stacking_buy:        0,
            stacking_sell:       0
          }));

          fullReprocess(histTicks);  // usa threshold global atual
          totalTicks = histTicks.length;
          autoFitView();

          const sourceLabel = document.getElementById('sourceLabel');
          if (sourceLabel) sourceLabel.textContent = `${msg.count} ticks (${msg.hours || '?'}h)`;

          updateUI();
          render();

        } else if (msg.clusters && msg.clusters.length > 0) {
          // ── Backend enviou clusters do DB diretamente (sem ticks em memória) ──
          loadClustersFromDB(msg.clusters);
          autoFitView();

          const sourceLabel = document.getElementById('sourceLabel');
          if (sourceLabel) sourceLabel.textContent = `${msg.clusters.length} clusters (DB)`;

          updateUI();
          render();

        } else {
          // ── Sem dados: apenas atualiza label ─────────────────────────────────
          const sourceLabel = document.getElementById('sourceLabel');
          if (sourceLabel) sourceLabel.textContent = 'aguardando ticks...';
        }
      } else if (msg.type === 'clusters_list') {
        // ── Clusters do DB: exibe diretamente no gráfico sem threshold reprocess ─
        if (msg.data && msg.data.length > 0) {
          loadClustersFromDB(msg.data);
          autoFitView();
          const sourceLabel = document.getElementById('sourceLabel');
          if (sourceLabel) sourceLabel.textContent = `${msg.count} clusters (DB)`;
          updateUI();
          render();
        }
      } else if (msg.type === 'engine_status') {
        engineState = msg.data || {};
        // Atualiza badge MT5 se o backend enviar o campo mt5_connected
        if (typeof msg.data?.mt5_connected === 'boolean' || msg.data?.source) {
          updateMT5Badge(msg.data.source || dataSource, msg.data.mt5_connected);
        }
        updateEnginePanel();
      } else if (msg.type === 'analysis') {
        console.log('📊 ANÁLISE RECEBIDA DO BACKEND!');
        hideAiLoading();
        showAnalysis(msg.data);
        if (msg.data && msg.data.ai_signal) {
          renderAiSignal(msg.data.ai_signal);
        }
      } else if (msg.type === 'ai_signal') {
        console.log('🤖 AI SIGNAL:', msg.data);
        hideAiLoading();
        renderAiSignal(msg.data);
      } else if (msg.type === 'cluster_closed') {
        console.log('🔒 CLUSTER FECHADO:', msg.data?.pattern, msg.data?.confidence);
        lastClosedCluster = msg.data || null;
      } else if (msg.type === 'symbol_changed') {
        if (msg.config) {
          const sourceLabel = document.getElementById('sourceLabel');
          if (sourceLabel) sourceLabel.textContent = msg.symbol;
        }
      }
    } catch (err) {
      console.log('❌ Erro ao processar mensagem:', err);
    }
  };

  ws.onclose = () => {
    console.log('🔌 WebSocket FECHADO');
    const wsStatus = document.getElementById('wsStatus');
    const binanceStatus = document.getElementById('binanceStatus');

    if (wsStatus) {
      wsStatus.className = 'status-badge disconnected';
      wsStatus.textContent = '⬤ DESCONECTADO';
    }
    if (binanceStatus) binanceStatus.style.display = 'none';
    hideMT5Badge();

    if (isLive) setTimeout(connectWS, 3000);
  };

  ws.onerror = (err) => {
    console.log('❌ WebSocket ERRO:', err);
  };
}

function disconnectWS() {
  if (ws) {
    ws.close();
    ws = null;
  }

  const wsStatus = document.getElementById('wsStatus');
  const binanceStatus = document.getElementById('binanceStatus');

  if (wsStatus) {
    wsStatus.className = 'status-badge disconnected';
    wsStatus.textContent = '⬤ DESCONECTADO';
  }
  if (binanceStatus) binanceStatus.style.display = 'none';
  hideMT5Badge();
}

// ---------- TICK PROCESSING ----------
function processTick(data) {
  const tick = {
    price: data.price,
    volume: data.volume_synthetic || data.volume || 1,
    side: data.side || 'buy',
    timestamp: data.timestamp != null ? data.timestamp : Date.now() / 1000,
    bid: data.bid || data.price,
    ask: data.ask || data.price,
    is_absorption: data.is_absorption || false,
    absorption_type: data.absorption_type || null,
    absorption_strength: data.absorption_strength || 0,
    composite_signal: data.composite_signal || 0,
    stacking_buy: data.stacking_buy || 0,
    stacking_sell: data.stacking_sell || 0
  };

  lastPrice = tick.price;
  lastSide = tick.side;
  totalTicks++;

  if (data.engines) {
    engineState = data.engines;
    updateEnginePanel();
  }

  masterTicks.push(tick);
  addTickToForming(tick);

  clusters = [...closedClusters];
  if (formingCluster) clusters.push(formingCluster);

  // Log de diagnóstico a cada 50 ticks
  if (totalTicks % 50 === 0) {
    console.log(`[DIAG] ticks=${totalTicks} | clusters fechados=${closedClusters.length} | formingDelta=${formingCluster ? formingCluster.delta.toFixed(2) : 'N/A'} | vol=${tick.volume.toFixed(4)} | threshold=${threshold} | price=${tick.price}`);
  }

  // Auto-scroll: mantém o último cluster (ou forming) sempre visível à direita
  _autoScrollToLast();

  updateUI();
  render();
}

/**
 * Ajusta offsetX para manter o cluster mais recente visível.
 * Só age se o usuário não estiver navegando manualmente (modo live).
 */
function _autoScrollToLast() {
  if (!isLive || clusters.length === 0 || !chartW) return;

  const cw = Math.max(8, 40 * viewState.scaleX);
  const gap = CONFIG.clusterGap;
  // posição X do centro do último cluster
  const lastX = viewState.offsetX + (clusters.length - 1) * (cw + gap) + cw / 2;
  const margin = cw * 3;  // deixa margem à direita

  if (lastX > chartW - margin) {
    // empurra o offset para deixar último cluster visível
    viewState.offsetX -= (lastX - (chartW - margin));
  } else if (lastX < margin && clusters.length > 1) {
    // muito à esquerda (zoom out muito) — centraliza
    const visibleClusters = Math.max(1, Math.floor(chartW / (cw + gap)));
    const targetIdx = Math.max(0, clusters.length - visibleClusters);
    viewState.offsetX = -(targetIdx * (cw + gap)) + 20;
  }
}

function addTickToForming(tick) {
  const vol = tick.volume;
  const dp = priceStep > 0 ? Math.round(tick.price / priceStep) * priceStep : tick.price;

  if (!formingCluster) {
    const pl = priceStep > 0
      ? [{ price: dp, volumeBuy: tick.side === 'buy' ? vol : 0, volumeSell: tick.side === 'sell' ? vol : 0, volumeTotal: vol }]
      : [];

    formingCluster = {
      id: closedClusters.length,
      open: dp, high: dp, low: dp, close: dp,
      volumeBuy: tick.side === 'buy' ? vol : 0,
      volumeSell: tick.side === 'sell' ? vol : 0,
      volumeTotal: vol, volumeBody: vol, volumeWick: 0, wickPercent: 0,
      delta: tick.side === 'buy' ? vol : -vol,
      tickCount: 1,
      startTime: tick.timestamp,
      isClosed: false,
      poc: dp,
      priceLevels: pl,
      absorptionCount: tick.is_absorption ? 1 : 0,
      absorptionBuyCount: tick.absorption_type === 'buy_absorption' ? 1 : 0,
      absorptionSellCount: tick.absorption_type === 'sell_absorption' ? 1 : 0,
      maxAbsorptionStrength: tick.absorption_strength || 0,
      maxStackingBuy: tick.stacking_buy || 0,
      maxStackingSell: tick.stacking_sell || 0,
      compositeSignalAvg: tick.composite_signal || 0,
      absorptionLevels: tick.is_absorption ? [{ price: dp, type: tick.absorption_type, strength: tick.absorption_strength || 0 }] : [],
      imbalanceLevels: (tick.stacking_buy > 0 || tick.stacking_sell > 0)
        ? [{ price: dp, buy: tick.stacking_buy || 0, sell: tick.stacking_sell || 0 }]
        : []
    };

    formingTicks = [tick];
    return;
  }

  const c = formingCluster;
  c.close = dp;
  c.high = Math.max(c.high, dp);
  c.low = Math.min(c.low, dp);
  c.volumeTotal += vol;
  c.tickCount++;
  formingTicks.push(tick);

  if (tick.side === 'buy') {
    c.volumeBuy += vol;
    c.delta += vol;
  } else {
    c.volumeSell += vol;
    c.delta -= vol;
  }

  if (Math.abs(c.delta) >= threshold) {
    c.isClosed = true;
    c.endTime = tick.timestamp;
    recalcBodyWick(c);
    closedClusters.push(c);
    formingCluster = null;
    formingTicks = [];
    return;
  }

  if (priceStep > 0) {
    const ex = c.priceLevels.find((l) => l.price === dp);
    if (ex) {
      if (tick.side === 'buy') ex.volumeBuy += vol;
      else ex.volumeSell += vol;
      ex.volumeTotal += vol;
    } else {
      c.priceLevels.push({
        price: dp,
        volumeBuy: tick.side === 'buy' ? vol : 0,
        volumeSell: tick.side === 'sell' ? vol : 0,
        volumeTotal: vol
      });
    }

    let maxV = 0;
    for (const l of c.priceLevels) {
      if (l.volumeTotal > maxV) {
        maxV = l.volumeTotal;
        c.poc = l.price;
      }
    }
  }

  if (tick.is_absorption) {
    c.absorptionCount++;
    if (tick.absorption_type === 'buy_absorption') c.absorptionBuyCount++;
    if (tick.absorption_type === 'sell_absorption') c.absorptionSellCount++;
    c.maxAbsorptionStrength = Math.max(c.maxAbsorptionStrength, tick.absorption_strength || 0);
    if (!c.absorptionLevels) c.absorptionLevels = [];
    c.absorptionLevels.push({ price: dp, type: tick.absorption_type, strength: tick.absorption_strength || 0 });
  }

  if ((tick.stacking_buy || 0) > 0 || (tick.stacking_sell || 0) > 0) {
    if (!c.imbalanceLevels) c.imbalanceLevels = [];
    c.imbalanceLevels.push({ price: dp, buy: tick.stacking_buy || 0, sell: tick.stacking_sell || 0 });
  }

  c.maxStackingBuy = Math.max(c.maxStackingBuy, tick.stacking_buy || 0);
  c.maxStackingSell = Math.max(c.maxStackingSell, tick.stacking_sell || 0);

  const n = c.tickCount;
  c.compositeSignalAvg = (c.compositeSignalAvg * (n - 1) + (tick.composite_signal || 0)) / n;
}

function recalcBodyWick(cluster) {
  const bodyHigh = Math.max(cluster.open, cluster.close);
  const bodyLow = Math.min(cluster.open, cluster.close);
  let bodyVol = 0;
  let wickVol = 0;

  for (const level of cluster.priceLevels) {
    if (level.price >= bodyLow && level.price <= bodyHigh) bodyVol += level.volumeTotal;
    else wickVol += level.volumeTotal;
  }

  cluster.volumeBody = bodyVol;
  cluster.volumeWick = wickVol;
  cluster.wickPercent = cluster.volumeTotal > 0 ? (wickVol / cluster.volumeTotal) * 100 : 0;
}

function fullReprocess(tickArray) {
  closedClusters = [];
  formingCluster = null;
  formingTicks = [];
  masterTicks = [...tickArray];

  for (const tick of tickArray) addTickToForming(tick);

  clusters = [...closedClusters];
  if (formingCluster) clusters.push(formingCluster);
}

function getAllTicks() {
  return masterTicks;
}

// ---------- CLUSTER HISTORY FROM DB ----------
/**
 * Carrega clusters pré-construídos do DB diretamente no gráfico.
 * Esses clusters NÃO passam pelo reprocessamento de threshold —
 * foram fechados conforme o threshold vigente na época.
 * Para reprocessar com novo threshold, use loadHistory(h) com ticks brutos.
 */
function loadClustersFromDB(dbClusters) {
  // Ordena cronologicamente (DB retorna em ordem desc)
  const sorted = [...dbClusters].sort((a, b) =>
    (a.timestamp_open || a.timestamp_close || 0) - (b.timestamp_open || b.timestamp_close || 0)
  );

  const converted = sorted.map((r, idx) => {
    const open  = r.price_open  || r.price_close || 0;
    const close = r.price_close || open;
    const high  = r.price_high  || Math.max(open, close);
    const low   = r.price_low   || Math.min(open, close);
    const delta = r.delta_final || (r.vol_buy - r.vol_sell) || 0;
    const volB  = r.vol_buy   || 0;
    const volS  = r.vol_sell  || 0;
    const volT  = r.vol_total || (volB + volS) || 1;

    return {
      id:               idx,
      open,
      close,
      high,
      low,
      volumeBuy:        volB,
      volumeSell:       volS,
      volumeTotal:      volT,
      volumeBody:       volT * (1 - (r.wick_ratio_top || 0) - (r.wick_ratio_bot || 0)),
      volumeWick:       0,
      wickPercent:      ((r.wick_ratio_top || 0) + (r.wick_ratio_bot || 0)) * 100,
      delta,
      tickCount:        r.tick_count    || 1,
      startTime:        r.timestamp_open  || 0,
      endTime:          r.timestamp_close || 0,
      isClosed:         true,
      poc:              r.poc_price || close,
      priceLevels:      [],
      absorptionCount:  0,
      absorptionBuyCount: 0,
      absorptionSellCount: 0,
      maxAbsorptionStrength: 0,
      maxStackingBuy:   0,
      maxStackingSell:  0,
      compositeSignalAvg: 0,
      absorptionLevels: [],
      imbalanceLevels:  [],
      // campos extras do DB
      pattern:          r.pattern,
      patternConf:      r.pattern_confidence,
      outcome:          r.outcome,
      analystSignals:   r.analyst_signals,
      fromDB:           true,
    };
  });

  closedClusters = converted;
  formingCluster = null;
  formingTicks   = [];
  // masterTicks permanece vazio — não há ticks brutos
  // Se o usuário alterar o threshold, autoFitView continuará funcionando
  // (apenas não haverá reprocessamento pois não há ticks brutos)
  clusters = [...closedClusters];

  if (converted.length > 0) {
    const last = converted[converted.length - 1];
    lastPrice = last.close || last.poc || 0;
    lastSide  = last.delta >= 0 ? 'buy' : 'sell';
    totalTicks = converted.reduce((s, c) => s + (c.tickCount || 0), 0);
  }
}

// ---------- FUNÇÃO yToPrice ----------
function yToPrice(y) {
  if (clusters.length === 0) return 0;

  let priceHigh = -Infinity;
  let priceLow = Infinity;
  for (const c of clusters) {
    priceHigh = Math.max(priceHigh, c.high);
    priceLow = Math.min(priceLow, c.low);
  }

  const range = (priceHigh - priceLow) * viewState.scaleY;
  const center = (priceHigh + priceLow) / 2;
  const pad = range * 0.15;
  const viewHigh = center + range / 2 + pad + viewState.offsetY;
  const viewLow = center - range / 2 - pad + viewState.offsetY;

  if (Math.abs(viewHigh - viewLow) < 0.000001) return (viewHigh + viewLow) / 2;
  return viewHigh - (y / chartH) * (viewHigh - viewLow);
}

// ===== REGIÃO =====
function calculateRegionStats(clusterIndices) {
  if (!clusterIndices || clusterIndices.length === 0) return null;

  const regionClusters = clusterIndices.map((i) => clusters[i]).filter(Boolean);
  if (regionClusters.length === 0) return null;

  const first = regionClusters[0];
  const last = regionClusters[regionClusters.length - 1];

  let totalVolume = 0;
  let totalDelta = 0;
  let buyVolume = 0;
  let sellVolume = 0;
  let ticksCount = 0;

  regionClusters.forEach((c) => {
    totalVolume += c.volumeTotal;
    totalDelta += c.delta;
    buyVolume += c.volumeBuy;
    sellVolume += c.volumeSell;
    ticksCount += c.tickCount;
  });

  return {
    startPrice: first.open,
    endPrice: last.close,
    priceChange: last.close - first.open,
    priceChangePercent: ((last.close / first.open) - 1) * 100,
    totalVolume,
    netDelta: totalDelta,
    buyRatio: buyVolume / (totalVolume || 1),
    clusterCount: regionClusters.length,
    tickCount: ticksCount,
    duration: ((last.endTime || last.startTime) - first.startTime),
    avgDeltaPerCluster: totalDelta / regionClusters.length
  };
}

function renderSelectedClusters() {
  if (!selectedClusters || selectedClusters.length === 0) return;
  if (!ctx) return;

  const clusterWidth = Math.max(8, 40 * viewState.scaleX);
  const clusterToX = (i) => viewState.offsetX + i * (clusterWidth + CONFIG.clusterGap) + clusterWidth / 2;

  const firstIdx = Math.min(...selectedClusters);
  const lastIdx = Math.max(...selectedClusters);

  const x1 = clusterToX(firstIdx) - clusterWidth / 2;
  const x2 = clusterToX(lastIdx) + clusterWidth / 2;

  ctx.fillStyle = 'rgba(59, 130, 246, 0.15)';
  ctx.fillRect(x1, 0, x2 - x1, chartH);

  ctx.strokeStyle = '#3b82f6';
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 3]);
  ctx.strokeRect(x1, 0, x2 - x1, chartH);
  ctx.setLineDash([]);
}

// ---------- RENDERING ----------
function render() {
  if (!ctx || !canvas) return;
  if (!chartW || !chartH) { resize(); return; } // garante dimensões antes de desenhar

  const w = canvas.width / (window.devicePixelRatio || 1);
  const h = canvas.height / (window.devicePixelRatio || 1);

  ctx.fillStyle = CONFIG.bg;
  ctx.fillRect(0, 0, w, h);

  if (clusters.length === 0) {
    ctx.fillStyle = CONFIG.text;
    ctx.font = '14px JetBrains Mono';
    ctx.textAlign = 'center';
    ctx.fillText('Aguardando ticks do MT5...', w / 2, h / 2 - 10);
    ctx.font = '11px JetBrains Mono';
    ctx.fillStyle = CONFIG.crosshair;
    ctx.fillText('Clique ▶ LIVE para conectar ao MT5 Exness', w / 2, h / 2 + 12);
    return;
  }

  const clusterWidth = Math.max(8, 40 * viewState.scaleX);

  let priceHigh = -Infinity;
  let priceLow = Infinity;
  for (const c of clusters) {
    priceHigh = Math.max(priceHigh, c.high);
    priceLow = Math.min(priceLow, c.low);
  }

  const range = (priceHigh - priceLow) * viewState.scaleY;
  const center = (priceHigh + priceLow) / 2;
  const pad = range * 0.15;
  const viewHigh = center + range / 2 + pad + viewState.offsetY;
  const viewLow = center - range / 2 - pad + viewState.offsetY;

  const priceToY = (p) => {
    const r = viewHigh - viewLow;
    if (r === 0 || !isFinite(r)) return chartH / 2;
    const y = ((viewHigh - p) / r) * chartH;
    return isFinite(y) ? y : chartH / 2;
  };

  const clusterToX = (i) => viewState.offsetX + i * (clusterWidth + CONFIG.clusterGap) + clusterWidth / 2;

  let maxVolume = 1;
  for (const c of clusters) maxVolume = Math.max(maxVolume, c.volumeTotal);

  // Grid
  ctx.lineWidth = 0.5;
  const gridLines = 10;
  const gridStep = (viewHigh - viewLow) / gridLines;
  for (let i = 0; i <= gridLines; i++) {
    const y = (chartH / gridLines) * i;
    const price = viewHigh - gridStep * i;
    ctx.strokeStyle = i % 2 === 0 ? `${CONFIG.gridStrong}66` : `${CONFIG.grid}44`;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(chartW, y);
    ctx.stroke();

    ctx.fillStyle = CONFIG.text;
    ctx.font = '9px JetBrains Mono';
    ctx.textAlign = 'left';
    ctx.fillText(price.toFixed(2), chartW + 5, y + 3);
  }

  ctx.strokeStyle = CONFIG.gridStrong;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(chartW, 0);
  ctx.lineTo(chartW, totalH);
  ctx.stroke();

  // Current price line
  if (lastPrice > 0 && lastPrice >= viewLow && lastPrice <= viewHigh) {
    const cpY = priceToY(lastPrice);
    ctx.strokeStyle = CONFIG.currentPriceColor;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([8, 4]);
    ctx.beginPath();
    ctx.moveTo(0, cpY);
    ctx.lineTo(chartW, cpY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = CONFIG.currentPriceColor;
    ctx.fillRect(chartW + 1, cpY - 10, PRICE_WIDTH - 6, 20);

    ctx.fillStyle = '#000';
    ctx.font = 'bold 10px JetBrains Mono';
    ctx.textAlign = 'left';
    ctx.fillText(`$${lastPrice.toFixed(2)}`, chartW + 4, cpY + 4);

    ctx.fillStyle = CONFIG.currentPriceColor;
    ctx.beginPath();
    ctx.moveTo(chartW, cpY);
    ctx.lineTo(chartW - 6, cpY - 5);
    ctx.lineTo(chartW - 6, cpY + 5);
    ctx.closePath();
    ctx.fill();
  }

  renderSelectedClusters();

  // Clusters
  for (let idx = 0; idx < clusters.length; idx++) {
    const cluster = clusters[idx];
    const centerX = clusterToX(idx);
    const x = centerX - clusterWidth / 2;
    const cw = clusterWidth;

    if (centerX < -cw || centerX > chartW + cw) continue;

    const isBull = cluster.close >= cluster.open;
    const deltaIntensity = Math.min(1, Math.abs(cluster.delta) / (threshold * 0.8));

    const highY = priceToY(cluster.high);
    const lowY = priceToY(cluster.low);

    ctx.strokeStyle = CONFIG.wickColor;
    ctx.lineWidth = CONFIG.wickWidth;
    ctx.beginPath();
    ctx.moveTo(centerX, highY);
    ctx.lineTo(centerX, lowY);
    ctx.stroke();

    let bodyTop = priceToY(Math.max(cluster.open, cluster.close));
    let bodyBottom = priceToY(Math.min(cluster.open, cluster.close));
    if (!isFinite(bodyTop)) bodyTop = chartH / 2 - 5;
    if (!isFinite(bodyBottom)) bodyBottom = chartH / 2 + 5;
    const bodyH = Math.max(3, bodyBottom - bodyTop);

    const baseAlpha = (CONFIG.clusterOpacity / 100) * (0.3 + deltaIntensity * 0.7);
    const alphaHex = Math.round(Math.min(255, baseAlpha * 255)).toString(16).padStart(2, '0');
    const borderAlpha = Math.round(Math.min(255, (0.5 + deltaIntensity * 0.5) * 255)).toString(16).padStart(2, '0');

    if (viewMode === 'clean') {
      ctx.fillStyle = (isBull ? CONFIG.bullBody : CONFIG.bearBody) + alphaHex;
      ctx.fillRect(x, bodyTop, cw, bodyH);
    } else {
      const grad = ctx.createLinearGradient(x, bodyTop, x, bodyTop + bodyH);
      if (isBull) {
        grad.addColorStop(0, CONFIG.bull + alphaHex);
        grad.addColorStop(0.5, CONFIG.bullBody + alphaHex);
        grad.addColorStop(1, CONFIG.bullDark + alphaHex);
      } else {
        grad.addColorStop(0, CONFIG.bearDark + alphaHex);
        grad.addColorStop(0.5, CONFIG.bearBody + alphaHex);
        grad.addColorStop(1, CONFIG.bear + alphaHex);
      }
      ctx.fillStyle = grad;
      ctx.fillRect(x, bodyTop, cw, bodyH);
    }

    if (CONFIG.showClusterBorder && CONFIG.clusterBorderWidth > 0) {
      ctx.strokeStyle = CONFIG.clusterBorderColor + borderAlpha;
      ctx.lineWidth = CONFIG.clusterBorderWidth;
      ctx.strokeRect(x, bodyTop, cw, bodyH);
    }

    // Delta label
    if (viewState.scaleX >= 0.9 && bodyH > 14) {
      ctx.fillStyle = `#ffffff${borderAlpha}`;
      ctx.font = 'bold 8px JetBrains Mono';
      ctx.textAlign = 'center';

      const deltaRounded = Math.round(cluster.delta * 10) / 10;
      const deltaText = (deltaRounded >= 0 ? '+' : '') +
        (Math.abs(deltaRounded) >= 1000 ? `${(deltaRounded / 1000).toFixed(1)}k` : deltaRounded.toFixed(1));

      ctx.fillText(deltaText, centerX, bodyTop + bodyH / 2 + 3);
    }

    // POC
    if (cluster.priceLevels.length > 0) {
      const pocY = priceToY(cluster.poc);

      ctx.strokeStyle = `${CONFIG.pocColor}22`;
      ctx.lineWidth = 7;
      ctx.beginPath();
      ctx.moveTo(x - 6, pocY);
      ctx.lineTo(x + cw + 6, pocY);
      ctx.stroke();

      ctx.strokeStyle = `${CONFIG.pocColor}55`;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(x - 5, pocY);
      ctx.lineTo(x + cw + 5, pocY);
      ctx.stroke();

      ctx.strokeStyle = CONFIG.pocColor;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x - 4, pocY);
      ctx.lineTo(x + cw + 4, pocY);
      ctx.stroke();

      ctx.fillStyle = CONFIG.pocColor;
      ctx.beginPath();
      ctx.moveTo(x - 6, pocY);
      ctx.lineTo(x - 3, pocY - 3);
      ctx.lineTo(x, pocY);
      ctx.lineTo(x - 3, pocY + 3);
      ctx.closePath();
      ctx.fill();

      if (viewState.scaleX >= 1.2) {
        ctx.fillStyle = CONFIG.pocColor;
        ctx.font = 'bold 7px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText('POC', centerX, pocY - 5);
      }
    }

    // Footprint
    if (viewMode !== 'clean' && cluster.priceLevels.length > 0) {
      const maxLevelVol = Math.max(...cluster.priceLevels.map((l) => l.volumeTotal));
      const barRatio = viewMode === 'raw' ? 0.9 : 0.65;

      for (const level of cluster.priceLevels) {
        const ly = priceToY(level.price);
        const volRatio = level.volumeTotal / maxLevelVol;
        const barW = volRatio * cw * barRatio;
        const levelAlpha = Math.round(80 + volRatio * 175).toString(16).padStart(2, '0');
        const isBuyDom = level.volumeBuy >= level.volumeSell;

        ctx.fillStyle = (isBuyDom ? CONFIG.histogramBullColor : CONFIG.histogramBearColor) + levelAlpha;
        ctx.fillRect(centerX - barW / 2, ly - 1.5, barW, 3);

        if (volRatio > 0.7) {
          ctx.fillStyle = (isBuyDom ? '#b9f6ca' : '#ffcdd2') + '66';
          ctx.fillRect(centerX - barW / 2, ly - 0.5, barW, 1);
        }

        if (viewMode === 'raw' && viewState.scaleX >= 1.5 && level.volumeTotal > 0) {
          ctx.fillStyle = isBuyDom ? `${CONFIG.bull}cc` : `${CONFIG.bear}cc`;
          ctx.font = '6px JetBrains Mono';
          ctx.textAlign = 'center';
          ctx.fillText(level.volumeTotal.toString(), centerX, ly + 6);
        }
      }

      if (CONFIG.showAbsorptionLevels && cluster.absorptionLevels && cluster.absorptionLevels.length > 0) {
        for (const abs of cluster.absorptionLevels) {
          const ay = priceToY(abs.price);
          const dotR = Math.max(2, Math.min(4, viewState.scaleX * 2.5));
          const isBuyAbs = abs.type === 'buy_absorption';
          const dotColor = isBuyAbs ? CONFIG.absorptionBuy : CONFIG.absorptionSell;

          ctx.shadowColor = dotColor;
          ctx.shadowBlur = 6;
          ctx.fillStyle = dotColor;
          ctx.beginPath();
          ctx.arc(x + cw - dotR - 2, ay, dotR, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;

          ctx.fillStyle = '#ffffff';
          ctx.beginPath();
          ctx.arc(x + cw - dotR - 2, ay, dotR * 0.4, 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = `${dotColor}55`;
          ctx.lineWidth = 0.5;
          ctx.setLineDash([2, 2]);
          ctx.beginPath();
          ctx.moveTo(x, ay);
          ctx.lineTo(x + cw, ay);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }

      if (CONFIG.showImbalanceLevels && cluster.imbalanceLevels && cluster.imbalanceLevels.length > 0) {
        for (const imb of cluster.imbalanceLevels) {
          const iy = priceToY(imb.price);
          const imbColor = CONFIG.imbalanceMarkerColor;
          const dotR = Math.max(1.5, Math.min(3, viewState.scaleX * 2));

          ctx.fillStyle = imbColor;
          ctx.beginPath();
          ctx.moveTo(x + dotR + 1, iy);
          ctx.lineTo(x + dotR + 1 + dotR, iy - dotR);
          ctx.lineTo(x + dotR + 1 + dotR * 2, iy);
          ctx.lineTo(x + dotR + 1 + dotR, iy + dotR);
          ctx.closePath();
          ctx.fill();

          ctx.fillStyle = `${imbColor}44`;
          ctx.fillRect(x, iy - 0.5, cw * 0.15, 1);
        }
      }
    }

    if (viewState.scaleX >= 1) {
      ctx.font = '7px JetBrains Mono';
      ctx.textAlign = 'center';

      ctx.fillStyle = '#667788';
      ctx.fillText(`W:${cluster.volumeWick}`, centerX, lowY + 10);

      ctx.fillStyle = isBull ? `${CONFIG.bull}cc` : `${CONFIG.bear}cc`;
      ctx.fillText(`B:${cluster.volumeBody}`, centerX, highY - 4);
    }

    if (!cluster.isClosed) {
      ctx.strokeStyle = CONFIG.highlight;
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 3]);
      ctx.strokeRect(x - 1, bodyTop - 1, cw + 2, bodyH + 2);
      ctx.setLineDash([]);

      ctx.shadowColor = CONFIG.highlight;
      ctx.shadowBlur = 6;
      ctx.strokeStyle = `${CONFIG.highlight}44`;
      ctx.lineWidth = 1;
      ctx.strokeRect(x - 2, bodyTop - 2, cw + 4, bodyH + 4);
      ctx.shadowBlur = 0;
    }

    if (cluster.wickPercent >= CONFIG.wickWarningThreshold) {
      const warningY = lowY + 16;
      ctx.shadowColor = CONFIG.highlight;
      ctx.shadowBlur = 8;

      ctx.fillStyle = CONFIG.highlight;
      ctx.beginPath();
      ctx.arc(centerX, warningY, 5, 0, Math.PI * 2);
      ctx.fill();

      ctx.shadowBlur = 0;
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(centerX, warningY, 2, 0, Math.PI * 2);
      ctx.fill();

      if (viewState.scaleX >= 0.8) {
        ctx.fillStyle = CONFIG.highlight;
        ctx.font = 'bold 8px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText(`${cluster.wickPercent.toFixed(0)}%`, centerX, warningY + 13);
      }
    }

    if (cluster.absorptionCount > 0) {
      const ms = Math.min(6, Math.max(3, cw * 0.3));

      if (cluster.absorptionBuyCount > cluster.absorptionSellCount) {
        ctx.fillStyle = CONFIG.absorptionBuy;
        ctx.beginPath();
        ctx.moveTo(centerX, lowY + ms * 3);
        ctx.lineTo(centerX - ms, lowY + ms * 3 + ms * 1.5);
        ctx.lineTo(centerX + ms, lowY + ms * 3 + ms * 1.5);
        ctx.closePath();
        ctx.fill();

        if (cluster.absorptionBuyCount > 1 && viewState.scaleX >= 0.8) {
          ctx.fillStyle = CONFIG.absorptionBuy;
          ctx.font = 'bold 7px JetBrains Mono';
          ctx.textAlign = 'center';
          ctx.fillText(`${cluster.absorptionBuyCount}`, centerX, lowY + ms * 3 + ms * 1.5 + 10);
        }
      } else if (cluster.absorptionSellCount > 0) {
        ctx.fillStyle = CONFIG.absorptionSell;
        ctx.beginPath();
        ctx.moveTo(centerX, highY - ms * 3);
        ctx.lineTo(centerX - ms, highY - ms * 3 - ms * 1.5);
        ctx.lineTo(centerX + ms, highY - ms * 3 - ms * 1.5);
        ctx.closePath();
        ctx.fill();

        if (cluster.absorptionSellCount > 1 && viewState.scaleX >= 0.8) {
          ctx.fillStyle = CONFIG.absorptionSell;
          ctx.font = 'bold 7px JetBrains Mono';
          ctx.textAlign = 'center';
          ctx.fillText(`${cluster.absorptionSellCount}`, centerX, highY - ms * 3 - ms * 1.5 - 4);
        }
      }
    }

    if (cluster.maxStackingBuy >= 2 || cluster.maxStackingSell >= 2) {
      const barW2 = Math.max(2, cw * 0.12);
      const bTop = bodyTop;
      const bH = Math.max(4, bodyH);

      if (cluster.maxStackingBuy >= 2) {
        const intensity = Math.min(cluster.maxStackingBuy / 5, 1);
        const alpha = Math.round(intensity * 200 + 55).toString(16).padStart(2, '0');
        ctx.fillStyle = CONFIG.absorptionBuy + alpha;
        ctx.fillRect(x - barW2 - 1, bTop, barW2, bH);

        if (viewState.scaleX >= 0.8) {
          ctx.fillStyle = CONFIG.absorptionBuy;
          ctx.font = 'bold 7px JetBrains Mono';
          ctx.textAlign = 'right';
          ctx.fillText(`S${cluster.maxStackingBuy}`, x - barW2 - 2, bTop + bH / 2 + 3);
        }
      }

      if (cluster.maxStackingSell >= 2) {
        const intensity = Math.min(cluster.maxStackingSell / 5, 1);
        const alpha = Math.round(intensity * 200 + 55).toString(16).padStart(2, '0');
        ctx.fillStyle = CONFIG.absorptionSell + alpha;
        ctx.fillRect(x + cw + 1, bTop, barW2, bH);

        if (viewState.scaleX >= 0.8) {
          ctx.fillStyle = CONFIG.absorptionSell;
          ctx.font = 'bold 7px JetBrains Mono';
          ctx.textAlign = 'left';
          ctx.fillText(`S${cluster.maxStackingSell}`, x + cw + barW2 + 2, bTop + bH / 2 + 3);
        }
      }
    }

    if (Math.abs(cluster.compositeSignalAvg) > 0.2 && viewState.scaleX >= 0.7) {
      const dotX = x + cw - 3;
      const dotY = highY - 2;
      const dotSize = Math.min(4, 2 + Math.abs(cluster.compositeSignalAvg) * 3);
      ctx.fillStyle = cluster.compositeSignalAvg > 0 ? `${CONFIG.absorptionBuy}88` : `${CONFIG.absorptionSell}88`;
      ctx.beginPath();
      ctx.arc(dotX, dotY, dotSize, 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Rótulo de padrão / outcome (clusters vindos do DB) ─────────────────
    if (cluster.fromDB && viewState.scaleX >= 0.7) {
      // Outcome dot (BULL=verde, BEAR=vermelho, NEUTRAL=cinza)
      if (cluster.outcome && cluster.outcome !== 'PENDENTE') {
        const outColor = cluster.outcome === 'BULL' ? CONFIG.bull
                       : cluster.outcome === 'BEAR' ? CONFIG.bear
                       : '#607d8b';
        ctx.fillStyle = outColor + 'cc';
        ctx.beginPath();
        ctx.arc(centerX, highY - 9, 3, 0, Math.PI * 2);
        ctx.fill();
      }

      // Pattern badge acima do cluster (visível com zoom >= 1)
      if (cluster.pattern && cluster.pattern !== 'UNKNOWN' && viewState.scaleX >= 1.0 && bodyH > 12) {
        const shortPat = cluster.pattern.length > 8 ? cluster.pattern.slice(0, 7) + '…' : cluster.pattern;
        ctx.fillStyle = '#ffffff33';
        ctx.font = '6px JetBrains Mono';
        ctx.textAlign = 'center';
        ctx.fillText(shortPat, centerX, highY - 14);
      }
    }
  }

  // Volume histogram
  if (histH > 0) {
    const histY = chartH;
    const labelH = 14;
    const gap = 4;
    const availH = histH - labelH - gap;
    const bar1H = availH * HIST_SPLIT;
    const bar2H = availH * (1 - HIST_SPLIT);

    const histGrad = ctx.createLinearGradient(0, histY, 0, histY + histH);
    histGrad.addColorStop(0, '#0f1923');
    histGrad.addColorStop(1, '#0a0e17');
    ctx.fillStyle = histGrad;
    ctx.fillRect(0, histY, chartW + PRICE_WIDTH, histH);

    ctx.strokeStyle = crosshair.visible && Math.abs(crosshair.y - histY) < 6 ? '#667788' : '#334455';
    ctx.lineWidth = crosshair.visible && Math.abs(crosshair.y - histY) < 6 ? 3 : 2;
    ctx.beginPath();
    ctx.moveTo(0, histY);
    ctx.lineTo(chartW + PRICE_WIDTH, histY);
    ctx.stroke();

    const midY = histY + labelH + bar1H + gap / 2;
    const nearMid = crosshair.visible && Math.abs(crosshair.y - midY) < 5;
    ctx.strokeStyle = nearMid ? '#8899aa' : '#1e2d3d';
    ctx.lineWidth = nearMid ? 2 : 0.5;
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(chartW, midY);
    ctx.stroke();

    ctx.font = 'bold 8px JetBrains Mono';
    ctx.textAlign = 'left';
    ctx.fillStyle = CONFIG.highlight;
    ctx.fillText('VOL', 4, histY + 10);
    ctx.fillStyle = '#667788';
    ctx.fillText('BODY/WICK', 4, midY + 10);

    for (let idx = 0; idx < clusters.length; idx++) {
      const cluster = clusters[idx];
      const centerX = clusterToX(idx);
      const x = centerX - clusterWidth / 2;
      if (centerX < -clusterWidth || centerX > chartW + clusterWidth) continue;

      const isBull = cluster.close >= cluster.open;
      const volRatio = cluster.volumeTotal / maxVolume;

      const v1H = volRatio * (bar1H - 4);
      const v1Y = histY + labelH + bar1H - v1H;

      const vGrad = ctx.createLinearGradient(x, v1Y, x, v1Y + v1H);
      if (isBull) {
        vGrad.addColorStop(0, CONFIG.bull);
        vGrad.addColorStop(1, `${CONFIG.bullDark}cc`);
      } else {
        vGrad.addColorStop(0, CONFIG.bear);
        vGrad.addColorStop(1, `${CONFIG.bearDark}cc`);
      }

      ctx.fillStyle = vGrad;
      ctx.fillRect(x + 0.5, v1Y, clusterWidth - 1, v1H);

      ctx.fillStyle = isBull ? '#b9f6ca55' : '#ffcdd255';
      ctx.fillRect(x + 0.5, v1Y, clusterWidth - 1, Math.min(2, v1H));

      if (volRatio > 0.3 && viewState.scaleX >= 0.8 && v1H > 10) {
        ctx.fillStyle = '#ffffffbb';
        ctx.font = '7px JetBrains Mono';
        ctx.textAlign = 'center';
        const vText = cluster.volumeTotal >= 1000 ? `${(cluster.volumeTotal / 1000).toFixed(1)}k` : `${cluster.volumeTotal}`;
        ctx.fillText(vText, centerX, v1Y + v1H / 2 + 3);
      }

      const v2H = volRatio * (bar2H - 4);
      const v2Y = midY + gap / 2;

      if (cluster.volumeTotal > 0) {
        const bodyPct = cluster.volumeBody / cluster.volumeTotal;
        const wickPct = cluster.volumeWick / cluster.volumeTotal;
        const bodyBarH = v2H * bodyPct;
        const wickBarH = v2H * wickPct;
        const baseY2 = v2Y + bar2H - v2H;

        if (wickBarH > 0) {
          const wickColor = cluster.wickPercent >= 50 ? '#ffd740' : '#455a64';
          ctx.fillStyle = `${wickColor}cc`;
          ctx.fillRect(x + 0.5, baseY2, clusterWidth - 1, wickBarH);
        }

        if (bodyBarH > 0) {
          ctx.fillStyle = isBull ? '#4caf50cc' : '#e53935cc';
          ctx.fillRect(x + 0.5, baseY2 + wickBarH, clusterWidth - 1, bodyBarH);
        }
      }

      if (cluster.wickPercent >= CONFIG.wickWarningThreshold) {
        ctx.fillStyle = `${CONFIG.highlight}aa`;
        ctx.fillRect(x, histY + histH - 3, clusterWidth, 3);
      }
    }
  }

  // Drawings (somente hline implementado nesta versão base)
  for (const d of drawings) {
    const isSel = d.id === selectedDrawing;
    const opacHex = Math.round((CONFIG.drawOpacity / 100) * 255).toString(16).padStart(2, '0');

    ctx.strokeStyle = d.color + opacHex;
    ctx.lineWidth = isSel ? CONFIG.drawLineWidth + 1 : CONFIG.drawLineWidth;

    if (d.type === 'hline') {
      const y = priceToY(d.p1.y);
      ctx.setLineDash(isSel ? [] : [6, 4]);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(chartW, y);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = d.color;
      ctx.font = 'bold 9px JetBrains Mono';
      ctx.textAlign = 'left';
      const symDig = (SYMBOLS[currentSymbol] || {}).dig || 2;
      ctx.fillText(d.p1.y.toFixed(symDig), chartW + 4, y - 3);

      if (isSel) {
        ctx.beginPath();
        ctx.arc(chartW - 8, y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  // Markers
  renderMarkers();

  // Crosshair
  if (crosshair.visible) {
    ctx.strokeStyle = CONFIG.crosshair;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);

    ctx.beginPath();
    ctx.moveTo(crosshair.x, 0);
    ctx.lineTo(crosshair.x, totalH);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(0, crosshair.y);
    ctx.lineTo(chartW, crosshair.y);
    ctx.stroke();

    ctx.setLineDash([]);

    if (crosshair.y < chartH) {
      const price = yToPrice(crosshair.y);
      ctx.fillStyle = CONFIG.highlight;
      ctx.fillRect(chartW + 1, crosshair.y - 10, PRICE_WIDTH - 6, 20);

      ctx.fillStyle = '#000';
      ctx.font = 'bold 10px JetBrains Mono';
      ctx.textAlign = 'left';
      ctx.fillText(price.toFixed(2), chartW + 4, crosshair.y + 4);
    }
  }

  // Header overlay
  ctx.fillStyle = '#0a0e17ee';
  ctx.fillRect(0, 0, 420, 34);

  ctx.fillStyle = CONFIG.highlight;
  ctx.font = 'bold 12px JetBrains Mono';
  ctx.textAlign = 'left';
  ctx.fillText(`${(SYMBOLS[currentSymbol] || {}).label || currentSymbol} | ${viewMode.toUpperCase()} | 6 Analistas`, 8, 13);

  ctx.fillStyle = CONFIG.text;
  ctx.font = '9px JetBrains Mono';
  const closedCount = clusters.filter((c) => c.isClosed).length;
  ctx.fillText(
    `Clusters: ${closedCount} | Δ: ${threshold >= 1000 ? (threshold / 1000) + 'k' : threshold} | Step: $${priceStep.toFixed(2)} | Zoom: ${(viewState.scaleX * 100).toFixed(0)}%`,
    8,
    26
  );

  // Legend (top right)
  ctx.fillStyle = `${CONFIG.bgPanel}dd`;
  ctx.fillRect(chartW - 260, 0, 260, 34);

  ctx.font = '7px JetBrains Mono';
  ctx.textAlign = 'left';
  ctx.fillStyle = CONFIG.absorptionBuy; ctx.fillText('▲ Buy Absorção', chartW - 255, 12);
  ctx.fillStyle = CONFIG.absorptionSell; ctx.fillText('▼ Sell Absorção', chartW - 255, 22);
  ctx.fillStyle = CONFIG.absorptionBuy; ctx.fillText('║ Stacking Buy', chartW - 170, 12);
  ctx.fillStyle = CONFIG.absorptionSell; ctx.fillText('║ Stacking Sell', chartW - 170, 22);
  ctx.fillStyle = CONFIG.aggressive; ctx.fillText('⚡ Agressivo', chartW - 85, 12);
  ctx.fillStyle = CONFIG.passive; ctx.fillText('🛡️ Passivo', chartW - 85, 22);

  // Minimap
  if (clusters.length > 2) {
    const mmW = 100, mmH = 24;
    const mmX = chartW - mmW - 8;
    const mmY = chartH - mmH - 8;

    ctx.fillStyle = CONFIG.bgPanel;
    ctx.fillRect(mmX, mmY, mmW, mmH);
    ctx.strokeStyle = CONFIG.gridStrong;
    ctx.lineWidth = 1;
    ctx.strokeRect(mmX, mmY, mmW, mmH);

    const mmScale = mmW / clusters.length;
    for (let i = 0; i < clusters.length; i++) {
      const c = clusters[i];
      const mx = mmX + i * mmScale;
      ctx.fillStyle = (c.close >= c.open ? CONFIG.bull : CONFIG.bear) + '77';
      ctx.fillRect(mx, mmY + 2, Math.max(1, mmScale), mmH - 4);

      if (c.wickPercent >= CONFIG.wickWarningThreshold) {
        ctx.fillStyle = `${CONFIG.highlight}cc`;
        ctx.fillRect(mx, mmY + mmH - 4, Math.max(1, mmScale), 3);
      }
      if (c.absorptionCount > 0) {
        ctx.fillStyle = (c.absorptionBuyCount > c.absorptionSellCount ? CONFIG.absorptionBuy : CONFIG.absorptionSell) + '88';
        ctx.fillRect(mx, mmY, Math.max(1, mmScale), 3);
      }
    }

    const totalWidth = clusters.length * (clusterWidth + CONFIG.clusterGap);
    const vpW = (chartW / totalWidth) * mmW;
    const vpX = mmX + (-viewState.offsetX / totalWidth) * mmW;

    ctx.strokeStyle = CONFIG.highlight;
    ctx.lineWidth = 2;
    ctx.strokeRect(Math.max(mmX, vpX), mmY, Math.min(vpW, mmW), mmH);
  }
}

// ===== MARKET ANALYST MARKER FUNCTIONS =====
function selMarker(type) {
  if (activeMarker === type) {
    activeMarker = null;
    canvas.style.cursor = 'crosshair';
  } else {
    activeMarker = type;
    canvas.style.cursor = 'cell';
  }

  document.querySelectorAll('[data-mk]').forEach((b) => {
    b.classList.toggle('active', b.dataset.mk === activeMarker);
  });

  console.log('🎯 Ferramenta selecionada:', activeMarker);
}

function clearMarkerPoints() {
  markerPoints = [];
  selectedClusters = [];
  closeAnalysis();
  render();
  console.log('🗑️ Marcadores limpos');
}

function closeAnalysis() {
  const panel = document.getElementById('analysisPanel');
  if (panel) panel.style.display = 'none';
  adjustGridForPanel(false);
}

// ===== SHOW ANALYSIS =====
function showAnalysis(data) {
  console.log('📊 ANÁLISE RECEBIDA:', data);
  if (!data || !data.analysts) {
    console.log('⚠️ Análise vazia ou sem analistas');
    return;
  }

  const panel = document.getElementById('analysisPanel');
  const content = document.getElementById('analysisPanelContent');
  if (!panel || !content) return;

  panel.style.display = 'block';
  adjustGridForPanel(true);

  let html = '';

  if (data.cluster_indices && data.cluster_indices.length > 1) {
    const stats = calculateRegionStats(data.cluster_indices);
    if (stats) {
      html += `<div style="background:#0d1321;border:1px solid #3b82f6;border-radius:6px;padding:10px;margin-bottom:10px">`;
      html += `<div style="font-size:12px;font-weight:700;color:#3b82f6;margin-bottom:6px">📊 REGIÃO DE ${stats.clusterCount} CLUSTERS</div>`;
      html += `<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:10px">`;
      html += `<div><span style="color:#475569">Preço:</span> ${stats.startPrice.toFixed(2)} → ${stats.endPrice.toFixed(2)}</div>`;
      html += `<div><span style="color:#475569">Variação:</span> <span style="color:${stats.priceChange >= 0 ? '#22c55e' : '#ef4444'}">${stats.priceChange > 0 ? '+' : ''}${stats.priceChange.toFixed(2)} (${stats.priceChangePercent.toFixed(2)}%)</span></div>`;
      html += `<div><span style="color:#475569">Volume total:</span> ${stats.totalVolume.toFixed(1)}</div>`;
      html += `<div><span style="color:#475569">Delta líquido:</span> <span style="color:${stats.netDelta >= 0 ? '#22c55e' : '#ef4444'}">${stats.netDelta > 0 ? '+' : ''}${stats.netDelta.toFixed(1)}</span></div>`;
      html += `<div><span style="color:#475569">Compras:</span> ${(stats.buyRatio * 100).toFixed(1)}%</div>`;
      html += `<div><span style="color:#475569">Duração:</span> ${stats.duration.toFixed(1)}s</div>`;
      html += `</div></div>`;
    }
  }

  if (data.synthesis) {
    const conf = data.synthesis.confidence || 0;
    const analystsCount = data.synthesis.agreeing_analysts || 0;
    const totalAnalysts = data.synthesis.total_analysts || data.analysts.length;

    html += `<div style="background:linear-gradient(135deg,rgba(59,130,246,.08),rgba(59,130,246,.02));border:1px solid #3b82f6;border-radius:6px;padding:10px;margin-bottom:10px">
      <div style="font-size:12px;font-weight:700;color:#3b82f6;margin-bottom:6px">🧠 Síntese</div>
      <div style="font-size:11px;line-height:1.5;color:#e2e8f0;white-space:pre-line">${escapeHtml(data.synthesis.summary || '')}</div>
      <div style="margin-top:6px;font-size:9px;color:#64748b">Confiança: ${(conf * 100).toFixed(0)}% · ${analystsCount}/${totalAnalysts} analistas concordam</div>
    </div>`;
  }

  for (const r of (data.analysts || [])) {
    if (r.error) {
      html += `<div style="background:#0d1321;border:1px solid #ef4444;border-radius:6px;padding:10px;margin-bottom:6px;color:#ef4444">❌ Erro em ${r.analyst}</div>`;
      continue;
    }

    const confPct = ((r.confidence || 0) * 100).toFixed(0);
    const confCls = r.confidence > 0.7 ? '#22c55e' : r.confidence > 0.4 ? '#eab308' : '#64748b';

    html += `<div style="background:#0d1321;border:1px solid #1e293b;border-radius:6px;padding:10px;margin-bottom:6px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <span style="font-weight:600;font-size:11px">${r.info?.emoji || '🔬'} ${r.info?.name || r.analyst}</span>
        <span style="font-size:9px;padding:2px 6px;border-radius:3px;background:${confCls}20;color:${confCls}">${confPct}%</span>
      </div>
      <div style="display:inline-block;font-size:10px;font-weight:600;padding:2px 6px;border-radius:3px;margin-bottom:4px;background:${getBgColor(r.classification)};color:${getTextColor(r.classification)}">${r.classification}</div>
      <div style="font-size:10px;line-height:1.5;color:#94a3b8;margin-bottom:6px">${escapeHtml(r.description || '')}</div>`;

    if (r.details) {
      html += '<div style="margin-top:4px;padding-top:4px;border-top:1px solid #1e293b">';

      if (r.analyst === 'execution_style' && r.details.aggressive_ratio != null) {
        const aggRatio = r.details.aggressive_ratio;
        html += `<div style="margin-bottom:4px">`;
        html += `<div style="display:flex;justify-content:space-between;margin-bottom:2px">`;
        html += `<span style="color:#ff6b35">🔥 Agressivo: ${r.details.aggressive_volume?.toFixed(1) || 0}</span>`;
        html += `<span style="color:#4ecdc4">🛡️ Passivo: ${r.details.passive_volume?.toFixed(1) || 0}</span>`;
        html += `</div>`;
        html += `<div style="height:6px;background:#1e293b;border-radius:3px;overflow:hidden">`;
        html += `<div style="height:100%;width:${aggRatio * 100}%;background:#ff6b35;float:left"></div>`;
        html += `<div style="height:100%;width:${(1 - aggRatio) * 100}%;background:#4ecdc4;float:left"></div>`;
        html += `</div></div>`;
      }

      for (const [k, v] of Object.entries(r.details)) {
        if (typeof v === 'object' && v !== null) continue;
        if (['aggressive_ratio', 'aggressive_volume', 'passive_volume'].includes(k)) continue;
        const fv = typeof v === 'number' ? (Math.abs(v) < 0.01 ? v.toFixed(6) : v.toFixed(4)) : v;
        html += `<div style="display:flex;justify-content:space-between;font-size:9px;padding:1px 0"><span style="color:#475569">${k}</span><span style="color:#e2e8f0">${fv}</span></div>`;
      }
      html += '</div>';
    }

    html += '</div>';
  }

  content.innerHTML = html;
}

function getBgColor(cls) {
  const buyClasses = ['EXCESSO_DEMANDA','ABSORCAO_COMPRA','SWEEP_BAIXA','IMBALANCE_COMPRADOR','BREAKOUT_REAL','POC_REJECTION','DEMANDA_MODERADA','AGRESSIVO_DOMINANTE','LEVEMENTE_AGRESSIVO'];
  const sellClasses = ['EXCESSO_OFERTA','ABSORCAO_VENDA','SWEEP_ALTA','IMBALANCE_VENDEDOR','AUSENCIA_DEMANDA','OFERTA_MODERADA','PASSIVO_DOMINANTE','LEVEMENTE_PASSIVO'];

  if (buyClasses.includes(cls)) return 'rgba(34,197,94,.12)';
  if (sellClasses.includes(cls)) return 'rgba(239,68,68,.12)';
  return 'rgba(148,163,184,.08)';
}
function getTextColor(cls) {
  const buyClasses = ['EXCESSO_DEMANDA','ABSORCAO_COMPRA','SWEEP_BAIXA','IMBALANCE_COMPRADOR','BREAKOUT_REAL','POC_REJECTION','DEMANDA_MODERADA','AGRESSIVO_DOMINANTE','LEVEMENTE_AGRESSIVO'];
  const sellClasses = ['EXCESSO_OFERTA','ABSORCAO_VENDA','SWEEP_ALTA','IMBALANCE_VENDEDOR','AUSENCIA_DEMANDA','OFERTA_MODERADA','PASSIVO_DOMINANTE','LEVEMENTE_PASSIVO'];

  if (buyClasses.includes(cls)) return '#22c55e';
  if (sellClasses.includes(cls)) return '#ef4444';
  return '#94a3b8';
}
function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ─── Estado do AI Synthesizer ───────────────────────────────────
let lastClosedCluster = null;
let aiAudioCtx = null;

// ─── Sons do alerta ─────────────────────────────────────────────
function _getAudioCtx() {
  if (!aiAudioCtx) aiAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return aiAudioCtx;
}
function playAiSound(alertType) {
  try {
    const ctxAudio = _getAudioCtx();
    const isBull = alertType.includes('BUY');
    const isStrong = alertType.includes('STRONG');

    const notes = isStrong
      ? (isBull ? [523, 659, 784, 1047] : [523, 415, 330, 262])
      : (isBull ? [523, 784] : [523, 415]);

    let time = ctxAudio.currentTime;
    notes.forEach((freq, i) => {
      const osc = ctxAudio.createOscillator();
      const gain = ctxAudio.createGain();
      osc.connect(gain);
      gain.connect(ctxAudio.destination);
      osc.type = isStrong ? 'sine' : 'triangle';
      osc.frequency.value = freq;

      gain.gain.setValueAtTime(0, time + i * 0.12);
      gain.gain.linearRampToValueAtTime(0.18, time + i * 0.12 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, time + i * 0.12 + 0.18);

      osc.start(time + i * 0.12);
      osc.stop(time + i * 0.12 + 0.2);
    });
  } catch (e) {
    console.log('🔇 Áudio não disponível:', e.message);
  }
}

// ─── Loading toast ──────────────────────────────────────────────
function showAiLoading() {
  const el = document.getElementById('aiLoadingToast');
  if (el) el.classList.add('visible');
}
function hideAiLoading() {
  const el = document.getElementById('aiLoadingToast');
  if (el) el.classList.remove('visible');
}

// ─── Renderiza o overlay do AI signal ───────────────────────────
function renderAiSignal(data) {
  if (!data) return;

  const direction = (data.direction || 'NEUTRAL').toUpperCase();
  const alertType = (data.alert_type || 'NEUTRAL').toUpperCase();
  const confidence = data.confidence || 0;
  const mechanism = (data.mechanism || 'INDEFINIDO').toUpperCase();
  const reasoning = data.reasoning || '';
  const riskNote = data.risk_note || '';
  const keySignals = data.key_signals || [];
  const pattern = data.pattern || 'N/A';
  const source = data.source || 'api';

  const dirClass = direction === 'BULL' ? 'bull' : direction === 'BEAR' ? 'bear' : 'neutral';
  const dirEmoji = direction === 'BULL' ? '▲' : direction === 'BEAR' ? '▼' : '◆';
  const confColor = confidence >= 0.75 ? '#22c55e' : confidence >= 0.50 ? '#eab308' : '#64748b';

  const mechClass = mechanism.includes('ABSORÇÃO') ? 'absorption'
    : mechanism.includes('VÁCUO') ? 'vacuo'
    : mechanism.includes('MOMENTUM') ? 'momentum'
    : '';

  const borderClass = alertType === 'STRONG_BUY' ? 'strong-buy'
    : alertType === 'STRONG_SELL' ? 'strong-sell'
    : dirClass;

  const border = document.getElementById('aiScreenBorder');
  if (!border) return;

  border.className = '';
  void border.offsetWidth;
  border.className = borderClass;

  const chipsHtml = keySignals.length
    ? `<div class="ai-signals-list">${keySignals.map((s) => `<span class="ai-sig-chip">${escapeHtml(s)}</span>`).join('')}</div>`
    : '';

  const riskHtml = riskNote ? `<div class="ai-risk-note">${escapeHtml(riskNote)}</div>` : '';

  const body = document.getElementById('aiSignalBody');
  if (body) {
    body.innerHTML = `
      <div class="ai-direction-row">
        <div class="ai-direction-badge ${dirClass}">${dirEmoji} ${direction}</div>
        <div class="ai-confidence-col">
          <div class="ai-conf-label">Confiança</div>
          <div class="ai-conf-bar-bg">
            <div class="ai-conf-bar-fill" style="width:${confidence * 100}%;background:${confColor}"></div>
          </div>
          <div class="ai-conf-value" style="color:${confColor}">${(confidence * 100).toFixed(0)}%</div>
        </div>
      </div>
      <div class="ai-mechanism-row">
        <span class="ai-tag ${mechClass}">${mechanism}</span>
        <span class="ai-tag">${escapeHtml(pattern)}</span>
        <span class="ai-tag" style="color:#475569">${source === 'local_fallback' ? '⚡ local' : '🤖 claude'}</span>
      </div>
      ${chipsHtml}
      <div class="ai-reasoning">${escapeHtml(reasoning)}</div>
      ${riskHtml}
    `;
  }

  const footerSource = document.getElementById('aiFooterSource');
  const footerTime = document.getElementById('aiFooterTime');
  if (footerSource) footerSource.textContent = source === 'local_fallback' ? '⚡ Análise local (API offline)' : '🤖 claude-sonnet-4-6';
  if (footerTime) {
    footerTime.textContent = new Date().toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  }

  const overlay = document.getElementById('aiSignalOverlay');
  if (overlay) overlay.classList.add('visible');

  playAiSound(alertType);

  const autoClose = alertType === 'NEUTRAL' ? 12000 : 20000;
  if (window._aiAutoCloseTimer) clearTimeout(window._aiAutoCloseTimer);
  window._aiAutoCloseTimer = setTimeout(closeAiSignal, autoClose);
}

function closeAiSignal() {
  const overlay = document.getElementById('aiSignalOverlay');
  const border = document.getElementById('aiScreenBorder');
  if (overlay) overlay.classList.remove('visible');
  if (border) border.className = '';
  if (window._aiAutoCloseTimer) clearTimeout(window._aiAutoCloseTimer);
}

function setupMarkerEvents() {
  canvas.addEventListener('mousedown', function (e) {
    if (!activeMarker) return;
    e.stopPropagation();

    const rect = canvas.getBoundingClientRect();
    isMarkerDrag = true;
    markerDragStart = { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, true);

  canvas.addEventListener('mouseup', function (e) {
    if (!isMarkerDrag || !activeMarker || !clusters.length) return;
    e.stopPropagation();

    isMarkerDrag = false;

    const rect = canvas.getBoundingClientRect();
    const startX = markerDragStart.x;
    const endX = e.clientX - rect.left;
    const startY = markerDragStart.y;
    const endY = e.clientY - rect.top;

    const clusterWidth = Math.max(8, 40 * viewState.scaleX);
    const startIdx = Math.floor((startX - viewState.offsetX) / (clusterWidth + CONFIG.clusterGap));
    const endIdx = Math.floor((endX - viewState.offsetX) / (clusterWidth + CONFIG.clusterGap));

    const idx1 = Math.max(0, Math.min(startIdx, endIdx));
    const idx2 = Math.min(clusters.length - 1, Math.max(startIdx, endIdx));

    const firstCluster = clusters[idx1];
    const lastCluster = clusters[idx2];
    if (!firstCluster || !lastCluster) return;

    const midY = (startY + endY) / 2;
    const price = yToPrice(midY);

    console.log(`📍 Cluster range: ${idx1} a ${idx2}`);
    console.log(`   Time range: ${firstCluster.startTime?.toFixed?.(0)} - ${lastCluster.endTime?.toFixed?.(0)}`);

    markerPoints.push({
      type: activeMarker,
      price,
      clusterIndex: Math.floor((idx1 + idx2) / 2),
      color: MARKER_COLORS[activeMarker],
      emoji: MARKER_EMOJIS[activeMarker],
      timestamp: Date.now() / 1000
    });

    selectedClusters = [];
    for (let i = idx1; i <= idx2; i++) selectedClusters.push(i);

    if (ws && ws.readyState === 1) {
      showAiLoading();
      ws.send(JSON.stringify({
        type: 'marker',
        marker_type: activeMarker,
        price,
        time_start: firstCluster.startTime,
        time_end: lastCluster.endTime != null ? lastCluster.endTime : (masterTicks.length ? masterTicks[masterTicks.length - 1].timestamp : Date.now() / 1000),
        cluster_indices: [idx1, idx2]
      }));
    }

    render();
    markerDragStart = null;
  }, true);
}

function renderMarkers() {
  if (!markerPoints.length || clusters.length === 0) return;

  let priceHigh = -Infinity, priceLow = Infinity;
  for (const c of clusters) {
    priceHigh = Math.max(priceHigh, c.high);
    priceLow = Math.min(priceLow, c.low);
  }

  const range = (priceHigh - priceLow) * viewState.scaleY;
  const center = (priceHigh + priceLow) / 2;
  const pad = range * 0.15;
  const viewHigh = center + range / 2 + pad + viewState.offsetY;
  const viewLow = center - range / 2 - pad + viewState.offsetY;

  const priceToY = (p) => {
    const r = viewHigh - viewLow;
    return r > 0 ? ((viewHigh - p) / r) * chartH : chartH / 2;
  };

  const clusterWidth = Math.max(8, 40 * viewState.scaleX);
  const clusterToX = (i) => viewState.offsetX + i * (clusterWidth + CONFIG.clusterGap) + clusterWidth / 2;

  for (const m of markerPoints) {
    const y = priceToY(m.price);
    if (y < -20 || y > chartH + 20) continue;

    const cx = clusterToX(m.clusterIndex);
    if (cx < -50 || cx > chartW + 50) continue;

    ctx.strokeStyle = `${m.color}50`;
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(chartW, y);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.strokeStyle = `${m.color}40`;
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(cx, 0);
    ctx.lineTo(cx, chartH);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = m.color;
    ctx.shadowColor = m.color;
    ctx.shadowBlur = 6;
    ctx.beginPath();
    ctx.moveTo(cx, y - 8);
    ctx.lineTo(cx + 8, y);
    ctx.lineTo(cx, y + 8);
    ctx.lineTo(cx - 8, y);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;

    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.arc(cx, y, 2.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = m.color;
    ctx.font = 'bold 9px JetBrains Mono';
    ctx.textAlign = 'left';
    const symDig = (SYMBOLS[currentSymbol] || {}).dig || 2;
    ctx.fillText(`${m.emoji} ${m.price.toFixed(symDig)}`, cx + 12, y + 3);
  }
}

// ---------- CANVAS EVENTS ----------
function setupCanvasEvents() {
  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    crosshair = { x: Math.min(x, chartW), y, visible: true };

    if (viewState.isDragging) {
      if (viewState.dragMode === 'zoom') {
        const dy = e.clientY - viewState.lastY;
        const zoomFactor = 1 + dy * 0.005;
        viewState.scaleY = Math.max(0.1, Math.min(20, viewState.scaleY * zoomFactor));
        viewState.lastY = e.clientY;
      } else if (viewState.dragMode === 'histResize') {
        const newChartH = Math.max(100, Math.min(totalH - 40, y));
        HISTOGRAM_RATIO = Math.max(0.05, Math.min(0.6, 1 - newChartH / totalH));
        histH = Math.floor(totalH * HISTOGRAM_RATIO);
        chartH = totalH - histH;
      } else if (viewState.dragMode === 'histSplitResize') {
        const histY = chartH;
        const labelH = 14;
        const gap = 4;
        const availH = histH - labelH - gap;
        const relativeY = y - histY - labelH;
        HIST_SPLIT = Math.max(0.15, Math.min(0.85, relativeY / availH));
      } else if (viewState.dragMode === 'moveDrawing' && selectedDrawing !== null) {
        const drawing = drawings.find((d) => d.id === selectedDrawing);
        if (drawing && drawing.type === 'hline') {
          drawing.p1.y = yToPrice(y);
        }
      } else {
        const dx = e.clientX - viewState.lastX;
        const dy = e.clientY - viewState.lastY;
        viewState.offsetX += dx;

        if (clusters.length > 0) {
          let pH = -Infinity, pL = Infinity;
          for (const c of clusters) {
            pH = Math.max(pH, c.high);
            pL = Math.min(pL, c.low);
          }
          const priceRange = (pH - pL) * viewState.scaleY * 1.3;
          const pricePerPixel = priceRange / chartH;
          viewState.offsetY += dy * pricePerPixel;
        }

        viewState.lastX = e.clientX;
        viewState.lastY = e.clientY;
      }
    }

    if (!viewState.isDragging) {
      const histBorderY = chartH;
      const labelH = 14, gap = 4;
      const availH = histH - labelH - gap;
      const midSepY = chartH + labelH + availH * HIST_SPLIT + gap / 2;

      if (Math.abs(y - histBorderY) < 6 && x < chartW) {
        canvas.style.cursor = 'row-resize';
      } else if (y > chartH && Math.abs(y - midSepY) < 5 && x < chartW) {
        canvas.style.cursor = 'row-resize';
      } else if (x > chartW) {
        canvas.style.cursor = 'ns-resize';
      } else if (drawTool !== 'none' || activeMarker !== null) {
        canvas.style.cursor = 'crosshair';
      } else {
        canvas.style.cursor = 'crosshair';
      }
    }

    render();
  });

  canvas.addEventListener('mouseleave', () => {
    crosshair.visible = false;
    viewState.isDragging = false;
    render();
  });

  canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (Math.abs(y - chartH) < 6 && x < chartW) {
      viewState.isDragging = true;
      viewState.dragMode = 'histResize';
      return;
    }

    if (y > chartH && x < chartW) {
      const labelH = 14, gap = 4;
      const availH = histH - labelH - gap;
      const midSepY = chartH + labelH + availH * HIST_SPLIT + gap / 2;

      if (Math.abs(y - midSepY) < 5) {
        viewState.isDragging = true;
        viewState.dragMode = 'histSplitResize';
        return;
      }
    }

    if (x > chartW) {
      viewState.isDragging = true;
      viewState.lastY = e.clientY;
      viewState.dragMode = 'zoom';
      return;
    }

    if (drawTool !== 'none' && activeMarker === null) {
      const price = yToPrice(y);
      const clusterIdx = Math.round((x - viewState.offsetX) / (Math.max(8, 40 * viewState.scaleX) + CONFIG.clusterGap));

      if (!currentDrawing) {
        currentDrawing = {
          id: nextDrawId++,
          type: drawTool,
          p1: { x: clusterIdx, y: price },
          p2: null,
          color: CONFIG.drawColor
        };

        if (drawTool === 'hline' || drawTool === 'vline') {
          drawings.push({ ...currentDrawing });
          currentDrawing = null;
          setDrawTool('none');
        }
      } else {
        currentDrawing.p2 = { x: clusterIdx, y: price };
        drawings.push({ ...currentDrawing });
        currentDrawing = null;
        setDrawTool('none');
      }

      render();
      return;
    }

    if (activeMarker === null) {
      // CORREÇÃO: priceToY local para hit-test
      let localPriceHigh = -Infinity, localPriceLow = Infinity;
      for (const c of clusters) {
        localPriceHigh = Math.max(localPriceHigh, c.high);
        localPriceLow = Math.min(localPriceLow, c.low);
      }

      const localRange = (localPriceHigh - localPriceLow) * viewState.scaleY;
      const localCenter = (localPriceHigh + localPriceLow) / 2;
      const localPad = localRange * 0.15;
      const localViewHigh = localCenter + localRange / 2 + localPad + viewState.offsetY;
      const localViewLow = localCenter - localRange / 2 - localPad + viewState.offsetY;
      const localPriceToY = (p) => {
        const r = localViewHigh - localViewLow;
        return r > 0 ? ((localViewHigh - p) / r) * chartH : chartH / 2;
      };

      selectedDrawing = null;
      for (const d of drawings) {
        if (d.type === 'hline') {
          const dy = Math.abs(localPriceToY(d.p1.y) - y);
          if (dy < 6) {
            selectedDrawing = d.id;
            break;
          }
        }
      }

      viewState.isDragging = true;
      viewState.lastX = e.clientX;
      viewState.lastY = e.clientY;
      viewState.dragMode = selectedDrawing ? 'moveDrawing' : 'pan';
    }
  });

  canvas.addEventListener('mouseup', () => {
    viewState.isDragging = false;
  });

  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();

    if (e.ctrlKey) {
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      viewState.scaleX = Math.max(0.2, Math.min(15, viewState.scaleX * delta));
    } else if (e.shiftKey) {
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      viewState.scaleY = Math.max(0.1, Math.min(20, viewState.scaleY * delta));
    } else {
      viewState.offsetX += e.deltaY > 0 ? 50 : -50;
    }

    render();
  }, { passive: false });

  document.addEventListener('keydown', (e) => {
    if ((e.key === 'Delete' || e.key === 'Backspace') && document.activeElement === document.body) {
      if (selectedDrawing !== null) {
        e.preventDefault();
        deleteSelectedDrawing();
      }
    }

    if (e.key === 'Escape') {
      setDrawTool('none');
      currentDrawing = null;
      selectedDrawing = null;
      render();
    }
  });
}

// ---------- CONTROLS ----------
function syncStepSlider() {
  const stSlider = document.getElementById('stepSlider');
  const stValue = document.getElementById('stepValue');
  if (!stSlider || !stValue) return;

  const sym = SYMBOLS[currentSymbol] || {};
  const baseStep = sym.step || 0.01;

  let mult = 0;
  if (priceStep && priceStep > 0) {
    mult = Math.max(1, Math.round(priceStep / baseStep));
  }

  stSlider.value = mult;
  stValue.textContent = priceStep === 0 ? 'AUTO' : (priceStep >= 1 ? `$${priceStep.toFixed(0)}` : priceStep.toFixed(4));
}

function setupControls() {
  const thSlider = document.getElementById('thresholdSlider');
  const thValue = document.getElementById('thresholdValue');

  if (thSlider && thValue) {
    thSlider.addEventListener('input', () => {
      threshold = Number(thSlider.value);
      thValue.textContent = threshold >= 1000 ? `${threshold / 1000}k` : `${threshold}`;
      const allT = getAllTicks();
      if (allT.length > 0) {
        // Ticks brutos disponíveis → reconstrói clusters com o novo threshold
        fullReprocess(allT);
        autoFitView();
      } else if (clusters.length > 0 && clusters[0].fromDB) {
        // Apenas clusters do DB carregados — threshold não pode reprocessar
        // mas avisa o usuário via sourceLabel
        const sourceLabel = document.getElementById('sourceLabel');
        if (sourceLabel) sourceLabel.textContent = `DB (use loadHistory para reprocessar)`;
      }
      updateUI();
      render();
    });
  }

  const stSlider = document.getElementById('stepSlider');
  const stValue = document.getElementById('stepValue');

  if (stSlider && stValue) {
    stSlider.addEventListener('input', () => {
      const val = Number(stSlider.value);
      const sym = SYMBOLS[currentSymbol] || {};
      const baseStep = sym.step || 0.01;

      priceStep = val === 0 ? 0 : val * baseStep;
      stValue.textContent = priceStep === 0 ? 'AUTO' : (priceStep >= 1 ? `$${priceStep.toFixed(0)}` : priceStep.toFixed(4));

      const allT = getAllTicks();
      if (allT.length > 0) {
        fullReprocess(allT);  // reconstrói footprint com novo step
        autoFitView();
      }
      updateUI();
      render();
    });
  }
}

function setColor(key, value) {
  CONFIG[key] = value;
  render();
}

function autoFitView() {
  if (clusters.length === 0) return;

  // Reseta zoom para estado neutro e calcula posição para mostrar os últimos clusters
  viewState.scaleX = 1;
  viewState.scaleY = 1;
  viewState.offsetY = 0;

  const cw = Math.max(8, 40 * viewState.scaleX);  // = 40 após reset
  const visibleClusters = Math.max(1, Math.floor(chartW / (cw + CONFIG.clusterGap)));
  const targetIdx = Math.max(0, clusters.length - visibleClusters);
  viewState.offsetX = -(targetIdx * (cw + CONFIG.clusterGap)) + 20;
}

function findClusters() {
  if (clusters.length === 0) {
    const label = document.getElementById('sourceLabel');
    if (label) label.textContent = 'Nenhum cluster';
    return;
  }

  viewState.scaleX = 1;
  viewState.scaleY = 1;
  viewState.offsetY = 0;
  autoFitView();
  render();

  const symDig = (SYMBOLS[currentSymbol] || {}).dig || 2;
  const label = document.getElementById('sourceLabel');
  if (label) label.textContent = `${clusters.length} clusters | ${clusters[clusters.length - 1].close.toFixed(symDig)}`;
}

function setViewMode(mode) {
  viewMode = mode;
  document.querySelectorAll('[data-mode]').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  render();
}

function setDrawTool(tool) {
  drawTool = tool;
  currentDrawing = null;
  document.querySelectorAll('[data-draw]').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.draw === tool);
  });
  canvas.style.cursor = 'crosshair';
}

function clearDrawings() {
  drawings = [];
  selectedDrawing = null;
  currentDrawing = null;
  render();
}

function deleteSelectedDrawing() {
  if (selectedDrawing !== null) {
    drawings = drawings.filter((d) => d.id !== selectedDrawing);
    selectedDrawing = null;
    render();
  }
}

function toggleEnginePanel() {
  showEnginePanel = !showEnginePanel;
  const panel = document.getElementById('enginePanel');
  const btn = document.getElementById('engineToggle');
  if (panel) panel.classList.toggle('visible', showEnginePanel);
  if (btn) btn.classList.toggle('active', showEnginePanel);
  resize();
}

function toggleLive() {
  isLive = !isLive;
  const btn = document.getElementById('liveBtn');
  if (!btn) return;

  if (isLive) {
    btn.textContent = '⏹ PARAR';
    btn.classList.add('stopped');
    connectWS();
  } else {
    btn.textContent = '▶ LIVE';
    btn.classList.remove('stopped');
    disconnectWS();
  }
}

function toggleCalibration() {
  showCalibration = !showCalibration;
  const panel = document.getElementById('calibPanel');
  const btn = document.getElementById('calibToggle');
  if (panel) panel.classList.toggle('visible', showCalibration);
  if (btn) btn.classList.toggle('active', showCalibration);
  resize();
}

function switchSymbol(sym) {
  currentSymbol = sym;

  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ type: 'switch_symbol', symbol: sym }));
    setTimeout(() => loadHistory(24), 500);
  }

  closedClusters = [];
  formingCluster = null;
  formingTicks = [];
  masterTicks = [];
  clusters = [];
  totalTicks = 0;
  lastPrice = 0;

  const cfg = SYMBOLS[sym] || {};
  if (cfg.delta_th) {
    threshold = cfg.delta_th;
    const thSlider = document.getElementById('thresholdSlider');
    const thValue = document.getElementById('thresholdValue');
    if (thSlider) thSlider.value = threshold;
    if (thValue) thValue.textContent = threshold >= 1000 ? `${threshold / 1000}k` : `${threshold}`;
  }

  if (cfg.step !== undefined) {
    priceStep = cfg.step;
    syncStepSlider();
  }

  const el = document.getElementById('engineSourceLabel');
  if (el) el.textContent = (cfg.label || sym);

  render();
}

function setWeightMode(mode) {
  weightMode = mode;
  if (ws && ws.readyState === 1) {
    ws.send(JSON.stringify({ action: 'set_weight_mode', mode }));
  }
}

function loadHistory(hours) {
  if (!ws || ws.readyState !== 1) {
    const sourceLabel = document.getElementById('sourceLabel');
    if (sourceLabel) sourceLabel.textContent = 'WS desconectado';
    return;
  }

  const sourceLabel = document.getElementById('sourceLabel');
  if (sourceLabel) sourceLabel.textContent = `carregando ${hours}h...`;

  ws.send(JSON.stringify({
    type: 'get_history',
    symbol: currentSymbol,
    hours
  }));
}

function resetChart() {
  closedClusters = [];
  formingCluster = null;
  formingTicks = [];
  masterTicks = [];
  clusters = [];
  totalTicks = 0;
  selectedClusters = [];

  viewState.offsetX = 0;
  viewState.offsetY = 0;
  viewState.scaleX = 1;
  viewState.scaleY = 1;

  updateUI();
  render();
}

// ---------- UI UPDATES ----------
function updateUI() {
  const priceEl = document.getElementById('priceDisplay');
  const symDig = (SYMBOLS[currentSymbol] || {}).dig || 2;

  if (priceEl) {
    priceEl.textContent = lastPrice > 0 ? lastPrice.toFixed(symDig) : '--';
    priceEl.className = `price-display ${lastSide === 'buy' ? 'up' : 'down'}`;
  }

  const tickCounter = document.getElementById('tickCounter');
  if (tickCounter) tickCounter.textContent = `${totalTicks.toLocaleString()} ticks`;

  const clusterCount = document.getElementById('clusterCount');
  if (clusterCount) {
    const closed  = clusters.filter((c) => c.isClosed).length;
    const fromDB  = clusters.filter((c) => c.fromDB).length;
    clusterCount.textContent = fromDB > 0 ? `${closed} (DB)` : closed;
  }

  const forming = clusters.find((c) => !c.isClosed);
  const bar = document.getElementById('formingBar');

  if (forming && bar) {
    bar.classList.add('visible');

    const deltaRounded = Math.round(forming.delta * 10) / 10;
    const deltaEl = document.getElementById('formingDelta');
    if (deltaEl) {
      deltaEl.textContent = (deltaRounded >= 0 ? '+' : '') + deltaRounded;
      deltaEl.style.color = forming.delta >= 0 ? CONFIG.bull : CONFIG.bear;
    }

    const bodyEl = document.getElementById('formingBody');
    const wickEl = document.getElementById('formingWick');
    if (bodyEl) bodyEl.textContent = forming.volumeTotal > 0 ? `${((forming.volumeBody / forming.volumeTotal) * 100).toFixed(0)}%` : '0%';
    if (wickEl) wickEl.textContent = `${forming.wickPercent.toFixed(0)}%`;

    const absEl = document.getElementById('formingAbsorptions');
    if (absEl) {
      if (forming.absorptionCount > 0) {
        absEl.style.display = 'inline';
        absEl.textContent = `🧩 ${forming.absorptionCount} abs (${forming.absorptionBuyCount}B / ${forming.absorptionSellCount}S)`;
      } else {
        absEl.style.display = 'none';
      }
    }

    const stackEl = document.getElementById('formingStacking');
    if (stackEl) {
      if (forming.maxStackingBuy >= 2 || forming.maxStackingSell >= 2) {
        stackEl.style.display = 'inline';
        stackEl.style.color = forming.maxStackingBuy > forming.maxStackingSell ? CONFIG.absorptionBuy : CONFIG.absorptionSell;
        stackEl.style.fontWeight = '700';
        stackEl.textContent = `🔥 Stack B${forming.maxStackingBuy}/S${forming.maxStackingSell}`;
      } else {
        stackEl.style.display = 'none';
      }
    }

    const fill = document.getElementById('deltaBarFill');
    if (fill) {
      const pct = Math.min(100, (Math.abs(forming.delta) / threshold) * 100);
      fill.style.width = `${pct}%`;
      fill.style.background = forming.delta >= 0 ? CONFIG.bull : CONFIG.bear;
    }
  } else if (bar) {
    bar.classList.remove('visible');
  }
}

function safeSetText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
  return el;
}

function updateEnginePanel() {
  const e = engineState || {};

  if (e.tick_velocity) {
    safeSetText('eng_velocity', `${(e.tick_velocity.velocity || 0).toFixed(1)} t/s`);
    safeSetText('eng_velocity_base', `${(e.tick_velocity.baseline || 0).toFixed(1)}`);
    const burstEl = document.getElementById('eng_burst');
    if (burstEl) burstEl.style.display = e.tick_velocity.is_burst ? 'inline' : 'none';
  }

  if (e.micro_cluster) {
    const absEl = document.getElementById('eng_absorption');
    if (absEl) {
      if (e.micro_cluster.is_absorption) {
        const isBuy = e.micro_cluster.absorption_type === 'buy_absorption';
        absEl.textContent = isBuy ? '🟢 BUY ABS' : '🔴 SELL ABS';
        absEl.style.color = isBuy ? CONFIG.absorptionBuy : CONFIG.absorptionSell;
      } else {
        absEl.textContent = 'Sem absorção';
        absEl.style.color = CONFIG.text;
      }
    }
    safeSetText('eng_abs_total', `${e.micro_cluster.total_absorptions || 0}`);
  }

  if (e.atr_normalize) {
    const atr = e.atr_normalize.atr;
    safeSetText('eng_atr', atr ? (atr * 100).toFixed(4) : '--');
    const regimeEl = document.getElementById('eng_atr_regime');
    if (regimeEl) {
      regimeEl.textContent = e.atr_normalize.regime || 'warmup';
      regimeEl.style.color = e.atr_normalize.regime === 'expanding'
        ? CONFIG.absorptionSell
        : e.atr_normalize.regime === 'contracting'
          ? CONFIG.absorptionBuy
          : CONFIG.text;
    }
  }

  if (e.imbalance_detector) {
    safeSetText('eng_stack_buy', `Buy: S${e.imbalance_detector.stacking_buy || 0}`);
    safeSetText('eng_stack_sell', `Sell: S${e.imbalance_detector.stacking_sell || 0}`);

    const dom = document.getElementById('eng_dominant');
    if (dom) {
      if (e.imbalance_detector.dominant_direction) {
        dom.textContent = `→ ${e.imbalance_detector.dominant_direction.toUpperCase()}`;
        dom.style.color = e.imbalance_detector.dominant_direction === 'buy' ? CONFIG.absorptionBuy : CONFIG.absorptionSell;
      } else {
        dom.textContent = '';
      }
    }
  }

  if (e.spread_weight) {
    safeSetText('eng_vol', `${(e.spread_weight.volatility || 0).toFixed(2)} bps`);
    const regEl = document.getElementById('eng_vol_regime');
    if (regEl) {
      regEl.textContent = e.spread_weight.regime || '--';
      regEl.style.color = e.spread_weight.regime === 'high'
        ? CONFIG.absorptionSell
        : e.spread_weight.regime === 'low'
          ? CONFIG.absorptionBuy
          : CONFIG.text;
    }
  }

  if (e.execution_style) {
    safeSetText('eng_execution', e.execution_style.trend || '--');
    const ratioEl = document.getElementById('eng_exec_ratio');
    if (ratioEl && e.execution_style.aggressive_ratio != null) {
      const ratio = (e.execution_style.aggressive_ratio * 100).toFixed(0);
      ratioEl.textContent = `${ratio}%`;
      ratioEl.style.color = e.execution_style.aggressive_ratio > 0.6
        ? CONFIG.aggressive
        : e.execution_style.aggressive_ratio < 0.4
          ? CONFIG.passive
          : CONFIG.text;
    }
  }

  // Elementos opcionais (não existem no HTML atual, mas mantidos sem quebrar)
  const signal = e.micro_cluster?.signal || 0;
  const sigEl = document.getElementById('eng_signal');
  if (sigEl) {
    sigEl.textContent = `${(signal * 100).toFixed(0)}%`;
    sigEl.style.color = signal > 0.2 ? CONFIG.absorptionBuy : signal < -0.2 ? CONFIG.absorptionSell : CONFIG.text;
  }
  const labEl = document.getElementById('eng_signal_label');
  if (labEl) {
    labEl.textContent = signal > 0 ? 'bullish' : signal < 0 ? 'bearish' : 'neutro';
  }
}

// Start
document.addEventListener('DOMContentLoaded', init);