# Interview Guide — Streamlit Dashboard

This guide prepares the team for questions about the interactive Streamlit dashboard.

---

## Short Summary

> "The dashboard provides an interactive view of NetSage's troubleshooting workflow. Users can filter cases by category, severity, and OSI layer, and the KPIs and charts are recalculated dynamically from the filtered dataset."

---

## Frequently Asked Interview Questions

### 1. Why did you choose Streamlit for this project?
* **Answer**: Streamlit allows building interactive web dashboards in pure Python without needing a separate frontend stack (HTML/CSS/React) or complex API routing. This keeps the application simple to run, maintain, and explain.

### 2. Why did you use Matplotlib inside Streamlit?
* **Answer**: Matplotlib provides reliable offline plotting and was used for generating static summary charts. Reusing the Matplotlib figure generation in Streamlit via `st.pyplot()` avoids adding extra heavy graphing libraries while maintaining consistent colors and layouts.

### 3. How does data filtering work?
* **Answer**: In `dashboard.py`, the `filter_cases_by_criteria` helper filters the in-memory case list based on the categories, severities, and OSI layers selected in the sidebar.

### 4. How are the KPIs calculated?
* **Answer**: KPIs are computed dynamically in `calculate_kpis` from the filtered lists (total cases, diagnoses count, approval rate, verified count, and vault entries). If a filter yields zero reviews, the approval rate safely returns `0.0%` to avoid division by zero.

### 5. How do you ensure metrics are real and not hardcoded?
* **Answer**: All metric cards and charts are computed directly from the active files (`cases.csv`, `ai_diagnoses.csv`, `human_review_log.csv`, and `data/memory.json`). No summary numbers are hardcoded.

### 6. How does the dashboard load project data?
* **Answer**: The dashboard reads the local CSV files and the JSON vault file when the script runs. Each sidebar filter change triggers a Streamlit rerun, updating all metrics and charts immediately.

### 7. What is a limitation of the current design?
* **Answer**: For large datasets with tens of thousands of rows, reading raw CSV files from disk on every rerun would become slower without caching.

### 8. What is a future improvement?
* **Answer**: Adding Streamlit data caching (`@st.cache_data`) or migrating to a lightweight database like SQLite for faster indexed queries as data volume grows.
