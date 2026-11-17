# traza_hospitvalle.py - Fase B del taller (Sesión 12)
# Simula los 4 saltos de la telemetría de una ambulancia de HospitValle con OpenTelemetry:
#   ambulancia -> broker MQTT (Edge K3s) -> API Gateway mTLS -> servicio de ingesta -> TimescaleDB
# Basado en el script traza_metromio.py de la guía; solo cambian los nombres al proyecto HospitValle.
#
# Uso:
#   python traza_hospitvalle.py          -> muestra los traceparent y una tabla resumen de los 5 spans
#   python traza_hospitvalle.py --json   -> además imprime cada span completo (ConsoleSpanExporter)
import sys
import time

from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (ConsoleSpanExporter, SimpleSpanProcessor,
                                            SpanExporter, SpanExportResult)


class ColectorSpans(SpanExporter):
    """Guarda los spans terminados para imprimir la tabla resumen al final."""
    def __init__(self):
        self.spans = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS


colector = ColectorSpans()
provider = TracerProvider(resource=Resource.create({
    "service.name": "hospitvalle-ingesta",
    "service.namespace": "hospitvalle-ambulancias",   # separa estas trazas de las de la UCI
}))
provider.add_span_processor(SimpleSpanProcessor(colector))
if "--json" in sys.argv:
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("hospitvalle.lab")


def consultar_timescaledb(headers_entrantes: dict):
    ctx = extract(headers_entrantes)                      # 1) EXTRAER el contexto del servicio anterior
    with tracer.start_as_current_span("salto4.timescaledb.insert", context=ctx) as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", "INSERT")
        time.sleep(0.003)                                 # 3 ms


def servicio_ingesta(headers_entrantes: dict):
    ctx = extract(headers_entrantes)                      # traceparent que llega del API Gateway
    with tracer.start_as_current_span("salto3.ingesta-service", context=ctx):
        time.sleep(0.045)                                 # 45 ms
        headers_salida = {}
        inject(headers_salida)                            # 2) INYECTAR para la llamada a la BD
        print(">> traceparent hacia la BD:     ", headers_salida["traceparent"])
        consultar_timescaledb(headers_salida)


with tracer.start_as_current_span("root.ambulancia-telemetria") as root:
    root.set_attribute("ambulancia.id", "AMB-042")
    with tracer.start_as_current_span("salto1.edge-mqtt-k3s"):
        time.sleep(0.012)                                 # 12 ms
    with tracer.start_as_current_span("salto2.api-gateway-mtls"):
        time.sleep(0.008)                                 # 8 ms
    h = {}
    inject(h)
    print(">> traceparent hacia ingesta:   ", h["traceparent"])
    servicio_ingesta(h)

provider.shutdown()

# ---- Tabla resumen: un renglón por span ----
spans = sorted(colector.spans, key=lambda s: s.start_time)
t0 = min(s.start_time for s in spans)
print("\nResumen de la traza (todos los spans deben tener el mismo trace_id)")
print(f"{'span':<28}{'trace_id':<34}{'span_id':<18}{'parent_id':<18}{'inicio':>8}{'duración':>10}")
for s in spans:
    c = s.get_span_context()
    padre = format(s.parent.span_id, "016x") if s.parent else "(raíz)"
    ini = (s.start_time - t0) / 1e6
    dur = (s.end_time - s.start_time) / 1e6
    print(f"{s.name:<28}{format(c.trace_id, '032x'):<34}{format(c.span_id, '016x'):<18}"
          f"{padre:<18}{ini:>6.1f}ms{dur:>8.1f}ms")
