# -*- coding: utf-8 -*-
"""API HTTP y vista web con la biblioteca estandar (http.server). Python 3.8+.

Uso:  python -m rutas.api [--puerto 8080] [--grafo datos/grafo_cali.json] [--nodos 10000]

Endpoints (JSON):
  GET  /api/salud
  GET  /api/metricas
  GET  /api/puntos
  POST /api/rutas          {"origen": "P07", "destino": "S1", "algoritmo": "alt"}
  POST /api/sedes/mejor    {"origen": "P07", "especialidad": "Medicina general", "modo": "una_pasada"}
  POST /api/ambulancia     {"base": "B1", "paciente": "P07", "especialidad": "Pediatria"}
  POST /api/vias/<via>/cerrar   ·   POST /api/vias/<via>/reabrir   ·   POST /api/comandos/deshacer
Vista: GET /mapa?origen=P07&especialidad=Medicina%20general&algoritmo=alt
"""
import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

from .repositorio import cargar_grafo
from .sedes import SinSedeDisponible
from .servicio import ServicioRutas
from .vista import pagina


def crear_manejador(serv):
    lock = threading.Lock()  # las escrituras sobre la red (cierres) se serializan

    class Manejador(BaseHTTPRequestHandler):
        server_version = "ValleVitalRutas/1.0"

        def log_message(self, fmt, *args):  # silencioso en mediciones
            pass

        def _json(self, codigo, datos):
            cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _html(self, texto):
            cuerpo = texto.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _redir(self, destino):
            self.send_response(303)
            self.send_header("Location", destino)
            self.end_headers()

        def _cuerpo(self):
            n = int(self.headers.get("Content-Length") or 0)
            crudo = self.rfile.read(n).decode("utf-8") if n else ""
            if "json" in (self.headers.get("Content-Type") or ""):
                return json.loads(crudo or "{}")
            return {k: v[0] for k, v in parse_qs(crudo).items()}

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path in ("/", "/mapa"):
                    with lock:
                        return self._html(pagina(serv, q))
                if u.path == "/api/salud":
                    return self._json(200, {"estado": "ok", "grafo": serv.grafo.resumen()})
                if u.path == "/api/metricas":
                    return self._json(200, serv.metricas())
                if u.path == "/api/puntos":
                    return self._json(200, {"puntos": serv.puntos,
                                            "sedes": [{k: s[k] for k in ("id", "nombre", "nodo", "especialidades")} for s in serv.selector.sedes],
                                            "bases": [{k: b[k] for k in ("id", "nombre", "nodo")} for b in serv.bases]})
                return self._json(404, {"error": "no encontrado"})
            except Exception as ex:
                return self._json(400, {"error": str(ex)})

        def do_POST(self):
            u = urlparse(self.path)
            partes = [unquote(p) for p in u.path.strip("/").split("/")]
            try:
                d = self._cuerpo()
                if u.path == "/api/rutas":
                    r = serv.ruta(d["origen"], d["destino"], d.get("algoritmo"), d.get("cache", True))
                    return self._json(200, r.a_dict(serv.grafo))
                if u.path == "/api/sedes/mejor":
                    rs, acierto = serv.mejor_sede(d["origen"], d["especialidad"], d.get("modo", "una_pasada"),
                                                  d.get("algoritmo"), d.get("cache", True))
                    salida = rs.resultado.a_dict(serv.grafo)
                    salida.update({"sede": rs.sede["id"], "sede_nombre": rs.sede["nombre"], "candidatas": rs.candidatas,
                                   "modo": rs.modo, "seleccion_ms": round(rs.tiempo_ms, 3), "desde_cache": acierto})
                    return self._json(200, salida)
                if u.path == "/api/ambulancia":
                    comp, t1, rs = serv.ruta_ambulancia(d.get("base", "B1"), d["paciente"], d["especialidad"])
                    return self._json(200, {"sede": rs.sede["id"], "tiempo_total_min": round(comp.tiempo_s() / 60.0, 2),
                                            "distancia_km": round(comp.distancia_m() / 1000.0, 2),
                                            "subrutas": [{"nombre": h.nombre, "tiempo_min": round(h.tiempo_s() / 60.0, 2)} for h in comp.hijos],
                                            "instrucciones": comp.instrucciones()})
                if len(partes) == 4 and partes[:2] == ["api", "vias"] and partes[3] in ("cerrar", "reabrir"):
                    with lock:
                        salida = serv.cerrar_via(partes[2], d.get("motivo", "api")) if partes[3] == "cerrar" else serv.reabrir_via(partes[2])
                    return self._json(200, salida)
                if u.path == "/api/comandos/deshacer":
                    with lock:
                        return self._json(200, {"deshecho": serv.deshacer()})
                if u.path == "/accion/cerrar":
                    with lock:
                        serv.cerrar_via(d["via"], "vista")
                    return self._redir(d.get("volver", "/mapa") + "&msg=" + quote("Vía %s cerrada: la ruta se recalculó" % d["via"]))
                if u.path == "/accion/deshacer":
                    with lock:
                        txt = serv.deshacer()
                    return self._redir(d.get("volver", "/mapa") + "&msg=" + quote("Deshecho: %s" % (txt or "nada que deshacer")))
                return self._json(404, {"error": "no encontrado"})
            except SinSedeDisponible as ex:
                return self._json(409, {"error": str(ex)})
            except (KeyError, ValueError) as ex:
                return self._json(400, {"error": "solicitud invalida: %s" % ex})

    return Manejador


def crear_servidor(serv, puerto=8080, host="127.0.0.1"):
    return ThreadingHTTPServer((host, puerto), crear_manejador(serv))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Valle Vital · servicio de rutas")
    ap.add_argument("--puerto", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--grafo", default=None, help="JSON del grafo real (por defecto datos/grafo_cali.json si existe)")
    ap.add_argument("--nodos", type=int, default=10000, help="tamano de la ciudad sintetica")
    a = ap.parse_args(argv)
    g = cargar_grafo(a.grafo, a.nodos)
    serv = ServicioRutas(g)
    print("Grafo: %s (%d nodos, %d aristas)" % (g.nombre, g.n_nodos, g.n_aristas))
    print("Vista:  http://%s:%d/mapa" % (a.host, a.puerto))
    srv = crear_servidor(serv, a.puerto, a.host)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
