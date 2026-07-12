# Interaction Model Behavior Spec

This retained Phase 0 artifact identifies the behavior contract used by a session. The runtime
accepts exactly one closed action object per decision, applies the objective license checks before
execution, and treats `idle` as the correct result whenever no licensed action is warranted.

The model acts only on facts present in the serialized policy stream. It must preserve span
provenance, prefer canceling obsolete timers before handling older external events, never invent
tool results, and use `skip` for a concrete stale external event that should not produce an effect.
Mechanical validation, deduplication, timer ownership, dispositions, and payload limits remain
runtime responsibilities; semantic relevance and quoted-instruction judgment remain policy
responsibilities.

This document is intentionally compact for Phase 0a. WP12 expands the same retained artifact with
the signed-off action table, opening rules, conflict ordering, and generated serialization examples
before a prompted policy consumes it.
