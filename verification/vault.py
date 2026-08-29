# verification/vault.py
import json
import sys
from pathlib import Path

# Ensure Windows UTF-8 stdout/stderr handles are safe (if run directly)
if sys.platform.startswith('win') and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DEFAULT_VAULT_PATH = "data/memory.json"


def load_memory(path: str = DEFAULT_VAULT_PATH) -> list[dict]:
    """Loads all verified cases from the Memory Vault JSON file."""
    file_path = Path(path)
    if not file_path.exists():
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading Memory Vault: {e}", file=sys.stderr)
        return []


def save_memory(cases: list[dict], path: str = DEFAULT_VAULT_PATH) -> None:
    """Saves the list of cases to the Memory Vault JSON file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cases, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving Memory Vault: {e}", file=sys.stderr)


def is_verified(human_review: str, post_fix_verification: str) -> bool:
    """
    Checks if a case is eligible for trust/verification.
    A case is trusted ONLY when human_review is approved AND post_fix_verification is verified.
    """
    return (human_review == "approved") and (post_fix_verification == "verified")


def add_verified_case(
    case_id: str,
    symptom: str,
    network_dna: dict,
    root_cause: str,
    fix: str,
    concept: str,
    human_review: str,
    post_fix_verification: str,
    path: str = DEFAULT_VAULT_PATH
) -> bool:
    """
    Adds a case to the Memory Vault if it meets the trust rule.
    If the case is already in the vault, updates it.
    """
    if not is_verified(human_review, post_fix_verification):
        print(f"Aborting vault entry for {case_id}: Trust checks failed.")
        return False

    cases = load_memory(path)

    # Check if case already exists to prevent duplicates
    for c in cases:
        if c.get("case_id") == case_id:
            c["symptom"] = symptom
            c["network_dna"] = network_dna
            c["root_cause"] = root_cause
            c["fix"] = fix
            c["concept"] = concept
            c["verified"] = True
            save_memory(cases, path)
            print(f"Updated verified case {case_id} in Memory Vault.")
            return True

    # Append new record
    new_record = {
        "case_id": case_id,
        "symptom": symptom,
        "network_dna": network_dna,
        "root_cause": root_cause,
        "fix": fix,
        "concept": concept,
        "verified": True
    }
    cases.append(new_record)
    save_memory(cases, path)
    print(f"Added verified case {case_id} to Memory Vault.")
    return True


def get_verified_cases(path: str = DEFAULT_VAULT_PATH) -> list[dict]:
    """Returns only verified cases in the vault."""
    cases = load_memory(path)
    return [c for c in cases if c.get("verified") is True]
