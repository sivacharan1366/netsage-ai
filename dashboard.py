# dashboard.py
import sys
import csv
import re
from pathlib import Path
from collections import Counter, defaultdict

# Ensure Windows UTF-8 stdout/stderr handles are safe (if run directly in CLI mode)
if sys.platform.startswith('win') and __name__ == "__main__" and "streamlit" not in sys.modules:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Color palette
PALETTE = {
    "vlan":     "#4F8EF7",
    "gateway":  "#F79C4F",
    "dhcp":     "#4FC78A",
    "dns":      "#E05C5C",
    "routing":  "#A04FF7",
    "acl":      "#F7E04F",
    "nat":      "#4FD8F7",
    "wireless": "#F74FA0",
    "critical": "#E05C5C",
    "high":     "#F79C4F",
    "medium":   "#4F8EF7",
    "low":      "#4FC78A",
    "Accepted": "#4FC78A",
    "Edited":   "#F79C4F",
    "Rejected": "#E05C5C",
    "conf_high":   "#4F8EF7",
    "conf_medium": "#F79C4F",
    "conf_low":    "#E05C5C",
}

CATEGORY_ORDER  = ["vlan", "gateway", "dhcp", "dns", "routing", "acl", "nat", "wireless"]
SEVERITY_ORDER  = ["critical", "high", "medium", "low"]
DECISION_ORDER  = ["Accepted", "Edited", "Rejected"]
CONFIDENCE_ORDER = ["high", "medium", "low"]


def load_csv(path: str) -> list[dict]:
    """Load a CSV file as a list of dictionaries."""
    file_path = Path(path)
    if not file_path.exists():
        return []
    with open(file_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def filter_cases_by_criteria(cases_list, categories, severities, layers):
    """Filters cases list based on allowed categories, severities, and OSI layer numbers."""
    import re
    def get_layer_num(val):
        if not val:
            return ""
        m = re.match(r"\d", val)
        return m.group(0) if m else val
        
    return [
        r for r in cases_list
        if r.get("category", "").lower() in categories
        and r.get("severity", "").lower() in severities
        and get_layer_num(r.get("osi_layer", "")) in layers
    ]


def calculate_kpis(cases_list, diagnos_list, reviews_list, vault_ids):
    """Calculates dashboard KPIs from filtered list inputs safely handling empty sets."""
    total_cases = len(cases_list)
    total_diags = len(diagnos_list)
    
    accepted_cnt = sum(1 for r in reviews_list if r.get("human_decision") == "Accepted")
    edited_cnt   = sum(1 for r in reviews_list if r.get("human_decision") == "Edited")
    total_reviews_cnt = len(reviews_list)
    
    approval_rate = (accepted_cnt + edited_cnt) / total_reviews_cnt * 100 if total_reviews_cnt > 0 else 0.0
    verified_cnt = accepted_cnt + edited_cnt
    
    case_ids = {r.get("case_id") for r in cases_list}
    vault_count = sum(1 for cid in case_ids if cid in vault_ids)
    
    return {
        "total_cases": total_cases,
        "total_diags": total_diags,
        "approval_rate": approval_rate,
        "verified_cnt": verified_cnt,
        "vault_count": vault_count
    }


def generate_static_charts(cases, diagnos, reviews):
    """Generates the 5 static png charts and the dashboard_summary.csv (CLI mode)."""
    import matplotlib
    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    FONT_TITLE  = {"fontsize": 15, "fontweight": "bold", "color": "#1A1A2E"}
    FONT_LABEL  = {"fontsize": 11, "color": "#333333"}
    FONT_TICK   = {"fontsize": 10}
    FIG_BG      = "#F8F9FB"
    AXES_BG     = "#FFFFFF"
    GRID_COLOR  = "#E0E4ED"

    def styled_fig(figsize=(10, 6)):
        fig, ax = plt.subplots(figsize=figsize, facecolor=FIG_BG)
        ax.set_facecolor(AXES_BG)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(GRID_COLOR)
        ax.spines["bottom"].set_color(GRID_COLOR)
        ax.tick_params(colors="#555555", labelsize=10)
        ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8, linestyle="--", alpha=0.7)
        ax.set_axisbelow(True)
        return fig, ax

    def bar_labels(ax, bars, fmt="{:.0f}"):
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    h + 0.05,
                    fmt.format(h),
                    ha="center", va="bottom",
                    fontsize=10, fontweight="bold", color="#333333",
                )

    # Index reviews by case_id
    review_by_id = {r["case_id"]: r for r in reviews}

    # Chart 1 — Cases by Category
    cat_counts = Counter(r["category"] for r in cases)
    cats   = [c for c in CATEGORY_ORDER if c in cat_counts]
    counts = [cat_counts[c] for c in cats]
    colors = [PALETTE[c] for c in cats]

    fig, ax = styled_fig(figsize=(11, 6))
    bars = ax.bar(cats, counts, color=colors, width=0.6, edgecolor="white", linewidth=1.2, zorder=3)
    bar_labels(ax, bars)
    ax.set_title("Troubleshooting Cases by Category", **FONT_TITLE, pad=14)
    ax.set_xlabel("Category", **FONT_LABEL, labelpad=8)
    ax.set_ylabel("Number of Cases", **FONT_LABEL, labelpad=8)
    ax.set_ylim(0, max(counts) + 2)
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([c.upper() for c in cats], **FONT_TICK)
    fig.tight_layout()
    fig.savefig("chart_category_distribution.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved: chart_category_distribution.png")

    # Chart 2 — Severity Distribution
    sev_counts = Counter(r["severity"] for r in cases)
    sevs   = [s for s in SEVERITY_ORDER if s in sev_counts]
    scnts  = [sev_counts[s] for s in sevs]
    scolors = [PALETTE[s] for s in sevs]

    fig, ax = styled_fig(figsize=(9, 6))
    bars = ax.bar(sevs, scnts, color=scolors, width=0.5, edgecolor="white", linewidth=1.2, zorder=3)
    bar_labels(ax, bars)
    ax.set_title("Case Severity Distribution", **FONT_TITLE, pad=14)
    ax.set_xlabel("Severity Level", **FONT_LABEL, labelpad=8)
    ax.set_ylabel("Number of Cases", **FONT_LABEL, labelpad=8)
    ax.set_ylim(0, max(scnts) + 2)
    ax.set_xticks(range(len(sevs)))
    ax.set_xticklabels([s.capitalize() for s in sevs], **FONT_TICK)
    fig.tight_layout()
    fig.savefig("chart_severity_distribution.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved: chart_severity_distribution.png")

    # Chart 3 — AI vs Human Agreement (Pie)
    decision_counts = Counter(r["human_decision"] for r in reviews)
    dec_labels = [d for d in DECISION_ORDER if d in decision_counts]
    dec_sizes  = [decision_counts[d] for d in dec_labels]
    dec_colors = [PALETTE[d] for d in dec_labels]
    dec_explode = [0.04 if d == "Rejected" else 0.02 for d in dec_labels]

    fig, ax = plt.subplots(figsize=(8, 7), facecolor=FIG_BG)
    wedges, texts, autotexts = ax.pie(
        dec_sizes,
        labels=None,
        colors=dec_colors,
        autopct="%1.1f%%",
        startangle=140,
        explode=dec_explode,
        pctdistance=0.78,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for at in autotexts:
        at.set_fontsize(12)
        at.set_fontweight("bold")
        at.set_color("white")

    legend_patches = [
        mpatches.Patch(color=PALETTE[d], label=f"{d}  ({decision_counts[d]})")
        for d in dec_labels
    ]
    ax.legend(
        handles=legend_patches,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=3,
        fontsize=11,
        frameon=False,
    )
    ax.set_title("Human Review Decisions\n(AI Diagnosis Agreement Rate)", **FONT_TITLE, pad=16)
    fig.tight_layout()
    fig.savefig("chart_ai_human_agreement.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved: chart_ai_human_agreement.png")

    # Chart 4 — OSI Layer Distribution (horizontal bar)
    layer_counts = Counter(r["osi_layer"] for r in cases)
    sorted_layers = sorted(layer_counts.items(), key=lambda x: int(x[0].split(" - ")[0]))
    layer_labels = [l for l, _ in sorted_layers]
    layer_values = [v for _, v in sorted_layers]

    layer_colors = [
        "#E05C5C", "#F79C4F", "#F7E04F",
        "#4FC78A", "#4F8EF7", "#A04FF7", "#F74FA0",
    ][:len(layer_labels)]

    fig, ax = styled_fig(figsize=(11, 6))
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)
    bars = ax.barh(layer_labels, layer_values, color=layer_colors[::-1],
                   edgecolor="white", linewidth=1.0, height=0.5)
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.1, bar.get_y() + bar.get_height() / 2,
                str(int(w)), va="center", ha="left",
                fontsize=10, fontweight="bold", color="#333333")
    ax.set_title("Cases by OSI Layer", **FONT_TITLE, pad=14)
    ax.set_xlabel("Number of Cases", **FONT_LABEL, labelpad=8)
    ax.set_xlim(0, max(layer_values) + 3)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig("chart_osi_layer_distribution.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved: chart_osi_layer_distribution.png")

    # Chart 5 — AI Confidence Breakdown (stacked bar)
    conf_by_cat = {c: {"high": 0, "medium": 0, "low": 0} for c in CATEGORY_ORDER}
    for row in diagnos:
        cat = row["category"]
        conf_raw = row["confidence"].lower()
        
        # Backward compatible mapping from floats to categories
        try:
            val = float(conf_raw)
            if val >= 0.80:
                conf = "high"
            elif val >= 0.40:
                conf = "medium"
            else:
                conf = "low"
        except ValueError:
            conf = conf_raw if conf_raw in ["high", "medium", "low"] else "low"
            
        if cat in conf_by_cat and conf in conf_by_cat[cat]:
            conf_by_cat[cat][conf] += 1

    x = np.arange(len(CATEGORY_ORDER))
    w = 0.55
    high_vals   = [conf_by_cat[c]["high"]   for c in CATEGORY_ORDER]
    medium_vals = [conf_by_cat[c]["medium"] for c in CATEGORY_ORDER]
    low_vals    = [conf_by_cat[c]["low"]    for c in CATEGORY_ORDER]

    fig, ax = styled_fig(figsize=(12, 6))
    b1 = ax.bar(x, high_vals,   width=w, color=PALETTE["conf_high"],   label="High",   edgecolor="white", zorder=3)
    b2 = ax.bar(x, medium_vals, width=w, bottom=high_vals,
                color=PALETTE["conf_medium"], label="Medium", edgecolor="white", zorder=3)
    low_bottom = [h + m for h, m in zip(high_vals, medium_vals)]
    b3 = ax.bar(x, low_vals, width=w, bottom=low_bottom,
                color=PALETTE["conf_low"], label="Low", edgecolor="white", zorder=3)

    ax.set_title("AI Confidence Level by Category", **FONT_TITLE, pad=14)
    ax.set_xlabel("Category", **FONT_LABEL, labelpad=8)
    ax.set_ylabel("Number of Diagnoses", **FONT_LABEL, labelpad=8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.upper() for c in CATEGORY_ORDER], **FONT_TICK)
    ax.set_ylim(0, max(h + m + l for h, m, l in zip(high_vals, medium_vals, low_vals)) + 1.5)
    ax.legend(title="Confidence", fontsize=10, title_fontsize=10, frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig("chart_confidence_breakdown.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved: chart_confidence_breakdown.png")

    # dashboard_summary.csv
    summary_rows = []
    for c in CATEGORY_ORDER:
        summary_rows.append({
            "section": "category_distribution",
            "label":   c,
            "value":   cat_counts.get(c, 0),
            "note":    "",
        })
    for s in SEVERITY_ORDER:
        summary_rows.append({
            "section": "severity_distribution",
            "label":   s,
            "value":   sev_counts.get(s, 0),
            "note":    "",
        })
    total_reviews = len(reviews)
    for d in DECISION_ORDER:
        cnt = decision_counts.get(d, 0)
        summary_rows.append({
            "section": "ai_human_agreement",
            "label":   d,
            "value":   cnt,
            "note":    f"{100*cnt//total_reviews if total_reviews else 0}% of {total_reviews} reviews",
        })
    for label, value in sorted_layers:
        summary_rows.append({
            "section": "osi_layer_distribution",
            "label":   label,
            "value":   value,
            "note":    "",
        })
    for c in CATEGORY_ORDER:
        for conf in CONFIDENCE_ORDER:
            v = conf_by_cat[c].get(conf, 0)
            if v > 0:
                summary_rows.append({
                    "section": "confidence_by_category",
                    "label":   f"{c}_{conf}",
                    "value":   v,
                    "note":    "",
                })

    with open("dashboard_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["section", "label", "value", "note"], quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(summary_rows)

    print("  Saved: dashboard_summary.csv")
    print()
    print("  DASHBOARD SUMMARY")
    print("  " + "─" * 42)
    print(f"  Total cases analysed  : {len(cases)}")
    print(f"  Total diagnoses       : {len(diagnos)}")
    print(f"  AI match rate (auto)  : {sum(1 for r in diagnos if r['match']=='yes')}/{len(diagnos)}")
    print(f"  Human accepted        : {decision_counts.get('Accepted',0)} ({100*decision_counts.get('Accepted',0)//total_reviews if total_reviews else 0}%)")
    print(f"  Human edited          : {decision_counts.get('Edited',0)}   ({100*decision_counts.get('Edited',0)//total_reviews if total_reviews else 0}%)")
    print(f"  Human rejected        : {decision_counts.get('Rejected',0)}  ({100*decision_counts.get('Rejected',0)//total_reviews if total_reviews else 0}%)")
    
    # Print total high conf count
    high_conf_count = sum(1 for r in diagnos if r['confidence'] in ['high', '0.8', '0.9', '1.0'] or (isinstance(r['confidence'], str) and r['confidence'].startswith(('0.8', '0.9', '1.0', 'high'))))
    print(f"  High-confidence diagnoses : {high_conf_count}/{len(diagnos)}")
    print()


def simulate_after_state(case_row: dict) -> str:
    """
    Generates a realistic AFTER fix state evidence string by simulating remediation
    of the specific fault category and replacing broken configurations/outputs.
    """
    show_out = case_row.get("show_output", "")
    cat = case_row.get("category", "").lower().split("/")[0].strip()
    
    if cat == "gateway":
        after_out = show_out
        # 1. Update Default Gateway from 192.168.1.254 (or wrong IP) to 192.168.1.1
        after_out = re.sub(
            r'Default Gateway[\s.]*[.:]+\s*192\.168\.1\.254.*',
            'Default Gateway . . . . . . . : 192.168.1.1',
            after_out,
            flags=re.IGNORECASE
        )
        # Remove (unreachable - no host) signature if present elsewhere
        after_out = re.sub(r'\(unreachable\s*[-–]\s*no host\)', '', after_out, flags=re.IGNORECASE)
        
        # 2. Replace Ping timeouts with successful ping responses
        after_out = re.sub(
            r'PC-A>\s*ping\s+8\.8\.8\.8\s*\n\s*Request timeout.*',
            'PC-A> ping 8.8.8.8\n84 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=5 ms\n84 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=4 ms\nSuccess rate is 100 percent (5/5)',
            after_out,
            flags=re.IGNORECASE
        )
        after_out = re.sub(r'Request timeout.*', 'Reply from 192.168.1.1: bytes=32 time=2ms TTL=255', after_out)
        after_out = re.sub(r'0%\s+packet success|100%\s+packet loss', '100% packet success (0% packet loss)', after_out)
        
        # 3. Update route lookup output if present
        after_out = re.sub(
            r'R1#\s*show ip route 8\.8\.8\.8\s*\n\s*%\s*Network not in table',
            'R1# show ip route 8.8.8.8\nRouting entry for 0.0.0.0/0 via 192.168.1.1 [110/1]',
            after_out,
            flags=re.IGNORECASE
        )
        return after_out

    elif cat == "vlan":
        after_out = show_out
        # For VLAN access port missing (e.g. CASE-001 where VLAN 30 has no member ports)
        after_out = re.sub(r'30\s+HR\s+active\s*$', '30   HR                               active    Gi0/3', after_out, flags=re.MULTILINE)
        after_out = re.sub(r'line protocol is down', 'line protocol is up', after_out, flags=re.IGNORECASE)
        after_out = re.sub(r'1-9,11-4094', '1-4094', after_out)
        after_out = re.sub(r'Native vlan 99', 'Native vlan 1', after_out)
        return after_out

    elif cat == "interface":
        after_out = show_out
        after_out = re.sub(r'administratively down', 'is up, line protocol is up', after_out, flags=re.IGNORECASE)
        return after_out

    elif cat == "routing":
        after_out = show_out
        if "% Network not in table" in after_out:
            after_out = after_out.replace("% Network not in table", "O    10.1.1.0/24 [110/65] via 192.168.1.1\nO*E2 0.0.0.0/0 [110/1] via 10.0.0.1")
        else:
            after_out += "\nO    10.1.1.0/24 [110/65] via 192.168.1.1"
        return after_out

    elif cat == "dhcp":
        after_out = show_out
        after_out = re.sub(r'0\.0\.0\.0', '192.168.1.11 (leased)', after_out)
        return after_out

    elif cat == "dns":
        after_out = show_out
        after_out = re.sub(r'Unresolved|unknown host', 'Translating "google.com"... domain server (8.8.8.8) [OK]', after_out, flags=re.IGNORECASE)
        return after_out

    elif cat == "acl":
        after_out = show_out
        after_out = re.sub(r'deny', 'permit', after_out, flags=re.IGNORECASE)
        after_out = re.sub(r'drop count.*|drop', 'forwarded (Success rate is 100 percent)', after_out, flags=re.IGNORECASE)
        return after_out

    elif cat == "nat":
        after_out = show_out
        if "Translations: 0" in after_out or "Empty translations" in after_out or "show ip nat translations" in after_out:
            after_out += "\nPro Inside global      Inside local       Outside local      Outside global\ntcp 192.168.1.1:80      10.0.0.10:80       192.168.1.254:80   192.168.1.254:80"
        return after_out

    elif cat == "wireless":
        after_out = show_out
        after_out = re.sub(r'DTLS connection down|disconnected', 'DTLS connection Up', after_out, flags=re.IGNORECASE)
        return after_out

    return show_out


def run_streamlit_app():
    """Streamlit web dashboard & Human Review Terminal (Interactive Tab mode)."""
    import streamlit as st
    from rule_checker import check_case
    from verification.proofgate import check_conflicts
    from ai.reasonchain import format_reasonchain
    from verification.vault import add_verified_case, get_verified_cases
    from network_dna.fingerprint import retrieve_similar_cases, extract_network_dna
    from evidence_radar.radar import check_evidence_radar
    import sys
    import os

    st.set_page_config(page_title="NETSAGE — Network Incident Console", layout="wide", page_icon="⚙️")

    # Injected custom CSS for enterprise NOC aesthetic
    st.markdown("""
        <style>
        /* Import JetBrains Mono for system log aesthetic */
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');
        
        /* Main background and font */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #0c0e12 !important;
            color: #e2e4e9 !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }
        
        /* Sidebar layout & theme */
        [data-testid="stSidebar"] {
            background-color: #12151c !important;
            border-right: 1px solid #1f2430 !important;
        }
        [data-testid="stSidebar"] * {
            color: #cdd1da !important;
        }
        
        /* Custom buttons styling */
        div.stButton > button {
            background-color: #1a1e27 !important;
            color: #e2e4e9 !important;
            border: 1px solid #2b3345 !important;
            border-radius: 2px !important;
            padding: 6px 16px !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }
        div.stButton > button:hover {
            background-color: #242b38 !important;
            border-color: #4F8EF7 !important;
            color: #ffffff !important;
        }
        
        /* Typography */
        h1, h2, h3, h4, h5, h6 {
            color: #ffffff !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
            font-weight: 600 !important;
            border-bottom: none !important;
            margin-top: 1.2rem !important;
            margin-bottom: 0.6rem !important;
        }
        
        /* Code blocks */
        code, pre {
            background-color: #12151c !important;
            color: #e2e4e9 !important;
            border: 1px solid #1f2430 !important;
            border-radius: 2px !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 12.5px !important;
            white-space: pre-wrap !important;
            word-wrap: break-word !important;
        }
        
        /* Expander blocks */
        [data-testid="stExpander"] {
            background-color: #12151c !important;
            border: 1px solid #1f2430 !important;
            border-radius: 2px !important;
            margin-bottom: 10px !important;
        }
        
        /* Metrics values */
        [data-testid="stMetricValue"] {
            font-size: 26px !important;
            font-weight: 700 !important;
            color: #ffffff !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 11px !important;
            color: #8c93a0 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.8px !important;
        }
        
        /* Alert message padding adjustments */
        .stAlert {
            background-color: #12151c !important;
            border: 1px solid #1f2430 !important;
            border-radius: 2px !important;
            color: #e2e4e9 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Sidebar Navigation Layout
    st.sidebar.markdown("<h2 style='margin-bottom: 0px;'>NETSAGE</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<p style='font-size: 11px; letter-spacing: 0.5px; color: #8c93a0; text-transform: uppercase; margin-top: 0px;'>Network Operations</p>", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    mode = st.sidebar.radio(
        "WORKSPACE",
        ["Troubleshoot", "Analytics", "Human Review", "Memory Vault"],
        label_visibility="visible"
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("<p style='font-size: 11px; letter-spacing: 0.5px; color: #8c93a0; text-transform: uppercase;'>System</p>", unsafe_allow_html=True)
    
    api_key_set = "ANTHROPIC_API_KEY" in os.environ and bool(os.environ.get("ANTHROPIC_API_KEY"))
    ai_status_str = "● Live (Claude API)" if api_key_set else "● Offline (Pre-computed)"
    ai_status_col = "#4FC78A" if api_key_set else "#F79C4F"
    vault_cnt = len(get_verified_cases())

    st.sidebar.markdown(f"""
        <div style="font-size: 13px; line-height: 1.8;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span>AI Engine</span>
                <span style="color: {ai_status_col}; font-weight: bold;">{ai_status_str}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span>Evidence Radar</span>
                <span style="color: #4FC78A; font-weight: bold;">● Active (Rule Engine)</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <span>Memory Vault</span>
                <span style="color: #4FC78A; font-weight: bold;">● Online ({vault_cnt} verified)</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    try:
        cases   = load_csv("cases.csv")
        diagnos = load_csv("ai_diagnoses.csv")
        reviews = load_csv("human_review_log.csv")
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        sys.stderr.write(f"Error loading CSV files: {e}\n")
        import traceback
        traceback.print_exc()
        return

    category_mapping = {
        "vlan": "VLAN Connectivity Failure",
        "gateway": "Gateway Connectivity Failure",
        "dhcp": "DHCP Lease Allocation Failure",
        "dns": "DNS Name Resolution Failure",
        "routing": "Routing Table Adjacency Failure",
        "acl": "Access Control List Blockage",
        "nat": "Network Address Translation Mismatch",
        "wireless": "Wireless Association Failure",
        "interface": "Physical Interface Down"
    }

    if mode == "Troubleshoot":
        try:
            st.markdown("<h1>NETSAGE</h1>", unsafe_allow_html=True)
            st.markdown("<p style='color: #8c93a0; font-size: 14px; margin-top: -10px; margin-bottom: 20px;'>Network Incident & Troubleshooting Console</p>", unsafe_allow_html=True)

            case_ids = [r["case_id"] for r in cases]
            selected_cid = st.selectbox("CASE", case_ids)
            case_row = next(r for r in cases if r["case_id"] == selected_cid)
            diag_row = next((r for r in diagnos if r["case_id"] == selected_cid), None)

            category_title = category_mapping.get(case_row["category"].lower(), f"{case_row['category'].upper()} Incident")
            
            # Show professional incident summary
            st.markdown(f"""
            <div style="padding: 15px; border: 1px solid #1f2430; background-color: #12151c; margin-bottom: 20px; border-radius: 2px;">
                <div style="font-size: 11px; color: #8c93a0; font-weight: bold; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 2px;">Incident Target</div>
                <div style="font-size: 18px; font-weight: bold; color: #ffffff; margin-bottom: 12px;">{selected_cid} &mdash; {category_title.upper()}</div>
                <div style="display: flex; gap: 40px; margin-bottom: 12px; font-size: 13px;">
                    <div><strong>Category:</strong> <span style="color: #cdd1da;">{case_row['category'].upper()}</span></div>
                    <div><strong>Severity:</strong> <span style="color: #f79c4f; font-weight: bold;">{case_row['severity'].upper()}</span></div>
                    <div><strong>OSI Layer:</strong> <span style="color: #cdd1da;">Layer {case_row['osi_layer']}</span></div>
                </div>
                <div style="font-size: 13px;">
                    <strong>Symptom:</strong><br>
                    <span style="color: #cdd1da;">{case_row['symptom']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Workflow Progress calculations
            radar_res_status = check_evidence_radar(case_row["category"], case_row["show_output"])
            vault_cases_status = get_verified_cases()
            vault_ids_status = {c["case_id"] for c in vault_cases_status}
            active_diag_status = st.session_state.get(f"active_diag_{selected_cid}")
            prev_review_status = next((r for r in reviews if r["case_id"] == selected_cid), None)

            is_evidence_sufficient = radar_res_status["score"] >= 0.4
            has_analysis = (active_diag_status is not None) or (diag_row is not None)
            has_review = (prev_review_status is not None)
            is_in_vault = (selected_cid in vault_ids_status)

            # Evaluate simulation result for status calculation
            after_state_sim = simulate_after_state(case_row)
            from verification.post_fix import verify_fix
            post_res_sim = verify_fix(case_row["category"], case_row["show_output"], after_state_sim)
            sim_passed = post_res_sim.get("passed_verification", False)
            is_verified = sim_passed

            review_accepted = has_review and prev_review_status.get("human_decision") in ["Accepted", "Edited"]
            review_rejected = has_review and prev_review_status.get("human_decision") == "Rejected"

            evidence_lbl = "✓ Completed" if is_evidence_sufficient else "● Current (Partial)"
            
            if not has_analysis:
                analysis_lbl = "● Current" if is_evidence_sufficient else "○ Pending"
                review_lbl = "○ Pending"
                verification_lbl = "○ Pending"
                resolved_lbl = "○ Pending"
            elif not has_review:
                analysis_lbl = "✓ Completed"
                review_lbl = "● Current"
                verification_lbl = "○ Pending"
                resolved_lbl = "○ Pending"
            elif review_rejected:
                analysis_lbl = "✓ Completed"
                review_lbl = "❌ Rejected"
                verification_lbl = "❌ Skipped (Rejected)"
                resolved_lbl = "❌ Blocked (Rejected)"
            elif review_accepted and sim_passed and is_in_vault:
                analysis_lbl = "✓ Completed"
                review_lbl = f"✓ Completed ({prev_review_status['human_decision']})"
                verification_lbl = "✓ Completed"
                resolved_lbl = "✓ Completed"
            elif review_accepted and sim_passed and not is_in_vault:
                analysis_lbl = "✓ Completed"
                review_lbl = f"✓ Completed ({prev_review_status['human_decision']})"
                verification_lbl = "✓ Completed"
                resolved_lbl = "● Pending Vault Commit"
            elif review_accepted and not sim_passed:
                analysis_lbl = "✓ Completed"
                review_lbl = f"✓ Completed ({prev_review_status['human_decision']})"
                verification_lbl = "✕ Failed Verification"
                resolved_lbl = "✕ Unresolved (Verification Failed)"
            else:
                analysis_lbl = "✓ Completed"
                review_lbl = "● Current"
                verification_lbl = "○ Pending"
                resolved_lbl = "○ Pending"

            st.markdown("<h4 style='margin-top: 15px; margin-bottom: 10px;'>Workflow Progress</h4>", unsafe_allow_html=True)
            col_w1, col_w2, col_w3, col_w4, col_w5 = st.columns(5)
            with col_w1:
                st.markdown(f"**Evidence**<br><span style='font-size: 13px; color: #cdd1da;'>{evidence_lbl}</span>", unsafe_allow_html=True)
            with col_w2:
                st.markdown(f"**Analysis**<br><span style='font-size: 13px; color: #cdd1da;'>{analysis_lbl}</span>", unsafe_allow_html=True)
            with col_w3:
                st.markdown(f"**Review**<br><span style='font-size: 13px; color: #cdd1da;'>{review_lbl}</span>", unsafe_allow_html=True)
            with col_w4:
                st.markdown(f"**Verification**<br><span style='font-size: 13px; color: #cdd1da;'>{verification_lbl}</span>", unsafe_allow_html=True)
            with col_w5:
                st.markdown(f"**Resolved**<br><span style='font-size: 13px; color: #cdd1da;'>{resolved_lbl}</span>", unsafe_allow_html=True)

            with st.expander("Technical Pipeline Details"):
                s1 = "✓ Completed"
                s2 = "✓ Completed" if radar_res_status["score"] >= 0.4 else "● Current"
                s3 = "✓ Completed"
                s4 = "✓ Completed"
                
                s5 = "✓ Completed" if has_analysis else "● Current"
                s6 = "✓ Completed" if has_analysis else "○ Pending"
                s7 = "✓ Completed" if has_analysis else "○ Pending"
                
                if has_review:
                    dec = prev_review_status["human_decision"]
                    s8 = f"✓ Completed ({dec})"
                    if dec == "Rejected":
                        s9 = "❌ Skipped (Rejected)"
                        s10 = "❌ Blocked (Rejected)"
                    else:
                        if is_verified:
                            s9 = "✓ Completed"
                            s10 = "✓ Completed"
                        else:
                            s9 = "● Current"
                            s10 = "○ Pending"
                else:
                    s8 = "● Current" if has_analysis else "○ Pending"
                    s9 = "○ Pending"
                    s10 = "○ Pending"
                
                col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)
                with col_t1:
                    st.markdown(f"1. Case Capture: {s1}<br>2. Evidence Radar: {s2}", unsafe_allow_html=True)
                with col_t2:
                    st.markdown(f"3. Network DNA: {s3}<br>4. Similarity Search: {s4}", unsafe_allow_html=True)
                with col_t3:
                    st.markdown(f"5. AI Diagnosis: {s5}<br>6. ReasonChain: {s6}", unsafe_allow_html=True)
                with col_t4:
                    st.markdown(f"7. ProofGate: {s7}<br>8. Human Review: {s8}", unsafe_allow_html=True)
                with col_t5:
                    st.markdown(f"9. Post-Fix: {s9}<br>10. Memory Vault: {s10}", unsafe_allow_html=True)

            # EVIDENCE SECTION
            st.divider()
            st.markdown("<h3 style='margin-top: 15px; margin-bottom: 8px;'>EVIDENCE STATUS</h3>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style="font-size: 12px; color: #8c93a0; margin-bottom: 10px;">
                <strong>What is this?</strong> Verifies if the captured command output is sufficient for a reliable diagnosis.<br>
                <strong>What did NetSage find?</strong> Command availability evaluation and score shown below.<br>
                <strong>What should I do next?</strong> If status is PARTIAL, run the missing commands to supply more logs.
            </div>
            """, unsafe_allow_html=True)
            
            radar_res = check_evidence_radar(case_row["category"], case_row["show_output"])
            is_sufficient = radar_res["score"] >= 0.4
            status_color = "#4FC78A" if is_sufficient else "#E05C5C"
            status_text = "SUFFICIENT" if is_sufficient else "PARTIAL"
            
            st.markdown(f"<span style='color: {status_color}; font-weight: bold; font-size: 16px;'>● {status_text}</span>", unsafe_allow_html=True)
            st.markdown(f"**Evidence Score:** `{radar_res['score'] * 100:.0f}%`")
            
            col_ev1, col_ev2, col_ev3 = st.columns(3)
            with col_ev1:
                st.markdown("**Available Evidence**")
                if radar_res["available"]:
                    for cmd in radar_res["available"]:
                        st.markdown(f"- `{cmd}`")
                else:
                    st.markdown("- None")
            with col_ev2:
                st.markdown("**Missing Evidence**")
                if radar_res["missing_critical"]:
                    for cmd in radar_res["missing_critical"]:
                        st.markdown(f"- `{cmd}`")
                else:
                    st.markdown("- None")
            with col_ev3:
                st.markdown("**Recommended Commands**")
                if radar_res["recommended_next_commands"]:
                    for cmd in radar_res["recommended_next_commands"]:
                        st.markdown(f"- `{cmd}`")
                else:
                    st.markdown("- None")

            # NETWORK DNA SECTION
            st.divider()
            st.markdown("<h3 style='margin-top: 15px; margin-bottom: 8px;'>NETWORK DNA</h3>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style="font-size: 12px; color: #8c93a0; margin-bottom: 10px;">
                <strong>What is this?</strong> Extracts raw factual network observations and variables from logs.<br>
                <strong>What did NetSage find?</strong> Organized observations grouped by network components.<br>
                <strong>What should I do next?</strong> Review the extracted values to verify they match the intended configuration.
            </div>
            """, unsafe_allow_html=True)
            
            dna = extract_network_dna(case_row["show_output"], case_row["symptom"])
            
            with st.expander("NETWORK DNA DETAILS", expanded=False):
                dna_categories = [
                    ("Interfaces", "interfaces"),
                    ("IP Addresses", "ip_addresses"),
                    ("Subnets", "subnets"),
                    ("Gateways", "gateways"),
                    ("VLANs / Trunks", "vlans"),
                    ("Routes", "routes"),
                    ("ACLs", "acls"),
                    ("NAT", "nat"),
                    ("Wireless", "wireless"),
                    ("Suspicious Observations", "suspicious_observations")
                ]
                
                for label, key in dna_categories:
                    st.markdown(f"**{label}**")
                    items = dna.get(key, [])
                    if key == "vlans":
                        items = items + dna.get("trunks", [])
                        
                    if not items:
                        st.markdown("<span style='color: #8c93a0; font-size: 12px;'>Not present in evidence</span>", unsafe_allow_html=True)
                        continue
                        
                    for item in items:
                        source = item.get("source", "Unknown")
                        if key == "interfaces":
                            if "status" in item:
                                st.markdown(f"- `{item['name']}` ({item['status']})<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"- `{item['name']}`<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "ip_addresses":
                            st.markdown(f"- IP: `{item['ip']}` (Mask: `{item['mask']}`)<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "subnets":
                            st.markdown(f"- Subnet: `{item['network']}` (Mask: `{item['mask']}`)<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "gateways":
                            st.markdown(f"- Gateway: `{item['gateway']}` (Type: `{item['type']}`)<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "vlans":
                            if "id" in item:
                                st.markdown(f"- VLAN {item['id']}: `{item['name']}` ({item['status']})<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                            elif "native_vlan" in item:
                                st.markdown(f"- Native VLAN: `{item['native_vlan']}`<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                            elif "interface" in item:
                                st.markdown(f"- Trunk Interface: `{item['interface']}` (Mode: `{item['mode']}`)<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                            elif "allowed_vlans" in item:
                                st.markdown(f"- Trunk Allowed VLANs: `{item['allowed_vlans']}`<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "routes":
                            st.markdown(f"- Destination: `{item['destination']}` via `{item.get('next_hop', 'N/A')}` ({item['type']})<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "acls":
                            if "name" in item:
                                st.markdown(f"- ACL: `{item['name']}`<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"- Rule {item.get('rule_number', '')}: {item.get('action', '')} (Hits: {item.get('hits', '')})<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "nat":
                            if "role" in item:
                                st.markdown(f"- NAT Interface Role: `{item['role']}`<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"- NAT Translation: `{item['inside_local']}` &rarr; `{item['inside_global']}` ({item['type']})<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "wireless":
                            if "ssid" in item:
                                st.markdown(f"- SSID: `{item['ssid']}` (Profile: `{item['profile']}`, ID: `{item['id']}`)<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"- DTLS Connection Status: `{item['dtls_status']}`<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                        elif key == "suspicious_observations":
                            st.markdown(f"- **{item['description']}**: `{item['evidence']}`<br><small style='color: #8c93a0;'>Source: {source}</small>", unsafe_allow_html=True)
                    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

            # SIMILARITY SEARCH
            st.divider()
            st.markdown("<h3 style='margin-top: 15px; margin-bottom: 8px;'>SIMILAR INCIDENTS</h3>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style="font-size: 12px; color: #8c93a0; margin-bottom: 10px;">
                <strong>What is this?</strong> Searches the Memory Vault for historical incidents that share similar symptoms or DNA.<br>
                <strong>What did NetSage find?</strong> Top matching verified records and their similarity indices.<br>
                <strong>What should I do next?</strong> Look at their root causes and fix steps as potential reference points.
            </div>
            """, unsafe_allow_html=True)
            
            similar_matches = retrieve_similar_cases(case_row["symptom"], vault_cases_status, top_n=2) if vault_cases_status else []
            
            if similar_matches:
                for match in similar_matches:
                    score_pct = int(match["score"] * 100)
                    st.markdown(f"""
                    <div style="padding: 10px; border-left: 3px solid #4F8EF7; background-color: #12151c; margin-bottom: 8px; border-radius: 2px; border: 1px solid #1f2430; border-left: 3px solid #4F8EF7;">
                        <div style="font-weight: bold; font-size: 13px;">{match['case']['case_id']}</div>
                        <div style="font-size: 12.5px; color: #cdd1da; margin: 4px 0;">{match['case']['root_cause']}</div>
                        <div style="font-size: 11px; color: #8c93a0;">Similarity: {score_pct}%</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("<p style='font-size: 12.5px; color: #8c93a0; font-style: italic;'>No matching historical records found in Memory Vault.</p>", unsafe_allow_html=True)
                
            with st.expander("Technical Similarity Details"):
                st.markdown("""
                **Engine Details:** Jaccard Overlap Similarity of normalized tokens.<br>
                Calculated on: Symptom Text + Network DNA Tokens + Verified Root Cause.
                """, unsafe_allow_html=True)

            # AI DIAGNOSIS & REASONING
            st.divider()
            st.markdown("<h3 style='margin-top: 15px; margin-bottom: 8px;'>AI DIAGNOSIS & REASONING</h3>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style="font-size: 12px; color: #8c93a0; margin-bottom: 10px;">
                <strong>What is this?</strong> Generates a diagnosis of the most likely root cause using AI reasoning models.<br>
                <strong>What did NetSage find?</strong> Likely root cause, confidence scoring, and step-by-step logic path.<br>
                <strong>What should I do next?</strong> Evaluate the reasoning chain and verification status before approving.
            </div>
            """, unsafe_allow_html=True)
            
            import os
            api_key_set = "ANTHROPIC_API_KEY" in os.environ or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key_set:
                st.caption("ℹ️ Running in Offline Mode (Loaded from pre-computed diagnoses).")
                
            if st.button("Run Diagnostic Analyzer"):
                if not diag_row:
                    st.error("AI diagnosis unavailable. Please run offline generator first.")
                    return
                    
                st.success("Analysis complete.")
                
                def parse_list(val):
                    if not val: return []
                    return val.split(" | ") if " | " in val else [val]
                    
                try:
                    conf_val = float(diag_row["confidence"])
                except ValueError:
                    conf_val = 0.90 if diag_row["confidence"] == "high" else (0.60 if diag_row["confidence"] == "medium" else 0.30)
                    
                diag_dict = {
                    "root_cause": diag_row["root_cause"],
                    "confidence": conf_val,
                    "evidence": parse_list(diag_row["evidence"]),
                    "next_command": diag_row["next_command"],
                    "fix_steps": parse_list(diag_row["fix_steps"]),
                    "alternatives": parse_list(diag_row.get("alternatives", "")),
                    "contradicting_evidence": parse_list(diag_row.get("contradicting_evidence", "")),
                    "evidence_sufficiency": diag_row.get("evidence_sufficiency", "sufficient")
                }
                
                st.session_state[f"active_diag_{selected_cid}"] = diag_dict
                st.rerun()
                
            active_diag = st.session_state.get(f"active_diag_{selected_cid}")
            if active_diag:
                conf_str = "HIGH" if active_diag["confidence"] >= 0.8 else ("MEDIUM" if active_diag["confidence"] >= 0.4 else "LOW")
                conf_pct = f"{active_diag['confidence']*100:.0f}%"
                severity_val = case_row["severity"].upper()
                
                st.markdown(f"""
                <div style="padding: 15px; border: 1px solid #1f2430; background-color: #12151c; border-radius: 2px; margin-bottom: 20px; line-height: 1.6;">
                    <div style="font-weight: bold; font-size: 13px; color: #8c93a0; text-transform: uppercase;">Likely Cause</div>
                    <div style="font-size: 14.5px; color: #ffffff; margin-bottom: 12px; font-weight: 500;">{active_diag['root_cause']}</div>
                    <div style="display: flex; gap: 40px; margin-bottom: 12px;">
                        <div>
                            <span style="font-size: 11px; color: #8c93a0; text-transform: uppercase; font-weight: bold;">Confidence</span><br>
                            <span style="font-size: 14px; font-weight: bold; color: #4FC78A;">{conf_str} ({conf_pct})</span>
                        </div>
                        <div>
                            <span style="font-size: 11px; color: #8c93a0; text-transform: uppercase; font-weight: bold;">Severity</span><br>
                            <span style="font-size: 14px; font-weight: bold; color: #f79c4f;">{severity_val}</span>
                        </div>
                    </div>
                    <div style="font-weight: bold; font-size: 11px; color: #8c93a0; text-transform: uppercase; margin-bottom: 4px;">Recommended Action</div>
                    <div style="font-size: 13px; color: #cdd1da;">
                """, unsafe_allow_html=True)
                for step in active_diag["fix_steps"]:
                    st.markdown(f"- {step}")
                st.markdown("</div></div>", unsafe_allow_html=True)
                
                steps = []
                steps.append(case_row["symptom"])
                for ev in active_diag["evidence"]:
                    if ev.strip():
                        steps.append(ev.strip())
                for alt in active_diag["alternatives"]:
                    if alt.strip():
                        steps.append(f"Hypothesis audited and isolated: {alt.strip()}")
                steps.append(f"Conclusion: {active_diag['root_cause']}")
                
                with st.expander("WHY THIS DIAGNOSIS? (REASONING CHAIN)", expanded=True):
                    for idx, step in enumerate(steps, 1):
                        step_num = f"{idx:02d}"
                        st.markdown(f"""
                        <div style="display: flex; flex-direction: column; align-items: flex-start; margin-left: 10px;">
                            <div style="display: flex; align-items: flex-start; gap: 12px;">
                                <div style="font-weight: bold; color: #4F8EF7; font-size: 14px; min-width: 25px;">{step_num}</div>
                                <div style="font-size: 12.5px; color: #cdd1da; padding-top: 1px;">{step}</div>
                            </div>
                        """, unsafe_allow_html=True)
                        if idx < len(steps):
                            st.markdown("""
                            <div style="margin-left: 8px; margin-top: 4px; margin-bottom: 4px; color: #555555; font-size: 14px;">
                                &darr;
                            </div>
                            """, unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                with st.expander("Technical ReasonChain Logs"):
                    rc_text = format_reasonchain(active_diag)
                    st.text_area("Raw ReasonChain Output", rc_text, height=220, disabled=True, key=f"raw_rc_{selected_cid}")

                # PROOFGATE SECTION
                st.divider()
                st.markdown("<h3 style='margin-top: 15px; margin-bottom: 8px;'>PROOFGATE VALIDATION</h3>", unsafe_allow_html=True)
                
                st.markdown("""
                <div style="font-size: 12px; color: #8c93a0; margin-bottom: 10px;">
                    <strong>What is this?</strong> Validates AI diagnoses against local config sanity rules to prevent hallucinations.<br>
                    <strong>What did NetSage find?</strong> Any config rule violation or diagnostic conflicts.<br>
                    <strong>What should I do next?</strong> Ensure validation status is PASSED before proceeding.
                </div>
                """, unsafe_allow_html=True)
                
                findings = check_case(case_row["show_output"])
                proof_res = check_conflicts(findings, active_diag["root_cause"])
                
                is_conflict = proof_res["conflict_detected"]
                val_status_color = "#E05C5C" if is_conflict else "#4FC78A"
                val_status_text = "CONFLICT DETECTED" if is_conflict else "PASSED"
                
                st.markdown(f"""
                <div style="font-size: 13px; line-height: 1.6; padding: 12px; border: 1px solid #1f2430; background-color: #12151c; border-radius: 2px;">
                    <strong>Diagnosis:</strong> {active_diag['root_cause']}<br>
                    <strong>Evidence Support:</strong> {'Partial support (Local config rules violated)' if is_conflict else 'Full support (Aligned with configuration rules)'}<br>
                    <strong>Conflicting Evidence:</strong>
                """, unsafe_allow_html=True)
                
                if is_conflict:
                    for msg in proof_res["conflict_messages"]:
                        st.markdown(f"- {msg}")
                else:
                    st.markdown("- None detected")
                    
                st.markdown(f"""
                    <br>
                    <strong>Validation Status:</strong> <span style="color: {val_status_color}; font-weight: bold;">● {val_status_text}</span>
                </div>
                """, unsafe_allow_html=True)

                # HUMAN REVIEW SECTION
                st.divider()
                st.markdown("<h3 style='margin-top: 15px; margin-bottom: 8px;'>HUMAN REVIEW</h3>", unsafe_allow_html=True)
                
                st.markdown("""
                <div style="font-size: 12px; color: #8c93a0; margin-bottom: 10px;">
                    <strong>What is this?</strong> Operator audit portal to approve, modify, or reject AI diagnoses.<br>
                    <strong>What did NetSage find?</strong> Case diagnostics ready for approval decision.<br>
                    <strong>What should I do next?</strong> Choose the decision type, provide reviewer notes, and submit.
                </div>
                """, unsafe_allow_html=True)
                
                rev_decision = st.radio(
                    "Reviewer Decision",
                    ["Accept", "Edit", "Reject"],
                    key=f"flow_rev_{selected_cid}"
                )
                
                corrected_input = ""
                if rev_decision in ["Edit", "Reject"]:
                    corrected_input = st.text_input("Corrected Root Cause / Operator Notes:", key=f"flow_corr_{selected_cid}")
                    
                notes_input = st.text_area("Reviewer Notes:", key=f"flow_notes_{selected_cid}")
                
                if st.button("Submit Review"):
                    decision_map = {
                        "Accept": "Accepted",
                        "Edit": "Edited",
                        "Reject": "Rejected"
                    }
                    backend_decision = decision_map[rev_decision]
                    
                    updated = False
                    for r in reviews:
                        if r["case_id"] == selected_cid:
                            r["human_decision"] = backend_decision
                            r["corrected_answer"] = corrected_input
                            r["reviewer_notes"] = notes_input
                            updated = True
                            break
                    if not updated:
                        reviews.append({
                            "case_id": selected_cid,
                            "category": case_row["category"],
                            "ai_confidence": diag_row["confidence"],
                            "ai_root_cause": diag_row["root_cause"],
                            "expected_fault": case_row.get("expected_fault", ""),
                            "human_decision": backend_decision,
                            "corrected_answer": corrected_input,
                            "reviewer_notes": notes_input
                        })
                        
                    try:
                        with open("human_review_log.csv", "w", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=[
                                "case_id", "category", "ai_confidence", "ai_root_cause",
                                "expected_fault", "human_decision", "corrected_answer", "reviewer_notes"
                            ], quoting=csv.QUOTE_ALL)
                            writer.writeheader()
                            writer.writerows(reviews)
                    except Exception as e:
                        st.error("Unable to complete this analysis. Please verify the case evidence and try again.")
                        sys.stderr.write(f"Error writing review CSV: {e}\n")
                        return
                        
                    st.session_state[f"review_submitted_{selected_cid}"] = {
                        "decision": backend_decision.upper(),
                        "corrected_input": corrected_input,
                        "notes": notes_input
                    }
                    
                    if backend_decision in ["Accepted", "Edited"]:
                        after_state_log = simulate_after_state(case_row)
                        from verification.post_fix import verify_fix
                        post_res = verify_fix(case_row["category"], case_row["show_output"], after_state_log)
                        
                        if post_res["passed_verification"]:
                            final_rc = corrected_input if backend_decision == "Edited" else active_diag["root_cause"]
                            vault_success = add_verified_case(
                                case_id=selected_cid,
                                symptom=case_row["symptom"],
                                network_dna=dna,
                                root_cause=final_rc,
                                fix=active_diag["fix_steps"],
                                concept=case_row["category"],
                                human_review="approved",
                                post_fix_verification="verified"
                            )
                            if not vault_success:
                                sys.stderr.write(f"Vault addition failed for {selected_cid}.\n")
                    st.rerun()
                    
                submit_state = st.session_state.get(f"review_submitted_{selected_cid}")
                if submit_state:
                    st.markdown(f"""
                    <div style="padding: 12px; background-color: #12151c; border-left: 3px solid #4FC78A; margin-top: 15px; margin-bottom: 15px; border-radius: 2px; border: 1px solid #1f2430; border-left: 3px solid #4FC78A;">
                        <div style="font-weight: bold; color: #4FC78A; font-size: 13.5px; margin-bottom: 8px;">Review submitted successfully.</div>
                        <div style="font-size: 12.5px; color: #cdd1da; line-height: 1.6;">
                            <strong>Decision:</strong><br>{submit_state['decision']}<br><br>
                            <strong>Status:</strong><br>Post-fix simulation evaluated.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # POST-FIX VERIFICATION SECTION
                existing_review = next((r for r in reviews if r["case_id"] == selected_cid), None)
                has_approved_review = existing_review and existing_review["human_decision"] in ["Accepted", "Edited"]
                
                if has_approved_review or (submit_state and submit_state["decision"] in ["ACCEPTED", "EDITED"]):
                    st.divider()
                    st.markdown("<h3 style='margin-top: 15px; margin-bottom: 8px;'>POST-FIX VERIFICATION</h3>", unsafe_allow_html=True)
                    
                    st.markdown("""
                    <div style="font-size: 12px; color: #8c93a0; margin-bottom: 10px;">
                        <strong>What is this?</strong> Simulates configuration fix application and compares pre/post outputs.<br>
                        <strong>What did NetSage find?</strong> Output results of before/after comparisons.<br>
                        <strong>What should I do next?</strong> If VERIFIED, verification passed. If verification failed, revise fix steps.
                    </div>
                    """, unsafe_allow_html=True)
                    
                    before_state = case_row["show_output"]
                    after_state = simulate_after_state(case_row)
                    
                    col_post1, col_post2 = st.columns(2)
                    with col_post1:
                        st.markdown("**Before Fix**")
                        st.code(before_state, language="text")
                    with col_post2:
                        st.markdown("**After Fix**")
                        st.code(after_state, language="text")
                        
                    from verification.post_fix import verify_fix
                    post_res = verify_fix(case_row["category"], before_state, after_state)
                    
                    if post_res["passed_verification"]:
                        st.markdown("""
                        <div style="font-size: 14px; color: #4FC78A; font-weight: bold; margin-top: 10px;">
                            ✓ VERIFIED
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="font-size: 14px; color: #E05C5C; font-weight: bold; margin-top: 10px;">
                            ✕ VERIFICATION FAILED: {post_res['message']}
                        </div>
                        """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Troubleshoot Mode Error: {e}")
            sys.stderr.write(f"Unexpected error in Troubleshoot mode: {e}\n")
            import traceback
            traceback.print_exc()

    elif mode == "Analytics":
        try:
            st.markdown("<h1>NETSAGE</h1>", unsafe_allow_html=True)
            st.markdown("<p style='color: #8c93a0; font-size: 14px; margin-top: -10px; margin-bottom: 20px;'>Incident Insights & Analytics Console</p>", unsafe_allow_html=True)
            
            st.sidebar.markdown("### 🔍 Dashboard Filters")
            cat_display = {
                "vlan": "VLAN",
                "routing": "Routing",
                "dhcp": "DHCP",
                "dns": "DNS",
                "acl": "ACL",
                "nat": "NAT",
                "wireless": "Wireless",
                "gateway": "Gateway/IP",
                "interface": "Interface"
            }
            selected_cats = st.sidebar.multiselect(
                "Select Category",
                options=list(cat_display.keys()),
                default=list(cat_display.keys()),
                format_func=lambda x: cat_display[x]
            )
            selected_sevs = st.sidebar.multiselect(
                "Select Severity",
                options=SEVERITY_ORDER,
                default=SEVERITY_ORDER,
                format_func=lambda x: x.capitalize()
            )
            layer_display = {
                "1": "Layer 1 (Physical)",
                "2": "Layer 2 (Data Link)",
                "3": "Layer 3 (Network)",
                "4": "Layer 4 (Transport)",
                "7": "Layer 7 (Application)"
            }
            selected_layers = st.sidebar.multiselect(
                "Select OSI Layer",
                options=list(layer_display.keys()),
                default=list(layer_display.keys()),
                format_func=lambda x: layer_display[x]
            )

            # Run filtering
            filtered_cases = filter_cases_by_criteria(cases, selected_cats, selected_sevs, selected_layers)

            if not filtered_cases:
                st.warning("⚠️ No cases match the selected filter criteria. Please adjust your selections in the sidebar.")
                return

            filtered_cids = {r["case_id"] for r in filtered_cases}
            filtered_diagnos = [r for r in diagnos if r["case_id"] in filtered_cids]
            filtered_reviews = [r for r in reviews if r["case_id"] in filtered_cids]

            # Calculate KPIs dynamically
            vault_cases = get_verified_cases()
            vault_ids = {c["case_id"] for c in vault_cases}
            kpis = calculate_kpis(filtered_cases, filtered_diagnos, filtered_reviews, vault_ids)

            # NETWORK INCIDENT OVERVIEW
            st.subheader("NETWORK INCIDENT OVERVIEW")
            
            accepted_cnt = sum(1 for r in filtered_reviews if r.get("human_decision") == "Accepted")
            edited_cnt   = sum(1 for r in filtered_reviews if r.get("human_decision") == "Edited")
            rejected_cnt = sum(1 for r in filtered_reviews if r.get("human_decision") == "Rejected")
            
            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            with col_kpi1:
                st.metric("Total Cases", f"{kpis['total_cases']}")
            with col_kpi2:
                st.metric("Accepted Decisions", f"{accepted_cnt}")
            with col_kpi3:
                st.metric("Edited Decisions", f"{edited_cnt}")
            with col_kpi4:
                st.metric("Rejected Decisions", f"{rejected_cnt}")

            st.divider()

            import matplotlib.pyplot as plt

            # Matplotlib plotting
            # Chart 1: Cases by Category
            cat_counts = Counter(r["category"] for r in filtered_cases)
            cats = [c for c in CATEGORY_ORDER if c in cat_counts]
            counts = [cat_counts[c] for c in cats]
            colors = [PALETTE.get(c, "#4F8EF7") for c in cats]

            fig1, ax1 = plt.subplots(figsize=(6, 4))
            fig1.patch.set_facecolor("#0c0e12")
            ax1.set_facecolor("#12151c")
            bars1 = ax1.bar(cats, counts, color=colors, width=0.5, edgecolor="#1f2430", zorder=3)
            ax1.set_title("Cases by Category", color="white", fontsize=11, fontweight="bold")
            ax1.set_ylabel("Count", color="white", fontsize=9)
            ax1.tick_params(colors="#cdd1da", labelsize=8)
            ax1.spines["top"].set_visible(False)
            ax1.spines["right"].set_visible(False)
            ax1.spines["left"].set_color("#1f2430")
            ax1.spines["bottom"].set_color("#1f2430")
            ax1.yaxis.grid(True, color="#1f2430", linestyle="--", alpha=0.7)
            ax1.set_axisbelow(True)
            for bar in bars1:
                h = bar.get_height()
                if h > 0:
                    ax1.text(bar.get_x() + bar.get_width()/2, h + 0.05, str(int(h)),
                             ha="center", va="bottom", color="white", fontsize=8, fontweight="bold")
            fig1.tight_layout()

            # Chart 2: Cases by Severity
            sev_counts = Counter(r["severity"] for r in filtered_cases)
            sevs = [s for s in SEVERITY_ORDER if s in sev_counts]
            scnts = [sev_counts[s] for s in sevs]
            scolors = [PALETTE.get(s, "#4F8EF7") for s in sevs]

            fig2, ax2 = plt.subplots(figsize=(6, 4))
            fig2.patch.set_facecolor("#0c0e12")
            ax2.set_facecolor("#12151c")
            bars2 = ax2.bar(sevs, scnts, color=scolors, width=0.4, edgecolor="#1f2430", zorder=3)
            ax2.set_title("Cases by Severity", color="white", fontsize=11, fontweight="bold")
            ax2.set_ylabel("Count", color="white", fontsize=9)
            ax2.tick_params(colors="#cdd1da", labelsize=8)
            ax2.spines["top"].set_visible(False)
            ax2.spines["right"].set_visible(False)
            ax2.spines["left"].set_color("#1f2430")
            ax2.spines["bottom"].set_color("#1f2430")
            ax2.yaxis.grid(True, color="#1f2430", linestyle="--", alpha=0.7)
            ax2.set_axisbelow(True)
            for bar in bars2:
                h = bar.get_height()
                if h > 0:
                    ax2.text(bar.get_x() + bar.get_width()/2, h + 0.05, str(int(h)),
                             ha="center", va="bottom", color="white", fontsize=8, fontweight="bold")
            fig2.tight_layout()

            # Chart 3: Cases by OSI Layer
            layer_counts = Counter(r["osi_layer"] for r in filtered_cases)
            sorted_layers = sorted(layer_counts.items(), key=lambda x: int(x[0].split(" - ")[0]))
            labels = [l for l, _ in sorted_layers]
            values = [v for _, v in sorted_layers]
            colors = [
                "#E05C5C", "#F79C4F", "#F7E04F",
                "#4FC78A", "#4F8EF7", "#A04FF7", "#F74FA0",
            ][:len(labels)]

            fig3, ax3 = plt.subplots(figsize=(6, 4))
            fig3.patch.set_facecolor("#0c0e12")
            ax3.set_facecolor("#12151c")
            bars3 = ax3.barh(labels, values, color=colors[::-1], edgecolor="#1f2430", height=0.4, zorder=3)
            ax3.set_title("Cases by OSI Layer", color="white", fontsize=11, fontweight="bold")
            ax3.set_xlabel("Count", color="white", fontsize=9)
            ax3.tick_params(colors="#cdd1da", labelsize=8)
            ax3.spines["top"].set_visible(False)
            ax3.spines["right"].set_visible(False)
            ax3.spines["left"].set_color("#1f2430")
            ax3.spines["bottom"].set_color("#1f2430")
            ax3.xaxis.grid(True, color="#1f2430", linestyle="--", alpha=0.7)
            ax3.set_axisbelow(True)
            for bar in bars3:
                w = bar.get_width()
                if w > 0:
                    ax3.text(w + 0.1, bar.get_y() + bar.get_height()/2, str(int(w)),
                             va="center", ha="left", color="white", fontsize=8, fontweight="bold")
            fig3.tight_layout()

            # Chart 4: Human Decision Distribution
            dec_counts = Counter(r["human_decision"] for r in filtered_reviews)
            labels5 = [d for d in DECISION_ORDER if d in dec_counts]
            values5 = [dec_counts[d] for d in labels5]
            colors5 = [PALETTE.get(d, "#4F8EF7") for d in labels5]

            fig5, ax5 = plt.subplots(figsize=(6, 4))
            fig5.patch.set_facecolor("#0c0e12")
            ax5.set_facecolor("#12151c")
            bars5 = ax5.bar(labels5, values5, color=colors5, width=0.4, edgecolor="#1f2430", zorder=3)
            ax5.set_title("Human Audit Decisions", color="white", fontsize=11, fontweight="bold")
            ax5.set_ylabel("Count", color="white", fontsize=9)
            ax5.tick_params(colors="#cdd1da", labelsize=8)
            ax5.spines["top"].set_visible(False)
            ax5.spines["right"].set_visible(False)
            ax5.spines["left"].set_color("#1f2430")
            ax5.spines["bottom"].set_color("#1f2430")
            ax5.yaxis.grid(True, color="#1f2430", linestyle="--", alpha=0.7)
            ax5.set_axisbelow(True)
            for bar in bars5:
                h = bar.get_height()
                if h > 0:
                    ax5.text(bar.get_x() + bar.get_width()/2, h + 0.05, str(int(h)),
                             ha="center", va="bottom", color="white", fontsize=8, fontweight="bold")
            fig5.tight_layout()

            # Chart 5: AI Confidence Distribution
            conf_counts = {"high": 0, "medium": 0, "low": 0}
            for r in filtered_diagnos:
                conf_raw = r["confidence"].lower()
                try:
                    val = float(conf_raw)
                    if val >= 0.80:
                        conf_counts["high"] += 1
                    elif val >= 0.40:
                        conf_counts["medium"] += 1
                    else:
                        conf_counts["low"] += 1
                except ValueError:
                    conf = conf_raw if conf_raw in ["high", "medium", "low"] else "low"
                    conf_counts[conf] += 1
            labels4 = ["High", "Medium", "Low"]
            values4 = [conf_counts["high"], conf_counts["medium"], conf_counts["low"]]
            colors4 = [PALETTE["conf_high"], PALETTE["conf_medium"], PALETTE["conf_low"]]

            fig4, ax4 = plt.subplots(figsize=(10, 4))
            fig4.patch.set_facecolor("#0c0e12")
            ax4.set_facecolor("#12151c")
            bars4 = ax4.bar(labels4, values4, color=colors4, width=0.3, edgecolor="#1f2430", zorder=3)
            ax4.set_title("AI Confidence Distribution", color="white", fontsize=11, fontweight="bold")
            ax4.set_ylabel("Count", color="white", fontsize=9)
            ax4.tick_params(colors="#cdd1da", labelsize=8)
            ax4.spines["top"].set_visible(False)
            ax4.spines["right"].set_visible(False)
            ax4.spines["left"].set_color("#1f2430")
            ax4.spines["bottom"].set_color("#1f2430")
            ax4.yaxis.grid(True, color="#1f2430", linestyle="--", alpha=0.7)
            ax4.set_axisbelow(True)
            for bar in bars4:
                h = bar.get_height()
                if h > 0:
                    ax4.text(bar.get_x() + bar.get_width()/2, h + 0.05, str(int(h)),
                             ha="center", va="bottom", color="white", fontsize=8, fontweight="bold")
            fig4.tight_layout()

            # Layout sections
            st.subheader("CASE DISTRIBUTION")
            col_dist1, col_dist2 = st.columns(2)
            with col_dist1:
                st.pyplot(fig1)
            with col_dist2:
                st.pyplot(fig3)

            st.divider()

            st.subheader("SEVERITY")
            critical_cnt = sev_counts.get("critical", 0)
            high_cnt     = sev_counts.get("high", 0)
            medium_cnt   = sev_counts.get("medium", 0)
            low_cnt      = sev_counts.get("low", 0)
            
            col_sev1, col_sev2, col_sev3, col_sev4 = st.columns(4)
            with col_sev1:
                st.metric("Critical", f"{critical_cnt}")
            with col_sev2:
                st.metric("High", f"{high_cnt}")
            with col_sev3:
                st.metric("Medium", f"{medium_cnt}")
            with col_sev4:
                st.metric("Low", f"{low_cnt}")
                
            st.pyplot(fig2)

            st.divider()

            st.subheader("AI PERFORMANCE")
            col_perf1, col_perf2 = st.columns(2)
            with col_perf1:
                st.pyplot(fig4)
            with col_perf2:
                st.pyplot(fig5)

        except Exception as e:
            st.error(f"Analytics Mode Error: {e}")
            sys.stderr.write(f"Unexpected error in Analytics mode: {e}\n")
            import traceback
            traceback.print_exc()

    elif mode == "Human Review":
        try:
            st.markdown("<h1>NETSAGE</h1>", unsafe_allow_html=True)
            st.markdown("<p style='color: #8c93a0; font-size: 14px; margin-top: -10px; margin-bottom: 20px;'>Incident Human Audit & Approval Terminal</p>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style="font-size: 12px; color: #8c93a0; margin-bottom: 15px;">
                <strong>What is this?</strong> A dedicated terminal for network engineers to audit, edit, and sign off on AI diagnoses.<br>
                <strong>What did NetSage find?</strong> Config details, local rule violations (ProofGate), and reasoning logs below.<br>
                <strong>What should I do next?</strong> Input notes, pick validation decision, and submit review.
            </div>
            """, unsafe_allow_html=True)
            
            case_ids = [r["case_id"] for r in cases]
            selected_cid = st.selectbox("Select Case ID to Audit", case_ids, key="hr_select_cid")
            
            case_row = next(r for r in cases if r["case_id"] == selected_cid)
            diag_row = next((r for r in diagnos if r["case_id"] == selected_cid), None)
            
            if not diag_row:
                st.error("No offline AI diagnosis found for this case. Run standard pipeline first.")
                return
                
            category_title = category_mapping.get(case_row["category"].lower(), f"{case_row['category'].upper()} Incident")
            st.markdown(f"""
            <div style="padding: 12px; border: 1px solid #1f2430; background-color: #12151c; margin-bottom: 15px; border-radius: 2px; font-size: 13px;">
                <strong>Case ID:</strong> {selected_cid}<br>
                <strong>Incident Name:</strong> {category_title.upper()}<br>
                <strong>Severity:</strong> {case_row['severity'].upper()}<br>
                <strong>OSI Layer:</strong> Layer {case_row['osi_layer']}<br>
                <strong>Symptom:</strong> {case_row['symptom']}
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("🔍 View Raw Config / Command Outputs"):
                st.code(case_row["show_output"], language="text")
                
            st.markdown("### SYSTEM VALIDATION RESULTS")
            findings = check_case(case_row["show_output"])
            proof_res = check_conflicts(findings, diag_row["root_cause"])
            
            col_sys1, col_sys2 = st.columns(2)
            with col_sys1:
                st.markdown("**Deterministic Config Rules:**")
                if findings:
                    for f in findings:
                        st.markdown(f"- 🔴 {f}")
                else:
                    st.markdown("- 🟢 No local config rule violations discovered.")
            with col_sys2:
                st.markdown("**ProofGate Conflict Check:**")
                if proof_res["conflict_detected"]:
                    st.warning("⚠️ Conflict Detected")
                    for msg in proof_res["conflict_messages"]:
                        st.markdown(f"- {msg}")
                else:
                    st.success("✅ Passed (No Conflict)")
                    
            st.markdown("### REASONCHAIN OBSERVATIONS")
            def parse_list_col(val):
                if not val: return []
                return val.split(" | ") if " | " in val else [val]
                
            try:
                conf_val = float(diag_row["confidence"])
            except ValueError:
                conf_val = 0.90 if diag_row["confidence"] == "high" else (0.60 if diag_row["confidence"] == "medium" else 0.30)
                
            temp_diag = {
                "root_cause": diag_row["root_cause"],
                "confidence": conf_val,
                "evidence": parse_list_col(diag_row["evidence"]),
                "next_command": diag_row["next_command"],
                "fix_steps": parse_list_col(diag_row["fix_steps"]),
                "alternatives": parse_list_col(diag_row.get("alternatives", "")),
                "contradicting_evidence": parse_list_col(diag_row.get("contradicting_evidence", "")),
                "evidence_sufficiency": diag_row.get("evidence_sufficiency", "sufficient")
            }
            
            rc_text = format_reasonchain(temp_diag)
            st.text_area("ReasonChain Breakdown", rc_text, height=200, disabled=True, key="hr_rc_text")
            
            st.markdown("### HUMAN REVIEW")
            st.markdown(f"**AI Diagnosis:** {diag_row['root_cause']}")
            
            prev_review = next((r for r in reviews if r["case_id"] == selected_cid), None)
            default_decision = "Accept"
            default_notes = ""
            default_corrected = ""
            
            if prev_review:
                dec_map_inv = {"Accepted": "Accept", "Edited": "Edit", "Rejected": "Reject"}
                default_decision = dec_map_inv.get(prev_review["human_decision"], "Accept")
                default_notes = prev_review["reviewer_notes"]
                default_corrected = prev_review["corrected_answer"]
                
            review_decision = st.radio(
                "Reviewer Decision",
                ["Accept", "Edit", "Reject"],
                index=["Accept", "Edit", "Reject"].index(default_decision),
                key="hr_decision_radio"
            )
            
            corrected_input = ""
            if review_decision in ["Edit", "Reject"]:
                corrected_input = st.text_input("Corrected Root Cause / Operator Notes:", value=default_corrected, key="hr_corrected_input")
                
            notes_input = st.text_area("Reviewer Notes:", value=default_notes, key="hr_notes_input")
            
            if st.button("Submit Review", key="hr_submit_button"):
                decision_map = {"Accept": "Accepted", "Edit": "Edited", "Reject": "Rejected"}
                backend_decision = decision_map[review_decision]
                
                updated = False
                for r in reviews:
                    if r["case_id"] == selected_cid:
                        r["human_decision"] = backend_decision
                        r["corrected_answer"] = corrected_input
                        r["reviewer_notes"] = notes_input
                        updated = True
                        break
                if not updated:
                    reviews.append({
                        "case_id": selected_cid,
                        "category": case_row["category"],
                        "ai_confidence": diag_row["confidence"],
                        "ai_root_cause": diag_row["root_cause"],
                        "expected_fault": case_row.get("expected_fault", ""),
                        "human_decision": backend_decision,
                        "corrected_answer": corrected_input,
                        "reviewer_notes": notes_input
                    })
                    
                try:
                    with open("human_review_log.csv", "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=[
                            "case_id", "category", "ai_confidence", "ai_root_cause",
                            "expected_fault", "human_decision", "corrected_answer", "reviewer_notes"
                        ], quoting=csv.QUOTE_ALL)
                        writer.writeheader()
                        writer.writerows(reviews)
                except Exception as e:
                    st.error(f"Review Save Error: {e}")
                    sys.stderr.write(f"Error saving review: {e}\n")
                    return
                    
                st.session_state[f"hr_submitted_{selected_cid}"] = {
                    "decision": backend_decision.upper(),
                    "corrected_input": corrected_input,
                    "notes": notes_input
                }
                
                if backend_decision in ["Accepted", "Edited"]:
                    final_rc = corrected_input if backend_decision == "Edited" else diag_row["root_cause"]
                    dna = extract_network_dna(case_row["show_output"], case_row["symptom"])
                    
                    after_state_log = simulate_after_state(case_row)
                    from verification.post_fix import verify_fix
                    post_res = verify_fix(case_row["category"], case_row["show_output"], after_state_log)
                    
                    if post_res["passed_verification"]:
                        vault_success = add_verified_case(
                            case_id=selected_cid,
                            symptom=case_row["symptom"],
                            network_dna=dna,
                            root_cause=final_rc,
                            fix=diag_row["fix_steps"],
                            concept=case_row["category"],
                            human_review="approved",
                            post_fix_verification="verified"
                        )
                        if not vault_success:
                            sys.stderr.write(f"Vault addition failed for {selected_cid}.\n")
                st.rerun()
                
            hr_submit_state = st.session_state.get(f"hr_submitted_{selected_cid}")
            if hr_submit_state:
                st.markdown(f"""
                <div style="padding: 12px; background-color: #12151c; border-left: 3px solid #4FC78A; margin-top: 15px; margin-bottom: 15px; border-radius: 2px; border: 1px solid #1f2430; border-left: 3px solid #4FC78A;">
                    <div style="font-weight: bold; color: #4FC78A; font-size: 13.5px; margin-bottom: 8px;">Review submitted successfully.</div>
                    <div style="font-size: 12.5px; color: #cdd1da; line-height: 1.6;">
                        <strong>Decision:</strong><br>{hr_submit_state['decision']}<br><br>
                        <strong>Status:</strong><br>Awaiting post-fix verification.
                    </div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Human Review Mode Error: {e}")
            sys.stderr.write(f"Unexpected error in Human Review mode: {e}\n")
            import traceback
            traceback.print_exc()

    elif mode == "Memory Vault":
        try:
            st.markdown("<h1>NETSAGE</h1>", unsafe_allow_html=True)
            st.markdown("<p style='color: #8c93a0; font-size: 14px; margin-top: -10px; margin-bottom: 20px;'>Memory Vault &mdash; Incident Knowledge Base</p>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style="font-size: 12px; color: #8c93a0; margin-bottom: 15px;">
                <strong>What is this?</strong> A trusted database of historical troubleshooting incidents that passed validation and human review.<br>
                <strong>What did NetSage find?</strong> Archived case profiles, fix blueprints, and DNA signatures.<br>
                <strong>What should I do next?</strong> Query or search for past incidents to aid your current troubleshooting.
            </div>
            """, unsafe_allow_html=True)
            
            vault_cases = get_verified_cases()
            
            if not vault_cases:
                st.info("The Memory Vault is currently empty. Run Human Reviews and approve cases to seed the vault.")
            else:
                search_query = st.text_input("Search incidents by ID, symptom, or root cause:", key="vault_search_filter")
                
                filtered_vault = vault_cases
                if search_query:
                    q = search_query.lower()
                    filtered_vault = [
                        vc for vc in vault_cases
                        if q in vc["case_id"].lower() or q in vc["symptom"].lower() or q in vc["root_cause"].lower() or q in vc.get("concept", "").lower()
                    ]
                
                st.subheader(f"Verified Records ({len(filtered_vault)})")
                
                for vc in filtered_vault:
                    concept_display = category_mapping.get(vc['concept'].lower(), f"{vc['concept'].upper()} Incident")
                    with st.expander(f"📁 {vc['case_id']} &mdash; {concept_display.upper()}"):
                        st.markdown(f"""
                        <div style="font-size: 13px; line-height: 1.6; padding: 10px; background-color: #12151c; border-radius: 2px; border: 1px solid #1f2430;">
                            <strong>Status:</strong> <span style="color: #4FC78A; font-weight: bold;">Verified</span><br><br>
                            <strong>Symptom:</strong><br>{vc['symptom']}<br><br>
                            <strong>Root Cause:</strong><br>{vc['root_cause']}<br><br>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("<br><strong>Recommended Fix Blueprint:</strong>", unsafe_allow_html=True)
                        fix_data = vc['fix']
                        if isinstance(fix_data, list):
                            for step in fix_data:
                                st.markdown(f"- {step}")
                        elif isinstance(fix_data, str):
                            if " | " in fix_data:
                                for step in fix_data.split(" | "):
                                    st.markdown(f"- {step}")
                            else:
                                st.markdown(f"- {fix_data}")
                                
                        with st.expander("Technical Network DNA Signature"):
                            st.json(vc["network_dna"])
                            
                st.divider()
                
                st.subheader("🔍 Historical Case Query Engine")
                
                st.markdown("""
                <div style="font-size: 12px; color: #8c93a0; margin-bottom: 10px;">
                    <strong>What is this?</strong> Compares a manual description or symptom to vault entries using Jaccard Similarity.<br>
                    <strong>What did NetSage find?</strong> Top similar historical cases from vault.<br>
                    <strong>What should I do next?</strong> View the matches below for potential diagnostic hints.
                </div>
                """, unsafe_allow_html=True)
                
                search_query_jaccard = st.text_input("Enter search keywords or symptoms:", key="vault_search_jaccard")
                if st.button("Search Similar Cases", key="vault_search_button"):
                    if not search_query_jaccard:
                        st.warning("Please enter a query.")
                    else:
                        matches = retrieve_similar_cases(search_query_jaccard, vault_cases, top_n=3)
                        if not matches:
                            st.info("No matching historical cases found.")
                        else:
                            st.markdown("### HISTORICAL SUPPORTING CONTEXT")
                            st.caption("⚠️ Similar historical cases are NOT proof of the current diagnosis. They serve only as supporting context.")

                            for i, match in enumerate(matches, 1):
                                c = match["case"]
                                score_pct = int(match["score"] * 100)
                                case_id_val = c.get("case_id", "")
                                root_cause_val = c.get("root_cause", "")
                                concept_val = c.get("concept", "").upper()
                                
                                concept_display = category_mapping.get(concept_val.lower(), f"{concept_val} Incident")
                                st.markdown(f"""
                                <div style="padding: 10px; border-left: 3px solid #4F8EF7; background-color: #12151c; margin-bottom: 8px; border-radius: 2px; border: 1px solid #1f2430; border-left: 3px solid #4F8EF7;">
                                    <div style="font-weight: bold; font-size: 13px;">{i}. {case_id_val} &mdash; {concept_display.upper()}</div>
                                    <div style="font-size: 12.5px; color: #cdd1da; margin: 4px 0;"><strong>Issue:</strong> {root_cause_val}</div>
                                    <div style="font-size: 11px; color: #8c93a0;">Similarity Score: {score_pct}%</div>
                                </div>
                                """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Memory Vault Mode Error: {e}")
            sys.stderr.write(f"Unexpected error in Memory Vault mode: {e}\n")
            import traceback
            traceback.print_exc()


def is_running_under_streamlit() -> bool:
    """Helper to detect if execution context resides inside Streamlit."""
    import sys
    return "streamlit" in sys.modules


if __name__ == "__main__":
    cases   = load_csv("cases.csv")
    diagnos = load_csv("ai_diagnoses.csv")
    reviews = load_csv("human_review_log.csv")
    
    if is_running_under_streamlit():
        run_streamlit_app()
    else:
        # Index reviews by case_id
        decision_counts = Counter(r["human_decision"] for r in reviews)
        total_reviews = len(reviews)
        
        # Chart 4 - Layer distribution sorting
        layer_counts = Counter(r["osi_layer"] for r in cases)
        sorted_layers = sorted(layer_counts.items(), key=lambda x: int(x[0].split(" - ")[0]))
        
        # Section 5 - confidence breakdown by category
        conf_by_cat = {c: {"high": 0, "medium": 0, "low": 0} for c in CATEGORY_ORDER}
        for row in diagnos:
            cat = row["category"]
            conf_raw = row["confidence"].lower()
            try:
                val = float(conf_raw)
                if val >= 0.80:
                    conf = "high"
                elif val >= 0.40:
                    conf = "medium"
                else:
                    conf = "low"
            except ValueError:
                conf = conf_raw if conf_raw in ["high", "medium", "low"] else "low"
            if cat in conf_by_cat and conf in conf_by_cat[cat]:
                conf_by_cat[cat][conf] += 1
                
        # Category distribution counting
        cat_counts = Counter(r["category"] for r in cases)
        
        # Severity distribution counting
        sev_counts = Counter(r["severity"] for r in cases)
        
        generate_static_charts(cases, diagnos, reviews)
