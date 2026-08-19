"""
数据库会话管理
- 默认 SQLite（零依赖，开箱即用）：data/stock.db
- 可切换 MySQL / PostgreSQL：设置环境变量 DATABASE_URL
  MySQL:      DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/stock
  PostgreSQL: DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/stock
"""
import os
from pathlib import Path
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from backend.db.base import Base

# ---- 数据库 URL 解析 ----
def _get_db_url() -> str:
    # 优先环境变量
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    # 默认 SQLite
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "stock.db"
    return f"sqlite:///{db_path}"


DATABASE_URL = _get_db_url()

# ---- 引擎创建 ----
_engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

db_engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True, **_engine_kwargs)

# SQLite 性能优化
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(db_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB
        cursor.close()

_SessionFactory = sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """获取数据库会话（上下文管理器，自动关闭）"""
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """建表（如果不存在）"""
    Base.metadata.create_all(db_engine)
