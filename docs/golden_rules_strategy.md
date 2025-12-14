# Golden rule usage strategy

The current pipeline chunks long golden rules before embedding so retrieval stays fast and affordable. When you need the model to consider the *entire* rule set instead of the top relevant chunks, use the lightest approach that keeps prompts within token limits:

1. **Single-embed small rules** – If a rule file is well under the model's context limit (including other prompt materials), embed and inject the whole text as one block instead of chunking. This avoids overlap and maintains full context.
2. **Pre-compress long rules** – Summarize or distill lengthy rulebooks into a shorter, non-lossy list of mandates, then embed that distilled version. This preserves holistic coverage with fewer tokens than the raw text.
3. **Hierarchical retrieval** – Keep the existing chunks for precision, but also embed a high-level summary paragraph. Retrieve both the summary (always) and the top-N detailed chunks so the model sees the full policy intent without an oversized prompt.
4. **Adjust `top_n` carefully** – If you must stay chunk-based, increase `top_n` only as far as your prompt budget allows. Raising it slightly can surface more of the rule set without sending every chunk.

These options let you balance completeness with latency and cost while reducing the risk of token overflow compared to sending every chunk on every request.
