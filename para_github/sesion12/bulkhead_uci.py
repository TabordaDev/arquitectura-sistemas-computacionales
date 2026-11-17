# bulkhead_uci.py - Ejercicio 2, paso 2.4 (Sesión 12)
# Bulkhead (mamparos) en el nodo Edge de la UCI: tres compartimentos con pools de hilos
# separados, para que un problema con la IA en la nube no se coma los hilos de las alertas.
#   python bulkhead_uci.py
import threading
import time
from concurrent.futures import ThreadPoolExecutor

pool_alertas = ThreadPoolExecutor(max_workers=16, thread_name_prefix="uci-alerta")
pool_telemetria = ThreadPoolExecutor(max_workers=8, thread_name_prefix="telemetria")
pool_ia = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ia-nube")
cupo_ia = threading.BoundedSemaphore(4 + 20)          # 4 en ejecución + 20 en cola

rechazadas = 0
candado = threading.Lock()


def fallback_local(muestra):
    return f"{muestra}: análisis local"


def llamar_ia(muestra):
    time.sleep(0.8)                                   # la WAN está mal: cada llamada agota el timeout
    return f"{muestra}: timeout"


def enviar_a_ia(muestra):
    global rechazadas
    if not cupo_ia.acquire(blocking=False):   # lleno -> no contagia al resto
        with candado:
            rechazadas += 1
        return fallback_local(muestra)
    # en el sistema real, llamar_ia incluye el Circuit Breaker
    fut = pool_ia.submit(llamar_ia, muestra)
    fut.add_done_callback(lambda _: cupo_ia.release())
    return fut


def alerta_critica(i):
    t0 = time.perf_counter()
    time.sleep(0.002)                                 # procesar una alerta toma ~2 ms
    return (time.perf_counter() - t0) * 1000


if __name__ == "__main__":
    print("Llegan 100 consultas a la IA de golpe (la WAN está caída) y, al mismo tiempo, 50 alertas UCI")
    for i in range(100):
        enviar_a_ia(f"ecg-{i}")
    tiempos = [f.result() for f in [pool_alertas.submit(alerta_critica, i) for i in range(50)]]
    print(f"  Consultas a la IA aceptadas (4 corriendo + 20 en cola): {100 - rechazadas}")
    print(f"  Consultas rechazadas al instante -> fallback local:      {rechazadas}")
    print(f"  Alertas UCI atendidas: {len(tiempos)}, tiempo máximo {max(tiempos):.1f} ms")
    print("  Las alertas no esperaron a la IA: cada compartimento tiene sus propios hilos.")
    for p in (pool_alertas, pool_telemetria, pool_ia):
        p.shutdown(wait=True)
