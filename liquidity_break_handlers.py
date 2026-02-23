"""
WebSocket Handlers para Liquidity Break
"""

import json
import logging
from liquidity_break_ml import dataset, ml_model

logger = logging.getLogger(__name__)


async def handle_liquidity_break_commands(websocket, message_data):
    """Processa comandos de liquidity break"""
    
    command = message_data.get('command')
    
    # ========== ADD BREAK ==========
    if command == 'add_liquidity_break':
        break_info = {
            'timestamp': message_data.get('timestamp'),
            'symbol': message_data.get('symbol', 'XAUUSD'),
            'price_broken': message_data.get('price_broken'),
            'type': message_data.get('type'),  # SELLERS_REPRICED_HIGHER ou BUYERS_REPRICED_LOWER
            'delta': message_data.get('delta'),
            'volume': message_data.get('volume'),
            'wick_top': message_data.get('wick_top'),
            'wick_bot': message_data.get('wick_bot'),
            'confidence_manual': message_data.get('confidence_manual', 0.7),
            'notes': message_data.get('notes', ''),
            'is_structural': message_data.get('is_structural', False),
        }
        
        success = dataset.add_liquidity_break(break_info)
        
        await websocket.send(json.dumps({
            'type': 'liquidity_break_added',
            'success': success,
            'break_id': len(dataset.data) if success else None,
        }))
    
    # ========== GET ALL BREAKS ==========
    elif command == 'get_liquidity_breaks':
        symbol = message_data.get('symbol', 'XAUUSD')
        breaks = dataset.get_breaks_by_symbol(symbol)
        
        await websocket.send(json.dumps({
            'type': 'liquidity_breaks_list',
            'data': breaks,
            'count': len(breaks),
        }, default=str))
    
    # ========== GET STATS ==========
    elif command == 'get_liquidity_stats':
        stats = dataset.get_stats()
        
        await websocket.send(json.dumps({
            'type': 'liquidity_stats',
            'data': stats,
        }))
    
    # ========== TRAIN ML ==========
    elif command == 'train_liquidity_ml':
        X, y = dataset.export_for_ml()
        
        if len(X) < 5:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': f'Dados insuficientes: {len(X)}/5',
            }))
            return
        
        success = ml_model.train(X, y)
        
        await websocket.send(json.dumps({
            'type': 'liquidity_ml_trained',
            'success': success,
            'samples': len(X),
        }))
    
    # ========== PREDICT BREAK ==========
    elif command == 'predict_liquidity_break':
        delta = message_data.get('delta')
        volume = message_data.get('volume')
        wick_top = message_data.get('wick_top')
        wick_bot = message_data.get('wick_bot')
        confidence = message_data.get('confidence', 0.5)
        
        break_type, prob = ml_model.predict(delta, volume, wick_top, wick_bot, confidence)
        
        await websocket.send(json.dumps({
            'type': 'liquidity_prediction',
            'break_type': break_type,
            'confidence': prob,
        }))
    
    # ========== UPDATE BREAK ==========
    elif command == 'update_liquidity_break':
        break_id = message_data.get('break_id')
        updates = {
            'type': message_data.get('type'),
            'confidence_manual': message_data.get('confidence_manual'),
            'notes': message_data.get('notes'),
            'is_structural': message_data.get('is_structural'),
        }
        
        success = dataset.update_break(break_id, {k: v for k, v in updates.items() if v is not None})
        
        await websocket.send(json.dumps({
            'type': 'liquidity_break_updated',
            'success': success,
        }))
    
    # ========== DELETE BREAK ==========
    elif command == 'delete_liquidity_break':
        break_id = message_data.get('break_id')
        
        dataset.data = [b for b in dataset.data if b.get('id') != break_id]
        dataset.save()
        
        await websocket.send(json.dumps({
            'type': 'liquidity_break_deleted',
            'success': True,
        }))
    
    # ========== GET ML STATUS ==========
    elif command == 'get_liquidity_ml_status':
        await websocket.send(json.dumps({
            'type': 'liquidity_ml_status',
            'is_trained': ml_model.is_trained,
            'dataset_size': len(dataset.data),
            'stats': dataset.get_stats(),
        }))