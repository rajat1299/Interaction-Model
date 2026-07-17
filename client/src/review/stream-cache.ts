/**
 * Index-once cache: reductions and fidelity results per stream.
 * Avoids reparsing / re-reducing on every navigation.
 */

import { checkStreamFidelity, reduceLoadedStream, type StreamFidelity } from "./reducer-fidelity";
import type { StreamReduction, VisibleState } from "./reducer";
import type { LoadedPacket, LoadedStream } from "./types";

export type IndexedStream = {
  stream: LoadedStream;
  reduction: StreamReduction;
  fidelity: StreamFidelity;
  /** policy_seq -> decision index */
  policySeqToDecision: Map<number, number>;
};

export type PacketIndex = {
  packet: LoadedPacket;
  bySha: Map<string, IndexedStream>;
  order: string[];
};

export function indexPacket(packet: LoadedPacket): PacketIndex {
  const bySha = new Map<string, IndexedStream>();
  const order: string[] = [];

  for (const stream of packet.streams) {
    const reduction = reduceLoadedStream(stream);
    const fidelity = checkStreamFidelity(stream, reduction);
    const policySeqToDecision = new Map<number, number>();
    for (let i = 0; i < stream.sidecar.decisions.length; i++) {
      policySeqToDecision.set(stream.sidecar.decisions[i].observed_policy_seq, i);
    }
    bySha.set(stream.sha256, { stream, reduction, fidelity, policySeqToDecision });
    order.push(stream.sha256);
  }

  return { packet, bySha, order };
}

export function stateAtEvent(indexed: IndexedStream, eventIndex: number): VisibleState {
  const states = indexed.reduction.states;
  if (eventIndex < 0 || eventIndex >= states.length) {
    throw new Error(`event index out of range: ${eventIndex}`);
  }
  return states[eventIndex];
}

export function eventIndexForPolicySeq(
  indexed: IndexedStream,
  policySeq: number,
): number {
  const states = indexed.reduction.states;
  for (let i = 0; i < states.length; i++) {
    if (states[i].eventSeq === policySeq) return i;
  }
  return -1;
}
