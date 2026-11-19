"""Tablas del pipeline definidas con SQLAlchemy (ORM): cada clase de Python = una tabla.
Hoy usa SQLite (data/emo.db). Para PostgreSQL o MySQL basta con definir DATABASE_URL en el .env, por ejemplo:
    DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/emo
"""
import os
from datetime import date

from sqlalchemy import JSON, Date, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.db import RUTA_DB

RUTA_DB.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{RUTA_DB.as_posix()}")


class Base(DeclarativeBase):
    """Clase base de la que heredan todas las tablas."""


class Documento(Base):
    """Documentos que pasaron el ETL (solo los 'processed'). Una fila = un documento."""
    __tablename__ = "documentos"

    document_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(16), index=True)
    document_date: Mapped[date | None] = mapped_column(Date)   # fecha real, no texto
    dates_found: Mapped[list] = mapped_column(JSON, default=list)
    word_count: Mapped[int] = mapped_column(Integer)
    ingested_at: Mapped[str] = mapped_column(String(32))
    processed_at: Mapped[str] = mapped_column(String(32))
    loaded_at: Mapped[str] = mapped_column(String(32))
    issues: Mapped[list] = mapped_column(JSON, default=list)


class EjecucionETL(Base):
    """Bitácora: una fila por cada vez que se ejecuta la carga (cuándo, cuántos y qué pasó con cada documento)."""
    __tablename__ = "ejecuciones_etl"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inicio: Mapped[str] = mapped_column(String(32))
    fin: Mapped[str | None] = mapped_column(String(32))
    estado: Mapped[str] = mapped_column(String(20))          # en_curso | ok | con_errores
    total: Mapped[int] = mapped_column(Integer, default=0)
    insertados: Mapped[int] = mapped_column(Integer, default=0)
    actualizados: Mapped[int] = mapped_column(Integer, default=0)
    sin_cambios: Mapped[int] = mapped_column(Integer, default=0)
    omitidos: Mapped[int] = mapped_column(Integer, default=0)
    errores: Mapped[int] = mapped_column(Integer, default=0)
    detalle: Mapped[list] = mapped_column(JSON, default=list)  # [{document_id, filename, accion, motivo}, ...]


engine = create_engine(DATABASE_URL)
Sesion = sessionmaker(engine)


def crear_tablas():
    """Crea las tablas si no existen (no borra ni modifica las que ya están)."""
    Base.metadata.create_all(engine)
