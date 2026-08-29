# tests/test_mentor.py
import pytest
import json
from ai.mentor import load_mentor_questions, validate_question_format

# 1. JSON loads successfully and is valid
def test_mentor_questions_db_valid():
    q_data = load_mentor_questions()
    assert len(q_data) > 0
    assert validate_question_format(q_data) is True


# 2. Corrupt schema is rejected
def test_mentor_questions_corrupt_rejected():
    # Corrupt data: missing question list
    bad_data_1 = {
        "vlan": {
            "overview": "Overview text",
            # missing "questions"
        }
    }
    assert validate_question_format(bad_data_1) is False

    # Corrupt data: wrong question count (2 instead of 3)
    bad_data_2 = {
        "vlan": {
            "overview": "Overview text",
            "questions": [
                {
                    "question": "Q1",
                    "options": ["A", "B"],
                    "correct_answer": 0,
                    "hint": "Hint",
                    "explanation": "Exp"
                },
                {
                    "question": "Q2",
                    "options": ["A", "B"],
                    "correct_answer": 0,
                    "hint": "Hint",
                    "explanation": "Exp"
                }
            ]
        }
    }
    assert validate_question_format(bad_data_2) is False

    # Corrupt data: correct_answer out of options range
    bad_data_3 = {
        "vlan": {
            "overview": "Overview text",
            "questions": [
                {
                    "question": "Q1",
                    "options": ["A", "B"],
                    "correct_answer": 5,  # Invalid index
                    "hint": "Hint",
                    "explanation": "Exp"
                },
                {
                    "question": "Q2",
                    "options": ["A", "B"],
                    "correct_answer": 0,
                    "hint": "Hint",
                    "explanation": "Exp"
                },
                {
                    "question": "Q3",
                    "options": ["A", "B"],
                    "correct_answer": 0,
                    "hint": "Hint",
                    "explanation": "Exp"
                }
            ]
        }
    }
    assert validate_question_format(bad_data_3) is False
