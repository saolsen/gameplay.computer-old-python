import sqlalchemy

metadata = sqlalchemy.MetaData()

matches = sqlalchemy.Table(
    "matches",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("game", sqlalchemy.String),
    sqlalchemy.Column("opponent", sqlalchemy.String),
    sqlalchemy.Column("state", sqlalchemy.JSON),
    sqlalchemy.Column("turn", sqlalchemy.Integer),
    sqlalchemy.Column("next_player", sqlalchemy.Integer),
)

turns = sqlalchemy.Table(
    "turns",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("number", sqlalchemy.Integer),
    sqlalchemy.Column("match_id", sqlalchemy.Integer),
    sqlalchemy.Column("player", sqlalchemy.Integer),
    sqlalchemy.Column("column", sqlalchemy.Integer),
)
