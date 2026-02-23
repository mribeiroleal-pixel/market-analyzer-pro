"""Database Models"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class ClusterRecord(Base):
    __tablename__ = 'clusters'
    __table_args__ = (Index('idx_symbol_timestamp', 'symbol', 'timestamp_close'),)
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cluster_id = Column(Integer)
    symbol = Column(String(20))
    price_open = Column(Float)
    price_close = Column(Float)
    price_high = Column(Float)
    price_low = Column(Float)
    delta_final = Column(Float)
    delta_max = Column(Float)
    delta_min = Column(Float)
    vol_total = Column(Float)
    vol_buy = Column(Float)
    vol_sell = Column(Float)
    duration_seconds = Column(Float)
    timestamp_open = Column(DateTime)
    timestamp_close = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    pattern = Column(String(50))
    outcome = Column(String(20), default='PENDENTE')
    liquidity_break = Column(JSON, nullable=True)
    ai_signal = Column(JSON, nullable=True)

class LiquidityBreakRecord(Base):
    __tablename__ = 'liquidity_breaks'
    __table_args__ = (Index('idx_symbol_timestamp', 'symbol', 'timestamp'),)
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String(20))
    break_type = Column(String(50))
    mechanism = Column(String(20))
    confidence = Column(Float)
    delta = Column(Float)
    is_structural = Column(Boolean, default=False)
    timestamp = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
