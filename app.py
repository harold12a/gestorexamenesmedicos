"""Gestor de Exámenes Médicos Ocupacionales (EMO)
Ejecutar:  streamlit run app.py
"""
import io
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src import config, consulta_ia, db, demo, importar_excel

load_dotenv()
st.set_page_config(page_title="Gestor EMO", page_icon="🩺", layout="wide")


# ---------------- Acceso ----------------
def secreto(nombre):
    valor = os.environ.get(nombre)
    if valor:
        return valor
    try:
        return st.secrets.get(nombre)
    except Exception:
        return None


def pedir_clave():
    clave = secreto("APP_PASSWORD")
    if not clave:
        st.sidebar.warning("Sin contraseña configurada (APP_PASSWORD). Úsalo solo en tu computador.")
        return True
    if st.session_state.get("acceso"):
        return True
    st.title("🩺 Gestor de Exámenes Médicos Ocupacionales")
    with st.form("login"):
        intento = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            if intento == clave:
                st.session_state.acceso = True
                st.rerun()
            st.error("Contraseña incorrecta.")
    return False


if not pedir_clave():
    st.stop()


@st.cache_resource
def conexion():
    return db.conectar()


con = conexion()

# MODO DEMO (para publicar en internet): solo datos ficticios y sin importar Excel
MODO_DEMO = str(secreto("MODO_DEMO") or "").strip().lower() in ("1", "true", "si", "sí")
if MODO_DEMO and con.execute("SELECT COUNT(*) FROM asignaciones").fetchone()[0] == 0:
    importar_excel.importar(con, demo.generar(300, "data/datos_demo.xlsx"))


# ---------------- Utilidades ----------------
NOMBRES_COLUMNAS = {
    "id": "ID", "nombre": "Nombre", "documento": "Documento", "cargo": "Cargo", "despacho": "Despacho/Oficina",
    "ciudad": "Ciudad", "correo": "Correo", "celular": "Celular", "fecha_requerimiento": "Fecha requerimiento",
    "mes_programado": "Mes", "fecha_programacion": "Fecha cita", "hora": "Hora", "sede": "Sede IPS",
    "tipo_examen": "Tipo de examen", "examenes": "Exámenes", "estado": "Estado", "notas": "Notas",
}


def a_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.rename(columns=NOMBRES_COLUMNAS).to_excel(buf, index=False, sheet_name="Asignaciones")
    return buf.getvalue()


def fecha_o_none(txt):
    try:
        return date.fromisoformat(txt) if txt else None
    except ValueError:
        return None


def chip(estado):
    color = config.COLOR_ESTADO.get(estado, "#6b7280")
    return (f"<span style='background:{color};color:white;padding:2px 10px;border-radius:999px;"
            f"font-size:0.85rem;font-weight:600'>{estado}</span>")


def datos() -> pd.DataFrame:
    return db.todas(con)


USUARIO = st.sidebar.text_input("👤 Tu nombre (para el historial)", key="nombre_usuario").strip() or "sin nombre"


# ---------------- Barra lateral: importar / exportar ----------------
with st.sidebar:
    st.header("📥 Datos")
    total = con.execute("SELECT COUNT(*) FROM asignaciones").fetchone()[0]
    st.caption(f"Registros en la base: **{total}**")

    if MODO_DEMO:
        st.info("🧪 **Versión de demostración.** Todos los datos son ficticios. "
                "La importación de Excel está desactivada para proteger datos reales.")
    if not MODO_DEMO:
        with st.expander("Importar desde Excel", expanded=total == 0):
            archivo = st.file_uploader("Archivo .xlsx", type="xlsx")
            if archivo:
                contenido = archivo.getvalue()
                hojas = importar_excel.hojas_disponibles(contenido)
                hoja = st.selectbox("Hoja", hojas)
                modo = st.radio("Modo", ["Agregar a lo existente", "Reemplazar todo"], horizontal=False)
                if st.button("Importar", type="primary", width="stretch"):
                    with st.spinner("Leyendo el Excel…"):
                        try:
                            rep = importar_excel.importar(con, contenido, hoja, reemplazar=modo == "Reemplazar todo")
                            st.session_state.reporte = rep
                        except Exception as e:
                            st.error(f"No pude importar: {e}")
                    st.rerun()
            if total == 0 and st.button("Cargar datos de demostración (ficticios)", width="stretch"):
                ruta = demo.generar(200)
                st.session_state.reporte = importar_excel.importar(con, ruta)
                st.rerun()

    if "reporte" in st.session_state:
        rep = st.session_state.reporte
        c = rep["conteo"]
        st.success(f"Importados {c['importados']} registros de «{rep['hoja']}».")
        if rep["problemas"]:
            with st.expander(f"⚠️ {len(rep['problemas'])} avisos de la importación"):
                st.caption("Estos registros quedaron guardados; revísalos en la pestaña Calidad de datos.")
                for p in rep["problemas"]:
                    st.write("•", p)

    if total:
        st.download_button("⬇️ Exportar todo a Excel", a_excel(datos()), "asignaciones_emo.xlsx",
                           width="stretch")


# ---------------- Pantalla principal ----------------
st.title("🩺 Gestor de Exámenes Médicos Ocupacionales")
if total == 0:
    st.info("La base está vacía. Importa tu Excel desde el panel izquierdo, o carga los datos de demostración.")
    st.stop()

tab_buscar, tab_tablero, tab_nueva, tab_ia, tab_calidad = st.tabs(
    ["🔎 Buscar y editar", "📊 Tablero", "➕ Nueva asignación", "🤖 Preguntar", "🧹 Calidad de datos"]
)
df = datos()


# ======== BUSCAR Y EDITAR ========
def ficha(registro: dict, clave: str):
    st.markdown(f"### {registro['nombre']} &nbsp; {chip(registro['estado'])}", unsafe_allow_html=True)
    st.caption(f"CC {registro['documento'] or '—'} · {registro['cargo'] or '—'} · {registro['despacho'] or '—'} · "
               f"{registro['ciudad'] or '—'} · {registro['correo'] or '—'} · {registro['celular'] or '—'}")
    with st.form(f"editar_{clave}_{registro['id']}"):
        c1, c2, c3 = st.columns(3)
        estado = c1.selectbox("Estado", config.ESTADOS, index=config.ESTADOS.index(registro["estado"])
                              if registro["estado"] in config.ESTADOS else len(config.ESTADOS) - 1)
        f_cita = c2.date_input("Fecha de la cita", value=fecha_o_none(registro["fecha_programacion"]), format="DD/MM/YYYY")
        hora = c3.text_input("Hora (HH:MM)", value=registro["hora"] or "")
        tipos = config.TIPOS_EXAMEN + ([registro["tipo_examen"]] if registro["tipo_examen"] and registro["tipo_examen"] not in config.TIPOS_EXAMEN else [])
        tipo = c1.selectbox("Tipo de examen", tipos, index=tipos.index(registro["tipo_examen"]) if registro["tipo_examen"] in tipos else 0)
        sedes = sorted(df["sede"].dropna().unique())
        sede = c2.selectbox("Sede IPS", [""] + sedes, index=([""] + sedes).index(registro["sede"]) if registro["sede"] in sedes else 0)
        mes = c3.selectbox("Mes programado", [""] + config.MESES,
                           index=([""] + config.MESES).index(registro["mes_programado"]) if registro["mes_programado"] in config.MESES else 0)
        actuales = [e for e in (registro["examenes"] or "").split(" | ") if e]
        examenes = st.multiselect("Exámenes a realizar", config.EXAMENES, placeholder="Elige…", default=[e for e in actuales if e in config.EXAMENES])
        notas = st.text_area("Notas", value=registro["notas"] or "")
        if st.form_submit_button("💾 Guardar cambios", type="primary"):
            n = db.actualizar(con, registro["id"], {
                "estado": estado, "fecha_programacion": f_cita.isoformat() if f_cita else None,
                "hora": hora or None, "tipo_examen": tipo, "sede": sede or None, "mes_programado": mes or None,
                "examenes": " | ".join(examenes) or None, "notas": notas or None,
            }, usuario=USUARIO)
            st.toast(f"Guardado ({n} cambios)." if n else "No había cambios.")
            st.rerun()
    h = db.historial(con, registro["id"])
    with st.expander(f"🕓 Historial de cambios ({len(h)})"):
        if len(h):
            st.dataframe(h, hide_index=True, width="stretch")
        else:
            st.caption("Sin cambios registrados.")
    st.caption(f"Origen del registro: {registro.get('origen') or '—'}")


with tab_buscar:
    texto = st.text_input("Buscar por nombre, cédula, correo o despacho",
                          placeholder="Ej: 1113 o GOMEZ o juzgado 003")
    f1, f2, f3, f4 = st.columns(4)
    estados_sel = f1.multiselect("Estado", config.ESTADOS, placeholder="Todos")
    ciudades_sel = f2.multiselect("Ciudad", sorted(df["ciudad"].dropna().unique()), placeholder="Todos")
    tipos_sel = f3.multiselect("Tipo de examen", sorted(df["tipo_examen"].dropna().unique()), placeholder="Todos")
    examen_sel = f4.multiselect("Incluye el examen", config.EXAMENES, placeholder="Todos")
    g1, g2 = st.columns([1, 3])
    usar_fechas = g1.checkbox("Filtrar por fecha de cita")
    rango = g2.date_input("Rango", value=(date.today(), date.today() + timedelta(days=30)),
                          format="DD/MM/YYYY", disabled=not usar_fechas)

    vista = df.copy()
    if texto:
        t = importar_excel.sin_tildes(texto.strip())  # sin tildes ni mayúsculas: "gomez" encuentra "GÓMEZ"
        campos = vista[["nombre", "documento", "correo", "despacho"]].fillna("").astype(str).map(importar_excel.sin_tildes)
        vista = vista[campos.apply(lambda col: col.str.contains(t, regex=False)).any(axis=1)]
    if estados_sel:
        vista = vista[vista.estado.isin(estados_sel)]
    if ciudades_sel:
        vista = vista[vista.ciudad.isin(ciudades_sel)]
    if tipos_sel:
        vista = vista[vista.tipo_examen.isin(tipos_sel)]
    for ex in examen_sel:
        vista = vista[vista.examenes.fillna("").str.contains(ex, regex=False)]
    if usar_fechas and isinstance(rango, tuple) and len(rango) == 2:
        vista = vista[vista.fecha_programacion.between(rango[0].isoformat(), rango[1].isoformat())]

    columnas = ["id", "nombre", "documento", "ciudad", "tipo_examen", "estado", "fecha_programacion", "hora", "cargo"]
    st.caption(f"**{len(vista)}** resultados · haz clic en una fila para ver y editar la ficha")
    evento = st.dataframe(
        vista[columnas].rename(columns=NOMBRES_COLUMNAS), hide_index=True, width="stretch",
        on_select="rerun", selection_mode="single-row", key="tabla_busqueda", height=380,
    )
    st.download_button("⬇️ Descargar estos resultados", a_excel(vista), "busqueda_emo.xlsx")
    if evento.selection.rows:
        st.divider()
        ficha(vista.iloc[evento.selection.rows[0]].to_dict(), "buscar")


# ======== TABLERO ========
with tab_tablero:
    hoy = date.today().isoformat()
    en7 = (date.today() + timedelta(days=7)).isoformat()
    m = st.columns(5)
    m[0].metric("Total asignaciones", len(df))
    m[1].metric("EMO realizados", int((df.estado == "EMO REALIZADO").sum()))
    m[2].metric("Citas próximos 7 días", int(df.fecha_programacion.between(hoy, en7).sum()))
    m[3].metric("Pendientes por agendar", int(df.estado.isin(["FALTA POR AGENDAR", "ENVIADO IPS - PENDIENTE FECHA"]).sum()))
    m[4].metric("No asistieron", int((df.estado == "NO ASISTIÓ").sum()))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Por estado")
        st.bar_chart(df.estado.value_counts(), horizontal=True, color="#1d4ed8")
    with c2:
        st.subheader("Por ciudad")
        st.bar_chart(df.ciudad.value_counts().head(10), horizontal=True, color="#15803d")

    st.subheader("📅 Próximas citas (14 días)")
    prox = df[df.fecha_programacion.between(hoy, (date.today() + timedelta(days=14)).isoformat())]
    prox = prox.sort_values(["fecha_programacion", "hora"])
    st.dataframe(prox[["fecha_programacion", "hora", "nombre", "documento", "ciudad", "sede", "tipo_examen", "estado"]]
                 .rename(columns=NOMBRES_COLUMNAS), hide_index=True, width="stretch")

    st.subheader("Citas por mes")
    por_mes = df.dropna(subset=["fecha_programacion"]).assign(mes=lambda d: d.fecha_programacion.str[:7])
    st.bar_chart(por_mes.groupby("mes").size(), color="#7c3aed")


# ======== NUEVA ASIGNACIÓN ========
with tab_nueva:
    st.caption("Al elegir el tipo de examen se marcan solos los exámenes que corresponden (según la matriz de la Hoja2).")
    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre completo *")
    documento = c2.text_input("Número de documento *")
    cargo = c3.text_input("Cargo")
    despacho = c1.text_input("Despacho / Oficina")
    ciudad = c2.selectbox("Ciudad", sorted(df["ciudad"].dropna().unique()), index=None, placeholder="Elige…")
    correo = c3.text_input("Correo electrónico")
    celular = c1.text_input("Celular")
    tipo = c2.selectbox("Tipo de examen *", config.TIPOS_EXAMEN, key="nuevo_tipo")
    estado = c3.selectbox("Estado", config.ESTADOS, index=0)
    f_cita = c1.date_input("Fecha de la cita", value=None, format="DD/MM/YYYY")
    hora = c2.text_input("Hora (HH:MM)")
    sedes = sorted(df[df.ciudad == ciudad]["sede"].dropna().unique()) if ciudad else []
    sede = c3.selectbox("Sede IPS", sedes, index=0 if sedes else None, placeholder="Elige la ciudad primero")
    examenes = st.multiselect("Exámenes", config.EXAMENES, default=config.EXAMENES_POR_TIPO.get(tipo, []),
                              key=f"nuevo_examenes_{tipo}")
    notas = st.text_area("Notas")

    previos = df[df.documento == documento.strip()] if documento.strip() else df.iloc[0:0]
    if len(previos):
        st.warning(f"Esta cédula ya tiene {len(previos)} registro(s): "
                   + ", ".join(f"{r.tipo_examen} ({r.estado})" for r in previos.itertuples()))

    if st.button("➕ Crear asignación", type="primary"):
        if not nombre.strip() or not documento.strip():
            st.error("Nombre y documento son obligatorios.")
        else:
            nuevo_id = db.insertar(con, {
                "nombre": nombre.strip().upper(), "documento": "".join(ch for ch in documento if ch.isdigit()),
                "cargo": cargo.strip().upper() or None, "despacho": despacho.strip() or None, "ciudad": ciudad,
                "correo": correo.strip().lower() or None, "celular": celular.strip() or None,
                "fecha_requerimiento": date.today().isoformat(),
                "mes_programado": config.MESES[f_cita.month - 1] if f_cita else None,
                "fecha_programacion": f_cita.isoformat() if f_cita else None, "hora": hora or None,
                "sede": sede, "tipo_examen": tipo, "examenes": " | ".join(examenes) or None,
                "estado": estado, "notas": notas or None,
            }, origen=f"app ({USUARIO})")
            st.success(f"Asignación creada (ID {nuevo_id}).")


# ======== PREGUNTAR CON IA ========
with tab_ia:
    st.caption("Escribe tu pregunta en español. La IA la convierte en una consulta y la ejecuta **en tu computador**.")
    st.info("🔒 A Google solo se envía tu pregunta y la estructura de la tabla (nombres de columnas, ciudades, estados), "
            "**nunca los datos de las personas**. Evita escribir nombres o cédulas en la pregunta; para eso usa «Buscar».")
    ejemplos = [
        "¿Cuántas personas hay por estado en cada ciudad?",
        "¿Quiénes no asistieron y todavía no tienen una nueva fecha?",
        "Citas programadas para la próxima semana en Palmira",
        "¿Cuántos exámenes de ingreso se realizaron por mes?",
    ]
    cols = st.columns(len(ejemplos))
    for c, ej in zip(cols, ejemplos):
        if c.button(ej, width="stretch"):
            st.session_state.pregunta_ia = ej
    pregunta = st.text_input("Tu pregunta", key="pregunta_ia")
    if pregunta:
        if not secreto("GEMINI_API_KEY"):
            st.error("Falta GEMINI_API_KEY en el archivo .env para usar esta función.")
        else:
            os.environ.setdefault("GEMINI_API_KEY", secreto("GEMINI_API_KEY"))
            with st.spinner("Pensando…"):
                try:
                    sql, resultado = consulta_ia.preguntar(con, pregunta)
                    st.dataframe(resultado.rename(columns=NOMBRES_COLUMNAS), hide_index=True, width="stretch")
                    st.caption(f"{len(resultado)} filas")
                    with st.expander("Ver la consulta SQL que generó la IA"):
                        st.code(sql, language="sql")
                except Exception as e:
                    st.error(f"No pude responder: {e}")


# ======== CALIDAD DE DATOS ========
with tab_calidad:
    st.caption("Registros que conviene revisar. Haz clic en uno para corregirlo.")
    dup_mask = df.duplicated(["documento", "tipo_examen", "fecha_programacion"], keep=False) & df.documento.notna()
    revisiones = {
        "Posibles duplicados (misma cédula, tipo y fecha)": df[dup_mask].sort_values("documento"),
        "Estado POR REVISAR": df[df.estado == "POR REVISAR"],
        "AGENDADO pero la cita ya pasó": df[(df.estado == "AGENDADO") & (df.fecha_programacion < date.today().isoformat())],
        "AGENDADO sin fecha de cita": df[(df.estado == "AGENDADO") & df.fecha_programacion.isna()],
        "Sin documento": df[df.documento.isna()],
        "Sin celular ni correo": df[df.celular.isna() & df.correo.isna()],
    }
    for titulo, sub in revisiones.items():
        with st.expander(f"{titulo} — {len(sub)}", expanded=False):
            if len(sub) == 0:
                st.caption("✅ Nada que revisar.")
                continue
            ev = st.dataframe(sub[columnas].rename(columns=NOMBRES_COLUMNAS), hide_index=True,
                              width="stretch", on_select="rerun", selection_mode="single-row",
                              key=f"cal_{titulo}")
            if ev.selection.rows:
                registro = sub.iloc[ev.selection.rows[0]].to_dict()
                ficha(registro, f"cal{abs(hash(titulo))}")
                if st.button("🗑️ Eliminar este registro", key=f"del_{registro['id']}"):
                    db.eliminar(con, registro["id"], USUARIO)
                    st.rerun()