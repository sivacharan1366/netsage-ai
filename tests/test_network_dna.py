# tests/test_network_dna.py
import json
import pytest
from network_dna.fingerprint import (
    extract_network_dna,
    tokenize,
    calculate_jaccard_similarity,
    retrieve_similar_cases,
)


# =============================================================================
# 1. NETWORK DNA PARSING TESTS
# =============================================================================

def test_extract_network_dna_structure():
    symptom = "PC cannot reach server."
    show_output = """
    SW1# show vlan brief
    VLAN Name                             Status    Ports
    ---- -------------------------------- --------- -------------------------------
    1    default                          active    Gi0/1
    30   HR                               active
    """
    dna = extract_network_dna(show_output, symptom)
    
    # Assert all keys are present
    expected_keys = {
        "interfaces", "ip_addresses", "subnets", "gateways", 
        "vlans", "trunks", "routes", "acls", "nat", "wireless", 
        "suspicious_observations"
    }
    assert set(dna.keys()) == expected_keys
    
    # Assert parsed VLANs are correct
    assert len(dna["vlans"]) == 2
    assert dna["vlans"][0]["id"] == "1"
    assert dna["vlans"][1]["id"] == "30"


def test_extract_network_dna_content():
    symptom = "Default Gateway unreachable."
    show_output = """
    interface GigabitEthernet0/1
     ip address 192.168.1.1 255.255.255.0
     ip nat inside
    ip route 10.0.0.0 255.0.0.0 192.168.1.254
    Default Gateway . . . . . . . : 192.168.1.254  (unreachable - no host)
    """
    dna = extract_network_dna(show_output, symptom)
    
    # Check IP
    assert len(dna["ip_addresses"]) >= 1
    assert dna["ip_addresses"][0]["ip"] == "192.168.1.1"
    
    # Check NAT role
    assert len(dna["nat"]) == 1
    assert dna["nat"][0]["role"] == "inside"
    
    # Check Routes
    assert len(dna["routes"]) == 1
    assert dna["routes"][0]["destination"] == "10.0.0.0"
    
    # Check Gateways
    assert len(dna["gateways"]) == 1
    assert dna["gateways"][0]["gateway"] == "192.168.1.254"
    
    # Check Suspicious Observations (e.g. unreachable gateway)
    assert len(dna["suspicious_observations"]) > 0
    assert "Default Gateway unreachable" in dna["suspicious_observations"][0]["description"] or \
           "unreachable" in dna["suspicious_observations"][0]["evidence"]


# =============================================================================
# 2. SIMILARITY RETRIEVAL TESTS
# =============================================================================

def test_tokenize():
    text = "FastEthernet0/0 is up, line protocol is down."
    tokens = tokenize(text)
    assert isinstance(tokens, set)
    assert "fastethernet0" in tokens
    assert "protocol" in tokens
    assert len(tokens) > 3


def test_jaccard_similarity():
    # Exact match sets
    set1 = {"vlan", "trunk"}
    set2 = {"vlan", "trunk"}
    score = calculate_jaccard_similarity(set1, set2)
    assert score == 1.0
    
    # Partial match sets
    set3 = {"vlan"}
    set4 = {"vlan", "routing"}
    score_partial = calculate_jaccard_similarity(set3, set4)
    assert score_partial == 0.5  # Intersection {'vlan'} (size 1) / Union {'vlan', 'routing'} (size 2)

    # No match sets
    set5 = {"vlan"}
    set6 = {"routing"}
    score_none = calculate_jaccard_similarity(set5, set6)
    assert score_none == 0.0


def test_retrieve_similar_cases():
    historical = [
        {
            "case_id": "CASE-001",
            "symptom": "PC cannot reach server across VLAN 30",
            "network_dna": {"vlans": [{"id": "30"}]},
            "root_cause": "SVI for VLAN 30 is down."
        },
        {
            "case_id": "CASE-002",
            "symptom": "OSPF routing table missing dynamic prefix",
            "network_dna": {"routes": []},
            "root_cause": "OSPF interface cost mismatch."
        }
    ]
    
    query = "VLAN 30 SVI line protocol down"
    matches = retrieve_similar_cases(query, historical, top_n=2)
    
    # The first case (VLAN 30) should be ranked higher than the second case
    assert len(matches) > 0
    assert matches[0]["case"]["case_id"] == "CASE-001"
    assert matches[0]["score"] > 0.0



