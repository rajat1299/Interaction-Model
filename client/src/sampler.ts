/** Production sampler — Phase 1 typing simulator drives this module (WP10). */

export type SamplerFrame = {
  text: string;
  selection_start: number;
  selection_end: number;
  is_composing: boolean;
  input_type: string | null;
  client_ts: number;
};

export type SamplerEmit = (frame: SamplerFrame) => void;

/** Placeholder until WP10. */
export function attachSampler(_textarea: HTMLTextAreaElement, _emit: SamplerEmit): () => void {
  return () => {};
}
