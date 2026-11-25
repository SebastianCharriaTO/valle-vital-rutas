# -*- coding: utf-8 -*-
"""Patron Command: cada solicitud sobre la red es un objeto con ejecutar() y deshacer().

El InvocadorComandos guarda el historial (registro auditable) y la pila para deshacer.
"""
import threading
import time


class Comando(object):
    reversible = False

    def ejecutar(self):  # pragma: no cover - interfaz
        raise NotImplementedError

    def deshacer(self):
        pass

    def descripcion(self):
        return self.__class__.__name__


class CerrarViaCmd(Comando):
    reversible = True

    def __init__(self, grafo, bus, via, motivo="cierre"):
        self.grafo, self.bus, self.via, self.motivo = grafo, bus, via, motivo

    def ejecutar(self):
        aristas = self.grafo.cerrar_via(self.via)
        self.bus.publicar("via.cerrada", {"via": self.via, "aristas": aristas, "motivo": self.motivo})
        return {"via": self.via, "estado": "cerrada", "aristas": len(aristas)}

    def deshacer(self):
        aristas = self.grafo.reabrir_via(self.via)
        self.bus.publicar("via.reabierta", {"via": self.via, "aristas": aristas})

    def descripcion(self):
        return "Cerrar via %s (%s)" % (self.via, self.motivo)


class ReabrirViaCmd(Comando):
    reversible = True

    def __init__(self, grafo, bus, via):
        self.grafo, self.bus, self.via = grafo, bus, via

    def ejecutar(self):
        aristas = self.grafo.reabrir_via(self.via)
        self.bus.publicar("via.reabierta", {"via": self.via, "aristas": aristas})
        return {"via": self.via, "estado": "abierta", "aristas": len(aristas)}

    def deshacer(self):
        aristas = self.grafo.cerrar_via(self.via)
        self.bus.publicar("via.cerrada", {"via": self.via, "aristas": aristas, "motivo": "deshacer"})

    def descripcion(self):
        return "Reabrir via %s" % self.via


class CalcularRutaCmd(Comando):
    """Solicitud de ruta como objeto: se puede registrar, encolar o reintentar."""

    def __init__(self, estrategia, grafo, origen, destino):
        self.estrategia, self.grafo, self.origen, self.destino = estrategia, grafo, origen, destino

    def ejecutar(self):
        return self.estrategia.buscar(self.grafo, self.origen, self.destino)

    def descripcion(self):
        return "Calcular ruta %s -> %s (%s)" % (self.origen, self.destino, self.estrategia.nombre)


class InvocadorComandos(object):
    def __init__(self, max_historial=500):
        self.historial = []
        self.pila = []
        self.max_historial = max_historial
        self._lock = threading.Lock()

    def ejecutar(self, cmd):
        with self._lock:
            salida = cmd.ejecutar()
            self._registrar(cmd.descripcion())
            if cmd.reversible:
                self.pila.append(cmd)
            return salida

    def deshacer(self):
        with self._lock:
            if not self.pila:
                return None
            cmd = self.pila.pop()
            cmd.deshacer()
            self._registrar("Deshacer: " + cmd.descripcion())
            return cmd.descripcion()

    def _registrar(self, texto):
        self.historial.append({"t": time.strftime("%H:%M:%S"), "comando": texto})
        if len(self.historial) > self.max_historial:
            del self.historial[0]
