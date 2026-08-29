# verification/post_fix.py
import re
import sys

# Ensure Windows UTF-8 stdout/stderr handles are safe (if run directly)
if sys.platform.startswith('win') and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Category success validation rules.
# Each category defines:
#   "fail_pattern": regex pattern indicating the network is broken (must NOT be present in AFTER output).
#   "success_pattern": regex pattern indicating the network is fixed (MUST be present in AFTER output).
#   "error_message": description when check fails.
VERIFICATION_RULES = {
    "vlan": {
        # Check A: Line protocol must no longer be down
        "fail_pattern": r"line protocol is down",
        # Check B: Line protocol must be up
        "success_pattern": r"line protocol is up",
        # Check C (VLAN-specific): An access port must now appear in show vlan brief
        # Matches things like 'Gi0/3' or 'Fa0/1' appearing in a vlan brief line
        "port_assigned_pattern": r"active\s+\S+",
        "error_message": "VLAN SVI line protocol remains down or configured access port not present in VLAN."
    },
    "interface": {
        "fail_pattern": r"administratively\s+down",
        "success_pattern": r"is\s+up,\s+line\s+protocol\s+is\s+up",
        "error_message": "Interface remains administratively down."
    },
    "routing": {
        "fail_pattern": r"Network not in table",
        "success_pattern": r"O\s+\d{1,3}(?:\.\d{1,3}){3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|via\s+\d{1,3}",
        "error_message": "Required routing path is absent from the table."
    },
    "gateway": {
        "fail_pattern": r"Request timeout|0% packet success|100% packet loss|unreachable",
        "success_pattern": r"100% packet success|0% packet loss|Success rate is 100 percent|Success rate is 80 percent",
        "error_message": "Ping to default gateway continues to fail."
    },
    "nat": {
        "fail_pattern": r"Translations:\s*0|Empty translations",
        "success_pattern": r"tcp\s+\d{1,3}(?:\.\d{1,3}){3}|udp\s+\d{1,3}(?:\.\d{1,3}){3}|icmp\s+\d{1,3}(?:\.\d{1,3}){3}",
        "error_message": "NAT translation table remains empty; no active mappings observed."
    },
    "dhcp": {
        "fail_pattern": r"IP Address.*:\s*0\.0\.0\.0",
        "success_pattern": r"IP Address.*:\s*(?!0\.0\.0\.0)\d{1,3}(?:\.\d{1,3}){3}|leased|binding",
        "error_message": "Client failed to acquire a valid IP address via DHCP."
    },
    "dns": {
        "fail_pattern": r"Unresolved|unknown host",
        "success_pattern": r"Translating|dns-server|8\.8\.8\.8|name server",
        "error_message": "DNS resolution is non-functional."
    },
    "acl": {
        "fail_pattern": r"deny|drop count|drop",
        "success_pattern": r"permit|Success rate is 100 percent",
        "error_message": "Traffic remains blocked by ACL filters."
    },
    "wireless": {
        "fail_pattern": r"DTLS connection down|disconnected",
        "success_pattern": r"DTLS connection Up|Associated|Up",
        "error_message": "DTLS CAPWAP tunnel or wireless association is down."
    }
}


def verify_fix(category: str, before_output: str, after_output: str) -> dict:
    """
    Verifies that a fix successfully resolved the fault for the given category.
    Enforces:
    1. The known failure condition is NO LONGER present in after_output.
    2. The expected success condition IS present in after_output.
    For VLAN category, also checks:
    3. An access port now appears in the 'show vlan brief' output (config change).
    If any check fails, returns verification failure.
    """
    cat_clean = category.lower().split("/")[0].strip()
    rule = VERIFICATION_RULES.get(cat_clean)
    
    if not rule:
        return {
            "passed_verification": False,
            "verification_status": "failed",
            "message": "Insufficient evidence to verify the fix."
        }
        
    fail_pat = rule["fail_pattern"]
    success_pat = rule["success_pattern"]
    err_msg = rule["error_message"]
    
    # Check A: The known failure condition must NO LONGER be present in the AFTER output
    if re.search(fail_pat, after_output, re.IGNORECASE):
        return {
            "passed_verification": False,
            "verification_status": "failed",
            "message": f"{err_msg} Failure signature still observed in state."
        }
        
    # Check B: The expected success condition MUST be present in the AFTER output
    if not re.search(success_pat, after_output, re.IGNORECASE):
        return {
            "passed_verification": False,
            "verification_status": "failed",
            "message": f"{err_msg} Expected success pattern not verified in state."
        }
    
    # Check C (VLAN-specific): Verify access port now appears in 'show vlan brief' output
    # This ensures 'line protocol is up' didn't just get text-replaced without a real config change
    if cat_clean == "vlan" and "port_assigned_pattern" in rule:
        port_pat = rule["port_assigned_pattern"]
        # Look for a vlan-brief line where an active VLAN now has at least one port
        port_found = False
        for line in after_output.splitlines():
            # A vlan brief entry looks like: 30   HR   active   Gi0/3
            if re.search(r'^\s*\d+\s+\S+\s+active\s+\S', line):
                port_found = True
                break
        if not port_found:
            return {
                "passed_verification": False,
                "verification_status": "failed",
                "message": f"{err_msg} Access port assignment not reflected in 'show vlan brief' output."
            }
        
    return {
        "passed_verification": True,
        "verification_status": "verified",
        "message": f"Successfully verified fix for {category.upper()}."
    }
