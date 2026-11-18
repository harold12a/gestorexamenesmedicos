"""Crea PDFs de prueba (contenido FICTICIO) en documentos_prueba/ para probar el ETL.
Uso:  python -m pipeline.crear_documentos_prueba"""
from pathlib import Path

import pymupdf

CARPETA = Path(__file__).resolve().parent.parent / "documentos_prueba"

DOCUMENTOS = {
    "servicios_ips_demo.pdf": {
        "metadata": {"title": "Portafolio de servicios - IPS Demo", "author": "Coordinación SST",
                     "subject": "servicios", "keywords": "servicios, exámenes ocupacionales"},
        "paginas": [
            "PORTAFOLIO DE SERVICIOS - IPS DEMO\n\nFecha de actualización: 15/10/2026\n\n"
            "1. Examen médico ocupacional de ingreso\n   Incluye: optometría, audiometría, prueba psicotécnica.\n"
            "2. Examen médico ocupacional periódico\n   Incluye: optometría, audiometría.\n"
            "3. Examen de egreso\n   Valoración médica general.",
            "SEDES Y HORARIOS\n\nPalmira:   lunes a viernes, 7:00 a. m. - 4:00 p. m.\n"
            "Buga:      lunes a viernes, 7:00 a. m. - 12:00 m.\nTuluá:     martes y jueves, 7:00 a. m. - 3:00 p. m.\n\n"
            "Contacto: citas@ipsdemo.ejemplo.com",
        ],
    },
    "procedimiento_agendamiento.pdf": {
        "metadata": {"title": "Procedimiento de agendamiento de EMO", "author": "Coordinación SST",
                     "subject": "procedimientos"},
        "paginas": [
            "PROCEDIMIENTO DE AGENDAMIENTO DE EXÁMENES MÉDICOS OCUPACIONALES\n\nVersión 2 - Vigente desde: 2026-09-01\n\n"
            "Paso 1. Recibir la solicitud con nombre, cédula, cargo y tipo de examen.\n"
            "Paso 2. Enviar la solicitud a la IPS y esperar la fecha asignada.\n"
            "Paso 3. Informar la cita al servidor por correo y celular.\n"
            "Paso 4. Si no asiste, reprogramar máximo una vez.\n"
            "Paso 5. Registrar el resultado (EMO REALIZADO) cuando llegue el certificado.",
        ],
    },
    "certificado_aptitud_demo.pdf": {
        "metadata": {"title": "Certificado de aptitud laboral", "author": "IPS Demo", "subject": "certificados"},
        "paginas": [
            "CERTIFICADO DE APTITUD LABORAL (DOCUMENTO FICTICIO)\n\nFecha del examen:   03 de noviembre de 2026\n"
            "Nombre:   ANA GÓMEZ RÍOS\nDocumento:   1000000001\nTipo de examen:   INGRESO - ÉNFASIS OSTEOMUSCULAR\n\n"
            "Concepto:   APTO SIN RESTRICCIONES\n\nMédico: Dr. Ejemplo Demo - Licencia 00000",
        ],
    },
}


def crear():
    """Genera los PDFs de prueba, más uno 'escaneado' (sin texto) y un archivo no soportado."""
    CARPETA.mkdir(exist_ok=True)
    for nombre, datos in DOCUMENTOS.items():
        doc = pymupdf.open()
        for texto in datos["paginas"]:
            doc.new_page().insert_text((50, 72), texto, fontsize=11)
        doc.set_metadata(datos["metadata"])
        doc.save(CARPETA / nombre)
    # PDF sin texto extraíble: simula un documento escaneado (solo un dibujo).
    doc = pymupdf.open()
    doc.new_page().draw_rect(pymupdf.Rect(50, 50, 300, 200), color=(0, 0, 0), fill=(0.8, 0.8, 0.8))
    doc.save(CARPETA / "escaneado_sin_texto.pdf")
    # Archivo de un tipo que todavía no soportamos.
    (CARPETA / "notas.docx").write_bytes(b"no es un pdf")
    return sorted(p.name for p in CARPETA.iterdir())


if __name__ == "__main__":
    print("Creados en documentos_prueba/:", crear())
