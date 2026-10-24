# Known limitations

By scope (guide): short text answers only; demo-size data (one question, three answers); no handwriting recognition, plagiarism detection or student portal.

By hosting: free hosts sleep, so the first load after idle is slow; free AI quota is limited.

Injection protection is a prompt rule plus a keyword check, so it catches obvious attempts only.

A typed request is matched to an assessment and batch by keywords from titles and labels, not understood by the model; anything unclear gets a question.

The model must return valid JSON. Each run allows one retry; a student who fails twice goes to manual grading.

The agent's 60 second limit covers the whole run, so a slow free model can time out. Try again.

TODO: add problems observed during testing.
