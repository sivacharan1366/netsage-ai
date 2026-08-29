"""
rule_checker.py
===============
NetSage Phase 2 — Deterministic Rule Checker

Reads cases.csv and runs six pattern-based checks against each row's
show_output field. Prints a human-readable report and saves it to
rule_checker_output.txt.

CHECKS IMPLEMENTED
  1. DUPLICATE_IP      — same IPv4 address appears on two or more interfaces / devices
  2. WRONG_MASK        — detects common wrong masks (/8 for a /24 network, /32 on a
                         non-loopback interface, etc.) or mask inconsistency across
                         interfaces in the same apparent subnet
  3. GATEWAY_MISMATCH  — a 'Default Gateway' or 'default-router' IP is not within
                         the subnet of the associated interface/host IP
  4. INTERFACE_DOWN    — any interface line matching "administratively down" or
                         "line protocol is down" (excluding expected SVI note)
  5. MISSING_VLAN      — a VLAN ID appears in a switchport/access config line but is
                         absent from the 'show vlan brief' table, OR vlan brief shows
                         a VLAN with no active ports when an SVI is also down
  6. MISSING_ROUTE     — "% Network not in table" or "% No route to host" present,
                         indicating a lookup failure

Each triggered check records:
  - The check name
  - Matched evidence (the specific line(s) from show_output)
  - A short explanation

Usage:
  python3 rule_checker.py                  # reads cases.csv in CWD
  python3 rule_checker.py --csv my.csv     # custom path
"""

import sys

import csv
import ipaddress
import re
import textwrap
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def wrap(text: str, width: int = 78, indent: int = 6) -> str:
    """Wrap a string for display."""
    return textwrap.fill(text, width=width, subsequent_indent=" " * indent)


def find_ip_mask_pairs(text: str):
    """
    Return list of (ip, mask) tuples from lines like:
      ip address 10.0.0.1 255.255.255.0
      network 192.168.1.0 255.255.255.0
      Default Gateway . . . : 192.168.1.1
    Also handles CIDR notation: 10.0.0.1/24
    Skips default-route entries (0.0.0.0 with any mask).
    """
    pairs = []
    # Dotted-decimal mask — skip the 0.0.0.0 default-route address
    for m in re.finditer(
        r'(?:ip address|network|default-router)\s+'
        r'(\d{1,3}(?:\.\d{1,3}){3})\s+'
        r'(\d{1,3}(?:\.\d{1,3}){3})',
        text, re.IGNORECASE
    ):
        ip, mask = m.group(1), m.group(2)
        if ip == "0.0.0.0":          # default route — not a misconfigured mask
            continue
        pairs.append((ip, mask))
    # CIDR on interface/topology line: 192.168.1.1/24
    for m in re.finditer(
        r'(\d{1,3}(?:\.\d{1,3}){3})/(\d{1,2})',
        text
    ):
        try:
            iface = ipaddress.ip_interface(f"{m.group(1)}/{m.group(2)}")
            if str(iface.ip) == "0.0.0.0":
                continue
            pairs.append((str(iface.ip), str(iface.netmask)))
        except ValueError:
            pass
    return pairs


def ip_in_subnet(ip_str: str, network_ip: str, mask_str: str) -> bool:
    """Return True if ip_str belongs to network_ip/mask_str."""
    try:
        net = ipaddress.IPv4Network(f"{network_ip}/{mask_str}", strict=False)
        return ipaddress.IPv4Address(ip_str) in net
    except ValueError:
        return True  # can't determine — don't false-positive


# ---------------------------------------------------------------------------
# CHECK 1 — DUPLICATE IP
# ---------------------------------------------------------------------------

def check_duplicate_ip(text: str):
    """
    Flag if the same IPv4 address appears as an 'ip address' on two or more
    distinct interfaces/devices, or appears twice in a DHCP binding table.
    """
    findings = []

    # Map: ip -> list of interface or context lines
    ip_contexts: dict[str, list[str]] = defaultdict(list)
    lines = text.splitlines()
    current_iface = None

    for line in lines:
        # Track interface context
        iface_match = re.match(r'^\s*interface\s+(\S+)', line, re.IGNORECASE)
        if iface_match:
            current_iface = iface_match.group(1)

        # ip address lines
        ip_match = re.search(
            r'ip address\s+(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE
        )
        if ip_match:
            ip = ip_match.group(1)
            ctx = current_iface or line.strip()
            ip_contexts[ip].append(ctx)

    for ip, contexts in ip_contexts.items():
        # Skip loopback and multicast
        try:
            addr = ipaddress.IPv4Address(ip)
            if addr.is_loopback or addr.is_multicast or addr.is_unspecified:
                continue
        except ValueError:
            continue
        if len(set(contexts)) >= 2:
            evidence = f"IP {ip} found on: {', '.join(set(contexts))}"
            findings.append({
                "check": "DUPLICATE_IP",
                "evidence": evidence,
                "explanation": (
                    f"The same IP address {ip} is configured on multiple "
                    f"interfaces or devices, which causes ARP conflicts and "
                    f"unpredictable routing."
                ),
            })

    return findings


# ---------------------------------------------------------------------------
# CHECK 2 — WRONG / SUSPICIOUS MASK
# ---------------------------------------------------------------------------

SUSPICIOUS_MASKS = {
    "255.0.0.0":     "A /8 mask on a non-10.x.x.x interface is likely misconfigured.",
    "255.255.0.0":   "A /16 mask may be too broad; verify addressing plan.",
    "255.255.255.255": "A /32 host mask on a non-loopback interface prevents broadcast and routing.",
    "0.0.0.0":       "A /0 mask effectively disables the interface subnet.",
}

def check_wrong_mask(text: str):
    """
    Flag /32 on non-loopback interfaces, /8 used where /24 is expected,
    or mask 0.0.0.0.
    Also flags mismatched masks for IPs that share the same first-three octets.
    Deduplicates findings by evidence string.
    """
    findings = []
    seen_evidence: set[str] = set()
    pairs = find_ip_mask_pairs(text)

    def add_finding(evidence: str, explanation: str) -> None:
        if evidence not in seen_evidence:
            seen_evidence.add(evidence)
            findings.append({
                "check": "WRONG_MASK",
                "evidence": evidence,
                "explanation": explanation,
            })

    # 1. Directly suspicious masks
    for ip, mask in pairs:
        if mask in SUSPICIOUS_MASKS:
            # /32 is normal for Loopback interfaces
            loopback_ctx = re.search(
                rf'(?:Loopback|lo)\d*.*?ip address\s+{re.escape(ip)}\s+{re.escape(mask)}',
                text, re.IGNORECASE | re.DOTALL
            )
            if mask == "255.255.255.255" and loopback_ctx:
                continue
            add_finding(f"ip address {ip} {mask}", SUSPICIOUS_MASKS[mask])

    # 2. Mask inconsistency: same /24 network, different masks
    subnet_masks: dict[str, list[tuple]] = defaultdict(list)
    for ip, mask in pairs:
        parts = ip.split(".")
        if len(parts) == 4:
            prefix3 = ".".join(parts[:3])
            subnet_masks[prefix3].append((ip, mask))

    for prefix3, entries in subnet_masks.items():
        masks_used = {e[1] for e in entries}
        if len(masks_used) > 1:
            detail = ", ".join(f"{ip}/{mask}" for ip, mask in dict.fromkeys((ip, mask) for ip, mask in entries))
            add_finding(
                f"Inconsistent masks in {prefix3}.0 network: {detail}",
                f"Multiple subnet masks found for what appears to be the same "
                f"{prefix3}.0 network. This causes routing and host-reachability issues.",
            )

    return findings


# ---------------------------------------------------------------------------
# CHECK 3 — GATEWAY MISMATCH
# ---------------------------------------------------------------------------

def check_gateway_mismatch(text: str):
    """
    Look for a 'Default Gateway' line and compare it against the host's own IP/mask.
    Also check DHCP 'default-router' against pool's 'network' statement.
    Handles both ipconfig /all colon format and Packet Tracer dot format.
    """
    findings = []

    # Pattern A: Windows ipconfig /all style  (colons or dots as separators)
    # e.g.  'Default Gateway . . . . . . . : 192.168.1.254'
    # or    'Default Gateway . . . . . . . : 192.168.1.254  (unreachable - no host)'
    gw_match = re.search(
        r'Default Gateway\s*[.:]+\s*(\d{1,3}(?:\.\d{1,3}){3})',
        text, re.IGNORECASE
    )
    ip_match = re.search(
        r'(?:IP Address|IPv4 Address)\s*[.:]+\s*(\d{1,3}(?:\.\d{1,3}){3})',
        text, re.IGNORECASE
    )
    mask_match = re.search(
        r'Subnet Mask\s*[.:]+\s*(\d{1,3}(?:\.\d{1,3}){3})',
        text, re.IGNORECASE
    )

    # If gateway is explicitly marked unreachable in the output, always flag it
    gw_unreachable = re.search(
        r'Default Gateway.*?(\d{1,3}(?:\.\d{1,3}){3}).*?unreachable',
        text, re.IGNORECASE
    )
    if gw_unreachable:
        gw = gw_unreachable.group(1)
        findings.append({
            "check": "GATEWAY_MISMATCH",
            "evidence": gw_unreachable.group(0).strip(),
            "explanation": (
                f"The default gateway {gw} is explicitly marked as unreachable in the output. "
                f"The host will fail to forward any off-subnet traffic."
            ),
        })
        return findings  # already found, no need for further sub-checks

    if gw_match and ip_match and mask_match:
        gw = gw_match.group(1)
        host_ip = ip_match.group(1)
        mask = mask_match.group(1)
        if not ip_in_subnet(gw, host_ip, mask):
            findings.append({
                "check": "GATEWAY_MISMATCH",
                "evidence": (
                    f"IP={host_ip}/{mask}, Default Gateway={gw}"
                ),
                "explanation": (
                    f"The default gateway {gw} is not within the subnet "
                    f"{host_ip}/{mask}. The host will ARP for the gateway "
                    f"and fail because it is unreachable on the local segment."
                ),
            })
    elif gw_match:
        # Gateway seen, but no host IP/mask present; check if it's defined anywhere
        gw = gw_match.group(1)
        gw_defined = bool(re.search(
            rf'ip address\s+{re.escape(gw)}', text, re.IGNORECASE
        ))
        if not gw_defined:
            findings.append({
                "check": "GATEWAY_MISMATCH",
                "evidence": f"Default Gateway {gw} does not appear as any configured ip address in the output.",
                "explanation": (
                    f"Gateway {gw} is configured on the host but is not defined "
                    f"anywhere in the provided output, suggesting it may be wrong "
                    f"or unreachable."
                ),
            })

    # Pattern B: DHCP pool default-router vs network
    pool_networks = re.findall(
        r'network\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3})',
        text, re.IGNORECASE
    )
    pool_routers = re.findall(
        r'default-router\s+(\d{1,3}(?:\.\d{1,3}){3})',
        text, re.IGNORECASE
    )

    if pool_networks and not pool_routers:
        for net_ip, net_mask in pool_networks:
            findings.append({
                "check": "GATEWAY_MISMATCH",
                "evidence": f"DHCP pool has 'network {net_ip} {net_mask}' but no 'default-router' statement.",
                "explanation": (
                    f"DHCP pool for {net_ip}/{net_mask} has no default-router option. "
                    f"Clients will receive an IP but no gateway, so off-subnet traffic will fail."
                ),
            })

    return findings


# ---------------------------------------------------------------------------
# CHECK 4 — INTERFACE DOWN
# ---------------------------------------------------------------------------

def check_interface_down(text: str):
    """
    Detect lines matching:
      - '<Interface> is administratively down, line protocol is down'
      - '<Interface> is up, line protocol is down'   (layer-1 up but L2 down)
    Captures the interface name for context.
    """
    findings = []
    patterns = [
        re.compile(
            r'(\S+)\s+is\s+administratively\s+down,\s+line\s+protocol\s+is\s+down',
            re.IGNORECASE
        ),
        re.compile(
            r'(\S+)\s+is\s+up,\s+line\s+protocol\s+is\s+down',
            re.IGNORECASE
        ),
    ]
    seen = set()
    for pat in patterns:
        for m in pat.finditer(text):
            iface = m.group(1)
            if iface not in seen:
                seen.add(iface)
                label = (
                    "administratively down"
                    if "administratively" in m.group(0).lower()
                    else "up but line protocol is down"
                )
                findings.append({
                    "check": "INTERFACE_DOWN",
                    "evidence": m.group(0).strip(),
                    "explanation": (
                        f"Interface {iface} is {label}. "
                        f"{'Use no shutdown to bring it up.' if 'administratively' in label else 'Check physical connectivity, encapsulation, or far-end status.'}"
                    ),
                })
    return findings


# ---------------------------------------------------------------------------
# CHECK 5 — MISSING VLAN
# ---------------------------------------------------------------------------

def check_missing_vlan(text: str):
    """
    Two sub-checks:
    a) A 'switchport access vlan <N>' or 'access vlan <N>' or 'VLAN <N> (Inactive)'
       references a VLAN ID that does not appear in the show vlan brief table.
    b) A VLAN appears in show vlan brief with no ports AND a related SVI
       has 'line protocol is down'.
    """
    findings = []

    # Parse show vlan brief table — VLANs that ARE in the database
    vlan_db: set[int] = set()
    in_table = False
    for line in text.splitlines():
        if re.match(r'\s*----\s+', line):
            in_table = True
            continue
        if in_table:
            m = re.match(r'\s*(\d+)\s+\S+', line)
            if m:
                vlan_db.add(int(m.group(1)))
            elif line.strip() == "":
                in_table = False

    # VLANs referenced in switchport config or "Access Mode VLAN: N (Inactive)"
    referenced_vlans: dict[int, str] = {}
    for pat, label in [
        (r'switchport access vlan\s+(\d+)', 'switchport access vlan'),
        (r'access vlan\s+(\d+)',            'access vlan'),
        (r'Access Mode VLAN:\s+(\d+)\s+\(Inactive\)', 'Access Mode VLAN (Inactive)'),
        (r'trunk allowed vlan.*?(\d{2,4})',  'trunk allowed vlan'),
    ]:
        for m in re.finditer(pat, text, re.IGNORECASE):
            vid = int(m.group(1))
            if vid not in (1, 1002, 1003, 1004, 1005):  # skip reserved
                referenced_vlans[vid] = label

    if vlan_db:
        for vid, source in referenced_vlans.items():
            if vid not in vlan_db:
                findings.append({
                    "check": "MISSING_VLAN",
                    "evidence": f"VLAN {vid} referenced via '{source}' but not found in 'show vlan brief' table.",
                    "explanation": (
                        f"VLAN {vid} is used in port configuration but is not in the VLAN "
                        f"database. The port will be inactive. Fix: create the VLAN with "
                        f"'vlan {vid}' in global config."
                    ),
                })

    # Sub-check b: VLAN in brief with no ports AND SVI line protocol down
    svi_down_vlans = set()
    for m in re.finditer(
        r'(Vlan\d+|vlan\d+)\s+is\s+up,\s+line\s+protocol\s+is\s+down',
        text, re.IGNORECASE
    ):
        vm = re.search(r'\d+', m.group(1))
        if vm:
            svi_down_vlans.add(int(vm.group(0)))

    for vid in svi_down_vlans:
        # Look for that VLAN in brief with empty ports column
        pattern = re.compile(
            rf'^\s*{vid}\s+\S+\s+active\s*$',   # active but no ports listed
            re.MULTILINE
        )
        if pattern.search(text):
            findings.append({
                "check": "MISSING_VLAN",
                "evidence": f"VLAN {vid} is 'active' in vlan brief with no ports, and 'Vlan{vid} is up, line protocol is down'.",
                "explanation": (
                    f"VLAN {vid} exists in the database but has no active access ports, "
                    f"so its SVI (Vlan{vid}) cannot bring line protocol up. "
                    f"Assign at least one active port to VLAN {vid}."
                ),
            })

    return findings


# ---------------------------------------------------------------------------
# CHECK 6 — MISSING ROUTE
# ---------------------------------------------------------------------------

ROUTE_FAILURE_PATTERNS = [
    re.compile(r'%\s*Network not in table',    re.IGNORECASE),
    re.compile(r'%\s*No route to host',        re.IGNORECASE),
    re.compile(r'%\s*Destination host unreachable', re.IGNORECASE),
    re.compile(r'Request timeout for icmp_seq',    re.IGNORECASE),
    re.compile(r'Temporary failure in name resolution', re.IGNORECASE),
    re.compile(r'TIMEOUT via \S+',             re.IGNORECASE),
    re.compile(r'no subnet defined for',       re.IGNORECASE),
    # Routing loop: traceroute shows same hops repeating
    re.compile(r'\(loop\)',                    re.IGNORECASE),
    # Comment in show output explicitly noting missing connected route
    re.compile(r'!\s*No connected route',      re.IGNORECASE),
    # Explicit unreachable note in ipconfig output
    re.compile(r'unreachable\s*[-–]\s*no host', re.IGNORECASE),
]

def check_missing_route(text: str):
    """
    Flag any line that explicitly states a routing / connectivity failure.
    """
    findings = []
    seen_evidence = set()
    for pat in ROUTE_FAILURE_PATTERNS:
        for m in pat.finditer(text):
            evidence = m.group(0).strip()
            if evidence not in seen_evidence:
                seen_evidence.add(evidence)
                findings.append({
                    "check": "MISSING_ROUTE",
                    "evidence": evidence,
                    "explanation": (
                        "An explicit routing or reachability failure was detected. "
                        "Check the routing table ('show ip route'), interface status, "
                        "and gateway/next-hop configuration."
                    ),
                })
    return findings


# ---------------------------------------------------------------------------
# RUNNER
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_duplicate_ip,
    check_wrong_mask,
    check_gateway_mismatch,
    check_interface_down,
    check_missing_vlan,
    check_missing_route,
]

CHECK_DESCRIPTIONS = {
    "DUPLICATE_IP":       "Same IP address on multiple interfaces/devices",
    "WRONG_MASK":         "Suspicious or inconsistent subnet mask",
    "GATEWAY_MISMATCH":   "Default gateway not in host's subnet / DHCP pool missing default-router",
    "INTERFACE_DOWN":     "Interface administratively or protocol down",
    "MISSING_VLAN":       "VLAN referenced in config but absent from VLAN database",
    "MISSING_ROUTE":      "Explicit routing or reachability failure message",
}


def run_all_checks(show_output: str) -> list[dict]:
    results = []
    for chk in ALL_CHECKS:
        results.extend(chk(show_output))
    return results


def format_case_report(row: dict, findings: list[dict], verbose: bool = True) -> str:
    lines = []
    sep = "─" * 78
    lines.append(sep)
    lines.append(
        f"  {row['case_id']}  [{row['category'].upper()}]  "
        f"severity={row['severity']}  layer={row['osi_layer']}"
    )
    lines.append(f"  Symptom : {wrap(row['symptom'], indent=12)}")
    lines.append("")

    if not findings:
        lines.append("  ✓  No deterministic checks triggered.")
    else:
        lines.append(f"  ⚠  {len(findings)} check(s) triggered:")
        for i, f in enumerate(findings, 1):
            lines.append(f"     [{i}] {f['check']}  —  {CHECK_DESCRIPTIONS.get(f['check'], '')}")
            lines.append(f"         Evidence   : {wrap(f['evidence'], indent=21)}")
            lines.append(f"         Explanation: {wrap(f['explanation'], indent=21)}")
    lines.append("")
    return "\n".join(lines)


def build_summary(all_results: list[tuple]) -> str:
    lines = ["", "=" * 78, "  SUMMARY", "=" * 78, ""]
    check_counts: dict[str, int] = defaultdict(int)
    cases_with_findings = 0
    for row, findings in all_results:
        if findings:
            cases_with_findings += 1
            for f in findings:
                check_counts[f["check"]] += 1

    lines.append(f"  Cases analysed     : {len(all_results)}")
    lines.append(f"  Cases with triggers: {cases_with_findings}")
    lines.append(f"  Cases clean        : {len(all_results) - cases_with_findings}")
    lines.append("")
    lines.append("  Triggers by check type:")
    for chk, count in sorted(check_counts.items(), key=lambda x: -x[1]):
        lines.append(f"    {chk:<22} {count:>3}  —  {CHECK_DESCRIPTIONS[chk]}")
    lines.append("")
    return "\n".join(lines)


def check_case(show_output: str) -> list[str]:
    """
    Wrapper function that runs all deterministic checks on a show output,
    and returns a list of string descriptions. These strings are formatted
    to contain trigger keywords that match ProofGate conflict rules.
    """
    findings = run_all_checks(show_output)
    mapped = []
    for f in findings:
        chk = f["check"]
        evidence = f["evidence"]
        explanation = f["explanation"]
        
        # Append specific trigger keywords to ensure ProofGate mapping works perfectly
        extra_keywords = ""
        if chk == "MISSING_VLAN":
            extra_keywords = " [vlan mismatch]"
        elif chk == "MISSING_ROUTE":
            extra_keywords = " [routing table lookup failed]"
        elif chk == "GATEWAY_MISMATCH":
            extra_keywords = " [unreachable / gateway mismatch]"
            
        mapped.append(f"{chk}: {explanation} (Evidence: {evidence}){extra_keywords}")
    return mapped


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    # Argument: optionally pass --csv <path>
    csv_path = Path("cases.csv")
    if "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        csv_path = Path(sys.argv[idx + 1])

    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found. Run generate_cases.py first.", file=sys.stderr)
        sys.exit(1)

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    all_results = []
    full_report_lines = [
        "=" * 78,
        "  NetSage Rule Checker — Deterministic Analysis Report",
        f"  Source: {csv_path}   Cases: {len(rows)}",
        "=" * 78,
        "",
    ]

    for row in rows:
        findings = run_all_checks(row["show_output"])
        all_results.append((row, findings))
        report_block = format_case_report(row, findings)
        print(report_block, end="")
        full_report_lines.append(report_block)

    summary = build_summary(all_results)
    print(summary)
    full_report_lines.append(summary)

    # Save to file
    output_path = Path("rule_checker_output.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_report_lines))
    print(f"  Report saved to: {output_path}")


if __name__ == "__main__":
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    main()

