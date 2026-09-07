"""Validate workbook parsing without requiring PostgreSQL."""

from io import BytesIO
import unittest

import pandas as pd

from project.etl.import_players import read_players


def workbook(rows, role_column="RM"):
    buffer = BytesIO()
    pd.DataFrame(rows, columns=["Id", "Nome", role_column, "Squadra"]).to_excel(
        buffer, index=False, startrow=1
    )
    return buffer.getvalue()


class ReadPlayersTests(unittest.TestCase):
    def test_multirole_and_alternate_header(self):
        result = read_players(workbook([[42, " Name ", "B;Dd;E", " Team "]], "Rm"))
        self.assertEqual(result.iloc[0]["Id"], "42")
        self.assertEqual(result.iloc[0]["Nome"], "Name")
        self.assertEqual(result.iloc[0]["Squadra"], "Team")
        self.assertEqual(result.iloc[0]["roles"], ["B", "Dd", "E"])

    def test_rejects_invalid_rows(self):
        cases = [
            [[1, None, "Por", "Team"]],
            [[1, "Name", "Coach", "Team"]],
            [[1.5, "Name", "Por", "Team"]],
            [[0, "Name", "Por", "Team"]],
            [[1, "Name", "Por", "Team"], [1, "Other", "Dc", "Team"]],
            [],
        ]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                read_players(workbook(rows))


if __name__ == "__main__":
    unittest.main()
