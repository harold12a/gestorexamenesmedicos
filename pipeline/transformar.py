"""ETL — Paso B (Transform): toma lo extraído, lo limpia, lo normaliza, lo clasifica y detecta duplicados.
Deja cada documento en el ESQUEMA COMÚN (DocumentoProcesado), listo para cargarse en la base (Paso C).

Entrada: salida/extraidos/*.json     Salida: salida/transformados/*.json + _reporte.csv
Uso desde la terminal:  python -m pipeline.transformar
"""
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src import config
from src.importar_excel import sin_tildes

from .extraer import CARPETA_SALIDA as CARPETA_EXTRAIDOS

CARPETA_TRANSFORMADOS = CARPETA_EXTRAIDOS.parent / "transformados"
LONGITUD_MINIMA = 50  # menos caracteres que esto → el documento no tiene contenido útil


@dataclass
class DocumentoProcesado:
    """Esquema común: forma de TODO documento después de transformarlo, sin importar su origen."""
    document_id: str
    filename: str
    document_type: str
    category: str                    # servicios | procedimientos | certificados | otros
    title: str | None
    author: str | None
    content: str                     # texto limpio
    content_hash: str                # huella del TEXTO: detecta el mismo contenido en archivos distintos
    document_date: str | None        # primera fecha encontrada en el texto, en AAAA-MM-DD
    dates_found: list
    word_count: int
    ingested_at: str
    processed_at: str
    processing_status: str           # processed | duplicate | rejected
    duplicate_of: str | None = None  # si es duplicado, id del documento original
    issues: list = field(default_factory=list)


# ---------------- Reglas de transformación (se ajustan aquí, sin tocar el resto) ----------------

# Nombre estándar del campo → nombres con los que puede venir en los metadatos de distintos archivos.
SINONIMOS_METADATOS = {
    "title": ["title", "titulo", "título"],
    "author": ["author", "autor", "creator"],
    "subject": ["subject", "asunto", "tema"],
}

# Categoría → palabras clave (en mayúsculas y sin tildes).
CATEGORIAS = {
    "certificados": ["CERTIFICADO", "APTITUD", "CONCEPTO"],
    "procedimientos": ["PROCEDIMIENTO", "PROTOCOLO", "PASO 1"],
    "servicios": ["PORTAFOLIO", "SERVICIOS", "SEDES", "HORARIO"],
}


# ---------------- Funciones de transformación ----------------

def unificar_metadatos(meta: dict) -> dict:
    """Pasa los metadatos a nombres estándar: {'Titulo': 'X'} → {'title': 'X'}."""
    minus = {str(k).lower(): v for k, v in (meta or {}).items()}
    return {estandar: next((minus[s] for s in sinonimos if minus.get(s)), None)
            for estandar, sinonimos in SINONIMOS_METADATOS.items()}


def limpiar_texto(texto: str) -> str:
    """Quita espacios repetidos y líneas vacías sobrantes, pero conserva los saltos de línea."""
    texto = (texto or "").replace("\xa0", " ").replace("\r", "")
    lineas = [re.sub(r"[ \t]+", " ", linea).strip() for linea in texto.split("\n")]
    resultado = []
    for linea in lineas:
        if linea or (resultado and resultado[-1]):  # deja como máximo una línea vacía seguida
            resultado.append(linea)
    return "\n".join(resultado).strip()


_MES_NUM = {sin_tildes(m): i + 1 for i, m in enumerate(config.MESES)}
_PATRONES_FECHA = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), ("a", "m", "d")),                 # 2026-09-01
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), ("d", "m", "a")),                 # 15/10/2026
    (re.compile(r"\b(\d{1,2}) DE ([A-Z]+) DE (\d{4})\b"), ("d", "mes", "a")),           # 03 DE NOVIEMBRE DE 2026
]


def encontrar_fechas(texto: str) -> list:
    """Encuentra fechas escritas de distintas formas y las devuelve en AAAA-MM-DD, en orden de aparición."""
    t = sin_tildes(texto)
    encontradas = []
    for patron, orden in _PATRONES_FECHA:
        for m in patron.finditer(t):
            partes = dict(zip(orden, m.groups()))
            mes = _MES_NUM.get(partes["mes"]) if "mes" in partes else int(partes["m"])
            try:
                encontradas.append((m.start(), date(int(partes["a"]), mes, int(partes["d"])).isoformat()))
            except (TypeError, ValueError):
                pass  # no es una fecha válida (ej. mes 13): se ignora
    fechas = []
    for _, f in sorted(encontradas):
        if f not in fechas:
            fechas.append(f)
    return fechas


def clasificar(subject, title, filename, content) -> str:
    """Asigna una categoría: primero por el 'asunto' del archivo; si no, por palabras clave."""
    if subject and subject.lower() in CATEGORIAS:
        return subject.lower()
    texto = sin_tildes(f"{title or ''} {filename} {content[:1000]}").replace("_", " ")
    puntajes = {cat: sum(texto.count(p) for p in palabras) for cat, palabras in CATEGORIAS.items()}
    mejor = max(puntajes, key=puntajes.get)
    return mejor if puntajes[mejor] > 0 else "otros"


def huella_contenido(texto: str) -> str:
    """Huella del texto ignorando mayúsculas, tildes y espacios: mismo contenido → misma huella."""
    normalizado = re.sub(r"\s+", " ", sin_tildes(texto)).strip()
    return hashlib.sha256(normalizado.encode("utf-8")).hexdigest()[:16]


def transformar(extraido: dict) -> DocumentoProcesado:
    """Transforma UN documento extraído al esquema común y decide si es válido (processed) o no (rejected)."""
    meta = unificar_metadatos(extraido.get("metadata"))
    contenido = limpiar_texto(extraido.get("content", ""))
    fechas = encontrar_fechas(contenido)

    doc = DocumentoProcesado(
        document_id=extraido["document_id"],
        filename=extraido["filename"],
        document_type=extraido["document_type"],
        category=clasificar(meta["subject"], meta["title"], extraido["filename"], contenido),
        title=meta["title"],
        author=meta["author"],
        content=contenido,
        content_hash=huella_contenido(contenido),
        document_date=fechas[0] if fechas else None,
        dates_found=fechas,
        word_count=len(contenido.split()),
        ingested_at=extraido["ingested_at"],
        processed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        processing_status="processed",
    )

    if extraido.get("extraction_status") != "extracted":
        doc.processing_status = "rejected"
        doc.issues.append(f"Extracción '{extraido.get('extraction_status')}': " + "; ".join(extraido.get("errors", [])))
    elif len(contenido) < LONGITUD_MINIMA:
        doc.processing_status = "rejected"
        doc.issues.append(f"Texto demasiado corto ({len(contenido)} caracteres).")
    elif not fechas:
        doc.issues.append("No se encontró ninguna fecha en el texto.")  # aviso: no impide procesarlo
    return doc


def marcar_duplicados(docs: list) -> None:
    """Entre los documentos válidos, marca como 'duplicate' los que repiten el texto de otro anterior."""
    tabla = pd.DataFrame([
        {"pos": i, "id": d.document_id, "huella": d.content_hash, "ingreso": d.ingested_at, "archivo": d.filename}
        for i, d in enumerate(docs) if d.processing_status == "processed"
    ])
    if tabla.empty:
        return
    tabla = tabla.sort_values(["ingreso", "archivo"])                    # el que entró primero es el original
    originales = tabla.drop_duplicates("huella").set_index("huella")["id"]
    for fila in tabla[tabla.duplicated("huella", keep="first")].itertuples():
        d = docs[fila.pos]
        d.processing_status = "duplicate"
        d.duplicate_of = originales[fila.huella]
        d.issues.append(f"Mismo contenido que {d.duplicate_of}.")


def transformar_lote(carpeta_entrada: Path = CARPETA_EXTRAIDOS) -> list:
    """Transforma todos los JSON extraídos de una carpeta y marca los duplicados entre ellos."""
    extraidos = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(carpeta_entrada).glob("*.json"))]
    docs = [transformar(e) for e in extraidos]
    marcar_duplicados(docs)
    return docs


def guardar(docs: list, carpeta: Path = CARPETA_TRANSFORMADOS) -> Path:
    """Guarda un JSON por documento y un reporte del lote (_reporte.csv) para revisar en Excel."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for d in docs:
        (carpeta / f"{d.document_id}.json").write_text(
            json.dumps(asdict(d), ensure_ascii=False, indent=2), encoding="utf-8")
    reporte = pd.DataFrame([asdict(d) for d in docs])[
        ["document_id", "filename", "category", "processing_status", "document_date", "word_count", "duplicate_of", "issues"]]
    reporte["issues"] = reporte["issues"].map(" | ".join)
    ruta = carpeta / "_reporte.csv"
    reporte.to_csv(ruta, index=False, encoding="utf-8-sig")  # utf-8-sig: Excel muestra bien las tildes
    return ruta


if __name__ == "__main__":
    docs = transformar_lote()
    ruta = guardar(docs)
    for d in docs:
        print(f"{d.processing_status:<10} {d.document_id}  {d.filename:<32} {d.category:<15} "
              f"{d.document_date or '—':<11} {'; '.join(d.issues)}")
    resumen = pd.Series([d.processing_status for d in docs]).value_counts().to_dict()
    print(f"\nResumen: {resumen}\nReporte: {ruta}")
