# -*- coding: utf-8 -*-
"""Diagramas UML como codigo: componentes, clases y actividad con Graphviz (dot);
secuencia con matplotlib. Uso:  python docs/uml/generar_uml.py   (requiere el binario `dot`)
Los nombres son identicos a los del codigo en rutas/."""
import os
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(os.path.dirname(AQUI), "figuras")
NAR, VER, GRI = "#F68421", "#02A554", "#f2f2f2"


def dot(nombre, texto):
    ruta = os.path.join(AQUI, nombre + ".dot")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    subprocess.check_call(["dot", "-Tpng", "-Gdpi=170", ruta, "-o", os.path.join(FIG, "u" + nombre + ".png")])


COMPONENTES = r'''digraph G {
rankdir=TB; nodesep=0.12; ranksep=0.3; compound=true; newrank=true;
node [shape=component, fontname="Helvetica", fontsize=17, style=filled, fillcolor="#ffffff", margin="0.08,0.04"];
edge [fontname="Helvetica", fontsize=16];
subgraph cluster_c { label="Clientes"; fontsize=17; fontname="Helvetica-Bold"; style=dashed;
  vista [label="Vista web\nGET /mapa"]; gestor [label="Gestor de\nreferencia"];
  gw [label="gateway Act. 4\n(futuro)", style="dashed,filled"]; }
api [label="rutas.api (http.server)\n/api/rutas · /api/sedes/mejor\n/api/vias/{id}/cerrar", fillcolor="#FBF1E8"];
subgraph cluster_o { label="Orquestación"; fontsize=17; fontname="Helvetica-Bold"; style=rounded;
  serv [label="ServicioRutas"]; inv [label="InvocadorComandos\n«Command»"]; sel [label="SelectorSede"]; comp [label="RutaCompuesta\n«Composite»"]; }
subgraph cluster_n { label="Navegación"; fontsize=17; fontname="Helvetica-Bold"; style=rounded;
  proxy [label="RutaCacheProxy\n«Proxy» + Cache-Aside", fillcolor="#FBF1E8"];
  est [label="EstrategiaRuta «Strategy»\nBFS · Dijkstra · Bidireccional\nAEstrella · ALT"];
  it [label="ExpansionIterator\n«Iterator»"]; }
subgraph cluster_e { label="Eventos de la red"; fontsize=17; fontname="Helvetica-Bold"; style=rounded;
  bus [label="BusEventosViales\n«Observer: sujeto»"]; act [label="RutasActivas\n«observador»"]; }
subgraph cluster_d { label="Datos (puertos y adaptadores)"; fontsize=17; fontname="Helvetica-Bold"; style=rounded;
  repo [label="RepositorioGrafo\n«puerto»"]; sint [label="GrafoSintetico\nAdapter"];
  arch [label="GrafoArchivo\nAdapter"]; json [shape=note, label="grafo_cali.json\nsedes.json"];
  osm [label="descargar_mapa\n_cali.py (OSMnx)", style="dashed,filled"]; }
vista -> api; gestor -> api; gw -> api [style=dashed];
api -> serv; serv -> inv; serv -> sel; serv -> comp; inv -> proxy [xlabel="CalcularRutaCmd"]; sel -> proxy;
proxy -> est [label=" fallo de caché"]; est -> it;
inv -> bus [label=" CerrarViaCmd"]; bus -> proxy [label=" invalidar", style=dashed, constraint=false]; bus -> act [style=dashed];
serv -> repo; {rank=same; proxy; bus; repo}
repo -> sint; repo -> arch; arch -> json; osm -> json [style=dashed, label=" una vez"];
}'''

CLASES = r'''digraph G {
rankdir=RL; nodesep=0.1; ranksep=0.4; splines=true;
node [shape=plain, fontname="Helvetica", fontsize=16];
edge [fontname="Helvetica", fontsize=15, arrowhead=empty];
EstrategiaRuta [label=<<table border="1" cellborder="0" cellspacing="0" bgcolor="#FBF1E8"><tr><td><i>«Strategy»</i></td></tr><tr><td><b><i>EstrategiaRuta</i></b></td></tr><tr><td align="left" sides="t" border="1">+ nombre: str<br align="left"/>+ exacta: bool</td></tr><tr><td align="left" sides="t" border="1">+ buscar(grafo, origen, destino): ResultadoBusqueda<br align="left"/>+ expansion(grafo, o, d): ExpansionIterator<br align="left"/># _expandir(): generador</td></tr></table>>];
BFS [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>BFS</b></td></tr></table>>];
Dijkstra [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>Dijkstra</b></td></tr></table>>];
Bidi [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>DijkstraBidireccional</b></td></tr></table>>];
Multi [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>DijkstraMultidestino</b></td></tr><tr><td align="left" sides="t" border="1">+ destinos: set</td></tr></table>>];
AEstrella [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>AEstrella</b></td></tr><tr><td align="left" sides="t" border="1">+ heuristica(grafo, t): h(v)</td></tr></table>>];
ALT [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>ALT</b></td></tr><tr><td align="left" sides="t" border="1">+ landmarks: list<br align="left"/>+ preprocesar()</td></tr></table>>];
Proxy [label=<<table border="1" cellborder="0" cellspacing="0" bgcolor="#FBF1E8"><tr><td><i>«Proxy» «Cache-Aside»</i></td></tr><tr><td><b>RutaCacheProxy</b></td></tr><tr><td align="left" sides="t" border="1">- real: EstrategiaRuta<br align="left"/>- ttl_s, capacidad (LRU)<br align="left"/>- _por_via: via → claves</td></tr><tr><td align="left" sides="t" border="1">+ obtener(clave, calcular)<br align="left"/>+ notificar(evento, datos)</td></tr></table>>];
Iter [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><i>«Iterator»</i></td></tr><tr><td><b>ExpansionIterator</b></td></tr><tr><td align="left" sides="t" border="1">+ __next__(): nodo<br align="left"/>+ expandidos: int<br align="left"/>+ resultado</td></tr></table>>];
Res [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>ResultadoBusqueda</b></td></tr><tr><td align="left" sides="t" border="1">+ costo_s, aristas<br align="left"/>+ expandidos, tiempo_ms</td></tr></table>>];
Obs [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><i>«interface»</i></td></tr><tr><td><b><i>ObservadorVial</i></b></td></tr><tr><td align="left" sides="t" border="1">+ notificar(evento, datos)</td></tr></table>>];
Bus [label=<<table border="1" cellborder="0" cellspacing="0" bgcolor="#FBF1E8"><tr><td><i>«Observer: sujeto»</i></td></tr><tr><td><b>BusEventosViales</b></td></tr><tr><td align="left" sides="t" border="1">+ suscribir(o)<br align="left"/>+ publicar(evento, datos)</td></tr></table>>];
Activas [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>RutasActivas</b></td></tr></table>>];
Cmd [label=<<table border="1" cellborder="0" cellspacing="0" bgcolor="#FBF1E8"><tr><td><i>«Command»</i></td></tr><tr><td><b><i>Comando</i></b></td></tr><tr><td align="left" sides="t" border="1">+ ejecutar()<br align="left"/>+ deshacer()</td></tr></table>>];
Cerrar [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>CerrarViaCmd</b></td></tr></table>>];
Reabrir [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>ReabrirViaCmd</b></td></tr></table>>];
Calc [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>CalcularRutaCmd</b></td></tr></table>>];
Inv [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>InvocadorComandos</b></td></tr><tr><td align="left" sides="t" border="1">+ historial, pila<br align="left"/>+ ejecutar(cmd)<br align="left"/>+ deshacer()</td></tr></table>>];
Elem [label=<<table border="1" cellborder="0" cellspacing="0" bgcolor="#FBF1E8"><tr><td><i>«Composite»</i></td></tr><tr><td><b><i>ElementoRuta</i></b></td></tr><tr><td align="left" sides="t" border="1">+ tiempo_s()<br align="left"/>+ distancia_m()<br align="left"/>+ instrucciones()</td></tr></table>>];
Tramo [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>Tramo</b></td></tr></table>>];
Compuesta [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>RutaCompuesta</b></td></tr><tr><td align="left" sides="t" border="1">+ hijos: list</td></tr></table>>];
Grafo [label=<<table border="1" cellborder="0" cellspacing="0"><tr><td><b>Grafo</b></td></tr><tr><td align="left" sides="t" border="1">+ cerrar_via(via)<br align="left"/>+ reabrir_via(via)</td></tr></table>>];
BFS -> EstrategiaRuta; Dijkstra -> EstrategiaRuta; Bidi -> EstrategiaRuta; Multi -> EstrategiaRuta; AEstrella -> EstrategiaRuta; ALT -> AEstrella;
Proxy -> EstrategiaRuta; Proxy -> Obs [style=dashed]; Activas -> Obs [style=dashed];
Proxy -> EstrategiaRuta [arrowhead=odiamond, label="real", constraint=false];
EstrategiaRuta -> Iter [arrowhead=vee, style=dashed, label="crea"]; Iter -> Res [arrowhead=vee, style=dashed, constraint=false];
Bus -> Obs [arrowhead=vee, label="0..*"];
Cerrar -> Cmd; Reabrir -> Cmd; Calc -> Cmd; Inv -> Cmd [arrowhead=odiamond, label="historial"];
Cerrar -> Bus [arrowhead=vee, style=dashed, label="publica"]; Cerrar -> Grafo [arrowhead=vee, style=dashed];
Tramo -> Elem; Compuesta -> Elem; Compuesta -> Elem [arrowhead=diamond, label="hijos 0..*", constraint=false];
}'''

ACTIVIDAD = r'''digraph G {
rankdir=TB; nodesep=0.15; ranksep=0.2;
node [fontname="Helvetica", fontsize=18, shape=box, style="rounded,filled", fillcolor="#ffffff", margin="0.06,0.03"];
edge [fontname="Helvetica", fontsize=16];
ini [shape=circle, label="", width=0.3, style=filled, fillcolor=black];
rec [label="Recibir solicitud\n(origen, especialidad)"];
val [shape=diamond, label="¿Datos\nválidos?", style=filled, fillcolor="#ffffff"];
e400 [label="Responder 400"];
cand [shape=diamond, label="¿Sedes\ncon cupo?", style=filled, fillcolor="#ffffff"];
e409 [label="Responder 409\n(sin sede)"];
cache [shape=diamond, label="¿En caché\ny vigente?", style=filled, fillcolor="#FBF1E8"];
hit [label="Devolver ruta\nguardada (acierto)"];
estr [label="Elegir estrategia\n(Strategy)", fillcolor="#FBF1E8"];
busc [label="Buscar: recorrer\nnodos expandidos\n(ExpansionIterator)"];
hay [shape=diamond, label="¿Ruta\nencontrada?", style=filled, fillcolor="#ffffff"];
sin [label="Responder \"sin ruta\""];
guar [label="Guardar en caché\ne indexar vías\n(Cache-Aside)"];
resp [label="Responder sede,\nruta e instrucciones\n(Composite)"];
fin [shape=doublecircle, label="", width=0.22, style=filled, fillcolor=black];
ev [label="Evento: cierre de vía\n(CerrarViaCmd)", fillcolor="#FBF1E8"];
fork [shape=box, label="", width=2.2, height=0.06, style=filled, fillcolor=black];
inval [label="Invalidar entradas\nque usan la vía"];
recal [label="Recalcular rutas\nactivas afectadas"];
join [shape=box, label="", width=2.2, height=0.06, style=filled, fillcolor=black];
ini -> rec -> val; val -> e400 [label="no"]; val -> cand [label="sí"];
cand -> e409 [label="no"]; cand -> cache [label="sí"];
cache -> hit [label="sí"]; cache -> estr [label="no"]; estr -> busc -> hay;
hay -> sin [label="no"]; hay -> guar [label="sí"]; guar -> resp; hit -> resp; resp -> fin;
ev -> fork; fork -> inval; fork -> recal; inval -> join; recal -> join; join -> fin [style=dashed];
{rank=same; rec; ev}
}'''


def secuencia(salida):
    part = ["Gestor", "rutas.api", "Servicio\nRutas", "RutaCache\nProxy", "Selector /\nEstrategia",
            "Invocador\nComandos", "Grafo", "BusEventos\nViales", "Rutas\nActivas"]
    PASO, FS = 1.13, 13
    X = [0.55 + i * PASO for i in range(len(part))]
    msgs = [
        ("T", "a) Consulta: mejor sede y ruta"),
        (0, 1, "POST /api/sedes/mejor", "s"),
        (1, 2, "mejor_sede(o, esp.)", "s"),
        (2, 3, "obtener(clave, calcular)", "s"),
        ("ALT1", "alt [fallo de caché]"),
        (3, 4, "mejor(o, esp., modo)", "s"),
        (4, 4, "for nodo in ExpansionIterator", "self"),
        (4, 3, "ResultadoSede", "r"),
        (3, 3, "guardar + indexar vías", "self"),
        ("ELSE", "[acierto]"),
        (3, 3, "devolver guardado", "self"),
        ("END",),
        (3, 2, "ResultadoSede", "r"),
        (1, 0, "200 {sede, ruta, min}", "r"),
        ("T", "b) Cierre de vía y recálculo"),
        (0, 1, "POST /api/vias/{id}/cerrar", "s"),
        (1, 5, "ejecutar(CerrarViaCmd)", "s"),
        (5, 6, "cerrar_via(via)", "s"),
        (5, 7, "publicar(\"via.cerrada\")", "s"),
        (7, 3, "notificar → invalidar claves", "s"),
        (7, 8, "notificar", "s"),
        (8, 4, "buscar(o, d) por ruta activa", "s"),
        (5, 1, "{via: cerrada}", "r"),
        (1, 0, "200 {via: cerrada}", "r"),
    ]
    fig, ax = plt.subplots(figsize=(X[-1] + 0.6, 12.0))
    ax.set_xlim(0, X[-1] + 0.6)
    ax.axis("off")
    for x, p in zip(X, part):
        ax.add_patch(FancyBboxPatch((x - 0.52, 0.35), 1.04, 0.62, boxstyle="round,pad=0.02", fc="#FBF1E8", ec="black"))
        ax.text(x, 0.66, p, ha="center", va="center", fontsize=FS - 2, weight="bold")
    y = -0.05
    pila = []
    n = 0
    for m in msgs:
        if m[0] == "T":
            y -= 0.22
            ax.text(0.02, y, m[1], fontsize=FS + 1, weight="bold", bbox=dict(fc="white", ec="black", boxstyle="square,pad=0.2"))
            y -= 0.45
            continue
        if m[0] == "ALT1":
            pila.append(y)
            ax.text(X[3] - 0.6, y - 0.03, m[1], fontsize=FS - 1, weight="bold", va="top")
            y -= 0.7
            continue
        if m[0] == "ELSE":
            ax.plot([X[3] - 0.65, X[4] + 1.0], [y + 0.12, y + 0.12], color="black", ls=":", lw=1.2)
            ax.text(X[3] - 0.6, y + 0.07, m[1], fontsize=FS - 1, weight="bold", va="top")
            y -= 0.55
            continue
        if m[0] == "END":
            y0 = pila.pop()
            ax.add_patch(Rectangle((X[3] - 0.65, y + 0.15), X[4] - X[3] + 1.65, y0 - y - 0.1, fill=False, ec="black", lw=1.3))
            y -= 0.12
            continue
        a, b, t, tipo = m
        n += 1
        if tipo == "self":
            ax.plot([X[a], X[a] + 0.22, X[a] + 0.22], [y, y, y - 0.2], color="black", lw=1.3)
            ax.annotate("", xy=(X[a] + 0.02, y - 0.2), xytext=(X[a] + 0.22, y - 0.2),
                        arrowprops=dict(arrowstyle="-|>", color="black", lw=1.3))
            ax.text(X[a] + 0.3, y - 0.1, "%d. %s" % (n, t), fontsize=FS, va="center", bbox=dict(fc="white", ec="none", pad=0.4))
            y -= 0.6
            continue
        ax.annotate("", xy=(X[b], y), xytext=(X[a], y),
                    arrowprops=dict(arrowstyle="-|>" if tipo == "s" else "->", color="black", lw=1.4, ls="-" if tipo == "s" else "--"))
        xm = (X[a] + X[b]) / 2
        ha = "center"
        if abs(b - a) == 1:   # mensajes cortos: el texto arranca en la linea de vida de origen
            xm, ha = min(X[a], X[b]) + 0.08, "left"
        ax.text(xm, y + 0.05, "%d. %s" % (n, t), ha=ha, va="bottom", fontsize=FS, bbox=dict(fc="white", ec="none", pad=0.4))
        y -= 0.42
    for x in X:
        ax.plot([x, x], [0.35, y], color="#888888", ls="--", lw=1, zorder=0)
    ax.set_ylim(y - 0.05, 1.0)
    fig.savefig(salida, dpi=170, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    dot("1-componentes", COMPONENTES)
    dot("3-clases", CLASES)
    dot("4-actividad", ACTIVIDAD)
    secuencia(os.path.join(FIG, "u2-secuencia.png"))
    print("UML en", FIG)
