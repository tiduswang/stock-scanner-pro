"""
数据库表模型
- Stock:        股票列表（代码/名称/拼音/板块/市场）
- DailyKline:   日K线行情（本地缓存，收盘后批量同步）
- RealtimeSnapshot: 实时快照缓存（盘中按需刷新）
- SyncLog:      数据同步日志
"""
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, Text, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Stock(Base):
    """股票列表（A股/港股/ETF统一表）"""
    __tablename__ = "stocks"

    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    pinyin: Mapped[str] = mapped_column(String(128), default="", index=True)
    first_letter: Mapped[str] = mapped_column(String(64), default="", index=True)
    sector: Mapped[str] = mapped_column(String(64), default="")
    market: Mapped[str] = mapped_column(String(8), default="A", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "code": self.code, "name": self.name, "pinyin": self.pinyin,
            "first_letter": self.first_letter, "sector": self.sector, "market": self.market,
        }


class DailyKline(Base):
    """日K线数据（本地缓存）"""
    __tablename__ = "daily_klines"
    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_code_date"),
        Index("ix_code_date", "code", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(12), index=True)
    market: Mapped[str] = mapped_column(String(8), default="A")
    trade_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    open: Mapped[float] = mapped_column(Float, default=0.0)
    close: Mapped[float] = mapped_column(Float, default=0.0)
    high: Mapped[float] = mapped_column(Float, default=0.0)
    low: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    turnover: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RealtimeSnapshot(Base):
    """实时行情快照缓存"""
    __tablename__ = "realtime_snapshots"

    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    market: Mapped[str] = mapped_column(String(8), default="A")
    name: Mapped[str] = mapped_column(String(64), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    change_amt: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    turnover: Mapped[float] = mapped_column(Float, default=0.0)
    amplitude: Mapped[float] = mapped_column(Float, default=0.0)
    high: Mapped[float] = mapped_column(Float, default=0.0)
    low: Mapped[float] = mapped_column(Float, default=0.0)
    open: Mapped[float] = mapped_column(Float, default=0.0)
    prev_close: Mapped[float] = mapped_column(Float, default=0.0)
    turnover_rate: Mapped[float] = mapped_column(Float, default=0.0)
    pe: Mapped[float] = mapped_column(Float, default=0.0)
    pb: Mapped[float] = mapped_column(Float, default=0.0)
    market_cap: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "code": self.code, "name": self.name, "price": self.price,
            "change_pct": self.change_pct, "change_amt": self.change_amt,
            "volume": self.volume, "turnover": self.turnover, "amplitude": self.amplitude,
            "high": self.high, "low": self.low, "open": self.open,
            "prev_close": self.prev_close, "turnover_rate": self.turnover_rate,
            "pe": self.pe, "pb": self.pb, "market_cap": self.market_cap,
        }


class SyncLog(Base):
    """数据同步日志"""
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sync_type: Mapped[str] = mapped_column(String(32))  # stock_list / daily_kline / snapshot
    market: Mapped[str] = mapped_column(String(8), default="ALL")
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/running/done/error
    error_msg: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
