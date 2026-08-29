# evidence_radar/radar.py
import sys

# Ensure Windows UTF-8 stdout/stderr handles are safe (if run directly)
if sys.platform.startswith('win') and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Required evidence mapping.
# Each inner list represents ONE required evidence item. 
# The first element is the canonical command, followed by accepted variations/aliases.
REQUIRED_COMMANDS = {
    "vlan": [
        ["show vlan", "show vlan brief"],
        ["show interfaces trunk", "show interface trunk"]
    ],
    "routing": [
        ["show ip route"]
    ],
    "dhcp": [
        ["show running-config", "show run"],
        ["show ip dhcp binding", "show ip dhcp pool", "dhcp binding"]
    ],
    "dns": [
        ["show running-config", "show run", "ip dhcp pool"],
        ["ping", "ipconfig"]
    ],
    "acl": [
        ["show access-lists", "show ip access-list", "access-list", "access-group"],
        ["show running-config", "show run"]
    ],
    "nat": [
        ["show ip nat translations", "ip nat translations"],
        ["show running-config", "show run"]
    ],
    "gateway": [
        ["show ip route", "ip route"],
        ["show ip interface brief", "show interface", "ipconfig"]
    ],
    "wireless": [
        ["show wlan summary", "show wlan"],
        ["show running-config", "show run"]
    ],
    "interface": [
        ["show ip interface brief", "show interface"]
    ]
}


import re


def normalize_text(text: str) -> str:
    """Strips CLI prompt prefixes (e.g. SW1#, R1>) and collapses extra whitespace for robust command matching."""
    cleaned = re.sub(r'^[a-zA-Z0-9_-]+[#>]\s*', '', text, flags=re.MULTILINE)
    return re.sub(r'\s+', ' ', cleaned.lower())


def check_evidence_sufficiency(category: str, show_output: str) -> dict:
    """
    Scans raw output context for the critical required command list corresponding
    to the given troubleshooting category. Computes availability scores.
    """
    # Normalize category string (e.g. Gateway/IP -> gateway)
    cat_clean = category.lower().split("/")[0].strip()
    
    checklist = REQUIRED_COMMANDS.get(cat_clean)
    if not checklist:
        # Default fallback checks
        checklist = [
            ["show ip interface brief", "show interface", "ipconfig"]
        ]
        
    available = []
    missing_critical = []
    recommended_commands = []
    
    norm_output = normalize_text(show_output)
    
    for variations in checklist:
        canonical = variations[0]  # The first element is the display name / recommended command
        found = False
        for variation in variations:
            norm_var = re.sub(r'\s+', ' ', variation.lower())
            if norm_var in norm_output:
                found = True
                break
        if found:
            available.append(canonical)
        else:
            missing_critical.append(canonical)
            recommended_commands.append(canonical)
            
    total = len(checklist)
    score = len(available) / total if total > 0 else 1.0
    can_diagnose = len(missing_critical) == 0
    
    return {
        "evidence_sufficiency": "sufficient" if can_diagnose else "partial",
        "available": available,
        "missing_critical": missing_critical,
        "recommended_next_commands": recommended_commands,
        "can_diagnose": can_diagnose,
        "score": round(score, 2)
    }


check_evidence_radar = check_evidence_sufficiency
