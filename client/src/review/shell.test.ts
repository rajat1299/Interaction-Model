import { afterEach, describe, expect, it, vi } from "vitest";
import {
  adoptLoadedPacket,
  loadPacketEntries,
  loadTeacherLabelsText,
  mountReviewShell,
} from "./shell";
import { loadPacketFromEntries } from "./packet-loader";
import { loadCanaryEntries, loadCanaryTeacherLabels, loadTimerWave1Entries } from "./test-fixtures";
import type { LoadedPacket } from "./types";

const PHASE2_EVIDENCE_SHA = `sha256:${"f".repeat(64)}`;

function phase2Packet(
  packet: LoadedPacket,
  phase2EvidenceSha256 = PHASE2_EVIDENCE_SHA,
): LoadedPacket {
  const targets = packet.streams.slice(0, 3).map((stream, index) => ({
    stream: stream.sidecar.stream_sha256,
    seq: stream.sidecar.decisions[0].observed_policy_seq,
    source: `source-${index}`,
  }));
  let rank = 0;
  const decisions = packet.streams.flatMap((stream) => stream.sidecar.decisions.map((sidecar) => {
    const target = targets.find((item) => item.stream === stream.sidecar.stream_sha256 && item.seq === sidecar.observed_policy_seq);
    const alternate = sidecar.action.type === "nudge"
      ? { type: "idle" as const, reason: "no_trigger" as const, related_event_id: null }
      : { type: "nudge" as const, fire_event_id: "e_000001" };
    const oracleFirst = target ? target.source !== "source-1" : rank % 2 === 0;
    const candidate = (id: "A" | "B", oracle: boolean) => ({
      candidate_id: id,
      action: oracle ? sidecar.action : alternate,
      license: { result: "licensed" as const, codes: [] },
      reveal: { origin: oracle ? "oracle" as const : "teacher" as const, provenance: { request_sha256: `sha256:${(oracle ? "1" : "2").repeat(64)}` } },
    });
    const record = {
      stream_sha256: stream.sidecar.stream_sha256,
      decision_policy_seq: sidecar.observed_policy_seq,
      oracle_action: sidecar.action,
      comparison: target ? "causal_disagreement" as const : "equivalent" as const,
      candidates: target ? (oracleFirst ? [candidate("A", true), candidate("B", false)] : [candidate("A", false), candidate("B", true)]) : [],
      cluster_signature: target ? `sha256:${"c".repeat(64)}` : null,
      priority_rank: rank++,
      source_unit_id: target?.source ?? "ordinary-source",
      review_evidence: {
        wave_id: "sentinel", template_id: "template", causal_state_class: "state", boundary_class: "ordinary",
        risk_flags: target ? ["oracle_teacher_non_equivalence"] : [], idle_boundary: null, rollover: false,
        trust_cell: { protocol: "generation", family: "neutral_typing", floor: "closed" },
        review_route: { review_required: Boolean(target), mandatory: Boolean(target), sample_rate: target ? 1 : 0, reasons: target ? ["disagreement"] : [], provisional_label_origin: null },
      },
    };
    return record;
  }));
  const identities = targets.map((target) => ({ stream_sha256: target.stream, decision_policy_seq: target.seq }));
  return {
    ...packet,
    integrity: { ...packet.integrity, phase2EvidenceSha256 },
    phase2ReviewEvidence: {
      format_version: 1,
      teacher_evidence_identity: `sha256:${"d".repeat(64)}`,
      blind_seed_sha256: `sha256:${"b".repeat(64)}`,
      decisions,
      clusters: [{
        signature: `sha256:${"c".repeat(64)}`,
        priority_rank: decisions.find((decision) => decision.cluster_signature !== null)!.priority_rank,
        representative: identities[0],
        confirmations: [identities[1], identities[2]],
        member_identities: identities,
        mechanical_invariants: { all_members_non_equivalent: true, distinct_source_unit_count: 3, member_count: 3, priority_order_sha256: `sha256:${"e".repeat(64)}`, three_distinct_source_units: true },
      }],
      mechanical_invariants: { all_packet_decisions_included: true, decision_identity_count: decisions.length, non_equivalent_decision_count: 3 },
    },
  } as LoadedPacket;
}

function phase2LegacyPacket(packet: LoadedPacket): LoadedPacket {
  const phase2 = phase2Packet(packet);
  const evidence = phase2.phase2ReviewEvidence!;
  return {
    ...phase2,
    phase2ReviewEvidence: {
      ...evidence,
      decisions: evidence.decisions.map((decision) => ({
        ...decision,
        comparison: "equivalent" as const,
        candidates: [],
        cluster_signature: null,
      })),
      clusters: [],
      mechanical_invariants: {
        ...evidence.mechanical_invariants,
        non_equivalent_decision_count: 0,
      },
    },
  } as LoadedPacket;
}

function queueGroupFor(button: Element): HTMLButtonElement[] {
  let label: Element | null = button.previousElementSibling;
  while (label && !label.classList.contains("queue-stream-label")) label = label.previousElementSibling;
  const result: HTMLButtonElement[] = [];
  for (let item = label?.nextElementSibling ?? null; item && !item.classList.contains("queue-stream-label"); item = item.nextElementSibling) {
    if (item instanceof HTMLButtonElement) result.push(item);
  }
  return result;
}

describe("review shell", () => {
  let cleanup: (() => void) | null = null;

  afterEach(() => {
    cleanup?.();
    cleanup = null;
    window.localStorage.clear();
    document.body.innerHTML = "";
  });

  it("starts as a checksum intake state and reveals the workspace only after load", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);

    expect(document.getElementById("empty-state")!.hidden).toBe(false);
    expect(document.getElementById("empty-state")!.textContent).toContain("Open a review packet to begin");
    expect(document.getElementById("empty-state")!.textContent).toContain("Choose the better blinded result");
    expect(document.getElementById("review-workspace")!.hidden).toBe(true);
    expect((document.getElementById("btn-save-cluster") as HTMLButtonElement).disabled).toBe(true);
    expect((document.getElementById("import-review") as HTMLInputElement).disabled).toBe(true);
    expect((document.getElementById("btn-export") as HTMLButtonElement).disabled).toBe(true);
    expect((document.getElementById("btn-reset-packet") as HTMLButtonElement).disabled).toBe(true);

    expect(await loadPacketEntries(loadCanaryEntries())).toBeNull();
    expect(document.getElementById("empty-state")!.hidden).toBe(true);
    expect(document.getElementById("review-workspace")!.hidden).toBe(false);
    expect((document.getElementById("import-review") as HTMLInputElement).disabled).toBe(false);
    expect((document.getElementById("btn-export") as HTMLButtonElement).disabled).toBe(false);
    expect((document.getElementById("btn-reset-packet") as HTMLButtonElement).disabled).toBe(false);
    expect((document.querySelector('#decision-decision option[value="accept"]') as HTMLOptionElement).textContent).toBe("Correct");
    expect((document.querySelector('#decision-decision option[value="reject"]') as HTMLOptionElement).textContent).toBe("Incorrect");
    expect((document.querySelector('#decision-decision option[value="flag"]') as HTMLOptionElement).textContent).toBe("Unsure");
  });

  it("starts only the current packet over after confirmation", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    expect(await loadPacketEntries(loadCanaryEntries())).toBeNull();

    const outcome = document.getElementById("stream-decision") as HTMLSelectElement;
    outcome.value = "accept";
    document.getElementById("btn-save-stream")!.click();
    window.localStorage.setItem("another-packet", "keep");
    const before = Object.keys(window.localStorage).filter((key) => key.startsWith("wp1-8-review-draft"));
    expect(before.length).toBeGreaterThan(0);

    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    document.getElementById("btn-reset-packet")!.click();
    expect((document.getElementById("stream-decision") as HTMLSelectElement).value).toBe("accept");
    document.getElementById("btn-reset-packet")!.click();

    expect(confirm).toHaveBeenCalledTimes(2);
    expect((document.getElementById("stream-decision") as HTMLSelectElement).value).toBe("");
    expect(Object.keys(window.localStorage).filter((key) => key.startsWith("wp1-8-review-draft"))).toEqual([]);
    expect(window.localStorage.getItem("another-packet")).toBe("keep");
  });

  it("supports essential keyboard navigation after load", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);

    const err = await loadPacketEntries(loadCanaryEntries());
    expect(err).toBeNull();

    const meta = () => document.getElementById("nav-meta")!.textContent ?? "";
    expect(meta()).toMatch(/Decision \d+ of \d+/);
    const initialEvent = JSON.parse(document.getElementById("inspect-event")!.textContent!).seq;
    const event = JSON.parse(document.getElementById("inspect-event")!.textContent!);
    const oracle = JSON.parse(document.getElementById("inspect-oracle")!.textContent!);
    expect(event.seq).toBe(oracle.observed_policy_seq);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "j" }));
    expect(JSON.parse(document.getElementById("inspect-event")!.textContent!).seq).toBe(initialEvent + 1);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k" }));
    expect(JSON.parse(document.getElementById("inspect-event")!.textContent!).seq).toBe(initialEvent);

    const initialDecision = Number(meta().match(/Decision (\d+) of/)?.[1]);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "n" }));
    expect(Number(meta().match(/Decision (\d+) of/)?.[1])).toBe(initialDecision + 1);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "p" }));
    expect(Number(meta().match(/Decision (\d+) of/)?.[1])).toBe(initialDecision);

    const activeBefore = document.querySelector(".stream-item.active")?.textContent;
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "]" }));
    expect(document.querySelector(".stream-item.active")?.textContent).not.toBe(activeBefore);
    expect(document.getElementById("load-status")!.textContent).not.toContain("family");
  });

  it("queues and opens a different-type teacher disagreement by decision identity", async () => {
    const result = await loadPacketFromEntries(loadCanaryEntries());
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const target = result.packet.streams[0];
    const targetDecision = target.sidecar.decisions[0];
    const teacherAction =
      targetDecision.action.type === "idle"
        ? { type: "nudge" as const, fire_event_id: "e_missing" }
        : { type: "idle" as const, reason: "no_trigger" as const, related_event_id: null };

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(result.packet);
    const preexistingReview = document.getElementById("stream-decision") as HTMLSelectElement;
    preexistingReview.value = "accept";
    document.getElementById("btn-save-stream")!.click();
    expect(
      await loadTeacherLabelsText(
        JSON.stringify({
          stream_sha256: `sha256:${target.sha256}`,
          decision_policy_seq: targetDecision.observed_policy_seq,
          action: teacherAction,
          label: "completed",
        }),
      ),
    ).toBeNull();
    expect((document.getElementById("stream-decision") as HTMLSelectElement).value).toBe("");

    const button = document.querySelector<HTMLButtonElement>(`.stream-item[data-stream-sha="${target.sha256}"]`);
    expect(button).toBeTruthy();
    button!.click();
    const event = JSON.parse(document.getElementById("inspect-event")!.textContent!);
    const oracle = JSON.parse(document.getElementById("inspect-oracle")!.textContent!);
    expect(event.seq).toBe(targetDecision.observed_policy_seq);
    expect(oracle.observed_policy_seq).toBe(targetDecision.observed_policy_seq);
    expect(document.getElementById("teacher-panel")!.textContent).toContain(
      "CAUSAL DISAGREEMENT",
    );
  });

  it("queues same-reference teacher wording for semantic review", async () => {
    const result = await loadPacketFromEntries(loadCanaryEntries());
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const target = result.packet.streams.find((stream) =>
      stream.sidecar.decisions.some(({ action }) =>
        action.type === "integrate" || action.type === "respond",
      ),
    );
    expect(target).toBeTruthy();
    if (!target) return;
    const targetDecision = target.sidecar.decisions.find(({ action }) =>
      action.type === "integrate" || action.type === "respond",
    );
    expect(targetDecision).toBeTruthy();
    if (!targetDecision || (targetDecision.action.type !== "integrate" && targetDecision.action.type !== "respond")) return;
    const teacherAction = { ...targetDecision.action, text: "Teacher wording requiring review." };

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(result.packet);
    expect(
      await loadTeacherLabelsText(
        JSON.stringify({
          stream_sha256: `sha256:${target.sha256}`,
          decision_policy_seq: targetDecision.observed_policy_seq,
          action: teacherAction,
          label: "semantic_review_required",
        }),
      ),
    ).toBeNull();

    const button = document.querySelector<HTMLButtonElement>(`.stream-item[data-stream-sha="${target.sha256}"]`);
    expect(button).toBeTruthy();
    button!.click();
    const oracle = JSON.parse(document.getElementById("inspect-oracle")!.textContent!);
    expect(oracle.observed_policy_seq).toBe(targetDecision.observed_policy_seq);
    expect(document.getElementById("teacher-panel")!.textContent).toContain(
      "SEMANTIC REVIEW REQUIRED",
    );
    expect(document.getElementById("progress")!.textContent).toContain("1 left");
  });

  it("loads the repaired canary labels into the real review queue", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    expect(await loadPacketEntries(loadCanaryEntries())).toBeNull();
    expect(await loadTeacherLabelsText(loadCanaryTeacherLabels())).toBeNull();
    expect(document.getElementById("progress")!.textContent).toContain("50 left");
  });

  it("persists a packet-keyed draft and guards unexported work", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    expect(await loadPacketEntries(loadCanaryEntries())).toBeNull();

    const select = document.getElementById("stream-decision") as HTMLSelectElement;
    select.value = "accept";
    document.getElementById("btn-save-stream")!.click();
    const unload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(true);

    cleanup();
    cleanup = null;
    document.body.innerHTML = "";
    const remount = document.createElement("div");
    document.body.appendChild(remount);
    cleanup = mountReviewShell(remount);
    expect(await loadPacketEntries(loadCanaryEntries())).toBeNull();
    expect((document.getElementById("stream-decision") as HTMLSelectElement).value).toBe(
      "accept",
    );
  });

  it("shows persistent divergence warning when reducer state mismatches oracle", async () => {
    const result = await loadPacketFromEntries(loadCanaryEntries());
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    // Corrupt every stream so rare-action-first queue still surfaces a mismatch.
    const packet = {
      ...result.packet,
      streams: result.packet.streams.map((s) => ({
        ...s,
        sidecar: {
          ...s.sidecar,
          decisions: s.sidecar.decisions.map((d, di) =>
            di === 0 ? { ...d, active_timer_ids: ["t_999"] } : d,
          ),
        },
      })),
    };

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(packet);

    const box = document.getElementById("divergence")!;
    expect(box.hidden).toBe(false);
    expect(box.getAttribute("role")).toBe("alert");
    expect(box.querySelector(".divergence-summary")!.textContent).toContain("Packet replay differs");
    expect(box.querySelector(".divergence-summary")!.textContent).not.toMatch(/active_timer_ids|[etr]_\d+/);
    expect(box.querySelector("details")!.hasAttribute("open")).toBe(false);
    expect(box.querySelector("details")!.textContent).toContain("active_timer_ids");
  });

  it("keeps Phase 2 origin evidence blind until a valid saved disposition, then restores it", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(phase2Packet(loaded.packet));
    expect(document.getElementById("progress")!.textContent).toContain("3 left");
    expect(document.querySelector(".rail-heading")!.textContent).toContain("Work through each interaction in order");

    document.querySelector<HTMLButtonElement>(".cluster-item")!.click();
    const preSave = [
      document.getElementById("phase2-compare")!.textContent ?? "",
      [...document.querySelectorAll<HTMLElement>("#viewport .vp-root > :not([hidden])")].map((node) => node.textContent ?? "").join("\n"),
      document.getElementById("inspect-oracle")!.textContent ?? "",
      document.getElementById("inspect-teacher")!.textContent ?? "",
    ]
      .join("\n");
    expect(preSave).not.toMatch(/oracle|teacher|request_sha256/i);
    expect(document.querySelector(".vp-action-row")?.hasAttribute("hidden")).toBe(true);
    expect(document.getElementById("cluster-context")!.hidden).toBe(false);
    expect(document.querySelectorAll(".cluster-evidence-cases li")).toHaveLength(3);
    const batch = document.getElementById("btn-save-cluster") as HTMLButtonElement;
    expect(batch.disabled).toBe(true);
    batch.click();
    expect(document.getElementById("cluster-status")!.textContent).not.toContain("saved");

    const acknowledgeCase = (index: number) => {
      const row = document.querySelectorAll<HTMLElement>(".cluster-evidence-cases li")[index];
      const checkbox = row.querySelector<HTMLInputElement>(".cluster-acknowledge")!;
      expect(checkbox.disabled).toBe(false);
      checkbox.click();
    };
    acknowledgeCase(0);
    expect(batch.disabled).toBe(true);
    document.querySelectorAll<HTMLButtonElement>(".cluster-open-evidence")[1].click();
    acknowledgeCase(1);
    expect(batch.disabled).toBe(true);
    document.querySelectorAll<HTMLButtonElement>(".cluster-open-evidence")[2].click();
    acknowledgeCase(2);
    expect((document.getElementById("btn-save-cluster") as HTMLButtonElement).disabled).toBe(false);
    expect(document.getElementById("cluster-status")!.textContent).toContain("Returned to the representative");

    document.querySelectorAll<HTMLButtonElement>(".cluster-open-evidence")[1].click();
    expect(document.querySelector(".cluster-evidence-cases li.current strong")!.textContent).toBe("confirmation 1");
    (document.getElementById("phase2-choice-A") as HTMLInputElement).checked = true;
    (document.getElementById("phase2-category") as HTMLSelectElement).value = "teacher_error";
    (document.getElementById("decision-note") as HTMLTextAreaElement).value = "Confirmation-local A must not be applied as representative A.";
    document.getElementById("btn-save-cluster")!.click();
    expect(document.getElementById("cluster-status")!.textContent).toContain("Batch not applied");
    expect(document.querySelector(".cluster-evidence-cases li.current strong")!.textContent).toBe("representative");
    expect(document.activeElement).toBe(document.getElementById("phase2-choice-A"));
    expect([...Array(window.localStorage.length).keys()]
      .map((index) => window.localStorage.getItem(window.localStorage.key(index)!) ?? "")
      .some((text) => text.includes("cluster_review"))).toBe(false);

    (document.getElementById("decision-decision") as HTMLSelectElement).value = "flag";
    (document.getElementById("phase2-choice-A") as HTMLInputElement).checked = true;
    (document.getElementById("phase2-category") as HTMLSelectElement).value = "teacher_error";
    (document.getElementById("decision-note") as HTMLTextAreaElement).value = "Candidate A preserves the evidence.";
    document.getElementById("btn-save-cluster")!.click();
    expect(document.getElementById("cluster-status")!.textContent).toContain("saved for its members");
    expect(document.getElementById("phase2-reveal")!.textContent).toContain("origins and provenance");
    expect(document.getElementById("phase2-compare")!.textContent).toContain("Origin:");
    const exportedDraft = [...Array(window.localStorage.length).keys()]
      .map((index) => window.localStorage.key(index)!)
      .filter((key) => !key.endsWith(":cluster-evidence"))
      .map((key) => window.localStorage.getItem(key) ?? "")
      .find((text) => text.includes("cluster_review"))!;
    const auditRecord = exportedDraft.trim().split("\n").map((line) => JSON.parse(line)).find((record) => record.cluster_review);
    expect(auditRecord.cluster_review.reviewed_evidence.map((item: { role: string }) => item.role)).toEqual([
      "representative", "confirmation_1", "confirmation_2",
    ]);

    cleanup();
    cleanup = null;
    document.body.innerHTML = "";
    const remount = document.createElement("div");
    document.body.appendChild(remount);
    cleanup = mountReviewShell(remount);
    adoptLoadedPacket(phase2Packet(loaded.packet));
    document.querySelector<HTMLButtonElement>(".cluster-item")!.click();
    expect(document.getElementById("phase2-compare")!.textContent).toContain("Origin:");
  });

  it("queues equivalent decisions when their Phase 2 route requires human review", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const packet = phase2Packet(loaded.packet);
    const equivalent = packet.phase2ReviewEvidence!.decisions.find(
      (decision) => decision.comparison === "equivalent",
    )!;
    equivalent.review_evidence.review_route.review_required = true;
    equivalent.review_evidence.review_route.mandatory = true;
    equivalent.review_evidence.review_route.reasons = ["mandatory_action"];

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(packet);

    expect(document.getElementById("progress")!.textContent).toContain("0 of 4 decisions reviewed · 4 left");
    expect(document.querySelectorAll(".stream-item")).toHaveLength(4);
    const verify = [...document.querySelectorAll<HTMLButtonElement>(".stream-item")].find(
      (button) => button.textContent?.includes("Verify "),
    );
    expect(verify).toBeTruthy();
    verify!.click();
    expect(document.getElementById("compare-title")!.textContent).toBe("Is this action correct?");
    expect(document.getElementById("oracle-panel")!.textContent).not.toContain("Oracle:");
    expect(document.getElementById("legacy-decision-fields")!.hidden).toBe(false);
    expect(document.getElementById("legacy-decision-fields")!.tagName).toBe("DIV");
    expect(document.getElementById("legacy-decision-fields")!.textContent).toContain("Correct");
    expect((document.getElementById("decision-reason") as HTMLInputElement).type).toBe("hidden");
    const beforeSave = document.getElementById("nav-meta")!.textContent;
    (document.getElementById("decision-decision") as HTMLSelectElement).value = "accept";
    (document.getElementById("decision-note") as HTMLTextAreaElement).value = "The action matches the visible request.";
    document.getElementById("btn-save-decision")!.click();
    expect(document.getElementById("nav-meta")!.textContent).not.toBe(beforeSave);
    expect(document.querySelectorAll(".stream-item.reviewed")).toHaveLength(1);
  });

  it("resolves the due reminder message in the real Wave-1 single-action panel", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    expect(await loadPacketEntries(loadTimerWave1Entries())).toBeNull();

    const reminders = [...document.querySelectorAll<HTMLButtonElement>(".stream-item")]
      .filter((button) => button.querySelector(".queue-title")?.textContent === "Verify send reminder");
    expect(reminders.length).toBeGreaterThanOrEqual(2);
    const target = reminders.find((button) => {
      button.click();
      const attention = document.querySelector(".vp-attention")?.textContent ?? "";
      return attention.includes("open the fern ledger for the desk note") && attention.includes("580 ms ago");
    });
    expect(target).toBeTruthy();

    expect(document.querySelector(".vp-attention")?.textContent).toContain("open the fern ledger for the desk note");
    expect(document.querySelector(".vp-attention")?.textContent).toContain("580 ms ago");
    expect(document.getElementById("oracle-panel")!.textContent).toBe(
      "Send reminder: Send the due reminder: “open the fern ledger for the desk note”.",
    );
    expect(document.getElementById("legacy-decision-fields")!.hidden).toBe(false);
  });

  it("filters and navigates Phase 2 work at decision scope", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const packet = phase2Packet(loaded.packet);
    for (const decision of packet.phase2ReviewEvidence!.decisions) {
      decision.review_evidence.review_route.review_required = true;
    }
    const expected = packet.phase2ReviewEvidence!.decisions.filter(
      (decision) => decision.oracle_action.type === "schedule",
    ).length;
    expect(expected).toBeGreaterThan(0);

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(packet);
    const actionFilter = document.getElementById("filter-action") as HTMLSelectElement;
    actionFilter.value = "schedule";
    actionFilter.dispatchEvent(new Event("change"));

    expect(document.querySelectorAll(".stream-item")).toHaveLength(expected);
    expect(document.getElementById("nav-meta")!.textContent).toContain(`of ${expected}`);
    for (const item of document.querySelectorAll(".stream-item")) {
      expect(item.textContent).toContain("create reminder");
    }
  });

  it("orders stream groups by their highest-priority pending decision and keeps each stream chronological", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const packet = phase2Packet(loaded.packet);
    const streams = [...new Set(packet.phase2ReviewEvidence!.decisions.map((decision) => decision.stream_sha256))];
    const first = packet.phase2ReviewEvidence!.decisions.find((decision) => decision.stream_sha256 === streams[0])!;
    const second = packet.phase2ReviewEvidence!.decisions.find((decision) => decision.stream_sha256 === streams[1])!;
    for (const decision of packet.phase2ReviewEvidence!.decisions) decision.review_evidence.review_route.review_required = false;
    first.review_evidence.review_route.review_required = true;
    second.review_evidence.review_route.review_required = true;
    first.priority_rank = 10;
    second.priority_rank = 0;
    second.comparison = "equivalent";
    second.candidates = [];
    second.cluster_signature = null;
    second.oracle_action = { type: "respond", reply_to_event_id: "e_1", text: "Priority interaction" };

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(packet);

    const buttons = [...document.querySelectorAll<HTMLButtonElement>(".stream-item")];
    expect(buttons).toHaveLength(2);
    expect(buttons[0].querySelector(".queue-title")!.textContent).toBe("Verify reply to user");
    expect(buttons[0].querySelector(".queue-meta")!.textContent).toBe("Needs review");
    expect(buttons[0].textContent).not.toContain("timer_creation_normal_fire");
  });

  it("rejects a stream at its first confirmed causal disagreement and removes its ordinary suffix", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const packet = phase2Packet(loaded.packet);
    const target = packet.phase2ReviewEvidence!.decisions.find((decision) => decision.comparison === "causal_disagreement")!;
    for (const decision of packet.phase2ReviewEvidence!.decisions) {
      decision.review_evidence.wave_id = "timer-wave-1";
      if (decision.stream_sha256 === target.stream_sha256) decision.review_evidence.review_route.review_required = true;
    }

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(packet);
    const active = document.querySelector<HTMLButtonElement>(".stream-item.active")!;
    expect(queueGroupFor(active).length).toBeGreaterThan(1);
    (document.getElementById("phase2-choice-A") as HTMLInputElement).checked = true;
    (document.getElementById("phase2-category") as HTMLSelectElement).value = "teacher_error";
    (document.getElementById("decision-note") as HTMLTextAreaElement).value = "The causal action is wrong.";
    document.getElementById("btn-save-decision")!.click();

    const reviewed = document.querySelector<HTMLButtonElement>(".stream-item.reviewed")!;
    expect(reviewed).toBeTruthy();
    expect(queueGroupFor(reviewed)).toHaveLength(1);
    reviewed.click();
    expect((document.getElementById("stream-decision") as HTMLSelectElement).value).toBe("reject");
  });

  it("honors an explicit interaction rejection by removing ordinary detailed-review rows", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const packet = phase2Packet(loaded.packet);
    const target = packet.phase2ReviewEvidence!.decisions.find((decision) => decision.comparison === "causal_disagreement")!;
    for (const decision of packet.phase2ReviewEvidence!.decisions) {
      decision.review_evidence.wave_id = "timer-wave-1";
      if (decision.stream_sha256 === target.stream_sha256) decision.review_evidence.review_route.review_required = true;
    }

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(packet);
    const active = document.querySelector<HTMLButtonElement>(".stream-item.active")!;
    expect(queueGroupFor(active).length).toBeGreaterThan(1);
    (document.getElementById("stream-decision") as HTMLSelectElement).value = "reject";
    document.getElementById("btn-save-stream")!.click();

    const remaining = [...document.querySelectorAll<HTMLButtonElement>(".stream-item")]
      .find((button) => button.classList.contains("active"));
    expect(remaining ? queueGroupFor(remaining).length : 0).toBeLessThan(2);
  });

  it("shows a visible validation error and preserves an existing comparison outcome on resave", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(phase2Packet(loaded.packet));

    document.getElementById("btn-save-decision")!.click();
    expect(document.getElementById("decision-error")!.hidden).toBe(false);
    expect(document.getElementById("decision-error")!.textContent).toContain("Choose Candidate A or Candidate B");
    expect(document.activeElement).toBe(document.getElementById("phase2-choice-A"));

    (document.getElementById("decision-decision") as HTMLSelectElement).value = "reject";
    (document.getElementById("phase2-choice-A") as HTMLInputElement).checked = true;
    (document.getElementById("phase2-category") as HTMLSelectElement).value = "teacher_error";
    (document.getElementById("decision-note") as HTMLTextAreaElement).value = "Initial review.";
    document.getElementById("btn-save-decision")!.click();
    document.querySelector<HTMLButtonElement>(".stream-item.reviewed")!.click();
    expect((document.getElementById("decision-decision") as HTMLSelectElement).value).toBe("reject");

    (document.getElementById("decision-note") as HTMLTextAreaElement).value = "Reviewed again.";
    document.getElementById("btn-save-decision")!.click();
    const draft = [...Array(window.localStorage.length).keys()]
      .map((index) => window.localStorage.getItem(window.localStorage.key(index)!) ?? "")
      .find((text) => text.includes("Reviewed again."))!;
    const record = draft.trim().split("\n").map((line) => JSON.parse(line)).find(
      (item) => item.note === "Reviewed again.",
    );
    expect(record.decision).toBe("reject");
  });

  it("never restores or reveals a paired decision from a replaced Phase 2 evidence hash", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(phase2Packet(loaded.packet, `sha256:${"1".repeat(64)}`));
    document.querySelector<HTMLButtonElement>(".cluster-item")!.click();
    (document.getElementById("decision-decision") as HTMLSelectElement).value = "flag";
    (document.getElementById("phase2-choice-A") as HTMLInputElement).checked = true;
    (document.getElementById("phase2-category") as HTMLSelectElement).value = "teacher_error";
    (document.getElementById("decision-note") as HTMLTextAreaElement).value = "Bound to the first evidence root.";
    document.getElementById("btn-save-decision")!.click();
    document.querySelector<HTMLButtonElement>(".stream-item.reviewed")!.click();
    expect(document.getElementById("phase2-compare")!.textContent).toContain("Origin:");

    cleanup();
    cleanup = null;
    document.body.innerHTML = "";
    const remount = document.createElement("div");
    document.body.appendChild(remount);
    cleanup = mountReviewShell(remount);
    adoptLoadedPacket(phase2Packet(loaded.packet, `sha256:${"2".repeat(64)}`));
    document.querySelector<HTMLButtonElement>(".cluster-item")!.click();
    expect(document.getElementById("phase2-compare")!.textContent).not.toContain("Origin:");
    expect((document.getElementById("phase2-choice-A") as HTMLInputElement).checked).toBe(false);
  });

  it("keeps equivalent Phase 2 decisions on the legacy save path", async () => {
    const loaded = await loadPacketFromEntries(loadCanaryEntries());
    expect(loaded.ok).toBe(true);
    if (!loaded.ok) return;
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(phase2LegacyPacket(loaded.packet));

    expect(document.getElementById("phase2-compare")!.hidden).toBe(true);
    expect(document.getElementById("phase2-fields")!.hidden).toBe(true);
    expect(document.getElementById("oracle-panel")!.hidden).toBe(false);
    (document.getElementById("decision-decision") as HTMLSelectElement).value = "accept";
    (document.getElementById("decision-note") as HTMLTextAreaElement).value = "legacy compatible";
    document.getElementById("btn-save-decision")!.click();

    document.querySelector<HTMLButtonElement>(".stream-item.reviewed")!.click();
    expect((document.getElementById("decision-decision") as HTMLSelectElement).value).toBe("accept");
    expect(document.getElementById("phase2-compare")!.hidden).toBe(true);
  });
});
