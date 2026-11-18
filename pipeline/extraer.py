"""ETL — Paso A (Extract): lee un documento y devuelve sus datos en una estructura organizada.
No depende de Streamlit ni de la base de datos. El texto se guarda TAL CUAL (crudo); limpiarlo es el Paso B.

Uso desde la terminal:
    python -m pipeline.extraer documentos_prueba/servicios_ips_demo.pdf   (un archivo)
    python -m pipeline.extraer documentos_prueba                           (toda la carpeta)
Resultado: muestra un resumen y guarda un JSON por documento en salida/extraidos/.
"""
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pymupdf  # PyMuPDF

CARPETA_SALIDA = Path(__file__).resolve().parent.parent / "salida" / "extraidos"


@dataclass
class DocumentoExtraido:
    """Forma que tiene TODO documento después de la extracción (sin importar si es PDF, CSV...)."""
    document_id: str                 # DOC- + huella del contenido: mismo archivo → mismo id
    filename: str
    document_type: str               # extensión: pdf, csv, xlsx...
    size_bytes: int
    ingested_at: str                 # cuándo entró al proceso (fecha y hora local con zona horaria)
    content: str = ""                # texto crudo, sin limpiar
    pages: int = 0
    metadata: dict = field(default_factory=dict)   # título, autor, fechas... que traiga el archivo
    extraction_status: str = "extracted"           # extracted | empty | error
    errors: list = field(default_factory=list)


def calcular_id(ruta: Path) -> str:
    """Id a partir del contenido (SHA-256). Si el mismo archivo entra dos veces, tendrá el mismo id."""
    huella = hashlib.sha256(ruta.read_bytes()).hexdigest()
    return f"DOC-{huella[:12].upper()}"


def _extraer_pdf(ruta: Path):
    """Extractor de PDF: devuelve (texto, número de páginas, metadatos no vacíos)."""
    with pymupdf.open(ruta) as doc:
        if doc.needs_pass:
            raise ValueError("el PDF está protegido con contraseña")
        texto = "\n".join(pagina.get_text() for pagina in doc)
        metadatos = {k: v for k, v in (doc.metadata or {}).items() if v}
        return texto, doc.page_count, metadatos


# Extensión → función que sabe leerla. Para soportar CSV o Excel, se agrega una línea aquí.
EXTRACTORES = {
    ".pdf": _extraer_pdf,
}


def extraer(ruta) -> DocumentoExtraido:
    """Extrae un documento. Nunca se detiene por un archivo dañado: lo marca con status 'error'."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")

    doc = DocumentoExtraido(
        document_id=calcular_id(ruta),
        filename=ruta.name,
        document_type=ruta.suffix.lower().lstrip("."),
        size_bytes=ruta.stat().st_size,
        ingested_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )

    extractor = EXTRACTORES.get(ruta.suffix.lower())
    if extractor is None:
        doc.extraction_status = "error"
        doc.errors.append(f"Tipo de archivo no soportado: .{doc.document_type}")
        return doc

    try:
        doc.content, doc.pages, doc.metadata = extractor(ruta)
    except Exception as e:
        doc.extraction_status = "error"
        doc.errors.append(f"No se pudo leer el archivo: {e}")
        return doc

    if not doc.content.strip():
        doc.extraction_status = "empty"
        doc.errors.append("No tiene texto extraíble (¿es un documento escaneado?). Necesitaría OCR.")
    return doc


def guardar_json(doc: DocumentoExtraido, carpeta: Path = CARPETA_SALIDA) -> Path:
    """Guarda el resultado como <document_id>.json (zona intermedia o 'staging')."""
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{doc.document_id}.json"
    ruta.write_text(json.dumps(asdict(doc), ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    entrada = Path(sys.argv[1])
    archivos = sorted(p for p in entrada.iterdir() if p.is_file()) if entrada.is_dir() else [entrada]

    for archivo in archivos:
        doc = extraer(archivo)
        guardar_json(doc)
        print(f"{doc.extraction_status:<10} {doc.document_id}  {doc.filename:<34} {doc.pages} pág.  "
              f"{len(doc.content):>5} caracteres  {'; '.join(doc.errors)}")
    print(f"\nJSON guardados en: {CARPETA_SALIDA}")
