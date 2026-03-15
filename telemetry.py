"""OpenTelemetry setup — traces and metrics exported via OTLP."""

import os
import logging

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

_logger = logging.getLogger(__name__)

_tracer: trace.Tracer | None = None
_meter: metrics.Meter | None = None

# Metrics handles (initialised in init())
agent_runs: metrics.Counter | None = None
agent_errors: metrics.Counter | None = None
agent_run_duration: metrics.Histogram | None = None
tasks_implemented: metrics.Counter | None = None
prs_opened: metrics.Counter | None = None
prs_reviewed: metrics.Counter | None = None
claude_calls: metrics.Counter | None = None
claude_call_duration: metrics.Histogram | None = None


def init() -> None:
    """Initialise OTel tracing and metrics. Safe to call if OTLP endpoint is not set."""
    global _tracer, _meter
    global agent_runs, agent_errors, agent_run_duration
    global tasks_implemented, prs_opened, prs_reviewed
    global claude_calls, claude_call_duration

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        _logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set — telemetry disabled")
        return

    resource = Resource.create({"service.name": "sweat"})

    # Traces
    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tp)
    _tracer = trace.get_tracer("sweat")

    # Metrics
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=15_000)
    mp = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(mp)
    _meter = metrics.get_meter("sweat")

    agent_runs = _meter.create_counter("sweat.agent.runs", description="Total agent run_once() cycles")
    agent_errors = _meter.create_counter("sweat.agent.errors", description="Agent run_once() errors")
    agent_run_duration = _meter.create_histogram("sweat.agent.run_duration_s", unit="s", description="Duration of agent run_once()")
    tasks_implemented = _meter.create_counter("sweat.tasks.implemented", description="Tasks successfully implemented")
    prs_opened = _meter.create_counter("sweat.prs.opened", description="PRs opened")
    prs_reviewed = _meter.create_counter("sweat.prs.reviewed", description="PRs reviewed")
    claude_calls = _meter.create_counter("sweat.claude.calls", description="Claude SDK invocations")
    claude_call_duration = _meter.create_histogram("sweat.claude.call_duration_s", unit="s", description="Duration of Claude SDK calls")

    _logger.info(f"OpenTelemetry initialised — exporting to {endpoint}")


def tracer() -> trace.Tracer:
    """Return the sweat tracer, or a no-op tracer if telemetry is disabled."""
    return _tracer or trace.get_tracer("sweat")
