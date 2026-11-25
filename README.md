# valle-vital-rutas · Ruta a la sede óptima

Prototipo de la **Actividad 6 (AA2 U3) · Navegando mareas** de Arquitectura de software (Tecnológica del Oriente, 20262).
Continúa el caso **Valle Vital** (Act. 2 y Act. 4): cuando el triaje prioriza a un paciente, el sistema
recomienda la **sede con cupo a la que se llega en menor tiempo** y la ruta, y la recalcula si se cierra una vía.

> Valle Vital es una entidad ficticia. Sedes, bases y coordenadas son inventadas. El sistema **recomienda**;
> no despacha ambulancias ni reemplaza al CRUE ni a la regulación médica. No hay tráfico en tiempo real:
> la congestión es un factor simulado por tramo.

Equipo: Sebastián Charria Muñoz y Esteban Charria Muñoz · Repositorio: <https://github.com/SebastianCharriaTO/valle-vital-rutas>

## Qué hay

| Módulo | Patrón | Qué hace |
|---|---|---|
| `rutas/estrategias.py` | **Strategy** + **Iterator** | `EstrategiaRuta` con `BFS`, `Dijkstra`, `DijkstraBidireccional`, `AEstrella`, `ALT` y `DijkstraMultidestino`. Cada búsqueda se recorre con un `ExpansionIterator` (nodos expandidos) |
| `rutas/cache.py` | **Proxy** + **Cache-Aside** | `RutaCacheProxy`: misma interfaz que la estrategia, TTL, LRU e índice vía → claves |
| `rutas/eventos.py` | **Observer** | `BusEventosViales` notifica a la caché (invalida) y a `RutasActivas` (recalcula) |
| `rutas/comandos.py` | **Command** | `CerrarViaCmd`, `ReabrirViaCmd`, `CalcularRutaCmd`, `InvocadorComandos` (historial y deshacer) |
| `rutas/ruta.py` | **Composite** | `Tramo` y `RutaCompuesta` (base → paciente → sede) con `tiempo_s()` e `instrucciones()` |
| `rutas/repositorio.py` | Puertos y adaptadores | `GrafoSinteticoAdapter` (semilla fija) y `GrafoArchivoAdapter` (`datos/grafo_cali.json`) |
| `rutas/sedes.py` | — | `SelectorSede`: consulta uno a varios |
| `rutas/servicio.py`, `rutas/api.py`, `rutas/vista.py` | — | Ensamble, API HTTP (biblioteca estándar) y vista web con el mapa en SVG |
| `bench/` | — | Experimentos E1–E6, CSV, `resumen.json` y gráficos |
| `docs/uml/` | — | Diagramas como código (Graphviz y matplotlib) y sus PNG en `docs/figuras/` |

## Requisitos

- **Python 3.8 o superior.** El motor, la API y los experimentos usan solo la biblioteca estándar.
- `matplotlib` para los gráficos; `pytest` y `networkx==3.1` (oráculo) para las pruebas.
- Solo para descargar el mapa real: **Python ≥ 3.11** con OSMnx 2.x (ver abajo).

```bash
python3 -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Ejecutar

```bash
python -m rutas.api                 # http://127.0.0.1:8080/mapa
python -m pytest -q                 # 15 pruebas (optimalidad contra NetworkX, heurísticas admisibles, Command, Observer, reproducibilidad)
```

Ejemplos de la API:

```bash
curl -X POST localhost:8080/api/sedes/mejor -H "Content-Type: application/json" -d '{"origen":"P07","especialidad":"Pediatria"}'
curl -X POST localhost:8080/api/rutas       -H "Content-Type: application/json" -d '{"origen":"P07","destino":"S2","algoritmo":"a_estrella"}'
curl -X POST localhost:8080/api/ambulancia  -H "Content-Type: application/json" -d '{"base":"B1","paciente":"P07","especialidad":"Medicina general"}'
curl -X POST localhost:8080/api/vias/A79/cerrar ; curl -X POST localhost:8080/api/comandos/deshacer
curl localhost:8080/api/metricas
```

`origen` y `destino` aceptan `P01`–`P50` (puntos de demanda), `S1`–`S3` (sedes), `B1` (base), un id de nodo o `"lat,lon"`.
`algoritmo`: `bfs`, `dijkstra`, `bidireccional`, `a_estrella` o `alt` (por defecto).

## Mapa: ciudad sintética o Cali real (OpenStreetMap)

Mientras no exista `datos/grafo_cali.json`, todo usa una **ciudad sintética reproducible** (semilla 42): una rejilla
de unos 10.000 nodos con la extensión de Cali–Jamundí, arterias cada ~2,2 km (60 km/h), colectoras (40 km/h),
locales de sentido único (25 km/h), una autopista diagonal (80 km/h), un río que solo cruzan las arterias y un factor
de congestión por tramo. **Las cifras actuales del informe salen de esta ciudad sintética.**

Para usar el **mapa real de Cali**, un integrante corre una vez, en su PC:

```bash
python3.11 -m venv .venv-osm && . .venv-osm/bin/activate
pip install -r requirements-descarga.txt
python scripts/descargar_mapa_cali.py          # crea datos/grafo_cali.json (1-3 min)
```

Luego, con el entorno normal (Python 3.8+), se regeneran resultados y figuras:

```bash
python -m bench.experimentos --grafo datos/grafo_cali.json
python bench/graficos.py --grafo datos/grafo_cali.json
python -m rutas.api                              # la vista ya usa el mapa real
```

Con el mapa real, los tiempos de viaje salen de las velocidades que imputa OSMnx (sin congestión simulada).
Datos © OpenStreetMap contributors, licencia ODbL (https://www.openstreetmap.org/copyright). La descarga es
puntual (una sola vez), como pide la política de uso de la Overpass API.

## Experimentos

Los resultados son reproducibles entre versiones de Python (3.8 a 3.13): coordenadas y longitudes se redondean y las distancias usan `math.sqrt`, así que el grafo, los landmarks de ALT y los nodos expandidos son idénticos; solo cambian los milisegundos según el equipo.

```bash
python -m bench.experimentos        # ~1,5 min; escribe bench/resultados/*.csv y resumen.json
python bench/graficos.py            # docs/figuras/g1..g4
python docs/uml/generar_uml.py      # docs/figuras/u1..u4 (requiere Graphviz `dot`)
```

| Exp. | Pregunta | Archivo |
|---|---|---|
| E1 | ¿Cuánto trabajo y tiempo cuesta cada estrategia? (200 pares, 5 repeticiones) | `e1_algoritmos.csv` |
| E2 | ¿Cuánto peor es la ruta de BFS? | derivado de E1 |
| E3 | ¿Cómo elegir entre 3 sedes: una pasada o una búsqueda por sede? | `e3_uno_a_varios.csv` |
| E4 | ¿Cuánto acelera la caché y cuántas rutas obsoletas sirve tras un cierre, con y sin Observer? | `e4_cache.csv` |
| E5 | ¿Cómo escala con 2.500, 10.000 y 40.000 nodos? Costo del preproceso de ALT | `e5_escala.csv` |
| E6 | Carga HTTP: 8 clientes, 400 solicitudes, con y sin caché | `resumen.json` |

## Equipo y commits

Cada integrante sube su parte desde su propio equipo y con su propia cuenta:

- **Sebastián Charria Muñoz** (líder y programador del prototipo): motor de búsqueda, patrones y API.
- **Esteban Charria Muñoz** (diseño UML, patrones y evaluación de pruebas): pruebas, experimentos, diagramas y descarga del mapa.
