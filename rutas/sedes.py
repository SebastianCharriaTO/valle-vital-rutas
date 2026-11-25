# -*- coding: utf-8 -*-
"""SelectorSede: consulta uno a varios. Entre las sedes con cupo para la especialidad,
elige la de menor tiempo de viaje desde el origen y devuelve la ruta."""
import time

from .estrategias import DijkstraMultidestino


class SinSedeDisponible(Exception):
    pass


class ResultadoSede(object):
    def __init__(self, sede, resultado, candidatas, modo, tiempo_ms, expandidos):
        self.sede = sede
        self.resultado = resultado
        self.candidatas = candidatas
        self.modo = modo
        self.tiempo_ms = tiempo_ms
        self.expandidos = expandidos
        self.aristas = resultado.aristas


class SelectorSede(object):
    MODOS = ("una_pasada", "por_sede")

    def __init__(self, grafo, sedes):
        self.grafo = grafo
        self.sedes = sedes
        for s in self.sedes:
            s["nodo"] = grafo.nodo_mas_cercano(s["lat"], s["lon"])

    def candidatas(self, especialidad):
        c = [s for s in self.sedes if s.get("especialidades", {}).get(especialidad)]
        if not c:
            raise SinSedeDisponible("No hay sede con cupo para %s" % especialidad)
        return c

    def mejor(self, origen, especialidad, modo="una_pasada", estrategia=None):
        """modo 'una_pasada': un Dijkstra que se detiene en la primera sede asentada.
        modo 'por_sede': la estrategia dada (A*, ALT...) una vez por cada sede candidata."""
        cands = self.candidatas(especialidad)
        t0 = time.perf_counter()
        if modo == "una_pasada":
            dm = DijkstraMultidestino([s["nodo"] for s in cands])
            r = dm.buscar(self.grafo, origen, None)
            sede = next(s for s in cands if s["nodo"] == dm.alcanzado) if r.encontrada else None
            expandidos = r.expandidos
        else:
            mejor_r, sede, expandidos = None, None, 0
            for s in cands:
                r = estrategia.buscar(self.grafo, origen, s["nodo"])
                expandidos += r.expandidos
                if r.encontrada and (mejor_r is None or r.costo_s < mejor_r.costo_s):
                    mejor_r, sede = r, s
            r = mejor_r
        ms = (time.perf_counter() - t0) * 1000.0
        if r is None or not r.encontrada:
            raise SinSedeDisponible("Ninguna sede alcanzable desde el nodo %s" % origen)
        return ResultadoSede(sede, r, [s["id"] for s in cands], modo, ms, expandidos)
