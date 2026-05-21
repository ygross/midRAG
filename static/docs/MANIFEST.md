# Corpus Manifest

**Corpus name:** Pediatric Hospital Medicine – Decision-Making & Case-Based Reference

**Domain:** Pediatric medicine (hospital medicine, decision-making, clinical reasoning)

**Source of documents:**

| File | Full title | Year | Publisher |
|---|---|---|---|
| `Kliegman_Pediatric Decision-Making Strategies_2015.pdf` | Pediatric Decision-Making Strategies | 2015 | Elsevier |
| `A Case-Based Educational Guide-American Academy of Pediatrics (2022).pdf` | Pediatric Hospital Medicine: A Case-Based Educational Guide | 2022 | AAP |

**Number of documents (PDF files):** 2

**Approximate number of pages / tokens:**
- Kliegman: 371 pages (~150 000 tokens)
- AAP Case-Based: 785 pages (~380 000 tokens)
- **Total: 1 156 pages / ~530 000 tokens**

**File types:** PDF (`.pdf`)

**License / permission:**
These are published textbooks used strictly for educational purposes as part of a university ML course project. No redistribution. The corpus will not be published or shared publicly.

**Why this corpus is suitable for RAG:**

1. **Non-trivial for LLMs without retrieval.** Strong general-purpose LLMs do not have reliable access to the specific case details, decision tree logic, numbered annotations, and drug/dosing recommendations found in these books. A baseline LLM would produce vague or incorrect answers to questions like "What are the exact discharge criteria for Simon the febrile seizure patient?" without retrieval.

2. **Rich factual density.** Both books contain dense clinical facts — differential diagnoses, age-specific findings, management protocols, named patient cases, specific measurements (e.g., "≥4 hours of pulse oximetry", "acute = <10 days") — that are ideal for precise retrieval evaluation.

3. **Two complementary structures.** The Kliegman book provides symptom-first decision trees with numbered footnotes, while the AAP book uses named patient scenarios in Q&A format. This variety tests the retriever across different text styles.

4. **50+ named patient cases.** Each AAP case has a unique patient (name, age, chief complaint), creating a rich evaluation space for specific factual questions.

**What kind of questions should the system answer:**

- *Factual:* "What is the most urgent diagnosis to rule out in scrotal pain?"
- *Case-specific:* "What are the discharge criteria for Simon's febrile seizure?"
- *Procedural:* "What physical examination is required for Baby Girl Smith?"
- *Differential diagnosis:* "What organisms cause bacterial gastroenteritis in children?"
- *Absence/negation:* "Does a sunken fontanel indicate hydrocephalus?"
- *Comparison:* "How does acute rhinorrhea differ from chronic rhinorrhea?"
- *Numerical:* "For how long should higher-risk BRUE infants be monitored with pulse oximetry?"

**Privacy / sensitivity:**
All source material is published textbook content. No private patient data. The named patients in the AAP book (Emma, Simon, etc.) are fictional teaching cases.
