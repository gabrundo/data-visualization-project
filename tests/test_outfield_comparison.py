"""Outfield query membership and plot contracts; database checks are read-only."""
import os
import unittest

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import text

from project.analysis.queries import GROUP_METRICS_QUERY, connect_database
from project.analysis.outfield_comparison import GROUPS, group_table, plot_outfield_comparison


def sample_players():
    rows = []
    for i in range(12):
        rows.append(dict(player_id=i, source_id=1, player_name=f'Player {i:02}',
                         group_key='attack', role_combination='A/Pc',
                         performance_season=2025, mean_fv=7 if i < 11 else None,
                         rated_matches=12 + i, rated_season_fraction=(12 + i) / 38,
                         coverage_status='complete'))
    # Same player legitimately belongs to another pool.
    rows.append(dict(rows[0], group_key='pc'))
    return pd.DataFrame(rows)


class OutfieldPlotTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_shared_coverage_colors_and_top_ten(self):
        players = sample_players()
        figures = plot_outfield_comparison(players)
        self.assertEqual(list(figures), list(GROUPS))
        attack, striker = figures['attack'].axes[0], figures['pc'].axes[0]
        self.assertEqual(attack.get_xlim(), striker.get_xlim())
        self.assertEqual(attack.get_ylim(), striker.get_ylim())
        self.assertEqual(attack.collections[0].get_facecolors().tolist(),
                         striker.collections[0].get_facecolors().tolist())
        labels = [label.get_text() for label in attack.texts]
        self.assertEqual(labels, [f'Player {i:02}' for i in range(10, 0, -1)])
        self.assertEqual(len(attack.collections[0].get_offsets()), 11)
        self.assertEqual(len(group_table(players, 'attack')), 12)
        self.assertIn('1 missing coordinates', attack.get_title(loc='left'))
        self.assertIn('No players', figures['dc'].axes[0].texts[0].get_text())

    def test_vote_limits_fit_each_group(self):
        players = sample_players()
        players.loc[players.group_key.eq('attack'), 'mean_fv'] = [6 + i / 100 for i in range(12)]
        players.loc[players.group_key.eq('pc'), 'mean_fv'] = 9.0
        figures = plot_outfield_comparison(players)
        attack, striker = figures['attack'].axes[0], figures['pc'].axes[0]
        self.assertLess(attack.get_ylim()[0], 6.0)
        self.assertGreater(attack.get_ylim()[1], 6.11)
        self.assertLess(attack.get_ylim()[1], 6.2)
        self.assertLess(striker.get_ylim()[0], 9.0)
        self.assertGreater(striker.get_ylim()[1], 9.0)
        self.assertGreater(striker.get_ylim()[0], attack.get_ylim()[1])

    def test_invalid_inputs(self):
        players = sample_players()
        mixed = players.copy()
        mixed.loc[0, 'performance_season'] = 2024
        with self.assertRaisesRegex(ValueError, 'one performance season'):
            plot_outfield_comparison(mixed)
        with self.assertRaisesRegex(ValueError, 'one row'):
            plot_outfield_comparison(pd.concat([players, players.iloc[:1]]))
        with self.assertRaisesRegex(ValueError, 'coverage filter'):
            plot_outfield_comparison(players, min_rated_season_fraction=0.8)

    def test_empty_and_missing_fv(self):
        players = sample_players()
        for frame in (players.iloc[:0], players.assign(mean_fv=float('nan'))):
            figures = plot_outfield_comparison(frame)
            self.assertEqual(len(figures), 6)
            self.assertEqual(sum(len(f.axes[0].collections) for f in figures.values()), 0)
            plt.close('all')


@unittest.skipUnless(os.environ.get('HISTORICAL_DB_TESTS') == '1', 'Requires local PostgreSQL')
class OutfieldQueryTests(unittest.TestCase):
    def test_membership_and_inclusive_boundary(self):
        # The CTE shadows the production view: no tables or records are changed.
        fixture = """
            WITH player_season_metrics AS (
                SELECT id AS player_id, 1 AS source_id, id::text AS player_name,
                       roles, fraction AS rated_season_fraction, 2025 AS performance_season,
                       6.0 AS mean_fv, 12 AS rated_matches
                FROM (VALUES
                    (1, ARRAY['Dd','Ds'], 0.30::numeric),
                    (2, ARRAY['C','T'], 12.0/38),
                    (3, ARRAY['A','Pc'], 12.0/38),
                    (4, ARRAY['M'], 12.0/38),
                    (5, ARRAY['Dc'], 11.0/38),
                    (6, ARRAY['Dc'], 12.0/38),
                    (7, ARRAY['E'], 0.8),
                    (8, ARRAY['B'], 0.8),
                    (9, ARRAY['Por'], 0.8),
                    (10, ARRAY['E','Ds'], 0.8),
                    (11, ARRAY['B','Dc'], 0.8),
                    (12, ARRAY['B','E'], 0.8)
                ) AS sample(id, roles, fraction)
            )
        """
        engine = connect_database()
        try:
            with engine.connect() as conn:
                frame = pd.read_sql_query(text(fixture + GROUP_METRICS_QUERY), conn,
                                          params={'season': 2025, 'min_fraction': 0.30})
        finally:
            engine.dispose()
        memberships = frame.groupby('player_id')['group_key'].agg(set).to_dict()
        self.assertEqual(memberships, {1: {'fullbacks'}, 2: {'c', 'attack'},
                                      3: {'attack', 'pc'}, 4: {'m'}, 6: {'dc'},
                                      7: {'fullbacks'}, 8: {'dc'}, 10: {'fullbacks'},
                                      11: {'dc'}, 12: {'dc', 'fullbacks'}})
        self.assertFalse(frame.duplicated(['player_id', 'source_id', 'group_key']).any())
        self.assertEqual(frame.loc[frame.player_id.eq(1), 'role_combination'].item(), 'Dd/Ds')


if __name__ == '__main__':
    unittest.main()
