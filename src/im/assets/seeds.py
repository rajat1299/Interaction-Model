"""Hand-authored, split-first Phase 1 seed pools.

This module contains only atomic lexical/world assets and small template
grammars. It does not generate scenarios, actions, labels, prompts, or timing
seeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from im.assets.model import (
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
)
from im.assets.registry import AssetRegistry


@dataclass(frozen=True, slots=True)
class SeedPools:
    """Unreviewed seed registry with the held-out pools awaiting human approval."""

    registry: AssetRegistry
    pending_review_splits: tuple[Split, ...]


@dataclass(frozen=True, slots=True)
class _SeedSpec:
    split: Split
    payload: TextAssetPayload | LookupAssetPayload | TimerAssetPayload
    protected_values: tuple[str, ...]


def _opaque_id(*parts: str) -> str:
    """Return a stable opaque artifact id; position, never content, owns identity."""
    preimage = "\0".join(("phase1-seed-pools-v1", *parts)).encode("utf-8")
    return f"a_{sha256(preimage).hexdigest()[:24]}"


def _text(split: Split, form: TextForm, text: str, protected: str) -> _SeedSpec:
    return _SeedSpec(split, TextAssetPayload(text=text, form=form), (protected,))


def _lookup(
    split: Split,
    subject: str,
    query_suffix: str,
    result_phrase: str,
    value_a: str,
    value_b: str,
    *protected: str,
    no_result_code: str | None = None,
) -> _SeedSpec:
    """Build a typed A/B/absent lookup package without repeating result shells."""
    code = no_result_code or f"{subject.casefold().replace(' ', '_')}_absent"
    return _SeedSpec(
        split,
        LookupAssetPayload(
            query=f"{subject} {query_suffix}",
            result_a=f"{subject} {result_phrase} {value_a}.",
            result_b=f"{subject} {result_phrase} {value_b}.",
            no_result_code=code,
        ),
        (subject, *(protected or (value_a, value_b))),
    )


def _timer(
    split: Split,
    instruction: str,
    form: TimerForm,
    protected: str,
    *,
    interval_ms: int | None = None,
    message: str | None = None,
) -> _SeedSpec:
    return _SeedSpec(
        split,
        TimerAssetPayload(
            instruction=instruction,
            form=form,
            interval_ms=interval_ms,
            message=message,
        ),
        (protected,),
    )


def _recurring_timer(
    split: Split,
    minutes: str,
    interval_ms: int,
    action: str,
    protected: str,
) -> _SeedSpec:
    return _timer(
        split,
        f"Remind me every {minutes} minutes to {action}.",
        TimerForm.SUPPORTED,
        protected,
        interval_ms=interval_ms,
        message=action,
    )


_SEEDS: dict[CorpusFamily, tuple[_SeedSpec, ...]] = {
    CorpusFamily.NEUTRAL_TYPING: (
        _text(
            Split.TRAIN,
            TextForm.NEUTRAL,
            "The terracotta envelope rests beside a damp sketchbook.",
            "terracotta envelope",
        ),
        _text(
            Split.TRAIN,
            TextForm.NEUTRAL,
            "Elowen revised the bridge paragraph twice after noon.",
            "Elowen",
        ),
        _text(
            Split.TRAIN,
            TextForm.NEUTRAL,
            "A blue cursor paused after the phrase about cedar shelves.",
            "cedar shelves",
        ),
        _text(
            Split.TRAIN,
            TextForm.NEUTRAL,
            "The final draft traded a long aside for a quieter ending.",
            "quieter ending",
        ),
        _text(
            Split.TRAIN,
            TextForm.NEUTRAL,
            "I moved the umber lamp sentence below the inventory list.",
            "umber lamp sentence",
        ),
        _text(
            Split.TRAIN,
            TextForm.NEUTRAL,
            "A brief revision replaced the narrow heading with a wider one.",
            "wider heading",
        ),
        _text(
            Split.TRAIN,
            TextForm.NEUTRAL,
            "Nico paused before finishing the final footnote.",
            "Nico",
        ),
        _text(
            Split.DEV,
            TextForm.NEUTRAL,
            "Mara left a small gap before continuing the itinerary.",
            "Mara",
        ),
        _text(
            Split.TEST,
            TextForm.NEUTRAL,
            "A silver bookmark shifted near the margin of the atlas.",
            "silver bookmark",
        ),
        _text(
            Split.DEMO,
            TextForm.NEUTRAL,
            "The kettle clicked while I rewrote the opening line.",
            "kettle clicked",
        ),
    ),
    CorpusFamily.MARK_POSITIVE: (
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Underline amber kiwi in the field notebook.",
            "amber kiwi",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Highlight the filler words um and you know in the interview transcript.",
            "filler words um and you know",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Mark the category Harbor Signal as active in the legend.",
            "category Harbor Signal",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Underline cobalt axolotl as a new amphibian member.",
            "cobalt axolotl",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Highlight 17 October 2031 in the harbor notes.",
            "17 October 2031",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Mark Dr. Imani Voss in the greenhouse log.",
            "Dr. Imani Voss",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Underline the first-aid kit in the weather journal.",
            "first-aid kit",
        ),
        _text(
            Split.DEV,
            TextForm.DIRECT,
            "Highlight coral badger in the survey summary.",
            "coral badger",
        ),
        _text(
            Split.TEST,
            TextForm.DIRECT,
            "Mark saffron tern in the shoreline notes.",
            "saffron tern",
        ),
        _text(
            Split.DEMO,
            TextForm.DIRECT,
            "Underline indigo vole in the garden ledger.",
            "indigo vole",
        ),
    ),
    CorpusFamily.MARK_NEGATIVE: (
        _text(
            Split.TRAIN,
            TextForm.AMBIGUOUS,
            "Stop marking the copper ibis.",
            "copper ibis",
        ),
        _text(
            Split.TRAIN,
            TextForm.AMBIGUOUS,
            "Switch from animal labels to color labels.",
            "color labels",
        ),
        _text(
            Split.TRAIN,
            TextForm.QUOTED,
            'The note says, "underline ember quail."',
            "ember quail",
        ),
        _text(Split.TRAIN, TextForm.CODE, "`underline frost marten`", "frost marten"),
        _text(Split.TRAIN, TextForm.PARTIAL, "Underli", "underli train fragment"),
        _text(
            Split.TRAIN,
            TextForm.AMBIGUOUS,
            "Stop marking the ruby otter.",
            "ruby otter",
        ),
        _text(
            Split.TRAIN,
            TextForm.AMBIGUOUS,
            "Highlight the specimen beside the margin.",
            "margin specimen",
        ),
        _text(
            Split.DEV,
            TextForm.QUOTED,
            'The archive quotes "underline jade otter" as an example.',
            "jade otter",
        ),
        _text(Split.TEST, TextForm.PARTIAL, "Highli", "highli fragment"),
        _text(Split.DEMO, TextForm.CODE, "`underline plum hare`", "plum hare"),
    ),
    CorpusFamily.LOOKUP_LIVE: (
        _lookup(Split.TRAIN, "Aster Quay", "wind index", "index is", "17", "29"),
        _lookup(
            Split.TRAIN, "Brindle Port", "tide color", "reports", "violet water", "copper water"
        ),
        _lookup(
            Split.TRAIN,
            "Cobalt Ridge",
            "trail count",
            "has",
            "41 open trails",
            "58 open trails",
            "41",
            "58",
        ),
        _lookup(
            Split.TRAIN,
            "Dawn Ferry",
            "gate letter",
            "gate is",
            "M",
            "R",
            "gate M",
            "gate R",
        ),
        _lookup(
            Split.TRAIN,
            "Hollow Cinder",
            "postal zone",
            "zone is",
            "14",
            "27",
            "zone 14",
            "zone 27",
        ),
        _lookup(
            Split.TRAIN,
            "Ivory Loop",
            "archive stamp",
            "stamp is",
            "heron",
            "ember",
            "heron stamp",
            "ember stamp",
        ),
        _lookup(
            Split.TRAIN,
            "Kindle Square",
            "ticket price",
            "price is",
            "18 crowns",
            "33 crowns",
        ),
        _lookup(Split.DEV, "Elder Basin", "lantern tax", "tax is", "6 shells", "9 shells"),
        _lookup(
            Split.TEST,
            "Fable Station",
            "platform",
            "uses platform",
            "3",
            "8",
            "platform 3",
            "platform 8",
        ),
        _lookup(
            Split.DEMO,
            "Glass Orchard",
            "harvest flag",
            "flag is",
            "north",
            "south",
            "flag north",
            "flag south",
        ),
    ),
    CorpusFamily.LOOKUP_DUPLICATE: (
        _lookup(Split.TRAIN, "Harbor Nix", "meter reading", "reads", "204", "317"),
        _lookup(Split.TRAIN, "Iron Vale", "signal word", "signal is", "kestrel", "waxflower"),
        _lookup(
            Split.TRAIN,
            "Juniper Arcade",
            "stall",
            "stall is",
            "12",
            "26",
            "stall 12",
            "stall 26",
        ),
        _lookup(Split.TRAIN, "Kestrel Moor", "ferry rate", "rate is", "5 tokens", "11 tokens"),
        _lookup(Split.TRAIN, "Orchid Span", "meter reading", "reads", "145", "266"),
        _lookup(
            Split.TRAIN,
            "Peregrine Dock",
            "signal word",
            "signal is",
            "spruce",
            "coral",
            "spruce signal",
            "coral signal",
        ),
        _lookup(
            Split.TRAIN,
            "Raven Hollow",
            "parcel shelf",
            "shelf is",
            "16",
            "24",
            "shelf 16",
            "shelf 24",
        ),
        _lookup(Split.DEV, "Lumen Wharf", "archive shelf", "shelf is", "Delta", "Sigma"),
        _lookup(Split.TEST, "Morrow Glen", "cistern level", "level is", "38", "64"),
        _lookup(
            Split.DEMO,
            "Nettle Crown",
            "beacon",
            "beacon is",
            "green",
            "gold",
            "green beacon",
            "gold beacon",
        ),
    ),
    CorpusFamily.LOOKUP_STALE: (
        _lookup(
            Split.TRAIN, "Opal Run", "rainfall", "received", "14 millimeters", "31 millimeters"
        ),
        _lookup(Split.TRAIN, "Parchment Bay", "museum hour", "opens at", "eight", "eleven"),
        _lookup(
            Split.TRAIN,
            "Quartz Fen",
            "bridge status",
            "bridge is",
            "clear",
            "closed",
            "clear bridge",
            "closed bridge",
        ),
        _lookup(Split.TRAIN, "Rook Market", "parcel color", "parcel is", "russet", "lilac"),
        _lookup(
            Split.TRAIN,
            "Violet Cove",
            "rainfall",
            "received",
            "12 millimeters",
            "28 millimeters",
        ),
        _lookup(
            Split.TRAIN,
            "Willow Yard",
            "museum hour",
            "opens at",
            "seven",
            "ten",
            "seven oclock",
            "ten oclock",
        ),
        _lookup(
            Split.TRAIN,
            "Xanthic Pier",
            "bridge status",
            "bridge is",
            "open",
            "blocked",
            "open bridge",
            "blocked bridge",
        ),
        _lookup(Split.DEV, "Sable Fork", "observatory code", "code is", "72", "94"),
        _lookup(
            Split.TEST,
            "Thistle Row",
            "gallery wing",
            "wing is",
            "east",
            "west",
            "east wing",
            "west wing",
        ),
        _lookup(
            Split.DEMO,
            "Umber Lake",
            "ferry bell",
            "bell rings",
            "two chimes",
            "seven times",
        ),
    ),
    CorpusFamily.TIMER_NORMAL: (
        _recurring_timer(Split.TRAIN, "seven", 420_000, "inspect the vellum chart", "vellum chart"),
        _recurring_timer(Split.TRAIN, "eleven", 660_000, "air the cedar room", "cedar room"),
        _recurring_timer(
            Split.TRAIN, "thirteen", 780_000, "check the brass compass", "brass compass"
        ),
        _recurring_timer(
            Split.TRAIN, "seventeen", 1_020_000, "refill the blue pitcher", "blue pitcher"
        ),
        _recurring_timer(
            Split.TRAIN, "thirty-one", 1_860_000, "sweep the quartz step", "quartz step"
        ),
        _recurring_timer(
            Split.TRAIN, "thirty-seven", 2_220_000, "open the fern ledger", "fern ledger"
        ),
        _recurring_timer(
            Split.TRAIN, "forty-one", 2_460_000, "warm the linen press", "linen press"
        ),
        _recurring_timer(Split.DEV, "nineteen", 1_140_000, "rotate the orchard map", "orchard map"),
        _recurring_timer(
            Split.TEST, "twenty-three", 1_380_000, "open the amber blinds", "amber blinds"
        ),
        _recurring_timer(Split.DEMO, "twenty-nine", 1_740_000, "water the moss tray", "moss tray"),
    ),
    CorpusFamily.TIMER_CANCEL: (
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Cancel the scarlet receipt reminder.",
            "scarlet receipt reminder",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Cancel the river stone reminder.",
            "river stone reminder",
        ),
        _timer(
            Split.TRAIN,
            'Oren said, "remind me every nine minutes to water juniper."',
            TimerForm.QUOTED,
            "Oren juniper timer",
        ),
        _timer(
            Split.TRAIN,
            (
                'The request says, "do not remind me every forty-one minutes '
                'to reset the copper dial."'
            ),
            TimerForm.QUOTED,
            "copper dial",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Stop the maroon lantern reminder.",
            "maroon lantern reminder",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Cancel the reminder beside the window.",
            "window reminder",
        ),
        _text(
            Split.TRAIN,
            TextForm.DIRECT,
            "Cancel the green harbor reminder.",
            "green harbor reminder",
        ),
        _text(
            Split.DEV,
            TextForm.QUOTED,
            'Ari wrote, "cancel the saffron reminder."',
            "Ari saffron reminder",
        ),
        _timer(
            Split.TEST,
            "Remind me tomorrow to tune the sun clock.",
            TimerForm.UNSUPPORTED,
            "sun clock tomorrow",
        ),
        _text(
            Split.DEMO,
            TextForm.NEGATED,
            "Do not cancel the ivory bell reminder.",
            "ivory bell reminder",
        ),
    ),
    CorpusFamily.TIMER_CONTENTION: (
        _recurring_timer(
            Split.TRAIN, "forty-seven", 2_820_000, "polish the jade lens", "jade lens"
        ),
        _recurring_timer(
            Split.TRAIN, "fifty-three", 3_180_000, "close the orchard gate", "orchard gate"
        ),
        _recurring_timer(
            Split.TRAIN, "fifty-nine", 3_540_000, "dust the copper shelf", "copper shelf"
        ),
        _recurring_timer(
            Split.TRAIN, "sixty-one", 3_660_000, "sort the violet cards", "violet cards"
        ),
        _recurring_timer(
            Split.TRAIN, "seventy-nine", 4_740_000, "clear the amber tray", "amber tray"
        ),
        _recurring_timer(
            Split.TRAIN, "eighty-three", 4_980_000, "dust the rose cabinet", "rose cabinet"
        ),
        _recurring_timer(
            Split.TRAIN, "eighty-nine", 5_340_000, "sort the pebble jars", "pebble jars"
        ),
        _recurring_timer(
            Split.DEV, "sixty-seven", 4_020_000, "fold the basalt flag", "basalt flag"
        ),
        _recurring_timer(
            Split.TEST, "seventy-one", 4_260_000, "seal the mint envelope", "mint envelope"
        ),
        _recurring_timer(
            Split.DEMO, "seventy-three", 4_380_000, "stack the linen tiles", "linen tiles"
        ),
    ),
    CorpusFamily.ROLLOVER: (
        _lookup(
            Split.TRAIN,
            "Varrow",
            "archive token",
            "token is",
            "AX-17",
            "BK-42",
            no_result_code="varrow_archive_absent",
        ),
        _lookup(
            Split.TRAIN,
            "Warden Quill",
            "docket",
            "docket is",
            "pine",
            "basalt",
            "pine docket",
            "basalt docket",
        ),
        _lookup(Split.TRAIN, "Xylo Basin", "cargo mark", "cargo is", "H-6", "J-9"),
        _lookup(Split.TRAIN, "Yarrow Pier", "signal", "signal is", "comet", "foxglove"),
        _lookup(Split.TRAIN, "Cedar Switch", "archive token", "token is", "CL-19", "DP-53"),
        _lookup(
            Split.TRAIN,
            "Dune Junction",
            "docket",
            "docket is",
            "moss",
            "slate",
            "moss docket",
            "slate docket",
        ),
        _lookup(Split.TRAIN, "Ember Crossing", "cargo mark", "cargo is", "L-4", "N-8"),
        _lookup(
            Split.DEV,
            "Zephyr Steps",
            "notice",
            "notice is",
            "ivory",
            "teal",
            "ivory notice",
            "teal notice",
        ),
        _lookup(Split.TEST, "Alder Loop", "registry", "registry is", "118", "203"),
        _lookup(
            Split.DEMO,
            "Birch Terminal",
            "route",
            "route is",
            "northbound",
            "southbound",
        ),
    ),
    CorpusFamily.RESERVED: (
        _text(
            Split.TRAIN,
            TextForm.OBSERVATIONAL,
            "The imported note carries a calm amber tag from a newer client.",
            "amber tag",
        ),
        _text(
            Split.TRAIN,
            TextForm.OBSERVATIONAL,
            "A future envelope records the fern badge without changing the draft.",
            "fern badge",
        ),
        _text(
            Split.TRAIN,
            TextForm.OBSERVATIONAL,
            "The sidebar shows a quiet cobalt stamp beside the entry.",
            "cobalt stamp",
        ),
        _text(
            Split.TRAIN,
            TextForm.OBSERVATIONAL,
            "An unfamiliar field preserves the violet ribbon as plain data.",
            "violet ribbon",
        ),
        _text(
            Split.TRAIN,
            TextForm.OBSERVATIONAL,
            "The imported row keeps a moss token beside the paragraph.",
            "moss token",
        ),
        _text(
            Split.TRAIN,
            TextForm.OBSERVATIONAL,
            "A future field carries a coral stamp through the session.",
            "coral stamp",
        ),
        _text(
            Split.TRAIN,
            TextForm.OBSERVATIONAL,
            "The saved envelope retains an indigo flag as plain data.",
            "indigo flag",
        ),
        _text(
            Split.DEV,
            TextForm.OBSERVATIONAL,
            "A forwarded parcel includes an umber token for later readers.",
            "umber token",
        ),
        _text(
            Split.TEST,
            TextForm.OBSERVATIONAL,
            "The archival row keeps a saffron seal without a visible effect.",
            "saffron seal",
        ),
        _text(
            Split.DEMO,
            TextForm.OBSERVATIONAL,
            "A dormant record holds a silver glyph for a future release.",
            "silver glyph",
        ),
    ),
}

_TEMPLATE_OPERATION = {
    CorpusFamily.NEUTRAL_TYPING: {
        Split.TRAIN: "leave the ordinary drafting pause intact",
        Split.DEV: "compare a quiet revision gap at the checkpoint",
        Split.TEST: "reserve an uneventful typing pause for scoring",
        Split.DEMO: "show a low-key editing continuation",
    },
    CorpusFamily.MARK_POSITIVE: {
        Split.TRAIN: "attach a direct mark to a concrete target",
        Split.DEV: "evaluate target-class marks without changing them",
        Split.TEST: "score a precise category activation",
        Split.DEMO: "present a clear marking cue",
    },
    CorpusFamily.MARK_NEGATIVE: {
        Split.TRAIN: "retain stopped or switched marking language",
        Split.DEV: "inspect a quoted or code-marked fragment",
        Split.TEST: "exercise a non-actionable mark boundary",
        Split.DEMO: "replay a partial or contextual mark phrase",
    },
    CorpusFamily.LOOKUP_LIVE: {
        Split.TRAIN: "pack an unresolved A/B/absent lookup",
        Split.DEV: "carry alternative lookup evidence through a check",
        Split.TEST: "test live-result ambiguity before choosing",
        Split.DEMO: "show competing lookup outcomes to the audience",
    },
    CorpusFamily.LOOKUP_DUPLICATE: {
        Split.TRAIN: "stage repeat-pressure lookup without issuing it",
        Split.DEV: "inspect the duplicated-result temptation",
        Split.TEST: "score a repeated-query boundary",
        Split.DEMO: "demonstrate unresolved duplicate pressure",
    },
    CorpusFamily.LOOKUP_STALE: {
        Split.TRAIN: "set aside a lookup as the topic moves",
        Split.DEV: "check a late result against a new topic",
        Split.TEST: "score an obsolete-result opening",
        Split.DEMO: "show a delayed answer missing its moment",
    },
    CorpusFamily.TIMER_NORMAL: {
        Split.TRAIN: "retain a recurring reminder with canonical fields",
        Split.DEV: "check the periodic reminder payload",
        Split.TEST: "score a normal repeating timer request",
        Split.DEMO: "present an ordinary recurring reminder",
    },
    CorpusFamily.TIMER_CONTENTION: {
        Split.TRAIN: "place a live timer beside unrelated work",
        Split.DEV: "inspect timing pressure around a normal event",
        Split.TEST: "score interference from a recurring source",
        Split.DEMO: "replay two competing event rhythms",
    },
    CorpusFamily.ROLLOVER: {
        Split.TRAIN: "carry lookup state across an explicit checkpoint",
        Split.DEV: "check continuation evidence after a handoff",
        Split.TEST: "score a preserved result package",
        Split.DEMO: "show a restart with unresolved lookup state",
    },
    CorpusFamily.RESERVED: {
        Split.TRAIN: "hold an unknown envelope as inert text",
        Split.DEV: "inspect unrecognized data without acting",
        Split.TEST: "score an opaque annotation boundary",
        Split.DEMO: "present a harmless future-facing field",
    },
}

_TEMPLATE_SCENE = {
    Split.TRAIN: "a quartz drafting table after the first revision",
    Split.DEV: "a topaz rehearsal card used for checkpoint selection",
    Split.TEST: "a basalt archive card reserved for final evaluation",
    Split.DEMO: "an obsidian stage prepared for public replay",
}


def _template_grammar(family: CorpusFamily, split: Split, kind: str) -> str:
    if family is CorpusFamily.TIMER_CANCEL:
        operation = {
            Split.TRAIN: (
                "record a cancellable text boundary"
                if kind == "text"
                else "frame a quoted timer boundary"
            ),
            Split.DEV: "inspect an in-context cancellation phrase",
            Split.TEST: "hold an unsupported timer request",
            Split.DEMO: "show a negated cancellation wording",
        }[split]
    else:
        operation = _TEMPLATE_OPERATION[family][split]
    scene = _TEMPLATE_SCENE[split]
    match split:
        case Split.TRAIN:
            return f"Start with {{seed}} at {scene}; {operation}."
        case Split.DEV:
            return f"Use {scene} to reshape {{seed}} while you {operation}."
        case Split.TEST:
            return f"At {scene}, let {{seed}} guide a held-out pass that will {operation}."
        case Split.DEMO:
            return f"Stage {{seed}} through {scene}, then {operation}."


def _asset_records() -> tuple[AssetRecord, ...]:
    records: list[AssetRecord] = []
    seeds_by_family_split: dict[tuple[CorpusFamily, Split], list[str]] = {}
    for family, entries in _SEEDS.items():
        if len(entries) != 10:
            raise AssertionError(f"{family} must have exactly ten atomic seeds")
        for index, entry in enumerate(entries, start=1):
            asset = AssetRecord.build(
                asset_id=_opaque_id("seed", family.value, entry.split.value, str(index)),
                split=entry.split,
                payload=entry.payload,
                provenance=AssetProvenance.SEED_AUTHORED,
                protected_values=entry.protected_values,
                coverage=(family,),
                rollover_eligible=family is CorpusFamily.ROLLOVER,
            )
            records.append(asset)
            seeds_by_family_split.setdefault((family, entry.split), []).append(asset.asset_id)

    for family in CorpusFamily:
        for split in Split:
            split_seeds = tuple(
                asset
                for asset in records
                if asset.asset_id in seeds_by_family_split[(family, split)]
            )
            for kind in sorted({asset.payload.kind for asset in split_seeds}, key=str):
                seed_asset_ids = tuple(
                    sorted(asset.asset_id for asset in split_seeds if asset.payload.kind is kind)
                )
                records.append(
                    AssetRecord.build(
                        asset_id=_opaque_id("template", family.value, split.value, str(kind)),
                        split=split,
                        payload=TemplateAssetPayload(
                            expands_kind=kind,
                            grammar=_template_grammar(family, split, str(kind)),
                            seed_asset_ids=seed_asset_ids,
                        ),
                        provenance=AssetProvenance.SEED_AUTHORED,
                        coverage=(family,),
                        rollover_eligible=family is CorpusFamily.ROLLOVER,
                    )
                )
    return tuple(records)


def build_seed_pools() -> SeedPools:
    """Build normal seed data without manufacturing review or seal evidence."""
    return SeedPools(
        registry=AssetRegistry(assets=_asset_records()),
        pending_review_splits=(Split.TEST, Split.DEMO),
    )


def build_seed_registry() -> AssetRegistry:
    """Return the deterministic seed registry without exposing scenario construction."""
    return build_seed_pools().registry
