from src.rag_system import answer

QUESTIONS = [
    "What are the discharge criteria for febrile seizure?",
    "What organisms cause bacterial gastroenteritis in children?",
    "What is the recommended dose of ibuprofen for adults?",   # out-of-scope — should say not found
]

for q in QUESTIONS:
    print("=" * 70)
    print(f"QUESTION: {q}")
    print("-" * 70)
    r = answer(q)
    print(r["answer"])
    print()
    print("Sources:", r["sources"])
    print()
    print("Retrieved chunks:")
    for c in r["retrieved_chunks"]:
        page = c["metadata"].get("page", "?")
        score = c["score"]
        cid = c["chunk_id"]
        print(f"  [{score:.3f}]  {cid}  (page {page})")
    print()
