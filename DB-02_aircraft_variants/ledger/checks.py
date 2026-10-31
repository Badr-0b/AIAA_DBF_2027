"""Orchestrator hand checks (independent of the stream code): first-principles numbers
the storyline relies on. Run: PYTHONDONTWRITEBYTECODE=1 python ledger/checks.py"""
import math

G = 9.80665
RHO = 1.064          # design density, kg/m^3 (proposal/data/numbers.tex \nRho)
B = 1.82             # design span, m
STRAIGHTS = 609.6    # m of straights per lap (2 x 304.8 m)


def raymer_e(ar):
    return 1.78 * (1 - 0.045 * ar ** 0.68) - 0.64


def lap(V, bank_deg):
    r = V ** 2 / (G * math.tan(math.radians(bank_deg)))
    turns = 4 * math.pi * r
    return r, turns, STRAIGHTS + turns, (STRAIGHTS + turns) / V


def drag(m, V, S, cd0, e, n):
    q = 0.5 * RHO * V ** 2
    cl = n * m * G / (q * S)
    ar = B ** 2 / S
    cdi = cl ** 2 / (math.pi * ar * e)
    return q * S * cd0, q * S * cdi, cl


def m2_reference():
    # s6 reference: 0.9 m2, 14.42 kg, 29.5 m/s, 70 deg; CD0 = 0.0086 + 0.013/S
    S, m, V, bank = 0.9, 14.42, 29.5, 70.0
    e = raymer_e(B ** 2 / S)
    cd0 = 0.0086 + 0.013 / S
    n = 1 / math.cos(math.radians(bank))
    r, turns, L, t = lap(V, bank)
    d0s, dis, cls = drag(m, V, S, cd0, e, 1.0)
    d0t, dit, clt = drag(m, V, S, cd0, e, n)
    straight_len = L - turns
    shaft_mean = ((d0s + dis) * straight_len + (d0t + dit) * turns) / L * V
    print(f"REF-D01 M2: AR {B**2/S:.2f}, Raymer e {e:.3f}, CD0 {cd0:.4f}, n {n:.2f}, r {r:.1f} m")
    print(f"  lap {L:.0f} m, {t:.1f} s model, {t*1.15:.1f} s flown; turns {turns/L:.0%} of distance")
    print(f"  straight: D {d0s+dis:.1f} N (induced {dis/(d0s+dis):.0%}), CL {cls:.3f}")
    print(f"  turn:     D {d0t+dit:.1f} N (induced {dit/(d0t+dit):.0%}), CL {clt:.3f}")
    t5 = 5 * t * 1.15 + 8.0
    for eta in (0.58, 0.645):
        wh = shaft_mean / eta * t5 / 3600
        print(f"  shaft mean {shaft_mean:.0f} W; eta {eta}: battery {shaft_mean/eta:.0f} W, "
              f"{wh:.1f} Wh over {t5:.0f} s (usable 80 Wh)")
    # induced-energy share
    e_ind = dis * straight_len + dit * turns
    e_tot = (d0s + dis) * straight_len + (d0t + dit) * turns
    print(f"  induced share of lap propulsive energy: {e_ind/e_tot:.0%}")
    for de in (0.85, 1.0, 1.15, 1.3):
        e2 = e * de
        _, dis2, _ = drag(m, V, S, cd0, e2, 1.0)
        _, dit2, _ = drag(m, V, S, cd0, e2, n)
        tot2 = (d0s + dis2) * straight_len + (d0t + dit2) * turns
        print(f"    e x{de:.2f}: lap energy x{tot2/e_tot:.3f}")


def stall_caps():
    print("\nStall-limited M2 gross (kg) = 0.5 rho Vs^2 CLmax S / g")
    for vs in (13, 14, 15):
        for cl in (1.45, 1.6, 1.9, 2.2):
            ws = 0.5 * RHO * vs ** 2 * cl
            row = "  ".join(f"S{S:.1f}:{ws*S/G:5.1f}" for S in (0.8, 0.9, 1.0, 1.1, 1.2, 1.3))
            print(f"  Vs {vs} CLmax {cl}: W/S {ws:5.1f} N/m2 | {row}")


def m3_cliffs():
    print("\nM3 laps in 300 s: take-off 8 s + N laps + stow (stow counted)")
    for lap_s in (33, 35, 37, 39.1, 41, 43):
        for stow in (3, 8, 12, 15):
            n = int((300 - 8 - stow) // lap_s)
            print(f"  lap {lap_s:5.1f} s stow {stow:2d} s -> {n} laps", end=";")
        print()
    print("  products: 7 x 3.4 =", 7 * 3.4, "| 7 x 4.4 =", round(7 * 4.4, 1),
          "| 6 x 5.4 =", round(6 * 5.4, 1), "| anchors aggr 27, exp 20.25")


def gm():
    print("\nGM: Ws x 1.524 m vs anchors (exp 9.14, aggr 12.19 kg m)")
    for ws in (3.4, 4.4, 6, 8, 10):
        p = ws * 1.524
        print(f"  {ws:4.1f} kg -> {p:5.2f} kg m; GM exp {0.5+min(1, p/9.14):.2f}, "
              f"aggr {0.5+min(1, p/12.19):.2f}")


def m2_rates():
    print("\nM2 W/t (kg/s) vs anchors (exp 0.0673, aggr 0.0898)")
    for W, t in ((8.0, 207), (9.0, 207), (10.0, 215), (11.5, 220), (13.0, 230)):
        r = W / t
        print(f"  W {W:4.1f} kg in {t} s: {r:.4f} kg/s -> M2 exp {1+min(1, r/0.0673):.2f} "
              f"aggr {1+min(1, r/0.0898):.2f}")


if __name__ == "__main__":
    m2_reference()
    stall_caps()
    m3_cliffs()
    gm()
    m2_rates()
