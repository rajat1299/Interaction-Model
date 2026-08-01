# Superseded before provider use

The raw context scan found current-count and near-future claims that were not covered by
the dated-fact filter. Those claims would become the premise of a generated follow-up even
though the source reply itself receives zero loss. The shared source-context filter now
rejects current-count and near-term prediction forms. No provider generation used this
ledger; `replay-ledger-v29` replaces it.
