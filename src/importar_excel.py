"""Convierte el Excel actual en registros limpios para la base de datos.

Uso desde la terminal:
    python -m src.importar_excel "ruta/al/archivo.xlsx"            (importa la hoja principal)
    python -m src.importar_excel "ruta/al/archivo.xlsx" --hoja JUEGOS
"""
import io
import re
import sys
import unicodedata
from datetime import date, datetime, time

import openpyxl

from . import config, db

PALABRAS_COLUMNA = {  # campo → texto que aparece en el encabezado del Excel
    "nombre": "NOMBRE COMPLETO",
    "documento": "NUMERO DE DOCUMENTO",
    "cargo": "CARGO",
    "despacho": "DESPACHO",
    "ciudad": "CIUDAD",
    "correo": "CORREO",
    "celular": "CELULAR",
    "fecha_requerimiento": "FECHA DE REQUERIMIENTO",
    "notas": "NOTAS",
    "fecha_programacion": "FECHA PROGRAMACION",
    "hora": "HORA",
    "sede": "DIRECCION",
    "tipo_examen": "TIPO DE EXAMEN",
    "observaciones": "OBSERVACIONES",
    "novedad": "NOVEDAD",
}


def sin_tildes(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", str(txt))
    return "".join(c for c in txt if not unicodedata.combining(c)).upper()


def limpiar(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = re.sub(r"\s+", " ", v.replace("\xa0", " ")).strip()
        return v or None
    return v


# ---------------- Fechas y horas ----------------
_MES_NUM = {sin_tildes(m): i + 1 for i, m in enumerate(config.MESES)}


def _mes_de_palabra(palabra):
    """'SEPTIEMBRE', 'SEPT', 'SEP' → 9"""
    for nombre, num in _MES_NUM.items():
        if len(palabra) >= 3 and nombre.startswith(palabra[:3]) and (palabra in nombre or nombre in palabra or len(palabra) <= 4):
            return num
    return None


def a_fecha(v, anio_defecto=None, mes_defecto=None):
    """Devuelve (fecha 'AAAA-MM-DD' o None, hora 'HH:MM' o None, ok)."""
    v = limpiar(v)
    if v is None:
        return None, None, True
    if isinstance(v, datetime):
        hora = v.strftime("%H:%M") if v.time() != time(0, 0) else None
        return v.date().isoformat(), hora, True
    if isinstance(v, date):
        return v.isoformat(), None, True
    if isinstance(v, (int, float)):  # número serial de Excel
        try:
            return openpyxl.utils.datetime.from_excel(v).date().isoformat(), None, True
        except Exception:
            return None, None, False
    t = sin_tildes(v)
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-]?(\d{4})", t)  # 21/07/2026 y también 21/072026
    if m:
        d, mes, a = map(int, m.groups())
        try:
            return date(a, mes, d).isoformat(), None, True
        except ValueError:
            return None, None, False
    anio = anio_defecto or date.today().year
    m = re.search(r"(\d{1,2})\s*(?:DE\s+)?([A-Z]{3,})", t)  # "MARTES 13 DE OCTUBRE", "JUEVES 17 SEPT"
    mes = _mes_de_palabra(m.group(2)) if m else None
    if not mes:  # "VIERNES 21": sin mes → usar el mes de la columna NOTAS
        m = re.fullmatch(r"\D*?(\d{1,2})[\s\-A-Z]*", t)  # también "15 - JUEVES"
        mes = mes_defecto if m else None
    if m and mes:
        try:
            return date(anio, mes, int(m.group(1))).isoformat(), None, True
        except ValueError:
            pass
    return None, None, False


def a_hora(v):
    v = limpiar(v)
    if v is None:
        return None
    if isinstance(v, (time, datetime)):
        return v.strftime("%H:%M")
    t = sin_tildes(v).replace(".", "").replace(" ", "")
    m = re.search(r"(\d{1,2})(?::?(\d{2}))?(AM|PM)?", t)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "PM" and h < 12:
        h += 12
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


# ---------------- Estado por color ----------------
def estado_por_color(celda):
    f = celda.fill
    if not f or not f.fill_type:
        return None
    c = f.fgColor
    clave = ("theme", c.theme) if c.type == "theme" else ("rgb", str(c.rgb).upper())
    return config.COLORES_EXCEL.get(clave)


# ---------------- Normalizaciones ----------------
def normalizar_ciudad(v):
    v = limpiar(v)
    if not v:
        return None
    v = sin_tildes(v)
    return config.CORRECCIONES_CIUDAD.get(v, v)


def normalizar_tipo(v):
    v = limpiar(v)
    if not v:
        return None
    v = v.upper()
    return config.CORRECCIONES_TIPO.get(v, v)


def a_texto_numero(v):
    v = limpiar(v)
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"[^\d]", "", str(v)) or str(v)


# ---------------- Lectura de la hoja ----------------
def _buscar_encabezado(ws):
    for fila in ws.iter_rows(min_row=1, max_row=15):
        textos = [sin_tildes(c.value) if c.value else "" for c in fila]
        if any("NOMBRE COMPLETO" in t for t in textos):
            return fila[0].row, textos
    raise ValueError(f"No encontré la fila de encabezados en la hoja «{ws.title}».")


def hojas_disponibles(origen):
    wb = openpyxl.load_workbook(origen if not isinstance(origen, bytes) else io.BytesIO(origen), read_only=True)
    return wb.sheetnames


def leer_hoja(origen, hoja=None):
    """origen: ruta o bytes del .xlsx. Devuelve (registros, reporte)."""
    if isinstance(origen, bytes):
        origen = io.BytesIO(origen)
    wb = openpyxl.load_workbook(origen, data_only=True)
    ws = wb[hoja] if hoja else wb.worksheets[0]
    fila_enc, textos = _buscar_encabezado(ws)

    col = {}
    for campo, palabra in PALABRAS_COLUMNA.items():
        for i, t in enumerate(textos):
            if palabra in t and i not in col.values():
                col[campo] = i
                break
    col_examen = {}
    for i, t in enumerate(textos):
        for palabra, examen in config.COLUMNA_A_EXAMEN:
            if palabra in t and examen not in col_examen.values():
                col_examen[i] = examen
                break

    registros, problemas = [], []
    conteo = {"filas_leidas": 0, "estado_por_revisar": 0, "fechas_no_entendidas": 0, "ciudades_corregidas": 0}

    vacias_seguidas = 0
    for fila in ws.iter_rows(min_row=fila_enc + 1, max_row=min(ws.max_row, fila_enc + 50000)):
        val = lambda campo: fila[col[campo]].value if campo in col and col[campo] < len(fila) else None
        nombre = limpiar(val("nombre"))
        if not nombre:
            vacias_seguidas += 1
            if vacias_seguidas > 200:  # el Excel dice tener 1 millón de filas, pero están vacías
                break
            continue
        vacias_seguidas = 0
        n = fila[0].row
        conteo["filas_leidas"] += 1

        notas_txt = limpiar(val("notas"))
        mes = None
        if notas_txt and sin_tildes(notas_txt) in _MES_NUM:
            mes, notas_txt = sin_tildes(notas_txt), None
        f_req, _, ok1 = a_fecha(val("fecha_requerimiento"))
        anio = int(f_req[:4]) if f_req else None
        f_prog, hora_en_fecha, ok2 = a_fecha(val("fecha_programacion"), anio, _MES_NUM.get(mes))
        for ok, nombre_col, v in ((ok1, "FECHA DE REQUERIMIENTO", val("fecha_requerimiento")),
                                  (ok2, "FECHA PROGRAMACIÓN", val("fecha_programacion"))):
            if not ok:
                conteo["fechas_no_entendidas"] += 1
                problemas.append(f"Fila {n}: no entendí la {nombre_col} «{limpiar(v)}». Quedó vacía; queda guardada en notas.")

        extras = [notas_txt, limpiar(val("observaciones")), limpiar(val("novedad"))]
        if not ok2:
            extras.append(f"Fecha original: {limpiar(val('fecha_programacion'))}")
        if not ok1:
            extras.append(f"Fecha requerimiento original: {limpiar(val('fecha_requerimiento'))}")
        notas = " · ".join(str(x) for x in extras if x) or None

        ciudad_original = limpiar(val("ciudad"))
        ciudad = normalizar_ciudad(ciudad_original)
        if ciudad_original and ciudad != ciudad_original:
            conteo["ciudades_corregidas"] += 1

        estado = estado_por_color(fila[col["nombre"]])
        if estado is None:
            estado = "POR REVISAR"
            conteo["estado_por_revisar"] += 1
            problemas.append(f"Fila {n}: el color de la fila no corresponde a la leyenda → estado POR REVISAR.")

        examenes = [ex for i, ex in col_examen.items() if i < len(fila) and sin_tildes(fila[i].value or "").strip() == "SI"]
        hora_col = val("hora")
        hora = a_hora(hora_col) if not (isinstance(hora_col, str) and ":" not in hora_col and len(hora_col) > 15) else None

        registros.append({
            "nombre": nombre.upper(),
            "documento": a_texto_numero(val("documento")),
            "cargo": (limpiar(val("cargo")) or "").upper() or None,
            "despacho": limpiar(val("despacho")),
            "ciudad": ciudad,
            "correo": (limpiar(val("correo")) or "").lower() or None,
            "celular": a_texto_numero(val("celular")),
            "fecha_requerimiento": f_req,
            "mes_programado": mes,
            "fecha_programacion": f_prog,
            "hora": hora or hora_en_fecha,
            "sede": limpiar(val("sede")),
            "tipo_examen": normalizar_tipo(val("tipo_examen")),
            "examenes": " | ".join(examenes) or None,
            "estado": estado,
            "notas": notas,
            "_origen": f"{ws.title}!fila {n}",
        })

    return registros, {"conteo": conteo, "problemas": problemas, "hoja": ws.title}


def importar(con, origen, hoja=None, reemplazar=False):
    registros, reporte = leer_hoja(origen, hoja)
    if reemplazar:
        db.vaciar(con)
    for r in registros:
        db.insertar(con, r, origen=r.pop("_origen"))
    reporte["conteo"]["importados"] = len(registros)
    return reporte


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    hoja = sys.argv[sys.argv.index("--hoja") + 1] if "--hoja" in sys.argv else None
    con = db.conectar()
    rep = importar(con, sys.argv[1], hoja, reemplazar="--reemplazar" in sys.argv)
    print(f"Hoja: {rep['hoja']}")
    for k, v in rep["conteo"].items():
        print(f"  {k}: {v}")
    print(f"\n{len(rep['problemas'])} avisos (primeros 15):")
    for p in rep["problemas"][:15]:
        print("  -", p)
