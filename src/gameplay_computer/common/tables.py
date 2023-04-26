import sqlalchemy

metadata = sqlalchemy.MetaData()

game = sqlalchemy.Enum("connect4", name="game")

agents = sqlalchemy.Table(
    "agents",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column("game", game, nullable=False, index=True),
    sqlalchemy.Column("user_id", sqlalchemy.String, nullable=False, index=True),
    sqlalchemy.Column("agentname", sqlalchemy.String, nullable=False),
    sqlalchemy.UniqueConstraint("game", "user_id", "agentname"),
)
