"""
🔧 Create Initial Liquidity Break Model
Cria um modelo inicial com dados de exemplo
"""

import os
import sys
import json
import pickle
import numpy as np
from datetime import datetime
from pathlib import Path

print("=" * 70)
print("🤖 CRIANDO MODELO INICIAL DE LIQUIDITY BREAK")
print("=" * 70)
print()

# ============================================================
# SETUP PATH CORRETO
# ============================================================

# Adicionar diretórios ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, 'backend')

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

print(f"Python Path Setup:")
print(f"   Current: {current_dir}")
print(f"   Backend: {backend_dir}")
print()

# ============================================================
# IMPORTS
# ============================================================

print("Importando módulos...")

try:
    from liquidity_break_ml import LiquidityBreakDataset, LiquidityBreakML
    print("✅ Liquidity Break ML importado com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar: {e}")
    print()
    print("Tentando criar os módulos automaticamente...")
    
    # Criar liquidity_break_ml.py se não existir
    if not os.path.exists(os.path.join(backend_dir, 'liquidity_break_ml.py')):
        print()
        print("Criando liquidity_break_ml.py...")
        
        liquidity_code = '''"""
🔥 Liquidity Break ML System
Sistema de aprendizado para quebras de liquidez
"""

import json
import pickle
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class LiquidityBreakDataset:
    """Gerencia dataset de liquidity breaks"""
    
    def __init__(self, dataset_path: str = "liquidity_breaks_dataset.json"):
        self.dataset_path = dataset_path
        self.data: List[Dict] = []
        self.load()
    
    def load(self):
        """Carrega dataset existente"""
        if Path(self.dataset_path).exists():
            try:
                with open(self.dataset_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"OK: Dataset carregado: {len(self.data)} quebras")
            except Exception as e:
                logger.error(f"ERROR ao carregar dataset: {e}")
                self.data = []
        else:
            self.data = []
    
    def save(self):
        """Salva dataset"""
        try:
            with open(self.dataset_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, default=str)
            logger.info(f"OK: Dataset salvo: {len(self.data)} quebras")
        except Exception as e:
            logger.error(f"ERROR ao salvar dataset: {e}")
    
    def add_liquidity_break(self, break_info: Dict) -> bool:
        """Adiciona uma quebra de liquidez ao dataset"""
        try:
            break_record = {
                'id': len(self.data) + 1,
                'timestamp': datetime.now().isoformat(),
                **break_info
            }
            self.data.append(break_record)
            self.save()
            logger.info(f"OK: Quebra adicionada: ID #{break_record['id']}")
            return True
        except Exception as e:
            logger.error(f"ERROR ao adicionar quebra: {e}")
            return False
    
    def get_breaks_by_symbol(self, symbol: str) -> List[Dict]:
        """Retorna quebras de um símbolo específico"""
        return [b for b in self.data if b.get('symbol') == symbol]
    
    def export_for_ml(self) -> Tuple[np.ndarray, np.ndarray]:
        """Exporta dados para treinamento ML"""
        X = []
        y = []
        
        for break_data in self.data:
            if break_data.get('type') not in ['SELLERS_REPRICED_HIGHER', 'BUYERS_REPRICED_LOWER']:
                continue
            
            features = [
                float(break_data.get('delta', 0)),
                float(break_data.get('volume', 0)),
                float(break_data.get('wick_top', 0)),
                float(break_data.get('wick_bot', 0)),
                float(break_data.get('confidence_manual', 0.5)),
                int(break_data.get('is_structural', False)),
            ]
            
            label = 1 if break_data.get('type') == 'SELLERS_REPRICED_HIGHER' else 0
            
            X.append(features)
            y.append(label)
        
        return np.array(X), np.array(y)
    
    def update_break(self, break_id: int, updates: Dict) -> bool:
        """Atualiza informações de uma quebra"""
        try:
            for item in self.data:
                if item.get('id') == break_id:
                    item.update(updates)
                    self.save()
                    logger.info(f"OK: Quebra #{break_id} atualizada")
                    return True
            return False
        except Exception as e:
            logger.error(f"ERROR ao atualizar: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do dataset"""
        sellers_higher = sum(1 for b in self.data if b.get('type') == 'SELLERS_REPRICED_HIGHER')
        buyers_lower = sum(1 for b in self.data if b.get('type') == 'BUYERS_REPRICED_LOWER')
        structural = sum(1 for b in self.data if b.get('is_structural'))
        
        return {
            'total': len(self.data),
            'sellers_repriced_higher': sellers_higher,
            'buyers_repriced_lower': buyers_lower,
            'structural_breaks': structural,
        }


class LiquidityBreakML:
    """ML para aprender padrões de liquidity breaks"""
    
    def __init__(self, model_path: str = "liquidity_break_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.is_trained = False
    
    def train(self, X: np.ndarray, y: np.ndarray) -> bool:
        """Treina modelo com dados de liquidity breaks"""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler
            
            if len(X) < 5:
                logger.error("ERROR: Dados insuficientes (mínimo 5)")
                return False
            
            logger.info(f"OK: Treinando com {len(X)} amostras...")
            
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            self.model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
            self.model.fit(X_scaled, y)
            
            self.is_trained = True
            self.save()
            
            logger.info("OK: Modelo treinado com sucesso")
            return True
        
        except Exception as e:
            logger.error(f"ERROR ao treinar: {e}")
            return False
    
    def predict(self, delta: float, volume: float, wick_top: float, wick_bot: float, confidence: float = 0.5) -> Tuple[str, float]:
        """Prediz o tipo de liquidity break"""
        if not self.is_trained or self.model is None:
            logger.warning("WARNING: Modelo não treinado")
            return None, 0.5
        
        try:
            features = np.array([[delta, volume, wick_top, wick_bot, confidence, 0]])
            X_scaled = self.scaler.transform(features)
            
            pred = self.model.predict(X_scaled)[0]
            probs = self.model.predict_proba(X_scaled)[0]
            prob_confidence = float(np.max(probs))
            
            break_type = 'SELLERS_REPRICED_HIGHER' if pred == 1 else 'BUYERS_REPRICED_LOWER'
            
            return break_type, prob_confidence
        
        except Exception as e:
            logger.error(f"ERROR na predição: {e}")
            return None, 0.5
    
    def save(self):
        """Salva modelo"""
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump({'model': self.model, 'scaler': self.scaler}, f)
            logger.info(f"OK: Modelo salvo: {self.model_path}")
        except Exception as e:
            logger.error(f"ERROR ao salvar: {e}")
    
    def load(self) -> bool:
        """Carrega modelo"""
        try:
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.scaler = data['scaler']
                self.is_trained = True
            logger.info(f"OK: Modelo carregado: {self.model_path}")
            return True
        except Exception as e:
            logger.debug(f"INFO: Modelo não encontrado: {e}")
            return False
'''
        
        with open(os.path.join(backend_dir, 'liquidity_break_ml.py'), 'w', encoding='utf-8') as f:
            f.write(liquidity_code)
        
        print("✅ liquidity_break_ml.py criado")
        
        # Tentar importar novamente
        try:
            from liquidity_break_ml import LiquidityBreakDataset, LiquidityBreakML
            print("✅ Liquidity Break ML importado com sucesso")
        except ImportError as e2:
            print(f"❌ Erro ao importar após criar: {e2}")
            sys.exit(1)
    else:
        print("❌ Arquivo já existe mas não consegue importar")
        sys.exit(1)

print()

# ============================================================
# CRIAR DATASET INICIAL COM DADOS DE EXEMPLO
# ============================================================

print("Criando dataset com dados de exemplo...")
print()

dataset = LiquidityBreakDataset()

# Dados de exemplo - Quebras de vendedores (SELLERS_REPRICED_HIGHER)
sellers_breaks = [
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2650.50,
        'type': 'SELLERS_REPRICED_HIGHER',
        'delta': 150.5,
        'volume': 1000.0,
        'wick_top': 0.4,
        'wick_bot': 0.2,
        'confidence_manual': 0.85,
        'notes': 'Quebra forte com momentum',
        'is_structural': True,
    },
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2648.30,
        'type': 'SELLERS_REPRICED_HIGHER',
        'delta': 120.3,
        'volume': 950.0,
        'wick_top': 0.35,
        'wick_bot': 0.15,
        'confidence_manual': 0.75,
        'notes': 'Quebra moderada',
        'is_structural': False,
    },
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2651.00,
        'type': 'SELLERS_REPRICED_HIGHER',
        'delta': 180.8,
        'volume': 1200.0,
        'wick_top': 0.50,
        'wick_bot': 0.25,
        'confidence_manual': 0.90,
        'notes': 'Quebra muito forte',
        'is_structural': True,
    },
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2649.80,
        'type': 'SELLERS_REPRICED_HIGHER',
        'delta': 95.2,
        'volume': 800.0,
        'wick_top': 0.30,
        'wick_bot': 0.10,
        'confidence_manual': 0.65,
        'notes': 'Quebra fraca',
        'is_structural': False,
    },
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2650.00,
        'type': 'SELLERS_REPRICED_HIGHER',
        'delta': 160.0,
        'volume': 1100.0,
        'wick_top': 0.45,
        'wick_bot': 0.20,
        'confidence_manual': 0.80,
        'notes': 'Quebra tipica',
        'is_structural': False,
    },
]

# Dados de exemplo - Quebras de compradores (BUYERS_REPRICED_LOWER)
buyers_breaks = [
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2645.50,
        'type': 'BUYERS_REPRICED_LOWER',
        'delta': 140.5,
        'volume': 950.0,
        'wick_top': 0.25,
        'wick_bot': 0.45,
        'confidence_manual': 0.82,
        'notes': 'Quebra de compradores forte',
        'is_structural': True,
    },
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2647.20,
        'type': 'BUYERS_REPRICED_LOWER',
        'delta': 110.3,
        'volume': 850.0,
        'wick_top': 0.20,
        'wick_bot': 0.40,
        'confidence_manual': 0.72,
        'notes': 'Quebra moderada',
        'is_structural': False,
    },
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2644.80,
        'type': 'BUYERS_REPRICED_LOWER',
        'delta': 170.8,
        'volume': 1150.0,
        'wick_top': 0.30,
        'wick_bot': 0.50,
        'confidence_manual': 0.88,
        'notes': 'Quebra muito forte',
        'is_structural': True,
    },
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2646.50,
        'type': 'BUYERS_REPRICED_LOWER',
        'delta': 85.2,
        'volume': 750.0,
        'wick_top': 0.15,
        'wick_bot': 0.35,
        'confidence_manual': 0.60,
        'notes': 'Quebra fraca',
        'is_structural': False,
    },
    {
        'timestamp': datetime.now().timestamp(),
        'symbol': 'XAUUSD',
        'price_broken': 2645.00,
        'type': 'BUYERS_REPRICED_LOWER',
        'delta': 155.0,
        'volume': 1000.0,
        'wick_top': 0.22,
        'wick_bot': 0.42,
        'confidence_manual': 0.78,
        'notes': 'Quebra tipica',
        'is_structural': False,
    },
]

# Adicionar todas as quebras ao dataset
all_breaks = sellers_breaks + buyers_breaks

for i, break_info in enumerate(all_breaks):
    success = dataset.add_liquidity_break(break_info)
    if success:
        print(f"   ✅ Quebra #{i+1}: {break_info['type']}")
    else:
        print(f"   ❌ Erro na quebra #{i+1}")

print()
print(f"✅ Dataset criado com {len(dataset.data)} quebras")
print()

# ============================================================
# TREINAR MODELO
# ============================================================

print("Treinando modelo ML...")
print()

ml_model = LiquidityBreakML()

X, y = dataset.export_for_ml()

print(f"Features: {X.shape}")
print(f"Labels: {y.shape}")
print()

success = ml_model.train(X, y)

if success:
    print("✅ Modelo treinado com sucesso!")
    print()
    print(f"   Arquivo: liquidity_break_model.pkl")
else:
    print("❌ Erro ao treinar modelo")
    sys.exit(1)

print()

# ============================================================
# TESTAR MODELO
# ============================================================

print("Testando modelo...")
print()

# Teste 1: Quebra de vendedores (forte)
pred1, conf1 = ml_model.predict(
    delta=160.0,
    volume=1100.0,
    wick_top=0.45,
    wick_bot=0.20,
    confidence=0.80
)
print(f"Teste 1 (Sellers forte): {pred1} ({conf1:.0%} confiança)")

# Teste 2: Quebra de compradores (forte)
pred2, conf2 = ml_model.predict(
    delta=150.0,
    volume=1000.0,
    wick_top=0.25,
    wick_bot=0.42,
    confidence=0.78
)
print(f"Teste 2 (Buyers forte): {pred2} ({conf2:.0%} confiança)")

# Teste 3: Quebra fraca de vendedores
pred3, conf3 = ml_model.predict(
    delta=90.0,
    volume=700.0,
    wick_top=0.30,
    wick_bot=0.10,
    confidence=0.60
)
print(f"Teste 3 (Sellers fraca): {pred3} ({conf3:.0%} confiança)")

print()

# ============================================================
# ESTATÍSTICAS
# ============================================================

print("=" * 70)
print("✅ MODELO INICIAL CRIADO COM SUCESSO!")
print("=" * 70)
print()

stats = dataset.get_stats()
print("Estatísticas do Dataset:")
print(f"   Total de quebras: {stats['total']}")
print(f"   Sellers Repriced Higher: {stats['sellers_repriced_higher']}")
print(f"   Buyers Repriced Lower: {stats['buyers_repriced_lower']}")
print(f"   Quebras Estruturais: {stats['structural_breaks']}")
print()

print("Arquivos criados:")
print(f"   ✅ liquidity_breaks_dataset.json")
print(f"   ✅ liquidity_break_model.pkl")
print()

print("Próximos passos:")
print("   1. Execute: .\\start.bat")
print("   2. Abra: frontend/liquidity_break_panel.html")
print("   3. Use o painel para adicionar mais quebras e treinar")
print()