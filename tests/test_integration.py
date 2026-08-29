# tests/test_integration.py
import pytest
import os
import json
from unittest.mock import patch, MagicMock

# Import core modules
from rule_checker import check_case
from evidence_radar.radar import check_evidence_radar
from network_dna.fingerprint import extract_network_dna, retrieve_similar_cases
from verification.proofgate import check_conflicts
from verification.post_fix import verify_fix
from verification.vault import add_verified_case, get_verified_cases
from ai.reasonchain import format_reasonchain

# Temporary memory vault seed path for testing
TEST_VAULT_PATH = "tests/test_memory.json"

@pytest.fixture(autouse=True)
def setup_and_teardown_vault():
    # Setup: Create empty mock vault
    with open(TEST_VAULT_PATH, "w", encoding="utf-8") as f:
        json.dump([], f)
        
    # Patch the global vault storage path in vault.py to redirect to test_memory.json
    with patch("verification.vault.DEFAULT_VAULT_PATH", TEST_VAULT_PATH):
        yield
        
    # Teardown: Remove test file
    if os.path.exists(TEST_VAULT_PATH):
        os.remove(TEST_VAULT_PATH)


def test_complete_integration_workflow():
    # 1. Mock inputs representing a VLAN SVI down case
    symptom = "VLAN 30 SVI interface is inactive"
    show_output = "Vlan30 is up, line protocol is down\nshow interfaces trunk\nshow vlan brief"
    category = "vlan"
    
    # 2. Step 1: Evidence Radar
    radar_res = check_evidence_radar(category, show_output)
    assert radar_res["score"] >= 0.4  # Sufficient evidence
    assert not radar_res["missing_critical"]
    
    # 3. Step 2: Network DNA Extraction
    dna = extract_network_dna(show_output, symptom)
    assert any(i["name"].lower() == "vlan30" for i in dna["interfaces"])
    
    # 4. Step 3: AI Diagnosis simulation (safe mock validation)
    mock_ai_output = {
        "root_cause": "No active physical switchports assigned to VLAN 30",
        "confidence": 0.90,
        "evidence": ["Vlan30 line protocol is down"],
        "next_command": "show vlan brief",
        "fix_steps": ["Assign GigabitEthernet0/1 to vlan 30", "no shutdown"],
        "alternatives": ["Check trunk allowed VLAN list"],
        "contradicting_evidence": ["None"],
        "evidence_sufficiency": "sufficient"
    }
    
    rc_text = format_reasonchain(mock_ai_output)
    assert "POSSIBLE CAUSES" in rc_text or "ROOT CAUSE" in rc_text
    
    # 5. Step 4: ProofGate Conflict Checks
    # Run local deterministic checks
    findings = check_case(show_output)
    assert len(findings) > 0  # SVI protocol down rule triggers
    
    # Check conflict with AI diagnosis
    proof_res = check_conflicts(findings, mock_ai_output["root_cause"])
    assert not proof_res["conflict_detected"]  # Aligns nicely
    
    # 6. Step 5: Human Review Approval
    human_decision = "Accepted"
    
    # 7. Step 6: Post-Fix Verification (Successful)
    # After output must include: port assignment in show vlan brief AND line protocol is up
    after_output = "30   HR                               active    Gi0/1\nVlan30 is up, line protocol is up"
    post_res = verify_fix(category, show_output, after_output)
    assert post_res["passed_verification"] is True
    
    # 8. Step 7: Archiving to Memory Vault
    # Eligibility check: Approved and verified
    assert human_decision in ["Accepted", "Edited"]
    assert post_res["passed_verification"] is True
    # Write to mock vault database
    success = add_verified_case(
        case_id="NS-MOCK-01",
        symptom=symptom,
        network_dna=dna,
        root_cause=mock_ai_output["root_cause"],
        fix=mock_ai_output["fix_steps"],
        concept=category,
        human_review="approved",
        post_fix_verification="verified",
        path=TEST_VAULT_PATH
    )
    assert success is True
    
    # Check that case became searchable and exists in vault list
    vault_cases = get_verified_cases(TEST_VAULT_PATH)
    assert len(vault_cases) == 1
    assert vault_cases[0]["case_id"] == "NS-MOCK-01"


def test_integration_insufficient_evidence():
    category = "vlan"
    # Show output lacks trunk and Brief logs required for VLAN
    show_output = "some simple log output"
    
    radar_res = check_evidence_radar(category, show_output)
    assert radar_res["score"] < 0.4  # Insufficient
    assert len(radar_res["missing_critical"]) > 0


def test_integration_proofgate_conflict():
    show_output = "Vlan30 is up, line protocol is down"
    # AI diagnosis completely unrelated to the SVI issue
    ai_root_cause = "OSPF hello timer mismatch on link"
    
    findings = check_case(show_output)
    proof_res = check_conflicts(findings, ai_root_cause)
    
    assert proof_res["conflict_detected"] is True
    assert "interface/protocol" in proof_res["conflict_messages"][0].lower()


def test_integration_verification_failure():
    category = "vlan"
    before = "Vlan30 is up, line protocol is down"
    # After state still retains the error protocol signature
    after = "Vlan30 is up, line protocol is down"
    
    post_res = verify_fix(category, before, after)
    assert post_res["passed_verification"] is False
    assert post_res["verification_status"] == "failed"
