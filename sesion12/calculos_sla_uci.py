# calculos_sla_uci.py - Ejercicios 1 y 2 (Sesión 12)
# Verifica los cálculos del informe: latencia del Root Span, error budget del SLA 99,999 %,
# disponibilidad en serie vs. paralelo y Ley de Little.
#   python calculos_sla_uci.py

# ---- Ejercicio 1: Root Span (saltos en secuencia) ----
saltos = {"Edge MQTT K3s": 12, "API Gateway mTLS": 8, "Ingesta Service": 45, "TimescaleDB": 3}
t_root = sum(saltos.values())
print(f"Root Span = {' + '.join(map(str, saltos.values()))} = {t_root} ms")
for n, t in saltos.items():
    print(f"  {n:<18} {t:>3} ms -> {t / t_root:6.1%} de la latencia")
print(f"  Con +2 ms de red entre los 4 saltos: {t_root} + 4 x 2 = {t_root + 8} ms")

# ---- Ejercicio 2.2: presupuesto de error del SLA 99,999 % ----
U = 1 - 0.99999
for periodo, minutos in [("Año", 525_600), ("Mes (30 d)", 43_200), ("Semana", 10_080), ("Día", 1_440)]:
    m = minutos * U
    print(f"{periodo:<11} {minutos:>7,} min x 1e-5 = {m:.4f} min = {m * 60:.2f} s")

# ---- Ejercicio 2.3: serie vs. paralelo ----
A_L, A_W, A_C, A_F = 0.999995, 0.999, 0.9995, 0.9999
A_remota = A_W * A_C
A_serie = A_L * A_remota
A_func = 1 - (1 - A_remota) * (1 - A_F)
A_total = A_L * A_func
print(f"\nA_remota = {A_W} x {A_C} = {A_remota:.7f}")
print(f"(a) Sin Circuit Breaker: A = {A_serie:.7f} -> caída {(1 - A_serie) * 525_600:,.0f} min/año"
      f" ({(1 - A_serie) * 8760:.1f} h)  NO cumple")
print(f"(b) Con CB + fallback:   A_func = {A_func:.8f}; A_total = {A_total:.7f}"
      f" -> caída {(1 - A_total) * 525_600:.2f} min/año  {'SÍ' if A_total >= 0.99999 else 'NO'} cumple (< 5,26)")
print(f"Verifique: si A_L = 0,99999 -> A = {0.99999 * A_func:.8f} < 0,99999 -> NO cumple")

# ---- Ley de Little: L = lambda x W ----
lam = 100                       # consultas por segundo de la UCI a la IA
print(f"\nLittle sin CB (timeout W = 5 s):     L = {lam} x 5 = {lam * 5} hilos bloqueados")
print(f"Little con CB OPEN (W = 0,05 ms):    L = {lam} x 0,00005 = {lam * 0.00005:.3f} hilos")
print(f"Little con timeout de 800 ms (CB CLOSED, WAN mala): L = {lam} x 0,8 = {lam * 0.8:.0f} hilos")
