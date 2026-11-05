"""Base de datos SQLite: un solo archivo, sin servidor. Guarda asignaciones e historial de cambios."""
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

RUTA_DB = Path(__file__).resolve().parent.parent / "data" / "emo.db"

CAMPOS = [
    "nombre", "documento", "cargo", "despacho", "ciudad", "correo", "celular",
    "fecha_requerimiento", "mes_programado", "fecha_programacion", "hora", "sede",
    "tipo_examen", "examenes", "estado", "notas",
]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS asignaciones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT NOT NULL,
    documento           TEXT,
    cargo               TEXT,
    despacho            TEXT,
    ciudad              TEXT,
    correo              TEXT,
    celular             TEXT,
    fecha_requerimiento TEXT,   -- AAAA-MM-DD
    mes_programado      TEXT,   -- ENERO..DICIEMBRE
    fecha_programacion  TEXT,   -- AAAA-MM-DD
    hora                TEXT,   -- HH:MM
    sede                TEXT,   -- dirección de la IPS
    tipo_examen         TEXT,
    examenes            TEXT,   -- lista separada por ' | '
    estado              TEXT NOT NULL DEFAULT 'FALTA POR AGENDAR',
    notas               TEXT,
    origen              TEXT,   -- de dónde vino (hoja y fila del Excel, o 'app')
    creado_en           TEXT,
    actualizado_en      TEXT
);
CREATE INDEX IF NOT EXISTS ix_doc    ON asignaciones(documento);
CREATE INDEX IF NOT EXISTS ix_estado ON asignaciones(estado);
CREATE INDEX IF NOT EXISTS ix_fecha  ON asignaciones(fecha_programacion);

CREATE TABLE IF NOT EXISTS historial (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    asignacion_id  INTEGER NOT NULL,
    campo          TEXT,
    valor_anterior TEXT,
    valor_nuevo    TEXT,
    usuario        TEXT,
    fecha          TEXT
);
"""


def conectar(ruta=RUTA_DB, solo_lectura=False):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if solo_lectura:
        con = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    else:
        con = sqlite3.connect(ruta, check_same_thread=False)
        con.executescript(ESQUEMA)
    con.row_factory = sqlite3.Row
    return con


def _ahora():
    return datetime.now().isoformat(timespec="seconds")


def insertar(con, datos: dict, origen="app"):
    fila = {c: datos.get(c) for c in CAMPOS}
    fila.update(origen=origen, creado_en=_ahora(), actualizado_en=_ahora())
    cols = ", ".join(fila)
    marcas = ", ".join("?" for _ in fila)
    cur = con.execute(f"INSERT INTO asignaciones ({cols}) VALUES ({marcas})", list(fila.values()))
    con.commit()
    return cur.lastrowid


def actualizar(con, id_: int, cambios: dict, usuario="app"):
    actual = dict(con.execute("SELECT * FROM asignaciones WHERE id=?", (id_,)).fetchone())
    reales = {k: v for k, v in cambios.items() if k in CAMPOS and (v or None) != (actual.get(k) or None)}
    if not reales:
        return 0
    for campo, nuevo in reales.items():
        con.execute(
            "INSERT INTO historial (asignacion_id, campo, valor_anterior, valor_nuevo, usuario, fecha) VALUES (?,?,?,?,?,?)",
            (id_, campo, actual.get(campo), nuevo, usuario, _ahora()),
        )
    sets = ", ".join(f"{k}=?" for k in reales) + ", actualizado_en=?"
    con.execute(f"UPDATE asignaciones SET {sets} WHERE id=?", [*reales.values(), _ahora(), id_])
    con.commit()
    return len(reales)


def eliminar(con, id_: int, usuario="app"):
    con.execute(
        "INSERT INTO historial (asignacion_id, campo, valor_anterior, valor_nuevo, usuario, fecha) VALUES (?,?,?,?,?,?)",
        (id_, "*ELIMINADO*", None, None, usuario, _ahora()),
    )
    con.execute("DELETE FROM asignaciones WHERE id=?", (id_,))
    con.commit()


def todas(con) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM asignaciones ORDER BY id", con)


def historial(con, id_: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT fecha, usuario, campo, valor_anterior, valor_nuevo FROM historial WHERE asignacion_id=? ORDER BY id DESC",
        con, params=(id_,),
    )


def vaciar(con):
    con.executescript("DELETE FROM asignaciones; DELETE FROM historial; DELETE FROM sqlite_sequence;")
    con.commit()
