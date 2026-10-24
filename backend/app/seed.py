"""Seed demo data. Run from backend/:  python -m app.seed   (safe to run twice)
Loads every seed/assessments/*.json. Command line only, never on host start.
ASSUMPTION (confirm with P2's schema.sql): tables assessments, rubric_criteria,
submission_batches, submissions; unique (batch_id, student_id); psycopg v3.
"""
import json, os, sys
from pathlib import Path
import psycopg

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "assessments"
MAX_ANSWER, MAX_BATCH = 2000, 10


def load_and_check() -> list:
    files = sorted(SEED_DIR.glob("*.json"))
    assert files, f"no seed files in {SEED_DIR}"
    items = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    for a in items:
        t, r = a["title"], a["rubric"]
        assert len(r) == 3, f"{t}: guide requires a three-criterion rubric"
        assert [c["position"] for c in r] == [1, 2, 3], f"{t}: bad positions"
        assert all(c["max_score"] > 0 for c in r), f"{t}: max_score must be > 0"
        assert a["reference_answer"].strip(), f"{t}: reference answer missing"
        for b in a["batches"]:
            ids = [s["student_id"] for s in b["submissions"]]
            assert len(ids) == len(set(ids)) <= MAX_BATCH, f"{b['label']}: duplicate ids or over {MAX_BATCH}"
            assert all(len(s["answer"]) <= MAX_ANSWER for s in b["submissions"]), f"{b['label']}: answer too long"
    return items


def ensure(cur, items: list) -> dict:
    n = {"assessments": 0, "batches": 0, "submissions": 0}
    for a in items:
        cur.execute("SELECT id FROM assessments WHERE title=%s", (a["title"],))
        row = cur.fetchone()
        if row:
            aid = row[0]
        else:
            cur.execute("INSERT INTO assessments (title, question, reference_answer) VALUES (%s,%s,%s) RETURNING id",
                        (a["title"], a["question"], a["reference_answer"]))
            aid = cur.fetchone()[0]
            n["assessments"] += 1
            for c in a["rubric"]:
                cur.execute("INSERT INTO rubric_criteria (assessment_id, position, name, description, max_score) VALUES (%s,%s,%s,%s,%s)",
                            (aid, c["position"], c["name"], c["description"], c["max_score"]))
        for b in a["batches"]:
            cur.execute("SELECT id FROM submission_batches WHERE assessment_id=%s AND label=%s", (aid, b["label"]))
            row = cur.fetchone()
            if row:
                bid = row[0]
            else:
                cur.execute("INSERT INTO submission_batches (assessment_id, label) VALUES (%s,%s) RETURNING id", (aid, b["label"]))
                bid = cur.fetchone()[0]
                n["batches"] += 1
            for s in b["submissions"]:
                cur.execute("INSERT INTO submissions (batch_id, student_id, answer) VALUES (%s,%s,%s) ON CONFLICT (batch_id, student_id) DO NOTHING",
                            (bid, s["student_id"], s["answer"]))
                n["submissions"] += cur.rowcount
    return n


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set.")
    items = load_and_check()
    with psycopg.connect(url) as conn, conn.cursor() as cur:  # one transaction
        print("Seed done. Added:", ensure(cur, items))


if __name__ == "__main__":
    main()
