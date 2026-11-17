# circuit_breaker_uci.py - Ejercicio 2, paso 2.1 (Sesión 12)
# Circuit Breaker entre el monitoreo de la UCI de HospitValle y el servicio de IA de
# arritmias en la nube. Implementado a mano (sin librerías) con los parámetros del informe.
#
# Para que corra en segundos, usa un RELOJ SIMULADO: no duerme de verdad, sino que suma
# el tiempo que tardaría cada llamada. Así se ve la secuencia CLOSED -> OPEN -> HALF_OPEN.
#   python circuit_breaker_uci.py
import random
from collections import deque

# ---- Parámetros (tabla del informe, nombres al estilo Resilience4j / Polly) ----
VENTANA = 20               # sliding window COUNT_BASED: últimas 20 llamadas
MIN_LLAMADAS = 10          # no se evalúa la tasa con menos de 10 llamadas
UMBRAL_FALLOS = 0.20       # failure rate threshold
UMBRAL_LENTA_S = 0.500     # slow call duration threshold
UMBRAL_LENTAS = 0.30       # slow call rate threshold
TIMEOUT_S = 0.800          # se corta la espera; cuenta como fallo
ESPERA_OPEN_S = 15.0       # wait duration in open state
PRUEBAS_HALF_OPEN = 3      # permitted calls in half-open

reloj = 0.0                # segundos simulados
estado = "CLOSED"
ventana = deque(maxlen=VENTANA)   # cada elemento: (ok, lenta)
t_apertura = 0.0
pruebas = 0
contador = {"nube": 0, "fallback": 0}


def cambiar(nuevo, motivo):
    global estado
    print(f"  t={reloj:7.2f} s  {estado:>9} -> {nuevo:<9} | {motivo}")
    estado = nuevo


def latencia_wan(escenario):
    """Tiempo que tardaría la IA en la nube según el estado de la WAN."""
    if escenario == "normal":
        return random.uniform(0.020, 0.060) if random.random() > 0.01 else None  # 1 % de errores
    if escenario == "degradada":
        return random.uniform(0.300, 0.900)       # muchas llamadas pasan de 500 ms
    return None                                   # "caida": no responde (timeout)


def fallback_local(muestra):
    contador["fallback"] += 1
    return "análisis local (modelo ligero en el Edge)"


def llamar_ia(muestra, escenario):
    global reloj, t_apertura, pruebas
    if estado == "OPEN":
        if reloj - t_apertura >= ESPERA_OPEN_S:
            cambiar("HALF_OPEN", f"pasaron {ESPERA_OPEN_S:.0f} s, se dejan {PRUEBAS_HALF_OPEN} llamadas de prueba")
            pruebas = 0
        else:
            reloj += 0.00005                       # fail-fast: ~0,05 ms, sin abrir conexión
            return fallback_local(muestra)

    lat = latencia_wan(escenario)
    ok = lat is not None and lat <= TIMEOUT_S
    dur = lat if ok else TIMEOUT_S                 # si falla, esperamos hasta el timeout
    reloj += dur
    contador["nube"] += 1

    if estado == "HALF_OPEN":
        pruebas += 1
        if not ok or dur > UMBRAL_LENTA_S:
            cambiar("OPEN", f"prueba {pruebas} falló ({'timeout' if not ok else 'lenta'})")
            t_apertura = reloj
        elif pruebas == PRUEBAS_HALF_OPEN:
            cambiar("CLOSED", f"las {PRUEBAS_HALF_OPEN} pruebas salieron bien")
            ventana.clear()
        return "IA nube" if ok else fallback_local(muestra)

    ventana.append((ok, dur > UMBRAL_LENTA_S))
    if len(ventana) >= MIN_LLAMADAS:
        tasa_fallos = sum(not o for o, _ in ventana) / len(ventana)
        tasa_lentas = sum(l for _, l in ventana) / len(ventana)
        if tasa_fallos >= UMBRAL_FALLOS or tasa_lentas >= UMBRAL_LENTAS:
            cambiar("OPEN", f"fallos {tasa_fallos:.0%}, lentas {tasa_lentas:.0%} en {len(ventana)} llamadas")
            t_apertura = reloj
    return "IA nube" if ok else fallback_local(muestra)


random.seed(7)
fases = [("normal", 40), ("caida", 60), ("degradada", 20), ("normal", 40)]
print("Simulación del Circuit Breaker UCI -> IA en nube (reloj simulado)")
for escenario, n in fases:
    print(f"\n-- WAN {escenario}: {n} muestras de ECG, una cada 0,5 s --")
    for i in range(n):
        llamar_ia(f"ecg-{i}", escenario)
        reloj += 0.5
print(f"\nLlamadas que sí salieron a la nube: {contador['nube']}")
print(f"Respuestas con el fallback local:  {contador['fallback']}")
print("La UCI nunca se quedó esperando más de 0,8 s por una respuesta.")
