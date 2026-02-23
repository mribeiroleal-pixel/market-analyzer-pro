/**
 * Event Listeners - Sem onclick inline
 */

document.addEventListener('DOMContentLoaded', () => {
  setupDrawToolListeners();
  setupSymbolListeners();
  setupHistoryListeners();
  setupWeightModeListeners();
});

// ============================================================
// DRAW TOOLS
// ============================================================

function setupDrawToolListeners() {
  const drawTools = document.querySelectorAll('.draw-tool-btn');
  
  drawTools.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const tool = e.target.dataset.tool;
      setDrawTool(tool);
      
      // Atualizar visual (remove active de todos, adiciona ao clicado)
      drawTools.forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
    });
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.key === '1') setDrawTool('hline');
    if (e.key === '2') setDrawTool('vline');
    if (e.key === '3') setDrawTool('rect');
    if (e.key === '4') setDrawTool('trend');
    if (e.key === 'Escape') setDrawTool('none');
  });
}

// ============================================================
// SYMBOL SELECTION
// ============================================================

function setupSymbolListeners() {
  const symbolSelect = document.getElementById('symbolSelect');
  
  if (symbolSelect) {
    symbolSelect.addEventListener('change', async (e) => {
      const symbol = e.target.value;
      
      try {
        await switchSymbol(symbol);
        console.log(`✅ Símbolo alterado para ${symbol}`);
      } catch (error) {
        console.error(`❌ Erro ao alterar símbolo: ${error}`);
        showNotification(`Erro ao alterar símbolo: ${error}`, 'error');
      }
    });
  }
}

// ============================================================
// HISTORY LOADING
// ============================================================

function setupHistoryListeners() {
  const historyButtons = document.querySelectorAll('[data-hours]');
  
  historyButtons.forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const hours = parseInt(e.target.dataset.hours);
      
      // Desabilitar durante carregamento
      e.target.disabled = true;
      const originalText = e.target.textContent;
      e.target.textContent = '⏳...';
      
      try {
        await loadHistory(hours);
        showNotification(`Histórico de ${hours}h carregado`, 'success');
      } catch (error) {
        showNotification(`Erro ao carregar histórico: ${error}`, 'error');
      } finally {
        e.target.disabled = false;
        e.target.textContent = originalText;
      }
    });
  });
}

// ============================================================
// WEIGHT MODE
// ============================================================

function setupWeightModeListeners() {
  const weightSelect = document.getElementById('weightSelect');
  
  if (weightSelect) {
    weightSelect.addEventListener('change', (e) => {
      const mode = e.target.value;
      setWeightMode(mode);
      console.log(`⚖️ Weight mode alterado para ${mode}`);
    });
  }
}

// ============================================================
// NOTIFICATIONS
// ============================================================

function showNotification(message, type = 'info') {
  console.log(`[${type.toUpperCase()}] ${message}`);
  
  // Toast notification (opcional)
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.remove();
  }, 3000);
}