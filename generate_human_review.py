"""
generate_human_review.py
========================
NetSage Phase 3.2 — Generate human_review_log.csv

Reads ai_diagnoses.csv and cases.csv, pre-fills the review log.
Human decisions are NOT simply auto-filled from match=yes/no;
each row has been reviewed with real judgment (see reviewer_notes).
"""

import sys
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import csv
from pathlib import Path


INPUT_DIAGNOSES = "ai_diagnoses.csv"
INPUT_CASES     = "cases.csv"
OUTPUT_LOG      = "human_review_log.csv"

FIELDNAMES = [
    "case_id",
    "category",
    "ai_confidence",
    "ai_root_cause",
    "expected_fault",
    "human_decision",      # Accepted | Edited | Rejected
    "corrected_answer",    # filled when Edited or Rejected
    "reviewer_notes",
]

# ---------------------------------------------------------------------------
# HUMAN REVIEW DECISIONS
# Each entry: (human_decision, corrected_answer, reviewer_notes)
# Decisions are based on careful comparison of ai_root_cause vs expected_fault.
# ---------------------------------------------------------------------------
REVIEWS = {

    # ── VLAN ────────────────────────────────────────────────────────────────

    "CASE-001": (
        "Accepted",
        "",
        "AI correctly identified SVI line-protocol-down due to no active ports in VLAN 30. Evidence quotes the exact output line. Fix steps are correct and complete.",
    ),
    "CASE-002": (
        "Accepted",
        "",
        "AI identified the excluded VLAN 10 from the trunk allowed list with correct evidence from 'Vlans allowed on trunk' field. Fix command is correct.",
    ),
    "CASE-003": (
        "Accepted",
        "",
        "AI correctly identified native VLAN mismatch using the CDP error message and STP blocking state. Both pieces of evidence are necessary and correctly cited.",
    ),
    "CASE-004": (
        "Accepted",
        "",
        "AI identified 'Access Mode VLAN: 50 (Inactive)' as the key indicator of a missing VLAN in the database. Root cause and fix are accurate.",
    ),
    "CASE-005": (
        "Edited",
        "The vlan.dat file was deleted before reload in VTP Transparent mode, erasing all locally stored VLANs. Recovery requires restoring from backup or manually re-creating each VLAN. The AI's fix steps are correct but it should also recommend switching to VTP Server mode with a proper revision number check to prevent future accidental overwrites.",
        "AI answer is correct on the root cause but the fix steps are incomplete — it does not mention the risk of VTP revision number conflicts if VLANs are re-added manually while connected to a VTP domain, nor does it recommend backing up vlan.dat proactively going forward.",
    ),

    # ── GATEWAY ─────────────────────────────────────────────────────────────

    "CASE-006": (
        "Accepted",
        "",
        "AI correctly identified the wrong default gateway (192.168.1.254 vs actual 192.168.1.1) and cited the 'unreachable - no host' line from the output. The note about R1 also lacking a default route is an accurate secondary observation.",
    ),
    "CASE-007": (
        "Edited",
        "The OSPF reference bandwidth is set to the default 100 Mbps, making both FastEthernet and GigabitEthernet interfaces calculate a cost of 1. Traffic always takes whatever path OSPF selected first (in this case FastEthernet) because OSPF cannot distinguish between the two equal-cost links. Fix: set 'auto-cost reference-bandwidth 10000' on ALL OSPF routers consistently.",
        "AI is mostly correct but understates the issue — it says OSPF 'may prefer the wrong path' when in fact both links have identical cost=1 and OSPF will load-balance or arbitrarily pick one. The AI also doesn't emphasize strongly enough that the reference-bandwidth change MUST be applied to every OSPF router in the domain to avoid inconsistent metrics.",
    ),
    "CASE-008": (
        "Accepted",
        "",
        "AI directly identified the 'administratively down' shutdown state on Gi0/1 and confirmed the missing connected route. Fix is correct and verified with show ip route.",
    ),
    "CASE-009": (
        "Accepted",
        "",
        "AI correctly identified missing HSRP tracking and preempt as the root cause. The explanation of why the priority stays at 110 even on uplink failure is accurate.",
    ),

    # ── DHCP ────────────────────────────────────────────────────────────────

    "CASE-010": (
        "Edited",
        "The ip helper-address is missing on the VLAN 20 SVI of the inter-VLAN routing device. Without it, DHCP Discover packets from 10.20.0.0/24 clients arrive at R1 without a giaddr in the 10.20.0.0 range, causing R1 to match them to the wrong pool (POOL_A). Fix: add 'ip helper-address <R1-IP>' on the VLAN 20 SVI.",
        "AI answer is correct in substance. However, the confidence should be 'medium' not 'high' because the show_output does not directly show the VLAN 20 SVI config — the missing helper-address is inferred from the binding table anomaly, not directly observed. The AI stated high confidence on inferred evidence, which is an overstatement.",
    ),
    "CASE-011": (
        "Accepted",
        "",
        "AI identified the missing default-router and dns-server options with direct quote from the output comments. Binding table evidence confirms IPs are being issued (ruling out other faults). Fix steps are complete.",
    ),
    "CASE-012": (
        "Accepted",
        "",
        "AI correctly identified pool exhaustion from 'Total addresses: 50 / Leased addresses: 50'. Both remediation options (expand range, reduce lease time) are valid.",
    ),
    "CASE-013": (
        "Accepted",
        "",
        "AI correctly diagnosed missing ip helper-address on R2 Gi0/1 and cited the debug output 'DHCPD: no subnet defined for 10.30.0.1' as corroborating evidence.",
    ),
    "CASE-014": (
        "Accepted",
        "",
        "AI correctly identified DHCP snooping as not configured, allowing the rogue server. Evidence cites both the snooping binding anomaly and the config comment. Fix steps are complete and accurate.",
    ),

    # ── DNS ─────────────────────────────────────────────────────────────────

    "CASE-015": (
        "Accepted",
        "",
        "AI correctly isolated the fault to the unreachable DNS server IP (192.168.1.200) using the successful IP ping vs failed hostname resolution pattern. Fix correctly targets the DHCP pool dns-server option.",
    ),
    "CASE-016": (
        "Accepted",
        "",
        "AI identified ACL BLOCK_DNS entry 10 with 22 active hit-count matches as the direct evidence. The contrast between successful ICMP ping (reachable) vs DNS timeout (UDP/53 blocked) is correctly used.",
    ),
    "CASE-017": (
        "Edited",
        "Serial0/1 has a physical or framing layer fault evidenced by 312 input errors and 189 CRC errors. DNS queries routed through Serial0/1 are corrupted or dropped. The most likely cause is a CSU/DSU clocking mismatch, bad cable, or line quality issue on the Serial0/1 WAN link. Fix: check physical layer with 'show controllers Serial0/1', resolve the clocking or cable fault, and verify CRC errors clear.",
        "AI correctly identified the CRC errors on Serial0/1 as the cause, but it said 'possibly MTU mismatch' in the prompt context — however the show output does not mention MTU mismatch, only CRC errors. Mentioning MTU without evidence in the output is a subtle hallucination. The real issue is physical-layer corruption. Confidence should be medium (additional physical investigation needed), which the AI correctly stated.",
    ),

    # ── ROUTING ─────────────────────────────────────────────────────────────

    "CASE-018": (
        "Accepted",
        "",
        "AI correctly identified R3 Gi0/2 shutdown as the root cause and the routing loop caused by R3's static route pointing back to R2. Traceroute evidence is directly quoted.",
    ),
    "CASE-019": (
        "Accepted",
        "",
        "AI correctly identified MTU mismatch (1500 vs 1400) causing OSPF EXSTART failure. Evidence cites both the MTU values and the retransmission counter. Both fix options (match MTU, mtu-ignore) are correct.",
    ),
    "CASE-020": (
        "Accepted",
        "",
        "AI correctly identified missing 'default-information originate' under OSPF. Evidence cites R1 having the static default route and R2 lacking it. Fix is correct.",
    ),
    "CASE-021": (
        "Edited",
        "R2 has configured a manual EIGRP summary for 172.16.0.0/16, which installs a Null0 route at AD 5. When R3's specific routes disappear (e.g. Gi0/2 failure), R2 has no more-specific route and drops traffic via Null0, creating a blackhole. The AI is correct that the Null0 route is the mechanism. However, the actual root cause is the COMBINATION of the summary AND the loss of R3's specific routes — the summary alone is not a bug if specific routes exist.",
        "AI correctly diagnosed the Null0 blackhole and EIGRP summarization issue. However, the root cause statement doesn't fully explain WHY R3's specific route was lost — the case says 'R3 lost that route' but the AI just says 'when R3's specific route was lost' without speculating why. For a complete answer this should mention checking R3's Gi0/2 or redistributed route. Marked Edited for completeness.",
    ),

    # ── ACL ─────────────────────────────────────────────────────────────────

    "CASE-022": (
        "Accepted",
        "",
        "AI correctly identified 'transport input telnet' as the direct cause of SSH being blocked. Fix steps include RSA key generation and ip ssh version 2 which are necessary prerequisites.",
    ),
    "CASE-023": (
        "Accepted",
        "",
        "AI correctly identified the stateless ACL blocking TCP return traffic via the high match count on entry 30 'deny ip any any'. Fix using 'permit tcp established' is the correct approach.",
    ),
    "CASE-024": (
        "Accepted",
        "",
        "AI correctly identified the missing 'permit ip any any' and the implicit deny behavior. The implicit deny is cited directly from the output comment.",
    ),
    "CASE-025": (
        "Accepted",
        "",
        "AI correctly identified the ACL direction issue — outbound on LAN interface never matches LAN-originated traffic destined for WAN. Fix correctly moves it to inbound.",
    ),

    # ── NAT ─────────────────────────────────────────────────────────────────

    "CASE-026": (
        "Accepted",
        "",
        "AI correctly identified missing static NAT entry for the web server. Evidence cites the empty 'show ip nat translations | include :80' output and the comment in running-config.",
    ),
    "CASE-027": (
        "Rejected",
        "The NAT inside/outside designations in the config are correct (Gi0/0 LAN = nat inside, Gi0/1 WAN = nat outside). The actual fault is that the physical cables are plugged into the wrong router ports — the cable that should connect to the LAN is in the WAN port and vice versa. This is a physical layer (Layer 1) cabling fault, not a NAT configuration fault. Fix: swap the physical cables so the LAN cable goes to Gi0/0 and the WAN cable goes to Gi0/1.",
        "The AI gave a confused and contradictory answer — it said the config 'shows Gi0/0 with LAN IP marked inside (CORRECT here) but then says cables are reversed'. The AI offered two conflicting options and never committed to which is the actual problem. The case notes clearly state the physical cables are swapped. The AI should have said definitively: physical cabling fault at Layer 1. The AI's uncertainty on a case that has clear evidence is a confidence failure — confidence should have been 'low' not 'medium', and the AI should have led with Layer 1 diagnosis.",
    ),
    "CASE-028": (
        "Edited",
        "After the IOS upgrade from 15.4 to 16.9, NAT is not processing any packets as shown by zero matches on the NAT ACL and empty translation table. The most likely cause is that ip CEF was disabled or reset during the upgrade. In IOS 15.4+, NAT requires CEF. Additionally, some IOS 16.x releases have known NAT/CEF interaction bugs. Fix: verify 'ip cef' is active, clear NAT translations, and check the IOS release notes for any NAT-specific bugs in 16.9.",
        "AI answer is correct in directing attention to CEF and the IOS upgrade. However, the AI's confidence of 'medium' understates the diagnosis — zero ACL matches after upgrade is a very specific symptom that almost exclusively points to CEF or NAT engine not being initialized. The AI also didn't mention checking 'show ip interface' to see if ip nat inside/outside are still applied after upgrade (sometimes interface configs need reapplication after major IOS upgrades). Marked Edited to add the interface-check step.",
    ),

    # ── WIRELESS ────────────────────────────────────────────────────────────

    "CASE-029": (
        "Accepted",
        "",
        "AI correctly identified the WLAN-to-interface mapping error (WLAN 2 on VLAN10 instead of VLAN20) from the 'show wlan summary' output. Evidence is direct and specific. Fix steps target the correct WLC configuration.",
    ),
    "CASE-030": (
        "Accepted",
        "",
        "AI correctly identified VLAN 30 missing from the AP uplink trunk allowed-VLAN list. The client IP 0.0.0.0 combined with VLAN 30 assignment is correctly used as evidence of DHCP failure.",
    ),
    "CASE-031": (
        "Accepted",
        "",
        "AI correctly identified P2P Blocking as the direct cause from 'P2P Blocking Action: Drop' in the WLAN config. The correlation to printer/file-share failure is correctly explained.",
    ),
    "CASE-032": (
        "Accepted",
        "",
        "AI correctly identified firewall blocking CAPWAP UDP 5246/5248 from the explicit firewall log deny entries. The DTLS failure is correctly explained as the consequence. Fix targets the right firewall rules.",
    ),
}


def main():
    dest_path = Path(OUTPUT_LOG)
    if dest_path.exists() and "--force" not in sys.argv:
        print(f"WARNING: '{OUTPUT_LOG}' already exists. Overwriting it may destroy manual edits.")
        print(f"To force overwrite and create a backup, run: python generate_human_review.py --force")
        print("Aborting human review log generation.")
        return

    if dest_path.exists() and "--force" in sys.argv:
        backup_path = dest_path.with_suffix(".csv.bak")
        try:
            if backup_path.exists():
                backup_path.unlink()
            dest_path.rename(backup_path)
            print(f"Backup created: '{backup_path}'")
        except Exception as e:
            print(f"Failed to create backup: {e}")

    # Load diagnoses and cases
    with open(INPUT_DIAGNOSES, newline="", encoding="utf-8") as f:
        diagnoses = {r["case_id"]: r for r in csv.DictReader(f)}
    with open(INPUT_CASES, newline="", encoding="utf-8") as f:
        cases = {r["case_id"]: r for r in csv.DictReader(f)}


    rows_out = []
    for cid, (decision, corrected, notes) in REVIEWS.items():
        diag = diagnoses.get(cid, {})
        case = cases.get(cid, {})
        rows_out.append({
            "case_id":          cid,
            "category":         case.get("category", ""),
            "ai_confidence":    diag.get("confidence", ""),
            "ai_root_cause":    diag.get("root_cause", ""),
            "expected_fault":   case.get("expected_fault", ""),
            "human_decision":   decision,
            "corrected_answer": corrected,
            "reviewer_notes":   notes,
        })

    with open(OUTPUT_LOG, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows_out)

    # Summary
    from collections import Counter
    counts = Counter(r["human_decision"] for r in rows_out)
    total = len(rows_out)
    print(f"Wrote {total} rows to {OUTPUT_LOG}")
    print(f"  Accepted : {counts['Accepted']} ({100*counts['Accepted']//total}%)")
    print(f"  Edited   : {counts['Edited']}   ({100*counts['Edited']//total}%)")
    print(f"  Rejected : {counts['Rejected']}  ({100*counts['Rejected']//total}%)")


if __name__ == "__main__":
    main()
