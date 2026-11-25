# -*- coding: utf-8 -*-
"""Descarga UNA VEZ la red vial de Cali-Jamundi desde OpenStreetMap y la guarda en
datos/grafo_cali.json (formato simple que lee rutas.repositorio.GrafoArchivoAdapter).

Requisitos (solo para este script): Python >= 3.11 y OSMnx >= 2.0
    python3.11 -m venv .venv-osm && . .venv-osm/bin/activate
    pip install -r requirements-descarga.txt
    python scripts/descargar_mapa_cali.py            # tarda 1-3 minutos
El motor, la API y los experimentos siguen funcionando en Python 3.8 con la biblioteca estandar.

Datos (c) OpenStreetMap contributors, licencia ODbL: https://www.openstreetmap.org/copyright
Uso puntual de la Overpass API: una sola descarga, sin ejecuciones en paralelo.
"""
import argparse
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "datos", "grafo_cali.json")
# (oeste, sur, este, norte) - Cali y Jamundi, aproximado
BBOX = (-76.60, 3.22, -76.46, 3.50)


def texto(valor):
    if isinstance(valor, (list, tuple)):
        return str(valor[0]) if valor else ""
    return "" if valor is None or valor != valor else str(valor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=SALIDA)
    ap.add_argument("--bbox", nargs=4, type=float, default=BBOX, metavar=("OESTE", "SUR", "ESTE", "NORTE"))
    a = ap.parse_args()
    if sys.version_info < (3, 11):
        sys.exit("Este script necesita Python >= 3.11 (OSMnx 2.x). El resto del proyecto corre en 3.8.")
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.log_console = True
    ox.settings.http_user_agent = "valle-vital-rutas/1.0 (prototipo academico)"
    t0 = time.time()
    G = ox.graph_from_bbox(tuple(a.bbox), network_type="drive", simplify=True)
    G = ox.truncate.largest_component(G, strongly=True)
    G = ox.routing.add_edge_speeds(G)          # imputa km/h por tipo de via cuando falta maxspeed
    G = ox.routing.add_edge_travel_times(G)

    ids = {}
    nodos = []
    for i, (nid, d) in enumerate(G.nodes(data=True)):
        ids[nid] = i
        nodos.append([i, round(float(d["y"]), 7), round(float(d["x"]), 7)])
    mejores = {}
    for u, v, k, d in G.edges(keys=True, data=True):   # aristas paralelas: se queda la mas rapida
        clave = (ids[u], ids[v])
        if clave not in mejores or d["travel_time"] < mejores[clave]["travel_time"]:
            mejores[clave] = d
    aristas = []
    for (u, v), d in mejores.items():
        via = "w%s" % texto(d.get("osmid")) if d.get("osmid") is not None else "e%d-%d" % (min(u, v), max(u, v))
        via = "%s:%d-%d" % (via, min(u, v), max(u, v))       # un tramo entre dos intersecciones
        aristas.append([u, v, round(float(d["length"]), 2), round(float(d["speed_kph"]), 1),
                        texto(d.get("highway")) or "via", texto(d.get("name")), via, 1.0])
    datos = {"meta": {"nombre": "Red vial Cali-Jamundi (OpenStreetMap)", "fuente": "osm",
                      "atribucion": "(c) OpenStreetMap contributors, ODbL", "bbox": list(a.bbox),
                      "descargado": time.strftime("%Y-%m-%d %H:%M"), "osmnx": ox.__version__},
             "nodos": nodos, "aristas": aristas}
    os.makedirs(os.path.dirname(a.salida), exist_ok=True)
    with open(a.salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    print("Guardado %s: %d nodos, %d aristas en %.0f s" % (a.salida, len(nodos), len(aristas), time.time() - t0))


if __name__ == "__main__":
    main()
