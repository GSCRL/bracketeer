import subprocess

subprocess.run("uv run isort .")
subprocess.run("uv run black .")

selected_rules = [
    "F401",
    "I001",
    "I002",
    "PERF",
    "YTT",
    "BLE",
    "A",
    "COM",
    "C400",
    "C401",
    "RUF001",
]

rule_2 = []
for r in selected_rules:
    rule_2.append("--select")
    rule_2.append(r)


# Perf401 is triggered by some comprehensions.  Should in the future comment out specifically.  Alas.
subprocess.run(f"uv run ruff check {' '.join(rule_2)} --fix --ignore PERF401")
