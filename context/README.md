# Serie A context snapshots

The auction companion keeps supplied expectations and dated verified updates as separate snapshots. Player details merge them field by field and show source and observation/retrieval dates. Imported Mantra roles remain authoritative.

## Supplied expectations

`supplied-2026-10-06.json` preserves the JSON supplied in this session, including its original names, tactical notes and percentages. Its source observation date was not supplied; 6 October 2026 is the receipt date, not a claimed observation date.

`mapping-review.json` reports 332 matched player records (330 unique player identities), 20 club records and 1 unmatched record. Parma’s `Konate A.` has no matching current canonical player. Unresolved entries stay stored without a player ID and are excluded from player details. No player is created.

`aliases.json` records reviewed abbreviations and name variants. Inter’s goalkeeper `Martinez` maps to `Martinez Jo.`; `Lautaro` and `Lautaro Martinez` map to `Martinez L.`. Venezia’s `Rrahmani` maps to `Rrahmani Al.`, avoiding Napoli’s different Rrahmani. The supplied `Schimd` spelling is preserved in raw JSON and mapped through an alias to Frosinone’s canonical `Schmid`.

## Verified source review

Official club or league sources for all twenty clubs were checked on 6 October 2026. The table records the manager observation imported for each club. Live pages without a published observation date retain null dates. Known dates use noon Europe/Rome as a storage convention; their exact publication times are unknown. The JSON retains the exact retrieval timestamp for every entry.

| Club | Manager in verified record | Observation date | Source |
| --- | --- | --- | --- |
| Atalanta | Maurizio Sarri | 2026-07-06 | [Official source](https://www.atalanta.it/news/atalanta-2026-27-lo-staff-tecnico-di-mister-sarri?appview=true) |
| Bologna | Raffaele Palladino | 2026-09-16 | [Official source](https://www.bolognafc.it/nota-del-club-45/) |
| Cagliari | Fabio Pisacane | Unknown | [Official source](https://cagliaricalcio.com/giocatore/fabio-pisacane/) |
| Como | Francesc Fabregas Soler | Unknown | [Official source](https://www.legaseriea.it/team/como) |
| Fiorentina | Paolo Vanoli | Unknown | [Official source](https://www.legaseriea.it/team/fiorentina) |
| Frosinone | Massimiliano Alvini | 2026-09-12 | [Official source](https://www.frosinonecalcio.com/conferenza-stampa-post-partita-mister-alvini-41/) |
| Genoa | Daniele De Rossi | 2026-08-14 | [Official source](https://genoacfc.it/2026/08/14/il-video-della-conferenza-del-tecnico-de-rossi-prima-di-genoa-ascoli/) |
| Inter | Cristian Chivu | 2026-09-07 | [Official source](https://www.inter.it/it/notizie/conferenza-stampa-chivu-vigilia-real-madrid-inter-champions-league-26-27) |
| Juventus | Luciano Spalletti | 2026-09-16 | [Official source](https://www.juventus.com/it/news/articoli/le-parole-di-kalulu-e-spalletti-alla-vigilia-di-juventus-nec) |
| Lazio | Gennaro Gattuso | Unknown | [Official source](https://prod.sslazio.it/it/news/eventi/amichevole-or-lazio-arezzo-i-convocati-biancocelesti) |
| Lecce | Eusebio Di Francesco | 2026-09-12 | [Official source](https://oo.uslecce.it/news/322455375366/la-conferenza-stampa-di-mister-di-francesco-us-lecce) |
| Milan | Rúben Amorim | 2026-09-19 | [Official source](https://www.acmilan.com/it/news/articoli/conferenza-stampa/2026-09-19/amorim-vogliamo-giocare-bene-e-vincere-per-i-nostri-tifosi) |
| Monza | Ivan Juric | 2026-09-17 | [Official source](https://www.acmonza.com/it/news/la-conferenza-di-mister-juric-prima-di-monza-sassuolo/) |
| Napoli | Massimiliano Allegri | 2026-07-03 | [Official source](https://sscnapoli.it/en/massimiliano-allegri-e-il-nuovo-allenatore-del-napoli/) |
| Parma | Alberto Gilardino | 2026-09-29 | [Official source](https://www.parmacalcio1913.com/en/main-news/alberto-gilardino-e-il-nuovo-allenatore-del-parma-calcio/) |
| Roma | Gian Piero Gasperini | 2026-09-18 | [Official source](https://www.asroma.com/it/notizie/75958/la-conferenza-stampa-di-gasperini-alla-vigilia-di-roma-inter) |
| Sassuolo | Alberto Aquilani | Unknown | [Official source](https://www.sassuolocalcio.it/squadre/prima-squadra-maschile/rosa-e-staff-3/) |
| Torino | Ignazio Abate | 2026-09-12 | [Official source](https://www.torinofc.it/index.php/news/12/09/2026/incontro-i-media-con-il-tecnico-abate_44719) |
| Udinese | Kosta Runjaic | 2026-09-26 | [Official source](https://www.udinese.it/news/squadra/pogon-szczecin-udinese-le-parole-di-runjaic-nel-post-partita) |
| Venezia | Giovanni Stroppa | 2026-09-10 | [Official source](https://www.veneziafc.it/news/la-conferenza-stampa-di-giovanni-stroppa-x2811) |

Parma announced Cuesta’s departure on [27 September](https://www.parmacalcio1913.com/news/nota-del-club-carlos-cuesta/) and [Gilardino’s appointment on 29 September](https://www.parmacalcio1913.com/en/main-news/alberto-gilardino-e-il-nuovo-allenatore-del-parma-calcio/). Both records are preserved; the later manager field displays Gilardino. The supplied formation and starter expectations remain labelled as supplied.

A [Parma medical statement from 26 August](https://www.parmacalcio1913.com/en/main-news/medical-update-hans-nicolussi-caviglia/) reports persistent groin pain and recommended surgery for Nicolussi Caviglia. The displayed source report replaces the conflicting supplied explanation. It states the report date and does not claim current fitness or a confirmed return date.

The source review verifies the manager records and the specific Parma medical report. It does not convert every supplied starter expectation, formation, duty or availability claim into a verified fact. `verified-mapping-review.json` records the official-update mappings; future updates are manual imports.

## Import workflow

Follow [the auction import guide](../db/auction-app.md#manual-context-imports). Validate with `--dry-run` and resolve aliases before the first import. Identical content is imported once. Preserve later corrections as new dated snapshots so prior observations and their sources remain available.
