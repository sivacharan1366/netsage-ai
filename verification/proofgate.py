# verification/proofgate.py
import sys

# Ensure Windows UTF-8 stdout/stderr handles are safe (if run directly)
if sys.platform.startswith('win') and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Conflict checking rules comparing deterministic findings to AI diagnosis keywords.
# Keys are rule category tags.
# finding_substrings: trigger strings in deterministic output.
# required_keywords: words that MUST exist in the AI's root cause text.
# error_message: visual warning message displayed if validation fails.
CONFLICT_RULES = {
    "NATIVE_VLAN_MISMATCH": {
        "finding_substrings": ["native vlan mismatch", "vlan mismatch"],
        "required_keywords": ["vlan", "native", "trunk"],
        "error_message": "Deterministic checks found a Native VLAN mismatch, but AI diagnosis does not mention VLAN or trunk configurations."
    },
    "ADMIN_DOWN": {
        "finding_substrings": ["administratively down", "protocol is down"],
        "required_keywords": ["interface", "down", "protocol", "port", "shutdown", "svi"],
        "error_message": "Deterministic checks found a down interface/protocol, but AI diagnosis does not address interface/port state."
    },
    "OSPF_COST_MISMATCH": {
        "finding_substrings": ["ospf", "routing table lookup failed"],
        "required_keywords": ["route", "ospf", "cost", "metric", "routing", "timer", "hello"],
        "error_message": "Deterministic checks found OSPF/routing issues, but AI diagnosis does not mention routing configuration."
    },
    "GATEWAY_UNREACHABLE": {
        "finding_substrings": ["unreachable", "request timeout", "ping", "packet loss"],
        "required_keywords": ["ping", "route", "gateway", "dns", "reach", "unreachable", "connectivity"],
        "error_message": "Deterministic checks found connectivity drops or unreachable hosts, but AI diagnosis does not address reachability."
    },
    "ROGUE_DHCP": {
        "finding_substrings": ["rogue dhcp", "dhcp server signature"],
        "required_keywords": ["dhcp", "rogue", "pool", "server", "ipconfig"],
        "error_message": "Deterministic checks found a rogue DHCP server, but AI diagnosis does not mention DHCP."
    }
}


def check_conflicts(deterministic_findings: list[str], ai_root_cause: str) -> dict:
    """
    Compares local deterministic rule findings against the AI diagnosis root cause text.
    If a conflict is detected, returns conflict_detected = True with error messages.
    """
    conflict_detected = False
    conflict_messages = []
    
    ai_rc_lower = ai_root_cause.lower()
    
    for rule_name, rule_data in CONFLICT_RULES.items():
        finding_matched = False
        
        # Check if any deterministic finding contains any trigger substring
        for finding in deterministic_findings:
            for substring in rule_data["finding_substrings"]:
                if substring.lower() in finding.lower():
                    finding_matched = True
                    break
            if finding_matched:
                break
                
        # If triggered, AI must contain at least one required keyword
        if finding_matched:
            keyword_found = False
            for kw in rule_data["required_keywords"]:
                if kw.lower() in ai_rc_lower:
                    keyword_found = True
                    break
            if not keyword_found:
                conflict_detected = True
                conflict_messages.append(rule_data["error_message"])
                
    return {
        "conflict_detected": conflict_detected,
        "conflict_messages": conflict_messages
    }
