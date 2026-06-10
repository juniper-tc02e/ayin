"""Scan orchestrator (M1-1, PRD §10.1).

The scan is an asynchronous, resumable pipeline:

    queued → gated → running → resolving → scoring → done | failed | held

Design: all state lives in Postgres (Scan + ConnectorJob rows); the engine
(``engine.py``) is pure functions over that state; Celery tasks (``tasks.py``)
are thin wrappers. That keeps the orchestrator testable without a broker and
makes the Temporal swap (Phase 1) an interface change, not a rewrite.
"""
