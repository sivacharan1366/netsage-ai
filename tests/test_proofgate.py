# tests/test_proofgate.py
import pytest
from verification.proofgate import check_conflicts

# 1. Conflict raised when deterministic rules find VLAN mismatch but AI diagnosis misses keywords
def test_proofgate_conflict_vlan():
    findings = ["CDP Native VLAN mismatch warning discovered on Gi0/1"]
    ai_rc = "The interface Gi0/1 is experiencing high interface latency."
    
    res = check_conflicts(findings, ai_rc)
    assert res["conflict_detected"] is True
    assert len(res["conflict_messages"]) == 1
    assert "Native VLAN mismatch" in res["conflict_messages"][0]


# 2. Clean pass when deterministic rules match VLAN mismatch and AI mentions keyword
def test_proofgate_pass_vlan():
    findings = ["CDP Native VLAN mismatch warning discovered on Gi0/1"]
    ai_rc = "The trunk interface native VLAN configuration is mismatched between switches."
    
    res = check_conflicts(findings, ai_rc)
    assert res["conflict_detected"] is False
    assert len(res["conflict_messages"]) == 0


# 3. No conflict when findings list has no triggers
def test_proofgate_no_triggers():
    findings = ["No critical errors found"]
    ai_rc = "The default gateway is configured on a separate subnet than client."
    
    res = check_conflicts(findings, ai_rc)
    assert res["conflict_detected"] is False
    assert len(res["conflict_messages"]) == 0


# 4. Interface down triggers and checks keywords
def test_proofgate_admin_down_conflict():
    findings = ["Interface is administratively down on Gi0/2"]
    ai_rc = "Routing metric cost mismatch."
    
    res = check_conflicts(findings, ai_rc)
    assert res["conflict_detected"] is True
    assert "down interface/protocol" in res["conflict_messages"][0]


# 5. Multiple conflicts aggregate
def test_proofgate_multiple_conflicts():
    findings = [
        "CDP Native VLAN mismatch warning discovered on Gi0/1",
        "Rogue DHCP server signature identified"
    ]
    ai_rc = "OSPF cost is mismatched."
    
    res = check_conflicts(findings, ai_rc)
    assert res["conflict_detected"] is True
    assert len(res["conflict_messages"]) == 2
