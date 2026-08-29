# ai/mentor.py
import json
import sys
from pathlib import Path

# Ensure Windows UTF-8 stdout/stderr handles are safe (if run directly)
if sys.platform.startswith('win') and __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DEFAULT_QUESTIONS_PATH = "data/mentor_questions.json"


def load_mentor_questions(path: str = DEFAULT_QUESTIONS_PATH) -> dict:
    """Loads the mentor Q&A JSON database."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading mentor questions: {e}", file=sys.stderr)
        return {}


def validate_question_format(q_data: dict) -> bool:
    """
    Validates the structure of the loaded mentor questions dictionary.
    Returns True if valid, False otherwise.
    """
    if not isinstance(q_data, dict):
        return False
        
    expected_categories = {"vlan", "routing", "dhcp", "dns", "acl", "nat", "gateway", "wireless", "interface"}
    
    # Check that at least some valid categories are present
    if not expected_categories.issubset(set(q_data.keys())):
        return False
        
    for cat, content in q_data.items():
        if not isinstance(content, dict):
            return False
            
        if "overview" not in content or not isinstance(content["overview"], str):
            return False
            
        if "questions" not in content or not isinstance(content["questions"], list):
            return False
            
        q_list = content["questions"]
        if len(q_list) != 3:
            return False
            
        for q in q_list:
            if not isinstance(q, dict):
                return False
                
            required_keys = {"question", "options", "correct_answer", "hint", "explanation"}
            if not required_keys.issubset(set(q.keys())):
                return False
                
            if not isinstance(q["question"], str):
                return False
                
            if not isinstance(q["options"], list) or len(q["options"]) < 2:
                return False
                
            for opt in q["options"]:
                if not isinstance(opt, str):
                    return False
                    
            try:
                ans_idx = int(q["correct_answer"])
                if not (0 <= ans_idx < len(q["options"])):
                    return False
            except (ValueError, TypeError):
                return False
                
            if not isinstance(q["hint"], str) or not q["hint"]:
                return False
                
            if not isinstance(q["explanation"], str) or not q["explanation"]:
                return False
                
    return True
