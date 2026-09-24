""" metrics

Metrics hooks (Prometheus/OTel).
"""

from prometheus_client import Counter, Gauge, Histogram

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

# Transactional outbox metrics (exported by the dedicated dispatcher process)
outbox_dispatch_attempts = Counter(
    "soit_outbox_dispatch_attempts_total",
    "Total outbox dispatch outcomes",
    ["outcome"],
)

outbox_pending = Gauge(
    "soit_outbox_pending",
    "Number of pending outbox events",
)

outbox_retries = Gauge(
    "soit_outbox_retries",
    "Number of pending outbox events that have been retried",
)

outbox_dead_letters = Gauge(
    "soit_outbox_dead_letters",
    "Number of terminally failed outbox events",
)

outbox_oldest_pending_age = Gauge(
    "soit_outbox_oldest_pending_age_seconds",
    "Age in seconds of the oldest pending outbox event",
)

outbox_delivery_latency = Histogram(
    "soit_outbox_delivery_latency_seconds",
    "Time from event occurrence to successful outbox delivery",
    buckets=[0.1, 0.5, 1.0, 5.0, 15.0, 30.0, 60.0, 300.0, 1800.0],
)

# Durable interaction worker (exported by the response-worker process, or by
# the API when it hosts the worker loop)
interaction_queue_wait = Histogram(
    "soit_interaction_queue_wait_seconds",
    "Time an accepted interaction waited for a worker slot (claim row age at execution start)",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

interaction_execution_duration = Histogram(
    "soit_interaction_execution_seconds",
    "Wall time one worker slot spent on an interaction",
    ["outcome"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)

interactions_in_flight = Gauge(
    "soit_interactions_in_flight",
    "Interactions this worker process is executing right now",
)

interaction_claims = Counter(
    "soit_interaction_claims_total",
    "Interactions claimed, split by whether the claim recovered an expired lease",
    ["kind"],
)
