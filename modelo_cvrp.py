"""
modelo_cvrp.py
CVRP — Florida Bebidas (FIFCO) · Provincia de Puntarenas
Minimiza la distancia total recorrida (km) · Capacidad: 24 pallets/camión
"""
from pulp import (LpProblem, LpMinimize, LpVariable, LpStatus,
                  lpSum, value, PULP_CBC_CMD)

# ── Datos fijos del problema ─────────────────────────────────
CANTONES = {
    0: "CD Puntarenas", 1: "Puntarenas",    2: "Esparza",
    3: "Buenos Aires",  4: "Montes de Oro", 5: "Osa",
    6: "Quepos",        7: "Golfito",       8: "Coto Brus",
    9: "Parrita",      10: "Corredores",   11: "Garabito",
   12: "Monteverde",   13: "Puerto Jiménez"
}

DEMANDA = {
    0: 0,   1: 107, 2: 27,  3: 37,  4: 12,
    5: 28,  6: 24,  7: 33,  8: 35,  9: 16,
   10: 39, 11: 20, 12:  4, 13:  8
}

# Coordenadas aproximadas (lat, lon) para el mapa
COORDS = {
    0:  (9.9748, -84.8316),   # CD Puntarenas
    1:  (9.9748, -84.8316),   # Puntarenas
    2:  (9.9883, -84.6672),   # Esparza
    3:  (9.1636, -83.3317),   # Buenos Aires
    4:  (10.0750,-84.6417),   # Montes de Oro
    5:  (8.9394, -83.4675),   # Osa
    6:  (9.4328, -84.1614),   # Quepos
    7:  (8.6470, -83.1818),   # Golfito
    8:  (8.9965, -82.9665),   # Coto Brus
    9:  (9.5155, -84.3272),   # Parrita
   10:  (8.5567, -83.0382),   # Corredores
   11:  (9.8725, -84.7255),   # Garabito
   12: (10.2992, -84.8258),   # Monteverde
   13:  (8.5341, -83.3101),   # Puerto Jiménez
}

DIST_RAW = [
#       0    1    2    3    4    5    6    7    8    9   10   11   12   13
    [   0,   0,  25, 244,  27, 243, 124, 307, 307,  99, 332,  60,  47, 303],  # 0
    [   0,   0,  25, 244,  27, 243, 124, 307, 307,  99, 332,  60,  47, 303],  # 1
    [  25,  25,   0, 224,  19, 226, 109, 290, 287,  85, 314,  55,  49, 288],  # 2
    [ 244, 244, 224,   0, 240,  41, 124,  80,  63, 150,  95, 196, 267,  92],  # 3
    [  27,  27,  19, 240,   0, 244, 127, 308, 303, 103, 331,  73,  30, 305],  # 4
    [ 243, 243, 226,  41, 244,   0, 119,  64,  79, 145,  90, 189, 272,  64],  # 5
    [ 124, 124, 109, 124, 127, 119,   0, 183, 186,  26, 208,  72, 156, 179],  # 6
    [ 307, 307, 290,  80, 308,  64, 183,   0,  54, 208,  31, 253, 336,  25],  # 7
    [ 307, 307, 287,  63, 303,  79, 186,  54,   0, 212,  46, 259, 330,  78],  # 8
    [  99,  99,  85, 150, 103, 145,  26, 208, 212,   0, 234,  47, 133, 204],  # 9
    [ 332, 332, 314,  95, 331,  90, 208,  31,  46, 234,   0, 279, 359,  52],  # 10
    [  60,  60,  55, 196,  73, 189,  72, 253, 259,  47, 279,   0, 102, 246],  # 11
    [  47,  47,  49, 267,  30, 272, 156, 336, 330, 133, 359, 102,   0, 335],  # 12
    [ 303, 303, 288,  92, 305,  64, 179,  25,  78, 204,  52, 246, 335,   0],  # 13
]

CAP = 24  # pallets por camión

def build_dist():
    d = {}
    N = list(range(14))
    for i in N:
        for j in N:
            if i != j and DIST_RAW[i][j] > 0 or (i == 0 or j == 0):
                d[(i, j)] = DIST_RAW[i][j]
    return d

DIST = build_dist()


def resolver_cvrp(time_limit: int = 180) -> dict:
    """
    Resuelve el CVRP para Puntarenas.

    Variables:
      y[i,j] : entero ≥ 0 — camiones que transitan el arco i→j
      f[i,j] : continua ≥ 0 — pallets transportados en el arco i→j

    Retorna dict con status, distancia total, arcos activos y rutas reconstruidas.
    """
    N = list(range(14))
    C = list(range(1, 14))   # clientes (sin depósito)
    ARCOS = [(i, j) for i in N for j in N if i != j and (i, j) in DIST]

    prob = LpProblem("CVRP_Puntarenas", LpMinimize)

    y = {(i, j): LpVariable(f"y_{i}_{j}", lowBound=0, cat="Integer") for (i, j) in ARCOS}
    f = {(i, j): LpVariable(f"f_{i}_{j}", lowBound=0) for (i, j) in ARCOS}

    # Objetivo: minimizar km totales
    prob += lpSum(DIST[i, j] * y[i, j] for (i, j) in ARCOS)

    # (1) Balance camiones — entran = salen en cada cliente
    for i in C:
        prob += (lpSum(y[i, j] for j in N if (i, j) in ARCOS) ==
                 lpSum(y[j, i] for j in N if (j, i) in ARCOS))

    # (2) Balance carga — entra − sale = demanda del cliente
    for i in C:
        prob += (lpSum(f[j, i] for j in N if (j, i) in ARCOS) -
                 lpSum(f[i, j] for j in N if (i, j) in ARCOS) == DEMANDA[i])

    # (3) Total pallets que sale del CD = demanda total
    prob += lpSum(f[0, j] for j in C if (0, j) in ARCOS) == sum(DEMANDA[i] for i in C)

    # (4) Capacidad por arco: f[i,j] ≤ 24 · y[i,j]
    for (i, j) in ARCOS:
        prob += f[i, j] <= CAP * y[i, j]

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

    # Reconstruir rutas desde el depósito
    rutas = _reconstruir_rutas(arcos_activos, N)

    return {
        "status":         status,
        "distancia_km":   dist_km,
        "arcos":          arcos_activos,
        "rutas":          rutas,
        "n_camiones":     sum(v["camiones"] for (i, j), v in arcos_activos.items() if i == 0),
    }


def _reconstruir_rutas(arcos: dict, N: list) -> list[list[int]]:
    """Reconstruye las rutas individuales trazando caminos desde el nodo 0."""
    # Construir grafo de sucesores
    succ: dict[int, list[int]] = {}
    for (i, j), v in arcos.items():
        for _ in range(v["camiones"]):
            succ.setdefault(i, []).append(j)

    rutas = []
    starts = succ.get(0, [])
    for nxt in list(starts):
        ruta = [0, nxt]
        succ[0].remove(nxt)
        cur = nxt
        while cur != 0:
            nexts = succ.get(cur, [])
            if not nexts:
                break
            nxt2 = nexts.pop(0)
            if nxt2 == 0:
                ruta.append(0)
                break
            ruta.append(nxt2)
            cur = nxt2
        if ruta[-1] != 0:
            ruta.append(0)
        rutas.append(ruta)
    return rutas


if __name__ == "__main__":
    print("Resolviendo CVRP Puntarenas…")
    res = resolver_cvrp()
    print(f"Status        : {res['status']}")
    print(f"Distancia total: {res['distancia_km']:.0f} km")
    print(f"Camiones usados: {res['n_camiones']}")
    print("\nArcos activos:")
    for (i, j), v in sorted(res["arcos"].items()):
        print(f"  {CANTONES[i]:20} → {CANTONES[j]:20}  {v['camiones']} camión(es)  {v['km']} km")
