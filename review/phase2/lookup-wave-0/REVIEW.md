# What to review

Use the review UI and judge each moment as the person using the product. You do not
need to read event IDs or raw JSON.

- When the user clearly asks for a fact, the product should start that lookup once.
- While a requested lookup is still running, unrelated writing should not start it again.
- A fresh result for a request the user still wants should be shown.
- If the user replaces one lookup with another, the old result should be ignored as replaced.
- If the user explicitly abandons a lookup, its later result should be ignored as stale.
- Every shown result should repeat the full subject, so it is understandable by itself.

Review all eight interactions. The five checkpoint interactions include earlier context because
the correctness of ignoring a result depends on what the user kept, replaced, or abandoned.
