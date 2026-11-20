# TaL3D Global Hunter 2.0 — Implementation and source status

This repository is **Global Hunter**; the separate `cults-radar` repository remains untouched.
The work is designed for a staged activation, with **no YouTube integration**.

## Pipeline (implemented)

1. **News ingestion** from the six original official/press RSS feeds; preserve source
   publication time, full-text status, ETag and errors. Never replace good data with a
   failed scan.
2. **Object extraction v5** rejects dangling sentence clauses and generic lines,
   records the source span and retires prior aliases without deleting historic records.
3. **Event/product/hypothesis separation:** `event_id`, `product_id`,
   `design_hypothesis.id` and source URLs, conservative exact-name identity.
   Fuzzy similarity alone never merges two editions.
4. **Competition:** bounded Cults3D searches (up to two variants per opportunity,
   four opportunities per run = nominally up to eight API calls); query-level
   sample sizes, deduplicated listings, no invented total or visual verification.
5. **Evidence:** community interest distinguishes generic enthusiasm from explicit
   STL requests. Optional human-reviewed imports require cited HTTPS URLs.
6. **Decision gates:** `WATCH`, `VALIDATE`, `DESIGN NOW`, `REJECT`,
   and `IGNORE`; never rely on a misleading unified score. DESIGN NOW needs
   two independent cited direct STL request sources and *explicit human
   validation* of demand, market gap, FDM and originality; it is not issued by
   unattended weak signals.
7. **FDM and dates:** shape-category FDM *risk estimate*, not a print test;
   seasonal deadline heuristics explicitly labelled, optional source-reviewed
   release date imports.
8. **History and feedback:** daily count of observed cited links (not search or
   sales volume), follow-up checkpoints after 30/60/90 days, manual feedback
   retained without self-modifying code.
9. **Arabic report:** actionable next check, summarized candidates, evidence
   completeness, hypothesis, FDM precheck, provisional timing and platform
   coverage. Archive and mail workflows remain the existing production code.

## Provider and activation matrix

| Source | Purpose | Mechanism | Active by default? |
|---|---|---|---|
| Existing 6 feeds | News | Existing RSS collection | Yes |
| Cults3D | STL competitor search | Existing authenticated GraphQL | Only with existing secrets |
| Printables, MakerWorld, MyMiniFactory, Thangs, Thingiverse | Competitor references | Reviewed HTTPS result export | No; import only |
| Reddit and other maker communities | STL demand discussion | Existing disabled authorized community feed, or reviewed observations | No; approval/access necessary |
| Etsy/eBay | Physical product listings | Reviewed cited references, *not* inferred sales | No; import only |
| AmiAmi, Good Smile, HobbyLink Japan | Announcements and dates | Reviewed cited release/calendar observations | No; import only |
| Google Trends/Pinterest Trends | Relative interest | Reviewed, source-linked relative-index exports | No; import only |
| TMDB | Movie/TV release-date candidates | Official bearer-token API, operator-specified title | No; opt-in |
| Anime/manga/game news beyond original feeds | New discovery | Source-by-source verified RSS setup | Not automatically added |
| YouTube | — | **Canceled completely** | No |

No unofficial Printables/MakerWorld API scraping is shipped. Each new access
path requires confirmed terms and credentials; a missing connector returns
`not_checked`, never "zero demand" or "zero competitors."

### Optional JSON imports (all files may be absent)

Only public URLs and operator-validated claims should be stored in this public
repository. Do **not** include private conversation text, tokens or personal info.

* `config/reviewed_evidence.json` — array entries:
  `{"opportunity_id":"<id>","url":"https://...","statement":"Where can I find the STL?","reviewed_by_human":true}`
* `config/external_market.json` — array entries:
  `{"opportunity_id":"<id>","platform":"printables","url":"https://www.printables.com/model/...","title":"...","reviewed_by_human":true}`
* `config/physical_market.json` — array entries:
  `{"opportunity_id":"<id>","platform":"etsy","url":"https://www.etsy.com/listing/...","observation":"listing","reviewed_by_human":true}`.
  `sold_verified` also requires `transaction_verified:true`.
* `config/trend_signals.json` — array entries:
  `{"opportunity_id":"<id>","source":"google_trends","url":"https://trends.google.com/trends/explore","relative_index":42,"period":"2026-W47","reviewed_by_human":true}`.
* `config/release_calendar.json` — array entries:
  `{"opportunity_id":"<id>","release_date":"2027-02-01","source_url":"https://...","verified_from_source":true}`.
* `config/reviewer_feedback.json` — array entries:
  `{"opportunity_id":"<id>","feedback":"needs_research","reviewed_by_human":true,"reviewed_at":"2026-11-20","validation":{"fdm_verified":true}}`.
* `config/tmdb_targets.json` — mapping of an opportunity to a movie/TV title
  for **TMDB** only:
  `{"opportunity_id":"<id>","media_title":"<exact movie title>","reviewed_by_human":true}`.

The importer validates shape, allowlisted URL hosts where appropriate, and
deduplicates each reviewed observation. Missing files are accepted; invalid
data cannot replace historic evidence.

### Optional TMDB activation

1. Obtain a TMDB application read token according to the current official terms.
2. Add it as GitHub Actions secret `TMDB_READ_TOKEN` **only** in Global Hunter.
3. Add repository Actions variable `HUNTER_TMDB_SHADOW=1`.
4. Curate `config/tmdb_targets.json` for exact title lookups.
5. Observe candidate results; TMDB candidates never become verified dates or
   buying demand automatically. Disable the variable to stop all TMDB requests.

Default is disabled. At most two requested title searches per run. Do not reuse
the canceled YouTube key.

## Validation and rollout

* `python -m pytest -q`
* `python main.py dry-run` (render from stored data, no external collection or email).
* The PR check `TaL3D V2 - Safe Preview From Stored Data` uploads HTML and
  uses **read-only GitHub permissions**.
* After merge, production scheduled collection may reprocess existing documents
  gradually (12 per run); original snapshots, report outbox and notification
  cadence stay intact. External source activation is *not* implied by merging.

### What this does *not* prove

No claim is made that named objects are visually verified, that FDM geometry
has been printed, that sample counts prove market saturation, that a source
offers licensed merchandise reproduction, or that any views/downloads equal
paid STL sales. No recommendation engine can manufacture missing buying data.
