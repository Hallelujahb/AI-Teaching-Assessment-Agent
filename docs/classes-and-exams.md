# Classes, exams, sign-in by id and forgotten passwords

## What a lecturer does
1. Classes page: make a class (a name and up to 10 students). A lecturer sees and edits only their own classes.
2. Assessments page, open an assessment, Assign: pick a class or individual students, and optionally a time limit in whole minutes (1 to 300).
3. Students hand in their answers. The assignment owns a normal submission batch, so Grade this batch works as before.
4. Once any grading run exists for the batch, the exam closes for students and the assignment cannot be removed.

## What a student does
My exams lists what was assigned. A timed exam hides the question until Start is pressed. The server keeps the clock
(30 seconds of grace) and accepts one answer of 1 to 2,000 characters. Students never receive the reference answer or the rubric.

## Rules kept
- At most 10 students per class and per assignment, because one assignment is one grading batch (limit of 10 answers).
- At most 20 batches per assessment, and batch names stay unique (a repeat gets "(2)").
- An assessment is locked once it is assigned or graded. Remove the assignment first to edit it.
- The student list is fixed when the assignment is made. Changing a class later does not change past assignments.
- All checks are on the server. The role is read from the database on every request.

## Sign in
Email, student id (ST001) or staff id (LT001), any letter case. The old `email` field still works in the API.

## Forgotten password
There is no email service (free hosting, no billing), so staff hand out the code.
1. The person asks for a code on the sign-in page. The reply is the same whether or not the account exists.
2. A lecturer (for students) or the super admin (for anyone) makes a code under Approvals and gives it over in person.
3. The person enters the id, the code and a new password. The code is 8 digits, works once, expires after 30 minutes
   and is locked after 5 wrong tries. Only a hash is stored.
4. The super admin has no one above them: run `python -m app.set_password EMAIL` from `backend/`.

Tests: `backend/tests/test_classes_exams.py` (needs `TEST_DATABASE_URL`, a throwaway database after setup_db, seed and seed_users).
