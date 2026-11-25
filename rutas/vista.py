# -*- coding: utf-8 -*-
"""Vista web (HTML + SVG generado en el servidor, sin CDN ni JavaScript externo)."""
from html import escape

COLOR_TIPO = {"local": ("#d9d9d9", 0.5), "colectora": ("#bdbdbd", 0.9), "arteria": ("#9e9e9e", 1.8),
              "autopista": ("#7a7a7a", 2.6)}
ALGORITMOS = [("alt", "ALT (landmarks)"), ("a_estrella", "A*"), ("bidireccional", "Dijkstra bidireccional"),
              ("dijkstra", "Dijkstra"), ("bfs", "BFS (ingenuo)")]


OSM_A_CLASE = {"motorway": "autopista", "trunk": "autopista", "motorway_link": "autopista", "trunk_link": "autopista",
               "primary": "arteria", "secondary": "arteria", "primary_link": "arteria", "secondary_link": "arteria",
               "tertiary": "colectora", "tertiary_link": "colectora"}


def clase_visual(tipo):
    """Clase de dibujo para tipos sinteticos (arteria...) y de OSM (primary...)."""
    return tipo if tipo in COLOR_TIPO else OSM_A_CLASE.get(tipo, "local")


class Proyeccion(object):
    def __init__(self, g, ancho=430.0, margen=10.0):
        self.x0, self.x1 = min(g.x), max(g.x)
        self.y0, self.y1 = min(g.y), max(g.y)
        self.esc = (ancho - 2 * margen) / (self.x1 - self.x0)
        self.m = margen
        self.ancho = ancho
        self.alto = (self.y1 - self.y0) * self.esc + 2 * margen

    def __call__(self, g, v):
        return (self.m + (g.x[v] - self.x0) * self.esc, self.m + (self.y1 - g.y[v]) * self.esc)


def svg_mapa(g, ruta=None, orden=None, sedes=(), origen=None, extra_rutas=(), proy=None):
    P = proy or Proyeccion(g)
    partes = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.0f %.0f" class="mapa">' % (P.ancho, P.alto),
              '<rect width="100%" height="100%" fill="#ffffff"/>']
    trazos = {}
    vistos = set()
    for e in range(g.n_aristas):
        via = g.a_via[e]
        if via in vistos:
            continue
        vistos.add(via)
        a, b = P(g, g.a_origen[e]), P(g, g.a_destino[e])
        trazos.setdefault(clase_visual(g.a_tipo[e]), []).append(
            "M%.1f %.1fL%.1f %.1f" % (a[0], a[1], b[0], b[1]))
    for tipo in ("local", "colectora", "arteria", "autopista"):
        if tipo in trazos:
            color, w = COLOR_TIPO[tipo]
            partes.append('<path d="%s" stroke="%s" stroke-width="%.1f" fill="none"/>' % ("".join(trazos[tipo]), color, w))
    if orden:
        pts = []
        for v in orden:
            x, y = P(g, v)
            pts.append("M%.1f %.1fh1.6v1.6h-1.6z" % (x - 0.8, y - 0.8))
        partes.append('<path d="%s" fill="#5b9bd5" fill-opacity="0.55"/>' % "".join(pts))
    for via in g.cerradas:
        for e in g.vias[via]:
            a, b = P(g, g.a_origen[e]), P(g, g.a_destino[e])
            partes.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#c00000" stroke-width="6"/>' % (a[0], a[1], b[0], b[1]))
    for (r, color, dash) in list(extra_rutas) + ([(ruta, "#1f1f1f", "")] if ruta is not None else []):
        if r is None or not r.aristas:
            continue
        pts = [P(g, v) for v in r.nodos(g)]
        partes.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="3.2" stroke-linejoin="round" %s/>' % (
            " ".join("%.1f,%.1f" % p for p in pts), color, ('stroke-dasharray="%s"' % dash) if dash else ""))
    for s in sedes:
        x, y = P(g, s["nodo"])
        partes.append('<rect x="%.1f" y="%.1f" width="12" height="12" fill="#02A554" stroke="#000"/>' % (x - 6, y - 6))
        partes.append('<text x="%.1f" y="%.1f" font-size="13" font-family="sans-serif" font-weight="bold">%s</text>' % (x + 8, y + 5, escape(s["id"])))
    if origen is not None:
        x, y = P(g, origen)
        partes.append('<circle cx="%.1f" cy="%.1f" r="7" fill="#F68421" stroke="#000"/>' % (x, y))
    partes.append("</svg>")
    return "".join(partes)


def pagina(serv, params):
    g = serv.grafo
    origen_txt = params.get("origen", "P07")
    esp = params.get("especialidad", "Medicina general")
    alg = params.get("algoritmo", "alt")
    msg = params.get("msg", "")
    try:
        o = serv.resolver_nodo(origen_txt)
        rs, acierto = serv.mejor_sede(o, esp)
        destino = rs.sede["nodo"]
        dibujo = serv.ruta(o, destino, alg, registrar_orden=True)
        comparacion = []
        for k, nombre in ALGORITMOS:
            r = serv.estrategias[k].buscar(g, o, destino)
            comparacion.append((nombre, r))
        error = ""
    except Exception as ex:  # se muestra en la pagina
        rs, dibujo, comparacion, error, acierto = None, None, [], str(ex), False
    svg = svg_mapa(g, dibujo, dibujo.orden_expansion if dibujo else None, serv.selector.sedes,
                   o if not error else None)
    # via sugerida para el cierre: el tramo de arteria o colectora mas largo de la ruta
    via_cierre = ""
    if dibujo is not None and dibujo.aristas:
        candidatas = [e for e in dibujo.aristas if clase_visual(g.a_tipo[e]) != "local"] or dibujo.aristas
        e_mid = candidatas[len(candidatas) // 2]
        via_cierre = g.a_via[e_mid]
    sel = lambda opts, actual: "".join('<option value="%s"%s>%s</option>' % (escape(v), " selected" if v == actual else "", escape(t)) for v, t in opts)
    puntos = [(k, k) for k in sorted(serv.puntos)] + [(b["id"], b["id"] + " (base)") for b in serv.bases]
    if origen_txt not in serv.puntos and origen_txt not in [b["id"] for b in serv.bases]:
        puntos.insert(0, (origen_txt, origen_txt))
    esps = sorted({e for s in serv.selector.sedes for e, ok in s.get("especialidades", {}).items()})
    filas = "".join("<tr><td>%s</td><td>%.1f</td><td>%s</td><td>%.1f</td></tr>" % (
        escape(n), r.costo_s / 60.0, "{:,}".format(r.expandidos).replace(",", "."), r.tiempo_ms) for n, r in comparacion)
    instr = ""
    if dibujo is not None:
        from .ruta import RutaCompuesta
        pasos = RutaCompuesta.desde_resultado(g, dibujo).instrucciones()
        instr = "".join("<li>%s</li>" % escape(p) for p in pasos[:8]) + ("<li>…</li>" if len(pasos) > 8 else "")
    cerradas = ", ".join(sorted(g.cerradas)) or "ninguna"
    stats = serv.proxies["alt"].estadisticas()
    fuente = "© OpenStreetMap contributors (ODbL)" if g.fuente == "osm" else "Ciudad sintética reproducible (semilla %s) — no es el mapa real" % g.meta.get("semilla", "?")
    cuerpo = """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Valle Vital · Ruta a la sede óptima</title>
<style>body{font-family:Segoe UI,Arial,sans-serif;margin:0;display:flex;color:#222}
.izq{flex:0 0 auto;padding:8px}.mapa{height:94vh;border:1px solid #ccc}
.der{padding:14px 18px;max-width:560px}h1{font-size:20px;margin:4px 0 8px}h2{font-size:15px;margin:14px 0 4px}
table{border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid #ddd;padding:3px 8px;text-align:right}td:first-child,th:first-child{text-align:left}
.res{background:#FBF1E8;padding:8px 10px;border-left:4px solid #F68421;font-size:14px}
button{background:#F68421;border:0;color:#fff;padding:6px 10px;margin:4px 4px 0 0;cursor:pointer}
.err{color:#c00000}.nota{font-size:11px;color:#666}ol{font-size:13px;padding-left:18px;margin:4px 0}
.ley span{display:inline-block;width:12px;height:12px;margin:0 4px 0 10px;vertical-align:middle}</style></head><body>
<div class="izq">%(svg)s</div><div class="der">
<h1>Valle Vital · Ruta a la sede óptima</h1>
<form method="get" action="/mapa">Origen <select name="origen">%(puntos)s</select>
Especialidad <select name="especialidad">%(esps)s</select><br>Algoritmo <select name="algoritmo">%(algs)s</select>
<button type="submit">Calcular</button></form>
%(msg)s%(error)s
<div class="res">%(resumen)s</div>
<h2>Comparación de estrategias (mismo origen y sede)</h2>
<table><tr><th>Estrategia</th><th>Tiempo de viaje (min)</th><th>Nodos expandidos</th><th>Consulta (ms)</th></tr>%(filas)s</table>
<h2>Instrucciones</h2><ol>%(instr)s</ol>
<h2>Cierre de vía (Command + Observer)</h2>
<form method="post" action="/accion/cerrar" style="display:inline"><input type="hidden" name="via" value="%(via)s">
<input type="hidden" name="volver" value="%(volver)s"><button>Cerrar la vía %(via)s</button></form>
<form method="post" action="/accion/deshacer" style="display:inline"><input type="hidden" name="volver" value="%(volver)s"><button>Deshacer último comando</button></form>
<p>Vías cerradas: %(cerradas)s · Caché ALT: %(ac)d aciertos, %(fa)d fallos, %(inv)d invalidadas</p>
<p class="ley"><span style="background:#5b9bd5"></span>nodos expandidos<span style="background:#1f1f1f"></span>ruta<span style="background:#02A554"></span>sede<span style="background:#F68421;border-radius:6px"></span>origen<span style="background:#c00000"></span>vía cerrada</p>
<p class="nota">%(fuente)s. Sedes y coordenadas ficticias. El sistema recomienda; no despacha ambulancias ni reemplaza al CRUE.</p>
</div></body></html>"""
    if rs is not None:
        resumen = ("Sede recomendada: <b>%s</b> (%s) · tiempo de viaje <b>%.1f min</b> · %.1f km · candidatas: %s · selección en %.2f ms%s"
                   % (escape(rs.sede["id"]), escape(rs.sede["nombre"]), rs.resultado.costo_s / 60.0,
                      sum(g.a_longitud[e] for e in rs.aristas) / 1000.0, ", ".join(rs.candidatas), rs.tiempo_ms,
                      " (desde caché)" if acierto else ""))
    else:
        resumen = "Sin resultado"
    volver = "/mapa?origen=%s&especialidad=%s&algoritmo=%s" % (escape(origen_txt), escape(esp), escape(alg))
    return cuerpo % {
        "svg": svg, "puntos": sel(puntos, origen_txt), "esps": sel([(e, e) for e in esps], esp),
        "algs": sel(ALGORITMOS, alg), "msg": ('<p><b>%s</b></p>' % escape(msg)) if msg else "",
        "error": ('<p class="err">%s</p>' % escape(error)) if error else "", "resumen": resumen, "filas": filas,
        "instr": instr, "via": escape(via_cierre), "volver": volver, "cerradas": escape(cerradas),
        "ac": stats["aciertos"], "fa": stats["fallos"], "inv": stats["invalidadas"], "fuente": fuente,
    }
