""" metrics

Metrics hooks (Prometheus/OTel).
"""

from prometheus_client import Counter, Histogram, Gauge

# Run metrics
run_count = Counter(
    "soit_runs_total",
    "Total number of runs",
    ["mode", "status", "tenant_id"],
)

run_duration = Histogram(
    "soit_run_duration_seconds",
    "Run duration in seconds",
    ["mode", "tenant_id"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
)

# Step metrics
step_count = Counter(
    "soit_steps_total",
    "Total number of steps",
    ["step_type", "status", "tenant_id"],
)

step_duration = Histogram(
    "soit_step_duration_seconds",
    "Step duration in seconds",
    ["step_type", "tenant_id"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
)

# Cost metrics
tokens_total = Counter(
    "soit_tokens_total",
    "Total tokens used",
    ["type", "tenant_id"],
)

cost_total = Counter(
    "soit_cost_total",
    "Total cost in currency units",
    ["resource_type", "tenant_id"],
)

# Active runs gauge
active_runs = Gauge(
    "soit_active_runs",
    "Number of active runs",
    ["mode", "tenant_id"],
)
