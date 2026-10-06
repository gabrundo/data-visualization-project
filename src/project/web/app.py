"""Run: uv run uvicorn project.web.app:app --host 127.0.0.1"""
from contextlib import asynccontextmanager
import csv
import io
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictInt, field_validator, model_validator
from sqlalchemy.exc import SQLAlchemyError

from project.etl.import_players import ROOT, database_engine
from project.web import store
from project.web.catalogue import catalogue

STATIC = Path(__file__).parent / 'static'


class Team(BaseModel):
    id: StrictInt | None = None
    name: str = Field(min_length=1, max_length=80)

    @field_validator('name')
    @classmethod
    def nonblank(cls, name):
        if not name.strip():
            raise ValueError('Team name cannot be blank.')
        return name.strip()


class Settings(BaseModel):
    teams: list[Team] = Field(min_length=1, max_length=50)
    my_team_index: StrictInt

    @model_validator(mode='after')
    def index_valid(self):
        if not 0 <= self.my_team_index < len(self.teams):
            raise ValueError('Select my team from the team list.')
        return self


class Sale(BaseModel):
    player_id: StrictInt
    buyer_id: StrictInt
    price: StrictInt = Field(ge=1, le=500)


class NewSale(Sale):
    idempotency_key: UUID


class Reset(BaseModel):
    confirmation: str
    revision: StrictInt


def create_app(engine=None):
    @asynccontextmanager
    async def lifespan(app):
        if app.state.engine is None:
            app.state.engine = database_engine(ROOT / '.env')
        yield
        if engine is None:
            app.state.engine.dispose()

    app = FastAPI(title='Mantra Auction', lifespan=lifespan)
    app.state.engine = engine
    app.mount('/static', StaticFiles(directory=STATIC), name='static')

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={'detail': 'Database unavailable or migration missing. Your changes were not saved. Check PostgreSQL and retry.'})

    def operation(fn, *args, **kwargs):
        try:
            with app.state.engine.begin() as conn:
                result = fn(conn, *args, **kwargs)
            return jsonable_encoder(result)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    def read(fn):
        with app.state.engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            with conn.begin():
                return jsonable_encoder(fn(conn))

    @app.get('/')
    def index():
        return FileResponse(STATIC / 'index.html')

    @app.get('/api/catalogue')
    def get_catalogue():
        return read(catalogue)

    @app.get('/api/state')
    def get_state():
        return read(store.state)

    @app.put('/api/settings')
    def settings(body: Settings):
        return operation(store.configure, body.teams, body.my_team_index)

    @app.post('/api/sales')
    def create_sale(body: NewSale):
        return operation(store.sale, body.player_id, body.buyer_id, body.price, key=str(body.idempotency_key))

    @app.put('/api/sales/{sale_id}')
    def edit_sale(sale_id: int, body: Sale):
        return operation(store.sale, body.player_id, body.buyer_id, body.price, sale_id=sale_id)

    @app.delete('/api/sales/{sale_id}')
    def delete_sale(sale_id: int):
        return operation(store.remove, sale_id)

    @app.post('/api/undo')
    def undo():
        return operation(store.remove, undo=True)

    @app.post('/api/reset')
    def reset(body: Reset):
        def action(conn):
            store.lock(conn)
            if body.confirmation != 'RESET':
                raise ValueError('Type RESET to confirm deleting all auction sales.')
            if store.state(conn)['settings']['revision'] != body.revision:
                raise ValueError('Auction changed. Review the current sales before resetting.')
            return store.remove(conn, reset=True)
        return operation(action)

    @app.get('/api/export/sales.csv')
    @app.get('/api/export/roster/{team_id}.csv')
    def export(team_id: int | None = None):
        data = read(store.state)
        names = {t['id']:t['name'] for t in data['teams']}
        if team_id is not None and team_id not in names:
            raise HTTPException(404, 'Team not found.')
        buffer = io.StringIO(newline='')
        writer = csv.writer(buffer)
        writer.writerow(['sale_id', 'player_id', 'player', 'team', 'role_group', 'price', 'recorded_at_utc'])
        def safe(value):
            return "'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')) else value
        for sale in reversed(data['sales']):
            if team_id is None or sale['buyer_id'] == team_id:
                writer.writerow([sale['id'],sale['player_id'],safe(sale['player_name']),safe(names[sale['buyer_id']]),sale['role_group'],sale['price'],sale['recorded_at']])
        return Response(buffer.getvalue(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="auction.csv"'})
    return app


app = create_app()
