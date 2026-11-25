# -*- coding: utf-8 -*-
"""Graficos del informe a partir de bench/resultados/resumen.json (Python 3.8+, matplotlib).

    python bench/graficos.py [--grafo datos/grafo_cali.json] [--salida docs/figuras]
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from rutas.repositorio import cargar_grafo  # noqa: E402
from rutas.servicio import ServicioRutas  # noqa: E402
from rutas.vista import clase_visual  # noqa: E402

plt.rcParams.update({"font.size": 12, "font.family": "DejaVu Sans", "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 200})
NOMBRE = {"bfs": "BFS", "dijkstra": "Dijkstra", "bidireccional": "Bidirecc.", "a_estrella": "A*", "alt": "ALT"}
GRIS = {"bfs": "#bdbdbd", "dijkstra": "#7f7f7f", "bidireccional": "#a6a6a6", "a_estrella": "#4d4d4d", "alt": "#F68421"}
TRAMA = {"bfs": "..", "dijkstra": "", "bidireccional": "//", "a_estrella": "xx", "alt": ""}


def es(x, d=1):
    return ("{:,.%df}" % d).format(x).replace(",", "X").replace(".", ",").replace("X", ".")


def g1(R, out):
    algs = ["bfs", "dijkstra", "bidireccional", "a_estrella", "alt"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    exp = [R["e1"][a]["expandidos_mediana"] for a in algs]
    b = ax[0].bar([NOMBRE[a] for a in algs], exp, color=[GRIS[a] for a in algs], edgecolor="black",
                  hatch=None)
    for barra, a in zip(b, algs):
        barra.set_hatch(TRAMA[a])
    ax[0].set_ylabel("Nodos expandidos (mediana)")
    for i, v in enumerate(exp):
        ax[0].text(i, v + 80, es(v, 0), ha="center", fontsize=11)
    ax[0].set_title("a) Trabajo por consulta")
    med = [R["e1"][a]["ms_mediana"] for a in algs]
    p = [R["e1"][a]["ms_p95"] for a in algs]
    x = range(len(algs))
    ax[1].bar([i - 0.2 for i in x], med, 0.4, color="#7f7f7f", edgecolor="black", label="Mediana")
    ax[1].bar([i + 0.2 for i in x], p, 0.4, color="white", edgecolor="black", hatch="//", label="p95")
    ax[1].set_xticks(list(x))
    ax[1].set_xticklabels([NOMBRE[a] for a in algs])
    ax[1].set_ylabel("Tiempo de consulta (ms)")
    for i, v in enumerate(med):
        ax[1].text(i - 0.2, v + 0.2, es(v), ha="center", fontsize=10)
    for i, v in enumerate(p):
        ax[1].text(i + 0.2, v + 0.2, es(v), ha="center", fontsize=10)
    ax[1].legend(frameon=False)
    ax[1].set_title("b) Tiempo de consulta")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "g1-algoritmos.png"))
    plt.close(fig)


def g2_mapa(serv, out):
    """Expansion de Dijkstra, A* y ALT para el mismo viaje (evidencia visual)."""
    g = serv.grafo
    o = g.nodo_mas_cercano(3.47, -76.50)
    d = serv.selector.sedes[2]["nodo"]   # S3 (Jamundi)
    fig, axs = plt.subplots(1, 3, figsize=(11, 7.2))
    tipos = {"arteria": 0.9, "autopista": 1.4, "colectora": 0.4}
    segs = {}
    for e in range(g.n_aristas):
        t = clase_visual(g.a_tipo[e])
        if t in tipos:
            segs.setdefault(t, []).append(((g.lon[g.a_origen[e]], g.lon[g.a_destino[e]]), (g.lat[g.a_origen[e]], g.lat[g.a_destino[e]])))
    bfs = serv.estrategias["bfs"].buscar(g, o, d)
    for ax, a in zip(axs, ["dijkstra", "a_estrella", "alt"]):
        for t, lista in segs.items():
            for xs, ys in lista:
                ax.plot(xs, ys, color="#c8c8c8", lw=tipos[t], zorder=1)
        r = serv.estrategias[a].buscar(g, o, d, registrar_orden=True)
        ax.scatter([g.lon[v] for v in r.orden_expansion], [g.lat[v] for v in r.orden_expansion], s=1.2,
                   color="#5b9bd5", alpha=0.6, zorder=2, linewidths=0)
        nodos = r.nodos(g)
        if a == "dijkstra":
            nb = bfs.nodos(g)
            ax.plot([g.lon[v] for v in nb], [g.lat[v] for v in nb], color="black", lw=1.6, ls="--", zorder=3,
                    label="BFS: %s min" % es(bfs.costo_s / 60))
        ax.plot([g.lon[v] for v in nodos], [g.lat[v] for v in nodos], color="black", lw=2.6, zorder=4,
                label="Ruta óptima: %s min" % es(r.costo_s / 60))
        ax.scatter([g.lon[o]], [g.lat[o]], s=70, color="#F68421", edgecolor="black", zorder=5)
        for s in serv.selector.sedes:
            ax.scatter([g.lon[s["nodo"]]], [g.lat[s["nodo"]]], s=60, marker="s", color="#02A554", edgecolor="black", zorder=5)
            ax.text(g.lon[s["nodo"]] + 0.003, g.lat[s["nodo"]], s["id"], fontsize=10, weight="bold", zorder=6)
        ax.set_title("%s\n%s nodos expandidos" % (NOMBRE[a], es(r.expandidos, 0)), fontsize=12)
        ax.set_axis_off()
        ax.set_aspect("equal")
        ax.legend(loc="lower right", fontsize=9, frameon=True)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(os.path.join(out, "g2-mapa-expansion.png"))
    plt.close(fig)
    return {"origen": o, "destino": d, "bfs_min": round(bfs.costo_s / 60, 2)}


def g3(R, out):
    v = R["e3"]["variantes"]
    claves = list(v.keys())
    etiquetas = {"una_pasada": "1 pasada\nDijkstra", "3 x dijkstra": "3 ×\nDijkstra", "3 x bidireccional": "3 ×\nBidirecc.",
                 "3 x a_estrella": "3 × A*", "3 x alt": "3 × ALT"}
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.9))
    med = [v[k]["ms_mediana"] for k in claves]
    colores = ["#F68421" if k == "una_pasada" else "#9e9e9e" for k in claves]
    ax[0].bar([etiquetas[k] for k in claves], med, color=colores, edgecolor="black")
    for i, m in enumerate(med):
        ax[0].text(i, m + 0.2, es(m), ha="center", fontsize=10)
    ax[0].set_ylabel("Tiempo para elegir sede (ms, mediana)")
    ax[0].set_title("a) E3: elegir entre 3 sedes")
    E4 = R["e4"]
    cats = ["Sin caché", "Con caché"]
    vals = [E4["sin_cache_total_s"], E4["con_cache_total_s"]]
    ax[1].bar(cats, vals, color=["#9e9e9e", "#F68421"], edgecolor="black")
    for i, m in enumerate(vals):
        ax[1].text(i, m + 0.02, "%s s" % es(m, 2), ha="center", fontsize=10)
    ax[1].set_ylabel("Tiempo total de 1.000 consultas (s)")
    ax[1].set_title("b) E4: caché (aciertos %s %%)" % es(E4["tasa_aciertos_pct"]))
    fig.tight_layout()
    fig.savefig(os.path.join(out, "g3-sedes-cache.png"))
    plt.close(fig)


def g4(R, out):
    con, sin = R["e4"]["cierre_con_observer"], R["e4"]["cierre_sin_observer"]
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.9))
    vals = [sin["rutas_obsoletas_servidas"], con["rutas_obsoletas_servidas"]]
    ax[0].bar(["Caché sin Observer", "Caché con Observer"], vals, color=["#4d4d4d", "#F68421"], edgecolor="black")
    for i, m in enumerate(vals):
        ax[0].text(i, m + 0.8, str(m), ha="center", fontsize=12, weight="bold")
    ax[0].set_ylabel("Rutas obsoletas servidas\n(de 100 consultas)")
    ax[0].set_title("a) E4: cierre de un tramo de autopista")
    for a, mk in (("dijkstra", "o"), ("bidireccional", "s"), ("a_estrella", "^"), ("alt", "D")):
        pts = [x for x in R["e5"]["consulta"] if x["algoritmo"] == a]
        ax[1].plot([x["nodos"] for x in pts], [x["ms_mediana"] for x in pts], marker=mk, color=GRIS[a] if a != "bidireccional" else "#7f7f7f",
                   ls="-" if a != "bidireccional" else "--", lw=2, label=NOMBRE[a])
    ax[1].set_xscale("log")
    ax[1].set_yscale("log")
    ax[1].set_xlabel("Nodos del grafo (escala log)")
    ax[1].set_ylabel("Consulta, mediana (ms, log)")
    ax[1].set_title("b) E5: escala del grafo")
    ax[1].legend(frameon=False, fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "g4-cierre-escala.png"))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grafo", default=None)
    ap.add_argument("--salida", default=os.path.join(RAIZ, "docs", "figuras"))
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    R = json.load(open(os.path.join(RAIZ, "bench", "resultados", "resumen.json"), encoding="utf-8"))
    g1(R, a.salida)
    info = g2_mapa(ServicioRutas(cargar_grafo(a.grafo)), a.salida)
    g3(R, a.salida)
    g4(R, a.salida)
    json.dump(info, open(os.path.join(RAIZ, "bench", "resultados", "figura_mapa.json"), "w"))
    print("Figuras en", a.salida, info)


if __name__ == "__main__":
    main()
