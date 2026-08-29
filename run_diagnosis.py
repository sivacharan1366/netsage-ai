"""
run_diagnosis.py
================
NetSage Phase 3.1 — AI Diagnosis Runner

Reads cases.csv, builds the diagnose_prompt.md template for each case,
sends it to the Claude API (claude-sonnet-4-6), and saves results to
ai_diagnoses.csv.  Also performs a rough "match" check against cases.csv's
expected_fault column.

SETUP
-----
Set your API key in one of these ways:
  export ANTHROPIC_API_KEY="sk-ant-..."          # shell environment variable
  echo ANTHROPIC_API_KEY=sk-ant-... > .env       # .env file in project dir

If neither is found the script falls back to the pre-generated
ai_diagnoses.csv that ships with the project (offline mode).

USAGE
-----
  python3 run_diagnosis.py              # process all 32 cases
  python3 run_diagnosis.py --case 6    # process single case by 1-based index
  python3 run_diagnosis.py --dry-run   # parse CSV + prompt but don't call API
"""

import sys

import csv
import json
import os
import re
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL          = "claude-sonnet-4-6"
MAX_TOKENS     = 1000
CASES_CSV      = "cases.csv"
DIAGNOSES_CSV  = "ai_diagnoses.csv"
PROMPT_FILE    = "diagnose_prompt.md"

FIELDNAMES_OUT = [
    "case_id", "category", "symptom", "root_cause", "confidence",
    "evidence", "next_command", "fix_steps", "alternatives",
    "contradicting_evidence", "evidence_sufficiency", "match",
]

# ---------------------------------------------------------------------------
# Load API key (env → .env file)
# ---------------------------------------------------------------------------
def get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY"):
                _, _, val = line.partition("=")
                return val.strip().strip('"').strip("'")
    return None


# ---------------------------------------------------------------------------
# Load prompt template
# ---------------------------------------------------------------------------
def load_prompt_template(path: str = PROMPT_FILE) -> str:
    return Path(path).read_text(encoding="utf-8")


def build_prompt(template: str, row: dict) -> str:
    """Fill {{SYMPTOM}}, {{TOPOLOGY_NOTE}}, {{SHOW_OUTPUT}} into template."""
    filled = template
    filled = filled.replace("{{SYMPTOM}}",       row["symptom"])
    filled = filled.replace("{{TOPOLOGY_NOTE}}", row["topology_note"])
    filled = filled.replace("{{SHOW_OUTPUT}}",   row["show_output"])
    return filled


# ---------------------------------------------------------------------------
# Call Claude API
# ---------------------------------------------------------------------------
def call_claude(client, prompt: str) -> dict:
    """
    Send prompt to Claude and return parsed JSON dict.
    Returns error dict on failure.
    """
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if model accidentally wraps output
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        raw = raw.strip()

        parsed = json.loads(raw)
        
        from ai.reasonchain import validate_diagnosis_json
        if not validate_diagnosis_json(parsed):
            print("\n[VALIDATION WARNING] AI JSON response did not match expected schema format.")
            return {
                "root_cause": f"[VALIDATION ERROR] Response JSON did not match expected schema. Raw response: {raw[:200]}",
                "confidence": 0.0,
                "evidence": [],
                "next_command": "",
                "fix_steps": [],
                "alternatives": [],
                "contradicting_evidence": [],
                "evidence_sufficiency": "partial"
            }
        return parsed

    except json.JSONDecodeError as e:
        return {
            "root_cause":    f"[PARSE ERROR] {e} | raw={raw[:200]}",
            "confidence":    0.0,
            "evidence":      [],
            "next_command":  "",
            "fix_steps":     [],
            "alternatives":  [],
            "contradicting_evidence": [],
            "evidence_sufficiency": "partial"
        }
    except Exception as e:
        return {
            "root_cause":    f"[API ERROR] {e}",
            "confidence":    0.0,
            "evidence":      [],
            "next_command":  "",
            "fix_steps":     [],
            "alternatives":  [],
            "contradicting_evidence": [],
            "evidence_sufficiency": "partial"
        }


# ---------------------------------------------------------------------------
# Match check (rough keyword overlap)
# ---------------------------------------------------------------------------
def compute_match(ai_root_cause: str, expected_fault: str) -> str:
    """
    Rough heuristic: extract keywords from expected_fault and see how many
    appear in ai_root_cause.  Threshold: ≥ 2 of the top-5 keywords match.
    """
    # Remove common stop words and short tokens
    stopwords = {
        "the", "a", "an", "is", "in", "on", "at", "to", "for", "of",
        "and", "or", "not", "with", "from", "this", "that", "its",
        "are", "was", "has", "have", "it", "be", "by", "as", "if",
        "fix", "add", "use", "run", "set", "no", "ip",
    }
    def keywords(text: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9_-]{4,}", text.lower())
        return [t for t in tokens if t not in stopwords]

    exp_kw = keywords(expected_fault)
    ai_kw  = set(keywords(ai_root_cause))
    if not exp_kw:
        return "no"
    hits = sum(1 for k in exp_kw[:8] if k in ai_kw)
    return "yes" if hits >= 2 else "no"


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    dry_run     = "--dry-run" in sys.argv
    single_case = None
    if "--case" in sys.argv:
        idx = sys.argv.index("--case")
        single_case = int(sys.argv[idx + 1])

    # Load cases
    with open(CASES_CSV, newline="", encoding="utf-8") as f:
        cases = list(csv.DictReader(f))

    if single_case:
        cases = [cases[single_case - 1]]

    # Load prompt template
    template = load_prompt_template(PROMPT_FILE)

    # API client
    api_key = get_api_key()
    client  = None

    if dry_run:
        print("DRY RUN — no API calls will be made.")
    elif not api_key:
        print(
            "⚠  ANTHROPIC_API_KEY not found.\n"
            "   Set it via:\n"
            "     export ANTHROPIC_API_KEY=sk-ant-...\n"
            "   or create a .env file with:\n"
            "     ANTHROPIC_API_KEY=sk-ant-...\n"
            "   Then re-run this script.\n\n"
            "   Falling back to pre-generated ai_diagnoses.csv if it exists."
        )
        if Path(DIAGNOSES_CSV).exists():
            print(f"   Found {DIAGNOSES_CSV} — nothing to do.")
        sys.exit(0)
    else:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            print(f"Connected to Claude API  model={MODEL}")
        except ImportError:
            print("ERROR: pip3 install anthropic")
            sys.exit(1)

    results = []
    matched = 0
    failed  = 0

    for i, row in enumerate(cases, 1):
        cid = row["case_id"]
        print(f"  [{i:02d}/{len(cases)}] {cid}  ({row['category']})  ", end="", flush=True)

        if dry_run:
            prompt = build_prompt(template, row)
            print(f"prompt_len={len(prompt)}  [skipped]")
            continue

        prompt   = build_prompt(template, row)
        response = call_claude(client, prompt)

        from ai.reasonchain import format_reasonchain
        rc_text = format_reasonchain(response)
        print("\n" + "=" * 50)
        print("REASONCHAIN SUMMARY:")
        print(rc_text)
        print("=" * 50)

        # Build list strings for CSV formatting
        fix_steps = response.get("fix_steps", [])
        fix_steps_str = " | ".join(fix_steps) if isinstance(fix_steps, list) else str(fix_steps)

        evidence = response.get("evidence", [])
        evidence_str = " | ".join(evidence) if isinstance(evidence, list) else str(evidence)

        alts = response.get("alternatives", [])
        alts_str = " | ".join(alts) if isinstance(alts, list) else str(alts)

        cev = response.get("contradicting_evidence", [])
        cev_str = " | ".join(cev) if isinstance(cev, list) else str(cev)

        match = compute_match(
            response.get("root_cause", ""),
            row.get("expected_fault", ""),
        )
        if match == "yes":
            matched += 1
        else:
            failed += 1

        out_row = {
            "case_id":      cid,
            "category":     row["category"],
            "symptom":      row["symptom"],
            "root_cause":   response.get("root_cause", ""),
            "confidence":   response.get("confidence", 0.0),
            "evidence":     evidence_str,
            "next_command": response.get("next_command", ""),
            "fix_steps":    fix_steps_str,
            "alternatives": alts_str,
            "contradicting_evidence": cev_str,
            "evidence_sufficiency": response.get("evidence_sufficiency", "partial"),
            "match":        match,
        }
        results.append(out_row)
        print(f"confidence={response.get('confidence','?')}  match={match}")

        # Respect rate limits (3 RPM for free tier)
        if i < len(cases):
            time.sleep(1)

    if not dry_run and results:
        with open(DIAGNOSES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES_OUT, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n  Saved {len(results)} diagnoses to {DIAGNOSES_CSV}")
        total = matched + failed
        print(f"  Match summary: {matched}/{total} matched  "
              f"({100*matched//total if total else 0}%)")


if __name__ == "__main__":
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    main()
