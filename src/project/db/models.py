from sqlalchemy import Integer, String, Float, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class PlayerRecord(DeclarativeBase):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    team: Mapped[str] = mapped_column(String(25), nullable=False)