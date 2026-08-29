# Interview Guide — Memory Vault & Similar Case Retrieval

This guide prepares the team for questions about the Memory Vault and similar-case retrieval.

---

## Short Summary

> "Memory Vault is a JSON file of verified network troubleshooting cases. NetSage only stores a case after human approval and successful post-fix verification. When troubleshooting a new case, we compare it with verified historical cases and show similar cases as supporting context."

---

## Frequently Asked Interview Questions

### 1. Why did you choose JSON for storage?
* **Answer**: JSON is human-readable, lightweight, and supported directly by Python's standard library. Since this is an offline demonstration with a compact dataset, a simple JSON file (`data/memory.json`) keeps file access fast, transparent, and easy to inspect.

### 2. Why not use PostgreSQL or a specialized vector database?
* **Answer**: Adding external database engines or heavy vector libraries (such as Chroma or FAISS) would introduce extra setup steps and dependencies. Jaccard similarity operates directly on Python sets using the standard library, keeping the logic fast, reliable, and completely self-contained.

### 3. Why do we need similarity search?
* **Answer**: When troubleshooting a network fault, seeing how similar symptoms were resolved in the past gives helpful clues. It serves as historical context to speed up investigation without replacing actual verification.

### 4. Why are only verified cases stored in the vault?
* **Answer**: To ensure the knowledge base contains only confirmed solutions. If unverified AI guesses were stored, incorrect or hallucinated fixes would accumulate and mislead future investigations.

### 5. Why not trust the AI diagnosis automatically?
* **Answer**: LLMs can misread subtle command outputs or make assumptions about topology details that are not present. A case is only saved into the vault once an operator reviews it and a post-fix test verifies that the network issue is resolved.

### 6. How does the similarity search work?
* **Answer**: We use Jaccard similarity (token overlap):
  1. We split the input symptom and Network DNA into words and store them in a Python set.
  2. For each historical case in the vault, we create a similar word set from its symptom and root cause.
  3. We compute the overlap: `score = len(set_a & set_b) / len(set_a | set_b)`.
  4. We rank matching cases by score and display any with a non-zero overlap.

### 7. What is the main limitation of this similarity search?
* **Answer**: Similar symptoms do not always mean the same root cause. For example, "PC cannot reach default gateway" could be an SVI shutdown, a trunk mismatch, or a wrong host IP. Historical matches are shown strictly as reference context, not automatic diagnoses.
