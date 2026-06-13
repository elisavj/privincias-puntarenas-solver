import streamlit as st
import pandas as pd
import altair as alt
import folium
from streamlit_folium import st_folium
from modelo_cvrp import (resolver_cvrp, CANTONES, DEMANDA, COORDS,
                          DIST_RAW, CAP, JORNADA, VELOCIDAD,
                          T_PARADA, T_PALLET, T_RELOAD, duracion_trip)

st.set_page_config(page_title="CVRP Puntarenas — FIFCO", page_icon="🍺", layout="wide")

# ── Tema rosado oscuro ────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #1a0010; color: #fce4ec; }
    [data-testid="stSidebar"] { background-color: #2d0020 !important; }
    [data-testid="stSidebar"] * { color: #fce4ec !important; }
    .stTabs [data-baseweb="tab-list"] {
        background-color: #2d0020; border-radius: 10px; padding: 4px; gap: 4px;
    }
    .stTabs [data-baseweb="tab"]   { color: #f48fb1; font-weight: 600; border-radius: 8px; }
    .stTabs [aria-selected="true"] { background-color: #880e4f !important; color: #fff !important; }
    [data-testid="stMetricValue"]    { font-size: 1.4rem !important; color: #f48fb1 !important; }
    [data-testid="stMetricLabel"]    { color: #f8bbd0 !important; font-weight: 600; }
    [data-testid="stMetricDelta"]    { color: #f48fb1 !important; }
    [data-testid="metric-container"] {
        background-color: #2d0020; border: 1px solid #880e4f;
        border-radius: 12px; padding: 14px 18px;
    }
    h1 { color: #f48fb1 !important; }
    h2, h3 { color: #f8bbd0 !important; }
    p, li { color: #fce4ec; }
    .stCaption { color: #ad1457 !important; }
    .stButton > button {
        background-color: #880e4f; color: #fff; border: none;
        border-radius: 8px; font-weight: 700;
    }
    .stButton > button:hover { background-color: #ad1457; color: #fff; }
    hr { border-color: #880e4f; opacity: 0.4; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

st.title("🍺 CVRP — Florida Bebidas · Puntarenas")
st.caption("Capacitated Vehicle Routing Problem · Minimiza km · Capacidad 24 pallets/camión · Jornada 8 h")

# ── Sidebar ───────────────────────────────────────────────────
st.sidebar.header("⚙️ Configuración")
respetar_jornada = st.sidebar.toggle(
    "Restricción de jornada en MIP (Opción A)",
    value=False,
    help="Desactivado por defecto: minimiza distancia total (5 388 km). "
         "Al activar, el solver restringe arcos largos y aumenta los km totales."
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**📦 Capacidad por camión:** {CAP} pallets")
st.sidebar.markdown(f"**⏱️ Jornada:** {JORNADA} min (8 h)")
st.sidebar.markdown(f"**🚗 Velocidad:** {VELOCIDAD} km/h")
st.sidebar.markdown(f"**🛑 Por parada:** {T_PARADA} min")
st.sidebar.markdown(f"**📦 Por pallet:** {T_PALLET} min")
st.sidebar.markdown(f"**🔄 Reload entre trips:** {T_RELOAD} min")
dem_total = sum(v for k, v in DEMANDA.items() if k > 0)
st.sidebar.markdown(f"**📊 Demanda total:** {dem_total} pallets")
st.sidebar.markdown(f"**🚛 Flota mínima:** ⌈{dem_total}/{CAP}⌉ = {-(-dem_total//CAP)}")
st.sidebar.markdown("---")
optimizar = st.sidebar.button("🚀 Optimizar rutas", use_container_width=True)

# ── Sesión ────────────────────────────────────────────────────
if optimizar:
    with st.spinner("Resolviendo CVRP… puede tardar hasta 3 min"):
        res = resolver_cvrp(respetar_jornada=respetar_jornada)
    st.session_state["res"] = res

res = st.session_state.get("res")

COLORES = ["#e91e8c","#f48fb1","#ad1457","#ff80ab","#880e4f",
           "#c2185b","#ff4081","#f06292","#e91e63","#d81b60",
           "#ec407a","#ff1744","#ff6d00","#ffab40","#ccff90",
           "#69ff47","#40c4ff","#18ffff","#b9f6ca","#fff176"]

# ── Pestañas ──────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Resultado",
    "🗺️ Mapa de rutas",
    "⏱️ Camiones físicos — Jornada 8 h",
    "📊 Datos del problema",
])

# ══════════════════════════════════════════════════════════════
# TAB 1 — RESULTADO
# ══════════════════════════════════════════════════════════════
with tab1:
    if res is None:
        st.info("Presioná **Optimizar rutas** en la barra lateral.")
    else:
        flota_min = -(-dem_total // CAP)
        st.success(f"✅ Solución encontrada — Distancia total: **{res['distancia_km']:.0f} km**")
        st.markdown("---")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📏 Distancia total",       f"{res['distancia_km']:.0f} km")
        c2.metric("🔀 Trips generados",        len(res["rutas"]))
        c3.metric("🚛 Camiones físicos",        res["n_trucks"],
                  f"mínimo teórico: {flota_min}")
        c4.metric("📦 Demanda total",          f"{dem_total} pallets")
        c5.metric("🔗 Arcos activos",           len(res["arcos"]))

        dedicados = sum(1 for r in res["rutas"] if r["dedicado"])
        if dedicados:
            st.warning(f"⚠️ **{dedicados} trip(s) dedicado(s):** su duración supera las 8 h por sí solos "
                       f"→ requieren un camión exclusivo (Hito 4, regla 3).")

        st.markdown("---")
        st.subheader("🔀 Trips óptimos")
        for idx, r in enumerate(res["rutas"]):
            col = COLORES[idx % len(COLORES)]
            badge = "🔴 Dedicado" if r["dedicado"] else "🟢 Normal"
            st.markdown(
                f"<div style='background:#2d0020;border-left:4px solid {col};"
                f"padding:10px 14px;border-radius:8px;margin-bottom:8px;'>"
                f"<b style='color:{col}'>Trip {idx+1}</b> &nbsp;{badge}&nbsp;·&nbsp;"
                f"<span style='color:#fce4ec'>{' → '.join(r['nombres'])}</span><br>"
                f"<small style='color:#f48fb1'>"
                f"{r['pallets']} pallets · {r['km']} km · {r['duracion']:.0f} min"
                f"{'  ⚠️ >480 min' if r['dedicado'] else ''}"
                f"</small></div>",
                unsafe_allow_html=True
            )

# ══════════════════════════════════════════════════════════════
# TAB 2 — MAPA DE RUTAS
# ══════════════════════════════════════════════════════════════
with tab2:
    if res is None:
        st.info("Optimizá primero desde la pestaña **Resultado**.")
    else:
        st.subheader("🗺️ Mapa de rutas óptimas — Puntarenas")

        m = folium.Map(location=[9.2, -84.0], zoom_start=8,
                       tiles="CartoDB dark_matter")

        for nodo, nombre in CANTONES.items():
            lat, lon = COORDS[nodo]
            color  = "red"  if nodo == 0 else "pink"
            icon   = "home" if nodo == 0 else "circle"
            popup  = (f"<b>{nombre}</b><br>Demanda: {DEMANDA[nodo]} pallets"
                      if nodo > 0 else "<b>CD Puntarenas (Depósito)</b>")
            folium.Marker([lat, lon], popup=popup, tooltip=nombre,
                          icon=folium.Icon(color=color, icon=icon, prefix="fa")
                          ).add_to(m)

        for idx, r in enumerate(res["rutas"]):
            color  = COLORES[idx % len(COLORES)]
            puntos = [COORDS[n] for n in r["nodos"]]
            tip    = (f"Trip {idx+1}: {' → '.join(r['nombres'])} "
                      f"({r['pallets']} pallets · {r['duracion']:.0f} min)")
            dash   = "10 5" if r["dedicado"] else None
            folium.PolyLine(puntos, color=color, weight=3,
                            opacity=0.85, tooltip=tip,
                            dash_array=dash).add_to(m)

        st_folium(m, width=None, height=560)
        st.caption("🔴 = CD Puntarenas · Cada color = un trip · Línea punteada = trip dedicado (>8 h)")

# ══════════════════════════════════════════════════════════════
# TAB 3 — CAMIONES FÍSICOS (HITO 4)
# ══════════════════════════════════════════════════════════════
with tab3:
    if res is None:
        st.info("Optimizá primero desde la pestaña **Resultado**.")
    else:
        st.subheader("⏱️ Asignación de trips a camiones físicos (Hito 4)")
        st.markdown(
            "Cada camión físico opera en una **jornada de 8 horas (480 min)**. "
            "Puede encadenar varios trips: entrega → vuelve al CD → "
            f"reload {T_RELOAD} min → sale otra vez, mientras la suma no pase de 480 min. "
            "Si un trip solo ya supera los **480 min** → **dedicated truck** (camión exclusivo para ese trip)."
        )
        st.markdown("---")

        trucks = res["trucks"]
        norm  = sum(1 for t in trucks if t["tipo"] == "Normal")
        ded   = sum(1 for t in trucks if t["tipo"] == "Dedicado")

        c1, c2, c3 = st.columns(3)
        c1.metric("🚛 Camiones normales",   norm)
        c2.metric("🔴 Camiones dedicados",  ded,
                  "Trip único > 8 h" if ded else "Ninguno")
        c3.metric("🚛 Total camiones",      norm + ded)

        st.markdown("---")

        for idx, t in enumerate(trucks):
            color = "#e91e8c" if t["tipo"] == "Normal" else "#ff1744"
            ocup  = t["tiempo"] / JORNADA * 100
            with st.expander(f"Camión {idx+1} — {t['tipo']} — {t['tiempo']:.0f} min"):
                df_bar = pd.DataFrame({
                    "Concepto": ["Utilizado", "Disponible"],
                    "Minutos":  [min(t["tiempo"], JORNADA),
                                 max(JORNADA - t["tiempo"], 0)]
                })
                bar = (
                    alt.Chart(df_bar)
                    .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
                    .encode(
                        x=alt.X("Minutos:Q", scale=alt.Scale(domain=[0, JORNADA + 50])),
                        y=alt.Y("Concepto:N", axis=alt.Axis(labelAngle=0)),
                        color=alt.Color("Concepto:N", scale=alt.Scale(
                            domain=["Utilizado", "Disponible"],
                            range=[color, "#2d0020"]
                        ), legend=None),
                    )
                    .properties(height=100)
                )
                st.altair_chart(bar, use_container_width=True)

                acum = 0
                for ti, trip in enumerate(t["trips"]):
                    if ti > 0:
                        acum += T_RELOAD
                    acum += trip["duracion"]
                    st.markdown(
                        f"<div style='background:#1a0010;border-left:3px solid {color};"
                        f"padding:8px 12px;border-radius:6px;margin-bottom:6px;'>"
                        f"<b style='color:{color}'>Trip {ti+1}</b> — "
                        f"{' → '.join(trip['nombres'])}<br>"
                        f"<small style='color:#f8bbd0'>"
                        f"{trip['pallets']} pallets · {trip['km']} km · "
                        f"{trip['duracion']:.0f} min · acumulado: {acum:.0f} min</small></div>",
                        unsafe_allow_html=True
                    )

        st.markdown("---")

        st.subheader("📊 Resumen por camión")
        rows = []
        for idx, t in enumerate(trucks):
            rows.append({
                "Camión":             f"Camión {idx+1}",
                "Tipo":               t["tipo"],
                "Trips":              len(t["trips"]),
                "Tiempo usado (min)": round(t["tiempo"], 0),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)



# ══════════════════════════════════════════════════════════════
# TAB 4 — DATOS DEL PROBLEMA
# ══════════════════════════════════════════════════════════════
with tab4:
    st.subheader("📊 Cantones y demanda")
    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total cantones",   len(CANTONES)-1)
    c2.metric("Demanda total",    f"{dem_total} pallets/sem")
    c3.metric("Capacidad camión", f"{CAP} pallets")

    df_dem = pd.DataFrame([
        {"Nodo": k, "Cantón": CANTONES[k], "Demanda total": DEMANDA[k],
         "Imperial": round(DEMANDA[k]*53/107),
         "Pilsen":   round(DEMANDA[k]*27/107),
         "Tropical": round(DEMANDA[k]*27/107)}
        for k in range(1, 14)
    ])
    st.dataframe(df_dem, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📏 Matriz de distancias (km)")
    labels  = [CANTONES[i] for i in range(14)]
    df_dist = pd.DataFrame(DIST_RAW, index=labels, columns=labels)
    st.dataframe(df_dist, use_container_width=True)

    st.markdown("---")
    st.subheader("📐 Modelo matemático")
    st.markdown(f"""
**Variables de decisión:**
- `y(i,j)` — entero ≥ 0: camiones en el arco i→j
- `f(i,j)` — continua ≥ 0: pallets en el arco i→j

**Función objetivo:**
```
Min Z = Σ dist(i,j) · y(i,j)
```

**Restricciones:**
```
(1) Balance camiones : Σⱼ y(i,j) = Σⱼ y(j,i)          ∀i ∈ clientes
(2) Balance carga    : Σⱼ f(j,i) − Σⱼ f(i,j) = dᵢ     ∀i ∈ clientes
(3) Total del CD     : Σⱼ f(0,j) = demanda total
(4) Capacidad        : f(i,j) ≤ {CAP} · y(i,j)          ∀(i,j)
(5) [Opción A] Tiempo: si t_est(i→j) > {JORNADA} min → y(i,j) = 0  ⚠️ desactivada por defecto
```

**Post-procesamiento (Opción B — Hito 4):**
```
Duración trip = (km/vel × 60) + paradas × {T_PARADA} + pallets × {T_PALLET}
Trip > {JORNADA} min → dedicated truck
Resto → bin-packing first-fit con reload de {T_RELOAD} min entre trips
```
    """)
