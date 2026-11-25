# -*- coding: utf-8 -*-
"""Estrategias de navegacion (patron Strategy) y su recorrido de expansion (patron Iterator).

Todas las estrategias comparten la interfaz EstrategiaRuta.buscar(grafo, origen, destino)
y devuelven un ResultadoBusqueda. El trabajo de cada algoritmo se expone como un
ExpansionIterator: recorre los nodos expandidos en orden, sin mostrar el monticulo ni las
estructuras internas. Asi se cuentan, se dibujan o se corta la busqueda desde afuera.
"""
import random
import time
from math import sqrt
from heapq import heappop, heappush
from collections import deque

from .grafo import INF


class ResultadoBusqueda(object):
    __slots__ = ("algoritmo", "origen", "destino", "costo_s", "aristas", "expandidos", "tiempo_ms",
                 "encontrada", "desde_cache", "orden_expansion")

    def __init__(self, algoritmo, origen, destino, costo_s, aristas, expandidos, tiempo_ms, encontrada,
                 orden_expansion=None):
        self.algoritmo = algoritmo
        self.origen = origen
        self.destino = destino
        self.costo_s = costo_s
        self.aristas = aristas
        self.expandidos = expandidos
        self.tiempo_ms = tiempo_ms
        self.encontrada = encontrada
        self.desde_cache = False
        self.orden_expansion = orden_expansion

    def nodos(self, grafo):
        if not self.aristas:
            return [self.origen]
        return [grafo.a_origen[self.aristas[0]]] + [grafo.a_destino[e] for e in self.aristas]

    def a_dict(self, grafo):
        return {
            "algoritmo": self.algoritmo,
            "origen": self.origen,
            "destino": self.destino,
            "encontrada": self.encontrada,
            "tiempo_viaje_min": round(self.costo_s / 60.0, 2) if self.encontrada else None,
            "distancia_km": round(sum(grafo.a_longitud[e] for e in self.aristas) / 1000.0, 2),
            "tramos": len(self.aristas),
            "nodos_expandidos": self.expandidos,
            "tiempo_consulta_ms": round(self.tiempo_ms, 3),
            "desde_cache": self.desde_cache,
        }


class ExpansionIterator(object):
    """Iterator sobre los nodos expandidos por una busqueda.

    Envuelve el generador del algoritmo. Al agotarse, deja en `resultado` lo que el
    generador devolvio (costo y aristas del camino) o None si no hay camino.
    """

    def __init__(self, generador):
        self._gen = generador
        self.resultado = None
        self.expandidos = 0
        self.terminado = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            nodo = next(self._gen)
        except StopIteration as fin:
            self.resultado = fin.value
            self.terminado = True
            raise
        self.expandidos += 1
        return nodo

    next = __next__


def _camino(grafo, pred, origen, destino):
    aristas = []
    v = destino
    while v != origen:
        e = pred[v]
        aristas.append(e)
        v = grafo.a_origen[e]
    aristas.reverse()
    return aristas


class EstrategiaRuta(object):
    """Interfaz Strategy. Las subclases implementan _expandir (un generador)."""

    nombre = "base"
    exacta = True   # garantiza la ruta de menor tiempo

    def expansion(self, grafo, origen, destino):
        return ExpansionIterator(self._expandir(grafo, origen, destino))

    def _expandir(self, grafo, origen, destino):  # pragma: no cover - interfaz
        raise NotImplementedError

    def buscar(self, grafo, origen, destino, registrar_orden=False):
        t0 = time.perf_counter()
        it = self.expansion(grafo, origen, destino)
        orden = [] if registrar_orden else None
        if registrar_orden:
            for nodo in it:
                orden.append(nodo)
        else:
            for _ in it:
                pass
        ms = (time.perf_counter() - t0) * 1000.0
        r = it.resultado
        if r is None:
            return ResultadoBusqueda(self.nombre, origen, destino, INF, [], it.expandidos, ms, False, orden)
        return ResultadoBusqueda(self.nombre, origen, destino, r[0], r[1], it.expandidos, ms, True, orden)


class BFS(EstrategiaRuta):
    """Busqueda en anchura: minimiza el numero de tramos, no el tiempo (linea base ingenua)."""

    nombre = "bfs"
    exacta = False

    def _expandir(self, g, s, t):
        pred = {s: None}
        cola = deque([s])
        sal, costo = g.sal, g.costo
        while cola:
            u = cola.popleft()
            yield u
            if u == t:
                aristas = _camino(g, pred, s, t)
                return (sum(costo[e] for e in aristas), aristas)
            for v, e in sal[u]:
                if v not in pred and costo[e] != INF:
                    pred[v] = e
                    cola.append(v)
        return None


class Dijkstra(EstrategiaRuta):
    """Dijkstra (1959), problema 2: camino minimo entre dos nodos; se detiene al asentar el destino."""

    nombre = "dijkstra"

    def _expandir(self, g, s, t):
        dist = {s: 0.0}
        pred = {}
        hecho = set()
        monticulo = [(0.0, s)]
        sal, costo = g.sal, g.costo
        while monticulo:
            d, u = heappop(monticulo)
            if u in hecho:
                continue
            hecho.add(u)
            yield u
            if u == t:
                return (d, _camino(g, pred, s, t))
            for v, e in sal[u]:
                c = costo[e]
                if c == INF:
                    continue
                nd = d + c
                if nd < dist.get(v, INF):
                    dist[v] = nd
                    pred[v] = e
                    heappush(monticulo, (nd, v))
        return None


class DijkstraMultidestino(EstrategiaRuta):
    """Una sola pasada de Dijkstra hacia un conjunto de destinos: el primero que se asienta
    es el mas cercano en tiempo. Se usa para elegir la sede (consulta uno a varios)."""

    nombre = "dijkstra_multidestino"

    def __init__(self, destinos=()):
        self.destinos = set(destinos)
        self.alcanzado = None

    def _expandir(self, g, s, t=None):
        destinos = self.destinos if t is None else {t}
        dist = {s: 0.0}
        pred = {}
        hecho = set()
        monticulo = [(0.0, s)]
        sal, costo = g.sal, g.costo
        while monticulo:
            d, u = heappop(monticulo)
            if u in hecho:
                continue
            hecho.add(u)
            yield u
            if u in destinos:
                self.alcanzado = u
                return (d, _camino(g, pred, s, u))
            for v, e in sal[u]:
                c = costo[e]
                if c == INF:
                    continue
                nd = d + c
                if nd < dist.get(v, INF):
                    dist[v] = nd
                    pred[v] = e
                    heappush(monticulo, (nd, v))
        return None


class DijkstraBidireccional(EstrategiaRuta):
    """Busca a la vez desde el origen (grafo directo) y desde el destino (grafo inverso)."""

    nombre = "bidireccional"

    def _expandir(self, g, s, t):
        if s == t:
            yield s
            return (0.0, [])
        costo = g.costo
        df, db = {s: 0.0}, {t: 0.0}
        pf, pb = {}, {}
        hf, hb = [(0.0, s)], [(0.0, t)]
        sf, sb = set(), set()
        mu, encuentro = INF, None
        while hf and hb:
            if hf[0][0] + hb[0][0] >= mu:
                break
            if hf[0][0] <= hb[0][0]:
                d, u = heappop(hf)
                if u in sf:
                    continue
                sf.add(u)
                yield u
                for v, e in g.sal[u]:
                    c = costo[e]
                    if c == INF:
                        continue
                    nd = d + c
                    if nd < df.get(v, INF):
                        df[v] = nd
                        pf[v] = e
                        heappush(hf, (nd, v))
                    if v in db and df[v] + db[v] < mu:
                        mu, encuentro = df[v] + db[v], v
            else:
                d, u = heappop(hb)
                if u in sb:
                    continue
                sb.add(u)
                yield u
                for v, e in g.ent[u]:          # arista e: v -> u
                    c = costo[e]
                    if c == INF:
                        continue
                    nd = d + c
                    if nd < db.get(v, INF):
                        db[v] = nd
                        pb[v] = e
                        heappush(hb, (nd, v))
                    if v in df and df[v] + db[v] < mu:
                        mu, encuentro = df[v] + db[v], v
        if encuentro is None:
            return None
        ida = _camino(g, pf, s, encuentro) if encuentro != s else []
        vuelta = []
        v = encuentro
        while v != t:
            e = pb[v]
            vuelta.append(e)
            v = g.a_destino[e]
        return (mu, ida + vuelta)


class AEstrella(EstrategiaRuta):
    """A* (Hart et al., 1968) con h(n) = distancia en linea recta / velocidad maxima del grafo.

    Es admisible: ningun tramo se recorre mas rapido que la velocidad maxima, asi que h nunca
    sobreestima el tiempo restante. El factor 0,99 cubre el error de la proyeccion plana.
    """

    nombre = "a_estrella"

    def __init__(self, grafo=None):
        self._vmax = grafo.velocidad_maxima_ms() if grafo is not None else None

    def heuristica(self, g, t):
        vmax = self._vmax or g.velocidad_maxima_ms()
        tx, ty = g.x[t], g.y[t]
        xs, ys = g.x, g.y
        k = 0.99 / vmax

        def h(v):
            dx = xs[v] - tx
            dy = ys[v] - ty
            return sqrt(dx * dx + dy * dy) * k
        return h

    def _expandir(self, g, s, t):
        h = self.heuristica(g, t)
        dist = {s: 0.0}
        pred = {}
        hecho = set()
        monticulo = [(h(s), 0.0, s)]
        sal, costo = g.sal, g.costo
        while monticulo:
            _, d, u = heappop(monticulo)
            if u in hecho:
                continue
            hecho.add(u)
            yield u
            if u == t:
                return (d, _camino(g, pred, s, t))
            for v, e in sal[u]:
                c = costo[e]
                if c == INF:
                    continue
                nd = d + c
                if nd < dist.get(v, INF):
                    dist[v] = nd
                    pred[v] = e
                    heappush(monticulo, (nd + h(v), nd, v))
        return None


def _dijkstra_completo(g, s, inverso=False, usar_base=True):
    """Distancias desde s a todos los nodos (o hacia s si inverso=True). Lista indexada por nodo."""
    dist = [INF] * g.n_nodos
    dist[s] = 0.0
    monticulo = [(0.0, s)]
    ady = g.ent if inverso else g.sal
    costo = g.costo_base if usar_base else g.costo
    while monticulo:
        d, u = heappop(monticulo)
        if d > dist[u]:
            continue
        for v, e in ady[u]:
            nd = d + costo[e]
            if nd < dist[v]:
                dist[v] = nd
                heappush(monticulo, (nd, v))
    return dist


class ALT(AEstrella):
    """A* con Landmarks y desigualdad Triangular (ALT).

    Preproceso: k landmarks elegidos por 'el mas lejano' (quedan en la periferia) y, para cada
    uno, las distancias desde y hacia todos los nodos (grafo dirigido) con los costos base.
    Cota: h(v) = max_L max(d(v,L) - d(t,L), d(L,t) - d(L,v)).
    Cerrar una via solo sube costos, asi que las cotas siguen siendo validas; reabrirla vuelve
    al costo base. Si algun costo bajara del base, hay que llamar a preprocesar() otra vez.
    """

    nombre = "alt"

    def __init__(self, grafo, k=8, semilla=7):
        AEstrella.__init__(self, grafo)
        self.k = k
        self.semilla = semilla
        self.grafo = grafo
        self.preprocesar()

    def preprocesar(self):
        g = self.grafo
        t0 = time.perf_counter()
        rnd = random.Random(self.semilla)
        inicio = rnd.randrange(g.n_nodos)
        d0 = _dijkstra_completo(g, inicio)
        primero = max(range(g.n_nodos), key=lambda v: d0[v] if d0[v] != INF else -1)
        self.landmarks = [primero]
        self.desde = [_dijkstra_completo(g, primero)]
        self.hacia = [_dijkstra_completo(g, primero, inverso=True)]
        minimo = [min(a, b) for a, b in zip(self.desde[0], self.hacia[0])]
        while len(self.landmarks) < self.k:
            nuevo = max(range(g.n_nodos), key=lambda v: minimo[v] if minimo[v] != INF else -1)
            self.landmarks.append(nuevo)
            dd = _dijkstra_completo(g, nuevo)
            dh = _dijkstra_completo(g, nuevo, inverso=True)
            self.desde.append(dd)
            self.hacia.append(dh)
            minimo = [min(m, a, b) for m, a, b in zip(minimo, dd, dh)]
        self.preproceso_s = time.perf_counter() - t0

    def heuristica(self, g, t):
        pares = [(dh, dh[t], dd, dd[t]) for dd, dh in zip(self.desde, self.hacia)]

        def h(v):
            mejor = 0.0
            for dh, dht, dd, ddt in pares:
                a = dh[v] - dht
                if a > mejor:
                    mejor = a
                b = ddt - dd[v]
                if b > mejor:
                    mejor = b
            return mejor
        return h


def crear_estrategias(grafo, k_landmarks=8):
    """Fabrica de las 5 estrategias comparadas (ALT preprocesa al crearse)."""
    return {
        "bfs": BFS(),
        "dijkstra": Dijkstra(),
        "bidireccional": DijkstraBidireccional(),
        "a_estrella": AEstrella(grafo),
        "alt": ALT(grafo, k=k_landmarks),
    }
