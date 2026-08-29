# tests/test_rule_checker.py
import pytest
from rule_checker import (
    check_duplicate_ip,
    check_wrong_mask,
    check_gateway_mismatch,
    check_interface_down,
    check_missing_vlan,
    check_missing_route,
)

# =============================================================================
# 1. DUPLICATE IP TESTS
# =============================================================================

def test_check_duplicate_ip_good():
    evidence = """
    interface GigabitEthernet0/1
     ip address 192.168.1.1 255.255.255.0
    interface GigabitEthernet0/2
     ip address 192.168.2.1 255.255.255.0
    """
    findings = check_duplicate_ip(evidence)
    assert len(findings) == 0

def test_check_duplicate_ip_bad():
    evidence = """
    interface GigabitEthernet0/1
     ip address 192.168.1.1 255.255.255.0
    interface GigabitEthernet0/2
     ip address 192.168.1.1 255.255.255.0
    """
    findings = check_duplicate_ip(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "DUPLICATE_IP"
    assert "192.168.1.1" in findings[0]["evidence"]

# =============================================================================
# 2. WRONG MASK TESTS
# =============================================================================

def test_check_wrong_mask_good():
    evidence = """
    interface GigabitEthernet0/1
     ip address 192.168.1.1 255.255.255.0
    interface Loopback0
     ip address 1.1.1.1 255.255.255.255
    """
    findings = check_wrong_mask(evidence)
    assert len(findings) == 0

def test_check_wrong_mask_bad_suspicious():
    evidence = """
    interface GigabitEthernet0/1
     ip address 192.168.1.1 255.255.255.255
    """
    findings = check_wrong_mask(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "WRONG_MASK"
    assert "255.255.255.255" in findings[0]["evidence"]

def test_check_wrong_mask_bad_inconsistent():
    evidence = """
    network 192.168.1.0 255.255.255.0
    network 192.168.1.128 255.255.255.240
    """
    findings = check_wrong_mask(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "WRONG_MASK"
    assert "Inconsistent masks" in findings[0]["evidence"]

# =============================================================================
# 3. GATEWAY MISMATCH TESTS
# =============================================================================

def test_check_gateway_mismatch_good():
    evidence = """
    IP Address. . . . . . . . . . . . : 192.168.1.10
    Subnet Mask . . . . . . . . . . . : 255.255.255.0
    Default Gateway . . . . . . . . . : 192.168.1.1
    """
    findings = check_gateway_mismatch(evidence)
    assert len(findings) == 0

def test_check_gateway_mismatch_bad_unreachable():
    evidence = """
    Default Gateway . . . . . . . : 192.168.1.254  (unreachable - no host)
    """
    findings = check_gateway_mismatch(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "GATEWAY_MISMATCH"
    assert "192.168.1.254" in findings[0]["evidence"]

def test_check_gateway_mismatch_bad_dhcp_pool():
    evidence = """
    ip dhcp pool LAN_POOL
     network 192.168.1.0 255.255.255.0
     ! default-router line missing
    """
    findings = check_gateway_mismatch(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "GATEWAY_MISMATCH"
    assert "default-router" in findings[0]["evidence"]

# =============================================================================
# 4. INTERFACE STATUS TESTS
# =============================================================================

def test_check_interface_down_good():
    evidence = """
    GigabitEthernet0/1 is up, line protocol is up
    """
    findings = check_interface_down(evidence)
    assert len(findings) == 0

def test_check_interface_down_bad_admin():
    evidence = """
    GigabitEthernet0/1 is administratively down, line protocol is down
    """
    findings = check_interface_down(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "INTERFACE_DOWN"
    assert "GigabitEthernet0/1" in findings[0]["evidence"]
    assert "administratively down" in findings[0]["explanation"]

def test_check_interface_down_bad_lineproto():
    evidence = """
    GigabitEthernet0/2 is up, line protocol is down
    """
    findings = check_interface_down(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "INTERFACE_DOWN"
    assert "GigabitEthernet0/2" in findings[0]["evidence"]
    assert "line protocol is down" in findings[0]["explanation"]

# =============================================================================
# 5. MISSING VLAN TESTS
# =============================================================================

def test_check_missing_vlan_good():
    evidence = """
    switchport access vlan 10
    SW1# show vlan brief
    VLAN Name                             Status    Ports
    ---- -------------------------------- --------- -------------------------------
    1    default                          active    Gi0/1
    10   SALES                            active    Gi0/2
    """
    findings = check_missing_vlan(evidence)
    assert len(findings) == 0

def test_check_missing_vlan_bad_absent():
    evidence = """
    switchport access vlan 50
    SW1# show vlan brief
    VLAN Name                             Status    Ports
    ---- -------------------------------- --------- -------------------------------
    1    default                          active    Gi0/1
    """
    findings = check_missing_vlan(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "MISSING_VLAN"
    assert "VLAN 50 referenced" in findings[0]["evidence"]

def test_check_missing_vlan_bad_empty_svi():
    evidence = """
    Vlan30 is up, line protocol is down
    SW1# show vlan brief
    VLAN Name                             Status    Ports
    ---- -------------------------------- --------- -------------------------------
    30   HR                               active
    """
    findings = check_missing_vlan(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "MISSING_VLAN"
    assert "VLAN 30 is 'active' in vlan brief with no ports" in findings[0]["evidence"]

# =============================================================================
# 6. MISSING ROUTE TESTS
# =============================================================================

def test_check_missing_route_good():
    evidence = """
    Sending 5, 100-byte ICMP Echos to 8.8.8.8, timeout is 2 seconds:
    !!!!!
    Success rate is 100 percent (5/5)
    """
    findings = check_missing_route(evidence)
    assert len(findings) == 0

def test_check_missing_route_bad():
    evidence = """
    R1# show ip route 8.8.8.8
    % Network not in table
    """
    findings = check_missing_route(evidence)
    assert len(findings) == 1
    assert findings[0]["check"] == "MISSING_ROUTE"
    assert "% Network not in table" in findings[0]["evidence"]
