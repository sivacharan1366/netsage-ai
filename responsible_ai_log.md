# Responsible AI Log — NetSage Network Troubleshooting Assistant
# Generated from human_review_log.csv
# Covers all cases marked "Edited" or "Rejected"

---

## Overview

This log documents cases where the AI diagnosis required human correction.
It records what the AI got wrong, what the correct answer was, and the
likely reason for the failure. This log is part of the project's
responsible AI accountability framework.

**Total cases reviewed:** 32  
**Accepted (no changes):** 25 (78%)  
**Edited (minor corrections):** 6 (19%)  
**Rejected (fundamentally wrong):** 1 (3%)

---

## Edited Cases

---

### CASE-005 — VLAN / VTP Transparent Mode (Edited)

**What the AI got wrong:**  
The AI correctly identified the root cause (vlan.dat deletion in VTP Transparent mode) and the immediate fix (restore from backup or manually recreate VLANs), but failed to mention a critical operational risk: if VLANs are re-added manually while the switch is connected to a VTP domain with a higher revision number, those VLANs can be overwritten again by a VTP advertisement.

**Correct answer:**  
The vlan.dat file was deleted before reload in VTP Transparent mode, erasing all locally stored VLANs. Recovery requires restoring from backup or manually re-creating each VLAN. Additionally, before reconnecting to the VTP domain, the engineer should verify the VTP revision number and consider keeping the switch in Transparent mode with local VLAN definitions backed up to startup-config.

**Why the AI failed:**  
The AI focused narrowly on the immediate symptom (VLANs missing) and the direct fix (recreate VLANs) without reasoning about downstream risks. This is a classic "last mile" failure where the AI gives a technically correct but operationally incomplete answer.

---

### CASE-007 — OSPF Reference Bandwidth / Path Selection (Edited)

**What the AI got wrong:**  
The AI said OSPF "may prefer the wrong path," which understates the certainty of the problem. When both FastEthernet (100 Mbps) and GigabitEthernet (1 Gbps) produce cost=1 with the default 100 Mbps reference bandwidth, OSPF treats them as equal-cost paths. OSPF will either load-balance across both or select based on router-ID, not bandwidth — the behavior is deterministic but wrong for the network intent.

**Correct answer:**  
With the default OSPF reference bandwidth of 100 Mbps, both FastEthernet and GigabitEthernet links calculate a cost of 1, making them equal-cost. OSPF cannot differentiate between a 100 Mbps and a 1 Gbps link. The `auto-cost reference-bandwidth 10000` fix must be applied to **every OSPF router** in the domain simultaneously, otherwise metric inconsistencies cause worse routing behavior than the original problem.

**Why the AI failed:**  
The AI used hedging language ("may prefer") when the evidence shows a definitive equal-cost situation. This overuse of uncertainty language when the output directly demonstrates the issue is a confidence calibration failure. The AI also did not emphasize the "apply to ALL routers" consistency requirement strongly enough.

---

### CASE-010 — DHCP Pool / Missing ip helper-address (Edited)

**What the AI got wrong:**  
The AI marked confidence as `high` but the root cause (missing `ip helper-address` on VLAN 20 SVI) is not directly visible in the provided show output. The diagnosis is inferred from the absence of POOL_B bindings in the DHCP binding table — the SVI config itself was never shown.

**Correct answer:**  
The ip helper-address for DHCP relay is missing on the VLAN 20 SVI. Without it, DHCP Discover packets from 10.20.0.0/24 clients arrive at R1 without a giaddr in the 10.20.0.0 range and are matched to POOL_A. Confidence should be `medium` because this is inferred from binding-table evidence, not directly observed in a `show running-config interface vlan 20` output.

**Why the AI failed:**  
The AI assigned `high` confidence to an inferred conclusion. The rule in the prompt template is: `high` confidence requires a "direct, unambiguous indicator" in the show output. Since the missing `ip helper-address` was not directly shown, `medium` is the correct confidence level. This is a prompt-rule-following failure.

---

### CASE-017 — DNS Failure via Serial Interface CRC Errors (Edited)

**What the AI got wrong:**  
The AI introduced "MTU mismatch" as a possible cause in its reasoning, but the show output for this case does not mention MTU mismatch anywhere — it only shows CRC errors (Input errors: 312, CRC: 189). Mentioning MTU without evidence in the provided output is a mild hallucination: the AI added a fact not supported by the input.

**Correct answer:**  
Serial0/1 has a physical or framing layer fault evidenced by 312 input errors and 189 CRC errors. DNS queries routed through Serial0/1 are corrupted or dropped as a result. The most likely cause is a CSU/DSU clocking mismatch, bad cable, or degraded line quality — NOT an MTU mismatch, which would show "giant" or "oversize" frame counters, not CRC errors.

**Why the AI failed:**  
The AI likely pattern-matched "DNS + serial link + partial failures" to MTU-related issues it was trained on, without strictly limiting itself to evidence in the provided output. This violates the explicit prompt rule: *"Never invent commands or output that wasn't provided."* CRC errors have a different failure signature than MTU errors, and the AI conflated them.

---

### CASE-021 — EIGRP Summarization / Null0 Blackhole (Edited)

**What the AI got wrong:**  
The AI correctly diagnosed the Null0 blackhole mechanism but framed the root cause as purely the manual summary configuration. It said "when R3's specific route was lost" without investigating or noting WHY R3's specific route was lost — which is a necessary part of a complete diagnosis.

**Correct answer:**  
The root cause is a combination of two conditions: (1) R2 has a manual EIGRP summary `172.16.0.0/16` which installs a Null0 route at AD 5, AND (2) R3's more-specific routes have disappeared (likely a link or redistribution failure on R3). Together these create the blackhole. A complete fix requires both removing or adjusting the summary AND restoring R3's specific routes.

**Why the AI failed:**  
The AI treated the summary configuration as the sole fault without asking what caused R3's specific routes to disappear. This is a partial-scope reasoning failure — the AI correctly diagnosed the proximate cause (Null0 route) but missed the upstream condition (R3 route loss) that made it trigger.

---

### CASE-028 — NAT Broken After IOS Upgrade (Edited)

**What the AI got wrong:**  
The AI's diagnosis (CEF disruption post-upgrade) is directionally correct but incomplete. It did not suggest checking whether `ip nat inside` and `ip nat outside` interface markings survived the IOS upgrade — a known issue where major IOS version jumps can reset interface-level features.

**Correct answer:**  
After the IOS upgrade from 15.4 to 16.9, NAT is processing zero packets as shown by zero ACL matches. The primary suspect is CEF being disabled or re-initialized. Additionally, `show ip interface GigabitEthernet0/0` and `show ip interface GigabitEthernet0/1` should be checked to verify that the `ip nat inside` and `ip nat outside` designations are still applied — these can be cleared by certain IOS upgrade procedures. Fix: verify CEF, check interface NAT designations, clear translation table, and retest.

**Why the AI failed:**  
The AI stopped at CEF as the sole hypothesis without reasoning through all the post-upgrade checks that would be needed for a complete troubleshooting methodology. This is a "diagnosis completeness" failure rather than an outright wrong answer.

---

## Rejected Cases

---

### CASE-027 — NAT Inside/Outside Reversed (Rejected)

**What the AI got wrong:**  
The AI gave a contradictory and uncommitted answer. It first said the config "shows Gi0/0 with LAN IP marked nat inside (CORRECT here)" — implying the config is right — but then immediately offered to "swap cables OR swap the nat inside/outside commands," treating both as equally valid options. This contradicts itself and fails to commit to a diagnosis. The AI's confidence of `medium` is also too high for an answer this internally inconsistent.

**Correct answer:**  
The logical config (ip nat inside on the LAN-facing port, ip nat outside on the WAN-facing port) is correct. The physical cables are swapped — the cable connecting to the LAN network is plugged into the WAN port (Gi0/1) and vice versa. This is a **Layer 1 physical cabling fault**. The correct fix is to swap the physical cables so that the LAN cable plugs into Gi0/0 (ip nat inside) and the WAN cable plugs into Gi0/1 (ip nat outside). No config changes needed.

**Why the AI failed:**  
The AI failed to commit to one explanation despite the case notes clearly stating "Physical cables connected in reverse order." The show output comments explicitly identified this as a physical issue. The AI saw the conflicting signals (correct logical config but cables swapped) and instead of choosing the one supported by the evidence, it offered both as options — this is a reasoning failure under ambiguity. The AI should have cited the topology note as definitive evidence for the Layer 1 fault and committed to a single diagnosis.

---

## Summary Table

| Case | Category | Decision | Failure Type |
|------|----------|----------|--------------|
| CASE-005 | VLAN | Edited | Incomplete fix / missing operational risk |
| CASE-007 | Gateway/OSPF | Edited | Confidence language too hedged; missing "all routers" caveat |
| CASE-010 | DHCP | Edited | Confidence overstatement (inferred evidence marked high) |
| CASE-017 | DNS | Edited | Mild hallucination (MTU not in evidence) |
| CASE-021 | Routing/EIGRP | Edited | Partial scope — missed upstream root cause |
| CASE-027 | NAT | Rejected | Contradictory diagnosis; failed to commit to Layer 1 fault |
| CASE-028 | NAT | Edited | Incomplete post-upgrade check list |

---

## Patterns Observed

1. **Confidence calibration errors** (CASE-010, CASE-007): The AI assigned `high` or `medium` confidence to conclusions inferred from indirect evidence, violating the prompt's confidence rubric.

2. **Hallucination of unsupported facts** (CASE-017): The AI introduced "MTU mismatch" as a possible cause when the show output only shows CRC errors. This violates the explicit "only use evidence from the provided output" rule.

3. **Incomplete fix steps** (CASE-005, CASE-028): The AI gave technically correct but operationally incomplete remediation — missing critical edge cases like VTP revision risks or post-upgrade interface verification.

4. **Ambiguity failure** (CASE-027): When the output contained contradictory signals (correct logical config + physical cable swap), the AI offered multiple conflicting options instead of committing to the one supported by the evidence (the topology note explicitly identifying it as a physical fault).

5. **Partial scope diagnosis** (CASE-021): The AI correctly identified the proximate mechanism (Null0 blackhole) but did not investigate or acknowledge the upstream condition that triggered it (loss of R3's specific routes).
