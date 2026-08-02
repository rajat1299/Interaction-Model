import { describe, expect, it } from "vitest";
import { recordKey, type ReviewMap } from "./review-sidecar";
import {
  applyClusterDisposition,
  categoryCopy,
  clusterEvidenceCases,
  renderBlindedComparison,
  renderClusterRail,
  summarizeAction,
  textEquivalentAllowed,
} from "./phase2-review";
import type { Phase2Cluster, Phase2DecisionEvidence, Phase2ReviewEvidence } from "./types";

const stream = (letter: string) => `sha256:${letter.repeat(64)}`;
const evidenceSha = stream("f");

function decision(letter: string, choiceForOracle: "A" | "B", rank: number): Phase2DecisionEvidence {
  const oracle = { type: "respond" as const, reply_to_event_id: "e_1", text: "oracle" };
  const teacher = { type: "respond" as const, reply_to_event_id: "e_1", text: "teacher" };
  const candidate = (candidate_id: "A" | "B", isOracle: boolean) => ({
    candidate_id,
    action: isOracle ? oracle : teacher,
    license: { result: "licensed" as const, codes: [] },
    reveal: { origin: isOracle ? "oracle" as const : "teacher" as const, provenance: { request_sha256: stream(isOracle ? "1" : "2") } },
  });
  return {
    stream_sha256: stream(letter),
    decision_policy_seq: rank,
    oracle_action: oracle,
    comparison: "semantic_review_required",
    candidates: choiceForOracle === "A" ? [candidate("A", true), candidate("B", false)] : [candidate("A", false), candidate("B", true)],
    cluster_signature: `sha256:${"c".repeat(64)}`,
    priority_rank: rank,
    source_unit_id: `source-${letter}`,
    review_evidence: {
      wave_id: "wave", template_id: "template", causal_state_class: "state", boundary_class: "ordinary",
      risk_flags: ["oracle_teacher_non_equivalence"], idle_boundary: null, rollover: false,
      trust_cell: { protocol: "generation", family: "neutral_typing", floor: "closed" },
      review_route: { review_required: true, mandatory: true, sample_rate: 1, reasons: ["teacher_oracle_disagreement", "risk_flag"], provisional_label_origin: null },
    },
  };
}

describe("Phase 2 cluster adjudication", () => {
  it("presents frozen review data in plain language without revealing candidate origins", () => {
    expect(summarizeAction({
      type: "schedule",
      instruction: { event_id: "e_1", start_utf16: 0, end_utf16: 10, text: "Remind me" },
      interval_ms: 2_220_000,
      message: "open the fern ledger",
    }).summary).toBe("Create a recurring reminder every 37 minutes: “open the fern ledger”.");
    expect(categoryCopy("teacher_error").label).toBe("Reference candidate is wrong");
    expect(summarizeAction({
      type: "skip",
      target_event_id: "e_fire",
      reason: "canceled_timer",
    })).toEqual({
      verb: "Skip timer fire",
      summary: "Leave the due reminder unused because it was canceled.",
    });
    expect(summarizeAction(
      { type: "nudge", fire_event_id: "e_000016" },
      { timerMessages: new Map(), fireMessages: new Map([["e_000016", "open the fern ledger for the desk note"]]) },
    )).toEqual({
      verb: "Send reminder",
      summary: "Send the due reminder: “open the fern ledger for the desk note”.",
    });
    expect(summarizeAction(
      { type: "skip", target_event_id: "e_000028", reason: "stale_tool_result" },
      {
        timerMessages: new Map(),
        fireMessages: new Map(),
        resultSubjects: new Map([["e_000028", "Hollow Cinder postal zone"]]),
      },
    )).toEqual({
      verb: "Skip lookup result",
      summary: "Leave the result for “Hollow Cinder postal zone” unused because the user abandoned that lookup.",
    });
    expect(summarizeAction({
      type: "integrate",
      result_event_id: "e_result",
      text: "Brindle Port reports violet water.",
    })).toEqual({
      verb: "Use result",
      summary: "Add the available lookup result: “Brindle Port reports violet water.”",
    });

    const target = document.createElement("section");
    renderBlindedComparison(target, decision("a", "A", 0), false);
    expect(target.textContent).toContain("Reply to user");
    expect(target.textContent).toContain("Choose Candidate A");
    expect(target.textContent).not.toMatch(/Origin:|request_sha256/);
  });

  it("maps a batch disposition to each member's local A/B order only", () => {
    const members = [decision("a", "A", 0), decision("b", "B", 1), decision("c", "A", 2)];
    const outsider = decision("d", "B", 3);
    const cluster: Phase2Cluster = {
      signature: `sha256:${"c".repeat(64)}`,
      priority_rank: 0,
      representative: { stream_sha256: members[0].stream_sha256, decision_policy_seq: 0 },
      confirmations: [
        { stream_sha256: members[1].stream_sha256, decision_policy_seq: 1 },
        { stream_sha256: members[2].stream_sha256, decision_policy_seq: 2 },
      ],
      member_identities: members.map((item) => ({ stream_sha256: item.stream_sha256, decision_policy_seq: item.decision_policy_seq })),
      mechanical_invariants: { all_members_non_equivalent: true as const, distinct_source_unit_count: 3, member_count: 3, priority_order_sha256: stream("e"), three_distinct_source_units: true as const },
    };
    const evidence: Phase2ReviewEvidence = {
      format_version: 1,
      teacher_evidence_identity: stream("d"),
      blind_seed_sha256: stream("b"),
      decisions: [...members, outsider],
      clusters: [cluster],
      mechanical_invariants: { all_packet_decisions_included: true, decision_identity_count: 4, non_equivalent_decision_count: 4 },
    };
    const reviews: ReviewMap = new Map([
      [recordKey(outsider), { stream_sha256: outsider.stream_sha256, decision_policy_seq: 3, decision: "accept", reason_code: "ordinary", note: "keep" }],
    ]);

    const acknowledged = new Set(clusterEvidenceCases(cluster).map(recordKey));
    const applied = applyClusterDisposition(reviews, evidence, evidenceSha, cluster, "A", "teacher_error", "Shared D7 diagnosis.", acknowledged);

    expect(members.map((member) => applied.get(recordKey(member))?.candidate_choice)).toEqual(["A", "B", "A"]);
    expect(members.every((member) => applied.get(recordKey(member))?.disagreement_category === "teacher_error")).toBe(true);
    expect(applied.get(recordKey(outsider))?.note).toBe("keep");
    expect(applied.get(recordKey(members[0]))?.cluster_review?.reviewed_evidence.map((item) => item.role)).toEqual([
      "representative", "confirmation_1", "confirmation_2",
    ]);
  });

  it("requires exactly three acknowledgments and validates category eligibility before writes", () => {
    const members = [decision("a", "A", 0), decision("b", "B", 1), decision("c", "A", 2)];
    const cluster: Phase2Cluster = {
      signature: stream("c"),
      priority_rank: 0,
      representative: members[0],
      confirmations: [members[1], members[2]],
      member_identities: members,
      mechanical_invariants: { all_members_non_equivalent: true, distinct_source_unit_count: 3, member_count: 3, priority_order_sha256: stream("e"), three_distinct_source_units: true },
    };
    const evidence: Phase2ReviewEvidence = {
      format_version: 1, teacher_evidence_identity: stream("d"), blind_seed_sha256: stream("b"),
      decisions: members, clusters: [cluster],
      mechanical_invariants: { all_packet_decisions_included: true, decision_identity_count: 3, non_equivalent_decision_count: 3 },
    };
    const reviews: ReviewMap = new Map();
    const onlyRepresentative = new Set([recordKey(members[0])]);
    expect(() => applyClusterDisposition(reviews, evidence, evidenceSha, cluster, "A", "teacher_error", "Shared.", onlyRepresentative)).toThrow("exactly three");
    expect(reviews.size).toBe(0);

    members[2].candidates[1].action = { type: "respond", reply_to_event_id: "e_2", text: "teacher" };
    const acknowledged = new Set(clusterEvidenceCases(cluster).map(recordKey));
    expect(() => applyClusterDisposition(reviews, evidence, evidenceSha, cluster, "C" as "A", "teacher_error", "Shared.", acknowledged)).toThrow("choice is invalid");
    expect(() => applyClusterDisposition(reviews, evidence, evidenceSha, cluster, "A", "text_equivalent", "Shared.", acknowledged)).toThrow("not valid for every");
    expect(reviews.size).toBe(0);
  });

  it("only licenses text_equivalent for same-reference respond or integrate candidates", () => {
    expect(textEquivalentAllowed(decision("a", "A", 0))).toBe(true);
    const mismatch = decision("b", "A", 1);
    mismatch.candidates[1].action = { type: "respond", reply_to_event_id: "e_2", text: "teacher" };
    expect(textEquivalentAllowed(mismatch)).toBe(false);
  });

  it("renders the cluster worklist in deterministic priority order", () => {
    const member = { stream_sha256: stream("a"), decision_policy_seq: 0 };
    const cluster = (signature: string, priority_rank: number): Phase2Cluster => ({
      signature,
      priority_rank,
      representative: member,
      confirmations: [member, member],
      member_identities: [member, member, member],
      mechanical_invariants: {
        all_members_non_equivalent: true,
        distinct_source_unit_count: 3,
        member_count: 3,
        priority_order_sha256: stream("e"),
        three_distinct_source_units: true,
      },
    });
    const evidence = {
      clusters: [cluster(stream("1"), 7), cluster(stream("2"), 2)],
    } as Phase2ReviewEvidence;
    const target = document.createElement("section");

    renderClusterRail(target, evidence, null, () => undefined);

    expect([...target.querySelectorAll("button")].map((button) => button.textContent)).toEqual([
      "Priority 3 · 3 decisions · 2 confirmations",
      "Priority 8 · 3 decisions · 2 confirmations",
    ]);
  });
});
