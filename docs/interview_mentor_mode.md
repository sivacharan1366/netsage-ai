# Interview Guide — Mentor Mode

This guide prepares the team for questions about the interactive Mentor Mode training feature.

---

## Short Summary

> "Mentor Mode is an interactive learning interface built directly into NetSage. It provides a concept overview followed by three progressive questions: conceptual understanding, diagnosis from CLI logs, and resolution commands. Questions unlock sequentially as the student answers correctly."

---

## Frequently Asked Interview Questions

### 1. Why did you use a local JSON file (`data/mentor_questions.json`) for the questions?
* **Answer**: Using a local JSON file ensures the questions load instantly, work completely offline, and remain consistent during a live demonstration. The questions are specifically aligned with the Cisco lab concepts used throughout the project.

### 2. Why did you use Streamlit's `session_state`?
* **Answer**: Streamlit reruns the script on each interaction, resetting regular Python variables. Using `st.session_state` allows persisting student progress (which level is unlocked, selected choices, and feedback) across reruns without needing an external database.

### 3. Why are there 3 progressive levels per topic?
* **Answer**: The 3 levels mirror the standard network troubleshooting workflow:
  1. **Level 1: Conceptual Understanding** — checks protocol fundamentals (e.g., how 802.1Q tagging or default routing works).
  2. **Level 2: Troubleshooting/Diagnosis** — presents CLI command logs and asks the student to identify the error signature.
  3. **Level 3: Resolution/Fix** — asks for the exact Cisco IOS configuration commands to fix the problem.

### 4. Why not generate questions dynamically using the LLM?
* **Answer**: Relying on live LLM generation for quizzes would introduce API latency, cost, and the risk of hallucinating invalid Cisco syntax. A curated JSON file guarantees reliable, accurate questions every time.

### 5. How does the sequential unlocking work?
* **Answer**: The current progress level (1, 2, or 3) is tracked in `st.session_state`. When the student submits a correct answer, the state increments, `st.rerun()` refreshes the interface, and the next level card unlocks.

### 6. What is a limitation of the current implementation?
* **Answer**: The question bank is fixed per concept rather than randomized from a large multi-question pool.

### 7. What could be improved in future versions?
* **Answer**: Expanding the question pool with randomized question selection, tracking student score history over time, and allowing instructors to import custom JSON question packs.
