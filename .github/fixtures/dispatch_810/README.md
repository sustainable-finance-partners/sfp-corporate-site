# Dispatch 810 (byte copy)

This is the file the corporate-site strings of 810 section 4 were generated from, taken 2026-11-06. The 810 rows of `.github/signed_strings.json` were generated from this copy by programmatic extraction (`.github/scripts/dispatch_810_strings.py --write`); no string was retyped.

How the copy is checked:
- `dispatch_810_strings.py --check` (in CI) re-derives every row from this file, asserts byte equality, and pins the file's size and SHA-256.
- `signed_strings_check.py` proves each string renders at its targets. At the desk, with `--source-root`, it also re-extracts each string from the original.

| Copy | Source | Bytes | SHA-256 |
|---|---|---|---|
| `dispatch_810_20261106.md` | `Sustainable Finance Partners Business Apparatus/00_Operating_Model/CCO_DISPATCH_810_809_HANDBACK_3_RULED_Q_DEPLOY_B_BY_FACT_FIVE_PRS_CLEARED_31_PRE_ENGINE_SENTINEL_CLASSED_THREE_WITHDRAWN_RPS_NOTE_SIGNED_AUDIT_KINDS_PERMANENT_MIGRATION_RUN_BURN_RULE_20261106.md` (COO, 2026-11-06, v2; section 4 "Corporate #24", line 26: the Privacy Policy header and the AP2 mandate claim-state) | 9288 | `6812b2b25843eef76f5388a67ed21a71ba51c418b3f5ad386a19dbe3a8794361` |

The copy is LF-only, so its house pin (sha256 after CRLF→LF, first 16 hex) is `6812b2b25843eef7`. `.gitattributes` marks this folder `-text`, so every checkout holds the same bytes.
