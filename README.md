# 🩺 Gestor de Exámenes Médicos Ocupacionales (EMO)

Aplicación web para **registrar, programar, buscar y hacer seguimiento** a las asignaciones de exámenes médicos ocupacionales (ingreso, periódicos, egreso, recomendaciones laborales). Reemplaza el control en Excel, donde el estado de cada persona se marcaba **con el color de la fila** y la búsqueda era manual.

## ¿Qué problema resuelve?

| Antes (Excel) | Ahora (Gestor EMO) |
|---|---|
| El estado se sabía por el **color** de la fila | El estado es un campo: se filtra y se cuenta |
| Fechas escritas de muchas formas ("JUEVES 17 SEPT", "21/072026") | Fechas normalizadas, con aviso cuando no se entienden |
| Buscar a alguien = Ctrl+F y revisar a ojo | Búsqueda por nombre, cédula, correo o despacho, sin importar tildes |
| No se sabe quién cambió qué | **Historial** de cada cambio (quién, cuándo, valor anterior y nuevo) |
| Duplicados y errores pasan desapercibidos | Pestaña de **calidad de datos** (duplicados, citas vencidas, faltantes) |
| Hay que recordar qué exámenes lleva cada tipo | Se **autocompletan** según el tipo de examen |
| Reportes hechos a mano | **Tablero** y preguntas en lenguaje natural con IA |

## Funciones

- **🔎 Buscar y editar:** filtros por estado, ciudad, tipo de examen, examen incluido y rango de fechas. Ficha editable con historial.
- **📊 Tablero:** totales, citas de los próximos días, gráficos por estado, ciudad y mes.
- **➕ Nueva asignación:** formulario con autocompletado de exámenes y aviso si la cédula ya tiene registros.
- **🤖 Preguntar:** "¿Quiénes no asistieron en Palmira este mes?" → la IA (Gemini) genera la consulta y se ejecuta en local.
- **🧹 Calidad de datos:** posibles duplicados, estados por revisar, agendados con cita vencida, sin datos de contacto.
- **📥 Importar / ⬇️ Exportar:** importa el Excel actual (leyendo el estado desde el color de la fila) y exporta a Excel en cualquier momento.

## 🔒 Privacidad y datos sensibles

Esta aplicación maneja **datos personales y datos relativos a la salud**, que en Colombia son **datos sensibles** (Ley 1581 de 2012). Por diseño:

- Los datos se guardan en un archivo local (`data/emo.db`), **no en la nube**.
- La función de IA **solo envía a Google la pregunta y la estructura de la tabla**, nunca registros de personas. La consulta se ejecuta en local y en **modo solo lectura**, y se bloquea cualquier instrucción que no sea de lectura.
- El `.gitignore` impide subir a GitHub los Excel, la base de datos y las claves.
- Acceso con contraseña (`APP_PASSWORD`).
- Para mostrar el proyecto se incluyen **datos de demostración ficticios** (`python -m src.demo`).

> Antes de usarlo con datos reales en una organización, valida con el responsable de protección de datos dónde se aloja, quién accede y la política de tratamiento.

## 🚀 Instalación

```bash
git clone https://github.com/TU_USUARIO/gestor-emo.git
cd gestor-emo
python -m venv .venv
.venv\Scripts\activate          # Windows  (en Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

Copia `.env.example` como `.env` y llena tus valores. Luego:

```bash
streamlit run app.py
```

Desde el panel izquierdo: **Importar desde Excel**, o **Cargar datos de demostración**.

Importar también desde la terminal:
```bash
python -m src.importar_excel "ruta/al/archivo.xlsx"
python -m src.importar_excel "ruta/al/archivo.xlsx" --hoja JUEGOS
```

## 🗂️ Estructura

```
gestor-emo/
├── app.py                 # Interfaz (Streamlit)
├── src/
│   ├── config.py          # Estados, exámenes, matriz tipo→exámenes, colores del Excel
│   ├── db.py              # Base de datos SQLite + historial de cambios
│   ├── importar_excel.py  # Limpieza e importación del Excel (fechas, ciudades, estado por color)
│   ├── consulta_ia.py     # Preguntas en lenguaje natural → SQL (Gemini), seguro y local
│   └── demo.py            # Generador de datos ficticios
├── data/                  # Base de datos local (ignorada por git)
├── requirements.txt
└── .env.example
```

## 🛠️ Tecnologías

Python · Streamlit · SQLite · pandas · openpyxl · Google Gemini (`gemini-3.5-flash`)

## 🧭 Próximos pasos

- Usuarios con roles (consulta / edición / administrador).
- Recordatorio automático por correo o WhatsApp antes de la cita.
- Carga del certificado de aptitud (PDF) en cada asignación.
- Base de datos en un servidor (PostgreSQL) para trabajo en equipo.

## 👤 Autor

Harold Alzate · [GitHub](https://github.com/harold12a)
