Review the working diff as a staff engineer who did not write it.

Check specifically:
1. Layer violations - logic in CLI or route bodies
2. Naive datetimes crossing the DB boundary
3. Time-dependent functions not taking `now`
4. Tests asserting on mocks or row counts instead of behaviour
5. Anything in CLAUDE.md's banned list

Be specific: file, line, why. If clean, say so in one line. Do not praise.
