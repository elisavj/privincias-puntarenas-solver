"""
modelo_cvrp.py
CVRP — Florida Bebidas (FIFCO) · Provincia de Puntarenas
Minimiza la distancia total recorrida (km) · Capacidad: 24 pallets/camión

Restricción de tiempo incluida de DOS formas:
  Opción A — restricción explícita en el MIP:
             tiempo_arco(i,j) · y(i,j) ≤ JORNADA · y(i,j)
             → limita que ningún trip individual supere 480 min
  Opción B — post-procesamiento (Hito 4):
             Dado el conjunto de trips óptimos, hace bin-packing en camiones
             físicos de 8 h. Trips > 480 min → dedicated truck automáticamente.
"""
import math
from pulp import (LpProblem, LpMinimize, LpVariable, LpStatus,
                  lpSum, value, PULP_CBC_CMD)

# ── Parámetros operativos (Hito 4) ──────────────────────────
VELOCIDAD  = 40    # km/h
T_PARADA   = 15    # min por parada
T_PALLET   = 3     # min por pallet
T_RELOAD   = 20    # min entre trips del mismo camión
JORNADA    = 480   # min (8 h)

# ── Datos fijos del problema ─────────────────────────────────
CANTONES = {
    0: "CD Puntarenas", 1: "Puntarenas",    2: "Esparza",
    3: "Buenos Aires",  4: "Montes de Oro", 5: "Osa",
    6: "Quepos",        7: "Golfito",       8: "Coto Brus",
    9: "Parrita",      10: "Corredores",   11: "Garabito",
   12: "Monteverde",   13: "Puerto Jiménez"
}
# NOTA: El nodo 0 (CD Puntarenas) y el nodo 1 (Puntarenas) comparten las mismas
# coordenadas y tienen distancia 0 entre sí, porque el centro de distribución está
# ubicado dentro del cantón de Puntarenas. Los arcos (0,1) y (1,0) son válidos pero
# de distancia nula; el solver los puede activar sin costo. En los resultados, trips
# CD→Puntarenas→CD son directos (km = 0 de CD a Puntarenas).

DEMANDA = {
    0: 0,   1: 107, 2: 27,  3: 37,  4: 12,
    5: 28,  6: 24,  7: 33,  8: 35,  9: 16,
   10: 39, 11: 20, 12:  4, 13:  8
}

COORDS = {
    0:  (9.9748, -84.8316),
    1:  (9.9748, -84.8316),
    2:  (9.9883, -84.6672),
    3:  (9.1636, -83.3317),
    4:  (10.0750,-84.6417),
    5:  (8.9394, -83.4675),
    6:  (9.4328, -84.1614),
    7:  (8.6470, -83.1818),
    8:  (8.9965, -82.9665),
    9:  (9.5155, -84.3272),
   10:  (8.5567, -83.0382),
   11:  (9.8725, -84.7255),
   12: (10.2992, -84.8258),
   13:  (8.5341, -83.3101),
}

DIST_RAW = [
#       0    1    2    3    4    5    6    7    8    9   10   11   12   13
    [   0,   0,  25, 244,  27, 243, 124, 307, 307,  99, 332,  60,  47, 303],
    [   0,   0,  25, 244,  27, 243, 124, 307, 307,  99, 332,  60,  47, 303],
    [  25,  25,   0, 224,  19, 226, 109, 290, 287,  85, 314,  55,  49, 288],
    [ 244, 244, 224,   0, 240,  41, 124,  80,  63, 150,  95, 196, 267,  92],
    [  27,  27,  19, 240,   0, 244, 127, 308, 303, 103, 331,  73,  30, 305],
    [ 243, 243, 226,  41, 244,   0, 119,  64,  79, 145,  90, 189, 272,  64],
    [ 124, 124, 109, 124, 127, 119,   0, 183, 186,  26, 208,  72, 156, 179],
    [ 307, 307, 290,  80, 308,  64, 183,   0,  54, 208,  31, 253, 336,  25],
    [ 307, 307, 287,  63, 303,  79, 186,  54,   0, 212,  46, 259, 330,  78],
    [  99,  99,  85, 150, 103, 145,  26, 208, 212,   0, 234,  47, 133, 204],
    [ 332, 332, 314,  95, 331,  90, 208,  31,  46, 234,   0, 279, 359,  52],
    [  60,  60,  55, 196,  73, 189,  72, 253, 259,  47, 279,   0, 102, 246],
    [  47,  47,  49, 267,  30, 272, 156, 336, 330, 133, 359, 102,   0, 335],
    [ 303, 303, 288,  92, 305,  64, 179,  25,  78, 204,  52, 246, 335,   0],
]

CAP = 24  # pallets/camión


# ── Funciones de tiempo ──────────────────────────────────────
def duracion_trip(ruta: list[int]) -> float:
    """
    Duración de un trip completo (min).
    Fórmula: (km_totales / velocidad × 60) + paradas × T_PARADA + pallets × T_PALLET
    La ruta incluye el nodo 0 al inicio y al final.
    """
    km = sum(DIST_RAW[ruta[k]][ruta[k+1]] for k in range(len(ruta)-1))
    paradas = len([n for n in ruta if n != 0])
    pallets = sum(DEMANDA[n] for n in ruta if n != 0)
    return (km / VELOCIDAD * 60) + paradas * T_PARADA + pallets * T_PALLET


def tiempo_arco(i: int, j: int) -> float:
    """
    Tiempo mínimo de un trip directo CD→i→j→CD (min).
    Usado en la restricción A del MIP para acotar arcos muy lentos.
    """
    km = DIST_RAW[0][i] + DIST_RAW[i][j] + DIST_RAW[j][0]
    return (km / VELOCIDAD * 60) + 2 * T_PARADA + (DEMANDA[i] + DEMANDA[j]) * T_PALLET


def build_dist():
    d = {}
    N = list(range(14))
    for i in N:
        for j in N:
            if i != j:
                if DIST_RAW[i][j] > 0 or i == 0 or j == 0:
                    d[(i, j)] = DIST_RAW[i][j]
    return d


DIST = build_dist()


# ── Resolver CVRP ────────────────────────────────────────────
def resolver_cvrp(time_limit: int = 180, respetar_jornada: bool = True) -> dict:
    """
    Resuelve el CVRP para Puntarenas.

    Parámetros
    ----------
    time_limit       : segundos máximos del solver CBC
    respetar_jornada : si True, agrega restricción A (tiempo por arco ≤ 480 min)

    Variables
    ---------
    y[i,j] : entero ≥ 0  — camiones en el arco i→j
    f[i,j] : continua ≥ 0 — pallets en el arco i→j
    """
    N     = list(range(14))
    C     = list(range(1, 14))
    ARCOS = [(i, j) for i in N for j in N if i != j and (i, j) in DIST]

    prob = LpProblem("CVRP_Puntarenas", LpMinimize)

    y = {(i, j): LpVariable(f"y_{i}_{j}", lowBound=0, cat="Integer") for (i, j) in ARCOS}
    f = {(i, j): LpVariable(f"f_{i}_{j}", lowBound=0)                for (i, j) in ARCOS}

    # Objetivo
    prob += lpSum(DIST[i, j] * y[i, j] for (i, j) in ARCOS)

    # (1) Balance camiones
    for i in C:
        prob += (lpSum(y[i, j] for j in N if (i, j) in ARCOS) ==
                 lpSum(y[j, i] for j in N if (j, i) in ARCOS))

    # (2) Balance carga
    for i in C:
        prob += (lpSum(f[j, i] for j in N if (j, i) in ARCOS) -
                 lpSum(f[i, j] for j in N if (i, j) in ARCOS) == DEMANDA[i])

    # (3) Total sale del CD
    prob += lpSum(f[0, j] for j in C if (0, j) in ARCOS) == sum(DEMANDA[i] for i in C)

    # (4) Capacidad
    for (i, j) in ARCOS:
        prob += f[i, j] <= CAP * y[i, j]

    # (5) OPCIÓN A — Restricción de tiempo por arco ≤ jornada
    #     Tiempo estimado mínimo del trip CD→i→j→CD ≤ 480 min
    #     Si el arco por sí solo ya excede la jornada, se fuerza y[i,j] = 0
    if respetar_jornada:
        for (i, j) in ARCOS:
            if i != 0 and j != 0:
                t_est = tiempo_arco(i, j)
                if t_est > JORNADA:
                    prob += y[i, j] == 0   # arco prohibido — trip imposible en 8 h

    prob.solve(PULP_CBC_CMD(msg=0, timeLimit=time_limit))

    status  = LpStatus[prob.status]
    dist_km = value(prob.objective) or 0

    arcos_activos = {
        (i, j): {
            "camiones": int(round(value(y[i, j]))),
            "pallets":  round(value(f[i, j]) or 0, 1),
            "km":       DIST[i, j],
        }
        for (i, j) in ARCOS
        if value(y[i, j]) and value(y[i, j]) > 0.5
    }

    rutas = _reconstruir_rutas(arcos_activos, N)

    # OPCIÓN B — post-procesamiento: bin-packing de trips en camiones físicos
    trucks = _bin_packing_trucks(rutas)

    return {
        "status":       status,
        "distancia_km": dist_km,
        "arcos":        arcos_activos,
        "rutas":        rutas,
        "trucks":       trucks,
        "n_camiones":   sum(v["camiones"] for (i, j), v in arcos_activos.items() if i == 0),
        "n_trucks":     len(trucks),
    }


# ── Reconstruir rutas ────────────────────────────────────────
def _reconstruir_rutas(arcos: dict, N: list) -> list[dict]:
    """
    Convierte arcos activos del MIP en trips individuales que respetan
    estrictamente la capacidad de CAP=24 pallets.

    Lógica:
    - Usa los arcos del MIP para determinar qué rutas combinar clientes.
    - Para nodos cuya demanda supera CAP (ej. Puntarenas 107 pallets),
      genera múltiples trips directos CD→nodo→CD de a CAP pallets.
    - Para rutas combinadas, verifica que la suma no exceda CAP;
      si lo hace, divide en sub-trips.
    """
    # Paso 1: construir grafo de sucesores
    succ: dict[int, list[int]] = {}
    for (i, j), v in arcos.items():
        for _ in range(v["camiones"]):
            succ.setdefault(i, []).append(j)

    # Paso 2: trazar rutas desde el depósito
    rutas_nodos: list[list[int]] = []
    starts = list(succ.get(0, []))
    for nxt in starts:
        ruta = [0, nxt]
        succ[0].remove(nxt)
        cur  = nxt
        while cur != 0:
            nexts = succ.get(cur, [])
            if not nexts:
                break
            nxt2 = nexts.pop(0)
            ruta.append(nxt2)
            if nxt2 == 0:
                break
            cur = nxt2
        if ruta[-1] != 0:
            ruta.append(0)
        rutas_nodos.append(ruta)

    # Paso 3: para cada ruta, dividir en sub-trips si excede CAP
    rutas = []
    for ruta in rutas_nodos:
        clientes = [n for n in ruta if n != 0]
        # Dividir demanda de cada cliente en chunks de CAP
        # y combinar clientes greedy respetando CAP
        sub_trip  = [0]
        carga_sub = 0
        for n in clientes:
            dem_n = DEMANDA[n]
            # Si la demanda del nodo por sí sola supera CAP, trips directos
            while dem_n > 0:
                espacio = CAP - carga_sub
                if espacio <= 0:
                    sub_trip.append(0)
                    rutas.append(_make_trip_pallets(sub_trip, carga_sub))
                    sub_trip, carga_sub = [0], 0
                    espacio = CAP
                tomar = min(dem_n, espacio)
                sub_trip.append(n)
                carga_sub += tomar
                dem_n     -= tomar
                # Si el nodo no cupo completo, cerrar este trip
                if dem_n > 0:
                    sub_trip.append(0)
                    rutas.append(_make_trip_pallets(sub_trip, carga_sub))
                    sub_trip, carga_sub = [0], 0

        if len(sub_trip) > 1:
            sub_trip.append(0)
            rutas.append(_make_trip_pallets(sub_trip, carga_sub))

    return rutas


def _make_trip_pallets(ruta: list[int], pallets_real: int) -> dict:
    """
    Construye dict de un trip. pallets_real es la carga real
    (puede diferir de la suma de DEMANDA si el nodo fue dividido).
    """
    # Eliminar nodos duplicados consecutivos que surgen al dividir
    ruta_unica = [ruta[0]]
    for n in ruta[1:]:
        if n != ruta_unica[-1]:
            ruta_unica.append(n)
    if ruta_unica[-1] != 0:
        ruta_unica.append(0)

    clientes_unicos = list(dict.fromkeys(n for n in ruta_unica if n != 0))
    km   = sum(DIST_RAW[ruta_unica[k]][ruta_unica[k+1]]
               for k in range(len(ruta_unica)-1))
    paradas = len(clientes_unicos)
    dur  = (km / VELOCIDAD * 60) + paradas * T_PARADA + pallets_real * T_PALLET
    return {
        "nodos":    ruta_unica,
        "nombres":  [CANTONES[n] for n in ruta_unica],
        "km":       km,
        "pallets":  pallets_real,
        "duracion": round(dur, 1),
        "dedicado": dur > JORNADA,
    }


def _make_trip(ruta: list[int]) -> dict:
    """
    Construye el dict de un trip usando la demanda completa de cada nodo.
    Delega en _make_trip_pallets para mantener consistencia de cálculo.
    """
    pallets = sum(DEMANDA[n] for n in ruta if n != 0)
    return _make_trip_pallets(ruta, pallets)


# ── Opción B: bin-packing trips → camiones físicos ──────────
def _bin_packing_trucks(rutas: list[dict]) -> list[dict]:
    """
    Agrupa trips en camiones físicos de jornada 8 h (480 min).
    Lógica:
      - Trip dedicado (> 480 min solo) → 1 camión exclusivo.
      - Resto: first-fit decreasing por duración, sumando T_RELOAD entre trips.
    """
    dedicados    = [r for r in rutas if r["dedicado"]]
    no_dedicados = sorted([r for r in rutas if not r["dedicado"]],
                          key=lambda r: r["duracion"], reverse=True)

    trucks = []

    # Camiones dedicados
    for r in dedicados:
        trucks.append({
            "tipo":     "Dedicado",
            "trips":    [r],
            "tiempo":   r["duracion"],
            "km_total": r["km"],
        })

    # Bin-packing first-fit para el resto
    bins: list[dict] = []
    for trip in no_dedicados:
        colocado = False
        for b in bins:
            usado = b["tiempo"] + T_RELOAD + trip["duracion"]
            if usado <= JORNADA:
                b["trips"].append(trip)
                b["tiempo"]   += T_RELOAD + trip["duracion"]
                b["km_total"] += trip["km"]
                colocado = True
                break
        if not colocado:
            bins.append({
                "tipo":     "Normal",
                "trips":    [trip],
                "tiempo":   trip["duracion"],
                "km_total": trip["km"],
            })

    trucks += bins
    return trucks


if __name__ == "__main__":
    print("Resolviendo CVRP con restricción de jornada…")
    res = resolver_cvrp()
    print(f"Status         : {res['status']}")
    print(f"Distancia total: {res['distancia_km']:.0f} km")
    print(f"Trips generados: {len(res['rutas'])}")
    print(f"Camiones físicos (Hito 4): {res['n_trucks']}")
    print()
    for i, t in enumerate(res["trucks"]):
        print(f"  Camión {i+1} [{t['tipo']}] — {t['tiempo']:.0f} min — {t['km_total']} km")
        for r in t["trips"]:
            print(f"    Trip: {' → '.join(r['nombres'])}  ({r['duracion']:.0f} min, {r['pallets']} pallets)")
