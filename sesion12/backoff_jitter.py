# backoff_jitter.py - Ejercicio 3 (Sesión 12)
# 10.000 dispositivos IoT de la red HospitValle se caen a la vez por una tormenta eléctrica
# y reintentan conectarse al API Gateway. Compara tres formas de esperar antes del reintento:
#   1) Backoff exponencial SIN jitter
#   2) Backoff exponencial CON jitter fijo U(0; 0,5 s)  (fórmula de la guía)
#   3) Full Jitter: random(0, min(t_max, t_base * 2^intento))  (mejora propuesta)
# Convención: el primer reintento es intento = 1  ->  base 2, 4, 8, 16 s.
#   python backoff_jitter.py       (necesita: pip install matplotlib)
import random
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

coma = FuncFormatter(lambda x, _: f"{x:g}".replace(".", ","))

T_BASE, T_MAX, JITTER, N = 1.0, 30.0, 0.5, 10_000
C_GATEWAY = 15_000            # TPS que soporta el API Gateway de HospitValle (parámetro de diseño)
BIN_MS = 10                   # se mide la carga en ventanas de 10 ms


def t_wait(intento, modo):
    base = min(T_MAX, T_BASE * 2 ** intento)
    if modo == "sin_jitter":
        return base
    if modo == "jitter_fijo":
        return min(T_MAX, T_BASE * 2 ** intento) + random.uniform(0, JITTER)
    return random.uniform(0, base)                    # full jitter


def llegadas(modo, intento=1):
    return [t_wait(intento, modo) for _ in range(N)]


def analizar(tiempos):
    por_ms = Counter(int(t * 1000) for t in tiempos)
    por_bin = Counter(int(t * 1000) // BIN_MS for t in tiempos)
    tps_bins = {b: c * (1000 / BIN_MS) for b, c in por_bin.items()}
    seg_sobre_c = sum(BIN_MS / 1000 for tps in tps_bins.values() if tps > C_GATEWAY)
    ventana = max(tiempos) - min(tiempos)
    return {
        "pico_ms": max(por_ms.values()),
        "ventana_s": ventana,
        "tps_medio": N / ventana if ventana > 0 else float("inf"),
        "seg_sobre_c": seg_sobre_c,
    }


def token_bucket(tiempos, tasa, rafaga):
    """Gateway con Token Bucket para los dispositivos IoT: cuántas peticiones deja pasar."""
    tokens, ultimo, ok = rafaga, 0.0, 0
    for t in sorted(tiempos):
        tokens = min(rafaga, tokens + (t - ultimo) * tasa)
        ultimo = t
        if tokens >= 1:
            tokens -= 1
            ok += 1
    return ok


random.seed(42)
print("Tabla de los reintentos (sin jitter / con jitter fijo de 0,5 s)")
acum_min = acum_max = 0.0
for i in range(1, 6):
    base = min(T_MAX, T_BASE * 2 ** i)
    acum_min += base
    acum_max += base + JITTER
    print(f"  intento {i}: base {T_BASE * 2 ** i:>4.0f} s -> espera [{base:.1f}; {base + JITTER:.1f}] s"
          f"  acumulado [{acum_min:.1f}; {acum_max:.1f}] s")

print(f"\nReintento 1 de {N:,} dispositivos, gateway de {C_GATEWAY:,} TPS (ventanas de {BIN_MS} ms)")
resultados = {}
for modo, nombre in [("sin_jitter", "Sin jitter"), ("jitter_fijo", "Jitter fijo 0,5 s"),
                     ("full_jitter", "Full Jitter")]:
    ts = llegadas(modo)
    r = analizar(ts)
    resultados[modo] = (nombre, ts, r)
    tasa = ("todas en el mismo ms (10.000.000 TPS instantáneos)" if r["ventana_s"] == 0
            else f"tasa media {r['tps_medio']:,.0f} TPS")
    print(f"  {nombre:<18} pico {r['pico_ms']:>6,} pet/ms | repartidas en {r['ventana_s'] * 1000:>5.0f} ms"
          f" | {tasa} | {r['seg_sobre_c']:.3f} s por encima de C")

print(f"\nVentana mínima para no saturar: W >= N / C = {N:,} / {C_GATEWAY:,} = {N / C_GATEWAY:.3f} s")

print("\nFull Jitter en los 4 reintentos (espera media = base / 2)")
for i in range(1, 5):
    ts = llegadas("full_jitter", i)
    r = analizar(ts)
    print(f"  intento {i}: espera entre 0 y {min(T_MAX, 2 ** i):>2.0f} s -> tasa media {r['tps_medio']:>6,.0f} TPS,"
          f" {r['seg_sobre_c']:.3f} s por encima de C")

# Token Bucket: IoT limitados a 10.000 TPS con ráfaga de 2.000 -> quedan >= 3.000 TPS para ambulancias
AMB, INTERVALO_S = 500, 10
TASA_IOT, RAFAGA_IOT = 10_000, 2_000
print(f"\nCarga de las ambulancias: {AMB} reportes cada {INTERVALO_S} s = {AMB // INTERVALO_S:,} TPS")
print(f"Token Bucket IoT: {TASA_IOT:,} TPS, ráfaga {RAFAGA_IOT:,} -> peor caso en 1 s ="
      f" {TASA_IOT + RAFAGA_IOT:,} TPS; reservado para ambulancias = {C_GATEWAY - TASA_IOT - RAFAGA_IOT:,} TPS")
ts = resultados["jitter_fijo"][1]
ok = token_bucket(ts, TASA_IOT, RAFAGA_IOT)
print(f"Con jitter fijo, el bucket deja pasar {ok:,} de {N:,} en el reintento 1; "
      f"las otras {N - ok:,} reciben 429 y reintentan después")

# ---- Gráfica comparativa del reintento 1 ----
fig, ejes = plt.subplots(1, 3, figsize=(13, 3.8), sharey=False)
for ax, modo in zip(ejes, ["sin_jitter", "jitter_fijo", "full_jitter"]):
    nombre, ts, r = resultados[modo]
    bins = [x / 1000 for x in range(0, 2600, BIN_MS)]
    ax.hist(ts, bins=bins, color={"sin_jitter": "#b23b3b", "jitter_fijo": "#d88a2b",
                                  "full_jitter": "#2e7d4f"}[modo])
    ax.axhline(C_GATEWAY * BIN_MS / 1000, color="#1f3864", ls="--", lw=1.2)
    ax.text(0.02, C_GATEWAY * BIN_MS / 1000 * 1.05, f"capacidad del gateway ({C_GATEWAY:,} TPS)".replace(",", "."),
            fontsize=8, color="#1f3864")
    ax.set_title(nombre, fontsize=11)
    ax.set_xlabel("segundos desde la falla")
    ax.set_xlim(0, 2.6)
    ax.xaxis.set_major_formatter(coma)
    if modo == "sin_jitter":
        ax.set_yscale("log")
        ax.set_ylabel(f"peticiones por ventana de {BIN_MS} ms (escala log)")
    else:
        ax.set_ylabel(f"peticiones por ventana de {BIN_MS} ms")
        ax.set_ylim(0, 260)
plt.tight_layout()
plt.savefig("grafica_backoff.png", dpi=200)
print("\nGráfica guardada en grafica_backoff.png")
