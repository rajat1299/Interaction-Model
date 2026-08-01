# Prompt template v4

V4 keeps the frozen behavior spec, schema, and prompt v1–v3 bytes unchanged. It resolves one
mark-lifecycle contract gap discovered during the Phase 2 mark canary:

- a visible ambiguous direct replacement suspends the standing mark control;
- it does not activate a replacement;
- a later complete direct mark control activates normally;
- removing the ambiguous replacement removes the suspension because v1 has no hidden mark state.

The owner explicitly selected this behavior on 2026-07-25. Mark generation opts into v4; completed
timer and lookup evidence remains on v3 and is semantically unaffected. No one-word contextual
completion rule or hidden suspension registry is introduced.

- v3: `sha256:31bea45fa5639c1eae8ad411779262d027bc705b499cf5eda3437a76a6d49ec9`
- v4: `sha256:e56e90b91a4ae43eeb39ed5181c037a4514c30a5edb00aa69a275e69ef225022`
