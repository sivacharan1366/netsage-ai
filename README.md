# NetSage: AI-Assisted Network Troubleshooting

NetSage is a network troubleshooting tool designed for Cisco lab environments. It combines deterministic pattern-checking rules with LLM-based diagnosis (Claude) to analyze network faults from `show` command outputs, check if enough evidence is available, require human review before saving decisions, and verify that simulated fixes actually resolve the problem.

---

## 1. Problem

When troubleshooting network faults (such as VLAN misconfigurations, OSPF metric issues, missing DHCP default gateways, or interface drops), finding the exact root cause from switch or router outputs can take time. Relying purely on an AI model can also lead to hallucinations or missed configuration details.

NetSage addresses this by using a structured pipeline: checking for required evidence first, running deterministic checks, generating an AI diagnosis with explicit evidence citations, comparing the AI output against rule checks (ProofGate), requiring operator sign-off, and performing post-fix verification before storing the case in a local knowledge base.

---

## 2. Technology Stack

* **Language**: Python 3.10+
* **User Interface**: Streamlit
* **Plotting & Analytics**: Matplotlib
* **AI Model API**: Anthropic Claude API (with offline fallback mode)
* **Testing**: Pytest
* **Data Storage**: Local CSV and JSON files (`cases.csv`, `ai_diagnoses.csv`, `data/memory.json`)

---

## 3. Project Workflow

```
Case Selection & Evidence
       ↓
Evidence Radar (Checks if necessary commands are present)
       ↓
Network DNA Extraction & Similar Case Search (Jaccard similarity on Memory Vault)
       ↓
AI Diagnosis & ReasonChain (Root cause, evidence citations, next commands, fix steps)
       ↓
ProofGate (Cross-checks AI diagnosis with deterministic rule checks)
       ↓
Human Review (Operator marks: Accepted / Edited / Rejected)
       ↓
Post-Fix Verification (Verifies before vs. after state logs)
       ↓
Memory Vault (Saves approved, verified cases to local JSON storage)
```

---

## 4. Team Contributions

### Member 1: Network DNA & Similarity Retrieval
* **Network DNA**: Built the observation extractor in `network_dna/fingerprint.py` to parse interfaces, IP addresses, subnets, gateways, VLANs, routes, ACLs, and NAT roles.
* **Memory Vault**: Implemented local JSON storage in `verification/vault.py` and Jaccard token-overlap matching to find similar historical cases.

### Member 2: Evidence Radar & AI ReasonChain
* **Evidence Radar**: Implemented command sufficiency checks in `evidence_radar/radar.py` to verify whether critical `show` commands are present for a given category.
* **ReasonChain**: Designed prompt templates and structured JSON parsing in `ai/reasonchain.py` to break down root causes, supporting evidence, and alternative hypotheses.

### Member 3: Verification, Dashboard & Mentor Mode
* **ProofGate**: Created conflict detection in `verification/proofgate.py` to catch discrepancies between deterministic rule checks and AI root-cause text.
* **Post-Fix Verification**: Implemented before-and-after log verification in `verification/post_fix.py` to check that the fault signature is removed and the success condition is met.
* **Dashboard & Mentor Mode**: Built the Streamlit interface in `dashboard.py` and the 3-level progressive study tool in `ai/mentor.py`.

---

## 5. Setup & Running the Project

### A. Virtual Environment Setup
**Windows (PowerShell)**:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### B. Install Dependencies
```bash
pip install -r requirements.txt
```

### C. Run the Streamlit Dashboard
```bash
python -m streamlit run dashboard.py
```

### D. Run Automated Tests
```bash
python -m pytest tests/ -q
```

---

## 6. Example Walkthrough (CASE-001: VLAN SVI Down)

1. **Select Case**: Choose `CASE-001` (VLAN category).
2. **Evidence Radar**: Checks for `show vlan brief` and `show interfaces trunk`. If present, evidence is marked sufficient.
3. **Network DNA**: Extracts the interface status: `Vlan30 is up, line protocol is down`.
4. **Similar Incidents**: Searches `data/memory.json` for matching past cases based on symptom and DNA tokens.
5. **AI Diagnosis & ReasonChain**: Identifies that VLAN 30 has no active access ports assigned, citing the empty ports column in `show vlan brief`.
6. **ProofGate**: Runs deterministic checks from `rule_checker.py`, logs `MISSING_VLAN`, and confirms the AI text mentions VLAN/port state.
7. **Human Review**: The operator reviews the diagnosis and selects `Accepted`.
8. **Post-Fix Verification**: Checks the simulated post-fix state (`Vlan30 is up, line protocol is up` with port assignment) and marks the case verified.
9. **Memory Vault**: The approved, verified case can be saved into `data/memory.json`.

---

## 7. Limitations & Future Work

* **Current Limitation**: Post-fix verification evaluates simulated before-and-after command output logs rather than live router CLI sessions.
* **Future Work**: Connect directly to Cisco equipment or network emulators (e.g., via Netmiko / Scrapli) to fetch live CLI logs and test configuration changes dynamically.
