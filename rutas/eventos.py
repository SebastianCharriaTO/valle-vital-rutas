# -*- coding: utf-8 -*-
"""Patron Observer: el bus publica los cambios de la red vial y los observadores reaccionan.

El Grafo no conoce la cache ni las rutas activas: solo el bus los conoce como ObservadorVial.
"""
import threading
import time


class ObservadorVial(object):
    def notificar(self, evento, datos):  # pragma: no cover - interfaz
        raise NotImplementedError


class BusEventosViales(object):
    """Sujeto. Notifica en el orden de suscripcion (primero la cache, luego las rutas activas)."""

    def __init__(self):
        self._obs = []
        self.historial = []
        self._lock = threading.Lock()

    def suscribir(self, observador):
        self._obs.append(observador)

    def desuscribir(self, observador):
        self._obs.remove(observador)

    def publicar(self, evento, datos):
        with self._lock:
            self.historial.append({"t": time.time(), "evento": evento, "via": datos.get("via")})
            for o in list(self._obs):
                o.notificar(evento, datos)


class RutasActivas(ObservadorVial):
    """Rutas en curso (por ejemplo, una ambulancia en camino). Si se cierra una via que usan,
    se recalculan con la estrategia indicada y se deja registro del cambio."""

    def __init__(self, grafo, estrategia):
        self.grafo = grafo
        self.estrategia = estrategia
        self.rutas = {}            # id -> ResultadoBusqueda
        self.recalculos = []
        self._lock = threading.Lock()

    def registrar(self, rid, resultado):
        with self._lock:
            self.rutas[rid] = resultado

    def notificar(self, evento, datos):
        if evento != "via.cerrada":
            return
        aristas = set(datos.get("aristas", []))
        with self._lock:
            for rid, r in list(self.rutas.items()):
                if aristas.intersection(r.aristas):
                    t0 = time.perf_counter()
                    nueva = self.estrategia.buscar(self.grafo, r.origen, r.destino)
                    self.rutas[rid] = nueva
                    self.recalculos.append({
                        "ruta": rid, "via": datos.get("via"),
                        "antes_min": round(r.costo_s / 60.0, 2),
                        "despues_min": round(nueva.costo_s / 60.0, 2) if nueva.encontrada else None,
                        "ms": round((time.perf_counter() - t0) * 1000.0, 2),
                    })
