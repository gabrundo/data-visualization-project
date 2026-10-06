"""Transaction-scoped auction operations. Every writer locks the singleton row."""
from sqlalchemy import text
from uuid import uuid4
from project.web.rules import team_summary, validate_purchase


def rows(conn, sql, **params):
    return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def lock(conn):
    conn.execute(text('SELECT id FROM auction_settings WHERE id=1 FOR UPDATE')).one()


def state(conn):
    settings = rows(conn, 'SELECT * FROM auction_settings WHERE id=1')[0]
    sales = rows(conn, '''SELECT s.*, p.name AS player_name FROM auction_sale s
                         JOIN player p ON p.id=s.player_id ORDER BY s.id DESC''')
    teams = rows(conn, 'SELECT * FROM fantasy_team ORDER BY lower(name),id')
    for t in teams:
        t['sales'] = [s for s in sales if s['buyer_id'] == t['id']]
        t.update(team_summary(t['sales']))
    return dict(settings=settings, teams=teams, sales=sales)


def touch(conn):
    conn.execute(text('UPDATE auction_settings SET revision=revision+1 WHERE id=1'))
    return state(conn)


def configure(conn, teams, my_team_index):
    lock(conn)
    existing = {t['id'] for t in rows(conn, 'SELECT id FROM fantasy_team')}
    provided = [t.id for t in teams if t.id is not None]
    if len(provided) != len(set(provided)) or not set(provided) <= existing:
        raise ValueError('Unknown or duplicate team ID.')
    names = [t.name.strip() for t in teams]
    if len(set(n.casefold() for n in names)) != len(names):
        raise ValueError('Team names must be unique.')
    removed = existing - set(provided)
    if any(s['buyer_id'] in removed for s in rows(conn, 'SELECT buyer_id FROM auction_sale')):
        raise ValueError('Cannot remove a team that owns players.')
    # Release the reference before deletion; unique names temporarily staged for swaps.
    conn.execute(text('UPDATE auction_settings SET my_team_id=NULL WHERE id=1'))
    for id in existing:
        conn.execute(text('UPDATE fantasy_team SET name=:name WHERE id=:id'), dict(id=id, name=f'__rename_{uuid4().hex}'))
    for id in removed:
        conn.execute(text('DELETE FROM fantasy_team WHERE id=:id'), dict(id=id))
    ids = []
    for team, name in zip(teams, names):
        if team.id is None:
            ids.append(conn.execute(text('INSERT INTO fantasy_team(name) VALUES (:name) RETURNING id'), dict(name=name)).scalar_one())
        else:
            conn.execute(text('UPDATE fantasy_team SET name=:name WHERE id=:id'), dict(id=team.id, name=name))
            ids.append(team.id)
    conn.execute(text('UPDATE auction_settings SET my_team_id=:id WHERE id=1'), dict(id=ids[my_team_index]))
    return touch(conn)


def sale(conn, player_id, buyer_id, price, *, sale_id=None, key=None):
    import json
    lock(conn)
    payload = dict(player_id=player_id, buyer_id=buyer_id, price=price)
    if key:
        receipt = rows(conn, 'SELECT payload FROM auction_request WHERE key=:key', key=key)
        if receipt:
            if receipt[0]['payload'] != payload:
                raise ValueError('This request key was used with different sale values.')
            return state(conn)
    previous = rows(conn, 'SELECT * FROM auction_sale WHERE id=:id', id=sale_id) if sale_id else []
    if sale_id and not previous:
        raise ValueError('Sale no longer exists.')
    if previous and previous[0]['player_id'] != player_id:
        raise ValueError('A correction cannot change the player. Delete and record a new sale.')
    player = rows(conn, 'SELECT * FROM current_eligible_player WHERE player_id=:id', id=player_id)
    if not player:
        raise ValueError('Player is not in the current eligible catalogue.')
    if not player[0]['roles']:
        raise ValueError('Player has no imported Mantra eligibility.')
    if not rows(conn, 'SELECT id FROM fantasy_team WHERE id=:id', id=buyer_id):
        raise ValueError('Choose an existing buying team.')
    if rows(conn, 'SELECT id FROM auction_sale WHERE player_id=:p AND id<>coalesce(:id,0)', p=player_id, id=sale_id):
        raise ValueError('Player is already sold. Use Edit to correct the sale.')
    group = previous[0]['role_group'] if previous else ('goalkeeper' if 'Por' in player[0]['roles'] else 'outfield')
    owned = rows(conn, 'SELECT * FROM auction_sale WHERE buyer_id=:buyer AND id<>coalesce(:id,0)', buyer=buyer_id, id=sale_id)
    validate_purchase(owned, group, price)
    if sale_id:
        conn.execute(text('UPDATE auction_sale SET buyer_id=:buyer,price=:price WHERE id=:id'), dict(buyer=buyer_id,price=price,id=sale_id))
    else:
        conn.execute(text('INSERT INTO auction_sale(player_id,buyer_id,price,role_group) VALUES (:p,:b,:price,:g)'), dict(p=player_id,b=buyer_id,price=price,g=group))
        conn.execute(text('INSERT INTO auction_request(key,payload) VALUES (:key,CAST(:payload AS jsonb))'), dict(key=key,payload=json.dumps(payload)))
    return touch(conn)


def remove(conn, sale_id=None, *, undo=False, reset=False):
    lock(conn)
    if reset:
        conn.execute(text('DELETE FROM auction_sale'))
    else:
        if undo:
            sale_id = conn.execute(text('SELECT max(id) FROM auction_sale')).scalar()
        result = conn.execute(text('DELETE FROM auction_sale WHERE id=:id'), dict(id=sale_id))
        if not result.rowcount:
            raise ValueError('No sale to remove.')
    return touch(conn)
