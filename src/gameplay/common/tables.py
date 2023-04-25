import sqlalchemy

metadata = sqlalchemy.MetaData()

games = sqlalchemy.Table(
    "games",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, unique=True, index=True),
)

agents = sqlalchemy.Table(
    "agents",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column("game_id", sqlalchemy.BigInteger, nullable=False, index=True),
    sqlalchemy.Column("user_id", sqlalchemy.String, nullable=False, index=True),
    sqlalchemy.Column("agentname", sqlalchemy.String, nullable=False),
    sqlalchemy.UniqueConstraint("game_id", "user_id", "agentname"),
)
