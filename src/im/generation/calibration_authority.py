"""Immutable authority checks shared by G1 calibration materialization and review."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from im.assets import build_seed_registry
from im.assets.model import (
    CorpusFamily,
    LookupAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    canonical_artifact_bytes,
)
from im.generation.sidecar import PerturbationKind
from im.schema.textspan import utf16_len

if TYPE_CHECKING:
    from collections.abc import Mapping


CALIBRATION_HARDENED_MANIFEST_VERSION = "calibration-manifest/v4"
CALIBRATION_HARDENED_RECIPE_VERSION = "calibration-replay-recipe/v3"
CALIBRATION_LEGACY_HARDENED_MANIFEST_VERSION = "calibration-manifest/v3"
CALIBRATION_LEGACY_HARDENED_RECIPE_VERSION = "calibration-replay-recipe/v2"
CALIBRATION_MATERIALIZER_ID = "phase1-c7-exact-sampler-materializer-v1"
CALIBRATION_TARGET_SOURCE_VERSION = "calibration-target-source/v1"
CALIBRATION_PREFLIGHT_VERSION = "calibration-synthetic-preflight/v2"
CALIBRATION_TARGET_SOURCE_SET_VERSION = "calibration-target-source-set/v1"
INPUT_SYNTHESIS_PROFILE_VERSION = "input-synthesis-profile/v1"
MATERIALIZER_SOURCE_SET_VERSION = "calibration-materializer-source-set/v2"
RUNTIME_PRODUCER_IDENTITY_VERSION = "calibration-runtime-producer-identity/v1"
CALIBRATION_SYNTHETIC_REQUEST_VERSION = "calibration-synthetic-request/v1"
CALIBRATION_REGIMES = (
    "natural-drafting",
    "revision-heavy-writing",
    "copied-or-scripted-typing",
    "cursor-and-selection-edits",
    "short-command-like-inputs",
    "pauses-and-resumptions",
)
_C6_STREAM_KEYS = set(
    "format_version engine_version split family template assets master_seed timing "
    "stream_sha256 capture_sha256 sidecar_sha256 teacher_segment_sha256s decision_count "
    "identities declared_perturbations counterfactual".split()
)
_MATERIALIZER_ROOT_PATHS = frozenset(
    {
        "client/package.json",
        "client/package-lock.json",
        "client/vitest.config.ts",
        "client/tsconfig.json",
    }
)
_MATERIALIZER_ADAPTER_PATH = "client/src/calibration-synthetic.test.ts"
_BROWSER_SOURCE_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".json")
_RUNTIME_REQUIRED_PATHS = frozenset(
    {
        "pyproject.toml",
        "uv.lock",
        "spec/schema/event-v1.json",
        "spec/schema/action-v1.json",
        "spec/behavior-spec.md",
        "spec/prompt-template-v1.txt",
    }
)
_RUNTIME_DEPENDENCIES = frozenset(
    {"fastapi", "httpx", "pydantic", "python-dotenv", "uvicorn", "websockets"}
)
_IDENTITY_NOISE_DIRECTORIES = frozenset({"__pycache__", "dist", "generated", "node_modules"})


class CalibrationAuthorityError(ValueError):
    """An immutable calibration input fails the G1 authority contract."""


def producer_identity_admissible(manifest_version: object) -> bool:
    """Only v4 binds both browser and runtime producers; v3 remains readable evidence."""
    return manifest_version == CALIBRATION_HARDENED_MANIFEST_VERSION


@dataclass(frozen=True, slots=True)
class SourceAuthority:
    family: CorpusFamily
    declarations: tuple[PerturbationKind, ...]
    text: str
    text_sha256: str


def sha256_digest(data: bytes) -> str:
    """Return the canonical textual SHA-256 representation."""
    return f"sha256:{sha256(data).hexdigest()}"


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise CalibrationAuthorityError(f"{label} must be a non-empty trimmed string")
    return value


def _uint(value: object, label: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < int(positive):
        adjective = "positive" if positive else "non-negative"
        raise CalibrationAuthorityError(f"{label} must be a {adjective} integer")
    return value


def _digest(value: object, label: str) -> str:
    value = _text(value, label)
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise CalibrationAuthorityError(f"{label} must be a sha256 digest")
    return value


def _exact(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise CalibrationAuthorityError(f"{label} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _canonical_json(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationAuthorityError(f"{label} is not UTF-8 JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise CalibrationAuthorityError(f"{label} must be a canonical JSON object")
    return value


def _source_text(stream: dict[str, object]) -> str:
    assets = stream["assets"]
    if not isinstance(assets, list) or not assets:
        raise CalibrationAuthorityError("C6 stream assets are invalid")
    registry = {asset.asset_id: asset for asset in build_seed_registry().assets}
    values: list[str] = []
    for raw in assets:
        item = _exact(raw, {"asset_id", "content_sha256"}, "C6 stream asset")
        asset_id = _text(item["asset_id"], "C6 stream asset_id")
        asset = registry.get(asset_id)
        if asset is None or item["content_sha256"] != asset.content_sha256:
            raise CalibrationAuthorityError("C6 stream asset is not the sealed seed asset")
        if isinstance(asset.payload, TextAssetPayload):
            values.append(asset.payload.text)
        elif isinstance(asset.payload, LookupAssetPayload):
            values.append(asset.payload.query)
        elif isinstance(asset.payload, TimerAssetPayload):
            values.append(asset.payload.instruction)
        else:
            raise CalibrationAuthorityError("C6 stream asset has no calibration text field")
    return "\n\n".join(values)


def package_authority(
    package_bytes: bytes, *, require_seed_assets: bool = False
) -> dict[str, SourceAuthority]:
    """Validate the C6 packet and optionally resolve its sealed seed text."""
    package = _exact(
        _canonical_json(package_bytes, "C6 package manifest"),
        {"format_version", "streams"},
        "C6 package manifest",
    )
    if (
        package["format_version"] != 1
        or not isinstance(package["streams"], list)
        or not package["streams"]
    ):
        raise CalibrationAuthorityError("C6 package manifest version/streams are invalid")
    authority: dict[str, SourceAuthority] = {}
    for raw in package["streams"]:
        stream = _exact(raw, _C6_STREAM_KEYS, "C6 stream manifest")
        identity = _digest(stream["stream_sha256"], "C6 stream_sha256")
        if identity in authority:
            raise CalibrationAuthorityError("C6 package manifest repeats a stream identity")
        try:
            family = CorpusFamily(stream["family"])
        except (TypeError, ValueError) as error:
            raise CalibrationAuthorityError("C6 stream family is not closed") from error
        values = stream["declared_perturbations"]
        if not isinstance(values, list):
            raise CalibrationAuthorityError("C6 declared_perturbations must be a list")
        try:
            declarations = tuple(PerturbationKind(value) for value in values)
        except (TypeError, ValueError) as error:
            raise CalibrationAuthorityError("C6 perturbation is not closed") from error
        if declarations != tuple(sorted(set(declarations), key=lambda item: item.value)):
            raise CalibrationAuthorityError("C6 perturbations must be sorted and unique")
        text = _source_text(stream) if require_seed_assets else ""
        authority[identity] = SourceAuthority(
            family,
            declarations,
            text,
            sha256_digest(text.encode("utf-8")) if text else "",
        )
    if tuple(authority) != tuple(sorted(authority)):
        raise CalibrationAuthorityError("C6 package streams must be sorted by stream identity")
    return authority


def input_profile(profile_bytes: bytes) -> str:
    """Verify a fitted, closed-regime synthesis profile and return its identity."""
    profile = _exact(
        _canonical_json(profile_bytes, "input synthesis profile"),
        {"format_version", "input_profile_id", "sampler_throttle_ms", "regimes"},
        "input synthesis profile",
    )
    profile_id = _text(profile["input_profile_id"], "input_profile_id")
    if (
        profile["format_version"] != INPUT_SYNTHESIS_PROFILE_VERSION
        or profile_id == "baseline-unfitted"
        or _uint(profile["sampler_throttle_ms"], "sampler_throttle_ms", positive=True) < 1
        or not isinstance(profile["regimes"], dict)
        or set(profile["regimes"]) != set(CALIBRATION_REGIMES)
    ):
        raise CalibrationAuthorityError(
            "input synthesis profile is not a fitted closed-regime artifact"
        )
    return profile_id


def materializer_source_set(source_set_bytes: bytes) -> None:
    """Verify the browser producer identity committed before materialization."""
    source_set = _exact(
        _canonical_json(source_set_bytes, "calibration materializer source set"),
        {"format_version", "materializer_id", "files", "environment"},
        "calibration materializer source set",
    )
    files = source_set["files"]
    if (
        source_set["format_version"] != MATERIALIZER_SOURCE_SET_VERSION
        or source_set["materializer_id"] != CALIBRATION_MATERIALIZER_ID
        or not isinstance(files, list)
    ):
        raise CalibrationAuthorityError("calibration materializer source set is invalid")
    parsed = [
        _exact(value, {"path", "sha256"}, "calibration materializer source") for value in files
    ]
    paths = tuple(
        _text(item["path"], "calibration materializer source path") for item in parsed
    )
    if (
        not paths
        or paths != tuple(sorted(paths))
        or len(set(paths)) != len(paths)
        or not _MATERIALIZER_ROOT_PATHS.issubset(paths)
        or _MATERIALIZER_ADAPTER_PATH not in paths
    ):
        raise CalibrationAuthorityError("calibration materializer source paths are invalid")
    for item in parsed:
        path = _text(item["path"], "calibration materializer source path")
        if (
            _IDENTITY_NOISE_DIRECTORIES.intersection(PurePosixPath(path).parts)
            or (
                path not in _MATERIALIZER_ROOT_PATHS
                and not (path.startswith("client/src/") and path.endswith(_BROWSER_SOURCE_SUFFIXES))
            )
        ):
            raise CalibrationAuthorityError("calibration materializer source path is not closed")
        _digest(item["sha256"], "calibration materializer source sha256")
    environment = _exact(
        source_set["environment"],
        {
            "node_version",
            "npm_version",
            "os",
            "os_version",
            "arch",
            "installed_dependency_graph_sha256",
        },
        "calibration materializer environment",
    )
    for key in ("node_version", "npm_version", "os", "os_version", "arch"):
        _text(environment[key], f"calibration materializer environment.{key}")
    _digest(
        environment["installed_dependency_graph_sha256"],
        "calibration materializer environment.installed_dependency_graph_sha256",
    )


def runtime_producer_identity(identity_bytes: bytes) -> None:
    """Verify the Python runtime producer identity committed before replay."""
    identity = _exact(
        _canonical_json(identity_bytes, "calibration runtime producer identity"),
        {"format_version", "files", "environment"},
        "calibration runtime producer identity",
    )
    files = identity["files"]
    if (
        identity["format_version"] != RUNTIME_PRODUCER_IDENTITY_VERSION
        or not isinstance(files, list)
    ):
        raise CalibrationAuthorityError("calibration runtime producer identity is invalid")
    parsed = [
        _exact(value, {"path", "sha256"}, "calibration runtime producer source") for value in files
    ]
    paths = tuple(
        _text(item["path"], "calibration runtime producer source path") for item in parsed
    )
    if (
        not paths
        or paths != tuple(sorted(paths))
        or len(set(paths)) != len(paths)
        or not _RUNTIME_REQUIRED_PATHS.issubset(paths)
        or not any(path.startswith("src/im/") and path.endswith(".py") for path in paths)
    ):
        raise CalibrationAuthorityError("calibration runtime producer paths are invalid")
    for item in parsed:
        path = _text(item["path"], "calibration runtime producer source path")
        if (
            _IDENTITY_NOISE_DIRECTORIES.intersection(PurePosixPath(path).parts)
            or (
                path not in _RUNTIME_REQUIRED_PATHS
                and not (path.startswith("src/im/") and path.endswith(".py"))
            )
        ):
            raise CalibrationAuthorityError(
                "calibration runtime producer source path is not closed"
            )
        _digest(item["sha256"], "calibration runtime producer source sha256")
    environment = _exact(
        identity["environment"],
        {
            "python_implementation",
            "python_version",
            "sqlite_version",
            "os",
            "os_version",
            "arch",
            "dependency_versions",
        },
        "calibration runtime producer environment",
    )
    for key in (
        "python_implementation",
        "python_version",
        "sqlite_version",
        "os",
        "os_version",
        "arch",
    ):
        _text(environment[key], f"calibration runtime producer environment.{key}")
    dependencies = environment["dependency_versions"]
    if not isinstance(dependencies, dict) or set(dependencies) != _RUNTIME_DEPENDENCIES:
        raise CalibrationAuthorityError("calibration runtime dependency versions are invalid")
    for name, version in dependencies.items():
        _text(name, "calibration runtime dependency name")
        _text(version, f"calibration runtime dependency version {name}")


def preflight_manifest(
    preflight_bytes: bytes,
    *,
    package_sha256: str,
    acceptance_sha256: str,
    input_profile_sha256: str,
    materializer_source_set_sha256: str,
    runtime_producer_identity_sha256: str,
    materialization_request_sha256: str,
) -> None:
    """Verify the compact plan committed before synthetic materialization."""
    manifest = _exact(
        _canonical_json(preflight_bytes, "calibration preflight manifest"),
        {
            "format_version",
            "source_package",
            "source_acceptance",
            "input_profile",
            "materializer_source_set",
            "runtime_producer_identity",
            "materialization_request",
            "target_source_set",
        },
        "calibration preflight manifest",
    )
    if manifest["format_version"] != CALIBRATION_PREFLIGHT_VERSION:
        raise CalibrationAuthorityError("calibration preflight manifest version is invalid")
    for key, path, digest in (
        ("source_package", "source-package.json", package_sha256),
        ("source_acceptance", "source-acceptance.json", acceptance_sha256),
        ("input_profile", "input-synthesis-profile.json", input_profile_sha256),
        (
            "materializer_source_set",
            "materializer-source-set.json",
            materializer_source_set_sha256,
        ),
        (
            "runtime_producer_identity",
            "runtime-producer-identity.json",
            runtime_producer_identity_sha256,
        ),
        (
            "materialization_request",
            "materialization/request.json",
            materialization_request_sha256,
        ),
        ("target_source_set", "target-source-set.json", None),
    ):
        reference = _exact(manifest[key], {"path", "sha256"}, f"preflight {key}")
        if _text(reference["path"], f"preflight {key}.path") != path or (
            digest is not None and reference["sha256"] != digest
        ):
            raise CalibrationAuthorityError("calibration preflight manifest binding is invalid")
        _digest(reference["sha256"], f"preflight {key}.sha256")


def materialization_request(
    request_bytes: bytes,
    *,
    input_profile_id: str,
    input_profile_sha256: str,
    materializer_sha256: str,
) -> dict[str, dict[str, object]]:
    """Return the uniquely keyed, bound materializer batch request."""
    request = _exact(
        _canonical_json(request_bytes, "calibration materializer request"),
        {"format_version", "records"},
        "calibration materializer request",
    )
    records = request["records"]
    if request["format_version"] != CALIBRATION_SYNTHETIC_REQUEST_VERSION or not isinstance(
        records, list
    ):
        raise CalibrationAuthorityError("calibration materializer request is invalid")
    parsed: dict[str, dict[str, object]] = {}
    for value in records:
        record = _exact(
            value,
            {
                "runtime_session_id",
                "regime",
                "seed",
                "target_text",
                "transient_texts",
                "input_profile_id",
                "input_profile_sha256",
                "materializer_sha256",
                "target_source_sha256",
            },
            "calibration materializer request record",
        )
        session_id = _text(record["runtime_session_id"], "request runtime_session_id")
        if (
            session_id in parsed
            or record["regime"] not in CALIBRATION_REGIMES
            or _text(record["seed"], "request seed") != record["seed"]
            or _text(record["target_text"], "request target_text") != record["target_text"]
            or record["input_profile_id"] != input_profile_id
            or record["input_profile_sha256"] != input_profile_sha256
            or record["materializer_sha256"] != materializer_sha256
        ):
            raise CalibrationAuthorityError("calibration materializer request record is invalid")
        _digest(record["target_source_sha256"], "request target_source_sha256")
        transient_texts = record["transient_texts"]
        if not isinstance(transient_texts, list) or any(
            _text(item, "request transient_text") != item for item in transient_texts
        ):
            raise CalibrationAuthorityError(
                "calibration materializer request transients are invalid"
            )
        parsed[session_id] = record
    if not parsed:
        raise CalibrationAuthorityError("calibration materializer request records are empty")
    return parsed


def _contributors(
    value: object, authority: Mapping[str, SourceAuthority], label: str
) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CalibrationAuthorityError(f"{label} must be a non-empty list")
    texts: list[str] = []
    for raw in value:
        contributor = _exact(raw, {"source_stream_sha256", "source_text_sha256"}, label)
        stream_id = _digest(contributor["source_stream_sha256"], f"{label}.source_stream_sha256")
        source = authority.get(stream_id)
        if source is None or contributor["source_text_sha256"] != source.text_sha256:
            raise CalibrationAuthorityError(f"{label} does not bind sealed source text")
        texts.append(source.text)
    return tuple(texts)


def target_source(
    target_source_bytes: bytes,
    *,
    source_stream_sha256: str,
    authority: Mapping[str, SourceAuthority],
) -> tuple[str, list[str]]:
    """Derive the materializer target and transient drafts from sealed source text."""
    source = _exact(
        _canonical_json(target_source_bytes, "calibration target source"),
        {
            "format_version",
            "selected_source_stream_sha256",
            "target_contributors",
            "transient_contributors",
            "joiner",
            "target_text",
            "transient_texts",
            "target_scalar_length",
            "target_utf16_length",
        },
        "calibration target source",
    )
    if (
        source["format_version"] != CALIBRATION_TARGET_SOURCE_VERSION
        or source["selected_source_stream_sha256"] != source_stream_sha256
        or source["joiner"] != "\n\n"
    ):
        raise CalibrationAuthorityError("calibration target source identity is invalid")
    target_contributors = _contributors(
        source["target_contributors"], authority, "target contributors"
    )
    transients = source["transient_contributors"]
    if not isinstance(transients, list):
        raise CalibrationAuthorityError("calibration target transients are invalid")
    contributor_ids = [
        _digest(item["source_stream_sha256"], "target contributors.source_stream_sha256")
        for item in source["target_contributors"]
    ]
    for value in transients:
        if not isinstance(value, list):
            raise CalibrationAuthorityError("calibration target transients are invalid")
        contributor_ids.extend(
            _digest(item["source_stream_sha256"], "transient contributors.source_stream_sha256")
            for item in value
            if isinstance(item, dict)
        )
    if source_stream_sha256 not in contributor_ids:
        raise CalibrationAuthorityError(
            "calibration target does not bind its selected source stream"
        )
    transient_texts = [
        "\n\n".join(_contributors(value, authority, "transient contributors"))
        for value in transients
    ]
    target_text = "\n\n".join(target_contributors)
    if (
        source["target_text"] != target_text
        or source["transient_texts"] != transient_texts
        or source["target_scalar_length"] != len(target_text)
        or source["target_utf16_length"] != utf16_len(target_text)
    ):
        raise CalibrationAuthorityError("calibration target source text is invalid")
    return target_text, transient_texts


def source_acceptance(
    acceptance_bytes: bytes,
    *,
    acceptance_sha256: str,
    package_bytes: bytes,
    package_sha256: str,
    strong: bool,
    repository_root: Path | None = None,
) -> dict[str, int]:
    """Validate acceptance scope and, for production, the canonical G7 packet binding."""
    try:
        value = json.loads(acceptance_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationAuthorityError("source acceptance is not UTF-8 JSON") from error
    accepted = _exact(
        value,
        {
            "decision",
            "format_version",
            "notes",
            "packet",
            "reviewed_at",
            "reviewer_id",
            "scope",
            "template_promotion",
            "training_corpus_admission_eligible",
        },
        "source acceptance",
    )
    packet = _exact(
        accepted["packet"],
        {
            "g7_readiness_sha256",
            "manifest_sha256",
            "packet_json_sha256",
            "path",
            "response_delta_sha256",
            "review_sha256",
            "sha256s_sha256",
        },
        "source acceptance.packet",
    )
    scope = _exact(
        accepted["scope"],
        {"approved_response_delta_count", "approved_stream_count"},
        "source acceptance scope",
    )
    approved_stream_count = _uint(
        scope["approved_stream_count"], "approved_stream_count", positive=True
    )
    approved_response_delta_count = _uint(
        scope["approved_response_delta_count"], "approved_response_delta_count"
    )
    if (
        accepted["format_version"] != 1
        or accepted["decision"] != "approved"
        or accepted["training_corpus_admission_eligible"] is not False
        or packet["manifest_sha256"] != package_sha256
    ):
        raise CalibrationAuthorityError(
            "source acceptance does not bind the approved non-training package"
        )
    if strong:
        from im.generation.calibration_coverage import (
            G7_ACCEPTANCE_PATH,
            G7_MANIFEST_PATH,
            _accepted_hashes,
            _verify_g7_binding,
        )

        root = repository_root or Path(__file__).resolve().parents[3]
        try:
            manifest, acceptance = _verify_g7_binding(
                {
                    "manifest": {"path": G7_MANIFEST_PATH, "sha256": package_sha256},
                    "acceptance": {
                        "path": G7_ACCEPTANCE_PATH,
                        "sha256": acceptance_sha256,
                    },
                    "accepted_artifact_hashes": _accepted_hashes(value),
                },
                root,
            )
        except ValueError as error:
            raise CalibrationAuthorityError(
                "source acceptance is not canonical G7 authority"
            ) from error
        if manifest.data != package_bytes or acceptance.data != acceptance_bytes:
            raise CalibrationAuthorityError("source acceptance does not bind canonical G7 bytes")
    return {
        "approved_response_delta_count": approved_response_delta_count,
        "approved_stream_count": approved_stream_count,
    }


def validate_materialization_recipe(
    recipe_bytes: bytes,
    *,
    package_sha256: str,
    acceptance_sha256: str,
    input_profile_bytes: bytes,
    input_profile_sha256: str,
    materializer_source_set_bytes: bytes,
    materializer_sha256: str,
    runtime_producer_identity_bytes: bytes,
    runtime_producer_identity_sha256: str,
    materialization_request_sha256: str,
    request_records: Mapping[str, dict[str, object]],
    target_source_bytes: bytes,
    target_source_sha256: str,
    authority: Mapping[str, SourceAuthority],
    source_stream_sha256: str,
    session_id: str,
    regime: str,
    browser_bundle_sha256: str,
    runtime_session_sha256: str,
    policy_id: str,
) -> tuple[str, list[str]]:
    """Validate a recipe's immutable identity bindings and return its sealed target."""
    recipe = _exact(
        _canonical_json(recipe_bytes, "calibration replay recipe"),
        {
            "format_version",
            "source_package_sha256",
            "source_acceptance_sha256",
            "source_stream_sha256",
            "runtime_session_id",
            "regime",
            "input_profile_id",
            "input_profile_sha256",
            "input_seed",
            "target_text",
            "target_source_sha256",
            "materialization_request_sha256",
            "browser_bundle_sha256",
            "runtime_session_sha256",
            "materializer_id",
            "materializer_sha256",
            "runtime_producer_identity_sha256",
            "policy_id",
            "network",
            "training_eligible",
        },
        "calibration replay recipe",
    )
    profile_id = input_profile(input_profile_bytes)
    materializer_source_set(materializer_source_set_bytes)
    runtime_producer_identity(runtime_producer_identity_bytes)
    if (
        recipe["format_version"] != CALIBRATION_HARDENED_RECIPE_VERSION
        or recipe["source_package_sha256"] != package_sha256
        or recipe["source_acceptance_sha256"] != acceptance_sha256
        or recipe["source_stream_sha256"] != source_stream_sha256
        or recipe["runtime_session_id"] != session_id
        or recipe["regime"] != regime
        or recipe["input_profile_id"] != profile_id
        or recipe["input_profile_sha256"] != input_profile_sha256
        or recipe["materializer_sha256"] != materializer_sha256
        or recipe["runtime_producer_identity_sha256"] != runtime_producer_identity_sha256
        or recipe["materialization_request_sha256"] != materialization_request_sha256
        or recipe["target_source_sha256"] != target_source_sha256
        or recipe["browser_bundle_sha256"] != browser_bundle_sha256
        or recipe["runtime_session_sha256"] != runtime_session_sha256
        or recipe["materializer_id"] != CALIBRATION_MATERIALIZER_ID
        or recipe["policy_id"] != policy_id
        or recipe["network"] != "disabled"
        or recipe["training_eligible"] is not False
    ):
        raise CalibrationAuthorityError("calibration replay recipe binding is invalid")
    input_seed = _text(recipe["input_seed"], "calibration input_seed")
    target_text, transient_texts = target_source(
        target_source_bytes,
        source_stream_sha256=source_stream_sha256,
        authority=authority,
    )
    if recipe["target_text"] != target_text:
        raise CalibrationAuthorityError("calibration replay recipe target is invalid")
    request = request_records.get(session_id)
    if request is None or (
        request["runtime_session_id"] != session_id
        or request["regime"] != regime
        or request["seed"] != input_seed
        or request["target_text"] != target_text
        or request["transient_texts"] != transient_texts
        or request["input_profile_id"] != profile_id
        or request["input_profile_sha256"] != input_profile_sha256
        or request["materializer_sha256"] != materializer_sha256
        or request["target_source_sha256"] != target_source_sha256
    ):
        raise CalibrationAuthorityError(
            "calibration replay recipe does not bind its materializer request"
        )
    return target_text, transient_texts
