# Branch cleanup — 2026-05-29

Triage and disposition of the `claude/*` working branches. Every
deleted branch was first archived as a lightweight tag
`archive/<branch-with-slashes-as-dashes>` pointing at its tip commit,
so any branch is fully restorable.

## Summary

| Bucket | Count | Disposition |
|---|---:|---|
| Merged-PR branches (content in `dev`) | 121 | archived + deleted |
| Closed-unmerged-PR branches | 3 | archived + deleted |
| Orphan branches, no PR (superseded) | 19 | archived + deleted |
| Open-PR branch #216 `fix-decimal-silence` (merged this session) | 1 | merged → archived + deleted |
| Open-PR branch #215 `measure-full-vtm1-corpus-sample` | 1 | kept until merge |
| Orchestrator branch `claude/wonderful-keller-S7SCC` | 1 | kept |

**144 archive tags** created; **143 + 1 (post-merge)** branches deleted.
Remaining heads after cleanup: `dev`, `main`, `claude/measure-full-vtm1-corpus-sample` (until #215 merges), and this orchestrator branch.

## Restore any branch

```bash
# tag -> branch
git push origin refs/tags/archive/claude-<slug>:refs/heads/claude/<slug>
# or via REST:
curl -H "Authorization: Bearer $GH_TOKEN" -X POST \
  https://api.github.com/repos/pktck/dectalk-python/git/refs \
  -d '{"ref":"refs/heads/claude/<slug>","sha":"<tip-sha>"}'
```

GitHub also offers one-click "Restore branch" on each merged/closed PR.

## Two parity leads salvaged from deleted branches

These ideas are preserved in their archive tags; verify before acting
(both reference now-CLOSED issues and may already be handled differently):

- **VTM "UI" samples/frame 110 → 71** — `archive/claude-recalibrate-ui-71-issue152`, `archive/claude-fix-default-speaker-ui-issue152` (issue #152). PR #214 reportedly closed ~95% of the UI=110 gap via another path; confirm whether 71 is still warranted.
- **Thread `SpdChip` F4/B4/F5/B5 into `parstochip_to_llframe_delayed`** — `archive/claude-thread-f4b5-from-spdchip-issue159` (issue #159). A sibling branch merged for #159; confirm coverage.

## Full disposition

### Merged-PR branches (content already in dev) — 121

| Branch | Archive tag | Tip SHA |
|---|---|---|
| `claude/abbreviation-policy-issue146` | `archive/claude-abbreviation-policy-issue146` | `01ddc94fdfcd` |
| `claude/agent-attribution-Kp7mQ` | `archive/claude-agent-attribution-Kp7mQ` | `d4555ecca956` |
| `claude/align-b4-b5-issue143` | `archive/claude-align-b4-b5-issue143` | `481032fde88e` |
| `claude/apply-vol-att-issue160-v2` | `archive/claude-apply-vol-att-issue160-v2` | `1fa79b4969e1` |
| `claude/arpabet-alias-issue62` | `archive/claude-arpabet-alias-issue62` | `f20f83e04a5b` |
| `claude/audit-f0-contour-issue75` | `archive/claude-audit-f0-contour-issue75` | `dc4624b1d004` |
| `claude/audit-init-phclause-issue74` | `archive/claude-audit-init-phclause-issue74` | `056c22780b1d` |
| `claude/audit-kernel-textnorm-issue90` | `archive/claude-audit-kernel-textnorm-issue90` | `b15f1420d071` |
| `claude/audit-klatt-frame-issue86` | `archive/claude-audit-klatt-frame-issue86` | `307518662dac` |
| `claude/audit-ksdt-issue84` | `archive/claude-audit-ksdt-issue84` | `42999375a4a3` |
| `claude/audit-lts-issue89` | `archive/claude-audit-lts-issue89` | `1127790c4b66` |
| `claude/audit-parstochip-issue87` | `archive/claude-audit-parstochip-issue87` | `2099586e67a1` |
| `claude/audit-spdchip-issue85` | `archive/claude-audit-spdchip-issue85` | `78ce78bc51ce` |
| `claude/audit-vtm-issue83` | `archive/claude-audit-vtm-issue83` | `01a584586812` |
| `claude/c-oracle-shard16-Lm3vT` | `archive/claude-c-oracle-shard16-Lm3vT` | `f190d981397e` |
| `claude/claude-md-foreground-merge-fix` | `archive/claude-claude-md-foreground-merge-fix` | `5cbd26e6f9e2` |
| `claude/claude-md-merge-loop-docs` | `archive/claude-claude-md-merge-loop-docs` | `87bf95db0b95` |
| `claude/claude-md-stall-prevention` | `archive/claude-claude-md-stall-prevention` | `bdc78da77e3c` |
| `claude/close-remaining-parity-gap` | `archive/claude-close-remaining-parity-gap` | `26b71ce1a8a1` |
| `claude/close-residual-parity-gap` | `archive/claude-close-residual-parity-gap` | `28efadcfc048` |
| `claude/close-schwa-drift` | `archive/claude-close-schwa-drift` | `a455e72a0791` |
| `claude/compound-marker-issue134` | `archive/claude-compound-marker-issue134` | `d691e6a50496` |
| `claude/date-pattern-issue145-noop` | `archive/claude-date-pattern-issue145-noop` | `e9c464da690c` |
| `claude/diagnostic-phsettar-state` | `archive/claude-diagnostic-phsettar-state` | `5e5718a7ed4e` |
| `claude/docs-plan-bit-parity-Wm4Rj` | `archive/claude-docs-plan-bit-parity-Wm4Rj` | `cd60d47be6ee` |
| `claude/exclaim-symbol-issue212` | `archive/claude-exclaim-symbol-issue212` | `057d41010fd9` |
| `claude/expand-corpus-issue166` | `archive/claude-expand-corpus-issue166` | `f74b7999e43d` |
| `claude/f0-ceiling-issue125` | `archive/claude-f0-ceiling-issue125` | `c5cbae875fab` |
| `claude/f0-contour-audit-issue75` | `archive/claude-f0-contour-audit-issue75` | `2059bf22e4c5` |
| `claude/fake-hlsyn-audit-issue165-v2` | `archive/claude-fake-hlsyn-audit-issue165-v2` | `3f823e41a7de` |
| `claude/fix-frame0-init-issue148` | `archive/claude-fix-frame0-init-issue148` | `4333d71794bf` |
| `claude/fix-frontend-underrun-issue201` | `archive/claude-fix-frontend-underrun-issue201` | `a464100316f1` |
| `claude/fix-hl-unit-conv-issue124` | `archive/claude-fix-hl-unit-conv-issue124` | `ca7e8dbfba3c` |
| `claude/fix-init-timing-issue155` | `archive/claude-fix-init-timing-issue155` | `0018421d953d` |
| `claude/fix-leading-frame-bleed-issue157` | `archive/claude-fix-leading-frame-bleed-issue157` | `fee561d657a3` |
| `claude/fix-rate-wpm-issue70` | `archive/claude-fix-rate-wpm-issue70` | `bce1e3b42e90` |
| `claude/fix-ruff-format-blockers` | `archive/claude-fix-ruff-format-blockers` | `a5aa1387fbe4` |
| `claude/fix-sp-gettar-lint-block` | `archive/claude-fix-sp-gettar-lint-block` | `71f7d217ecfb` |
| `claude/fix-test-lint-blockers` | `archive/claude-fix-test-lint-blockers` | `6fc91f2f546e` |
| `claude/fix-tradition-test-conflict` | `archive/claude-fix-tradition-test-conflict` | `7845ecf7d1dc` |
| `claude/fix-trailing-silence-issue72` | `archive/claude-fix-trailing-silence-issue72` | `67249ed3cfad` |
| `claude/form-class-disambiguator-issue144` | `archive/claude-form-class-disambiguator-issue144` | `f9e1908d99bf` |
| `claude/frame-parity-audit-issue86` | `archive/claude-frame-parity-audit-issue86` | `10ac7f589375` |
| `claude/full-pipeline-skeleton` | `archive/claude-full-pipeline-skeleton` | `5cbade69cbed` |
| `claude/hlsyn-pump-helper` | `archive/claude-hlsyn-pump-helper` | `0ecf0d6ae72f` |
| `claude/initial-cluster-silent-issue127` | `archive/claude-initial-cluster-silent-issue127` | `9ffcf2f22f88` |
| `claude/issue-driven-agent-workflow` | `archive/claude-issue-driven-agent-workflow` | `bf9fa45c3980` |
| `claude/ix-vs-ah-issue133` | `archive/claude-ix-vs-ah-issue133` | `11d5b2914ba6` |
| `claude/latinate-stress-issue132` | `archive/claude-latinate-stress-issue132` | `6406d3200ec9` |
| `claude/lexicon-resource-issue128` | `archive/claude-lexicon-resource-issue128` | `b77530078bf3` |
| `claude/load-assertiveness-issue122` | `archive/claude-load-assertiveness-issue122` | `245fcc612d86` |
| `claude/lts-silent-letter-issue127` | `archive/claude-lts-silent-letter-issue127` | `f3ff37020cb2` |
| `claude/lts-vowel-mispredictions-issue140` | `archive/claude-lts-vowel-mispredictions-issue140` | `51ea286ecf05` |
| `claude/non-us-special-coartic-issue136-v3` | `archive/claude-non-us-special-coartic-issue136-v3` | `71101f589fd8` |
| `claude/one-homograph-issue212` | `archive/claude-one-homograph-issue212` | `878b4e28cb7b` |
| `claude/ough-variants-issue135` | `archive/claude-ough-variants-issue135` | `642ab7d93514` |
| `claude/palatalisation-rules-issue131` | `archive/claude-palatalisation-rules-issue131` | `1b168ff5f76b` |
| `claude/parity-audit-2026-05-23-v3` | `archive/claude-parity-audit-2026-05-23-v3` | `accfcddf80e7` |
| `claude/parity-audit-issue58` | `archive/claude-parity-audit-issue58` | `8e37f486fbf5` |
| `claude/parstochip-out-ph-issue141` | `archive/claude-parstochip-out-ph-issue141` | `320e5e020dad` |
| `claude/parstochip-to-llframe-adapter` | `archive/claude-parstochip-to-llframe-adapter` | `535f94eb04c1` |
| `claude/per-frame-out-t0-test-issue149-v2` | `archive/claude-per-frame-out-t0-test-issue149-v2` | `f4289ae8d647` |
| `claude/per-stage-parity-issue150-v2` | `archive/claude-per-stage-parity-issue150-v2` | `ca21fe919ad5` |
| `claude/perf-bench-issue3` | `archive/claude-perf-bench-issue3` | `6520a46f8155` |
| `claude/phinton-rule9-goto-issue73` | `archive/claude-phinton-rule9-goto-issue73` | `e28d47cf169c` |
| `claude/pht0draw-female-issue41` | `archive/claude-pht0draw-female-issue41` | `aca6bf7bd999` |
| `claude/port-cmd-par-rule-issue-38-rebased` | `archive/claude-port-cmd-par-rule-issue-38-rebased` | `82b2e8016301` |
| `claude/port-fr-gettar-issue82` | `archive/claude-port-fr-gettar-issue82` | `0c2a9dd51d06` |
| `claude/port-getbegtar-getendtar` | `archive/claude-port-getbegtar-getendtar` | `cf3fd53696d8` |
| `claude/port-getbegtar-getendtar-coartic-dispatch` | `archive/claude-port-getbegtar-getendtar-coartic-dispatch` | `891bd7f43b24` |
| `claude/port-gr-gettar-issue79` | `archive/claude-port-gr-gettar-issue79` | `848cba72a6e7` |
| `claude/port-hlsyn-circuit-issue-39` | `archive/claude-port-hlsyn-circuit-issue-39` | `4cc0badfc6ee` |
| `claude/port-hlsyn-nasalf1x-issue-40` | `archive/claude-port-hlsyn-nasalf1x-issue-40` | `12698c982275` |
| `claude/port-la-gettar-issue80` | `archive/claude-port-la-gettar-issue80` | `aaad2f0c1368` |
| `claude/port-lineartilt-and-frame-delay` | `archive/claude-port-lineartilt-and-frame-delay` | `83cec5218bc1` |
| `claude/port-par-pars1-issue126` | `archive/claude-port-par-pars1-issue126` | `d9e072376a54` |
| `claude/port-ph-phsettar-AdwAE` | `archive/claude-port-ph-phsettar-AdwAE` | `e76bfbebdb7f` |
| `claude/port-ph-setallofeats-issue63` | `archive/claude-port-ph-setallofeats-issue63` | `1de848f42f8e` |
| `claude/port-ph-setar-dispatch-issue48` | `archive/claude-port-ph-setar-dispatch-issue48` | `f30c8ef9b1d1` |
| `claude/port-ph-sort-issue49` | `archive/claude-port-ph-sort-issue49` | `c1d6af9403dd` |
| `claude/port-ph-stage-python-a1ewa` | `archive/claude-port-ph-stage-python-a1ewa` | `9cd7772533af` |
| `claude/port-phalloph2-issue69` | `archive/claude-port-phalloph2-issue69` | `7ac895583261` |
| `claude/port-phdraw` | `archive/claude-port-phdraw` | `a58d369a8117` |
| `claude/port-phdraw-1594-2398-issue71` | `archive/claude-port-phdraw-1594-2398-issue71` | `9c00247c597d` |
| `claude/port-phdraw-chunk2-issue34` | `archive/claude-port-phdraw-chunk2-issue34` | `7bc1a7d1ba22` |
| `claude/port-phdraw-chunk2-remainder-issue59` | `archive/claude-port-phdraw-chunk2-remainder-issue59` | `08a2237a3fc0` |
| `claude/port-phdraw-chunk3-issue-35` | `archive/claude-port-phdraw-chunk3-issue-35` | `ac6133373a8c` |
| `claude/port-phdraw-chunk4-issue-37` | `archive/claude-port-phdraw-chunk4-issue-37` | `e5ab316c6c5a` |
| `claude/port-phdraw-hlsyn-area-loop` | `archive/claude-port-phdraw-hlsyn-area-loop` | `274144a0007f` |
| `claude/port-phinton-and-hook-fail-fast` | `archive/claude-port-phinton-and-hook-fail-fast` | `8667c14828a4` |
| `claude/port-phinton-issue50` | `archive/claude-port-phinton-issue50` | `8921f373e824` |
| `claude/port-phsettar-milestone` | `archive/claude-port-phsettar-milestone` | `4a40cd00d1ba` |
| `claude/port-phsettar-orchestrator` | `archive/claude-port-phsettar-orchestrator` | `da8a4579e5d6` |
| `claude/port-phsettar-smooth-rules` | `archive/claude-port-phsettar-smooth-rules` | `122a72d2a043` |
| `claude/port-pht0draw-issue-33` | `archive/claude-port-pht0draw-issue-33` | `12526b7f8b23` |
| `claude/port-seed-speaker-state` | `archive/claude-port-seed-speaker-state` | `80c79a6c5a31` |
| `claude/port-setloc-issue51` | `archive/claude-port-setloc-issue51` | `008c51129954` |
| `claude/port-sp-gettar-issue81` | `archive/claude-port-sp-gettar-issue81` | `d2da7781db5d` |
| `claude/port-uk-gettar-issue78` | `archive/claude-port-uk-gettar-issue78` | `38c7ed396f0f` |
| `claude/port-us-phalloph` | `archive/claude-port-us-phalloph` | `dfd34b258c10` |
| `claude/port-us-phinton` | `archive/claude-port-us-phinton` | `75a3026f107f` |
| `claude/port-us-phtiming` | `archive/claude-port-us-phtiming` | `baa5d807e5aa` |
| `claude/port-us-phtiming-issue199-v2` | `archive/claude-port-us-phtiming-issue199-v2` | `7c13e41b69be` |
| `claude/port-vtm3-issue158` | `archive/claude-port-vtm3-issue158` | `fe44e308b6cd` |
| `claude/re-audit-parity-issue68` | `archive/claude-re-audit-parity-issue68` | `781e3270833e` |
| `claude/refine-symbol-stream-issue156` | `archive/claude-refine-symbol-stream-issue156` | `2e3d1d35a7f3` |
| `claude/refresh-status-issue88` | `archive/claude-refresh-status-issue88` | `c4e98a292103` |
| `claude/refresh-tasks-post-205` | `archive/claude-refresh-tasks-post-205` | `e2296d3acd48` |
| `claude/remove-leading-gensil-issue139` | `archive/claude-remove-leading-gensil-issue139` | `54a587f08879` |
| `claude/restore-leading-silence-issue200` | `archive/claude-restore-leading-silence-issue200` | `68899b7cf6ad` |
| `claude/route-through-parse-issue64-retry` | `archive/claude-route-through-parse-issue64-retry` | `ad9e2223c4e4` |
| `claude/spdefs-voice-threading-issue164` | `archive/claude-spdefs-voice-threading-issue164` | `d7b15aab3074` |
| `claude/thread-spdchip-f4b5-issue159` | `archive/claude-thread-spdchip-f4b5-issue159` | `a7717cf6198c` |
| `claude/verify-hlsyn-parity-issue91` | `archive/claude-verify-hlsyn-parity-issue91` | `ab4ed83d7959` |
| `claude/vtm-dump-hooks-issue151-v2` | `archive/claude-vtm-dump-hooks-issue151-v2` | `401c4ff09980` |
| `claude/vtm3-full-port-issue158` | `archive/claude-vtm3-full-port-issue158` | `70b58ebc7ded` |
| `claude/widen-sample-count-bounds` | `archive/claude-widen-sample-count-bounds` | `06f3c1031afe` |
| `claude/wire-all-phsort-issue94` | `archive/claude-wire-all-phsort-issue94` | `98bfd2d7d12c` |
| `claude/wire-init-timing` | `archive/claude-wire-init-timing` | `8f52b911ada6` |
| `claude/wire-phdraw-and-disable-hook` | `archive/claude-wire-phdraw-and-disable-hook` | `956a0c39e54d` |
| `claude/wire-phinton` | `archive/claude-wire-phinton` | `caad81e81c43` |

### Closed-unmerged-PR branches (abandoned/superseded) — 3

| Branch | Archive tag | Tip SHA |
|---|---|---|
| `claude/eval-vtm1-default` | `archive/claude-eval-vtm1-default` | `1c308e56ab91` |
| `claude/switch-to-full-pipeline-default` | `archive/claude-switch-to-full-pipeline-default` | `c16cc1509daa` |
| `claude/wire-us-phalloph-issue121` | `archive/claude-wire-us-phalloph-issue121` | `e0db2bc403c9` |

### Orphan branches, no PR (superseded leftovers, all map to CLOSED issues) — 19

| Branch | Archive tag | Tip SHA |
|---|---|---|
| `claude/audit-back-smooth-hlsyn-skips` | `archive/claude-audit-back-smooth-hlsyn-skips` | `a7ecd5ecb2b6` |
| `claude/corpus-expansion-issue166` | `archive/claude-corpus-expansion-issue166` | `93226022cd23` |
| `claude/date-pattern-issue145` | `archive/claude-date-pattern-issue145` | `3843c4a17c2c` |
| `claude/fix-default-speaker-ui-issue152` | `archive/claude-fix-default-speaker-ui-issue152` | `21f9dc2d7503` |
| `claude/lts-compound-marker-sidecars` | `archive/claude-lts-compound-marker-sidecars` | `0507675449cc` |
| `claude/lts-initial-cluster-issue127` | `archive/claude-lts-initial-cluster-issue127` | `a701e2861eab` |
| `claude/lts-ough-variants-issue135` | `archive/claude-lts-ough-variants-issue135` | `062b7d2d25e8` |
| `claude/lts-vowel-fixes-issue140` | `archive/claude-lts-vowel-fixes-issue140` | `0507675449cc` |
| `claude/per-stage-parity-tests-issue150` | `archive/claude-per-stage-parity-tests-issue150` | `64dd9a14b7b8` |
| `claude/phinton-rule9-issue73` | `archive/claude-phinton-rule9-issue73` | `da8160333880` |
| `claude/port-cmd-par-rule-match-input` | `archive/claude-port-cmd-par-rule-match-input` | `aee46b56f04e` |
| `claude/port-hlframe-hl-to-ll` | `archive/claude-port-hlframe-hl-to-ll` | `c051930404ba` |
| `claude/port-non-us-locus-tables` | `archive/claude-port-non-us-locus-tables` | `89b1fd6a77e7` |
| `claude/port-phdraw-chunk3-state-machine` | `archive/claude-port-phdraw-chunk3-state-machine` | `a8aaa7dd9d9e` |
| `claude/port-phdraw-chunk4-issue-37-rebased` | `archive/claude-port-phdraw-chunk4-issue-37-rebased` | `e5ab316c6c5a` |
| `claude/port-phdraw-remainder-issue71` | `archive/claude-port-phdraw-remainder-issue71` | `da8160333880` |
| `claude/port-us-all-phsort-v2` | `archive/claude-port-us-all-phsort-v2` | `58087b2d8f5b` |
| `claude/recalibrate-ui-71-issue152` | `archive/claude-recalibrate-ui-71-issue152` | `f7051420d922` |
| `claude/thread-f4b5-from-spdchip-issue159` | `archive/claude-thread-f4b5-from-spdchip-issue159` | `b8f359342dbc` |