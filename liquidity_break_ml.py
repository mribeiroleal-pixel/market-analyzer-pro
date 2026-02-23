"""Liquidity Break ML"""

import json
import pickle
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class LiquidityBreakDataset:
    def __init__(self, dataset_path: str = "liquidity_breaks_dataset.json"):
        self.dataset_path = dataset_path
        self.data: List[Dict] = []
        self.load()
    
    def load(self):
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
        try:
            with open(self.dataset_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, default=str)
            logger.info(f"OK: Dataset salvo: {len(self.data)} quebras")
        except Exception as e:
            logger.error(f"ERROR ao salvar dataset: {e}")
    
    def add_liquidity_break(self, break_info: Dict) -> bool:
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
        return [b for b in self.data if b.get('symbol') == symbol]
    
    def export_for_ml(self) -> Tuple[np.ndarray, np.ndarray]:
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
    def __init__(self, model_path: str = "liquidity_break_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.is_trained = False
    
    def train(self, X: np.ndarray, y: np.ndarray) -> bool:
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
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump({'model': self.model, 'scaler': self.scaler}, f)
            logger.info(f"OK: Modelo salvo: {self.model_path}")
        except Exception as e:
            logger.error(f"ERROR ao salvar: {e}")
    
    def load(self) -> bool:
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
