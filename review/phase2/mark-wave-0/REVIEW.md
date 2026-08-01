# What to review

Judge each interaction as the person using the product:

- A direct mark instruction only affects a matching occurrence that appears later.
- The date `17 October 2031` must remain exact in both the instruction and marked target.
- A direct stop or replacement follows a matching visible active control and should itself do
  nothing: no mark and no ambiguity.
- `Underli` is unfinished, so the product should wait for typing.
- A genuinely unresolved target should wait as ambiguous.
- Quoted or code-form mark wording is not a direct instruction and should be ignored.

Approve or reject the eight interactions. `template-expansion.json` records the required rendered
direct-replacement expansion of template `a_cf3fb85cbef8786d98724b33`.
