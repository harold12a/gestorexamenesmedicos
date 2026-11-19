"""ETL — Paso C (Load): guarda en la base de datos los documentos transformados.
Solo carga los 'processed'. Se puede ejecutar varias veces sin duplicar nada (es idempotente).
Cada ejecución queda registrada en la tabla ejecuciones_etl.

Entrada: salida/transformados/*.json     Destino: tablas documentos y ejecuciones_etl
Uso desde la terminal:  python -m pipeline.cargar
"""
import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select

from .modelos import Documento, EjecucionETL, Sesion, crear_tablas
from .transformar import CARPETA_TRANSFORMADOS

# Campos que, si cambian, hacen que un documento ya cargado se actualice.
CAMPOS_COMPARABLES = ["category", "title", "author", "content", "document_date", "dates_found", "word_count", "issues"]


def _ahora():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def a_columnas(d: dict) -> dict:
    """Convierte el JSON transformado en los valores de las columnas de la tabla documentos."""
    columnas = {c: d.get(c) for c in Documento.__table__.columns.keys() if c in d}
    columnas["document_date"] = date.fromisoformat(d["document_date"]) if d.get("document_date") else None
    columnas["loaded_at"] = _ahora()
    return columnas


def cargar_documento(sesion, d: dict) -> tuple:
    """Decide qué hacer con UN documento y lo hace. Devuelve (acción, motivo).
    Acciones: insertado | actualizado | sin_cambios | omitido."""
    if d["processing_status"] != "processed":
        return "omitido", f"Estado '{d['processing_status']}': " + " ".join(d.get("issues", []))

    existente = sesion.get(Documento, d["document_id"])
    nuevos = a_columnas(d)

    if existente is None:
        # Duplicado ENTRE cargas: el mismo texto ya está en la base con otro id.
        otro = sesion.scalar(select(Documento.document_id).where(Documento.content_hash == d["content_hash"]))
        if otro:
            return "omitido", f"Mismo contenido que {otro}, cargado en una ejecución anterior."
        sesion.add(Documento(**nuevos))
        return "insertado", ""

    cambios = [c for c in CAMPOS_COMPARABLES if getattr(existente, c) != nuevos[c]]
    if not cambios:
        return "sin_cambios", ""
    for campo in cambios + ["loaded_at"]:
        setattr(existente, campo, nuevos[campo])
    return "actualizado", "Cambió: " + ", ".join(cambios)


def cargar_lote(carpeta: Path = CARPETA_TRANSFORMADOS) -> EjecucionETL:
    """Carga todos los documentos transformados. Un documento con error no detiene a los demás."""
    crear_tablas()
    with Sesion() as sesion:
        ejecucion = EjecucionETL(inicio=_ahora(), estado="en_curso")
        sesion.add(ejecucion)
        sesion.commit()  # queda registrado que la carga empezó, aunque luego falle

        conteo = {"insertado": 0, "actualizado": 0, "sin_cambios": 0, "omitido": 0, "error": 0}
        detalle = []
        for ruta in sorted(Path(carpeta).glob("DOC-*.json")):
            d = {"document_id": ruta.stem, "filename": ruta.name}
            try:
                d = json.loads(ruta.read_text(encoding="utf-8"))
                accion, motivo = cargar_documento(sesion, d)
                sesion.commit()       # una transacción por documento
            except Exception as e:
                sesion.rollback()     # deshace solo este documento
                accion, motivo = "error", str(e)
            conteo[accion] += 1
            detalle.append({"document_id": d.get("document_id"), "filename": d.get("filename"),
                            "accion": accion, "motivo": motivo})

        ejecucion.fin = _ahora()
        ejecucion.total = len(detalle)
        ejecucion.insertados = conteo["insertado"]
        ejecucion.actualizados = conteo["actualizado"]
        ejecucion.sin_cambios = conteo["sin_cambios"]
        ejecucion.omitidos = conteo["omitido"]
        ejecucion.errores = conteo["error"]
        ejecucion.detalle = detalle
        ejecucion.estado = "con_errores" if conteo["error"] else "ok"
        sesion.commit()
        sesion.refresh(ejecucion)
        sesion.expunge(ejecucion)  # para poder leerla después de cerrar la sesión
        return ejecucion


def resumen_base() -> dict:
    """Cuántos documentos hay en la base por categoría."""
    with Sesion() as sesion:
        filas = sesion.execute(select(Documento.category, func.count()).group_by(Documento.category)).all()
        return dict(filas)


if __name__ == "__main__":
    e = cargar_lote()
    for item in e.detalle:
        print(f"{item['accion']:<12} {item['document_id']}  {item['filename']:<32} {item['motivo']}")
    print(f"\nEjecución #{e.id} ({e.estado}): {e.insertados} insertados, {e.actualizados} actualizados, "
          f"{e.sin_cambios} sin cambios, {e.omitidos} omitidos, {e.errores} errores")
    print("Documentos en la base por categoría:", resumen_base())
