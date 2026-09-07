from pathlib import Path

import pandas as pd


def main():
    file = Path("data/Statistiche_Fantacalcio_Stagione_2026_27.xlsx")
    df = pd.read_excel(file, skiprows=1)

    player_columns = ["Id", "Nome", "Squadra"]
    player_df = df[player_columns]
    print("Number of players:", len(player_df))

    invalid_names = player_df["Nome"].str.endswith("*").astype(int)
    print("Number of invalid players:", invalid_names.sum())

    print(df.head())

if __name__ == "__main__":
    main()