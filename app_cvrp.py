import streamlit as st
import pandas as pd
import altair as alt
import folium
from streamlit_folium import st_folium
from modelo_cvrp import (resolver_cvrp, CANTONES, DEMANDA, COORDS,
                          DIST_RAW, CAP)

st.set_page_config(
    page_title="CVRP Puntarenas — FIFCO",
    page_icon="🍺",
    layout="wide",
)

# ── Tema rosado oscuro ────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #1a0010; color: #fce4ec; }
    [data-testid="stSidebar"] { background-color: #2d0020 !important; }
    [data-testid="stSidebar"] * { color: #fce4ec !important; }

    .stTabs [data-baseweb="tab-list"] {
        background-color: #2d0020; border-radius: 10px; padding: 4px; gap: 4px;
    }
    .stTabs [data-baseweb="tab"]         { color: #f48fb1; font-weight: 600; border-radius: 8px; }
    .stTabs [aria-selected="true"]       { background-color: #880e4f !important; color: #fff !important; }

    [data-testid="stMetricValue"]        { font-size: 1.45rem !important; color: #f48fb1 !important; }
    [data-testid="stMetricLabel"]        { color: #f8bbd0 !important; font-weight: 600; }
    [data-testid="stMetricDelta"]        { color: #f48fb1 !important; }
    [data-testid="metric-container"]     {
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

    [data-testid="stNumberInput"] input  {
        background-color: #2d0020 !important; color: #fce4ec !important;
        border-color: #880e4f !important;
    }
    hr { border-color: #880e4f; opacity: 0.4; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

st.title("🍺 CVRP — Florida Bebidas · Puntarenas")
st.caption("Capacitated Vehicle Routing Problem · Minimiza km recorridos · Capacidad 24 pallets/camión")

# ── Sidebar ───────────────────────────────────────────────────
st.sidebar.header("⚙️ Configuración")
st.sidebar.markdown("**Parámetros del modelo**")
time_limit = st.sidebar.slider("Tiempo máximo solver (s)", 30, 300, 180, step=30)
st.sidebar.markdown("---")
st.sidebar.markdown(f"**📦 Capacidad por camión:** {CAP} pallets")
st.sidebar.markdown(f"**📍 Cantones:** {len(CANTONES)-1}")
st.sidebar.markdown(f"**📊 Demanda total:** {sum(v for k,v in DEMANDA.items() if k>0)} pallets/sem")
st.sidebar.markdown(f"**🚛 Flota mínima teórica:** ⌈{sum(v for k,v in DEMANDA.items() if k>0)}/{CAP}⌉ = {-(-sum(v for k,v in DEMANDA.items() if k>0)//CAP)} camiones")
st.sidebar.markdown("---")
optimizar = st.sidebar.button("🚀 Optimizar rutas", use_container_width=True)

# ── Sesión ────────────────────────────────────────────────────
if optimizar:
    with st.spinner("Resolviendo CVRP… puede tomar hasta 3 min la primera vez"):
        res = resolver_cvrp(time_limit=time_limit)
    st.session_state["res"] = res

res = st.session_state.get("res")

# ── Pestañas ──────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Resultado",
    "🗺️ Mapa de rutas",
    "📦 Detalle de rutas",
    "📊 Datos del problema",
])

# ══════════════════════════════════════════════════════════════
# TAB 1 — RESULTADO
# ══════════════════════════════════════════════════════════════
with tab1:
    if res is None:
        st.info("Presioná **Optimizar rutas** en la barra lateral para resolver el modelo.")
    else:
        demanda_total = sum(v for k, v in DEMANDA.items() if k > 0)
        flota_min     = -(-demanda_total // CAP)

        st.success(f"✅ Solución encontrada — Distancia total: **{res['distancia_km']:.0f} km**")
        st.markdown("---")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📏 Distancia total",      f"{res['distancia_km']:.0f} km")
        c2.metric("🚛 Camiones utilizados",  res["n_camiones"],
                  f"mínimo teórico: {flota_min}")
        c3.metric("📦 Demanda total",        f"{demanda_total} pallets")
        c4.metric("🔀 Arcos activos",        len(res["arcos"]))

        st.markdown("---")
        st.subheader("🔀 Rutas óptimas reconstruidas")

        COLORES = ["#e91e8c","#f48fb1","#ad1457","#f8bbd0","#880e4f",
                   "#c2185b","#ff80ab","#ff4081","#f06292","#e91e63",
                   "#d81b60","#ec407a","#ff1744","#ff6d00","#ff9100",
                   "#ffab40","#ffd740","#ffff00","#ccff90","#69ff47"]

        for idx, ruta in enumerate(res["rutas"]):
            nombres = " → ".join(CANTONES[n] for n in ruta)
            pallets = sum(DEMANDA[n] for n in ruta if n != 0)
            kms     = sum(DIST_RAW[ruta[k]][ruta[k+1]] for k in range(len(ruta)-1))
            col = COLORES[idx % len(COLORES)]
            st.markdown(
                f"<div style='background:#2d0020;border-left:4px solid {col};"
                f"padding:10px 14px;border-radius:8px;margin-bottom:8px;'>"
                f"<b style='color:{col}'>Camión {idx+1}</b> &nbsp;·&nbsp; "
                f"<span style='color:#fce4ec'>{nombres}</span><br>"
                f"<small style='color:#f48fb1'>{pallets} pallets · {kms} km</small></div>",
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

        COLORES_MAP = ["#e91e8c","#f48fb1","#ad1457","#ff80ab","#880e4f",
                       "#c2185b","#ff4081","#f06292","#e91e63","#d81b60",
                       "#ec407a","#ff1744","#ff6d00","#ffab40","#ccff90",
                       "#69ff47","#40c4ff","#18ffff","#b9f6ca","#fff176"]

        m = folium.Map(location=[9.2, -84.0], zoom_start=8,
                       tiles="CartoDB dark_matter")

        # Marcadores de cantones
        for nodo, nombre in CANTONES.items():
            lat, lon = COORDS[nodo]
            color  = "red" if nodo == 0 else "pink"
            icon   = "home" if nodo == 0 else "circle"
            dem    = DEMANDA[nodo]
            popup  = f"<b>{nombre}</b><br>Demanda: {dem} pallets" if nodo > 0 else "<b>CD Puntarenas (Depósito)</b>"
            folium.Marker(
                [lat, lon],
                popup=popup,
                tooltip=nombre,
                icon=folium.Icon(color=color, icon=icon, prefix="fa")
            ).add_to(m)

        # Trazar rutas
        for idx, ruta in enumerate(res["rutas"]):
            color = COLORES_MAP[idx % len(COLORES_MAP)]
            puntos = [COORDS[n] for n in ruta]
            pallets = sum(DEMANDA[n] for n in ruta if n != 0)
            nombre_ruta = " → ".join(CANTONES[n] for n in ruta)
            folium.PolyLine(
                puntos,
                color=color,
                weight=3,
                opacity=0.85,
                tooltip=f"Camión {idx+1}: {nombre_ruta} ({pallets} pallets)"
            ).add_to(m)

        st_folium(m, width=None, height=550)
        st.caption("Rojo = CD Puntarenas (depósito) · Cada color es un camión diferente")

# ══════════════════════════════════════════════════════════════
# TAB 3 — DETALLE DE RUTAS
# ══════════════════════════════════════════════════════════════
with tab3:
    if res is None:
        st.info("Optimizá primero desde la pestaña **Resultado**.")
    else:
        st.subheader("📦 Detalle de cada ruta")
        st.markdown("---")

        # Tabla de arcos activos
        st.markdown("**Arcos con flujo activo**")
        rows = []
        for (i, j), v in sorted(res["arcos"].items()):
            rows.append({
                "Desde":       CANTONES[i],
                "Hasta":       CANTONES[j],
                "Camiones":    v["camiones"],
                "Pallets":     v["pallets"],
                "Distancia km":v["km"],
                "Subtotal km": v["km"] * v["camiones"],
            })
        df_arcos = pd.DataFrame(rows)
        st.dataframe(df_arcos, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Tabla de rutas reconstruidas
        st.markdown("**Rutas completas**")
        ruta_rows = []
        for idx, ruta in enumerate(res["rutas"]):
            pallets = sum(DEMANDA[n] for n in ruta if n != 0)
            kms     = sum(DIST_RAW[ruta[k]][ruta[k+1]] for k in range(len(ruta)-1))
            paradas = [CANTONES[n] for n in ruta if n != 0]
            ruta_rows.append({
                "Camión":   f"Camión {idx+1}",
                "Ruta":     " → ".join(CANTONES[n] for n in ruta),
                "Paradas":  len(paradas),
                "Pallets":  pallets,
                "Ocup. %":  f"{pallets/CAP*100:.0f}%",
                "km":       kms,
            })
        df_rutas = pd.DataFrame(ruta_rows)
        st.dataframe(df_rutas, use_container_width=True, hide_index=True)

        st.markdown("---")

        # Gráfico km por camión
        st.subheader("📊 Kilómetros por camión")
        bar = (
            alt.Chart(df_rutas)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Camión:N", axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("km:Q", title="Kilómetros"),
                color=alt.value("#e91e8c"),
                tooltip=["Camión:N", "km:Q", "Pallets:Q", "Ocup. %:N"]
            )
            .properties(height=300)
        )
        st.altair_chart(bar, use_container_width=True)

        # Gráfico ocupación
        st.subheader("📦 Ocupación de cada camión")
        df_rutas["Pallets_n"] = [sum(DEMANDA[n] for n in r if n != 0) for r in res["rutas"]]
        df_rutas["Libre"]     = CAP - df_rutas["Pallets_n"]
        df_occ = df_rutas[["Camión","Pallets_n","Libre"]].melt("Camión", var_name="Tipo", value_name="Pallets")
        bar_occ = (
            alt.Chart(df_occ)
            .mark_bar()
            .encode(
                x=alt.X("Camión:N", axis=alt.Axis(labelAngle=-30)),
                y=alt.Y("Pallets:Q"),
                color=alt.Color("Tipo:N", scale=alt.Scale(
                    domain=["Pallets_n", "Libre"],
                    range=["#e91e8c", "#2d0020"]
                )),
                tooltip=["Camión:N", "Tipo:N", "Pallets:Q"]
            )
            .properties(height=280, title=f"Capacidad máx: {CAP} pallets")
        )
        st.altair_chart(bar_occ, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# TAB 4 — DATOS DEL PROBLEMA
# ══════════════════════════════════════════════════════════════
with tab4:
    st.subheader("📊 Cantones y demanda")
    st.markdown("---")

    df_dem = pd.DataFrame([
        {"Nodo": k, "Cantón": CANTONES[k], "Demanda (pallets)": DEMANDA[k]}
        for k in CANTONES if k > 0
    ])
    df_dem["Imperial"]  = [round(DEMANDA[k]*53/107) if k==1 else round(DEMANDA[k]*53/107) for k in range(1,14)]
    df_dem["Pilsen"]    = [round(DEMANDA[k]*27/107) if k==1 else round(DEMANDA[k]*27/107) for k in range(1,14)]
    df_dem["Tropical"]  = [round(DEMANDA[k]*27/107) if k==1 else round(DEMANDA[k]*27/107) for k in range(1,14)]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total cantones",      len(CANTONES)-1)
    c2.metric("Demanda total",       f"{sum(v for k,v in DEMANDA.items() if k>0)} pallets/sem")
    c3.metric("Capacidad camión",    f"{CAP} pallets")

    st.markdown("---")
    st.dataframe(df_dem, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📏 Matriz de distancias (km)")
    labels = [CANTONES[i] for i in range(14)]
    df_dist = pd.DataFrame(DIST_RAW, index=labels, columns=labels)
    st.dataframe(df_dist, use_container_width=True)

    st.markdown("---")
    st.subheader("📐 Modelo matemático")
    st.markdown("""
**Variables de decisión:**
- `y(i,j)` — entero ≥ 0: número de camiones que transitan el arco i→j
- `f(i,j)` — continua ≥ 0: pallets transportados en el arco i→j

**Función objetivo:**
```
Min Z = Σ dist(i,j) · y(i,j)
```

**Restricciones:**
```
(1) Balance camiones:  Σⱼ y(i,j) = Σⱼ y(j,i)             ∀i ∈ clientes
(2) Balance carga:     Σⱼ f(j,i) − Σⱼ f(i,j) = dᵢ        ∀i ∈ clientes
(3) Carga total CD:    Σⱼ f(0,j) = demanda total
(4) Capacidad:         f(i,j) ≤ 24 · y(i,j)               ∀(i,j)
```
    """)
