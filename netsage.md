# NetSage AI — Troubleshooting Assistant with Human Review

**Track:** Artificial Intelligence | **Domain:** Networking Labs | **Safety Rule:** Human Review Required

## 1. Overview

NetSage AI is a troubleshooting assistant for Cisco-style lab networks. Given a symptom, a topology
note, and real `show`-command output, it returns a structured diagnosis — the likely root cause, an
OSI layer, a confidence level, the next command to confirm the fault, and concrete fix steps. Every AI
diagnosis is checked by a human reviewer before it is treated as correct, and every case where the AI
was wrong is logged with an explanation. A separate, non-AI Python script also runs deterministic
checks against the same evidence, so obvious configuration mistakes can be caught without relying on
the model at all.

## 2. Problem Being Solved

Junior engineers often know individual Cisco commands but struggle to connect a symptom to its real
root cause — for example, a PC that gets an IP address but can't reach a server could be a VLAN,
routing, DHCP, DNS, ACL, or NAT problem. NetSage AI is designed to narrow that gap by pairing an AI
diagnosis with mandatory human oversight, so it speeds up troubleshooting without letting an
unverified AI answer become the final word.

## 3. Project Structure

| File | Purpose |
|---|---|
| `cases.csv` | 32 troubleshooting cases spanning VLAN, gateway, DHCP, DNS, routing, ACL, NAT, and wireless faults |
| `generate_cases.py` | Script used to assemble `cases.csv` |
| `diagnose_prompt.md` | The structured prompt given to the AI, including the required JSON schema and two worked few-shot examples |
| `rule_checker.py` | Deterministic (non-AI) Python checker for duplicate IPs, wrong masks, gateway mismatches, interfaces down, missing VLANs, and missing routes |
| `rule_checker_output.txt` | Sample output from running `rule_checker.py` against all 32 cases |
| `generate_ai_diagnoses.py` / `run_diagnosis.py` | Scripts that send each case through the diagnosis prompt and collect the AI's JSON response |
| `ai_diagnoses.csv` | The AI's diagnosis for every case, with a `match` column comparing it against the known expected fault |
| `generate_human_review.py` | Script used to build the human review log from `ai_diagnoses.csv` and `cases.csv` |
| `human_review_log.csv` | Human reviewer decision (Accepted / Edited / Rejected) for every case |
| `responsible_ai_log.md` | Detailed notes on the 7 cases where the AI's answer was corrected, including the pattern of failure in each |
| `dashboard.py` | Generates the summary charts and `dashboard_summary.csv` |
| `dashboard_summary.csv`, `chart_*.png` | The resulting dashboard: case distribution by category, severity, OSI layer, confidence, and AI/human agreement rate |

## 4. Workflow

1. **Collect cases** — 32 real troubleshooting scenarios were written up with symptom, topology note,
   `show`-command output, expected fault, OSI layer, concept tag, and severity.
2. **Design the prompt** — `diagnose_prompt.md` forces the AI to return JSON with `root_cause`,
   `confidence`, `evidence`, `next_command`, and `fix_steps`, and requires the AI to quote or directly
   reference the evidence it used rather than guessing.
3. **Run the deterministic rule checker** — `rule_checker.py` independently scans the same
   `show`-command output for six common, catchable mistakes, without using AI at all.
4. **Run the AI diagnosis** — every case is sent through the prompt and the response is saved and
   compared against the known correct answer.
5. **Human review** — every one of the 32 AI diagnoses is reviewed and marked Accepted, Edited, or
   Rejected, with reviewer notes explaining the decision.
6. **Responsible AI log** — the 7 cases that needed correction are documented individually, describing
   exactly what the AI got wrong (e.g. overstated confidence, an unsupported inference, an incomplete
   fix) and why the human correction is right.
7. **Dashboard** — case counts and outcomes are summarized in five charts plus a raw-numbers CSV.

## 5. Results Summary

- **Case coverage:** 32 cases across 8 fault categories — VLAN (5), DHCP (5), gateway (4), routing (4),
  ACL (4), wireless (4), DNS (3), NAT (3).
- **Severity spread:** 7 critical, 18 high, 7 medium.
- **OSI layer spread:** mostly Layer 3 (16) and Layer 2 (9), with some Layer 1, 4, and 7 cases included
  so the AI isn't only tested on routing-style problems.
- **Rule checker:** flagged 13 of 32 cases on deterministic grounds alone (12 missing-route triggers,
  4 wrong-mask, 2 interface-down, 2 missing-VLAN, 2 gateway-mismatch), confirming the checker catches
  real, evidence-based problems independent of the AI.
- **AI vs human agreement:** 25 of 32 AI diagnoses (78%) were **Accepted** as-is, 6 (18%) were
  **Edited**, and 1 (3%) was **Rejected** outright — 7 total corrections, documented in full in
  `responsible_ai_log.md`.
- **Common AI failure patterns:** overconfident labeling of inferred (not directly observed) evidence,
  one instance of introducing a detail not present in the actual show output, and a few cases of
  technically-correct-but-operationally-incomplete fix steps.

## 6. Responsible AI Approach

NetSage AI treats the AI's output as a *draft diagnosis*, never a final answer. Three safeguards
enforce this:

1. The prompt requires the AI to cite the specific evidence it used, making it easy for a human
   reviewer to check the AI's reasoning against the actual output rather than trusting a bare
   conclusion.
2. A fully deterministic, non-AI rule checker runs against the same evidence, giving an independent
   second opinion that doesn't depend on the model at all.
3. No diagnosis is used until a human has explicitly marked it Accepted, Edited, or Rejected — and
   every correction is logged with a specific explanation of the failure, not just a pass/fail mark.

## 7. Tools Used

- Python 3 (case generation, diagnosis pipeline, rule checker, dashboard/matplotlib charts)
- Claude (Anthropic) for generating diagnoses against the structured prompt
- Cisco Packet Tracer for the underlying lab topologies and `show`-command evidence
