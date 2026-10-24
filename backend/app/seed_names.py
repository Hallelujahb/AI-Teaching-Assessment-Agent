"""Give every existing account an Ethiopian name, and make sure each seeded student id has an account.
    python -m app.seed_names
Safe to run twice. Names are fictitious. Students are matched by student_id and lecturers by staff_id.
A student id with no account yet (ST003, PY002, PY003 only appear in seeded answers) gets an active
account: email <id>@qeleme.test, password <id>-student. Existing passwords are never touched.

Owner: P2
"""
import os
import sys

import psycopg
from dotenv import load_dotenv

from .auth import hash_password

load_dotenv()

STUDENTS = {
    "ST001": "Abebe Kebede", "ST002": "Selam Tesfaye", "ST003": "Dawit Haile", "ST004": "Meron Alemu",
    "ST005": "Yonas Bekele", "ST006": "Rahel Mengistu", "ST007": "Kidus Getachew", "ST008": "Liya Assefa",
    "ST009": "Natnael Desta", "ST010": "Eden Berhanu", "ST011": "Samuel Negash", "ST012": "Bethlehem Worku",
    "ST013": "Henok Tilahun", "ST014": "Saron Abera", "ST015": "Fikru Lemma", "ST016": "Mahlet Zewdu",
    "ST017": "Amanuel Shiferaw", "ST018": "Helina Gebre", "ST019": "Elias Mulugeta", "ST020": "Tsion Demeke",
    "ST021": "Nahom Taye", "ST022": "Ruth Aschalew", "ST023": "Bereket Fekadu", "ST024": "Birtukan Ayele",
    "ST025": "Yared Solomon",
    "PY001": "Hanna Girma", "PY002": "Biruk Tadesse", "PY003": "Tigist Wolde",
}
LECTURERS = {
    "LT001": "Dr. Mulugeta Assefa", "LT002": "Dr. Almaz Hailu", "LT003": "Dr. Getnet Abate",
    "LT004": "Dr. Senait Bogale", "LT005": "Dr. Tadesse Wondimu", "LT006": "Dr. Zenebech Kassa",
    "LT007": "Dr. Fasil Yimer", "LT008": "Dr. Genet Teshome", "LT009": "Dr. Mekonnen Ayalew",
    "LT010": "Dr. Wubit Dereje",
}


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set.")
    renamed = created = 0
    with psycopg.connect(url) as conn:
        for sid, name in STUDENTS.items():
            cur = conn.execute("UPDATE users SET name=%s WHERE role='student' AND student_id=%s", (name, sid))
            if cur.rowcount:
                renamed += 1
            elif sid in ("ST003", "PY002", "PY003"):   # ids used by seeded answers: give them an account
                cur = conn.execute(
                    "INSERT INTO users (email, name, role, student_id, password_hash, status) "
                    "VALUES (%s,%s,'student',%s,%s,'active') ON CONFLICT (email) DO NOTHING",
                    (f"{sid.lower()}@qeleme.test", name, sid, hash_password(f"{sid.lower()}-student")))
                created += cur.rowcount
        for code, name in LECTURERS.items():
            renamed += conn.execute("UPDATE users SET name=%s WHERE role='lecturer' AND staff_id=%s", (name, code)).rowcount
    print(f"Names set on {renamed} accounts, {created} accounts created.")


if __name__ == "__main__":
    main()
