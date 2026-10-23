# Actual Windows frozen UTF8 cause and fix verified

Sourcec45dc236/run39630607193: same0c4 product on the same native host, original acceptance unchanged. Baseline actual EXE logsutf8_mode0, completes0units with exact source/cache failure, exit1. Fixed actual EXE logsutf8_mode1, both original phasesPASS (14exercise+7resume checks), including first committed unit pause, restart without auto-resume, reuse without rewrite, unchanged confirmed replay, safe report and real window cleanup. Product source_matches_head and source unchanged true. EXE hashes recorded separately in utf8-comparison.json.

Cause: frozen interpreter locale settings differed from the source runner's UTF8. Explicit pinned PyInstaller bootloader Xutf8 resolves it; original cache integrity checks remain. This run did not execute source tests and did not publish; prior original176 Windows source cases passed at03a7. Final normal pipeline still requires176 and actualEXE/download verification.
