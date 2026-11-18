"""Base de datos SQLite: un solo archivo, sin servidor. Guarda asignaciones e historial de cambios."""
"""La base de datos. Todo lo demás guarda o lee aquí"""
"""
db.py — Capa de acceso a datos (persistencia) del Gestor EMO.

RESPONSABILIDAD
    Es el ÚNICO archivo que habla directamente con la base de datos.
    Crea las tablas, guarda, actualiza, borra y consulta asignaciones,
    y deja registro de cada cambio en la tabla `historial`.
    Ningún otro archivo debería escribir SQL de INSERT/UPDATE/DELETE:
    si necesitan guardar algo, llaman a una función de aquí.

BASE DE DATOS
    SQLite: un solo archivo (data/emo.db), sin servidor que instalar.
    Tablas:
      - asignaciones : una fila por cada solicitud de examen médico ocupacional.
      - historial    : una fila por cada campo que se cambia (auditoría).

QUIÉN USA ESTE ARCHIVO (API pública)
    Si cambias el NOMBRE, los PARÁMETROS o lo que DEVUELVE una de estas
    funciones, debes actualizar también los archivos de la derecha:

      conectar()    → app.py, consulta_ia.py, importar_excel.py
      insertar()    → app.py (Nueva asignación), importar_excel.py
      actualizar()  → app.py (guardar ficha)
      eliminar()    → app.py (Calidad de datos)
      todas()       → app.py
      historial()   → app.py (historial de la ficha)
      vaciar()      → importar_excel.py (modo "Reemplazar todo")
      RUTA_DB       → consulta_ia.py

    Lo que empieza con guion bajo (_ahora) es de uso INTERNO: se puede
    cambiar libremente sin afectar a otros archivos.

PENDIENTES PARA EL SPRINT 2 (no cambiar todavía)
    1. Las fechas se guardan como TEXT ('AAAA-MM-DD'): la base no impide
       guardar una fecha inválida. En MySQL/PostgreSQL se usaría DATE.
    2. `historial.asignacion_id` no declara FOREIGN KEY (la relación solo
       existe en la lógica). Es a propósito: al eliminar una asignación,
       su historial se conserva como auditoría.
    3. La tabla no está normalizada: la persona se repite en cada
       asignación y `examenes` es texto separado por ' | '.
    4. Hay SQL propio de SQLite (los '?' , 'mode=ro', 'sqlite_sequence').
       Con SQLAlchemy se podría cambiar a MySQL/PostgreSQL sin reescribir esto.
    5. eliminar() borra de verdad (borrado físico). Alternativa a evaluar:
       borrado lógico (columna `eliminado = 1`).
"""

import sqlite3   # Librería estándar de Python para SQLite (no hay que instalarla)
from datetime import datetime   # Para guardar la fecha y hora de cada cambio
from pathlib import Path   # Manejo de rutas que funciona igual en Windows, Mac y Linux

import pandas as pd     # Para devolver resultados como tablas (DataFrame)


RUTA_DB = Path(__file__).resolve().parent.parent / "data" / "emo.db"
# Columnas que se pueden escribir desde fuera. Si agregas una columna a la tabla, agrégala aquí.
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
    """Abre la base (y crea las tablas si no existen). Usada por app.py, consulta_ia.py e importar_excel.py."""
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
    """Fecha y hora actual en texto ISO. Uso interno."""
    return datetime.now().isoformat(timespec="seconds")


def insertar(con, datos: dict, origen="app"):
    """Crea una asignación y devuelve su id. Usada por app.py (Nueva asignación) e importar_excel.py."""
    fila = {c: datos.get(c) for c in CAMPOS}
    fila.update(origen=origen, creado_en=_ahora(), actualizado_en=_ahora())
    cols = ", ".join(fila)
    marcas = ", ".join("?" for _ in fila)
    cur = con.execute(f"INSERT INTO asignaciones ({cols}) VALUES ({marcas})", list(fila.values()))
    con.commit()
    return cur.lastrowid


def actualizar(con, id_: int, cambios: dict, usuario="app"):
    """Crea una asignación y devuelve su id. Usada por app.py (Nueva asignación) e importar_excel.py."""
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
    """Borra una asignación y deja constancia en el historial. Usada por app.py (Calidad de datos)."""
    con.execute(
        "INSERT INTO historial (asignacion_id, campo, valor_anterior, valor_nuevo, usuario, fecha) VALUES (?,?,?,?,?,?)",
        (id_, "*ELIMINADO*", None, None, usuario, _ahora()),
    )
    con.execute("DELETE FROM asignaciones WHERE id=?", (id_,))
    con.commit()


def todas(con) -> pd.DataFrame:
    """Devuelve todas las asignaciones como tabla. Usada por app.py."""
    return pd.read_sql_query("SELECT * FROM asignaciones ORDER BY id", con)


def historial(con, id_: int) -> pd.DataFrame:
    """Devuelve todas las asignaciones como tabla. Usada por app.py."""
    return pd.read_sql_query(
        "SELECT fecha, usuario, campo, valor_anterior, valor_nuevo FROM historial WHERE asignacion_id=? ORDER BY id DESC",
        con, params=(id_,),
    )


def vaciar(con):
    """⚠️ Borra todas las asignaciones y el historial. Usada por importar_excel.py (Reemplazar todo)."""
    con.executescript("DELETE FROM asignaciones; DELETE FROM historial; DELETE FROM sqlite_sequence;")
    con.commit()
