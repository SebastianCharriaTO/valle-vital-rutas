# -*- coding: utf-8 -*-
"""Grafo vial dirigido: nodos (intersecciones) y aristas (tramos con sentido).

El costo de cada arista es el tiempo de viaje en segundos:
    tiempo_s = longitud_m / (velocidad_kmh / 3.6) * factor_congestion
Cerrar una via pone el costo de sus aristas en infinito; reabrirla restaura el costo base.
Compatible con Python 3.8 (solo biblioteca estandar).
"""
import math

INF = float("inf")
RADIO_TIERRA_M = 6371008.8


class Grafo(object):
    """Listas de adyacencia en arreglos paralelos (rapido en Python puro).

    Los nodos se identifican con enteros 0..n-1. Cada arista tiene un indice entero `e`.
    """

    def __init__(self, nombre="grafo", fuente="sintetico"):
        self.nombre = nombre
        self.fuente = fuente
        self.lat = []
        self.lon = []
        self.x = []          # proyeccion equirectangular en metros
        self.y = []
        self.sal = []        # sal[u] = [(v, e), ...]
        self.ent = []        # ent[v] = [(u, e), ...] (grafo inverso, para bidireccional y ALT)
        self.a_origen = []
        self.a_destino = []
        self.a_longitud = []
        self.a_velocidad = []
        self.a_factor = []
        self.a_tipo = []
        self.a_nombre = []
        self.a_via = []
        self.costo_base = []
        self.costo = []
        self.vias = {}       # via_id -> [e, ...]
        self.cerradas = set()
        self._lat0 = None
        self.meta = {}

    # ------------------------------------------------------------------ construccion
    def agregar_nodo(self, lat, lon):
        if self._lat0 is None:
            self._lat0 = math.radians(lat)
        self.lat.append(lat)
        self.lon.append(lon)
        # redondeo a milimetros: evita diferencias de ultimo bit entre versiones de Python/libm
        self.x.append(round(RADIO_TIERRA_M * math.radians(lon) * math.cos(self._lat0), 3))
        self.y.append(round(RADIO_TIERRA_M * math.radians(lat), 3))
        self.sal.append([])
        self.ent.append([])
        return len(self.lat) - 1

    def agregar_arista(self, u, v, longitud_m, velocidad_kmh, tipo="local", nombre="", via=None, factor=1.0):
        e = len(self.a_origen)
        self.a_origen.append(u)
        self.a_destino.append(v)
        self.a_longitud.append(float(longitud_m))
        self.a_velocidad.append(float(velocidad_kmh))
        self.a_factor.append(float(factor))
        self.a_tipo.append(tipo)
        self.a_nombre.append(nombre)
        via = via if via is not None else "v%d" % e
        self.a_via.append(via)
        c = float(longitud_m) / (float(velocidad_kmh) / 3.6) * float(factor)
        self.costo_base.append(c)
        self.costo.append(c)
        self.sal[u].append((v, e))
        self.ent[v].append((u, e))
        self.vias.setdefault(via, []).append(e)
        return e

    # ------------------------------------------------------------------ consultas
    @property
    def n_nodos(self):
        return len(self.lat)

    @property
    def n_aristas(self):
        return len(self.a_origen)

    def distancia_recta_m(self, a, b):
        # math.sqrt es correctamente redondeada (IEEE 754); math.hypot cambio de precision en Python 3.10
        dx = self.x[a] - self.x[b]
        dy = self.y[a] - self.y[b]
        return math.sqrt(dx * dx + dy * dy)

    def velocidad_maxima_ms(self):
        """Velocidad maxima efectiva (m/s): cota para la heuristica admisible de A*."""
        return max(v / 3.6 / max(f, 1e-9) for v, f in zip(self.a_velocidad, self.a_factor))

    def nodo_mas_cercano(self, lat, lon):
        mejor, dmin = 0, INF
        for i in range(self.n_nodos):
            d = (self.lat[i] - lat) ** 2 + ((self.lon[i] - lon) * math.cos(self._lat0)) ** 2
            if d < dmin:
                mejor, dmin = i, d
        return mejor

    # ------------------------------------------------------------------ cambios en la red
    def cerrar_via(self, via):
        """Cierra todas las aristas de la via (ambos sentidos). Devuelve sus indices."""
        if via not in self.vias:
            raise KeyError("via inexistente: %s" % via)
        for e in self.vias[via]:
            self.costo[e] = INF
        self.cerradas.add(via)
        return list(self.vias[via])

    def reabrir_via(self, via):
        if via not in self.vias:
            raise KeyError("via inexistente: %s" % via)
        for e in self.vias[via]:
            self.costo[e] = self.costo_base[e]
        self.cerradas.discard(via)
        return list(self.vias[via])

    def resumen(self):
        return {
            "nombre": self.nombre,
            "fuente": self.fuente,
            "nodos": self.n_nodos,
            "aristas": self.n_aristas,
            "vias": len(self.vias),
            "vias_cerradas": sorted(self.cerradas),
        }
