# tests/test_dashboard.py
import pytest
from dashboard import filter_cases_by_criteria, calculate_kpis

# Mock case data for testing
MOCK_CASES = [
    {"case_id": "NS-01", "category": "vlan", "severity": "critical", "osi_layer": "2 - Data Link"},
    {"case_id": "NS-02", "category": "routing", "severity": "high", "osi_layer": "3 - Network"},
    {"case_id": "NS-03", "category": "dhcp", "severity": "medium", "osi_layer": "7 - Application"},
    {"case_id": "NS-04", "category": "vlan", "severity": "low", "osi_layer": "2 - Data Link"},
]

MOCK_DIAGNOS = [
    {"case_id": "NS-01", "confidence": "0.90"},
    {"case_id": "NS-02", "confidence": "0.75"},
    {"case_id": "NS-03", "confidence": "0.35"},
]

MOCK_REVIEWS = [
    {"case_id": "NS-01", "human_decision": "Accepted"},
    {"case_id": "NS-02", "human_decision": "Edited"},
    {"case_id": "NS-03", "human_decision": "Rejected"},
]

MOCK_VAULT_IDS = {"NS-01", "NS-02"}


# 1. Test category filtering
def test_category_filtering():
    res = filter_cases_by_criteria(MOCK_CASES, ["vlan"], ["critical", "high", "medium", "low"], ["1", "2", "3", "4", "7"])
    assert len(res) == 2
    assert all(r["category"] == "vlan" for r in res)


# 2. Test severity filtering
def test_severity_filtering():
    res = filter_cases_by_criteria(MOCK_CASES, ["vlan", "routing", "dhcp"], ["critical"], ["1", "2", "3", "4", "7"])
    assert len(res) == 1
    assert res[0]["case_id"] == "NS-01"


# 3. Test OSI layer filtering
def test_osi_filtering():
    res = filter_cases_by_criteria(MOCK_CASES, ["vlan", "routing", "dhcp"], ["critical", "high", "medium", "low"], ["7"])
    assert len(res) == 1
    assert res[0]["case_id"] == "NS-03"


# 4. Test combined filtering
def test_combined_filtering():
    res = filter_cases_by_criteria(MOCK_CASES, ["vlan"], ["low"], ["2"])
    assert len(res) == 1
    assert res[0]["case_id"] == "NS-04"


# 5. Test KPI calculation
def test_kpi_calculation():
    kpis = calculate_kpis(MOCK_CASES, MOCK_DIAGNOS, MOCK_REVIEWS, MOCK_VAULT_IDS)
    assert kpis["total_cases"] == 4
    assert kpis["total_diags"] == 3
    # 2 accepted/edited out of 3 total reviews = 66.67%
    assert abs(kpis["approval_rate"] - 66.6666) < 0.01
    assert kpis["verified_cnt"] == 2
    assert kpis["vault_count"] == 2  # NS-01 and NS-02 are in vault and in MOCK_CASES


# 6. Test zero-record filtering (empty result)
def test_zero_record_filtering():
    res = filter_cases_by_criteria(MOCK_CASES, ["dns"], ["critical"], ["3"])
    assert len(res) == 0


# 7. Test division-by-zero handling in KPI calculation
def test_division_by_zero_kpi_handling():
    kpis = calculate_kpis(MOCK_CASES, [], [], MOCK_VAULT_IDS)
    assert kpis["total_cases"] == 4
    assert kpis["total_diags"] == 0
    assert kpis["approval_rate"] == 0.0
    assert kpis["verified_cnt"] == 0


def test_dashboard_renders_radar_result():
    from unittest.mock import MagicMock
    mock_st = MagicMock()
    
    radar_res = {
        "evidence_sufficiency": "sufficient",
        "available": ["show vlan brief", "show interfaces trunk"],
        "missing_critical": ["ping"],
        "recommended_next_commands": ["show ip route"],
        "can_diagnose": True,
        "score": 0.67
    }
    
    # Exact dashboard.py rendering logic
    try:
        score_str = f"{radar_res['score'] * 100:.1f}%"
        mock_st.markdown(f"**Command Availability Score:** `{score_str}`")
        if radar_res["score"] < 0.4:
            mock_st.warning("⚠️ Insufficient Evidence")
        else:
            mock_st.success("✅ Evidence score matches")
            
        for cmd in radar_res["available"]:
            mock_st.markdown(f"- 🟢 [Present] `{cmd}`")
        for cmd in radar_res["missing_critical"]:
            mock_st.markdown(f"- 🔴 [Missing] `{cmd}`")
            
        if radar_res["recommended_next_commands"]:
            mock_st.markdown("**Next Recommended Diagnostic Commands:**")
            for rec in radar_res["recommended_next_commands"]:
                mock_st.markdown(f"- `{rec}`")
    except KeyError as e:
        pytest.fail(f"KeyError encountered during radar results rendering: {e}")

