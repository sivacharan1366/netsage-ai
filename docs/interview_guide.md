# NetSage — Viva Interview Guide

This guide contains direct, clear answers to key questions examiners may ask during project evaluation.

---

### 1. What problem does NetSage solve?
* **Answer**: NetSage helps troubleshoot Cisco network problems by combining rule-based configuration checks with an LLM diagnosis. It cross-checks the AI's diagnosis against deterministic rules so mistakes are caught before fix commands are trusted.

### 2. Why did you build it?
* **Answer**: Manually checking long router and switch configs is slow, while asking a generic AI model directly can result in hallucinations or invented commands. NetSage acts as a guided tool that validates whether the diagnosis actually matches the provided show-command outputs.

### 3. Why use AI instead of only rules?
* **Answer**: Rule checks are great for catching explicit mistakes (like a shutdown interface or mismatched mask), but they struggle with open-ended symptoms across multiple devices. The LLM can synthesize symptoms, topology notes, and command logs into clear explanations, fix steps, and recommended next commands.

### 4. Why not let AI diagnose everything alone?
* **Answer**: LLMs can invent non-existent IP addresses or misread subtle configuration dependencies. Deterministic rules run instantly and give a reliable second opinion on factual network state (like whether an SVI is down or a route is missing).

### 5. What is Network DNA?
* **Answer**: Network DNA is an extraction function (`extract_network_dna`) that pulls out observed network entities from raw evidence: configured interfaces, IP addresses, subnets, default gateways, VLANs, static/OSPF routes, ACLs, and NAT roles. It gives structured context rather than raw unstructured text.

### 6. What is Evidence Radar?
* **Answer**: Evidence Radar checks if the required `show` commands for a troubleshooting category are present in the evidence. For example, a VLAN issue requires `show vlan brief` and trunk outputs. If critical commands are missing, it warns the user and suggests the next commands to run.

### 7. What is ProofGate?
* **Answer**: ProofGate is a validation step that compares deterministic rule findings with the AI diagnosis text. If a deterministic check found an issue (like `MISSING_VLAN`) but the AI's root cause never mentions VLANs or switchports, ProofGate flags a conflict and alerts the operator.

### 8. How do you prevent incorrect or hallucinated diagnoses?
* **Answer**: We use a multi-stage check:
  1. **Evidence Radar**: Flags if required evidence is missing.
  2. **Prompt schema**: Forces the AI to cite exact lines from the show output.
  3. **ProofGate**: Flags conflicts between rule findings and AI statements.
  4. **Human Review**: Requires an operator to approve or edit the diagnosis.
  5. **Post-Fix Verification**: Verifies that the fault is cleared in the after-fix state log.

### 9. How does Post-Fix Verification work?
* **Answer**: It compares the before-fix and after-fix output logs. It verifies two things: the failure pattern is gone, and the expected success condition (such as `line protocol is up` or active port assignment) is present in the after output.

### 10. Why is Human Review required?
* **Answer**: In a real network, applying the wrong fix can cause an outage. Having an operator explicitly review, accept, or edit the diagnosis ensures that no unreviewed AI output gets saved into the Memory Vault.

### 11. How does the Memory Vault work?
* **Answer**: The Memory Vault (`data/memory.json`) stores verified, historical troubleshooting cases. A case is only added to the vault if it was approved during human review and passed post-fix verification.

### 12. Why did you use JSON and CSV files instead of an external database?
* **Answer**: JSON and CSV files are human-readable, lightweight, and work without installing or configuring external database servers. This makes the project portable and easy to run and demonstrate.

### 13. How does similarity search work?
* **Answer**: We use Jaccard similarity (token overlap) on the words in the symptom and Network DNA. It calculates `intersection / union` of word tokens against verified cases in `data/memory.json` to show relevant historical cases as reference.

### 14. What happens if the Anthropic API is unavailable or offline?
* **Answer**: NetSage automatically falls back to Offline Mode, loading pre-computed diagnoses from `ai_diagnoses.csv`. This ensures the application and all workflow steps remain fully functional during a demo even without internet access.

### 15. What are the main limitations of the project?
* **Answer**: Currently, evidence is provided as text logs from Cisco Packet Tracer / CLI captures rather than live SSH/Telnet sessions, and post-fix verification checks simulated before-and-after logs.

### 16. What could be added in the future?
* **Answer**: Connecting directly to real network equipment or GNS3/EVE-NG over SSH (using Netmiko/Paramiko) to pull real-time logs and verify configuration changes live on devices.
