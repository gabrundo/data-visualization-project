"""Apply the additive auction migration to an existing statistics database."""
from project.etl.import_players import ROOT, database_engine


def main():
    engine = database_engine(ROOT / '.env')
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql((ROOT / 'db/init/003_auction.sql').read_text())
            conn.commit()
        print('Auction migration installed. Existing players and performances preserved.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
