"""Genera un Excel de DEMOSTRACIÓN con personas ficticias y el mismo formato del original
(encabezado en la fila 2, columnas de exámenes con "SI" y el estado indicado por el color de la fila).

Uso:  python -m src.demo            → crea data/datos_demo.xlsx
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Color, PatternFill

from . import config

NOMBRES = ["ANA", "CARLOS", "LUISA", "JORGE", "DIANA", "ANDRÉS", "PAOLA", "JULIÁN", "MARÍA", "FELIPE",
           "CAMILA", "DAVID", "SOFÍA", "MATEO", "LAURA", "SANTIAGO", "VALENTINA", "SEBASTIÁN", "ISABEL", "MIGUEL"]
APELLIDOS = ["GÓMEZ", "RODRÍGUEZ", "LÓPEZ", "MARTÍNEZ", "GARCÍA", "HERNÁNDEZ", "RAMÍREZ", "TORRES", "VARGAS",
             "CASTRO", "MORALES", "ROJAS", "ORTIZ", "MEJÍA", "SALAZAR", "CARDONA", "OSORIO", "RÍOS"]
CARGOS = ["JUEZ", "OFICIAL MAYOR", "CITADOR", "ESCRIBIENTE", "SECRETARIO", "ASISTENTE ADMINISTRATIVO",
          "PROFESIONAL UNIVERSITARIO", "AUXILIAR JUDICIAL"]
ESPECIALIDADES = ["CIVIL MUNICIPAL", "PENAL MUNICIPAL", "LABORAL DEL CIRCUITO", "PROMISCUO DE FAMILIA",
                  "ADMINISTRATIVO", "PENAL DEL CIRCUITO"]
CIUDADES = ["PALMIRA"] * 5 + ["BUGA"] * 4 + ["TULUA"] * 3 + ["CARTAGO", "CARTAGO", "BUENAVENTURA", "CALI"]
TIPOS = (["INGRESO - ENFASIS EN OSTEOMUSCULAR"] * 6 + ["PERIÓDICO - ENFASIS EN OSTEOMUSCULAR"] * 3
         + ["EGRESO - ENFASIS EN OSTEOMUSCULAR", "RECOMENDACIONES LABORALES PSICOSOCIAL", "INGRESO - CONDUCTORES"])
ESTADOS_PESOS = {"EMO REALIZADO": 50, "AGENDADO": 15, "NO ASISTIÓ": 10, "FALTA POR AGENDAR": 12,
                 "ENVIADO IPS - PENDIENTE FECHA": 6, "NO SE REALIZÓ": 7}
RELLENO = {
    "FALTA POR AGENDAR": PatternFill("solid", fgColor=Color(theme=7, tint=0.0)),
    "AGENDADO": PatternFill("solid", fgColor=Color(theme=4, tint=0.6)),
    "EMO REALIZADO": PatternFill("solid", fgColor=Color(theme=9, tint=0.4)),
    "ENVIADO IPS - PENDIENTE FECHA": PatternFill("solid", fgColor="FFF7D5D5"),
    "NO ASISTIÓ": PatternFill("solid", fgColor="FFFF0000"),
    "NO SE REALIZÓ": PatternFill("solid", fgColor=Color(theme=2, tint=-0.1)),
}
ENCABEZADOS = ["N°", "NOMBRE COMPLETO", "NÚMERO DE DOCUMENTO", "CARGO", "DESPACHO/OFICINA", "CIUDAD",
               "CORREO ELECTRÓNICO", "CELULAR", "FECHA DE REQUERIMIENTO", "NOTAS", "FECHA PROGRAMACIÓN EXAMEN",
               "HORA", "DIRECCIÓN", "TIPO DE EXAMEN"] + config.EXAMENES + ["OBSERVACIONES"]


def generar(n=200, ruta="data/datos_demo.xlsx", semilla=7):
    rnd = random.Random(semilla)
    wb = Workbook()
    ws = wb.active
    ws.title = "DEMO"
    ws.append(["DATOS DE DEMOSTRACIÓN — PERSONAS FICTICIAS"])
    ws.append(ENCABEZADOS)
    hoy = date.today()
    for i in range(1, n + 1):
        nombre = f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)} {rnd.choice(APELLIDOS)}"
        ciudad = rnd.choice(CIUDADES)
        tipo = rnd.choice(TIPOS)
        estado = rnd.choices(list(ESTADOS_PESOS), weights=ESTADOS_PESOS.values())[0]
        f_req = hoy - timedelta(days=rnd.randint(10, 180))
        if estado in ("FALTA POR AGENDAR", "ENVIADO IPS - PENDIENTE FECHA"):
            f_prog = None
        elif estado == "AGENDADO":
            f_prog = hoy + timedelta(days=rnd.randint(1, 30))
        else:
            f_prog = f_req + timedelta(days=rnd.randint(5, 40))
        hora = f"{rnd.choice([7, 8, 9, 10, 14, 15])}:{rnd.choice(['00', '30'])}" if f_prog else None
        usuario = nombre.split()[0].lower().translate(str.maketrans("áéíóú", "aeiou"))
        examenes = set(config.EXAMENES_POR_TIPO.get(tipo, []))
        fila = [i, nombre, str(rnd.randint(10_000_000, 1_199_999_999)), rnd.choice(CARGOS),
                f"JUZGADO {rnd.randint(1, 9):03d} {rnd.choice(ESPECIALIDADES)}", ciudad,
                f"{usuario}{rnd.randint(1, 99)}@ejemplo.com", f"3{rnd.randint(100000000, 299999999)}",
                f_req, config.MESES[(f_prog or f_req).month - 1] if f_prog else None, f_prog, hora,
                f"{ciudad}: SEDE IPS DEMO", tipo] + ["SI" if ex in examenes else None for ex in config.EXAMENES] + [None]
        ws.append(fila)
        for c in ws[ws.max_row]:
            c.fill = RELLENO[estado]
        for col in (9, 11):
            ws.cell(ws.max_row, col).number_format = "yyyy-mm-dd"
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    wb.save(ruta)
    return ruta


if __name__ == "__main__":
    print("Creado:", generar(int(sys.argv[1]) if len(sys.argv) > 1 else 200))
