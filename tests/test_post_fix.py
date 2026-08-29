# tests/test_post_fix.py
import pytest
from verification.post_fix import verify_fix

# 1. VLAN failure -> success (includes port assignment in show vlan brief)
def test_verify_fix_vlan_success():
    category = "VLAN"
    before = "Vlan30 is up, line protocol is down"
    # After: VLAN 30 now has Gi0/3 assigned (dual criterion: port + line protocol)
    after  = "30   HR                               active    Gi0/3\nVlan30 is up, line protocol is up"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is True
    assert res["verification_status"] == "verified"
    assert "VLAN" in res["message"]


# 2. Interface admin-down -> up
def test_verify_fix_interface_success():
    category = "Interface"
    before = "GigabitEthernet0/1 is administratively down, line protocol is down"
    after  = "GigabitEthernet0/1 is up, line protocol is up"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is True
    assert res["verification_status"] == "verified"


# 3. Routing failure -> valid route
def test_verify_fix_routing_success():
    category = "Routing"
    before = "% Network not in table"
    after  = "O    10.1.1.0/24 [110/65] via 192.168.1.1"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is True
    assert res["verification_status"] == "verified"


# 4. Gateway timeout -> successful gateway response
def test_verify_fix_gateway_success():
    category = "Gateway"
    before = "Request timeout.\nRequest timeout.\n0% packet success."
    after  = "Success rate is 100 percent (5/5), round-trip min/avg/max = 1/2/4 ms"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is True
    assert res["verification_status"] == "verified"


# 5. Failure when fault remains
def test_verify_fix_fault_remains():
    category = "VLAN"
    before = "Vlan30 is up, line protocol is down"
    after  = "Vlan30 is up, line protocol is down (no ports active)"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is False
    assert res["verification_status"] == "failed"


# 5b. VLAN: line protocol is up but no port in show vlan brief -> still FAILED
def test_verify_fix_vlan_port_missing():
    """Verifies that 'line protocol is up' alone is not enough — port must appear in vlan brief."""
    category = "VLAN"
    before = "Vlan30 is up, line protocol is down"
    # Simulates an AFTER state where only line protocol text was changed but no port was configured
    after  = "30   HR                               active\nVlan30 is up, line protocol is up"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is False
    assert res["verification_status"] == "failed"
    assert "Access port assignment not reflected" in res["message"]


# 6. Failure when evidence is insufficient
def test_verify_fix_insufficient_evidence():
    category = "UnknownCategory"
    before = "some output"
    after  = "some output"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is False
    assert res["verification_status"] == "failed"
    assert "Insufficient evidence" in res["message"]


# 7. NAT verification
def test_verify_fix_nat_success():
    category = "NAT"
    before = "Empty translations"
    after  = "Pro Inside global      Inside local       Outside local      Outside global\ntcp 192.168.1.1:80      10.0.0.10:80       192.168.1.254:80   192.168.1.254:80"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is True
    assert res["verification_status"] == "verified"


# 8. DHCP verification
def test_verify_fix_dhcp_success():
    category = "DHCP"
    before = "IP Address . . . . . . . . . . . : 0.0.0.0"
    after  = "IP Address . . . . . . . . . . . : 192.168.1.11 (leased)"
    
    res = verify_fix(category, before, after)
    assert res["passed_verification"] is True
    assert res["verification_status"] == "verified"


# 9. CASE-006 Gateway Simulation and Verification Test
def test_case_006_gateway_simulation_and_verification():
    from dashboard import simulate_after_state
    
    case_006_row = {
        "case_id": "CASE-006",
        "category": "gateway",
        "symptom": "PC can ping hosts on the local subnet but cannot reach anything beyond the router.",
        "show_output": (
            "PC-A> ping 8.8.8.8\n"
            "Request timeout for icmp_seq 0\n\n"
            "PC-A> ping 192.168.1.1\n"
            "84 bytes from 192.168.1.1: icmp_seq=1 ttl=255 time=1 ms\n\n"
            "R1# show ip route 8.8.8.8\n"
            "% Network not in table\n\n"
            "PC-A ipconfig:\n"
            "  Default Gateway . . . . . . . : 192.168.1.254  (unreachable - no host)"
        )
    }
    
    after_output = simulate_after_state(case_006_row)
    
    # Assert AFTER output is genuinely different from BEFORE output
    assert after_output != case_006_row["show_output"]
    assert "Default Gateway . . . . . . . : 192.168.1.1" in after_output
    assert "192.168.1.254" not in after_output
    assert "unreachable - no host" not in after_output
    assert "Success rate is 100 percent" in after_output
    
    # Run post-fix verification
    res = verify_fix("gateway", case_006_row["show_output"], after_output)
    assert res["passed_verification"] is True
    assert res["verification_status"] == "verified"

