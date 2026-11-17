# ingesta_service.py - Ejercicio 1, paso 1.5 (Sesión 12)
# Microservicio de ingesta de HospitValle: recibe la telemetría de una ambulancia,
# EXTRAE el traceparent que manda el API Gateway, crea su propio span y lo INYECTA
# hacia la base de datos (como comentario SQL, estilo sqlcommenter).
#
# En producción escribe en TimescaleDB (PostgreSQL) con psycopg2.
# Para probarlo en el PC sin base de datos, el modo demo usa SQLite en memoria:
#   python ingesta_service.py --demo
# El demo simula al API Gateway: manda una petición con un traceparent conocido y
# verifica que el trace_id del log y de la respuesta sea el mismo que llegó.
import json
import logging
import os
import sqlite3
import sys

from flask import Flask, request
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

trace.set_tracer_provider(TracerProvider(resource=Resource.create({
    "service.name": "ingesta-service",
    "service.namespace": "hospitvalle-ambulancias",
})))
tracer = trace.get_tracer("ingesta-service")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("ingesta")

DSN = os.getenv("TIMESCALE_DSN")          # p. ej. "host=timescaledb dbname=telemetria user=ingesta"
if DSN:
    import psycopg2                       # solo se necesita con la base de datos real
else:
    BD_DEMO = sqlite3.connect(":memory:", check_same_thread=False)
    BD_DEMO.execute("CREATE TABLE telemetria (ambulancia_id TEXT, fc INTEGER, spo2 INTEGER)")


def guardar(sql, valores):
    """Ejecuta el INSERT en TimescaleDB (real) o en SQLite (demo)."""
    if DSN:
        with psycopg2.connect(DSN) as cn, cn.cursor() as cur:
            cur.execute(sql, valores)
    else:
        BD_DEMO.execute(sql.replace("%s", "?"), valores)


@app.post("/telemetria")
def recibir():
    # 1. extraer el traceparent entrante. Se pasa request.headers directo (no dict(...)):
    #    Flask entrega la llave como "Traceparent" y un dict normal distingue mayúsculas,
    #    así que con dict(request.headers) el contexto se perdía y nacía una traza nueva.
    ctx = extract(request.headers)
    with tracer.start_as_current_span("ingesta.procesar", context=ctx,
                                      kind=trace.SpanKind.SERVER) as span:
        trace_id = format(span.get_span_context().trace_id, "032x")
        d = request.get_json()
        span.set_attribute("ambulancia.id", d["ambulancia_id"])
        with tracer.start_as_current_span("timescaledb.insert",
                                          kind=trace.SpanKind.CLIENT):
            carrier = {}
            # 2. inyectar el contexto del span hijo (el de la BD)
            inject(carrier)
            sql = (f"/*traceparent='{carrier['traceparent']}'*/ "
                   "INSERT INTO telemetria VALUES (%s,%s,%s)")
            guardar(sql, (d["ambulancia_id"], d["fc"], d["spo2"]))
        # 3. log estructurado en JSON con el mismo trace_id -> correlaciona log y traza
        log.info(json.dumps({"level": "INFO", "service": "ingesta-service",
                             "msg": "guardada", "trace_id": trace_id,
                             "sql_traceparent": carrier["traceparent"]}))
    return {"trace_id": trace_id}, 201


if __name__ == "__main__":
    if "--demo" in sys.argv:
        traceparent_gateway = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        print(">> El API Gateway envía:", traceparent_gateway)
        cliente = app.test_client()
        r = cliente.post("/telemetria", json={"ambulancia_id": "AMB-042", "fc": 88, "spo2": 97},
                         headers={"traceparent": traceparent_gateway})
        print(">> Respuesta del servicio:", r.status_code, r.get_json())
        igual = r.get_json()["trace_id"] == traceparent_gateway.split("-")[1]
        print(">> ¿El trace_id se conservó?", "Sí" if igual else "No")
        print(">> Filas guardadas:", BD_DEMO.execute("SELECT * FROM telemetria").fetchall())

        print("\n>> Prueba 2: el gateway descarta el encabezado traceparent")
        r2 = cliente.post("/telemetria", json={"ambulancia_id": "AMB-042", "fc": 90, "spo2": 96})
        print(">> trace_id nuevo:", r2.get_json()["trace_id"],
              "-> es otra traza, se perdió la correlación")
    else:
        app.run(host="0.0.0.0", port=8080)
