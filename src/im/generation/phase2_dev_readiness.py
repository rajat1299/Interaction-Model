"""Offline WP2-8 DEV asset-readiness: coverage audit, candidate tranche, owner packet.

This is D14's deliberately-late DEV tranche (D11 stage 2).  It reuses the Phase 1 asset
registry, validator, and seal machinery and the WP2-0a/WP2-4 packet shape; it adds no
subsystem.  It writes review input only: no approval record, no registry mutation, and no
``dev-seal.json``.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetKind,
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, load_registry_jsonl, render_registry_jsonl
from im.assets.validate import ValidationIssue, validate_registry
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
#: The pre-Gate-B registry this packet was built and approved against, preserved byte-exact.
#: Same pattern as WP2-0a's frozen source registry: a readiness packet is bound to the state it
#: reviewed, not to the live approved registry it later changed.
DEFAULT_REGISTRY = _ROOT / "review" / "phase2" / "mark-tranche-2-approved" / "registry.jsonl"
LIVE_APPROVED_REGISTRY = _ROOT / "review" / "phase1" / "approved" / "registry.jsonl"
DEFAULT_TRAIN_SEAL = _ROOT / "review" / "phase1" / "approved" / "train-seal.json"
DEFAULT_ACCEPTED_INVENTORY = _ROOT / "review" / "phase2" / "wp2-6-exit" / "candidate-inventory.json"
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "dev-asset-readiness-v2"
SUPERSEDED_OUTPUT = _ROOT / "review" / "phase2" / "dev-asset-readiness"
DEFAULT_HELDOUT_ROOTS = (
    _ROOT / "probes" / "states",
    _ROOT / "golden",
    _ROOT / "review" / "phase1",
)

_VERSION = "phase2-dev-tranche-v2"
REVIEW_SAMPLING_SEED = "wp2-8-dev-asset-review-v2-2026-07-28"
ORDINARY_REVIEW_FRACTION = 0.20

#: MARK_NEGATIVE `text:direct` carries two semantically distinct controls that the shared
#: `(family, kind, form)` key cannot separate.  Same rule the TRAIN coverage matrix uses.
_SUBTYPE_PREFIXES: dict[tuple[str, str, str], tuple[tuple[str, str], ...]] = {
    (CorpusFamily.MARK_NEGATIVE.value, "text", "direct"): (
        ("direct_stop", "stop marking "),
        ("direct_replacement", "switch from "),
    ),
}


class DevReadinessError(ValueError):
    """The deterministic WP2-8 DEV packet cannot be built or verified."""


# --------------------------------------------------------------------------------------
# Candidate tranche
# --------------------------------------------------------------------------------------

#: Only the atomic shapes the coverage audit proves absent from DEV.  Every string is
#: DEV-original: no TRAIN/TEST/DEMO word, fact, message, interval, or template value.
_ATOMIC_CANDIDATES: tuple[tuple[str, CorpusFamily, str, object, str], ...] = (
    (
        "mark-negative-direct-stop",
        CorpusFamily.MARK_NEGATIVE,
        "text",
        (TextForm.DIRECT, "Stop marking the vermilion heron."),
        "vermilion heron",
    ),
    (
        "mark-negative-direct-replacement",
        CorpusFamily.MARK_NEGATIVE,
        "text",
        (TextForm.DIRECT, "Switch from district codes to platform codes."),
        "platform codes",
    ),
    (
        "mark-negative-ambiguous",
        CorpusFamily.MARK_NEGATIVE,
        "text",
        (TextForm.AMBIGUOUS, "Switch to the other marker set."),
        "unresolved marker set",
    ),
    (
        "mark-negative-code",
        CorpusFamily.MARK_NEGATIVE,
        "text",
        (TextForm.CODE, 'highlightAll("Thistle Landing");'),
        "Thistle Landing",
    ),
    (
        # Repair B: the v1 wording "Underline every mention of Perig" was a complete
        # instruction -- "Perig" reads as an ordinary proper name -- so it could not be a
        # partial control. This fragment is unmistakably truncated and names no target.
        "mark-negative-partial",
        CorpusFamily.MARK_NEGATIVE,
        "text",
        (TextForm.PARTIAL, "Underline every mention of"),
        "",
    ),
    (
        "timer-cancel-direct",
        CorpusFamily.TIMER_CANCEL,
        "text",
        (TextForm.DIRECT, "Cancel the pewter kettle reminder."),
        "pewter kettle reminder",
    ),
    (
        "timer-cancel-ambiguous",
        CorpusFamily.TIMER_CANCEL,
        "text",
        (TextForm.AMBIGUOUS, "Cancel the reminder from earlier."),
        "unresolved earlier reminder",
    ),
    (
        "timer-cancel-quoted",
        CorpusFamily.TIMER_CANCEL,
        "timer",
        (
            TimerForm.QUOTED,
            'Nils said, "remind me every thirteen minutes to rinse the slate jug."',
        ),
        "slate jug",
    ),
    (
        "timer-cancel-negated",
        CorpusFamily.TIMER_CANCEL,
        "timer",
        (
            TimerForm.NEGATED,
            "Do not remind me every twenty-three minutes to wind the flax clock.",
        ),
        "flax clock",
    ),
    (
        "timer-cancel-unsupported",
        CorpusFamily.TIMER_CANCEL,
        "timer",
        (TimerForm.UNSUPPORTED, "Remind me at 7:15 AM to seal the birch crate."),
        "birch crate",
    ),
)

#: DEV template counterparts for the TRAIN template roles DEV does not yet mirror, plus the
#: repaired MARK_NEGATIVE grammar.  `seed_roles` are candidate roles above; `seed_asset_ids`
#: are already-registered DEV records reused as seeds without being edited.
_TemplateCandidate = tuple[
    str, CorpusFamily, AssetKind, str, tuple[str, ...], tuple[str, ...]
]
_TEMPLATE_CANDIDATES: tuple[_TemplateCandidate, ...] = (
    (
        "timer-cancel-ambiguous-template",
        CorpusFamily.TIMER_CANCEL,
        AssetKind.TEXT,
        (
            "Use {seed} verbatim as a direct cancellation request while several running "
            "reminders stay on screen; keep the referent unresolved."
        ),
        ("timer-cancel-ambiguous",),
        (),
    ),
    (
        "timer-cancel-negated-template",
        CorpusFamily.TIMER_CANCEL,
        AssetKind.TIMER,
        (
            "Use {seed} verbatim as direct user control that turns down a repeating "
            "reminder; keep the negation and never render it as quotation."
        ),
        ("timer-cancel-negated",),
        (),
    ),
    (
        "timer-cancel-quoted-unsupported-template",
        CorpusFamily.TIMER_CANCEL,
        AssetKind.TIMER,
        (
            "Use {seed} as the factual subject; construct a natural drafting scenario in "
            "which the reminder wording keeps the quoted or unsupported form shown; place "
            "it while margin notes are being tidied."
        ),
        ("timer-cancel-quoted", "timer-cancel-unsupported"),
        (),
    ),
    (
        "mark-negative-repaired-template",
        CorpusFamily.MARK_NEGATIVE,
        AssetKind.TEXT,
        (
            "Use {seed} as the factual subject; construct a natural drafting scenario in "
            "which mark wording keeps the seed's subtype as direct stop, direct "
            "replacement, genuinely ambiguous, quoted, code, or partial; place it while "
            "margin notes are being tidied."
        ),
        (
            "mark-negative-direct-stop",
            "mark-negative-direct-replacement",
            "mark-negative-ambiguous",
            "mark-negative-code",
            "mark-negative-partial",
        ),
        ("a_4b9ff1fa143be8c680ed4de9",),
    ),
    (
        "lookup-live-template",
        CorpusFamily.LOOKUP_LIVE,
        AssetKind.LOOKUP,
        (
            "Use {seed} as the factual subject; construct a natural drafting scenario in "
            "which an unresolved factual lookup returns one of two answers that each "
            "restate the full subject; place it during a sentence revision."
        ),
        (
            "lookup-live-elder-basin-corrected",
            "lookup-live-halloway-gate",
            "lookup-live-marrow-cove",
        ),
        (),
    ),
    (
        "lookup-duplicate-template",
        CorpusFamily.LOOKUP_DUPLICATE,
        AssetKind.LOOKUP,
        (
            "Use {seed} as the factual subject; construct a natural drafting scenario in "
            "which the same unresolved lookup would otherwise be requested twice while the "
            "first remains pending; place it while margin notes are being tidied."
        ),
        (
            "lookup-duplicate-lumen-wharf-corrected",
            "lookup-duplicate-pellow-yard",
            "lookup-duplicate-verity-steps",
        ),
        (),
    ),
    (
        "lookup-stale-template",
        CorpusFamily.LOOKUP_STALE,
        AssetKind.LOOKUP,
        (
            "Use {seed} as the factual subject; construct a natural drafting scenario in "
            "which a factual lookup is abandoned before its delayed answer arrives; place it "
            "after a writer returns to the page."
        ),
        (
            "lookup-stale-sable-fork-corrected",
            "lookup-stale-torrin-bluff",
            "lookup-stale-windlass-court",
        ),
        (),
    ),
)

#: Shapes and boundaries that entered Phase 2 *after* the original Phase 1 seeds, whether by
#: addition or by repair.  The `(family, kind, form)` slot table cannot express these — they
#: are stream-level shapes — so they are audited here by name against their own evidence.
_POST_SEED_SHAPES: tuple[tuple[str, str, str, str], ...] = (
    (
        "lookup_prose_need",
        "review/phase2/lookup-prose-need-addendum-v1/frozen-pairs.json",
        "covered_by_this_tranche",
        (
            "A sufficiently specified factual need stated in natural drafting prose licenses "
            "delegate on the exact subject span; the same subject merely mentioned does not. "
            "The shape uses live_lookup_lifecycle sources. TRAIN drew six frozen pairs from a "
            "population of seven sealed sources. DEV's single source was rejected under repair "
            "A; the tranche supplies three corrected seal-eligible sources, so three pairs are "
            "reproducible."
        ),
    ),
    (
        "lookup_prose_need_stale_slice",
        "review/phase2/lookup-prose-need-addendum-v1/amended-lookup-closeout",
        "explicitly_dropped_upstream",
        (
            "The stale-context arm of the prose-need addendum was explicitly dropped by the "
            "owner, not left pending. It is therefore not a DEV coverage slot."
        ),
    ),
    (
        "timer_wave0_boundaries",
        "review/phase2/timer-wave-0-boundaries",
        "covered_by_this_tranche",
        (
            "Ambiguous-referent cancel, negated decline, and unsupported/one-shot timer. These "
            "boundary streams are template-proof material and do not appear in the 505 accepted "
            "streams, so their TRAIN atomic sources show zero accepted-pool use. They are still "
            "final surviving shapes, and DEV had no counterpart for any of the three; this "
            "tranche adds both the atomics and the three templates."
        ),
    ),
    (
        "mark_negative_repaired_subtypes",
        "review/phase2/mark-wave-1-repair-v4",
        "covered_by_this_tranche",
        (
            "WP2-4 repaired the mark-negative grammar so direct stop, direct replacement, and "
            "genuine ambiguity are distinguished from quoted, code, and partial. DEV carried "
            "only the pre-repair three; this tranche adds the missing five atomics and the "
            "repaired template. See JUDGMENT-NEEDED JN-2 for the superseded DEV template."
        ),
    ),
    (
        "response_floor_twins",
        "review/phase2/response-cluster-exit/exit-report.json",
        "covered_by_the_companion_dev_response_tranche",
        (
            "The active-floor twin (warrant+active -> awaiting_opening, warrant+open -> respond) "
            "and the four response kinds are exercised by 60 accepted streams over 30 approved "
            "TRAIN response payloads. Owner decision 1 authorized 14 DEV-only response records "
            "(8 ordinary grounded, 2 ambiguity clarifications, 2 unsupported-feature "
            "limitations, 2 failed-tool notices). They are built with the existing response "
            "schema in review/phase2/dev-response-tranche and are governed separately from "
            "dev-seal.json."
        ),
    ),
    (
        "rollover_and_checkpoint_variants",
        "review/phase2/timer-wave-3-repaired/raw-streams.json",
        "covered_by_existing_dev_assets",
        (
            "Rollover was woven through the timer and lookup clusters rather than run as a "
            "standalone family. Its asset requirement is a rollover_eligible lookup source. "
            "a_9ffb19423f7e143d6b25fde2 already restates its full subject and is kept, with "
            "template a_4a403aaa78fb587f5ca4d4d0; two further sources are added only to reach "
            "the three-source minimum."
        ),
    ),
    (
        "idle_reason_stratification",
        "review/phase2/wp2-6-exit/balance-report.json",
        "not_an_asset_shape",
        (
            "The seven idle-reason quotas are a selection-contract concern over generated "
            "states, not an asset property. No DEV asset closes or fails to close them; the "
            "DEV allocation decides them at Gate C."
        ),
    ),
)

#: Owner decision 4: at least three seal-eligible DEV atomic sources per family. These are
#: exactly the records needed to reach three -- no volume beyond that. The three roles marked
#: `-corrected` replace rejected records under new identities; the old identities are never
#: edited.
_MULTIPLICITY_TEXT: tuple[tuple[str, CorpusFamily, TextForm, str, str], ...] = (
    (
        "neutral-ledger-column",
        CorpusFamily.NEUTRAL_TYPING,
        TextForm.NEUTRAL,
        "Odile paused before finishing the ledger column.",
        "Odile",
    ),
    (
        "neutral-closing-line",
        CorpusFamily.NEUTRAL_TYPING,
        TextForm.NEUTRAL,
        "The afternoon draft sat open while Hollis reread the closing line.",
        "Hollis",
    ),
    (
        "mark-positive-gorse-alley",
        CorpusFamily.MARK_POSITIVE,
        TextForm.DIRECT,
        "Underline Gorse Alley in the delivery log.",
        "Gorse Alley",
    ),
    (
        "mark-positive-quiet-vellum",
        CorpusFamily.MARK_POSITIVE,
        TextForm.DIRECT,
        "Highlight quiet vellum each time it shows up in the notes.",
        "quiet vellum",
    ),
    (
        "reserved-sorrel-glyph",
        CorpusFamily.RESERVED,
        TextForm.OBSERVATIONAL,
        "The archived envelope keeps a pale sorrel glyph beside the entry.",
        "sorrel glyph",
    ),
    (
        "reserved-hazel-sigil",
        CorpusFamily.RESERVED,
        TextForm.OBSERVATIONAL,
        "An unfamiliar column preserves the hazel sigil without changing the page.",
        "hazel sigil",
    ),
)

_MULTIPLICITY_TIMER: tuple[tuple[str, CorpusFamily, str, int, str, str], ...] = (
    (
        "timer-normal-bracken-border",
        CorpusFamily.TIMER_NORMAL,
        "Remind me every thirty-one minutes to trim the bracken border.",
        1_860_000,
        "trim the bracken border",
        "bracken border",
    ),
    (
        "timer-normal-marsh-gauge",
        CorpusFamily.TIMER_NORMAL,
        "Remind me every forty-three minutes to log the marsh gauge.",
        2_580_000,
        "log the marsh gauge",
        "marsh gauge",
    ),
    (
        "timer-contention-tallow-lamp",
        CorpusFamily.TIMER_CONTENTION,
        "Remind me every fifty-one minutes to rotate the tallow lamp.",
        3_060_000,
        "rotate the tallow lamp",
        "tallow lamp",
    ),
    (
        "timer-contention-reed-panels",
        CorpusFamily.TIMER_CONTENTION,
        "Remind me every eighty-seven minutes to stack the reed panels.",
        5_220_000,
        "stack the reed panels",
        "reed panels",
    ),
)

#: Every result restates the query's complete subject verbatim, then differs in exactly one
#: grounded token. Repair A rejected the three DEV lookups that dropped a subject word.
_MULTIPLICITY_LOOKUP: tuple[
    tuple[str, CorpusFamily, bool, str, str, str, str, str], ...
] = (
    (
        "lookup-live-elder-basin-corrected",
        CorpusFamily.LOOKUP_LIVE,
        False,
        "Elder Basin lantern tax",
        "Elder Basin lantern tax is 6 shells.",
        "Elder Basin lantern tax is 9 shells.",
        "elder_basin_lantern_absent",
        "6 shells|9 shells",
    ),
    (
        "lookup-live-marrow-cove",
        CorpusFamily.LOOKUP_LIVE,
        False,
        "Marrow Cove ferry fare",
        "Marrow Cove ferry fare is 4 tokens.",
        "Marrow Cove ferry fare is 7 tokens.",
        "marrow_cove_fare_absent",
        "4 tokens|7 tokens",
    ),
    (
        "lookup-live-halloway-gate",
        CorpusFamily.LOOKUP_LIVE,
        False,
        "Halloway Gate berth number",
        "Halloway Gate berth number is 18.",
        "Halloway Gate berth number is 25.",
        "halloway_gate_berth_absent",
        "berth number 18|berth number 25",
    ),
    (
        "lookup-duplicate-lumen-wharf-corrected",
        CorpusFamily.LOOKUP_DUPLICATE,
        False,
        "Lumen Wharf archive shelf",
        "Lumen Wharf archive shelf is Delta.",
        "Lumen Wharf archive shelf is Sigma.",
        "lumen_wharf_archive_absent",
        "Delta|Sigma",
    ),
    (
        "lookup-duplicate-pellow-yard",
        CorpusFamily.LOOKUP_DUPLICATE,
        False,
        "Pellow Yard freight bay",
        "Pellow Yard freight bay is Larch.",
        "Pellow Yard freight bay is Rowan.",
        "pellow_yard_freight_absent",
        "Larch|Rowan",
    ),
    (
        "lookup-duplicate-verity-steps",
        CorpusFamily.LOOKUP_DUPLICATE,
        False,
        "Verity Steps mailing slot",
        "Verity Steps mailing slot is Ochre.",
        "Verity Steps mailing slot is Puce.",
        "verity_steps_mailing_absent",
        "Ochre|Puce",
    ),
    (
        "lookup-stale-sable-fork-corrected",
        CorpusFamily.LOOKUP_STALE,
        False,
        "Sable Fork observatory code",
        "Sable Fork observatory code is 72.",
        "Sable Fork observatory code is 94.",
        "sable_fork_observatory_absent",
        "observatory code 72|observatory code 94",
    ),
    (
        "lookup-stale-torrin-bluff",
        CorpusFamily.LOOKUP_STALE,
        False,
        "Torrin Bluff kiln count",
        "Torrin Bluff kiln count is 11.",
        "Torrin Bluff kiln count is 26.",
        "torrin_bluff_kiln_absent",
        "kiln count 11|kiln count 26",
    ),
    (
        "lookup-stale-windlass-court",
        CorpusFamily.LOOKUP_STALE,
        False,
        "Windlass Court dock letter",
        "Windlass Court dock letter is Fennel.",
        "Windlass Court dock letter is Vane.",
        "windlass_court_dock_absent",
        "Fennel|Vane",
    ),
    (
        "lookup-rollover-pallis-yard",
        CorpusFamily.ROLLOVER,
        True,
        "Pallis Yard convoy tag",
        "Pallis Yard convoy tag is Gypsum.",
        "Pallis Yard convoy tag is Feldspar.",
        "pallis_yard_convoy_absent",
        "Gypsum|Feldspar",
    ),
    (
        "lookup-rollover-renwick-landing",
        CorpusFamily.ROLLOVER,
        True,
        "Renwick Landing crate mark",
        "Renwick Landing crate mark is Sienna.",
        "Renwick Landing crate mark is Verdigris.",
        "renwick_landing_crate_absent",
        "Sienna|Verdigris",
    ),
)

#: Repair A: DEV records that cannot enter `dev-seal.json`. The three lookups carry the
#: content defect; the three templates are unusable only because they seed a rejected
#: record. Nothing here is edited -- the identities stay in the registry, unapproved.
_REJECTED_DEV_RECORDS: tuple[tuple[str, str], ...] = (
    (
        "a_34dfabfe62696f80b2369012",
        "content: results say 'Elder Basin tax', dropping the subject word 'lantern' from the "
        "query 'Elder Basin lantern tax'. Replaced by lookup-live-elder-basin-corrected.",
    ),
    (
        "a_5503de16ebb134c361f9da99",
        "content: results say 'Sable Fork code', dropping 'observatory' from the query "
        "'Sable Fork observatory code'. Replaced by lookup-stale-sable-fork-corrected.",
    ),
    (
        "a_f335df3ed80a593cd2e26e4b",
        "content: results say 'Lumen Wharf shelf', dropping 'archive' from the query "
        "'Lumen Wharf archive shelf'. Replaced by lookup-duplicate-lumen-wharf-corrected.",
    ),
    (
        "a_7e1d3ea22ce2b596581d855b",
        "template: seeds the rejected a_34dfabfe62696f80b2369012, and its grammar demands "
        "'value-only results', which the complete-subject rule forbids. Replaced by "
        "lookup-live-template.",
    ),
    (
        "a_a83bf071eb48807b48934e78",
        "template: seeds the rejected a_f335df3ed80a593cd2e26e4b. Replaced by "
        "lookup-duplicate-template.",
    ),
    (
        "a_79369ef0645cf83737b1ae7c",
        "template: seeds the rejected a_5503de16ebb134c361f9da99. Replaced by "
        "lookup-stale-template.",
    ),
)


#: TRAIN template role -> DEV counterpart.  `""` means "supplied by this tranche", named by
#: candidate role.  `parity` records the audit finding that justifies the DEV side.
_TEMPLATE_ROLE_MAP: tuple[tuple[str, str, str, str], ...] = (
    (
        "live_lookup_full_subject_results",
        "a_93beb83846363b159a8f8f67",
        "lookup-live-template",
        (
            "REPAIRED: the registered DEV template a_7e1d3ea22ce2b596581d855b seeded the "
            "rejected a_34dfabfe62696f80b2369012 and its grammar demanded 'value-only "
            "results', which the complete-subject rule forbids. The replacement drops that "
            "clause and requires each answer to restate the full subject."
        ),
    ),
    (
        "lookup_duplicate_pressure",
        "a_0c05ad0e07dcb3adfcea1ca1",
        "lookup-duplicate-template",
        (
            "REPAIRED: the registered DEV template a_a83bf071eb48807b48934e78 seeded the "
            "rejected a_f335df3ed80a593cd2e26e4b. The replacement seeds the three corrected "
            "duplicate-pressure sources."
        ),
    ),
    (
        "mark_positive_direct",
        "a_a1c85d29665460b9b04ffcd2",
        "a_484a98cb9f3aa72092073a01",
        "role parity: direct request naming the exact words to mark",
    ),
    (
        "mark_negative_subtype_preserving",
        "a_cf3fb85cbef8786d98724b33",
        "mark-negative-repaired-template",
        (
            "GAP: the registered DEV template a_0c8d927628aaf337c9b1b181 admits only quoted, "
            "code, or partial mark wording, while the TRAIN grammar was repaired during WP2-4 "
            "to preserve direct stop, direct replacement, genuinely ambiguous, quoted, code, "
            "and partial subtypes. This tranche adds the repaired DEV counterpart. Owner "
            "decision 2 keeps the narrow template approved as a deliberate variant; it is "
            "unedited."
        ),
    ),
    (
        "neutral_typing_revision_pause",
        "a_fac3874e81fa3f510b29a562",
        "a_f9fb7e61b8bd7a9477003568",
        "role parity: ordinary revision continuing after a quiet pause",
    ),
    (
        "reserved_unknown_annotation",
        "a_ebfbdb97e5da6bb07abf0262",
        "a_2b0e71a0c80c2a54d44441d5",
        "role parity: unknown annotation beside ordinary text without an instruction",
    ),
    (
        "rollover_unresolved_lookup",
        "a_95c425c1e1736f407ccc54db",
        "a_4a403aaa78fb587f5ca4d4d0",
        "role parity: unresolved lookup still relevant after a drafting break",
    ),
    (
        "stale_abandoned_lookup",
        "a_dd5c4e7300588ffc83ce7bb2",
        "lookup-stale-template",
        (
            "REPAIRED: the registered DEV template a_79369ef0645cf83737b1ae7c seeded the "
            "rejected a_5503de16ebb134c361f9da99. The replacement seeds the three corrected "
            "stale-boundary sources."
        ),
    ),
    (
        "timer_cancel_form_preserving",
        "a_e35790e7d64ca17bc1e3b4d9",
        "a_3d0bfcfa3a3c0990cbe83c11",
        "role parity: cancellation wording retaining the direct, quoted, or negated form",
    ),
    (
        "timer_cancel_ambiguous_referent",
        "a_064c3dae3e3abe4e7bd7a487",
        "timer-cancel-ambiguous-template",
        (
            "GAP: DEV had no counterpart for the ambiguous-referent cancellation boundary "
            "exercised by the WP2-1 sentinel and the WP2-6 ambiguous-cancel repair."
        ),
    ),
    (
        "timer_cancel_negated_decline",
        "a_9d4278e5ace95912cec8d008",
        "timer-cancel-negated-template",
        "GAP: DEV had no counterpart for the negated-decline timer boundary.",
    ),
    (
        "timer_cancel_quoted_or_unsupported",
        "a_a240fd307b1c0cd3995e7157",
        "timer-cancel-quoted-unsupported-template",
        "GAP: DEV had no counterpart for the quoted/unsupported timer boundary.",
    ),
    (
        "timer_contention_fire_during_drafting",
        "a_21e7ddae34d168708913157f",
        "a_d9e4797beeb4b756ddc5a1ec",
        "role parity: repeating reminder firing while unrelated drafting continues",
    ),
    (
        "timer_normal_full_specification",
        "a_77870a0d84d3da57e4b0318d",
        "a_8757bfbc6cba684b27e651f4",
        "role parity: direct request fully specifying a repeating reminder",
    ),
)


def dev_tranche_candidates() -> tuple[AssetRecord, ...]:
    """Return the deterministic DEV candidate tranche, sorted by asset id."""
    by_role: dict[str, AssetRecord] = {}

    def add(
        role: str,
        family: CorpusFamily,
        payload: TextAssetPayload | TimerAssetPayload | LookupAssetPayload,
        protected: tuple[str, ...],
        *,
        rollover_eligible: bool = False,
    ) -> None:
        by_role[role] = AssetRecord.build(
            asset_id=_asset_id(role),
            split=Split.DEV,
            payload=payload,
            provenance=AssetProvenance.SEED_AUTHORED,
            protected_values=protected,
            coverage=(family,),
            rollover_eligible=rollover_eligible,
        )

    for role, family, kind, spec, protected in _ATOMIC_CANDIDATES:
        form, text = spec
        payload: TextAssetPayload | TimerAssetPayload
        if kind == "text":
            payload = TextAssetPayload(text=text, form=form)
        else:
            payload = TimerAssetPayload(instruction=text, form=form, interval_ms=None, message=None)
        add(role, family, payload, (protected,) if protected else ())
    for role, family, form, text, protected in _MULTIPLICITY_TEXT:
        add(role, family, TextAssetPayload(text=text, form=form), (protected,))
    for role, family, instruction, interval_ms, message, protected in _MULTIPLICITY_TIMER:
        add(
            role,
            family,
            TimerAssetPayload(
                instruction=instruction,
                form=TimerForm.SUPPORTED,
                interval_ms=interval_ms,
                message=message,
            ),
            (protected,),
        )
    for role, family, rollover, query, a, b, code, values in _MULTIPLICITY_LOOKUP:
        add(
            role,
            family,
            LookupAssetPayload(query=query, result_a=a, result_b=b, no_result_code=code),
            (query, *values.split("|")),
            rollover_eligible=rollover,
        )
    for role, family, expands, grammar, seed_roles, seed_ids in _TEMPLATE_CANDIDATES:
        seeds = tuple(sorted({*(_asset_id(seed) for seed in seed_roles), *seed_ids}))
        by_role[role] = AssetRecord.build(
            asset_id=_asset_id(role),
            split=Split.DEV,
            payload=TemplateAssetPayload(
                expands_kind=expands, grammar=grammar, seed_asset_ids=seeds
            ),
            provenance=AssetProvenance.SEED_AUTHORED,
            coverage=(family,),
        )
    return tuple(sorted(by_role.values(), key=lambda asset: asset.asset_id))


# --------------------------------------------------------------------------------------
# Coverage audit against the materialized accepted Phase 2 artifacts
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AcceptedUsage:
    """What the final accepted WP2-6 pool actually materialized, read from evidence."""

    inventory_sha256: str
    stream_count: int
    provenance_paths: tuple[str, ...]
    streams_by_template: dict[str, int]
    streams_without_template_link: int
    atomic_asset_ids: frozenset[str]


def read_accepted_usage(inventory_path: Path = DEFAULT_ACCEPTED_INVENTORY) -> AcceptedUsage:
    """Resolve template and atomic-asset usage from the accepted whole-stream evidence."""
    data = inventory_path.read_bytes()
    inventory = json.loads(data)
    streams = inventory["streams"]
    wanted = {stream["stream_sha256"] for stream in streams}
    if len(wanted) != len(streams):
        raise DevReadinessError("accepted inventory stream digests are not unique")
    paths = tuple(sorted({path for stream in streams for path in stream["provenance"]}))
    matched: dict[str, dict[str, object]] = {digest: {} for digest in wanted}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            digest = node.get("stream_sha256")
            if isinstance(digest, str) and digest in matched:
                target = matched[digest]
                template = node.get("template")
                if isinstance(node.get("template_id"), str):
                    target["template_id"] = node["template_id"]
                elif isinstance(template, dict) and isinstance(template.get("asset_id"), str):
                    target["template_id"] = template["asset_id"]
                assets = set(target.get("asset_ids", ()))  # type: ignore[arg-type]
                assets.update(
                    item for item in (node.get("asset_ids") or []) if isinstance(item, str)
                )
                for item in node.get("assets") or []:
                    if isinstance(item, dict) and isinstance(item.get("asset_id"), str):
                        assets.add(item["asset_id"])
                    elif isinstance(item, str):
                        assets.add(item)
                target["asset_ids"] = assets
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in paths:
        walk(json.loads((_ROOT / path).read_bytes()))

    unresolved = [digest for digest, found in matched.items() if not found]
    if unresolved:
        raise DevReadinessError(
            f"{len(unresolved)} accepted streams have no provenance evidence record"
        )
    by_template: Counter[str] = Counter()
    unlinked = 0
    atomics: set[str] = set()
    for found in matched.values():
        template_id = found.get("template_id")
        if isinstance(template_id, str):
            by_template[template_id] += 1
        else:
            unlinked += 1
        atomics.update(found.get("asset_ids", ()))  # type: ignore[arg-type]
    return AcceptedUsage(
        inventory_sha256=_digest(data),
        stream_count=len(streams),
        provenance_paths=paths,
        streams_by_template=dict(sorted(by_template.items())),
        streams_without_template_link=unlinked,
        atomic_asset_ids=frozenset(atomics),
    )


MINIMUM_DEV_SOURCES_PER_FAMILY = 3

_WORD_TOKEN = re.compile(r"\w+(?:[-\u2010-\u2015']\w+)*")


def rejected_dev_asset_ids() -> frozenset[str]:
    """Ids that must stay outside `dev-seal.json` and outside every selection path."""
    return frozenset(asset_id for asset_id, _ in _REJECTED_DEV_RECORDS)


def seal_eligible_dev_records(dev: tuple[AssetRecord, ...]) -> tuple[AssetRecord, ...]:
    """DEV corpus records that could enter the seal once the owner approves them."""
    rejected = rejected_dev_asset_ids()
    return tuple(asset for asset in dev if asset.asset_id not in rejected)


def subject_restatement_review_signals(
    records: tuple[AssetRecord, ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Scoped DEV signal: which query words a lookup's results do not repeat.

    The owner resolved this as a *referent-level* rule (JN-5, 2026-07-28): a result must
    clearly refer to the same complete entity or property the query asked for, and natural
    wording that preserves the meaning need not repeat every query word. A missing token is
    therefore a mechanical review signal that routes the record to a human, never an
    automatic content rejection. Rejections are the owner's, recorded in
    `_REJECTED_DEV_RECORDS`.

    ponytail: deliberately local to DEV readiness rather than added to
    `im.assets.validate`, so no TRAIN/TEST/DEMO seal is reopened.
    """
    issues = []
    for asset in records:
        payload = asset.payload
        if not isinstance(payload, LookupAssetPayload):
            continue
        query = [token.casefold() for token in _WORD_TOKEN.findall(payload.query)]
        missing = sorted(
            {
                token
                for result in (payload.result_a, payload.result_b)
                for token in query
                if token not in {t.casefold() for t in _WORD_TOKEN.findall(result)}
            }
        )
        if missing:
            issues.append((asset.asset_id, tuple(missing)))
    return tuple(sorted(issues))


def _slot_keys(asset: AssetRecord) -> tuple[tuple[str, str, str, str], ...]:
    """Return `(family, kind, form, subtype)` shape keys for one atomic record."""
    payload = asset.payload
    if isinstance(payload, TemplateAssetPayload):
        return ()
    form = getattr(payload, "form", None)
    form_value = form.value if form is not None else "none"
    keys = []
    for family in asset.coverage:
        subtype = ""
        rules = _SUBTYPE_PREFIXES.get((family.value, payload.kind.value, form_value), ())
        for name, prefix in rules:
            text = payload.text if isinstance(payload, TextAssetPayload) else ""
            if text.casefold().startswith(prefix):
                subtype = name
        keys.append((family.value, payload.kind.value, form_value, subtype))
    return tuple(keys)


def _other_split_restatement_tally(registry: AssetRegistry) -> dict[str, object]:
    """Report the token signal on TRAIN/TEST/DEMO without acting on it.

    Informational only. Under the referent-level resolution of JN-5 these counts are not
    defects; they are retained so the signal's base rate is visible.
    """
    rows: dict[str, object] = {
        "note": (
            "Informational only, and not defects. Under the owner's referent-level resolution "
            "of JN-5 these records are not reopened: TRAIN, TEST, and DEMO stand as sealed. "
            "The counts show how often natural wording drops a query word while keeping the "
            "same referent, which is why the token check is a review signal rather than a gate."
        )
    }
    for split in (Split.TRAIN, Split.TEST, Split.DEMO):
        records = registry.pool(split).corpus_records
        lookups = tuple(
            asset for asset in records if isinstance(asset.payload, LookupAssetPayload)
        )
        signals = subject_restatement_review_signals(lookups)
        rows[split.value] = {
            "lookup_records": len(lookups),
            "results_not_repeating_every_query_word": len(signals),
        }
    return rows


def build_dev_coverage_matrix(
    registry: AssetRegistry,
    candidates: tuple[AssetRecord, ...],
    usage: AcceptedUsage,
) -> dict[str, object]:
    """Audit DEV against every TRAIN template role and atomic shape that Phase 2 left final."""
    train = registry.pool(Split.TRAIN).corpus_records
    candidate_index = {asset.asset_id: asset for asset in candidates}
    # `registry` is the augmented registry, so its DEV pool already contains `candidates`.
    all_dev = registry.pool(Split.DEV).corpus_records
    # Owner decision 3 + repair A: coverage counts only records that could enter the seal.
    dev = seal_eligible_dev_records(all_dev)
    train_index = {asset.asset_id: asset for asset in train}
    dev_index = {
        asset.asset_id: asset for asset in dev if asset.asset_id not in candidate_index
    }

    train_slots: dict[tuple[str, str, str, str], list[AssetRecord]] = {}
    for asset in train:
        for key in _slot_keys(asset):
            train_slots.setdefault(key, []).append(asset)
    dev_slots: dict[tuple[str, str, str, str], list[AssetRecord]] = {}
    for asset in dev:
        for key in _slot_keys(asset):
            dev_slots.setdefault(key, []).append(asset)

    shape_rows = []
    for key in sorted(train_slots):
        sources = train_slots[key]
        covering = dev_slots.get(key, [])
        existing = [asset.asset_id for asset in covering if asset.asset_id in dev_index]
        added = [asset.asset_id for asset in covering if asset.asset_id in candidate_index]
        shape_rows.append(
            {
                "family": key[0],
                "kind": key[1],
                "form": key[2],
                "subtype": key[3],
                "train_sealed_source_count": len(sources),
                "train_sources_used_in_accepted_pool": sum(
                    asset.asset_id in usage.atomic_asset_ids for asset in sources
                ),
                "dev_existing_asset_ids": sorted(existing),
                "dev_added_asset_ids": sorted(added),
                "status": (
                    "covered_by_existing_dev_asset"
                    if existing
                    else "covered_by_this_tranche"
                    if added
                    else "absent"
                ),
                "was_absent_before_this_tranche": not existing,
            }
        )

    dev_only_rows = [
        {
            "family": key[0],
            "kind": key[1],
            "form": key[2],
            "subtype": key[3],
            "dev_asset_ids": sorted(asset.asset_id for asset in dev_slots[key]),
            "note": "DEV-only shape with no sealed TRAIN counterpart; retained, not a gap.",
        }
        for key in sorted(set(dev_slots) - set(train_slots))
    ]

    template_rows = []
    for role, train_id, dev_id, parity in _TEMPLATE_ROLE_MAP:
        train_template = train_index.get(train_id)
        if train_template is None or not isinstance(train_template.payload, TemplateAssetPayload):
            raise DevReadinessError(f"TRAIN template role lost its record: {role}")
        resolved = dev_id if dev_id.startswith("a_") else _asset_id(dev_id)
        counterpart = dev_index.get(resolved) or candidate_index.get(resolved)
        if counterpart is None or not isinstance(counterpart.payload, TemplateAssetPayload):
            raise DevReadinessError(f"DEV template counterpart is missing for role: {role}")
        template_rows.append(
            {
                "role": role,
                "train_template_asset_id": train_id,
                "train_grammar": train_template.payload.grammar,
                "train_expands_kind": train_template.payload.expands_kind.value,
                "accepted_streams_using_train_template": usage.streams_by_template.get(train_id, 0),
                "dev_template_asset_id": resolved,
                "dev_grammar": counterpart.payload.grammar,
                "dev_expands_kind": counterpart.payload.expands_kind.value,
                "dev_source": "existing" if resolved in dev_index else "added_by_this_tranche",
                "rendered_dev_expansion": _rendered_expansion(
                    counterpart.payload, {**dev_index, **candidate_index}
                ),
                "parity": parity,
            }
        )

    covered_train_templates = {row["train_template_asset_id"] for row in template_rows}
    unmapped = sorted(
        asset.asset_id
        for asset in train
        if isinstance(asset.payload, TemplateAssetPayload)
        and asset.asset_id not in covered_train_templates
    )
    if unmapped:
        raise DevReadinessError(f"sealed TRAIN templates are absent from the role map: {unmapped}")

    unmapped_dev_templates = sorted(
        asset.asset_id
        for asset in dev
        if isinstance(asset.payload, TemplateAssetPayload)
        and asset.asset_id not in {row["dev_template_asset_id"] for row in template_rows}
    )
    multiplicity_rows = []
    for family in CorpusFamily:
        sources = [
            asset
            for asset in dev
            if family in asset.coverage and not isinstance(asset.payload, TemplateAssetPayload)
        ]
        multiplicity_rows.append(
            {
                "family": family.value,
                "seal_eligible_atomic_sources": len(sources),
                "meets_minimum": len(sources) >= MINIMUM_DEV_SOURCES_PER_FAMILY,
                "asset_ids": sorted(asset.asset_id for asset in sources),
            }
        )
    below_minimum = [row["family"] for row in multiplicity_rows if not row["meets_minimum"]]
    if below_minimum:
        raise DevReadinessError(
            f"families below the {MINIMUM_DEV_SOURCES_PER_FAMILY}-source minimum: {below_minimum}"
        )
    eligible_signals = subject_restatement_review_signals(dev)

    post_seed_rows = []
    for shape, evidence, status, detail in _POST_SEED_SHAPES:
        if not (_ROOT / evidence).exists():
            raise DevReadinessError(f"post-seed shape evidence is missing: {evidence}")
        post_seed_rows.append(
            {"shape": shape, "evidence": evidence, "dev_status": status, "detail": detail}
        )

    concentration = []
    for family, row in zip(CorpusFamily, multiplicity_rows, strict=True):
        train_sources = [
            asset
            for asset in train
            if family in asset.coverage and not isinstance(asset.payload, TemplateAssetPayload)
        ]
        concentration.append(
            {
                "family": family.value,
                "train_sealed_atomic_sources": len(train_sources),
                "dev_seal_eligible_atomic_sources": row["seal_eligible_atomic_sources"],
                "meets_minimum": row["meets_minimum"],
                "dev_atomic_source_ids": row["asset_ids"],
            }
        )

    return {
        "format_version": 1,
        "kind": "wp2-8-dev-coverage-matrix",
        "status": "pending_owner_review",
        "audit_basis": {
            "accepted_inventory": str(
                DEFAULT_ACCEPTED_INVENTORY.relative_to(_ROOT).as_posix()
            ),
            "accepted_inventory_sha256": usage.inventory_sha256,
            "accepted_whole_streams": usage.stream_count,
            "accepted_provenance_paths": list(usage.provenance_paths),
            "accepted_streams_without_template_link_in_evidence": (
                usage.streams_without_template_link
            ),
            "template_link_note": (
                "Timer wave-1/wave-2 eligibility evidence records whole-stream digests without a "
                "template field. Those streams are counted here as unlinked; their template roles "
                "are still audited through the sealed TRAIN template inventory, which is the "
                "authoritative slot list."
            ),
            "distinct_train_atomic_assets_used": len(usage.atomic_asset_ids),
        },
        "template_slots": template_rows,
        "dev_templates_outside_the_train_role_map": {
            "asset_ids": unmapped_dev_templates,
            "note": (
                "a_0c8d927628aaf337c9b1b181 admits only quoted, code, or partial mark wording. "
                "Owner decision 2 keeps it as a deliberately narrow DEV variant; the repaired "
                "broader template supplies the missing lifecycle subtypes. It mirrors no sealed "
                "TRAIN role by design, so it is listed here rather than in template_slots."
            ),
        },
        "rejected_records": {
            "policy": (
                "Owner decision 3: DEV now follows TRAIN's cumulative approved-subset seal "
                "policy. These records stay in the registry, stay unapproved, stay outside "
                "dev-seal.json, and cannot be selected. TEST and DEMO remain strict."
            ),
            "records": [
                {"asset_id": asset_id, "reason": reason}
                for asset_id, reason in _REJECTED_DEV_RECORDS
            ],
            "dev_records_total": len(all_dev),
            "dev_records_seal_eligible": len(dev),
        },
        "subject_restatement": {
            "rule": (
                "A lookup result must clearly refer to the same complete entity or property the "
                "query asked for. Natural wording that preserves the meaning need not repeat "
                "every query word."
            ),
            "resolution": (
                "Owner decision JN-5, 2026-07-28: referent-level, not exact-token. A missing "
                "query word is a mechanical review signal, not an automatic rejection. TRAIN, "
                "TEST, and DEMO are not reopened."
            ),
            "scope": "DEV lookup records only",
            "signal_kind": "review_signal",
            "seal_eligible_signals": [
                {"asset_id": asset_id, "unrepeated_query_words": list(missing)}
                for asset_id, missing in eligible_signals
            ],
            "owner_rejected_for_changed_referent": [
                {"asset_id": asset_id, "unrepeated_query_words": list(missing)}
                for asset_id, missing in subject_restatement_review_signals(all_dev)
                if asset_id in rejected_dev_asset_ids()
            ],
            "informational_other_splits": _other_split_restatement_tally(registry),
        },
        "source_multiplicity": {
            "minimum_per_family": MINIMUM_DEV_SOURCES_PER_FAMILY,
            "counted": "seal-eligible DEV atomic records only",
            "families": multiplicity_rows,
            "prose_need_capacity": {
                "shape": "lookup prose-need pairs",
                "dev_live_lookup_sources": next(
                    row["seal_eligible_atomic_sources"]
                    for row in multiplicity_rows
                    if row["family"] == CorpusFamily.LOOKUP_LIVE.value
                ),
                "reproducible_pairs": next(
                    row["seal_eligible_atomic_sources"]
                    for row in multiplicity_rows
                    if row["family"] == CorpusFamily.LOOKUP_LIVE.value
                ),
                "train_reference": "six frozen pairs over seven sealed TRAIN sources",
            },
        },
        "atomic_shape_slots": shape_rows,
        "post_seed_shapes_and_boundaries": post_seed_rows,
        "dev_only_shapes": dev_only_rows,
        "missing_after_tranche": [
            {
                "family": row["family"],
                "kind": row["kind"],
                "form": row["form"],
                "subtype": row["subtype"],
            }
            for row in shape_rows
            if row["status"] == "absent"
        ],
        "source_unit_concentration": concentration,
        "out_of_scope_for_this_gate": [
            {
                "item": "dev response payloads",
                "detail": (
                    "The approved response corpus is TRAIN-scoped and lives outside the asset "
                    "registry. No DEV response payload exists. Whether the DEV state allocation "
                    "contains respond decisions is a Gate C decision; see JUDGMENT-NEEDED.md."
                ),
            },
            {
                "item": "dev timing pools",
                "detail": (
                    "Timing seeds are already split-scoped (im.generation.timing.TimingSeed); DEV "
                    "draws a disjoint stream without new assets or code."
                ),
            },
        ],
    }


def _rendered_expansion(
    template: TemplateAssetPayload, index: dict[str, AssetRecord]
) -> str:
    """Render the template's first seed exactly as the offline expander would supply it."""
    seed = index[template.seed_asset_ids[0]]
    return template.grammar.replace(
        "{seed}", canonical_artifact_bytes(seed.payload.model_dump(mode="json")).decode()
    )


# --------------------------------------------------------------------------------------
# Owner review packet
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReviewUnit:
    role: str
    selection_class: str
    assets: tuple[AssetRecord, ...]
    rationale: str

    @property
    def unit_id(self) -> str:
        return f"{self.selection_class}:{self.role}:{','.join(a.asset_id for a in self.assets)}"


def _flagged_ids(
    registry: AssetRegistry, dev: tuple[AssetRecord, ...], issues: tuple[ValidationIssue, ...]
) -> frozenset[str]:
    dev_ids = {asset.asset_id for asset in dev}
    flagged = {
        asset_id
        for issue in issues
        if issue.severity.value == "review"
        for asset_id in issue.asset_ids
        if asset_id in dev_ids
    }
    flagged.update(
        asset.asset_id
        for asset in dev
        if (review := registry.current_review(asset)) is not None
        and review.decision in {ReviewDecision.FLAGGED, ReviewDecision.REJECTED}
    )
    return frozenset(flagged)


def _ordinary_sample(existing: tuple[AssetRecord, ...], skip: frozenset[str]) -> tuple[str, ...]:
    """Deterministic ~20% stratified draw over ordinary existing DEV records."""
    pool = [asset for asset in existing if asset.asset_id not in skip]
    if not pool:
        return ()
    target = -(-len(pool) * 5 // 25)  # ceil(20%)
    ranked = sorted(pool, key=lambda asset: _rank("ordinary-sample", asset.asset_id))
    selected: list[str] = []
    seen: set[str] = set()
    for asset in ranked:
        stratum = (
            "template"
            if isinstance(asset.payload, TemplateAssetPayload)
            else asset.payload.kind.value
        )
        if stratum not in seen:
            seen.add(stratum)
            selected.append(asset.asset_id)
    for asset in ranked:
        if len(selected) >= target:
            break
        if asset.asset_id not in selected:
            selected.append(asset.asset_id)
    return tuple(selected)


def build_dev_readiness_artifacts(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    train_seal_path: Path = DEFAULT_TRAIN_SEAL,
    inventory_path: Path = DEFAULT_ACCEPTED_INVENTORY,
    heldout_roots: tuple[Path, ...] = DEFAULT_HELDOUT_ROOTS,
) -> dict[str, bytes]:
    """Build the closed WP2-8 Gate-A packet without changing approval or seal state."""
    registry_bytes = registry_path.read_bytes()
    seal_bytes = train_seal_path.read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    candidates = dev_tranche_candidates()
    _assert_no_frozen_overlap(candidates, heldout_roots, registry_path)

    augmented = AssetRegistry(assets=(*registry.assets, *candidates), reviews=registry.reviews)
    dev = augmented.pool(Split.DEV).corpus_records
    dev_ids = {asset.asset_id for asset in dev}
    report = validate_registry(augmented)
    dev_issues = tuple(
        issue
        for issue in report.issues
        if not issue.asset_ids or dev_ids.intersection(issue.asset_ids)
    )
    errors = tuple(issue for issue in dev_issues if issue.severity.value == "error")
    if errors:
        raise DevReadinessError(
            "DEV pool fails the automated asset battery: "
            + ", ".join(f"{issue.code.value}{list(issue.asset_ids)}" for issue in errors)
        )

    usage = read_accepted_usage(inventory_path)
    coverage = build_dev_coverage_matrix(augmented, candidates, usage)
    if coverage["missing_after_tranche"]:
        raise DevReadinessError("DEV coverage matrix still reports absent shape slots")

    index = {asset.asset_id: asset for asset in dev}
    candidate_ids = frozenset(asset.asset_id for asset in candidates)
    existing = tuple(asset for asset in dev if asset.asset_id not in candidate_ids)
    rejected = rejected_dev_asset_ids()
    reason_by_id = dict(_REJECTED_DEV_RECORDS)
    flagged = _flagged_ids(augmented, dev, dev_issues) | rejected
    # A sampled lookup defect expanded review to the whole DEV lookup stratum (D14's
    # "a sampled defect expands review to that record's semantic stratum").
    lookup_stratum = tuple(
        sorted(
            asset.asset_id
            for asset in dev
            if isinstance(asset.payload, LookupAssetPayload)
            and asset.asset_id not in candidate_ids | flagged
        )
    )
    sampled = _ordinary_sample(existing, flagged | candidate_ids | frozenset(lookup_stratum))

    units = (
        *(
            ReviewUnit(
                "rejected_or_flagged",
                "mandatory_flagged",
                (index[asset_id],),
                reason_by_id.get(
                    asset_id,
                    "Automated battery raised a review flag, or a prior review flagged it.",
                )
                + (
                    "  Confirm the rejection: the record stays registered, unapproved, and "
                    "outside dev-seal.json."
                    if asset_id in rejected
                    else ""
                ),
            )
            for asset_id in sorted(flagged)
        ),
        *(
            ReviewUnit(
                "lookup_semantic_stratum",
                "expanded_semantic_stratum",
                (index[asset_id],),
                "The sampled lookup defect expanded review to every DEV lookup record.",
            )
            for asset_id in lookup_stratum
        ),
        *(
            ReviewUnit(
                _candidate_role(asset.asset_id),
                "new_dev_candidate",
                (asset,),
                _candidate_rationale(asset.asset_id),
            )
            # Grouped by declared role, not asset id: a human read follows the families,
            # and the registry rows stay id-sorted regardless.
            for asset in sorted(candidates, key=lambda item: _candidate_role(item.asset_id))
        ),
        *(
            ReviewUnit(
                "ordinary_stratified",
                "ordinary_stratified_sample",
                (index[asset_id],),
                "Deterministic ~20% stratified draw over ordinary already-registered DEV records.",
            )
            for asset_id in sampled
        ),
    )

    packet = {
        "format_version": 1,
        "kind": "wp2-8-dev-asset-readiness-packet",
        "review_status": "pending_owner_review",
        "scope": {
            "registry_sha256": _digest(registry_bytes),
            "train_seal_sha256": _digest(seal_bytes),
            "existing_dev_records": len(existing),
            "new_dev_candidates": len(candidates),
            "dev_records_after_tranche": len(dev),
            "dev_records_seal_eligible": len(dev) - len(rejected),
            "dev_records_rejected": len(rejected),
            "dev_approved_records_now": sum(augmented.is_approved(asset) for asset in dev),
            "dev_seal_present": False,
            "supersedes": {
                "packet": "review/phase2/dev-asset-readiness",
                "status": "superseded_historical_evidence_do_not_approve_or_seal",
            },
            "companion_response_packet": "review/phase2/dev-response-tranche",
        },
        "battery": {
            "validator": "im.assets.validate.validate_registry",
            "records_checked": len(dev),
            "coverage_percent": 100,
            "executed_on_dev_record_ids": sorted(dev_ids),
            "errors": [],
            "review_flags": [
                {
                    "code": issue.code.value,
                    "asset_ids": list(issue.asset_ids),
                    "detail": issue.detail,
                }
                for issue in dev_issues
                if issue.severity.value == "review"
            ],
        },
        "selection": {
            "sampling_seed": REVIEW_SAMPLING_SEED,
            "ordinary_review_fraction": ORDINARY_REVIEW_FRACTION,
            "ordinary_population": len(existing) - len(flagged),
            "ordinary_sampled_asset_ids": list(sampled),
            "flagged_or_rejected_asset_ids": sorted(flagged),
            "expanded_lookup_stratum_asset_ids": list(lookup_stratum),
            "new_candidate_asset_ids": [asset.asset_id for asset in candidates],
            "reviewed_unit_ids": [unit.unit_id for unit in units],
            "reviewed_asset_ids": sorted(
                {asset.asset_id for unit in units for asset in unit.assets}
            ),
            "units": [_unit_json(unit, {**index}) for unit in units],
        },
        "counts_by_family_and_type": _counts(dev, candidates),
        "owner_review": {
            "reply_format": (
                "approved|flagged|rejected <unit_id> <asset_id> <content_sha256> "
                "[brief reason for flagged/rejected]"
            ),
            "approval_boundary": (
                "Review input only. This packet writes no approval record, does not touch the "
                "approved registry, and issues no dev-seal.json."
            ),
            "open_questions": "See JUDGMENT-NEEDED.md; four items are recorded for adjudication.",
        },
        "non_actions": [
            "No approval record was written.",
            "No dev-seal.json was written.",
            "The approved registry, train/test/demo seals, and owner-disposition files are",
            "unchanged.",
            "No provider, teacher, or Chat UI call occurred.",
        ],
        "coverage_matrix_file": "coverage-matrix.json",
    }

    files = {
        "REVIEW.md": _review_markdown(packet, units, coverage, index).encode(),
        "candidate-assets.jsonl": _candidate_jsonl(candidates),
        "coverage-matrix.json": canonical_artifact_bytes(coverage),
        "review-packet.json": canonical_artifact_bytes(packet),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_readiness_artifacts(
    output: Path = DEFAULT_OUTPUT,
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    train_seal_path: Path = DEFAULT_TRAIN_SEAL,
    inventory_path: Path = DEFAULT_ACCEPTED_INVENTORY,
) -> None:
    """Publish the closed packet directory; create-only, never overwriting owner evidence."""
    publish_directory_transaction(
        output,
        build_dev_readiness_artifacts(
            registry_path=registry_path,
            train_seal_path=train_seal_path,
            inventory_path=inventory_path,
        ),
    )


def _candidate_jsonl(candidates: tuple[AssetRecord, ...]) -> bytes:
    """Render candidates in registry-row form.

    ponytail: not `render_registry_jsonl`, because one candidate template seeds from an
    already-registered DEV record and a candidate-only `AssetRegistry` cannot resolve it.
    """
    return b"".join(
        canonical_artifact_bytes(
            {"record_type": "asset", "record": asset.model_dump(mode="json")}
        )
        + b"\n"
        for asset in candidates
    )


def _counts(dev: tuple[AssetRecord, ...], candidates: tuple[AssetRecord, ...]) -> dict[str, object]:
    new_ids = {asset.asset_id for asset in candidates}

    def tally(records: tuple[AssetRecord, ...]) -> dict[str, dict[str, int]]:
        rows: dict[str, dict[str, int]] = {}
        for asset in records:
            family = asset.coverage[0].value
            kind = asset.payload.kind.value
            form = getattr(asset.payload, "form", None)
            label = f"{kind}:{form.value}" if form is not None else kind
            rows.setdefault(family, {})
            rows[family][label] = rows[family].get(label, 0) + 1
        return {family: dict(sorted(counts.items())) for family, counts in sorted(rows.items())}

    return {
        "existing": tally(tuple(a for a in dev if a.asset_id not in new_ids)),
        "added_by_this_tranche": tally(candidates),
        "total": tally(dev),
        "totals": {
            "existing": len(dev) - len(candidates),
            "added": len(candidates),
            "atomic_added": sum(
                not isinstance(a.payload, TemplateAssetPayload) for a in candidates
            ),
            "template_added": sum(
                isinstance(a.payload, TemplateAssetPayload) for a in candidates
            ),
            "total": len(dev),
        },
    }


def _unit_json(unit: ReviewUnit, index: dict[str, AssetRecord]) -> dict[str, object]:
    return {
        "unit_id": unit.unit_id,
        "role": unit.role,
        "selection_class": unit.selection_class,
        "rationale": unit.rationale,
        "asset_ids": [asset.asset_id for asset in unit.assets],
        "lookup_query_and_ab_reviewed_as_one_unit": any(
            isinstance(asset.payload, LookupAssetPayload) for asset in unit.assets
        ),
        "records": [_asset_json(asset, index) for asset in unit.assets],
        "owner_disposition": "pending",
    }


def _asset_json(asset: AssetRecord, index: dict[str, AssetRecord]) -> dict[str, object]:
    value: dict[str, object] = {
        "asset_id": asset.asset_id,
        "content_sha256": asset.content_sha256,
        "split": asset.split.value,
        "coverage": [family.value for family in asset.coverage],
        "kind": asset.payload.kind.value,
    }
    if isinstance(asset.payload, TemplateAssetPayload):
        value["template"] = {
            "expands_kind": asset.payload.expands_kind.value,
            "raw_grammar": asset.payload.grammar,
            "seed_asset_ids": list(asset.payload.seed_asset_ids),
            "rendered_expansion": _rendered_expansion(asset.payload, index),
        }
    else:
        value["payload"] = asset.payload.model_dump(mode="json")
        value["protected_values"] = list(asset.protected_values)
    return value


_REPAIR_NOTES: dict[str, str] = {
    "mark-negative-partial": (
        "Repair B. The superseded wording 'Underline every mention of Perig' was a complete "
        "instruction, since 'Perig' reads as an ordinary proper name. This fragment stops "
        "mid-phrase and names no target, so it is unmistakably partial."
    ),
    "lookup-live-elder-basin-corrected": (
        "Repair A. Corrected replacement for a_34dfabfe62696f80b2369012: both answers now "
        "restate 'Elder Basin lantern tax' in full."
    ),
    "lookup-duplicate-lumen-wharf-corrected": (
        "Repair A. Corrected replacement for a_f335df3ed80a593cd2e26e4b: both answers now "
        "restate 'Lumen Wharf archive shelf' in full."
    ),
    "lookup-stale-sable-fork-corrected": (
        "Repair A. Corrected replacement for a_5503de16ebb134c361f9da99: both answers now "
        "restate 'Sable Fork observatory code' in full."
    ),
    "lookup-live-template": (
        "Repair A. Replaces a_7e1d3ea22ce2b596581d855b, which seeded a rejected record and "
        "demanded 'value-only results'. That clause is gone."
    ),
    "lookup-duplicate-template": (
        "Repair A. Replaces a_a83bf071eb48807b48934e78, which seeded a rejected record."
    ),
    "lookup-stale-template": (
        "Repair A. Replaces a_79369ef0645cf83737b1ae7c, which seeded a rejected record."
    ),
}


def _candidate_rationale(asset_id: str) -> str:
    role = _candidate_role(asset_id)
    if role in _REPAIR_NOTES:
        return _REPAIR_NOTES[role]
    if role in {row[0] for row in (*_MULTIPLICITY_TEXT, *_MULTIPLICITY_TIMER)} or role in {
        row[0] for row in _MULTIPLICITY_LOOKUP
    }:
        return (
            "Added to reach the three-seal-eligible-source-per-family minimum; reviewed at 100%."
        )
    return "New DEV candidate closing an audited coverage gap; reviewed at 100%."


def _candidate_role(asset_id: str) -> str:
    for role, *_ in (
        *_ATOMIC_CANDIDATES,
        *_MULTIPLICITY_TEXT,
        *_MULTIPLICITY_TIMER,
        *_MULTIPLICITY_LOOKUP,
        *_TEMPLATE_CANDIDATES,
    ):
        if _asset_id(role) == asset_id:
            return role
    raise DevReadinessError(f"asset id is not a tranche candidate: {asset_id}")


def _review_markdown(
    packet: dict[str, object],
    units: tuple[ReviewUnit, ...],
    coverage: dict[str, object],
    index: dict[str, AssetRecord],
) -> str:
    scope = packet["scope"]
    assert isinstance(scope, dict)
    selection = packet["selection"]
    assert isinstance(selection, dict)
    templates = coverage["template_slots"]
    assert isinstance(templates, list)
    gaps = [row for row in templates if str(row["parity"]).startswith("GAP")]
    shapes_source = coverage["atomic_shape_slots"]
    assert isinstance(shapes_source, list)
    absent = [row for row in shapes_source if row["was_absent_before_this_tranche"]]
    topped = [
        row
        for row in shapes_source
        if row["dev_added_asset_ids"] and not row["was_absent_before_this_tranche"]
    ]
    multiplicity = coverage["source_multiplicity"]
    assert isinstance(multiplicity, dict)
    restatement = coverage["subject_restatement"]
    assert isinstance(restatement, dict)
    rejected = coverage["rejected_records"]
    assert isinstance(rejected, dict)
    lines = [
        "# WP2-8 DEV asset-readiness review — v2",
        "",
        "Status: **pending owner review**. Nothing here is approved or sealed.",
        "",
        "This supersedes `review/phase2/dev-asset-readiness`, which is kept only as historical",
        "evidence and must not be approved or sealed.",
        "",
        "## What this is, in plain terms",
        "",
        "The development set is the last heldout canary before the training inputs freeze. It has",
        "to be written from wording the model has never seen in training, and it has to exercise",
        "every situation shape that survived the Phase 2 repairs — otherwise a template defect can",
        "slip past it.",
        "",
        f"There were already {scope['existing_dev_records']} DEV records on file. They were",
        "written early, against the original seeds, so they mirror the first version of each",
        "situation and miss everything that was added or repaired later. Three of them turned out",
        "to be wrong outright. This rebuild does four things:",
        "",
        f"1. **Rejects {len(rejected['records'])} records.** Three lookup records answered a",
        "   narrower question than they asked; three templates are built on them. None is edited —",
        "   they stay on file, unapproved, and outside the seal.",
        f"2. **Fills the coverage gaps.** {len(gaps)} template roles and {len(absent)} wording",
        "   shapes had no usable DEV record behind them.",
        f"3. **Raises every family to at least {multiplicity['minimum_per_family']} usable",
        "   sources**, so no DEV situation rests on a single piece of wording.",
        "4. **Adds 14 DEV-only responses** in a companion packet, so the dev set can exercise what",
        "   the assistant actually says out loud.",
        "",
        f"That comes to {scope['new_dev_candidates']} new records. After the rejections,",
        f"{scope['dev_records_seal_eligible']} of the {scope['dev_records_after_tranche']} DEV",
        "records on file could enter the seal.",
        "",
        "## The three rejected lookups, and why",
        "",
        "A lookup record holds a question and the two answers the world might give back. The rule",
        "is that an answer has to be about the same thing the question asked about. Wording can",
        "vary; the referent cannot. These three changed the referent:",
        "",
    ]
    for row in restatement["owner_rejected_for_changed_referent"]:
        record = index.get(row["asset_id"])
        if record is None or not isinstance(record.payload, LookupAssetPayload):
            continue
        payload = record.payload
        lines.append(
            f"- `{row['asset_id']}` asks `{_md(payload.query)}` but answers "
            f"`{_md(payload.result_a)}` — the word "
            + ", ".join(f"**{word}**" for word in row["unrepeated_query_words"])
            + " is gone, and with it the referent: it is a different thing."
        )
    lines.extend(
        [
            "",
            "Each has a corrected replacement under a new identity. The three templates that seed",
            "them are replaced too, so no approved template depends on a rejected record. The",
            "live-lookup template also loses its old “value-only results” instruction, which",
            "directly contradicted the rule above.",
            "",
            "`a_9ffb19423f7e143d6b25fde2` is fine and is kept: both of its answers say",
            "“Zephyr Steps notice” in full.",
            "",
            "A purely mechanical version of this test — every query word must reappear — also",
            "fires on records inside the existing TRAIN seal and the frozen TEST and DEMO seals,",
            "where the wording varies but the referent does not. Those are not defects and are",
            "not reopened. The token check is kept only as a review signal; the counts are in the",
            "coverage matrix under `subject_restatement.informational_other_splits`.",
            "",
            "## What the audit found missing",
            "",
        ]
    )
    for row in gaps:
        lines.append(f"- **{row['role']}** — {row['parity']}")
    lines.extend(
        ["", "On the wording side, DEV had no usable record for any of these:", ""]
    )
    for row in absent:
        label = f"{row['family']} · {row['kind']}:{row['form']}"
        if row["subtype"]:
            label += f" ({row['subtype']})"
        lines.append(f"- {label}")
    if topped:
        lines.extend(
            [
                "",
                "These shapes already had one usable record; sources were added only to reach the",
                f"{multiplicity['minimum_per_family']}-per-family minimum:",
                "",
            ]
        )
        for row in topped:
            label = f"{row['family']} · {row['kind']}:{row['form']}"
            if row["subtype"]:
                label += f" ({row['subtype']})"
            lines.append(
                f"- {label} — {len(row['dev_existing_asset_ids'])} already usable, "
                f"{len(row['dev_added_asset_ids'])} added"
            )
    lines.extend(
        ["", "## Usable sources per family", "", "| family | usable sources |", "|---|---:|"]
    )
    for row in multiplicity["families"]:
        lines.append(f"| `{row['family']}` | {row['seal_eligible_atomic_sources']} |")
    capacity = multiplicity["prose_need_capacity"]
    lines.extend(
        [
            "",
            "Only records that could enter the seal are counted, so the three rejected lookups do",
            "not prop up any number here. The prose-need shape — a factual need stated in ordinary",
            f"drafting prose — now has {capacity['reproducible_pairs']} usable DEV pairs, against",
            f"{capacity['train_reference']}.",
            "",
        ]
    )
    post_seed = coverage["post_seed_shapes_and_boundaries"]
    assert isinstance(post_seed, list)
    lines.extend(["", "## Shapes added or repaired after the original seeds", ""])
    lines.append(
        "These are stream-level shapes, not wording slots, so they are audited by name:"
    )
    lines.append("")
    for row in post_seed:
        lines.append(f"- **{row['shape']}** — `{row['dev_status']}`. {row['detail']}")
    lines.extend(
        [
            "",
            "## How the review list was chosen",
            "",
            f"- Every one of the {scope['new_dev_candidates']} new candidates is here. They are",
            "  new material, so none of them is sampled away.",
            f"- Every already-registered record the automated battery flagged is here"
            f" ({len(selection['flagged_or_rejected_asset_ids'])} of them, including the three"
            " rejected lookups and the three templates that seed them).",
            f"- Because one of the sampled records turned out to be defective, review expanded to"
            f" the whole lookup stratum: every DEV lookup record is here, which adds"
            f" {len(selection['expanded_lookup_stratum_asset_ids'])} more.",
            f"- A deterministic one-in-five stratified draw over the remaining ordinary"
            f" already-registered records adds {len(selection['ordinary_sampled_asset_ids'])}"
            " more, covering each payload kind at least once.",
            f"- Sampling seed: `{selection['sampling_seed']}`.",
            "- The 14 DEV response records are reviewed in the companion packet"
            " `review/phase2/dev-response-tranche`, at 100%.",
            "",
            "A lookup record carries its query and both A/B results in one record, so it is always",
            "read as a single unit. Templates are shown with their raw grammar and with the exact",
            "expansion the offline generator would hand a scenario.",
            "",
            "Reply once per listed asset:",
            "`approved|flagged|rejected <unit_id> <asset_id> <content_sha256> [reason]`.",
            "",
            "## Review units",
        ]
    )
    for unit in units:
        lines.extend(_unit_markdown(unit, index))
    lines.extend(
        [
            "",
            "## Not done here",
            "",
            "No approval record, no `dev-seal.json`, no registry change, no state generation, and",
            "no provider or teacher call. Four open questions are recorded in",
            "`JUDGMENT-NEEDED.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def _unit_markdown(unit: ReviewUnit, index: dict[str, AssetRecord]) -> list[str]:
    lines = ["", f"### `{unit.unit_id}`", "", unit.rationale]
    for asset in unit.assets:
        payload = asset.payload
        lines.extend(
            ["", f"Asset `{asset.asset_id}` — digest `{asset.content_sha256}` — split `dev`."]
        )
        if isinstance(payload, TextAssetPayload):
            lines.append(f"Text ({payload.form.value}): `{_md(payload.text)}`")
        elif isinstance(payload, LookupAssetPayload):
            lines.extend(
                [
                    "Read the query and both results together as one factual unit:",
                    f"- Query: `{_md(payload.query)}`",
                    f"- Result A: `{_md(payload.result_a)}`",
                    f"- Result B: `{_md(payload.result_b)}`",
                    f"- No-result code: `{payload.no_result_code}`",
                ]
            )
        elif isinstance(payload, TimerAssetPayload):
            lines.extend(
                [
                    f"Timer ({payload.form.value}): `{_md(payload.instruction)}`",
                    f"interval_ms: `{payload.interval_ms}`; "
                    f"message: `{_md(payload.message or '')}`",
                ]
            )
        elif isinstance(payload, TemplateAssetPayload):
            lines.extend(
                [
                    f"Template expanding `{payload.expands_kind.value}`.",
                    f"Grammar: `{_md(payload.grammar)}`",
                    "Seeds: " + ", ".join(f"`{seed}`" for seed in payload.seed_asset_ids),
                    "",
                    "Rendered expansion handed to the offline generator:",
                    "```text",
                    _rendered_expansion(payload, index),
                    "```",
                ]
            )
        if asset.protected_values:
            lines.append(
                "Protected wording: " + ", ".join(f"`{value}`" for value in asset.protected_values)
            )
    return lines


def _assert_no_frozen_overlap(
    candidates: tuple[AssetRecord, ...], roots: tuple[Path, ...], registry_path: Path
) -> None:
    """Fail closed if any candidate string appears in frozen TEST/DEMO or heldout material."""
    needles: dict[bytes, str] = {}
    for asset in candidates:
        payload = asset.payload
        values = [*asset.protected_values]
        if isinstance(payload, TextAssetPayload):
            values.append(payload.text)
        elif isinstance(payload, TimerAssetPayload):
            values.append(payload.instruction)
        elif isinstance(payload, LookupAssetPayload):
            values.extend((payload.query, payload.result_a, payload.result_b))
        for value in values:
            # ponytail: a byte scan on a 2-3 character needle only produces false hits. The
            # registry's own word-boundary cross-split protected check is the real guard for
            # short values; raise this floor only if a short leak is ever observed.
            if len(value) >= 4:
                needles[value.encode()] = asset.asset_id
    # Any asset registry inside a scan root is filtered to the other splits: DEV candidates
    # legitimately appear in the live approved registry once Gate B publishes them.
    registries = {registry_path.resolve(), LIVE_APPROVED_REGISTRY.resolve()}
    for root in roots:
        if not root.is_dir():
            raise DevReadinessError(f"heldout overlap root is missing: {root}")
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            if path.resolve() in registries:
                heldout = tuple(
                    asset
                    for asset in load_registry_jsonl(data).assets
                    if asset.split in (Split.TRAIN, Split.TEST, Split.DEMO)
                )
                data = render_registry_jsonl(AssetRegistry(assets=heldout))
            for needle, asset_id in needles.items():
                if needle in data:
                    raise DevReadinessError(
                        f"DEV candidate {asset_id} overlaps frozen material at {path}"
                    )


def _asset_id(role: str) -> str:
    return f"a_{sha256(f'{_VERSION}\0{role}'.encode()).hexdigest()[:24]}"


def _rank(role: str, asset_id: str) -> bytes:
    return sha256(f"{REVIEW_SAMPLING_SEED}\0{role}\0{asset_id}".encode()).digest()


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode("ascii")


def _md(value: str) -> str:
    return value.replace("`", "\\`").replace("\n", "<br>")
