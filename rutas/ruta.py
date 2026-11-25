# -*- coding: utf-8 -*-
"""Patron Composite para rutas: un Tramo (hoja) y una RutaCompuesta (nodo) responden igual.

Ejemplo: ruta de ambulancia = [base -> paciente] + [paciente -> sede], y cada subruta es una
secuencia de tramos. El cliente pide tiempo_s(), distancia_m() o instrucciones() sin saber
si tiene un tramo o una ruta completa.
"""


class ElementoRuta(object):
    def tiempo_s(self):  # pragma: no cover - interfaz
        raise NotImplementedError

    def distancia_m(self):  # pragma: no cover - interfaz
        raise NotImplementedError

    def tramos(self):
        """Iterator sobre las hojas (tramos) en orden de recorrido."""
        raise NotImplementedError  # pragma: no cover

    def __iter__(self):
        return iter(self.tramos())

    def instrucciones(self):
        """Agrupa tramos consecutivos de la misma via en una instruccion legible."""
        pasos = []
        for t in self.tramos():
            if pasos and pasos[-1]["via"] == t.nombre:
                pasos[-1]["distancia_m"] += t.distancia_m()
                pasos[-1]["tiempo_s"] += t.tiempo_s()
            else:
                pasos.append({"via": t.nombre, "distancia_m": t.distancia_m(), "tiempo_s": t.tiempo_s()})
        return ["Siga por %s %.0f m (%.1f min)" % (p["via"] or "via sin nombre", p["distancia_m"], p["tiempo_s"] / 60.0)
                for p in pasos]


class Tramo(ElementoRuta):
    """Hoja: una arista del grafo."""

    def __init__(self, grafo, e):
        self.e = e
        self.nombre = grafo.a_nombre[e]
        self.via = grafo.a_via[e]
        self._t = grafo.costo[e]
        self._d = grafo.a_longitud[e]

    def tiempo_s(self):
        return self._t

    def distancia_m(self):
        return self._d

    def tramos(self):
        return [self]


class RutaCompuesta(ElementoRuta):
    """Nodo: contiene tramos u otras rutas compuestas."""

    def __init__(self, nombre="ruta", hijos=None):
        self.nombre = nombre
        self.hijos = list(hijos or [])

    def agregar(self, elemento):
        self.hijos.append(elemento)
        return self

    def tiempo_s(self):
        return sum(h.tiempo_s() for h in self.hijos)

    def distancia_m(self):
        return sum(h.distancia_m() for h in self.hijos)

    def tramos(self):
        salida = []
        for h in self.hijos:
            salida.extend(h.tramos())
        return salida

    @classmethod
    def desde_resultado(cls, grafo, resultado, nombre="ruta"):
        return cls(nombre, [Tramo(grafo, e) for e in resultado.aristas])
