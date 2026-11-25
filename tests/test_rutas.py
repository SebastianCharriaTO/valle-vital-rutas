# -*- coding: utf-8 -*-
"""Pruebas del motor de rutas. Ejecutar:  python -m pytest -q"""
import json
import os
import random
import tempfile
import threading
import urllib.request

import pytest

from rutas.api import crear_servidor
from rutas.cache import RutaCacheProxy
from rutas.estrategias import ALT, AEstrella, Dijkstra, _dijkstra_completo
from rutas.grafo import INF
from rutas.repositorio import GrafoArchivoAdapter, GrafoSinteticoAdapter, guardar_json
from rutas.ruta import RutaCompuesta
from rutas.servicio import ServicioRutas


@pytest.fixture(scope="module")
def serv():
    return ServicioRutas(GrafoSinteticoAdapter(nodos=1500, semilla=5).obtener())


def pares(g, n, semilla=1):
    rnd = random.Random(semilla)
    return [(rnd.randrange(g.n_nodos), rnd.randrange(g.n_nodos)) for _ in range(n)]


def test_grafo_sintetico_reproducible():
    a = GrafoSinteticoAdapter(800, 3).obtener()
    b = GrafoSinteticoAdapter(800, 3).obtener()
    assert a.n_nodos == b.n_nodos and a.costo == b.costo


def test_estrategias_exactas_igualan_a_dijkstra(serv):
    g = serv.grafo
    for o, d in pares(g, 60):
        ref = serv.estrategias["dijkstra"].buscar(g, o, d).costo_s
        for k in ("bidireccional", "a_estrella", "alt"):
            assert serv.estrategias[k].buscar(g, o, d).costo_s == pytest.approx(ref, rel=1e-9), k
        assert serv.estrategias["bfs"].buscar(g, o, d).costo_s >= ref - 1e-9


def test_oraculo_networkx(serv):
    nx = pytest.importorskip("networkx")
    g = serv.grafo
    G = nx.DiGraph()
    for e in range(g.n_aristas):
        u, v = g.a_origen[e], g.a_destino[e]
        if not G.has_edge(u, v) or G[u][v]["w"] > g.costo[e]:
            G.add_edge(u, v, w=g.costo[e])
    for o, d in pares(g, 30, 9):
        assert serv.estrategias["alt"].buscar(g, o, d).costo_s == pytest.approx(
            nx.dijkstra_path_length(G, o, d, weight="w"), rel=1e-9)


def test_heuristicas_admisibles(serv):
    g = serv.grafo
    rnd = random.Random(4)
    for t in [rnd.randrange(g.n_nodos) for _ in range(5)]:
        real = _dijkstra_completo(g, t, inverso=True, usar_base=False)  # d(v, t)
        for est in (serv.estrategias["a_estrella"], serv.estrategias["alt"]):
            h = est.heuristica(g, t)
            for v in rnd.sample(range(g.n_nodos), 300):
                assert h(v) <= real[v] + 1e-6


def test_alt_menos_expandidos_que_dijkstra(serv):
    g = serv.grafo
    tot_d = tot_a = 0
    for o, d in pares(g, 40, 2):
        tot_d += serv.estrategias["dijkstra"].buscar(g, o, d).expandidos
        tot_a += serv.estrategias["alt"].buscar(g, o, d).expandidos
    assert tot_a < tot_d


def test_composite_suma_tiempos(serv):
    comp, t1, rs = serv.ruta_ambulancia("B1", "P03", "Medicina general")
    assert comp.tiempo_s() == pytest.approx(sum(h.tiempo_s() for h in comp.hijos))
    assert comp.tiempo_s() == pytest.approx(t1.costo_s + rs.resultado.costo_s)
    assert len(list(comp)) == len(t1.aristas) + len(rs.aristas)
    assert comp.instrucciones()


def test_command_cerrar_y_deshacer(serv):
    g = serv.grafo
    o, d = serv.puntos["P05"], serv.selector.sedes[0]["nodo"]
    antes = serv.ruta(o, d, "dijkstra", usar_cache=False)
    via = g.a_via[antes.aristas[len(antes.aristas) // 2]]
    serv.cerrar_via(via, "prueba")
    despues = serv.ruta(o, d, "dijkstra", usar_cache=False)
    assert not set(g.vias[via]) & set(despues.aristas)
    assert despues.costo_s >= antes.costo_s
    serv.deshacer()
    otra = serv.ruta(o, d, "dijkstra", usar_cache=False)
    assert otra.costo_s == pytest.approx(antes.costo_s)
    assert any("Deshacer" in h["comando"] for h in serv.invocador.historial)


def test_observer_invalida_cache_y_no_sirve_rutas_obsoletas(serv):
    g = serv.grafo
    p = serv.proxies["alt"]
    o, d = serv.puntos["P11"], serv.selector.sedes[1]["nodo"]
    r1 = serv.ruta(o, d, "alt")
    r2 = serv.ruta(o, d, "alt")
    assert r2.desde_cache and r2.costo_s == r1.costo_s
    via = g.a_via[r1.aristas[len(r1.aristas) // 2]]
    serv.cerrar_via(via)
    r3 = serv.ruta(o, d, "alt")
    assert not r3.desde_cache
    assert not set(g.vias[via]) & set(r3.aristas)
    assert p.invalidadas >= 1
    serv.deshacer()


def test_sin_observer_la_cache_sirve_rutas_obsoletas():
    g = GrafoSinteticoAdapter(1200, 8).obtener()
    s = ServicioRutas(g, con_observer=False)
    o, d = s.puntos["P02"], s.selector.sedes[0]["nodo"]
    r1 = s.ruta(o, d, "alt")
    via = g.a_via[r1.aristas[len(r1.aristas) // 2]]
    s.cerrar_via(via)
    r2 = s.ruta(o, d, "alt")
    assert r2.desde_cache and set(g.vias[via]) & set(r2.aristas)   # justo lo que el Observer evita


def test_ttl_expira():
    reloj = [0.0]
    g = GrafoSinteticoAdapter(500, 1).obtener()
    p = RutaCacheProxy(Dijkstra(), g, ttl_s=10, reloj=lambda: reloj[0])
    p.buscar(g, 0, 5)
    assert p.buscar(g, 0, 5).desde_cache
    reloj[0] = 11
    assert not p.buscar(g, 0, 5).desde_cache


def test_selector_una_pasada_igual_a_por_sede(serv):
    for k in ("P01", "P09", "P20", "P33"):
        a = serv.selector.mejor(serv.puntos[k], "Medicina general", "una_pasada")
        b = serv.selector.mejor(serv.puntos[k], "Medicina general", "por_sede", serv.estrategias["a_estrella"])
        assert a.resultado.costo_s == pytest.approx(b.resultado.costo_s)


def test_alt_sigue_valido_tras_cierre(serv):
    g = serv.grafo
    o, d = pares(g, 1, 77)[0]
    r = serv.estrategias["dijkstra"].buscar(g, o, d)
    via = g.a_via[r.aristas[0]]
    g.cerrar_via(via)
    try:
        assert serv.estrategias["alt"].buscar(g, o, d).costo_s == pytest.approx(
            serv.estrategias["dijkstra"].buscar(g, o, d).costo_s)
    finally:
        g.reabrir_via(via)


def test_adaptador_archivo_ida_y_vuelta():
    g = GrafoSinteticoAdapter(400, 2).obtener()
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "g.json")
        guardar_json(g, ruta)
        h = GrafoArchivoAdapter(ruta).obtener()
    assert h.n_nodos == g.n_nodos and h.n_aristas == g.n_aristas
    assert Dijkstra().buscar(h, 0, 50).costo_s == pytest.approx(Dijkstra().buscar(g, 0, 50).costo_s, rel=1e-6)


def test_api_http(serv):
    srv = crear_servidor(serv, 0)
    puerto = srv.server_address[1]
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    try:
        def post(ruta, datos):
            req = urllib.request.Request("http://127.0.0.1:%d%s" % (puerto, ruta), json.dumps(datos).encode(),
                                         {"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req).read().decode())
        r = post("/api/sedes/mejor", {"origen": "P07", "especialidad": "Pediatria"})
        assert r["sede"] == "S1" and r["encontrada"]
        r = post("/api/rutas", {"origen": "P07", "destino": "S2", "algoritmo": "a_estrella"})
        assert r["tiempo_viaje_min"] > 0
        html = urllib.request.urlopen("http://127.0.0.1:%d/mapa?origen=P07" % puerto).read().decode()
        assert "<svg" in html and "Sede recomendada" in html
    finally:
        srv.shutdown()
        srv.server_close()


def test_reproducible_entre_versiones_de_python():
    """Huella del grafo sintetico y de los landmarks de ALT. Debe dar lo mismo en Python 3.8 a 3.13:
    longitudes y coordenadas se redondean y las distancias usan math.sqrt (correctamente redondeada)."""
    import hashlib
    g = GrafoSinteticoAdapter(800, 3).obtener()
    a = ALT(g, 4)
    huella = hashlib.md5(repr((g.costo, g.x, g.y, a.landmarks)).encode()).hexdigest()
    assert huella == "b987d2b840b39f3808534e6e40179784"
