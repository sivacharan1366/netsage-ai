# ai/reasonchain.py
import sys

# Ensure Windows UTF-8 stdout/stderr handles are safe (if run directly)
if sys.platform.startswith('win') and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def validate_diagnosis_json(diagnosis: dict) -> bool:
    """
    Validates that the AI JSON response conforms strictly to the expected schema.
    Returns True if valid, False otherwise.
    """
    if not isinstance(diagnosis, dict):
        return False
        
    # Required keys existence and type checks
    if "root_cause" not in diagnosis or not isinstance(diagnosis["root_cause"], str):
        return False
        
    if "confidence" not in diagnosis:
        return False
        
    try:
        conf = float(diagnosis["confidence"])
        if not (0.0 <= conf <= 1.0):
            return False
    except (ValueError, TypeError):
        return False
        
    if "evidence" not in diagnosis or not isinstance(diagnosis["evidence"], list):
        return False
        
    if "fix_steps" not in diagnosis or not isinstance(diagnosis["fix_steps"], list):
        return False
        
    if "alternatives" not in diagnosis or not isinstance(diagnosis["alternatives"], list):
        return False
        
    if "contradicting_evidence" not in diagnosis or not isinstance(diagnosis["contradicting_evidence"], list):
        return False
        
    if "evidence_sufficiency" not in diagnosis or diagnosis["evidence_sufficiency"] not in ["sufficient", "partial"]:
        return False
        
    return True


def format_reasonchain(diagnosis: dict) -> str:
    """
    Formats the parsed diagnosis dictionary into a structured, user-facing
    ReasonChain explanation.
    """
    if not validate_diagnosis_json(diagnosis):
        return "Invalid Diagnosis Format. Cannot generate ReasonChain."
        
    root_cause = diagnosis["root_cause"]
    confidence = float(diagnosis["confidence"])
    evidence = diagnosis["evidence"]
    contradicting = diagnosis["contradicting_evidence"]
    alternatives = diagnosis["alternatives"]
    
    lines = []
    lines.append("POSSIBLE CAUSES")
    
    # 1. Primary Cause
    lines.append(f"1. {root_cause}")
    lines.append("Supporting evidence:")
    if evidence:
        for ev in evidence:
            lines.append(f"- {ev}")
    else:
        lines.append("- None provided")
        
    lines.append("Contradicting evidence:")
    if contradicting:
        for cev in contradicting:
            lines.append(f"- {cev}")
    else:
        lines.append("- None found")
        
    lines.append("Confidence:")
    lines.append(f"{int(confidence * 100)}%")
    lines.append("")
    
    # 2. Alternatives
    idx = 2
    for alt in alternatives:
        lines.append(f"{idx}. {alt}")
        lines.append("Supporting evidence:")
        lines.append("- Alternative hypothesis (evidence incomplete)")
        lines.append("Contradicting evidence:")
        lines.append("- None found")
        
        # Calculate a split remainder confidence for alternative
        alt_conf = max(0, min(100, int((1.0 - confidence) * 100 / len(alternatives)))) if len(alternatives) > 0 else 0
        lines.append("Confidence:")
        lines.append(f"{alt_conf}%")
        lines.append("")
        idx += 1
        
    # Summary
    lines.append("CURRENT MOST LIKELY CAUSE:")
    lines.append(root_cause)
    lines.append("")
    lines.append("WHY?")
    
    ev_summary = ", ".join(evidence) if evidence else "available observations"
    lines.append(f"The evidence supports this diagnosis ({ev_summary}) and no contradicting facts were found.")
    
    return "\n".join(lines)
