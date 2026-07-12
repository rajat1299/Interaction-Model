"""Deterministic scripted tool adapter backed by the durable request ledger."""

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from pydantic import ValidationError

from im.canonical_json import (
    TimJsonValue,
    canonicalize_tim_json,
    normalize_tim_json,
    parse_tim_json,
)
from im.schema.actions import LookupArgs
from im.schema.common import ToolName, ToolResultStatus
from im.store import (
    DuplicatePendingToolRequestError,
    IdKind,
    PolicyEventDraft,
    Store,
    ToolRequestRecord,
)


class Clock(Protocol):
    """The Phase-0 injected time boundary used by schedulers and fake tools."""

    def monotonic_ns(self) -> int:
        """Return the current monotonic time in nanoseconds."""

    def wall_utc(self) -> datetime:
        """Return the current timezone-aware UTC wall time for audit rows."""

    def sleep_until(self, mono_ns: int) -> Awaitable[None]:
        """Wait until a monotonic deadline (implemented by the production clock)."""


class ToolValidationError(ValueError):
    """Raised when a request does not belong to the closed v1 tool registry."""


@dataclass(frozen=True, slots=True)
class ScriptedToolResult:
    """The complete deterministic outcome configured for one fake request."""

    latency_ms: int
    data: object
    status: ToolResultStatus | str = ToolResultStatus.SUCCEEDED

    def __post_init__(self) -> None:
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, int):
            raise TypeError("tool result latency_ms must be an integer")
        if self.latency_ms < 0:
            raise ValueError("tool result latency_ms must be non-negative")
        try:
            status = ToolResultStatus(self.status)
        except ValueError as error:
            raise ValueError(f"unknown tool result status: {self.status}") from error
        normalized_data = normalize_tim_json(self.data)
        canonicalize_tim_json(normalized_data)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "data", normalized_data)


@dataclass(frozen=True, slots=True)
class ToolResultDelivery:
    """A due scripted result durably appended to ingress, ready for the tick buffer."""

    event_id: str
    request_id: str
    occurred_mono_ns: int
    received_utc: str
    ingress_payload: bytes

    @property
    def payload(self) -> TimJsonValue:
        """Return the canonical result payload without interpreting its opaque data."""
        return parse_tim_json(self.ingress_payload)

    def as_policy_draft(self) -> PolicyEventDraft:
        """Expose the delivered ingress result as the next policy-stream draft."""
        payload = self.payload
        if not isinstance(payload, dict):  # pragma: no cover - store verifies this at delivery.
            raise RuntimeError("tool result ingress payload is not an object")
        return PolicyEventDraft(
            id=self.event_id,
            source="tool",
            kind="result",
            payload=payload,
            occurred_mono_ns=self.occurred_mono_ns,
        )


def _normalize_tool_request(tool: ToolName | str, args: object) -> tuple[ToolName, dict[str, str]]:
    """Validate the frozen v1 registry and return its canonical typed arguments."""
    try:
        normalized_tool = ToolName(tool)
    except ValueError as error:
        raise ToolValidationError(f"unknown tool: {tool}") from error
    # Defensive if a future enum is added without its closed argument schema.
    if normalized_tool is not ToolName.LOOKUP:
        raise ToolValidationError(f"tool is not in registry version 1: {normalized_tool.value}")
    try:
        lookup_args = LookupArgs.model_validate(args)
    except ValidationError as error:
        raise ToolValidationError("invalid lookup args") from error
    return normalized_tool, lookup_args.model_dump(mode="python")


def canonical_tool_key(tool: ToolName | str, args: object) -> str:
    """Return the sole v1 canonical dedup key for a closed tool request.

    The preimage is the closed tool name, one NUL framing byte, then the
    ``tim-json-v1`` canonical argument bytes.  The NUL makes the concatenation
    unambiguous while avoiding a second arbitrary-JSON envelope just for a
    ledger key.  Callers must import this helper rather than recreate it.
    """
    normalized_tool, normalized_args = _normalize_tool_request(tool, args)
    preimage = normalized_tool.value.encode("utf-8") + b"\0" + canonicalize_tim_json(
        normalized_args
    )
    return f"sha256:{sha256(preimage).hexdigest()}"


class ToolAdapter:
    """A fake server whose only results are the explicit scenario scripts supplied to it."""

    def __init__(self, store: Store, clock: Clock) -> None:
        self._store = store
        self._clock = clock
        self._changed = asyncio.Event()
        self._closed = False

    @property
    def pending(self) -> frozenset[str]:
        """Expose pending canonical keys for the license layer's duplicate check."""
        return frozenset(record.canonical_key for record in self._store.pending_tool_requests())

    def request(
        self,
        canonical_tool: ToolName | str,
        args: object,
        *,
        scripted_result: ScriptedToolResult | None = None,
        fact_event_id: str = "",
    ) -> str:
        """Create or reuse a pending request and schedule its explicit fake result.

        ``fact_event_id`` is optional only so WP8 can exercise the adapter in
        isolation; delegate execution supplies the source fact event when it
        exists.  A missing script deliberately yields a zero-latency successful
        ``null`` result rather than calculating any fact.
        """
        normalized_tool, normalized_args = _normalize_tool_request(canonical_tool, args)
        canonical_key = canonical_tool_key(normalized_tool, normalized_args)
        existing = self._store.find_pending_tool_request(canonical_key)
        if existing is not None:
            return existing.request_id
        if not isinstance(fact_event_id, str):
            raise TypeError("fact_event_id must be a string")
        result = scripted_result or ScriptedToolResult(latency_ms=0, data=None)
        now_mono_ns = self._monotonic_ns()
        due_mono_ns = now_mono_ns + result.latency_ms * 1_000_000
        if due_mono_ns > (1 << 63) - 1:
            raise ValueError("tool result due time exceeds SQLite integer range")
        request_id = self._store.allocate_id(IdKind.REQUEST)
        try:
            self._store.create_tool_request(
                request_id=request_id,
                fact_event_id=fact_event_id,
                tool=normalized_tool.value,
                args=normalized_args,
                canonical_key=canonical_key,
                requested_mono_ns=now_mono_ns,
                due_mono_ns=due_mono_ns,
                result_status=result.status,
                result_data=result.data,
            )
        except DuplicatePendingToolRequestError:
            # Separate adapter instances can race through the preceding read.
            duplicate = self._store.find_pending_tool_request(canonical_key)
            if duplicate is None:  # pragma: no cover - only possible on external ledger corruption.
                raise
            return duplicate.request_id
        self._changed.set()
        return request_id

    def deliver_due(self) -> tuple[ToolResultDelivery, ...]:
        """Append every due scripted result as an atomic ingress + ledger delivery."""
        now_mono_ns = self._monotonic_ns()
        received_utc = self._received_utc()
        deliveries: list[ToolResultDelivery] = []
        for request in self._store.due_tool_requests(now_mono_ns):
            ingress_payload = self._result_ingress_payload(request)
            with self._store.transaction():
                event_id = self._store.allocate_id(IdKind.EVENT)
                completed = self._store.deliver_due_tool_request(
                    request_id=request.request_id,
                    event_id=event_id,
                    received_utc=received_utc,
                    received_mono_ns=now_mono_ns,
                    ingress_payload=ingress_payload,
                )
            if completed.result_event_id != event_id:  # pragma: no cover - transaction invariant.
                raise RuntimeError("tool result delivery did not retain its event id")
            deliveries.append(
                ToolResultDelivery(
                    event_id=event_id,
                    request_id=request.request_id,
                    occurred_mono_ns=now_mono_ns,
                    received_utc=received_utc,
                    ingress_payload=ingress_payload,
                )
            )
        return tuple(deliveries)

    async def wait_for_due(self) -> tuple[ToolResultDelivery, ...]:
        """Wait for due scripted results, waking for newly requested work."""
        while not self._closed:
            deliveries = self.deliver_due()
            if deliveries:
                return deliveries
            next_due_mono_ns = self._store.next_pending_tool_due_mono_ns()
            self._changed.clear()
            if self._closed:
                break
            if next_due_mono_ns is None:
                await self._changed.wait()
                continue
            sleeper = asyncio.create_task(self._clock.sleep_until(next_due_mono_ns))
            changed = asyncio.create_task(self._changed.wait())
            _done, pending = await asyncio.wait(
                (sleeper, changed), return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        return ()

    async def run(
        self,
        enqueue: Callable[[ToolResultDelivery], Awaitable[None] | None],
    ) -> None:
        """Deliver results and enqueue them only after durable completion."""
        while not self._closed:
            deliveries = await self.wait_for_due()
            for delivery in deliveries:
                result = enqueue(delivery)
                if inspect.isawaitable(result):
                    await result

    def close(self) -> None:
        """Stop the adapter's optional delivery worker."""
        self._closed = True
        self._changed.set()

    @staticmethod
    def _result_ingress_payload(request: ToolRequestRecord) -> bytes:
        return canonicalize_tim_json(
            {
                "request_id": request.request_id,
                "status": request.result_status.value,
                "data": request.result_data,
            }
        )

    def _monotonic_ns(self) -> int:
        value = self._clock.monotonic_ns()
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("clock.monotonic_ns() must return an integer")
        if value < 0:
            raise ValueError("clock.monotonic_ns() must not return a negative value")
        return value

    def _received_utc(self) -> str:
        value = self._clock.wall_utc()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("clock.wall_utc() must return an aware UTC datetime")
            return value.astimezone(UTC).isoformat(timespec="microseconds")
        raise TypeError("clock.wall_utc() must return a datetime")
