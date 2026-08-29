# tests/test_ai_diagnosis.py
import pytest
from run_diagnosis import build_prompt
from ai.reasonchain import validate_diagnosis_json, format_reasonchain

# Helper valid JSON response
def get_valid_mock_diagnosis():
    return {
        "root_cause": "VLAN 30 is missing active member ports.",
        "confidence": 0.95,
        "evidence": ["Vlan30 is up, line protocol is down"],
        "next_command": "show interfaces status",
        "fix_steps": ["SW1(config-if)# switchport access vlan 30"],
        "alternatives": ["VLAN 30 shutdown globally"],
        "contradicting_evidence": ["VLAN 30 is active in brief"],
        "evidence_sufficiency": "sufficient"
    }


# 1. Valid AI JSON
def test_valid_ai_json():
    diag = get_valid_mock_diagnosis()
    assert validate_diagnosis_json(diag) is True


# 2. Invalid confidence
def test_invalid_confidence():
    # Confidence out of range (greater than 1.0)
    diag = get_valid_mock_diagnosis()
    diag["confidence"] = 1.5
    assert validate_diagnosis_json(diag) is False

    # Confidence out of range (negative)
    diag["confidence"] = -0.1
    assert validate_diagnosis_json(diag) is False

    # Confidence is non-numeric string
    diag["confidence"] = "high"
    assert validate_diagnosis_json(diag) is False


# 3. Missing root_cause
def test_missing_root_cause():
    diag = get_valid_mock_diagnosis()
    del diag["root_cause"]
    assert validate_diagnosis_json(diag) is False


# 4. Invalid evidence type
def test_invalid_evidence_type():
    diag = get_valid_mock_diagnosis()
    diag["evidence"] = "Vlan30 line protocol down string instead of list"
    assert validate_diagnosis_json(diag) is False


# 5. ReasonChain formatting
def test_reasonchain_formatting():
    diag = get_valid_mock_diagnosis()
    rc = format_reasonchain(diag)
    
    assert "POSSIBLE CAUSES" in rc
    assert "1. VLAN 30 is missing active member ports." in rc
    assert "Confidence:\n95%" in rc
    assert "CURRENT MOST LIKELY CAUSE:" in rc
    assert "WHY?" in rc


# 6. Alternatives formatting
def test_alternatives_formatting():
    diag = get_valid_mock_diagnosis()
    diag["alternatives"] = ["Mock Alternative A", "Mock Alternative B"]
    
    rc = format_reasonchain(diag)
    
    assert "2. Mock Alternative A" in rc
    assert "3. Mock Alternative B" in rc
    assert "Confidence:\n2%" in rc  # (1.0 - 0.95) * 100 / 2 = 2.5 -> 2%


# 7. Contradicting evidence formatting
def test_contradicting_evidence_formatting():
    diag = get_valid_mock_diagnosis()
    diag["contradicting_evidence"] = ["Contradicting observation 1"]
    
    rc = format_reasonchain(diag)
    
    assert "Contradicting evidence:" in rc
    assert "- Contradicting observation 1" in rc


# 8. Prompt variable replacement
def test_prompt_variable_replacement():
    template = "SYMPTOM: {{SYMPTOM}} | TOPOLOGY: {{TOPOLOGY_NOTE}} | OUTPUT: {{SHOW_OUTPUT}}"
    row = {
        "symptom": "Test Symptom",
        "topology_note": "Test Note",
        "show_output": "Test Output"
    }
    filled = build_prompt(template, row)
    
    assert "SYMPTOM: Test Symptom" in filled
    assert "TOPOLOGY: Test Note" in filled
    assert "OUTPUT: Test Output" in filled
