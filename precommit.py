import subprocess

subprocess.run("uv run isort .")
subprocess.run("uv run black .")
subprocess.run("uv run ruff check --select 'F401 I001 I002 PERF*' --fix")
