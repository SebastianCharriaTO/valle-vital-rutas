# -*- coding: utf-8 -*-
"""Puertos y adaptadores para obtener el grafo vial.

- GrafoSinteticoAdapter: ciudad sintetica reproducible (semilla fija), con la misma
  extension geografica que Cali-Jamundi. Sirve para pruebas y mediciones.
- GrafoArchivoAdapter: lee el grafo real exportado por scripts/descargar_mapa_cali.py
  (formato JSON simple, biblioteca estandar).
- cargar_grafo(): usa el archivo si existe y, si no, la ciudad sintetica.
"""
import json
import math
import os
import random
from collections import deque

from .grafo import Grafo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVO_CALI = os.path.join(RAIZ, "datos", "grafo_cali.json")
ARCHIVO_SEDES = os.path.join(RAIZ, "datos", "sedes.json")

# Extension aproximada Cali-Jamundi (lat 3.22-3.50, lon -76.60 a -76.46)
BBOX = {"sur": 3.22, "norte": 3.50, "oeste": -76.60, "este": -76.46}


class RepositorioGrafo(object):
    """Puerto: cualquier fuente de grafo vial."""

    def obtener(self):  # pragma: no cover - interfaz
        raise NotImplementedError


class GrafoSinteticoAdapter(RepositorioGrafo):
    """Rejilla con jerarquia de vias, sentidos unicos, una autopista diagonal y un rio.

    - Arterias cada ~2,2 km (60 km/h, doble sentido), colectoras a mitad (40 km/h),
      locales (25 km/h, sentido unico alterno). Autopista diagonal a 80 km/h.
    - Un rio cruza la ciudad de oeste a este: solo lo atraviesan arterias y autopista.
    - Factor de congestion simulado por tramo (hora pico), con semilla fija.
    - Se quita el 6 % de las cuadras locales y se conserva la componente fuertemente conexa.
    """

    def __init__(self, nodos=10000, semilla=42):
        self.nodos = nodos
        self.semilla = semilla

    def obtener(self):
        rnd = random.Random(self.semilla)
        filas = int(round(math.sqrt(self.nodos * 2.0)))
        cols = int(round(self.nodos / float(filas)))
        dlat = (BBOX["norte"] - BBOX["sur"]) / (filas - 1)
        dlon = (BBOX["este"] - BBOX["oeste"]) / (cols - 1)
        paso_m = dlat * 111195.0
        k = max(2, int(round(2200.0 / paso_m)))          # arterias cada ~2,2 km
        kc = max(1, k // 2)
        fila_rio = int(round(0.35 * (filas - 1)))

        tmp = Grafo("sintetico-%d" % self.nodos, "sintetico")
        idx = {}
        for r in range(filas):
            for c in range(cols):
                jl = rnd.uniform(-0.15, 0.15) * dlat
                jo = rnd.uniform(-0.15, 0.15) * dlon
                idx[(r, c)] = tmp.agregar_nodo(BBOX["sur"] + r * dlat + jl, BBOX["oeste"] + c * dlon + jo)

        def clase(i):
            if i % k == 0:
                return "arteria", 60.0, (1.1, 1.9)
            if i % kc == 0:
                return "colectora", 40.0, (1.0, 1.5)
            return "local", 25.0, (1.0, 1.3)

        aristas = []  # (u, v, vel, tipo, nombre, via, factor, doble)
        for r in range(filas):
            tipo, vel, rf = clase(r)
            for c in range(cols - 1):
                if tipo == "local" and rnd.random() < 0.06:
                    continue
                u, v = idx[(r, c)], idx[(r, c + 1)]
                nombre = ("Av. Calle %d" if tipo == "arteria" else "Calle %d") % r
                via = "C%d.%d" % (r, c)
                f = rnd.uniform(*rf)
                if tipo == "local":
                    if r % 2 == 0:
                        aristas.append((u, v, vel, tipo, nombre, via, f))
                    else:
                        aristas.append((v, u, vel, tipo, nombre, via, f))
                else:
                    aristas.append((u, v, vel, tipo, nombre, via, f))
                    aristas.append((v, u, vel, tipo, nombre, via, f))
        for c in range(cols):
            tipo, vel, rf = clase(c)
            for r in range(filas - 1):
                if r == fila_rio and tipo != "arteria":
                    continue  # el rio solo se cruza por puentes de arterias
                if tipo == "local" and rnd.random() < 0.06:
                    continue
                u, v = idx[(r, c)], idx[(r + 1, c)]
                nombre = ("Av. Carrera %d" if tipo == "arteria" else "Carrera %d") % c
                via = "K%d.%d" % (c, r)
                f = rnd.uniform(*rf)
                if tipo == "local":
                    if c % 2 == 0:
                        aristas.append((u, v, vel, tipo, nombre, via, f))
                    else:
                        aristas.append((v, u, vel, tipo, nombre, via, f))
                else:
                    aristas.append((u, v, vel, tipo, nombre, via, f))
                    aristas.append((v, u, vel, tipo, nombre, via, f))
        # autopista diagonal (de sur-occidente a nororiente)
        prev = None
        for r in range(filas):
            c = int(round(0.2 * (cols - 1) + 0.4 * (cols - 1) * r / (filas - 1)))
            cur = idx[(r, c)]
            if prev is not None and prev != cur:
                f = rnd.uniform(1.0, 1.6)
                via = "A%d" % r
                aristas.append((prev, cur, 80.0, "autopista", "Autopista diagonal", via, f))
                aristas.append((cur, prev, 80.0, "autopista", "Autopista diagonal", via, f))
            prev = cur

        for (u, v, vel, tipo, nombre, via, f) in aristas:
            tmp.agregar_arista(u, v, round(tmp.distancia_recta_m(u, v), 2), vel, tipo, nombre, via, round(f, 4))

        g = _componente_fuerte(tmp, idx[(filas // 2, cols // 2)])
        g.nombre = "Ciudad sintetica (%d nodos, semilla %d)" % (g.n_nodos, self.semilla)
        g.meta = {"filas": filas, "columnas": cols, "paso_m": round(paso_m, 1), "semilla": self.semilla,
                  "fila_rio": fila_rio, "arterias_cada": k}
        return g


def _componente_fuerte(g, centro):
    """Subgrafo de los nodos alcanzables desde y hacia `centro` (su componente fuertemente conexa)."""
    def alcanzables(ady):
        vis = {centro}
        cola = deque([centro])
        while cola:
            u = cola.popleft()
            for v, _ in ady[u]:
                if v not in vis:
                    vis.add(v)
                    cola.append(v)
        return vis
    keep = alcanzables(g.sal) & alcanzables(g.ent)
    nuevo = Grafo(g.nombre, g.fuente)
    mapa = {}
    for i in range(g.n_nodos):
        if i in keep:
            mapa[i] = nuevo.agregar_nodo(g.lat[i], g.lon[i])
    for e in range(g.n_aristas):
        u, v = g.a_origen[e], g.a_destino[e]
        if u in mapa and v in mapa:
            nuevo.agregar_arista(mapa[u], mapa[v], g.a_longitud[e], g.a_velocidad[e], g.a_tipo[e],
                                 g.a_nombre[e], g.a_via[e], g.a_factor[e])
    return nuevo


class GrafoArchivoAdapter(RepositorioGrafo):
    """Lee un grafo en formato JSON simple:

    {"meta": {...}, "nodos": [[id, lat, lon], ...],
     "aristas": [[u, v, longitud_m, velocidad_kmh, tipo, nombre, via], ...]}
    """

    def __init__(self, ruta=ARCHIVO_CALI):
        self.ruta = ruta

    def obtener(self):
        with open(self.ruta, encoding="utf-8") as f:
            datos = json.load(f)
        meta = datos.get("meta", {})
        g = Grafo(meta.get("nombre", os.path.basename(self.ruta)), meta.get("fuente", "archivo"))
        mapa = {}
        for nid, lat, lon in datos["nodos"]:
            mapa[nid] = g.agregar_nodo(float(lat), float(lon))
        for fila in datos["aristas"]:
            u, v, lon_m, vel = fila[0], fila[1], fila[2], fila[3]
            tipo = fila[4] if len(fila) > 4 else "via"
            nombre = fila[5] if len(fila) > 5 else ""
            via = fila[6] if len(fila) > 6 else None
            factor = fila[7] if len(fila) > 7 else 1.0
            if u in mapa and v in mapa and float(vel) > 0:
                g.agregar_arista(mapa[u], mapa[v], max(float(lon_m), 0.1), float(vel), tipo, nombre or "",
                                 str(via) if via is not None else None, factor)
        g.meta = meta
        return g


def guardar_json(g, ruta):
    """Exporta un Grafo al formato de GrafoArchivoAdapter (util para pruebas)."""
    datos = {
        "meta": {"nombre": g.nombre, "fuente": g.fuente},
        "nodos": [[i, g.lat[i], g.lon[i]] for i in range(g.n_nodos)],
        "aristas": [[g.a_origen[e], g.a_destino[e], round(g.a_longitud[e], 2), g.a_velocidad[e], g.a_tipo[e],
                     g.a_nombre[e], g.a_via[e], g.a_factor[e]] for e in range(g.n_aristas)],
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)


def cargar_grafo(ruta=None, nodos=10000, semilla=42):
    """Grafo real si existe datos/grafo_cali.json (o la ruta dada); si no, ciudad sintetica."""
    ruta = ruta or ARCHIVO_CALI
    if os.path.exists(ruta):
        return GrafoArchivoAdapter(ruta).obtener()
    return GrafoSinteticoAdapter(nodos, semilla).obtener()


def cargar_sedes(ruta=ARCHIVO_SEDES):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)
