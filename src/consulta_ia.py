"""Preguntas en lenguaje natural → SQL con Gemini.

PRIVACIDAD: a Gemini solo se le envía la ESTRUCTURA de la tabla (nombres de columnas y
valores posibles de estado/ciudad/tipo) y la pregunta. Los datos de las personas
NUNCA salen del computador: la consulta se ejecuta aquí, sobre la base local, en modo solo lectura.
"""
import os
import re
from datetime import date

import pandas as pd

from . import config, db

MODELO = "gemini-3.5-flash"
LIMITE_FILAS = 500

ESQUEMA_TEXTO = """Tabla: asignaciones (una fila = una solicitud de examen médico ocupacional de un servidor judicial)
- id INTEGER
- nombre TEXT (MAYÚSCULAS, nombre completo)
- documento TEXT (cédula, solo dígitos)
- cargo TEXT (MAYÚSCULAS: JUEZ, CITADOR, ESCRIBIENTE, OFICIAL MAYOR, SECRETARIO, ...)
- despacho TEXT (juzgado u oficina)
- ciudad TEXT (MAYÚSCULAS sin tildes)
- correo TEXT, celular TEXT
- fecha_requerimiento TEXT 'AAAA-MM-DD' (cuándo se solicitó)
- mes_programado TEXT (mes previsto en mayúsculas: ENERO..DICIEMBRE, puede ser NULL)
- fecha_programacion TEXT 'AAAA-MM-DD' (cita del examen, puede ser NULL)
- hora TEXT 'HH:MM'
- sede TEXT (dirección de la IPS)
- tipo_examen TEXT
- examenes TEXT (pruebas separadas por ' | ', buscar con LIKE '%OPTOMETRÍA%')
- estado TEXT
- notas TEXT
"""


def _valores(con, campo):
    filas = con.execute(f"SELECT DISTINCT {campo} FROM asignaciones WHERE {campo} IS NOT NULL ORDER BY 1").fetchall()
    return [f[0] for f in filas]


def construir_prompt(con, pregunta):
    return f"""Eres un experto en SQLite. Convierte la pregunta del usuario en UNA sola consulta SQL SELECT.

{ESQUEMA_TEXTO}
Valores existentes:
- estado: {config.ESTADOS}
- ciudad: {_valores(con, 'ciudad')}
- tipo_examen: {_valores(con, 'tipo_examen')}
- examenes posibles: {config.EXAMENES}

Reglas:
- Solo SELECT (o WITH ... SELECT). Nunca INSERT, UPDATE, DELETE, DROP, ALTER, PRAGMA ni ATTACH.
- Para buscar texto usa UPPER(columna) LIKE UPPER('%texto%').
- Hoy es {date.today().isoformat()}. Para fechas usa date('now', ...) o comparaciones de texto 'AAAA-MM-DD'.
- Si piden listar personas, devuelve: id, nombre, documento, ciudad, tipo_examen, estado, fecha_programacion, hora, sede.
- Si piden cantidades, usa COUNT(*) con nombres de columna claros en español (AS total, AS ciudad...).
- Responde SOLO con el SQL, sin explicación y sin ```.

Pregunta: {pregunta}"""


def limpiar_sql(texto: str) -> str:
    sql = re.sub(r"^```(?:sql)?|```$", "", texto.strip(), flags=re.I | re.M).strip().rstrip(";").strip()
    if ";" in sql:
        raise ValueError("La IA devolvió más de una instrucción; la descarté por seguridad.")
    if not re.match(r"^(SELECT|WITH)\b", sql, re.I):
        raise ValueError("La IA no devolvió una consulta de lectura (SELECT); la descarté por seguridad.")
    if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|PRAGMA|ATTACH|DETACH|VACUUM)\b", sql, re.I):
        raise ValueError("La consulta contiene instrucciones no permitidas; la descarté por seguridad.")
    return sql


def ejecutar(sql: str, ruta=db.RUTA_DB) -> pd.DataFrame:
    con_ro = db.conectar(ruta, solo_lectura=True)  # aunque la IA se equivoque, no puede modificar nada
    try:
        return pd.read_sql_query(f"SELECT * FROM ({sql}) LIMIT {LIMITE_FILAS}", con_ro)
    finally:
        con_ro.close()


def preguntar(con, pregunta: str, ruta=db.RUTA_DB, cliente=None):
    """Devuelve (sql, DataFrame)."""
    if cliente is None:
        from google import genai
        clave = os.environ.get("GEMINI_API_KEY")
        if not clave:
            raise RuntimeError("Falta GEMINI_API_KEY en el archivo .env")
        cliente = genai.Client(api_key=clave)
    from google.genai import types
    resp = cliente.models.generate_content(
        model=MODELO,
        contents=construir_prompt(con, pregunta),
        config=types.GenerateContentConfig(temperature=0),
    )
    sql = limpiar_sql(resp.text)
    return sql, ejecutar(sql, ruta)
