# Historical HTML samples

Retrieved on 2026-09-07 from:

- https://www.fantacalcio.it/voti-fantacalcio-serie-a/2023-24/1
- https://www.fantacalcio.it/voti-fantacalcio-serie-a/2024-25/1
- https://www.fantacalcio.it/voti-fantacalcio-serie-a/2025-26/38

The gzip files retain season/matchday selectors, fixture menu entries, and team
rating tables. Navigation, advertisements, scripts, and other unrelated markup
were removed. Tests use the original attributes, provider headings, player
links, coaches, event counts, and card classes.

The missing gzip files were restored on 2026-09-12 from the existing local HTML
cache, retaining `#season`, `#matchweek`, `li.match`, and `li.team-table` elements.
Parsed fixtures and performances were checked for equality with the full cached
pages before saving deterministic gzip files (`mtime=0`). Original HTML SHA-256:

| Sample | Cached source SHA-256 |
| --- | --- |
| 2023-1 | `848902c0908f7c9af158f564bfe53ddfb1f343399198009995a3ff6d0f97abf5` |
| 2024-1 | `7e2946c5812a16339f17f30166a2629291541a6e89cdbf0e95f150abaa3198b7` |
| 2025-38 | `6437e7adc63428f788d3733747299faded859c11b59e6b39107afa53810a1b46` |

The source stylesheet `/css/pages/grades.page.min.css` was also inspected:
grade token `55` displays a placeholder 6 with a dash for Fanta Voto; `56`
displays dashes for both. Both are stored as unrated/null, never as 55, 56,
or an actual rating of 6. The provider's `yellow-card` and `red-card` classes
encode card flags, rather than event columns. A red marker alone does not
establish an earlier yellow card or distinguish a second-yellow dismissal.

Identity verification: 218 IDs in the 2025–26 matchday 38 sample overlap with
the local 2026–27 quotations workbook; all 218 names match. This establishes
the shared Fantacalcio.it source namespace for these inputs. Historical names
remain in raw values and never replace canonical names from current imports.
