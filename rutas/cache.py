# -*- coding: utf-8 -*-
"""RutaCacheProxy: patron Proxy (proxy de cache) con la politica Cache-Aside.

- Ofrece la misma interfaz que EstrategiaRuta (buscar), asi que el cliente no nota si hay cache.
- Cache-Aside: en un fallo calcula con la estrategia real y guarda; en un acierto devuelve lo guardado.
- Expiracion por TTL y desalojo LRU por capacidad.
- Consistencia: es ObservadorVial. Al cerrarse una via invalida SOLO las entradas cuya ruta
  usa esa via (indice via -> claves). Al reabrirse una via se vacia la cache entera, porque la
  via reabierta puede mejorar rutas que hoy no la usan.
"""
import threading
import time
from collections import OrderedDict

from .estrategias import EstrategiaRuta, ResultadoBusqueda
from .eventos import ObservadorVial


class RutaCacheProxy(EstrategiaRuta, ObservadorVial):

    def __init__(self, estrategia, grafo, capacidad=5000, ttl_s=300.0, reloj=time.monotonic):
        self.real = estrategia
        self.grafo = grafo
        self.nombre = estrategia.nombre
        self.exacta = estrategia.exacta
        self.capacidad = capacidad
        self.ttl_s = ttl_s
        self.reloj = reloj
        self._datos = OrderedDict()   # clave -> (vence, valor, aristas)
        self._por_via = {}            # via -> set(claves)
        self._lock = threading.RLock()
        self.aciertos = 0
        self.fallos = 0
        self.invalidadas = 0

    # ---------------------------------------------------------------- Cache-Aside genérico
    def obtener(self, clave, calcular, aristas_de=lambda r: r.aristas):
        with self._lock:
            item = self._datos.get(clave)
            if item is not None and item[0] > self.reloj():
                self._datos.move_to_end(clave)
                self.aciertos += 1
                return item[1], True
            if item is not None:
                self._quitar(clave)
        valor = calcular()
        with self._lock:
            self.fallos += 1
            aristas = aristas_de(valor)
            self._datos[clave] = (self.reloj() + self.ttl_s, valor, aristas)
            for via in {self.grafo.a_via[e] for e in aristas}:
                self._por_via.setdefault(via, set()).add(clave)
            while len(self._datos) > self.capacidad:
                viejo = next(iter(self._datos))
                self._quitar(viejo)
        return valor, False

    def _quitar(self, clave):
        item = self._datos.pop(clave, None)
        if item is None:
            return
        for via in {self.grafo.a_via[e] for e in item[2]}:
            s = self._por_via.get(via)
            if s is not None:
                s.discard(clave)

    # ---------------------------------------------------------------- Proxy de EstrategiaRuta
    def buscar(self, grafo, origen, destino, registrar_orden=False):
        if registrar_orden:   # la vista que dibuja la expansion siempre calcula
            return self.real.buscar(grafo, origen, destino, True)
        t0 = time.perf_counter()
        valor, acierto = self.obtener(("ruta", self.real.nombre, origen, destino),
                                      lambda: self.real.buscar(grafo, origen, destino))
        if not acierto:
            return valor
        copia = ResultadoBusqueda(valor.algoritmo, origen, destino, valor.costo_s, valor.aristas, 0,
                                  (time.perf_counter() - t0) * 1000.0, valor.encontrada)
        copia.desde_cache = True
        return copia

    # ---------------------------------------------------------------- Observer
    def notificar(self, evento, datos):
        with self._lock:
            if evento == "via.cerrada":
                claves = list(self._por_via.get(datos["via"], ()))
                for c in claves:
                    self._quitar(c)
                self.invalidadas += len(claves)
            elif evento == "via.reabierta":
                self.invalidadas += len(self._datos)
                self._datos.clear()
                self._por_via.clear()

    def vaciar(self):
        with self._lock:
            self._datos.clear()
            self._por_via.clear()

    def estadisticas(self):
        total = self.aciertos + self.fallos
        return {"entradas": len(self._datos), "aciertos": self.aciertos, "fallos": self.fallos,
                "tasa_aciertos": round(self.aciertos / float(total), 4) if total else 0.0,
                "invalidadas": self.invalidadas, "ttl_s": self.ttl_s, "capacidad": self.capacidad}
