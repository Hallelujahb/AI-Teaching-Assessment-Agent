"""Seed demo data. Run from backend/:
    python -m app.seed            add demo data only if missing (safe to run twice)
    python -m app.seed --reset    wipe runs, proposals, results and added batches, then reseed
Loads every seed/assessments/*.json that has a rubric (placeholders are skipped).
Assessments are matched by title; the database assigns integer ids (SERIAL).
--reset restarts ids, so JS101 is always id 1 and its first batch is id 1.
Reads DATABASE_URL from the environment or backend/.env. Command line only.
Owner: P5. Matches schema.sql.
"""
import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

SEED_DIR = Path(__file__).resolve().parents[2] / "seed" / "assessments"
MAX_ANSWER, MAX_BATCH = 2000, 10


def load_and_check() -> list:
    items = []
    for f in sorted(SEED_DIR.glob("*.json")):
        a = json.loads(f.read_text(encoding="utf-8"))
        if "rubric" not in a:
            print(f"skipping {f.name}: no rubric (placeholder)")
            continue
        items.append(a)
    assert items, f"no usable seed files in {SEED_DIR}"
    for a in items:
        t, r = a.get("title", "?"), a["rubric"]
        assert a.get("title", "").strip(), "title is required"
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
        sys.exit("DATABASE_URL is not set (put it in backend/.env).")
    items = load_and_check()
    with psycopg.connect(url) as conn, conn.cursor() as cur:  # one transaction
        if "--reset" in sys.argv[1:]:
            cur.execute("TRUNCATE reviewed_results, ai_proposals, tool_logs, grading_runs, submissions, "
                        "submission_batches, rubric_criteria, assessments RESTART IDENTITY CASCADE")
            print("Reset: demo data, runs, proposals and results wiped.")
        print("Seed done. Added:", ensure(cur, items))


if __name__ == "__main__":
    main()