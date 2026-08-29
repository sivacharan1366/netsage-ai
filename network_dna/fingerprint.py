# network_dna/fingerprint.py
import re
import sys
import ipaddress

# Ensure Windows UTF-8 stdout/stderr handles are safe (if run directly)
if sys.platform.startswith('win') and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def calculate_subnet(ip: str, mask_or_prefix: str) -> str:
    """Calculates exact network subnet address (e.g. 192.168.20.0/24) using Python standard library ipaddress."""
    try:
        if mask_or_prefix.startswith("/"):
            iface = ipaddress.ip_interface(f"{ip}{mask_or_prefix}")
        else:
            iface = ipaddress.ip_interface(f"{ip}/{mask_or_prefix}")
        return str(iface.network)
    except Exception:
        return f"{ip}/{mask_or_prefix}"


def extract_network_dna(show_output: str, symptom: str) -> dict:
    """
    Parses network evidence (symptom + show-command outputs) to build a structured
    Network DNA object (fingerprint). Represents only observations, not diagnoses.
    """
    dna = {
        "interfaces": [],
        "ip_addresses": [],
        "subnets": [],
        "gateways": [],
        "vlans": [],
        "trunks": [],
        "routes": [],
        "acls": [],
        "nat": [],
        "wireless": [],
        "suspicious_observations": []
    }

    # Combined text for overall search context
    full_text = symptom + "\n" + show_output
    lines = show_output.splitlines()

    # 1. Parse Interfaces
    # Matches 'interface GigabitEthernet0/1' or 'Vlan30 is up, line protocol is down'
    for line in lines:
        iface_match = re.match(r'^\s*interface\s+(\S+)', line, re.IGNORECASE)
        if iface_match:
            dna["interfaces"].append({
                "name": iface_match.group(1),
                "status": "config",
                "source": "running-config"
            })
        status_match = re.search(r'(\S+)\s+is\s+(up|down|administratively down),\s+line\s+protocol\s+is\s+(\S+)', line, re.IGNORECASE)
        if status_match:
            dna["interfaces"].append({
                "name": status_match.group(1),
                "status": f"Physical: {status_match.group(2)}, LineProtocol: {status_match.group(3)}",
                "source": "show interfaces"
            })

    # 2. Parse IP Addresses & Subnets
    # Matches 'ip address 192.168.1.1 255.255.255.0', CIDR '192.168.1.10/24', 'IP Address. . . : 192.168.1.10', or ping targets
    all_lines = full_text.splitlines()
    for line in all_lines:
        ip_addr_match = re.search(r'ip address\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE)
        if ip_addr_match:
            ip, mask = ip_addr_match.group(1), ip_addr_match.group(2)
            if ip != "0.0.0.0":
                subnet_net = calculate_subnet(ip, mask)
                dna["ip_addresses"].append({"ip": ip, "mask": mask, "source": "ip address config"})
                dna["subnets"].append({"network": subnet_net, "mask": mask, "source": "ip address config"})
        
        cidr_match = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})/(\d{1,2})', line)
        if cidr_match:
            ip, prefix = cidr_match.group(1), cidr_match.group(2)
            subnet_net = calculate_subnet(ip, f"/{prefix}")
            dna["ip_addresses"].append({"ip": ip, "mask": f"/{prefix}", "source": "network topology/note"})
            dna["subnets"].append({"network": subnet_net, "mask": f"/{prefix}", "source": "topology note"})

        ipconfig_match = re.search(r'(?:IP Address|IPv4 Address)[\s.]*[.:]+\s*(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE)
        if ipconfig_match:
            ip = ipconfig_match.group(1)
            dna["ip_addresses"].append({"ip": ip, "mask": "N/A", "source": "ipconfig"})

        mask_match = re.search(r'Subnet Mask[\s.]*[.:]+\s*(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE)
        if mask_match:
            dna["subnets"].append({"network": "host_subnet", "mask": mask_match.group(1), "source": "ipconfig"})

        ping_match = re.search(r'ping\s+(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE)
        if ping_match:
            target_ip = ping_match.group(1)
            dna["ip_addresses"].append({"ip": target_ip, "mask": "N/A", "source": "ping command observation"})

        # Generic IPv4 extraction for any IP addresses mentioned in evidence text
        ip_matches = re.findall(r'\b(?!0\.0\.0\.0)(?:1\d\d|2[0-4]\d|25[0-5]|[1-9]\d|[1-9])\.(?:\d{1,3})\.(?:\d{1,3})\.(?:\d{1,3})\b', line)
        for ip_found in ip_matches:
            # Filter out version strings or subnet masks
            if not ip_found.endswith(".0") and ip_found not in ["255.255.255.0", "255.255.0.0", "255.0.0.0"]:
                dna["ip_addresses"].append({"ip": ip_found, "mask": "N/A", "source": "evidence text observation"})

    # Deduplicate IP addresses & subnets by IP/network string
    seen_ips = set()
    unique_ips = []
    for item in dna["ip_addresses"]:
        if item["ip"] not in seen_ips:
            seen_ips.add(item["ip"])
            unique_ips.append(item)
    dna["ip_addresses"] = unique_ips

    seen_nets = set()
    unique_nets = []
    for item in dna["subnets"]:
        if item["network"] not in seen_nets:
            seen_nets.add(item["network"])
            unique_nets.append(item)
    dna["subnets"] = unique_nets

    # 3. Parse Gateways
    # Matches 'default-router 192.168.1.1' or 'Default Gateway . . . : 192.168.1.1' or 'standby 1 ip 10.10.10.1'
    for line in all_lines:
        gw_match = re.search(r'Default Gateway[\s.]*[.:]+\s*(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE)
        if gw_match:
            dna["gateways"].append({"gateway": gw_match.group(1), "type": "host_gateway", "source": "ipconfig"})
        
        dr_match = re.search(r'default-router\s+(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE)
        if dr_match:
            dna["gateways"].append({"gateway": dr_match.group(1), "type": "dhcp_pool_router", "source": "dhcp config"})
            
        standby_match = re.search(r'standby\s+\d+\s+ip\s+(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE)
        if standby_match:
            dna["gateways"].append({"gateway": standby_match.group(1), "type": "hsrp_virtual_ip", "source": "hsrp config"})

    # 4. Parse VLANs & Trunks
    # Reads VLANs in brief and allowed/native VLAN trunk configurations
    in_vlan_brief = False
    for line in lines:
        if "show vlan brief" in line.lower() or "vlan brief" in line.lower():
            in_vlan_brief = True
            continue
        if in_vlan_brief:
            if re.match(r'^\s*----', line):
                continue
            vlan_match = re.match(r'^\s*(\d+)\s+(\S+)\s+(\S+)', line)
            if vlan_match:
                dna["vlans"].append({
                    "id": vlan_match.group(1),
                    "name": vlan_match.group(2),
                    "status": vlan_match.group(3),
                    "source": "show vlan brief"
                })
            elif line.strip() == "" or "show" in line:
                in_vlan_brief = False
        
        # Trunk configurations
        trunk_mode = re.search(r'switchport mode trunk', line, re.IGNORECASE)
        if trunk_mode:
            dna["trunks"].append({"interface": "config_context", "mode": "trunk", "source": "running-config"})
            
        allowed_match = re.search(r'switchport trunk allowed vlan\s+(\S+)', line, re.IGNORECASE)
        if allowed_match:
            dna["trunks"].append({"allowed_vlans": allowed_match.group(1), "source": "running-config"})
            
        native_match = re.search(r'switchport trunk native vlan\s+(\d+)', line, re.IGNORECASE)
        if native_match:
            dna["vlans"].append({"native_vlan": native_match.group(1), "source": "running-config"})

    # 5. Parse Routes
    # Parses static and dynamic route configurations and route lookups
    for line in lines:
        static_route = re.search(r'ip route\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\S+)', line, re.IGNORECASE)
        if static_route:
            dna["routes"].append({
                "destination": static_route.group(1),
                "mask": static_route.group(2),
                "next_hop": static_route.group(3),
                "type": "static",
                "source": "running-config"
            })
            
        # OSPF/EIGRP routes in routing table
        ospf_route = re.match(r'^\s*O\s+(\d{1,3}(?:\.\d{1,3}){3}/\d+)\s+\[\d+/\d+\]\s+via\s+(\d{1,3}(?:\.\d{1,3}){3})', line, re.IGNORECASE)
        if ospf_route:
            dna["routes"].append({
                "destination": ospf_route.group(1),
                "next_hop": ospf_route.group(2),
                "type": "OSPF",
                "source": "show ip route"
            })

    # 6. Parse ACLs
    # Checks for access lists, matches, deny hit counts
    for line in lines:
        acl_match = re.match(r'^\s*(?:ip\s+)?access-list\s+(?:extended\s+|standard\s+)?(\S+)', line, re.IGNORECASE)
        if acl_match:
            dna["acls"].append({"name": acl_match.group(1), "source": "access-list definition"})
            
        ace_match = re.search(r'^\s*(\d+)\s+(permit|deny)\s+.*?\s*(\(\d+\s+matches\))?', line, re.IGNORECASE)
        if ace_match:
            hits = ace_match.group(3) or "0 matches"
            dna["acls"].append({
                "rule_number": ace_match.group(1),
                "action": ace_match.group(2),
                "hits": hits,
                "source": "show access-lists"
            })

    # 7. Parse NAT
    # Captures ip nat inside/outside and static NAT configurations
    for line in lines:
        nat_in = re.search(r'ip nat inside', line, re.IGNORECASE)
        if nat_in:
            dna["nat"].append({"role": "inside", "source": "interface configuration"})
        nat_out = re.search(r'ip nat outside', line, re.IGNORECASE)
        if nat_out:
            dna["nat"].append({"role": "outside", "source": "interface configuration"})
            
        static_nat = re.search(r'ip nat inside source static\s+(\S+)\s+(\S+)', line, re.IGNORECASE)
        if static_nat:
            dna["nat"].append({
                "inside_local": static_nat.group(1),
                "inside_global": static_nat.group(2),
                "type": "static_translation",
                "source": "running-config"
            })

    # 8. Parse Wireless
    # Captures WLC interfaces, WLANs, and CAPWAP/DTLS states
    for line in lines:
        wlan_match = re.search(r'WLAN\s+(\d+)\s+:\s+(\S+)\s+,\s+SSID:\s+(\S+)', line, re.IGNORECASE)
        if wlan_match:
            dna["wireless"].append({
                "id": wlan_match.group(1),
                "profile": wlan_match.group(2),
                "ssid": wlan_match.group(3),
                "source": "show wlan summary"
            })
            
        capwap_match = re.search(r'DTLS connection\s+(\S+)', line, re.IGNORECASE)
        if capwap_match:
            dna["wireless"].append({"dtls_status": capwap_match.group(1), "source": "AP logs"})

    # 9. Suspicious Observations
    # Flag warnings, errors, loops, shutdowns, and reachability drops
    suspicious_patterns = [
        (r'%CDP-4-NATIVE_VLAN_MISMATCH.*', "CDP Native VLAN mismatch warning"),
        (r'administratively\s+down', "Interface is administratively down"),
        (r'line\s+protocol\s+is\s+down', "Interface line protocol is down"),
        (r'%\s*Network not in table', "Routing table lookup failed (Network not in table)"),
        (r'Request timeout', "Ping packet loss (Request timeout)"),
        (r'\(loop\)', "Routing loop detected in traceroute"),
        (r'CRC\s+errors?\s*:\s*[1-9]\d*', "Interface CRC framing errors observed"),
        (r'input\s+errors?\s*:\s*[1-9]\d*', "Interface input errors observed"),
        (r'Access Mode VLAN:\s+\d+\s+\(Inactive\)', "Access port VLAN exists in config but inactive in database"),
        (r'rogue', "Rogue DHCP server signature identified"),
        (r'unreachable\s*[-–]\s*no host', "Host gateway is unreachable (no host)"),
    ]
    for pat, label in suspicious_patterns:
        for m in re.finditer(pat, full_text, re.IGNORECASE):
            dna["suspicious_observations"].append({
                "description": label,
                "evidence": m.group(0).strip(),
                "source": "Automated DNA scanner"
            })

    return dna


# =============================================================================
# SIMILARITY RETRIEVAL LAYER (JACCARD OVERLAP SIMILARITY)
# =============================================================================

def tokenize(text: str) -> set[str]:
    """Clean and split text into normalized unique keyword tokens."""
    if not text:
        return set()
    return set(re.findall(r'[a-zA-Z0-9_-]{3,}', text.lower()))


def calculate_jaccard_similarity(set1: set[str], set2: set[str]) -> float:
    """
    Calculates Jaccard similarity score: Intersection / Union.
    Returns a score between 0.0 and 1.0.
    """
    union_len = len(set1 | set2)
    if union_len == 0:
        return 0.0
    return len(set1 & set2) / union_len


def retrieve_similar_cases(query_text: str, historical_cases: list[dict], top_n: int = 3) -> list[dict]:
    """
    Compares the current query_text against the symptoms + evidence of all historical
    verified cases using Jaccard Similarity. Returns the top_n most similar cases.
    """
    query_tokens = tokenize(query_text)
    scored_cases = []
    
    for case in historical_cases:
        combined_text = (case.get("symptom", "") + "\n" + 
                         str(case.get("network_dna", "")) + "\n" + 
                         case.get("root_cause", ""))
        case_tokens = tokenize(combined_text)
        
        sim_score = calculate_jaccard_similarity(query_tokens, case_tokens)
        scored_cases.append({
            "case": case,
            "score": round(sim_score, 4)
        })
        
    # Sort descending by similarity score
    scored_cases.sort(key=lambda x: -x["score"])
    
    # Filter cases with zero overlap and slice top_n
    similar_list = [item for item in scored_cases if item["score"] > 0.0][:top_n]
    return similar_list
