"""
Database Repository — Market Analyst Pro
SQLite (padrão) ou PostgreSQL via SQLAlchemy.
Persiste clusters, ticks e liquidity breaks com todos os campos do sistema.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("db")

try:
    from sqlalchemy import (
        create_engine, Column, Integer, String, Float,
        DateTime, Boolean, JSON, Index, Text,
    )
    from sqlalchemy.orm import declarative_base, sessionmaker
    _SA_AVAILABLE = True
except ImportError:
    _SA_AVAILABLE = False
    logger.warning("SQLAlchemy not installed — DB disabled")

if _SA_AVAILABLE:
    Base = declarative_base()

    class ClusterRecord(Base):
        __tablename__ = "clusters"
        __table_args__ = (Index("idx_cluster_sym_ts", "symbol", "timestamp_close"),)

        id               = Column(String(36), primary_key=True)
        cluster_id       = Column(Integer, index=True)
        symbol           = Column(String(20), index=True)
        price_open       = Column(Float)
        price_close      = Column(Float)
        price_high       = Column(Float)
        price_low        = Column(Float)
        price_range      = Column(Float)
        delta_final      = Column(Float)
        delta_max        = Column(Float)
        delta_min        = Column(Float)
        delta_direction  = Column(String(10))
        vol_total        = Column(Float)
        vol_buy          = Column(Float)
        vol_sell         = Column(Float)
        vol_efficiency   = Column(Float)
        wick_ratio_top   = Column(Float)
        wick_ratio_bot   = Column(Float)
        duration_seconds = Column(Float)
        tick_count       = Column(Integer)
        ticks_per_second = Column(Float)
        timestamp_open   = Column(DateTime)
        timestamp_close  = Column(DateTime, index=True)
        created_at       = Column(DateTime, default=datetime.utcnow)
        pattern              = Column(String(60))
        pattern_confidence   = Column(Float)
        analyst_signals      = Column(JSON, nullable=True)
        outcome              = Column(String(20), default="PENDENTE")
        next_price_change    = Column(Float, nullable=True)
        ml_prediction        = Column(JSON, nullable=True)
        liquidity_break      = Column(JSON, nullable=True)
        ai_signal            = Column(JSON, nullable=True)

    class TickRecord(Base):
        __tablename__ = "ticks"
        __table_args__ = (Index("idx_tick_sym_ts", "symbol", "timestamp"),)

        id         = Column(Integer, primary_key=True, autoincrement=True)
        symbol     = Column(String(20), index=True)
        price      = Column(Float)
        side       = Column(String(10))
        volume     = Column(Float)
        spread     = Column(Float, default=0.0)
        timestamp  = Column(Float, index=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class LiquidityBreakRecord(Base):
        __tablename__ = "liquidity_breaks"
        __table_args__ = (Index("idx_lb_sym_ts", "symbol", "timestamp"),)

        id            = Column(String(36), primary_key=True)
        symbol        = Column(String(20), index=True)
        break_type    = Column(String(50))
        mechanism     = Column(String(20))
        confidence    = Column(Float)
        delta         = Column(Float)
        is_structural = Column(Boolean, default=False)
        timestamp     = Column(DateTime, index=True)
        created_at    = Column(DateTime, default=datetime.utcnow)
        notes         = Column(Text, nullable=True)
        extra         = Column(JSON, nullable=True)


class Database:
    """Interface principal para persistência."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        if not _SA_AVAILABLE:
            raise RuntimeError("SQLAlchemy not installed — pip install sqlalchemy")

        self._url = database_url or "sqlite:///market_analyst.db"
        connect_args = {"check_same_thread": False} if self._url.startswith("sqlite") else {}

        self._engine = create_engine(
            self._url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False,
        )
        self._Session = sessionmaker(bind=self._engine, expire_on_commit=False)
        Base.metadata.create_all(self._engine)
        logger.info(f"Database ready: {self._url.split('://')[0]}")

    def get_session(self):
        return self._Session()

    # ── clusters ──────────────────────────────────────────────────────────────
    def save_cluster(self, data: Dict[str, Any]) -> bool:
        import uuid
        try:
            session = self.get_session()
            rec = ClusterRecord(
                id               = data.get("id") or str(uuid.uuid4()),
                cluster_id       = int(data.get("cluster_id", 0)),
                symbol           = str(data.get("symbol", "XAUUSD")),
                price_open       = _f(data.get("price_open")),
                price_close      = _f(data.get("price_close")),
                price_high       = _f(data.get("price_high")),
                price_low        = _f(data.get("price_low")),
                price_range      = _f(data.get("price_range")),
                delta_final      = _f(data.get("delta_final")),
                delta_max        = _f(data.get("delta_max")),
                delta_min        = _f(data.get("delta_min")),
                delta_direction  = str(data.get("delta_direction", "neutral")),
                vol_total        = _f(data.get("vol_total")),
                vol_buy          = _f(data.get("vol_buy")),
                vol_sell         = _f(data.get("vol_sell")),
                vol_efficiency   = _f(data.get("vol_efficiency")),
                wick_ratio_top   = _f(data.get("wick_ratio_top")),
                wick_ratio_bot   = _f(data.get("wick_ratio_bot")),
                duration_seconds = _f(data.get("duration_seconds")),
                tick_count       = int(data.get("tick_count", 0)),
                ticks_per_second = _f(data.get("ticks_per_second")),
                timestamp_open   = _dt(data.get("timestamp_open")),
                timestamp_close  = _dt(data.get("timestamp_close")) or datetime.utcnow(),
                pattern              = str(data.get("pattern", "UNKNOWN")),
                pattern_confidence   = _f(data.get("pattern_confidence")),
                analyst_signals      = data.get("analyst_signals"),
                outcome              = str(data.get("outcome", "PENDENTE")),
                next_price_change    = _f(data.get("next_price_change")),
                ml_prediction        = data.get("ml_prediction"),
                liquidity_break      = data.get("liquidity_break"),
                ai_signal            = data.get("ai_signal"),
            )
            session.add(rec)
            session.commit()
            session.close()
            return True
        except Exception as exc:
            logger.error(f"save_cluster error: {exc}")
            return False

    def get_clusters(
        self,
        symbol: str,
        limit: int = 500,
        outcome_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            session = self.get_session()
            q = session.query(ClusterRecord).filter(ClusterRecord.symbol == symbol)
            if outcome_filter:
                q = q.filter(ClusterRecord.outcome == outcome_filter)
            rows = q.order_by(ClusterRecord.timestamp_close.desc()).limit(limit).all()
            result = [_cluster_to_dict(r) for r in rows]
            session.close()
            return result
        except Exception as exc:
            logger.error(f"get_clusters error: {exc}")
            return []

    def update_cluster_outcome(
        self, cluster_id: int, symbol: str, outcome: str, next_price_change: float = 0.0
    ) -> bool:
        try:
            session = self.get_session()
            rec = session.query(ClusterRecord).filter(
                ClusterRecord.cluster_id == cluster_id,
                ClusterRecord.symbol == symbol,
            ).first()
            if rec:
                rec.outcome = outcome
                rec.next_price_change = next_price_change
                session.commit()
            session.close()
            return rec is not None
        except Exception as exc:
            logger.error(f"update_outcome error: {exc}")
            return False

    def get_labeled_clusters(self, symbol: str, limit: int = 10000) -> List[Dict[str, Any]]:
        """Retorna clusters com outcome != PENDENTE — para treino ML."""
        try:
            session = self.get_session()
            rows = (
                session.query(ClusterRecord)
                .filter(
                    ClusterRecord.symbol == symbol,
                    ClusterRecord.outcome != "PENDENTE",
                )
                .order_by(ClusterRecord.timestamp_close.asc())
                .limit(limit)
                .all()
            )
            result = [_cluster_to_dict(r) for r in rows]
            session.close()
            return result
        except Exception as exc:
            logger.error(f"get_labeled_clusters error: {exc}")
            return []

    # ── ticks ─────────────────────────────────────────────────────────────────
    def save_tick(self, tick: Dict[str, Any]) -> None:
        try:
            session = self.get_session()
            rec = TickRecord(
                symbol    = tick.get("symbol", "XAUUSD"),
                price     = _f(tick.get("price")),
                side      = tick.get("side", "neutral"),
                volume    = _f(tick.get("volume_synthetic", tick.get("volume", 0.0))),
                spread    = _f(tick.get("spread", 0.0)),
                timestamp = float(tick.get("timestamp", time.time())),
            )
            session.add(rec)
            session.commit()
            session.close()
        except Exception:
            pass  # ticks são não-críticos

    def get_ticks(self, symbol: str, hours: float = 1.0) -> List[Dict[str, Any]]:
        try:
            cutoff_ts = time.time() - hours * 3600
            session = self.get_session()
            rows = (
                session.query(TickRecord)
                .filter(TickRecord.symbol == symbol, TickRecord.timestamp >= cutoff_ts)
                .order_by(TickRecord.timestamp.asc())
                .limit(100_000)
                .all()
            )
            result = [
                {
                    "price": r.price, "side": r.side,
                    "volume_synthetic": r.volume, "spread": r.spread,
                    "timestamp": r.timestamp, "symbol": r.symbol,
                }
                for r in rows
            ]
            session.close()
            return result
        except Exception as exc:
            logger.error(f"get_ticks error: {exc}")
            return []

    # ── liquidity breaks ──────────────────────────────────────────────────────
    def save_liquidity_break(self, data: Dict[str, Any]) -> bool:
        import uuid
        try:
            session = self.get_session()
            rec = LiquidityBreakRecord(
                id            = data.get("id") or str(uuid.uuid4()),
                symbol        = data.get("symbol", "XAUUSD"),
                break_type    = data.get("type", "UNKNOWN"),
                mechanism     = data.get("mechanism", "UNKNOWN"),
                confidence    = _f(data.get("confidence", 0.5)),
                delta         = _f(data.get("delta", 0.0)),
                is_structural = bool(data.get("is_structural", False)),
                timestamp     = _dt(data.get("timestamp")) or datetime.utcnow(),
                notes         = data.get("notes", ""),
                extra         = data.get("extra"),
            )
            session.add(rec)
            session.commit()
            session.close()
            return True
        except Exception as exc:
            logger.error(f"save_liquidity_break error: {exc}")
            return False

    def get_liquidity_breaks(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            session = self.get_session()
            rows = (
                session.query(LiquidityBreakRecord)
                .filter(LiquidityBreakRecord.symbol == symbol)
                .order_by(LiquidityBreakRecord.timestamp.desc())
                .limit(limit)
                .all()
            )
            result = [
                {
                    "id": r.id, "symbol": r.symbol, "type": r.break_type,
                    "mechanism": r.mechanism, "confidence": r.confidence,
                    "delta": r.delta, "is_structural": r.is_structural,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "notes": r.notes,
                }
                for r in rows
            ]
            session.close()
            return result
        except Exception as exc:
            logger.error(f"get_liquidity_breaks error: {exc}")
            return []


# ── helpers ───────────────────────────────────────────────────────────────────
def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.utcfromtimestamp(float(v))
    except (TypeError, ValueError):
        return None


def _cluster_to_dict(r: Any) -> Dict[str, Any]:
    return {
        "id": r.id, "cluster_id": r.cluster_id, "symbol": r.symbol,
        "price_open": r.price_open, "price_close": r.price_close,
        "price_high": r.price_high, "price_low": r.price_low,
        "price_range": r.price_range, "delta_final": r.delta_final,
        "delta_max": r.delta_max, "delta_min": r.delta_min,
        "delta_direction": r.delta_direction,
        "vol_total": r.vol_total, "vol_buy": r.vol_buy,
        "vol_sell": r.vol_sell, "vol_efficiency": r.vol_efficiency,
        "wick_ratio_top": r.wick_ratio_top, "wick_ratio_bot": r.wick_ratio_bot,
        "duration_seconds": r.duration_seconds, "tick_count": r.tick_count,
        "ticks_per_second": r.ticks_per_second,
        "timestamp_open": r.timestamp_open.timestamp() if r.timestamp_open else None,
        "timestamp_close": r.timestamp_close.timestamp() if r.timestamp_close else None,
        "pattern": r.pattern, "pattern_confidence": r.pattern_confidence,
        "analyst_signals": r.analyst_signals, "outcome": r.outcome,
        "next_price_change": r.next_price_change, "ml_prediction": r.ml_prediction,
        "liquidity_break": r.liquidity_break, "ai_signal": r.ai_signal,
    }
