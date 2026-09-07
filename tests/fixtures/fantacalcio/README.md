# Historical HTML samples

Retrieved on 2026-09-07 from:

- https://www.fantacalcio.it/voti-fantacalcio-serie-a/2023-24/1
- https://www.fantacalcio.it/voti-fantacalcio-serie-a/2024-25/1
- https://www.fantacalcio.it/voti-fantacalcio-serie-a/2025-26/38

The gzip files retain season/matchday selectors, fixture menu entries, and team
rating tables. Navigation, advertisements, scripts, and other unrelated markup
were removed. Tests use the original attributes, provider headings, player
links, coaches, event counts, and card classes.

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
