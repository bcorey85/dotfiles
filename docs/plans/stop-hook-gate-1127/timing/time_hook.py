"""Median wall time of a hook run beside a bare Python start. Usage: time_hook.py <script> <payload.json> [runs]"""
import statistics, subprocess, sys, time
script, payload_path = sys.argv[1], sys.argv[2]
runs = int(sys.argv[3]) if len(sys.argv) > 3 else 21
payload = open(payload_path).read()
def median(cmd):
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        subprocess.run(cmd, input=payload, capture_output=True, text=True)
        times.append(time.perf_counter() - start)
    return statistics.median(times) * 1000
print(f"bare python: {median([sys.executable, '-c', 'pass']):.1f} ms; {script.rsplit('/',1)[-1]}: {median([sys.executable, script]):.1f} ms")
