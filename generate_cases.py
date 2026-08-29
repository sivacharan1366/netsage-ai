"""
generate_cases.py
=================
NetSage Phase 1 — Data Collection Script
Generates cases.csv with 30+ realistic network troubleshooting cases.

HOW TO ADD NEW CASES:
  1. Add a new dictionary to the CASES list below.
  2. Fill in all 7 fields (see field guide at the top of CASES).
  3. Run:  python generate_cases.py
  4. Verify the last rows of cases.csv.

FIELD GUIDE:
  symptom       — Plain-English symptom the user/engineer observes
  topology_note — Topology context (devices, links, vlans involved)
  show_output   — Verbatim Cisco IOS show-command output (multi-line OK)
  expected_fault— Root cause / what is actually broken
  osi_layer     — OSI layer number + name, e.g. "2 - Data Link"
  concept_tag   — Comma-separated tags, e.g. "vlan,trunk,802.1q"
  severity      — low | medium | high | critical
"""

import sys
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import csv
import textwrap
from pathlib import Path


# =============================================================================
# CASES — edit this list to add / modify cases
# =============================================================================
CASES = [

    # =========================================================================
    # CATEGORY 1: VLAN  (cases 1-5)
    # =========================================================================
    {
        "symptom": "PC in VLAN 20 cannot reach PC in VLAN 30; both can ping their default gateway.",
        "topology_note": "SW1 (3560) inter-VLAN routing; SVI for VLAN 20 (192.168.20.1) and VLAN 30 (192.168.30.1). PC-A: 192.168.20.10/24, PC-B: 192.168.30.10/24.",
        "show_output": textwrap.dedent("""\
            SW1# show vlan brief

            VLAN Name                             Status    Ports
            ---- -------------------------------- --------- -------------------------------
            1    default                          active    Gi0/1
            20   SALES                            active    Gi0/2
            30   HR                               active
            1002 fddi-default                     act/unsup
            1003 token-ring-default               act/unsup
            1004 fddinet-default                  act/unsup
            1005 trnet-default                    act/unsup

            SW1# show interfaces vlan 30
            Vlan30 is up, line protocol is down"""),
        "expected_fault": "SVI for VLAN 30 is down (line protocol down) because no active access port is assigned to VLAN 30. PC-B port Gi0/3 was never added to VLAN 30.",
        "osi_layer": "2 - Data Link",
        "concept_tag": "vlan,svi,inter-vlan-routing",
        "severity": "high",
    },
    {
        "symptom": "Trunk between SW1 and SW2 is up, but VLAN 10 traffic does not cross the trunk.",
        "topology_note": "SW1 Gi0/1 <-> SW2 Gi0/1 trunk link. VLAN 10 (ENGINEERING) exists on both switches.",
        "show_output": textwrap.dedent("""\
            SW1# show interfaces trunk

            Port        Mode         Encapsulation  Status        Native vlan
            Gi0/1       on           802.1q         trunking      1

            Port        Vlans allowed on trunk
            Gi0/1       1-9,11-4094

            Port        Vlans allowed and active in management domain
            Gi0/1       1

            Port        Vlans in spanning tree forwarding state and not pruned
            Gi0/1       1"""),
        "expected_fault": "VLAN 10 is explicitly excluded from the trunk allowed-VLAN list (1-9,11-4094 skips 10). Command needed: switchport trunk allowed vlan add 10",
        "osi_layer": "2 - Data Link",
        "concept_tag": "vlan,trunk,802.1q,allowed-vlan",
        "severity": "high",
    },
    {
        "symptom": "Native VLAN mismatch warning on trunk; spanning-tree port goes err-disabled.",
        "topology_note": "SW1 Gi0/1 native VLAN 1; SW2 Gi0/1 native VLAN 99. CDP sends mismatch warning.",
        "show_output": textwrap.dedent("""\
            SW1# show interfaces Gi0/1 trunk
            Port        Mode         Encapsulation  Status        Native vlan
            Gi0/1       desirable    802.1q         trunking      1

            %CDP-4-NATIVE_VLAN_MISMATCH: Native VLAN mismatch discovered on
            GigabitEthernet0/1 (1), with SW2 GigabitEthernet0/1 (99).

            SW1# show spanning-tree vlan 1
            VLAN0001
              ...
              Gi0/1   *BLK*   128.1    P2p"""),
        "expected_fault": "Native VLAN mismatch between SW1 (native 1) and SW2 (native 99). Fix: set both trunk ports to the same native VLAN with 'switchport trunk native vlan 99'.",
        "osi_layer": "2 - Data Link",
        "concept_tag": "vlan,trunk,native-vlan,cdp,spanning-tree",
        "severity": "medium",
    },
    {
        "symptom": "Access port on SW1 is assigned to VLAN 50 but VLAN 50 does not exist in the VLAN database.",
        "topology_note": "SW1 Gi0/5 configured as access port for VLAN 50. No VLAN 50 in VTP database.",
        "show_output": textwrap.dedent("""\
            SW1# show vlan brief
            VLAN Name                             Status    Ports
            ---- -------------------------------- --------- ------
            1    default                          active    Gi0/5

            SW1# show running-config interface GigabitEthernet0/5
            interface GigabitEthernet0/5
             switchport access vlan 50
             switchport mode access

            SW1# show interfaces GigabitEthernet0/5 switchport
            Name: Gi0/5
            Administrative Mode: static access
            Operational Mode: static access
            Access Mode VLAN: 50 (Inactive)"""),
        "expected_fault": "VLAN 50 is referenced in port config but does not exist in the VLAN database. Port falls back to VLAN 1. Fix: 'vlan 50' then 'name <name>' in global config.",
        "osi_layer": "2 - Data Link",
        "concept_tag": "vlan,vlan-database,access-port",
        "severity": "medium",
    },
    {
        "symptom": "All VLANs were wiped from a switch after a reload; only VLAN 1 remains.",
        "topology_note": "VTP mode is transparent on SW1. Technician ran 'delete flash:vlan.dat' before reload.",
        "show_output": textwrap.dedent("""\
            SW1# show vtp status
            VTP Version capable             : 1 to 3
            VTP version running             : 2
            VTP Domain Name                 : CorpNet
            VTP Pruning Mode                : Disabled
            VTP Operating Mode              : Transparent
            Maximum VLANs supported locally : 1005
            Number of existing VLANs        : 1

            SW1# show vlan brief
            VLAN Name                             Status    Ports
            ---- -------------------------------- --------- ------
            1    default                          active    ..."""),
        "expected_fault": "The vlan.dat file was deleted before reload, removing all locally defined VLANs. In VTP Transparent mode VLANs are stored in vlan.dat. Restore from backup or re-create VLANs manually.",
        "osi_layer": "2 - Data Link",
        "concept_tag": "vlan,vtp,vlan.dat,transparent-mode",
        "severity": "critical",
    },

    # =========================================================================
    # CATEGORY 2: GATEWAY / LAYER-3 REACHABILITY  (cases 6-9)
    # =========================================================================
    {
        "symptom": "PC can ping hosts on the local subnet but cannot reach anything beyond the router.",
        "topology_note": "PC-A: 192.168.1.10/24, gateway 192.168.1.254. Router R1 Gi0/0: 192.168.1.1/24.",
        "show_output": textwrap.dedent("""\
            PC-A> ping 8.8.8.8
            Request timeout for icmp_seq 0

            PC-A> ping 192.168.1.1
            84 bytes from 192.168.1.1: icmp_seq=1 ttl=255 time=1 ms

            R1# show ip route 8.8.8.8
            % Network not in table

            PC-A ipconfig:
              Default Gateway . . . . . . . : 192.168.1.254  (unreachable - no host)"""),
        "expected_fault": "PC default gateway is set to 192.168.1.254 but the router interface is 192.168.1.1. PC sends all off-subnet traffic to a non-existent host. Fix: change PC gateway to 192.168.1.1.",
        "osi_layer": "3 - Network",
        "concept_tag": "gateway,ip-config,default-gateway",
        "severity": "high",
    },
    {
        "symptom": "Router has two paths to 10.0.0.0/8; traffic always takes the slower WAN link.",
        "topology_note": "R1 connected to HQ via FastEthernet (100 Mbps) and MPLS via GigabitEthernet (1 Gbps). Both learned via OSPF.",
        "show_output": textwrap.dedent("""\
            R1# show ip route ospf
            O    10.0.0.0/8 [110/20] via 172.16.0.1, FastEthernet0/0

            R1# show interfaces FastEthernet0/0
            FastEthernet0/0 is up, line protocol is up
              MTU 1500 bytes, BW 100000 Kbit/sec

            R1# show interfaces GigabitEthernet0/1
            GigabitEthernet0/1 is up, line protocol is up
              MTU 1500 bytes, BW 1000000 Kbit/sec

            R1# show ip ospf interface GigabitEthernet0/1
              Process ID 1, Router ID 1.1.1.1, Network Type POINT_TO_POINT
              Cost: 1"""),
        "expected_fault": "OSPF auto-cost reference bandwidth is 100 Mbps (default). GigabitEthernet cost rounds to 1, same as FastEthernet, so OSPF may prefer the wrong path. Fix: set 'auto-cost reference-bandwidth 10000' on all OSPF routers.",
        "osi_layer": "3 - Network",
        "concept_tag": "ospf,cost,reference-bandwidth,routing",
        "severity": "medium",
    },
    {
        "symptom": "Hosts in 192.168.2.0/24 cannot reach 192.168.3.0/24 even though both subnets connect to R1.",
        "topology_note": "R1 Gi0/0: 192.168.2.1/24, Gi0/1: 192.168.3.1/24. PC-B: 192.168.2.10 gateway 192.168.2.1.",
        "show_output": textwrap.dedent("""\
            R1# show ip route
            Gateway of last resort is not set
                 192.168.2.0/24 is variably subnetted, 2 subnets, 2 masks
            C       192.168.2.0/24 is directly connected, GigabitEthernet0/0
            L       192.168.2.1/32 is directly connected, GigabitEthernet0/0

            R1# show interfaces GigabitEthernet0/1
            GigabitEthernet0/1 is administratively down, line protocol is down

            R1# show running-config interface GigabitEthernet0/1
            interface GigabitEthernet0/1
             ip address 192.168.3.1 255.255.255.0
             shutdown"""),
        "expected_fault": "Gi0/1 is in administrative shutdown. Connected route for 192.168.3.0/24 is absent. Fix: 'no shutdown' on Gi0/1.",
        "osi_layer": "3 - Network",
        "concept_tag": "interface,shutdown,routing,connected-route",
        "severity": "high",
    },
    {
        "symptom": "HSRP failover does not occur when the active router loses its uplink.",
        "topology_note": "R1 (active, priority 110) and R2 (standby, priority 100) serving VLAN 10 gateway 10.10.10.1. HSRP group 1.",
        "show_output": textwrap.dedent("""\
            R1# show standby brief
            Interface   Grp  Pri P State    Active          Standby         Virtual IP
            Gi0/0       1    110   Active   local           10.10.10.2      10.10.10.1

            R1# show running-config | section standby
             standby 1 ip 10.10.10.1
             standby 1 priority 110
             ! track object and preempt NOT configured

            R2# show standby brief
            Interface   Grp  Pri P State    Active          Standby         Virtual IP
            Gi0/0       1    100   Standby  10.10.10.1      local           10.10.10.1"""),
        "expected_fault": "HSRP tracking is not configured on R1. When R1 WAN uplink fails its priority is not decremented, so R2 never takes over. Fix: 'standby 1 track <WAN-interface> decrement 20' and 'standby 1 preempt' on R1.",
        "osi_layer": "3 - Network",
        "concept_tag": "hsrp,gateway-redundancy,tracking,preempt",
        "severity": "high",
    },

    # =========================================================================
    # CATEGORY 3: DHCP  (cases 10-14)
    # =========================================================================
    {
        "symptom": "Clients in 10.20.0.0/24 receive IP addresses in the 10.10.0.0/24 range instead of their own subnet.",
        "topology_note": "R1 is DHCP server with two pools: POOL_A (10.10.0.0/24) and POOL_B (10.20.0.0/24). SW1 separates the subnets.",
        "show_output": textwrap.dedent("""\
            R1# show running-config | section dhcp
            ip dhcp pool POOL_A
             network 10.10.0.0 255.255.255.0
             default-router 10.10.0.1
             dns-server 8.8.8.8
            ip dhcp pool POOL_B
             network 10.20.0.0 255.255.255.0
             default-router 10.20.0.1

            R1# show ip dhcp binding
            IP address       Client-ID         Lease expiration        Type
            10.10.0.2        0100.5056.b3.4a   Aug 26 2026 12:00 AM    Automatic
            10.10.0.3        0100.5056.b3.4b   Aug 26 2026 12:00 AM    Automatic"""),
        "expected_fault": "The relay (ip helper-address) is missing on the VLAN 20 SVI so all DHCP requests arrive on VLAN 10 interface and match POOL_A. Fix: add 'ip helper-address <R1-IP>' on the VLAN 20 SVI.",
        "osi_layer": "3 - Network",
        "concept_tag": "dhcp,helper-address,ip-relay,pool",
        "severity": "high",
    },
    {
        "symptom": "DHCP clients receive an IP address but no default gateway and no DNS server.",
        "topology_note": "R1 DHCP server for 192.168.1.0/24. Pool configured by junior engineer.",
        "show_output": textwrap.dedent("""\
            R1# show running-config | section dhcp
            ip dhcp excluded-address 192.168.1.1 192.168.1.10
            ip dhcp pool LAN_POOL
             network 192.168.1.0 255.255.255.0
             ! default-router line missing
             ! dns-server line missing

            R1# show ip dhcp binding
            IP address       Client-ID         Lease expiration
            192.168.1.11     0100.1a2b.3c.4d   Aug 27 2026 08:00 AM"""),
        "expected_fault": "DHCP pool LAN_POOL is missing 'default-router' and 'dns-server' options. Clients receive an IP but cannot route or resolve DNS. Fix: add 'default-router 192.168.1.1' and 'dns-server 8.8.8.8' inside the pool.",
        "osi_layer": "3 - Network",
        "concept_tag": "dhcp,pool,default-router,dns-server,option",
        "severity": "high",
    },
    {
        "symptom": "DHCP pool is exhausted; new clients get APIPA addresses (169.254.x.x).",
        "topology_note": "R1 DHCP pool for 192.168.1.0/24. 254 hosts in the office; pool not sized correctly.",
        "show_output": textwrap.dedent("""\
            R1# show ip dhcp pool
             Pool LAN_POOL :
              Total addresses                : 50
              Leased addresses               : 50
              Current index        IP address range                    Leased addresses
              192.168.1.61         192.168.1.11     - 192.168.1.60     50

            R1# show ip dhcp binding | count
            50"""),
        "expected_fault": "Pool provides only 50 leases (192.168.1.11 - 192.168.1.60) for 254 hosts. Pool exhausted. Fix: extend range or reduce lease time with 'lease 0 4' (4-hour leases).",
        "osi_layer": "3 - Network",
        "concept_tag": "dhcp,pool-exhaustion,lease,apipa",
        "severity": "critical",
    },
    {
        "symptom": "DHCP server on R1 is not serving addresses to clients on a remote subnet connected via R2.",
        "topology_note": "R1 (DHCP server) - R2 - SW2 - clients (10.30.0.0/24). R2 Gi0/1 faces SW2.",
        "show_output": textwrap.dedent("""\
            R2# show running-config interface GigabitEthernet0/1
            interface GigabitEthernet0/1
             ip address 10.30.0.1 255.255.255.0
             ! ip helper-address missing

            R1# show ip dhcp binding
            (empty — no bindings for 10.30.0.0/24)

            R2# debug ip dhcp server packet
            DHCPD: DHCPDISCOVER received on interface GigabitEthernet0/1
            DHCPD: no subnet defined for 10.30.0.1"""),
        "expected_fault": "'ip helper-address <R1-IP>' is missing on R2 Gi0/1. DHCP broadcasts are not relayed to R1. Fix: add 'ip helper-address <R1_IP>' on R2 Gi0/1.",
        "osi_layer": "3 - Network",
        "concept_tag": "dhcp,helper-address,relay-agent,broadcast",
        "severity": "high",
    },
    {
        "symptom": "A rogue DHCP server hands out wrong gateway addresses; clients lose internet access intermittently.",
        "topology_note": "Managed network with authorized DHCP on R1. An unmanaged home router added to VLAN 10 is acting as rogue DHCP server.",
        "show_output": textwrap.dedent("""\
            SW1# show ip dhcp snooping binding
            MacAddress          IpAddress        Lease(sec)  Type       VLAN  Interface
            00:1A:2B:3C:4D:5E   192.168.1.50     86400       dynamic    10    Gi0/3
            00:AA:BB:CC:DD:EE   192.168.0.100    86400       dynamic    10    Gi0/7  <- rogue

            SW1# show running-config | include snooping
            ! ip dhcp snooping vlan 10 NOT configured
            ! ip dhcp snooping trust on uplink NOT configured"""),
        "expected_fault": "DHCP snooping is not enabled. Rogue DHCP server on Gi0/7 serves incorrect gateways. Fix: 'ip dhcp snooping vlan 10', trust legitimate uplinks with 'ip dhcp snooping trust'.",
        "osi_layer": "2 - Data Link",
        "concept_tag": "dhcp,dhcp-snooping,rogue-server,security",
        "severity": "critical",
    },

    # =========================================================================
    # CATEGORY 4: DNS  (cases 15-17)
    # =========================================================================
    {
        "symptom": "Users can ping IP addresses but cannot browse websites by domain name.",
        "topology_note": "Office LAN 192.168.1.0/24, ISP gateway 203.0.113.1, DNS should be 8.8.8.8.",
        "show_output": textwrap.dedent("""\
            PC-A> ping 8.8.8.8
            84 bytes from 8.8.8.8: icmp_seq=1 ttl=57 time=14 ms

            PC-A> ping google.com
            google.com: Temporary failure in name resolution

            PC-A> ipconfig /all
              DNS Servers . . . . . . . . . . : 192.168.1.200

            R1# ping 192.168.1.200
            % No route to host"""),
        "expected_fault": "DNS server address pushed via DHCP (192.168.1.200) points to a non-existent host. Fix: update DHCP pool dns-server to a reachable resolver such as 8.8.8.8.",
        "osi_layer": "7 - Application",
        "concept_tag": "dns,dhcp,name-resolution,dns-server",
        "severity": "high",
    },
    {
        "symptom": "Internal hostname resolution works but external DNS queries fail on a router acting as DNS forwarder.",
        "topology_note": "R1 configured as DNS proxy for the LAN. ISP DNS is 203.0.113.53.",
        "show_output": textwrap.dedent("""\
            R1# show running-config | include dns
             ip dns server
             ip name-server 203.0.113.53

            R1# debug ip dns
            DNS: Sending DNS request to 203.0.113.53
            DNS: Timed out waiting for reply

            R1# ping 203.0.113.53
            !!!!!

            R1# show access-lists
            Extended IP access list BLOCK_DNS
             10 deny udp any host 203.0.113.53 eq 53 (22 matches)
             20 permit ip any any"""),
        "expected_fault": "ACL BLOCK_DNS denies UDP port 53 to ISP DNS server. DNS queries dropped before reaching 203.0.113.53. Fix: remove ACL entry 10 or add permit for UDP/53 to the DNS server.",
        "osi_layer": "7 - Application",
        "concept_tag": "dns,acl,udp,port-53,name-resolution",
        "severity": "high",
    },
    {
        "symptom": "DNS resolution is intermittently slow or times out; some queries succeed, others fail.",
        "topology_note": "Dual-ISP setup. DNS queries load-balanced across two serial links. CRC errors on one link.",
        "show_output": textwrap.dedent("""\
            R1# show interfaces Serial0/1
            Serial0/1 is up, line protocol is up
              MTU 1500 bytes
              Input errors: 312, CRC: 189

            R1# debug ip dns
            DNS query for mail.corp.com -- SUCCESS via Serial0/0
            DNS query for intranet.corp.com -- TIMEOUT via Serial0/1"""),
        "expected_fault": "Serial0/1 has high CRC errors indicating a physical or MTU issue. DNS queries routed via Serial0/1 fail. Fix: investigate cable/CSU-DSU on S0/1 or route DNS traffic only via S0/0.",
        "osi_layer": "1 - Physical",
        "concept_tag": "dns,mtu,crc-errors,dual-isp,serial",
        "severity": "medium",
    },

    # =========================================================================
    # CATEGORY 5: ROUTING  (cases 18-21)
    # =========================================================================
    {
        "symptom": "Traffic to 10.50.0.0/24 is dropped; traceroute shows packets looping between R2 and R3.",
        "topology_note": "R1-R2-R3 ring topology. Static routes configured. 10.50.0.0/24 is behind R3.",
        "show_output": textwrap.dedent("""\
            R2# show ip route 10.50.0.0
            S    10.50.0.0/24 [1/0] via 10.0.23.3

            R3# show ip route 10.50.0.0
            S    10.50.0.0/24 [1/0] via 10.0.23.2  <- points back to R2!

            R3# show ip route
            ! No connected route for 10.50.0.0/24; Gi0/2 is shut

            traceroute 10.50.0.10 from R1:
            1  10.0.12.2  R2
            2  10.0.23.3  R3
            3  10.0.23.2  R2  (loop)
            4  10.0.23.3  R3  (loop)"""),
        "expected_fault": "R3 Gi0/2 (the 10.50.0.0/24 interface) is shutdown so the connected route is absent and R3 static route loops back to R2. Fix: 'no shutdown' on R3 Gi0/2.",
        "osi_layer": "3 - Network",
        "concept_tag": "routing,static-route,routing-loop,traceroute",
        "severity": "critical",
    },
    {
        "symptom": "OSPF adjacency between R1 and R2 is stuck in EXSTART/EXCHANGE state.",
        "topology_note": "R1 (RID 1.1.1.1) and R2 (RID 2.2.2.2) on same Ethernet segment, area 0.",
        "show_output": textwrap.dedent("""\
            R1# show ip ospf neighbor
            Neighbor ID     Pri   State           Dead Time   Address         Interface
            2.2.2.2           1   EXSTART/DR      00:00:32    10.0.12.2       Gi0/0

            R1# show ip ospf interface Gi0/0
              MTU is 1500

            R2# show ip ospf interface Gi0/0
              MTU is 1400

            R1# show ip ospf neighbor detail
              Index 1/1, retransmission queue length 4, number of retransmission 8"""),
        "expected_fault": "MTU mismatch between R1 (1500) and R2 (1400). OSPF DBD packets from R1 exceed R2 MTU and are dropped, preventing LSA exchange. Fix: match MTUs with 'ip mtu 1400' on R1 Gi0/0, or use 'ip ospf mtu-ignore' as workaround.",
        "osi_layer": "3 - Network",
        "concept_tag": "ospf,mtu,adjacency,exstart,lsa",
        "severity": "high",
    },
    {
        "symptom": "Default route is not being advertised into OSPF; branch offices cannot reach the internet.",
        "topology_note": "R1 is ASBR connected to ISP. Default route should be redistributed into OSPF area 0.",
        "show_output": textwrap.dedent("""\
            R1# show ip route
            Gateway of last resort is 203.0.113.1 to network 0.0.0.0
            S*   0.0.0.0/0 [1/0] via 203.0.113.1

            R1# show ip ospf
             Routing Process "ospf 1" with ID 1.1.1.1
             ! default-information originate NOT in config

            R2# show ip route 0.0.0.0
            % Network not in table"""),
        "expected_fault": "'default-information originate' is missing from R1 OSPF process. Static default route exists but is not redistributed. Fix: add 'default-information originate' under 'router ospf 1' on R1.",
        "osi_layer": "3 - Network",
        "concept_tag": "ospf,default-route,default-information-originate,redistribution",
        "severity": "high",
    },
    {
        "symptom": "EIGRP summary route from R2 is present on R1 but traffic to specific subnets is blackholed.",
        "topology_note": "R1-R2-R3 EIGRP AS 100. R2 is hub. Manual summarization 172.16.0.0/16 configured on R2.",
        "show_output": textwrap.dedent("""\
            R1# show ip route eigrp
            D    172.16.0.0/16 [90/2195456] via 10.0.12.2, Gi0/0

            R2# show ip route 172.16.10.0
            % Network not in table

            R2# show running-config | include summary
             ip summary-address eigrp 100 172.16.0.0 255.255.0.0 5

            R2# show ip route
            D    172.16.0.0/16 is a summary, Null0 [5/0]"""),
        "expected_fault": "R2 advertises summary 172.16.0.0/16 but has no specific route to 172.16.10.0/24 (R3 lost that route). R2 installs a Null0 route for the summary and blackholes traffic. Fix: restore R3 specific routes or remove manual summary on R2.",
        "osi_layer": "3 - Network",
        "concept_tag": "eigrp,summarization,null0,blackhole,auto-summary",
        "severity": "high",
    },

    # =========================================================================
    # CATEGORY 6: ACL  (cases 22-25)
    # =========================================================================
    {
        "symptom": "SSH to R1 from the management station is denied but Telnet works fine.",
        "topology_note": "R1 management interface 10.0.0.1/24. ACL applied to vty lines. Management station 10.100.0.5.",
        "show_output": textwrap.dedent("""\
            R1# show access-lists
            Standard IP access list MGMT_ACCESS
             10 permit 10.0.0.0 0.0.0.255
             20 deny   any (44 matches)

            R1# show running-config | section line vty
            line vty 0 4
             access-class MGMT_ACCESS in
             transport input telnet
             ! SSH not in transport input"""),
        "expected_fault": "vty lines configured with 'transport input telnet' only. SSH blocked by transport policy. Fix: 'transport input ssh telnet'. Also verify 'crypto key generate rsa' and 'ip ssh version 2'.",
        "osi_layer": "7 - Application",
        "concept_tag": "acl,ssh,telnet,vty,transport-input",
        "severity": "medium",
    },
    {
        "symptom": "Web server is reachable via ping but HTTP connections are established then hang.",
        "topology_note": "R1 with ACL on Gi0/0 (internet-facing). Web server 192.168.10.50 behind Gi0/1.",
        "show_output": textwrap.dedent("""\
            R1# show ip access-lists INTERNET_IN
            Extended IP access list INTERNET_IN
             10 permit tcp any host 192.168.10.50 eq 80 (1203 matches)
             20 permit tcp any host 192.168.10.50 eq 443 (892 matches)
             30 deny ip any any (1400 matches)

            ! Entry 30 also blocks TCP established return packets and ICMP unreachables"""),
        "expected_fault": "Stateless ACL permits inbound HTTP/HTTPS but entry 30 denies TCP return traffic (SYN-ACK from server). Fix: add 'permit tcp host 192.168.10.50 any established' before entry 30, or use stateful ZBF.",
        "osi_layer": "4 - Transport",
        "concept_tag": "acl,stateless,tcp-established,return-traffic,firewall",
        "severity": "high",
    },
    {
        "symptom": "ACL was meant to block only ICMP from outside but is also blocking all other traffic.",
        "topology_note": "R1 Gi0/0 internet-facing. Extended ACL BLOCK_PING applied inbound.",
        "show_output": textwrap.dedent("""\
            R1# show access-lists BLOCK_PING
            Extended IP access list BLOCK_PING
             10 deny icmp any any
             ! implicit deny all -- no permit statement follows

            R1# show running-config interface GigabitEthernet0/0
            interface GigabitEthernet0/0
             ip access-group BLOCK_PING in"""),
        "expected_fault": "ACL BLOCK_PING denies ICMP but has no 'permit ip any any'. The implicit deny blocks all remaining traffic. Fix: add 'permit ip any any' as last explicit entry.",
        "osi_layer": "3 - Network",
        "concept_tag": "acl,implicit-deny,permit,icmp,access-list",
        "severity": "critical",
    },
    {
        "symptom": "ACL has zero matches; traffic it should block is still flowing through.",
        "topology_note": "R1 Gi0/1 LAN-facing. ACL intended to block 192.168.1.100 from reaching 10.0.0.0/8.",
        "show_output": textwrap.dedent("""\
            R1# show access-lists BLOCK_HOST
            Extended IP access list BLOCK_HOST
             10 deny ip host 192.168.1.100 10.0.0.0 0.0.255.255
             20 permit ip any any

            R1# show running-config interface GigabitEthernet0/1
            interface GigabitEthernet0/1
             ip address 192.168.1.1 255.255.255.0
             ip access-group BLOCK_HOST out   <- outbound on LAN, wrong direction

            ! Traffic from .100 to 10.0.0.0 exits via Gi0/0 (WAN), never hits Gi0/1 outbound"""),
        "expected_fault": "ACL applied outbound on LAN interface Gi0/1 but target traffic exits via WAN Gi0/0. ACL never matches. Fix: apply 'ip access-group BLOCK_HOST in' on Gi0/1 (inbound from LAN).",
        "osi_layer": "3 - Network",
        "concept_tag": "acl,direction,inbound,outbound,access-group",
        "severity": "medium",
    },

    # =========================================================================
    # CATEGORY 7: NAT  (cases 26-28)
    # =========================================================================
    {
        "symptom": "Inside hosts browse the internet but external hosts cannot reach the internal web server via its public IP.",
        "topology_note": "R1 NAT router. Public IP 203.0.113.10. Internal web server 192.168.1.80 port 80.",
        "show_output": textwrap.dedent("""\
            R1# show ip nat translations
            Pro Inside global      Inside local       Outside local      Outside global
            tcp 203.0.113.10:1024  192.168.1.10:1024  8.8.8.8:80         8.8.8.8:80

            R1# show running-config | include nat
             ip nat inside source list NAT_ACL interface GigabitEthernet0/0 overload
             ! Static NAT for web server MISSING

            R1# show ip nat translations | include 203.0.113.10:80
            (no output)"""),
        "expected_fault": "Static NAT entry for the web server is missing. Only dynamic PAT configured. Fix: 'ip nat inside source static tcp 192.168.1.80 80 203.0.113.10 80'.",
        "osi_layer": "3 - Network",
        "concept_tag": "nat,static-nat,pat,port-forwarding,dnat",
        "severity": "high",
    },
    {
        "symptom": "NAT translations appear but internet access fails; inside/outside seem reversed.",
        "topology_note": "R1 NAT. Gi0/0 = WAN (203.0.113.2), Gi0/1 = LAN (192.168.1.1). inside/outside may be swapped.",
        "show_output": textwrap.dedent("""\
            R1# show running-config interface GigabitEthernet0/0
            interface GigabitEthernet0/0
             ip address 192.168.1.1 255.255.255.0
             ip nat inside   <- LAN marked inside (CORRECT here but WAN has wrong IP)

            R1# show running-config interface GigabitEthernet0/1
            interface GigabitEthernet0/1
             ip address 203.0.113.2 255.255.255.252
             ip nat outside  <- WAN marked outside (CORRECT)

            ! BUT ip addresses are swapped: Gi0/0 has LAN IP and Gi0/1 has WAN IP
            ! Physical cables connected in reverse order at the router"""),
        "expected_fault": "Physical cables are swapped: LAN cable plugged into Gi0/0 (marked nat inside, correct) but WAN cable plugged into Gi0/1. The router config is correct but physical connectivity is reversed. Fix: swap cables or update config to match cabling.",
        "osi_layer": "1 - Physical",
        "concept_tag": "nat,inside,outside,pat,physical,cabling",
        "severity": "critical",
    },
    {
        "symptom": "After an IOS upgrade, all NAT translations stopped working; show ip nat translations is empty.",
        "topology_note": "R1 upgraded from IOS 15.4 to 16.9. NAT config unchanged. LAN 10.0.0.0/8, PAT to WAN interface.",
        "show_output": textwrap.dedent("""\
            R1# show ip nat translations
            (empty)

            R1# show running-config | section nat
             ip nat inside source list 10 interface GigabitEthernet0/0 overload

            R1# show access-lists 10
            Standard IP access list 10
             10 permit 10.0.0.0, wildcard bits 0.255.255.255 (0 matches)

            R1# show ip nat statistics
            Total active translations: 0 (0 static, 0 dynamic; 0 extended)"""),
        "expected_fault": "Zero matches on NAT ACL. In IOS 16.x CEF must be active for NAT. If CEF was inadvertently disabled post-upgrade, NAT stops working. Fix: verify 'ip cef' is in config and run 'no ip cef' then 'ip cef' to reset, then test.",
        "osi_layer": "3 - Network",
        "concept_tag": "nat,cef,ios-upgrade,acl,pat",
        "severity": "high",
    },

    # =========================================================================
    # CATEGORY 8: WIRELESS / GUEST ISOLATION  (cases 29-32)
    # =========================================================================
    {
        "symptom": "Wireless guest clients can reach the internet but can also reach internal corporate servers.",
        "topology_note": "WLC 5508 with two SSIDs: CORP (VLAN 10) and GUEST (VLAN 20). Guest should be isolated.",
        "show_output": textwrap.dedent("""\
            WLC> show wlan summary
            WLAN ID  Profile Name  SSID         Status  Interface
            1        CORP          CorpWiFi      Enabled VLAN10
            2        GUEST         GuestWiFi     Enabled VLAN10   <- should be VLAN20!

            WLC> show interface summary
            Interface Name        VLAN  IP Address      Type
            management            1     10.0.0.10       Static
            VLAN10                10    192.168.10.1    Dynamic
            VLAN20                20    192.168.20.1    Dynamic"""),
        "expected_fault": "Guest SSID (WLAN 2) mapped to VLAN10 instead of VLAN20. Guest traffic enters corporate VLAN. Fix: change WLAN 2 interface mapping to VLAN20 on the WLC.",
        "osi_layer": "2 - Data Link",
        "concept_tag": "wireless,wlan,vlan-mapping,guest-isolation,wlc",
        "severity": "critical",
    },
    {
        "symptom": "Wireless clients associate to the AP but cannot obtain a DHCP address; they self-assign 169.254.x.x.",
        "topology_note": "Lightweight AP in FlexConnect local switching mode, VLAN 30 for wireless clients. DHCP on 10.0.0.50.",
        "show_output": textwrap.dedent("""\
            AP# show dot11 associations
            MAC Address     IP Address   SSID       VLAN  State
            00:aa:bb:cc:dd  0.0.0.0      CorpWiFi   30    Assoc

            SW1# show running-config interface GigabitEthernet0/5  (AP uplink)
            interface GigabitEthernet0/5
             switchport trunk encapsulation dot1q
             switchport mode trunk
             switchport trunk allowed vlan 1,10,20
             ! VLAN 30 NOT in allowed list"""),
        "expected_fault": "VLAN 30 is missing from the trunk allowed-VLAN list on the AP uplink. DHCP broadcasts cannot reach the server. Fix: 'switchport trunk allowed vlan add 30' on SW1 Gi0/5.",
        "osi_layer": "2 - Data Link",
        "concept_tag": "wireless,flexconnect,trunk,vlan,dhcp,ap",
        "severity": "high",
    },
    {
        "symptom": "Wireless clients on the same SSID cannot communicate with each other; printers and file shares stopped working.",
        "topology_note": "Cisco WLC, WLAN 1 CorpWiFi, P2P blocking was enabled during a security audit.",
        "show_output": textwrap.dedent("""\
            WLC> show wlan 1
            WLAN Identifier.................................. 1
            Profile Name..................................... CORP
            P2P Blocking Action.............................. Drop

            Client A> ping Client B (both on CorpWiFi)
            Request timeout for icmp_seq 0
            (all wireless-to-wireless pings fail)"""),
        "expected_fault": "P2P Blocking is enabled on WLAN 1. Drops all unicast between wireless clients on the same SSID. Fix: WLC > WLAN > Advanced > P2P Blocking = Disabled.",
        "osi_layer": "2 - Data Link",
        "concept_tag": "wireless,p2p-blocking,wlan,client-isolation,wlc",
        "severity": "medium",
    },
    {
        "symptom": "New AP is not joining the WLC; AP console shows 'DTLS connection failed'.",
        "topology_note": "Cisco 9120AX AP, WLC 9800. CAPWAP control UDP 5246 must be open through firewall.",
        "show_output": textwrap.dedent("""\
            AP Console:
            *Aug 25 17:00:01.123: %CAPWAP-3-ERRORLOG: Did not get DTLS connection
            *Aug 25 17:00:01.456: %CAPWAP-3-ERRORLOG: Go join a capwap controller

            WLC# show ap summary
            (AP 00:AA:BB:CC:DD:EE NOT listed)

            Firewall log:
            DENY UDP 10.0.50.15:56432 -> 10.0.0.10:5246 (CAPWAP-Control)
            DENY UDP 10.0.50.15:56433 -> 10.0.0.10:5248 (CAPWAP-Data)"""),
        "expected_fault": "Firewall blocks CAPWAP control (UDP 5246) and data (UDP 5248) from AP subnet to WLC. AP cannot complete DTLS handshake. Fix: permit UDP 5246 and 5248 from AP subnets to WLC management IP.",
        "osi_layer": "4 - Transport",
        "concept_tag": "wireless,capwap,dtls,wlc,firewall,udp",
        "severity": "high",
    },
]


# =============================================================================
# CATEGORY MAPPING (auto-assign category label by index)
# =============================================================================
CATEGORY_MAP = {
    "vlan":     range(0, 5),
    "gateway":  range(5, 9),
    "dhcp":     range(9, 14),
    "dns":      range(14, 17),
    "routing":  range(17, 21),
    "acl":      range(21, 25),
    "nat":      range(25, 28),
    "wireless": range(28, 32),
}

FIELDNAMES = [
    "case_id",
    "category",
    "symptom",
    "topology_note",
    "show_output",
    "expected_fault",
    "osi_layer",
    "concept_tag",
    "severity",
]


def get_category(idx: int) -> str:
    for cat, rng in CATEGORY_MAP.items():
        if idx in rng:
            return cat
    return "other"


def write_csv(output_path: str = "cases.csv") -> bool:
    path = Path(output_path)
    if path.exists() and "--force" not in sys.argv:
        print(f"WARNING: '{output_path}' already exists. Overwriting it may destroy manual edits.")
        print(f"To force overwrite and create a backup, run: python generate_cases.py --force")
        print("Aborting file generation.")
        return False

    if path.exists() and "--force" in sys.argv:
        backup_path = path.with_suffix(".csv.bak")
        try:
            if backup_path.exists():
                backup_path.unlink()
            path.rename(backup_path)
            print(f"Backup created: '{backup_path}'")
        except Exception as e:
            print(f"Failed to create backup: {e}")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES,
            quoting=csv.QUOTE_ALL,  # ensures multi-line show_output quoted correctly
        )
        writer.writeheader()
        for idx, case in enumerate(CASES):
            row = {
                "case_id":  f"CASE-{idx + 1:03d}",
                "category": get_category(idx),
                **case,
            }
            writer.writerow(row)
    print(f"Wrote {len(CASES)} cases to '{output_path}'")
    return True



def preview_csv(path: str = "cases.csv", n: int = 5) -> None:
    """Print the first n rows in a readable format."""
    import textwrap as tw
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [row for _, row in zip(range(n), reader)]

    print(f"\n{'=' * 78}")
    print(f"  PREVIEW: first {n} rows of {path}")
    print(f"{'=' * 78}")
    for row in rows:
        print(f"\n  case_id      : {row['case_id']}")
        print(f"  category     : {row['category']}")
        print(f"  severity     : {row['severity']}")
        print(f"  osi_layer    : {row['osi_layer']}")
        print(f"  concept_tag  : {row['concept_tag']}")
        print(f"  symptom      : {tw.fill(row['symptom'], 68, subsequent_indent=' ' * 17)}")
        fault_preview = row["expected_fault"][:140] + ("..." if len(row["expected_fault"]) > 140 else "")
        print(f"  expected_fault: {tw.fill(fault_preview, 68, subsequent_indent=' ' * 17)}")
        first_show_line = row["show_output"].splitlines()[0]
        print(f"  show_output  : (first line) {first_show_line}")
        print(f"{'─' * 78}")


if __name__ == "__main__":
    if write_csv("cases.csv"):
        preview_csv("cases.csv", n=5)
        print(f"\n  Total cases  : {len(CASES)}")
        print(f"  Categories   : {', '.join(CATEGORY_MAP.keys())}")

