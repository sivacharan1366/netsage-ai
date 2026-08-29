# tests/test_evidence_radar.py
import pytest
from evidence_radar.radar import check_evidence_sufficiency

# 1. Sufficiency on fully sufficient output
def test_evidence_sufficiency_complete():
    category = "VLAN"
    show_output = """
    SW1# show vlan brief
    10   SALES   active
    SW1# show interfaces trunk
    Gi0/1 on 802.1q trunking 1
    """
    res = check_evidence_sufficiency(category, show_output)
    
    assert res["evidence_sufficiency"] == "sufficient"
    assert res["can_diagnose"] is True
    assert res["score"] == 1.0
    assert len(res["missing_critical"]) == 0
    assert len(res["recommended_next_commands"]) == 0


# 2. Missing critical command override
def test_evidence_sufficiency_missing_critical():
    category = "VLAN"
    show_output = """
    SW1# show vlan brief
    10   SALES   active
    """
    res = check_evidence_sufficiency(category, show_output)
    
    assert res["evidence_sufficiency"] == "partial"
    assert res["can_diagnose"] is False
    assert res["score"] == 0.5
    assert "show interfaces trunk" in res["missing_critical"]
    assert "show interfaces trunk" in res["recommended_next_commands"]


# 3. Correct command recommendation
def test_evidence_sufficiency_recommendations():
    category = "Routing"
    show_output = ""  # Empty output, missing all
    res = check_evidence_sufficiency(category, show_output)
    
    assert res["can_diagnose"] is False
    assert res["score"] == 0.0
    assert "show ip route" in res["recommended_next_commands"]


# 4. Unregistered categories fallback checks
def test_evidence_sufficiency_fallback():
    category = "UnknownCategory"
    show_output = "SW1# show ip interface brief"
    res = check_evidence_sufficiency(category, show_output)
    
    # Fallback checklist expects show ip interface brief (which exists)
    assert res["can_diagnose"] is True
    assert res["score"] == 1.0
    assert len(res["recommended_next_commands"]) == 0


# 5. Case-insensitivity and alias support
def test_evidence_sufficiency_case_insensitive():
    category = "Gateway/IP"
    show_output = "ip ROUTE 10.0.0.0 via 192.168.1.1\nipconfig"
    res = check_evidence_sufficiency(category, show_output)
    
    assert res["can_diagnose"] is True
    assert res["score"] == 1.0
