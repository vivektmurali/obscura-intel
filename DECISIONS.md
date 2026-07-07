# Decisions log

Running log of autonomous implementation decisions per CLAUDE.md rule 5.

## Phase 0

- **GDELT rate limiting is aggressive from this network.** The 5s inter-call sleep in the HANDOVER.md template was insufficient — hit 429 repeatedly, once requiring ~4 min of cumulative backoff before succeeding. Changed `scripts/00_smoke_gdelt.py` to: 20s sleep between calls, retry loop on 429 with linear backoff (30s * attempt, up to 6 attempts). Future scripts pulling GDELT in bulk (Phase 1+) must budget for this — expect real wall-clock cost, not just the nominal 5s/call from the handover.
- **JSON shapes matched the handover template's assumptions exactly**: `artlist` → `{"articles": [...]}` with `seendate`/`title` keys; `timelinevolraw`/`timelinetone` → `{"timeline": [{"data": [...]}]}`. No parsing changes needed beyond the above.
- **`sourcecountry:IN` returns mixed-language results**, including Hindi-script headlines (e.g. "Tata Motors बनी देश की नंबर 2 कार कंपनी"), not just English-language Indian sources. This matters for later qualitative sampling (Phase 2 `event_samples.csv`) — some headlines will need translation context to assess "does this spike correspond to real identifiable news." Not a blocker, just a fact to carry forward.
- **Windows console encoding fix**: default Python stdout on this machine is cp1252, which cannot print the Hindi-script headlines above and crashes with `UnicodeEncodeError`. Added `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at the top of `00_smoke_gdelt.py`. Same fix will be needed in any future script that prints raw GDELT text.
