# Skill health candidate collector

`collect_candidates.py` is the deterministic first stage of the weekly skill
health audit. It streams only recent active OpenClaw transcripts and outputs a
bounded JSON candidate index. Message bodies, tool arguments, and tool results
are never included in the output.

```bash
python3 jobs/skill-health/collect_candidates.py \
  --openclaw-root /Users/chumji/.openclaw \
  --days 7 \
  --max-candidates 5 \
  --max-sessions-per-candidate 3
```

The model reviews only the emitted candidate session references. Reset/deleted
archives and broad transcript enumeration are outside this collector's scope.
