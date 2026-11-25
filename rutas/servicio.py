# -*- coding: utf-8 -*-
"""ServicioRutas: arma los componentes (grafo, estrategias, cache, bus, comandos, selector)
y ofrece las operaciones que usan la API, la vista y los experimentos."""
import copy
import random
import time

from .cache import RutaCacheProxy
from .comandos import CalcularRutaCmd, CerrarViaCmd, InvocadorComandos, ReabrirViaCmd
from .estrategias import crear_estrategias
from .eventos import BusEventosViales, RutasActivas
from .repositorio import cargar_grafo, cargar_sedes
from .ruta import RutaCompuesta
from .sedes import SelectorSede


class ServicioRutas(object):
    def __init__(self, grafo=None, sedes=None, algoritmo_defecto="alt", ttl_s=300.0, k_landmarks=8,
                 con_observer=True):
        self.grafo = grafo if grafo is not None else cargar_grafo()
        datos_sedes = sedes if sedes is not None else cargar_sedes()
        self.datos_sedes = copy.deepcopy(datos_sedes)
        self.estrategias = crear_estrategias(self.grafo, k_landmarks)
        self.bus = BusEventosViales()
        self.proxies = {}
        for nombre, e in self.estrategias.items():
            p = RutaCacheProxy(e, self.grafo, ttl_s=ttl_s)
            self.proxies[nombre] = p
            if con_observer:
                self.bus.suscribir(p)
        self.algoritmo_defecto = algoritmo_defecto
        self.rutas_activas = RutasActivas(self.grafo, self.estrategias[algoritmo_defecto])
        self.bus.suscribir(self.rutas_activas)
        self.invocador = InvocadorComandos()
        self.selector = SelectorSede(self.grafo, self.datos_sedes["sedes"])
        self.bases = self.datos_sedes.get("bases", [])
        for b in self.bases:
            b["nodo"] = self.grafo.nodo_mas_cercano(b["lat"], b["lon"])
        rnd = random.Random(2026)
        self.puntos = {"P%02d" % (i + 1): rnd.randrange(self.grafo.n_nodos) for i in range(50)}

    # ------------------------------------------------------------------ utilidades
    def resolver_nodo(self, valor):
        """Acepta id de nodo, P01..P50, S1..S3, B1 o 'lat,lon'."""
        if isinstance(valor, int):
            return valor
        v = str(valor).strip()
        if v in self.puntos:
            return self.puntos[v]
        for s in self.selector.sedes:
            if s["id"] == v:
                return s["nodo"]
        for b in self.bases:
            if b["id"] == v:
                return b["nodo"]
        if "," in v:
            lat, lon = [float(x) for x in v.split(",")]
            return self.grafo.nodo_mas_cercano(lat, lon)
        n = int(v)
        if not 0 <= n < self.grafo.n_nodos:
            raise ValueError("nodo fuera de rango")
        return n

    def _estrategia(self, algoritmo, usar_cache):
        algoritmo = algoritmo or self.algoritmo_defecto
        if algoritmo not in self.estrategias:
            raise ValueError("algoritmo desconocido: %s" % algoritmo)
        return self.proxies[algoritmo] if usar_cache else self.estrategias[algoritmo]

    # ------------------------------------------------------------------ operaciones
    def ruta(self, origen, destino, algoritmo=None, usar_cache=True, registrar_orden=False):
        est = self._estrategia(algoritmo, usar_cache)
        cmd = CalcularRutaCmd(est, self.grafo, self.resolver_nodo(origen), self.resolver_nodo(destino))
        if registrar_orden:
            return est.buscar(self.grafo, cmd.origen, cmd.destino, registrar_orden=True)
        return self.invocador.ejecutar(cmd)

    def mejor_sede(self, origen, especialidad, modo="una_pasada", algoritmo=None, usar_cache=True):
        o = self.resolver_nodo(origen)
        alg = algoritmo or self.algoritmo_defecto
        calcular = lambda: self.selector.mejor(o, especialidad, modo, self.estrategias[alg])
        if not usar_cache:
            return calcular(), False
        return self.proxies[alg].obtener(("sede", modo, alg, o, especialidad), calcular)

    def ruta_ambulancia(self, base, paciente, especialidad, algoritmo=None):
        """Composite: base -> paciente -> sede."""
        b, p = self.resolver_nodo(base), self.resolver_nodo(paciente)
        tramo1 = self.ruta(b, p, algoritmo)
        rs, _ = self.mejor_sede(p, especialidad)
        compuesta = RutaCompuesta("ambulancia", [
            RutaCompuesta.desde_resultado(self.grafo, tramo1, "base -> paciente"),
            RutaCompuesta.desde_resultado(self.grafo, rs.resultado, "paciente -> sede"),
        ])
        return compuesta, tramo1, rs

    def cerrar_via(self, via, motivo="cierre"):
        return self.invocador.ejecutar(CerrarViaCmd(self.grafo, self.bus, via, motivo))

    def reabrir_via(self, via):
        return self.invocador.ejecutar(ReabrirViaCmd(self.grafo, self.bus, via))

    def deshacer(self):
        return self.invocador.deshacer()

    def metricas(self):
        return {
            "grafo": self.grafo.resumen(),
            "cache": {k: p.estadisticas() for k, p in self.proxies.items()},
            "comandos": self.invocador.historial[-20:],
            "recalculos_rutas_activas": self.rutas_activas.recalculos[-20:],
            "alt": {"landmarks": len(self.estrategias["alt"].landmarks),
                    "preproceso_s": round(self.estrategias["alt"].preproceso_s, 3)},
            "hora": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
