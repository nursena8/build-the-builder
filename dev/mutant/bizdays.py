"""Business-day helper for the mutant brief. Mon-Fri except the mutant holiday list."""
import datetime as dt
HOLIDAYS = {"2026-10-20", "2026-11-03", "2026-11-19", "2026-12-24", "2027-01-04"}
def is_bd(d): return d.weekday() < 5 and d.isoformat() not in HOLIDAYS
def nth_bd_after(d, n, trace=None):
    c, x = 0, d
    while c < n:
        x += dt.timedelta(days=1)
        if is_bd(x):
            c += 1
            if trace is not None: trace.append(f"  bd {c:2d}: {x.strftime('%a')} {x.isoformat()}")
        elif trace is not None: trace.append(f"  skip  : {x.strftime('%a')} {x.isoformat()} ({'holiday' if x.weekday() < 5 else 'weekend'})")
    return x
if __name__ == "__main__":
    now = dt.date(2026, 10, 14)
    print("now =", now.strftime("%a"), now)
    for name, n in (("late band (5th bd)", 5), ("early band (10th bd)", 10)):
        tr = []; d = nth_bd_after(now, n, tr); print(name, "->", d.strftime("%a"), d); print("\n".join(tr))
    print("26 Oct is bd:", is_bd(dt.date(2026, 10, 26)), "| 15 Oct is bd:", is_bd(dt.date(2026, 10, 15)), "| 16 Oct is bd:", is_bd(dt.date(2026, 10, 16)))
    weeks = {}
    for h in sorted(HOLIDAYS):
        d = dt.date.fromisoformat(h); weeks.setdefault(d.isocalendar()[:2], []).append(h)
    print("holidays:", {h: dt.date.fromisoformat(h).strftime("%a") for h in sorted(HOLIDAYS)}, "| ayni hafta cakismasi:", [v for v in weeks.values() if len(v) > 1] or "yok")
