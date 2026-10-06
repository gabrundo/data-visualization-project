"""Manually import preserved, dated context snapshots with reviewed name aliases."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import unicodedata
from urllib.parse import urlparse
from sqlalchemy import text
from project.etl.import_players import ROOT, database_engine


FIELD_NAMES = {'allenatore':'manager', 'modulo':'formation', 'titolare':'expected_starter',
 'percentuale_titolare':'starter_percentage', 'posizione':'position', 'ballottaggio_con':'competition',
 'note_tattiche':'tactical_notes'}


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c)).strip()


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Context timestamps must include a timezone.')
    return result


def flatten(raw):
    if 'entries' in raw:
        return raw['entries']
    entries = []
    for club, data in raw['serie_a_2026_27'].items():
        entries.append(dict(club=club, fields={FIELD_NAMES[k]:v for k,v in data.items() if k in FIELD_NAMES}))
        players = {}
        for group in data.get('ruoli', {}).values():
            for p in group:
                players.setdefault(p['nome'], {}).update({FIELD_NAMES.get(k,k):v for k,v in p.items() if k != 'nome'})
        for field, key in [('penalty_rank','rigoristi'), ('set_piece_rank','calci_da_fermo')]:
            for rank, name in enumerate(data.get(key, []), 1):
                players.setdefault(name, {})[field] = rank
        for key,status in [('indisponibili','unavailable'), ('in_dubbio','doubtful')]:
            for p in data.get(key, []):
                players.setdefault(p['nome'], {}).update(availability=status, availability_report=p['motivo'])
        entries += [dict(club=club, name=name, fields=fields) for name,fields in players.items()]
    return entries


def map_entry(entry, players, aliases):
    if not entry.get('name'):
        return None, 'club', None
    alias = aliases.get(f"{entry['club']}|{entry['name']}")
    # Explicit reviewed aliases reference canonical names or IDs, never fuzzy guesses.
    candidates = [p for p in players if p['player_id'] == alias] if type(alias) is int else [p for p in players if normalize(p['player_name']) == normalize(alias or entry['name'])]
    if not candidates:
        return None, 'unmatched', 'No exact canonical name or reviewed alias.'
    in_club = [p for p in candidates if normalize(p['current_team'] or '') == normalize(entry['club'])]
    if len(in_club) == 1:
        return in_club[0]['player_id'], 'matched', 'Reviewed alias' if alias is not None else 'Exact normalized name and club'
    if not in_club:
        return None, 'club_conflict', 'Canonical candidate belongs to another current club.'
    return None, 'ambiguous', 'Multiple canonical identities match.'


def import_snapshot(engine, path, aliases, *, retrieved_at, observed_at=None, verified=False, source_uri=None, dry_run=False):
    content = path.read_bytes()
    raw = json.loads(content)
    entries = flatten(raw)
    report = []
    with engine.begin() as conn:
        players = [dict(r) for r in conn.execute(text('SELECT * FROM current_eligible_player')).mappings()]
        prepared = []
        for e in entries:
            if not isinstance(e.get('club'), str) or not e['club'].strip():
                raise ValueError('Each context entry needs a club name.')
            if e.get('name') is not None and (not isinstance(e['name'], str) or not e['name'].strip()):
                raise ValueError('Player context names must be nonblank strings.')
            pid,status,note = map_entry(e, players, aliases)
            url = e.get('source_url') or source_uri or path.as_uri()
            is_verified = e.get('verified', verified)
            if type(is_verified) is not bool:
                raise ValueError('verified must be a JSON boolean, never a string.')
            if not isinstance(url, str):
                raise ValueError('Context source URLs must be strings.')
            parsed_url = urlparse(url)
            if is_verified and (parsed_url.scheme not in ('https', 'http') or not parsed_url.netloc):
                raise ValueError('Verified context requires a source URL.')
            if not isinstance(e['fields'], dict):
                raise ValueError('Context fields must be an object.')
            percentage = e['fields'].get('starter_percentage')
            if percentage is not None and (type(percentage) not in (int, float) or not math.isfinite(percentage) or not 0 <= percentage <= 100):
                raise ValueError('Starter percentages must be numbers between 0 and 100.')
            starter = e['fields'].get('expected_starter')
            if starter is not None and type(starter) is not bool:
                raise ValueError('Expected starter must be a JSON boolean or null.')
            at = timestamp(e['observed_at']) if e.get('observed_at') else observed_at
            retrieved = timestamp(e['retrieved_at']) if e.get('retrieved_at') else retrieved_at
            prepared.append(dict(club=e['club'].strip(),name=e.get('name'),pid=pid,status=status,note=note,
                                 fields=json.dumps(e['fields']),url=url,verified=is_verified,at=at,retrieved=retrieved))
            report.append(dict(club=e['club'], name=e.get('name'), player_id=pid, status=status, note=note))
        if not dry_run:
            conn.execute(text('SELECT pg_advisory_xact_lock(202627,3)'))
            sid = conn.execute(text('''INSERT INTO context_snapshot(content_sha256,source_uri,retrieved_at,observed_at,verified,raw_values)
              VALUES (:digest,:uri,:retrieved,:at,:verified,CAST(:raw AS jsonb)) ON CONFLICT DO NOTHING RETURNING id'''),
              dict(digest=sha256(content).hexdigest(),uri=source_uri or path.as_uri(),retrieved=retrieved_at,at=observed_at,verified=verified,raw=content.decode())).scalar()
            if sid is not None:
                for p in prepared:
                    conn.execute(text('''INSERT INTO context_entry(snapshot_id,club,supplied_name,player_id,mapping_status,mapping_note,fields,source_url,verified,observed_at,retrieved_at)
                     VALUES (:sid,:club,:name,:pid,:status,:note,CAST(:fields AS jsonb),:url,:verified,:at,:retrieved)'''),dict(sid=sid,**p))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--aliases', type=Path)
    parser.add_argument('--retrieved-at', help='Timezone-aware timestamp; defaults to now')
    parser.add_argument('--observed-at', help='Known source observation timestamp; omitted when unknown')
    parser.add_argument('--source-url')
    parser.add_argument('--verified', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--report', type=Path, help='Write mapping report JSON')
    args = parser.parse_args()
    engine = database_engine(ROOT / '.env')
    try:
        report = import_snapshot(engine,args.file.resolve(),json.loads(args.aliases.read_text()) if args.aliases else {},
            retrieved_at=timestamp(args.retrieved_at) if args.retrieved_at else datetime.now(timezone.utc),
            observed_at=timestamp(args.observed_at) if args.observed_at else None,verified=args.verified,source_uri=args.source_url,dry_run=args.dry_run)
        result = json.dumps(report, indent=2, ensure_ascii=False)
        if args.report:
            args.report.write_text(result+'\n')
            print(f"Mapping report: {args.report}; {dict(Counter(r['status'] for r in report))}")
        else:
            print(result)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
