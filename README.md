# Small Models for Live Text Interaction

Training a compact language model to track what you're typing, fetch information when it matters, and otherwise stay out of the way.

I fine-tuned Qwen3.6-35B-A3B into a text interaction model. It reads your typing as a stream of timestamped events and, at each moment, picks a single action: do nothing, highlight a phrase, request a lookup, fold in a previously fetched result, drop information that's no longer relevant, or reply. Most of the time, it does nothing.

The project grew out of a concrete question raised by Thinking Machines' work on interaction models: what would that idea become in plain text — a setting where the model watches unfinished drafts but should intervene only rarely?

The finished model can highlight relevant phrases, kick off a lookup mid-sentence, hold onto the result, and apply it later if it still fits. It can also throw away information once the user has moved on. Getting these behaviors to work took surprisingly little training; the harder challenge was curbing the model's urge to share accurate information nobody asked for.
