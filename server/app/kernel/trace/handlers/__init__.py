"""Trace-related outbox hooks.

Wave C execution-fact subscriptions live under ``app.kernel.observability.handlers`` so
kernel trace models stay free of consumer orchestration.
"""
