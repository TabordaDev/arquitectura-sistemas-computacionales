# Taller Sesión 12 · Observabilidad, trazabilidad y resiliencia · HospitValle-Cloud (S641B)

Código del taller guiado de la Sesión 12 de Arquitectura de Sistemas Computacionales (UNIAJC).

| Archivo | Ejercicio | Qué hace |
|---|---|---|
| `traza_hospitvalle.py` | Fase B / Ejercicio 1 | Traza de 5 spans (ambulancia → Edge MQTT → API Gateway → ingesta → TimescaleDB) con OpenTelemetry |
| `ingesta_service.py` | Ejercicio 1 (paso 1.5) | Microservicio Flask que extrae e inyecta el `traceparent`; `--demo` lo prueba sin base de datos |
| `calculos_sla_uci.py` | Ejercicios 1 y 2 | Root Span, error budget 99,999 %, serie vs. paralelo y Ley de Little |
| `circuit_breaker_uci.py` | Ejercicio 2 (paso 2.1) | Circuit Breaker UCI → IA en nube con reloj simulado |
| `bulkhead_uci.py`, `bulkhead-uci.yaml` | Ejercicio 2 (paso 2.4) | Bulkhead con pools de hilos y con cgroups/Kubernetes |
| `backoff_jitter.py` | Ejercicio 3 | Backoff sin jitter, con jitter fijo y Full Jitter; Token Bucket; genera `grafica_backoff.png` |

## Cómo correrlo (Windows)

```
python -m venv venv-otel
venv-otel\Scripts\activate
pip install -r requirements.txt
python traza_hospitvalle.py
python ingesta_service.py --demo
python calculos_sla_uci.py
python circuit_breaker_uci.py
python bulkhead_uci.py
python backoff_jitter.py
```

Integrantes: Sebastián Martínez Rodríguez, Ángel Isaac Castillo Cuesta, Juan David Taborda Cruz, Joel Mina Orejuela.
