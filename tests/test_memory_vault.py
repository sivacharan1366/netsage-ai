# tests/test_memory_vault.py
import json
import pytest
from verification.vault import (
    load_memory,
    save_memory,
    is_verified,
    add_verified_case,
    get_verified_cases,
)
from network_dna.fingerprint import retrieve_similar_cases

@pytest.fixture
def temp_vault(tmp_path):
    """Fixture returning a temporary path for the vault JSON file."""
    return str(tmp_path / "memory.json")


# 1. Unverified case cannot enter vault
def test_unverified_case_rejected(temp_vault):
    success = add_verified_case(
        case_id="NS-001",
        symptom="PC cannot reach SVI default gateway.",
        network_dna={"interfaces": ["Vlan10"]},
        root_cause="VLAN interface is down.",
        fix="no shutdown",
        concept="VLAN",
        human_review="unreviewed",
        post_fix_verification="failed",
        path=temp_vault
    )
    assert success is False
    assert len(load_memory(temp_vault)) == 0


# 2. AI-only approval cannot enter vault
def test_ai_only_approval_rejected(temp_vault):
    # Vault does not take AI review fields; it only takes human and post-fix validation
    success = add_verified_case(
        case_id="NS-002",
        symptom="Route missing.",
        network_dna={"routes": []},
        root_cause="No default route.",
        fix="ip route 0.0.0.0 ...",
        concept="Routing",
        human_review="unreviewed",            # AI might have high confidence, but human has not reviewed
        post_fix_verification="unverified",     # Post-fix has not run
        path=temp_vault
    )
    assert success is False
    assert len(load_memory(temp_vault)) == 0


# 3. Human approval without verification cannot enter vault
def test_human_approved_but_unverified_rejected(temp_vault):
    success = add_verified_case(
        case_id="NS-003",
        symptom="NAT translations empty.",
        network_dna={"nat": []},
        root_cause="NAT inside not defined.",
        fix="ip nat inside",
        concept="NAT",
        human_review="approved",               # Human approved
        post_fix_verification="unverified",    # Post-fix is NOT verified
        path=temp_vault
    )
    assert success is False
    assert len(load_memory(temp_vault)) == 0


# 4. Verification without human approval cannot enter vault
def test_verified_but_unapproved_rejected(temp_vault):
    success = add_verified_case(
        case_id="NS-004",
        symptom="DHCP failure.",
        network_dna={"dhcp": []},
        root_cause="Pool empty.",
        fix="network 10.0.0.0 ...",
        concept="DHCP",
        human_review="rejected",               # Human did NOT approve (rejected/edited)
        post_fix_verification="verified",      # Post-fix passed (maybe by accident or false positive)
        path=temp_vault
    )
    assert success is False
    assert len(load_memory(temp_vault)) == 0


# 5. Human approval + successful verification allows entry
def test_approved_and_verified_allowed(temp_vault):
    success = add_verified_case(
        case_id="NS-005",
        symptom="Duplicate IP warning.",
        network_dna={"ip_addresses": ["10.0.0.1"]},
        root_cause="Duplicate IP on Gi0/1 and Gi0/2.",
        fix="change Gi0/2 IP",
        concept="IP Addressing",
        human_review="approved",
        post_fix_verification="verified",
        path=temp_vault
    )
    assert success is True
    
    cases = load_memory(temp_vault)
    assert len(cases) == 1
    assert cases[0]["case_id"] == "NS-005"
    assert cases[0]["verified"] is True


# 6. Duplicate verified cases are handled safely
def test_duplicate_verified_cases_updated(temp_vault):
    # Add initial case
    add_verified_case(
        case_id="NS-006",
        symptom="OSPF down.",
        network_dna={"routes": []},
        root_cause="OSPF cost mismatch.",
        fix="match interface costs",
        concept="OSPF",
        human_review="approved",
        post_fix_verification="verified",
        path=temp_vault
    )
    
    # Add same case ID with updated information
    add_verified_case(
        case_id="NS-006",
        symptom="OSPF down (updated).",
        network_dna={"routes": []},
        root_cause="OSPF hello timer mismatch.",
        fix="match hello interval",
        concept="OSPF",
        human_review="approved",
        post_fix_verification="verified",
        path=temp_vault
    )
    
    cases = load_memory(temp_vault)
    assert len(cases) == 1  # No duplicate record added
    assert cases[0]["symptom"] == "OSPF down (updated)."
    assert cases[0]["root_cause"] == "OSPF hello timer mismatch."


# 7. Similarity search only searches verified memories
def test_similarity_searches_verified_only(temp_vault):
    # Seed mock vault file directly with one verified and one unverified record
    mock_data = [
        {
            "case_id": "NS-007",
            "symptom": "OSPF cost mismatch on Serial0/0.",
            "network_dna": {},
            "root_cause": "OSPF cost.",
            "concept": "OSPF",
            "verified": True
        },
        {
            "case_id": "NS-008",
            "symptom": "OSPF link state down.",
            "network_dna": {},
            "root_cause": "OSPF down.",
            "concept": "OSPF",
            "verified": False  # NOT verified
        }
    ]
    save_memory(mock_data, temp_vault)
    
    # Retrieve only verified cases from vault
    verified_cases = get_verified_cases(temp_vault)
    assert len(verified_cases) == 1
    assert verified_cases[0]["case_id"] == "NS-007"
    
    # Run similarity retrieval on the verified list
    query = "OSPF issue link"
    matches = retrieve_similar_cases(query, verified_cases, top_n=2)
    
    assert len(matches) == 1
    assert matches[0]["case"]["case_id"] == "NS-007"


# 8. Similarity ranking works correctly
def test_similarity_ranking(temp_vault):
    mock_data = [
        {
            "case_id": "NS-009",
            "symptom": "Native VLAN mismatch warning CDP.",
            "network_dna": {},
            "root_cause": "VLAN native mismatch.",
            "concept": "VLAN",
            "verified": True
        },
        {
            "case_id": "NS-010",
            "symptom": "DHCP address pool exhausted.",
            "network_dna": {},
            "root_cause": "DHCP full.",
            "concept": "DHCP",
            "verified": True
        }
    ]
    save_memory(mock_data, temp_vault)
    verified = get_verified_cases(temp_vault)
    
    # Query is highly related to VLANs, should rank NS-009 higher
    matches = retrieve_similar_cases("CDP VLAN Native mismatch", verified, top_n=2)
    assert len(matches) == 1  # NS-010 has no overlapping tokens, filtered out
    assert matches[0]["case"]["case_id"] == "NS-009"
