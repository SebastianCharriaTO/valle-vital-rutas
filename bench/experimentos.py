# -*- coding: utf-8 -*-
"""Experimentos E1-E6 del informe. Python 3.8+, solo biblioteca estandar.

    python -m bench.experimentos                       # ciudad sintetica (semilla 42)
    python -m bench.experimentos --grafo datos/grafo_cali.json   # grafo real de Cali

Escribe bench/resultados/*.csv y bench/resultados/resumen.json.
"""
import argparse
import csv
import json
import os
import platform
import random
import statistics
import sys
import threading
import time
import tracemalloc
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from rutas.api import crear_servidor  # noqa: E402
from rutas.estrategias import ALT  # noqa: E402
from rutas.repositorio import GrafoSinteticoAdapter, cargar_grafo  # noqa: E402
from rutas.servicio import ServicioRutas  # noqa: E402

SALIDA = os.path.join(RAIZ, "bench", "resultados")
ALGS = ["bfs", "dijkstra", "bidireccional", "a_estrella", "alt"]


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def mediana(xs):
    return statistics.median(xs)


def guardar_csv(nombre, filas):
    with open(os.path.join(SALIDA, nombre), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)


def entorno():
    cpu = platform.processor() or ""
    try:
        with open("/proc/cpuinfo") as f:
            for linea in f:
                if linea.startswith("model name"):
                    cpu = linea.split(":", 1)[1].strip()
                    break
    except IOError:
        pass
    return {"python": platform.python_version(), "so": platform.platform(), "cpu": cpu,
            "nucleos": os.cpu_count(), "fecha": time.strftime("%Y-%m-%d %H:%M")}


def pares(g, n, semilla=42):
    rnd = random.Random(semilla)
    salida = []
    while len(salida) < n:
        o, d = rnd.randrange(g.n_nodos), rnd.randrange(g.n_nodos)
        if o != d:
            salida.append((o, d))
    return salida


def medir(est, g, o, d, reps):
    tiempos, r = [], None
    for _ in range(reps):
        r = est.buscar(g, o, d)
        tiempos.append(r.tiempo_ms)
    return r, mediana(tiempos)


# ----------------------------------------------------------------------------- E1 y E2
def e1_e2(serv, n_pares, reps):
    g = serv.grafo
    filas = []
    for i, (o, d) in enumerate(pares(g, n_pares)):
        ref = None
        for a in ["dijkstra"] + [x for x in ALGS if x != "dijkstra"]:
            r, ms = medir(serv.estrategias[a], g, o, d, reps)
            if a == "dijkstra":
                ref = r.costo_s
            filas.append({"par": i, "origen": o, "destino": d, "algoritmo": a, "ms": round(ms, 4),
                          "expandidos": r.expandidos, "costo_s": round(r.costo_s, 3), "tramos": len(r.aristas),
                          "brecha": round(r.costo_s / ref - 1.0, 6)})
    guardar_csv("e1_algoritmos.csv", filas)
    res = {}
    med_dij = mediana([f["ms"] for f in filas if f["algoritmo"] == "dijkstra"])
    exp_dij = mediana([f["expandidos"] for f in filas if f["algoritmo"] == "dijkstra"])
    for a in ALGS:
        fa = [f for f in filas if f["algoritmo"] == a]
        res[a] = {"ms_mediana": round(mediana([f["ms"] for f in fa]), 3), "ms_p95": round(p95([f["ms"] for f in fa]), 3),
                  "expandidos_mediana": int(mediana([f["expandidos"] for f in fa])),
                  "expandidos_p95": int(p95([f["expandidos"] for f in fa])),
                  "brecha_media_pct": round(100 * statistics.mean([f["brecha"] for f in fa]), 3),
                  "rutas_optimas_pct": round(100.0 * sum(1 for f in fa if f["brecha"] < 1e-9) / len(fa), 1),
                  "aceleracion_vs_dijkstra": round(med_dij / mediana([f["ms"] for f in fa]), 2),
                  "reduccion_expandidos_vs_dijkstra": round(exp_dij / max(1, mediana([f["expandidos"] for f in fa])), 2)}
    bfs = [f for f in filas if f["algoritmo"] == "bfs"]
    dij = {f["par"]: f for f in filas if f["algoritmo"] == "dijkstra"}
    extra = [(f["costo_s"] - dij[f["par"]]["costo_s"]) / 60.0 for f in bfs]
    e2 = {"pares": len(bfs),
          "rutas_mas_lentas_pct": round(100.0 * sum(1 for f in bfs if f["brecha"] > 1e-9) / len(bfs), 1),
          "sobrecosto_medio_min": round(statistics.mean(extra), 2),
          "sobrecosto_max_min": round(max(extra), 2),
          "brecha_media_pct": round(100 * statistics.mean([f["brecha"] for f in bfs]), 1),
          "brecha_max_pct": round(100 * max(f["brecha"] for f in bfs), 1),
          "viaje_medio_dijkstra_min": round(statistics.mean([f["costo_s"] for f in dij.values()]) / 60.0, 2),
          "tramos_medios_bfs": round(statistics.mean([f["tramos"] for f in bfs]), 1),
          "tramos_medios_dijkstra": round(statistics.mean([f["tramos"] for f in dij.values()]), 1)}
    return res, e2


# ----------------------------------------------------------------------------- E3
def e3(serv, n, reps):
    g = serv.grafo
    sel = serv.selector
    origenes = [o for o, _ in pares(g, n, 7)]
    filas = []
    variantes = [("una_pasada", None)] + [("por_sede", a) for a in ("dijkstra", "bidireccional", "a_estrella", "alt")]
    for i, o in enumerate(origenes):
        ref = None
        for modo, a in variantes:
            tiempos = []
            for _ in range(reps):
                rs = sel.mejor(o, "Medicina general", modo, serv.estrategias[a] if a else None)
                tiempos.append(rs.tiempo_ms)
            if ref is None:
                ref = rs.sede["id"]
            filas.append({"origen": o, "variante": modo if a is None else "3 x " + a, "ms": round(mediana(tiempos), 4),
                          "expandidos": rs.expandidos, "sede": rs.sede["id"], "misma_sede": int(rs.sede["id"] == ref)})
    guardar_csv("e3_uno_a_varios.csv", filas)
    res = {}
    for v in sorted({f["variante"] for f in filas}, key=lambda x: [f["variante"] for f in filas].index(x)):
        fv = [f for f in filas if f["variante"] == v]
        res[v] = {"ms_mediana": round(mediana([f["ms"] for f in fv]), 3), "ms_p95": round(p95([f["ms"] for f in fv]), 3),
                  "expandidos_mediana": int(mediana([f["expandidos"] for f in fv])),
                  "coincide_sede_pct": round(100.0 * sum(f["misma_sede"] for f in fv) / len(fv), 1)}
    reparto = {}
    for f in filas:
        if f["variante"] == "una_pasada":
            reparto[f["sede"]] = reparto.get(f["sede"], 0) + 1
    return {"origenes": len(origenes), "variantes": res, "sedes_elegidas": reparto}


# ----------------------------------------------------------------------------- E4
def zipf(rnd, n, s):
    pesos = [1.0 / (k ** s) for k in range(1, n + 1)]
    return rnd.choices(range(n), weights=pesos)[0]


def e4(g, n_consultas=1000, s=1.1):
    rnd = random.Random(11)
    claves_p = sorted(ServicioRutas(g).puntos)
    carga = [(claves_p[zipf(rnd, len(claves_p), s)], "S%d" % rnd.randint(1, 3)) for _ in range(n_consultas)]

    def correr(serv, usar_cache):
        lat, ac, lat_ac, lat_fa = [], 0, [], []
        for o, d in carga:
            t0 = time.perf_counter()
            r = serv.ruta(o, d, "alt", usar_cache=usar_cache)
            ms = (time.perf_counter() - t0) * 1000.0
            lat.append(ms)
            ac += int(r.desde_cache)
            (lat_ac if r.desde_cache else lat_fa).append(ms)
        correr.ac, correr.fa = lat_ac, lat_fa
        return lat, ac

    sin = ServicioRutas(g)
    lat_sin, _ = correr(sin, False)
    con = ServicioRutas(g)
    lat_con, ac = correr(con, True)
    filas = [{"consulta": i, "origen": c[0], "sede": c[1], "ms_sin_cache": round(a, 4), "ms_con_cache": round(b, 4)}
             for i, (c, a, b) in enumerate(zip(carga, lat_sin, lat_con))]
    guardar_csv("e4_cache.csv", filas)
    res = {"consultas": n_consultas, "zipf_s": s, "puntos_origen": len(claves_p), "claves_posibles": len(claves_p) * 3,
           "tasa_aciertos_pct": round(100.0 * ac / n_consultas, 1),
           "sin_cache_ms_mediana": round(mediana(lat_sin), 3), "sin_cache_ms_p95": round(p95(lat_sin), 3),
           "con_cache_ms_mediana": round(mediana(lat_con), 4), "con_cache_ms_p95": round(p95(lat_con), 3),
           "sin_cache_total_s": round(sum(lat_sin) / 1000.0, 3), "con_cache_total_s": round(sum(lat_con) / 1000.0, 3)}
    res["acierto_ms_mediana"] = round(mediana(correr.ac), 4) if correr.ac else None
    res["fallo_ms_mediana"] = round(mediana(correr.fa), 3) if correr.fa else None

    # cierre de via: con y sin Observer
    def escenario(con_observer):
        serv = ServicioRutas(g, con_observer=con_observer)
        for o, d in carga[:300]:
            serv.ruta(o, d, "alt")
        conteo = {}
        for clave, item in serv.proxies["alt"]._datos.items():
            for via in {g.a_via[e] for e in item[2]}:
                conteo[via] = conteo.get(via, 0) + 1
        via = max(sorted(conteo), key=lambda v: conteo[v])
        entradas = len(serv.proxies["alt"]._datos)
        activas = 0
        for i, (clave, item) in enumerate(list(serv.proxies["alt"]._datos.items())[:20]):
            serv.rutas_activas.registrar("amb-%02d" % i, item[1])
            activas += 1
        t0 = time.perf_counter()
        serv.cerrar_via(via, "accidente simulado")
        ms_cierre = (time.perf_counter() - t0) * 1000.0
        cerradas = set(g.vias[via])
        obsoletas, aciertos = 0, 0
        for o, d in carga[300:400]:
            r = serv.ruta(o, d, "alt")
            aciertos += int(r.desde_cache)
            obsoletas += int(bool(cerradas & set(r.aristas)))
        recalc = serv.rutas_activas.recalculos
        salida = {"via_cerrada": via, "entradas_que_la_usaban": conteo[via],
                  "entradas_en_cache": entradas,
                  "invalidadas": serv.proxies["alt"].invalidadas, "ms_comando_cierre": round(ms_cierre, 2),
                  "rutas_activas": activas, "rutas_activas_recalculadas": len(recalc),
                  "recalculo_ms_medio": round(statistics.mean([x["ms"] for x in recalc]), 2) if recalc else 0,
                  "demora_media_min": round(statistics.mean([x["despues_min"] - x["antes_min"] for x in recalc]), 2) if recalc else 0,
                  "consultas_despues": 100, "aciertos_despues": aciertos, "rutas_obsoletas_servidas": obsoletas}
        serv.deshacer()
        return salida

    res["cierre_con_observer"] = escenario(True)
    res["cierre_sin_observer"] = escenario(False)
    return res


# ----------------------------------------------------------------------------- E5
def e5(tamanos, n_pares, reps):
    filas, prep = [], []
    for n in tamanos:
        t0 = time.perf_counter()
        g = GrafoSinteticoAdapter(n, 42).obtener()
        t_carga = time.perf_counter() - t0
        tracemalloc.start()
        alt = ALT(g, k=8)
        _, pico = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        serv = ServicioRutas(g)
        serv.estrategias["alt"] = alt
        prep.append({"nodos": g.n_nodos, "aristas": g.n_aristas, "carga_s": round(t_carga, 3),
                     "alt_preproceso_s": round(alt.preproceso_s, 3), "alt_memoria_mb": round(pico / 1e6, 2)})
        for o, d in pares(g, n_pares, 3):
            for a in ("dijkstra", "bidireccional", "a_estrella", "alt"):
                r, ms = medir(serv.estrategias[a], g, o, d, reps)
                filas.append({"nodos": g.n_nodos, "algoritmo": a, "ms": round(ms, 4), "expandidos": r.expandidos})
    guardar_csv("e5_escala.csv", filas)
    res = {"pares": n_pares, "preproceso": prep, "consulta": []}
    for p in prep:
        for a in ("dijkstra", "bidireccional", "a_estrella", "alt"):
            fa = [f for f in filas if f["nodos"] == p["nodos"] and f["algoritmo"] == a]
            res["consulta"].append({"nodos": p["nodos"], "algoritmo": a, "ms_mediana": round(mediana([f["ms"] for f in fa]), 3),
                                    "ms_p95": round(p95([f["ms"] for f in fa]), 3),
                                    "expandidos_mediana": int(mediana([f["expandidos"] for f in fa]))})
    return res


# ----------------------------------------------------------------------------- E6
def e6(g, hilos=8, n=400):
    rnd = random.Random(5)
    salida = {}
    for usar_cache in (True, False):
        serv = ServicioRutas(g)
        srv = crear_servidor(serv, 0)
        puerto = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        claves = sorted(serv.puntos)
        carga = [claves[zipf(rnd, len(claves), 1.1)] for _ in range(n)]
        lat, lock = [], threading.Lock()
        errores = [0]

        def cliente(trozo):
            for o in trozo:
                cuerpo = json.dumps({"origen": o, "especialidad": "Medicina general", "cache": usar_cache}).encode()
                req = urllib.request.Request("http://127.0.0.1:%d/api/sedes/mejor" % puerto, cuerpo,
                                             {"Content-Type": "application/json"})
                t0 = time.perf_counter()
                try:
                    urllib.request.urlopen(req, timeout=30).read()
                    with lock:
                        lat.append((time.perf_counter() - t0) * 1000.0)
                except Exception:
                    with lock:
                        errores[0] += 1
        trozos = [carga[i::hilos] for i in range(hilos)]
        t0 = time.perf_counter()
        ths = [threading.Thread(target=cliente, args=(t,)) for t in trozos]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        dur = time.perf_counter() - t0
        srv.shutdown()
        srv.server_close()
        salida["con_cache" if usar_cache else "sin_cache"] = {
            "solicitudes": n, "clientes": hilos, "errores": errores[0], "req_s": round(len(lat) / dur, 1),
            "p50_ms": round(mediana(lat), 2), "p95_ms": round(p95(lat), 2)}
    return salida


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--grafo", default=None, help="JSON del grafo real; si no existe, ciudad sintetica")
    ap.add_argument("--nodos", type=int, default=10000)
    ap.add_argument("--pares", type=int, default=200)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args(argv)
    if a.rapido:
        a.pares, a.reps = 30, 2
    os.makedirs(SALIDA, exist_ok=True)
    t0 = time.time()
    g = cargar_grafo(a.grafo, a.nodos)
    serv = ServicioRutas(g)
    print("Grafo:", g.nombre, g.n_nodos, "nodos", g.n_aristas, "aristas")
    R = {"entorno": entorno(), "grafo": dict(g.resumen(), meta=g.meta),
         "metodo": {"pares": a.pares, "repeticiones": a.reps, "semilla_pares": 42,
                    "alt_landmarks": len(serv.estrategias["alt"].landmarks),
                    "alt_preproceso_s": round(serv.estrategias["alt"].preproceso_s, 3)}}
    print("E1/E2 ..."); R["e1"], R["e2"] = e1_e2(serv, a.pares, a.reps)
    print("E3 ..."); R["e3"] = e3(serv, a.pares, a.reps)
    print("E4 ..."); R["e4"] = e4(g)
    print("E5 ..."); R["e5"] = e5([2500, 10000, 40000] if not a.rapido else [2500, 10000], 50 if not a.rapido else 10, 3 if not a.rapido else 1)
    print("E6 ..."); R["e6"] = e6(g)
    R["duracion_s"] = round(time.time() - t0, 1)
    with open(os.path.join(SALIDA, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: R[k] for k in ("e1", "e2")}, ensure_ascii=False, indent=1))
    print("Listo en %.1f s -> %s" % (R["duracion_s"], SALIDA))


if __name__ == "__main__":
    main()
