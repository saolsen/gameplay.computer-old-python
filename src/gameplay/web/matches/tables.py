import sqlalchemy

from .. import common

matches = sqlalchemy.Table(
    "matches",
    common.tables.metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column(
        "game_id",
        sqlalchemy.BigInteger,
        sqlalchemy.ForeignKey("games.id"),
        nullable=False,
    ),
    sqlalchemy.Column(
        "status",
        sqlalchemy.Enum("in_progress", "finished", name="match_status"),
    ),
    sqlalchemy.Column(
        "winner",
        sqlalchemy.Integer,
    ),
    sqlalchemy.Column(
        "created_by",
        sqlalchemy.String,
        nullable=False,
    ),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column("finished_at", sqlalchemy.DateTime),
)

match_players = sqlalchemy.Table(
    "match_players",
    common.tables.metadata,
    sqlalchemy.Column(
        "match_id",
        sqlalchemy.BigInteger,
        sqlalchemy.ForeignKey("matches.id"),
        nullable=False,
        primary_key=True,
    ),
    sqlalchemy.Column("number", sqlalchemy.Integer, nullable=False, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.String),
    sqlalchemy.Column("agent_id", sqlalchemy.BigInteger),
    sqlalchemy.CheckConstraint(
        "(user_id IS NOT NULL and agent_id IS NULL) OR (user_id IS NULL and agent_id IS NOT NULL)"
    ),
    sqlalchemy.CheckConstraint("number > 0"),
)


match_turns = sqlalchemy.Table(
    "match_turns",
    common.tables.metadata,
    sqlalchemy.Column(
        "match_id",
        sqlalchemy.BigInteger,
        sqlalchemy.ForeignKey("matches.id"),
        nullable=False,
        primary_key=True,
    ),
    sqlalchemy.Column(
        "number",
        sqlalchemy.Integer,
        nullable=False,
        primary_key=True,
    ),
    sqlalchemy.Column(
        "player",
        sqlalchemy.Integer,
    ),
    sqlalchemy.Column("action", sqlalchemy.JSON),
    sqlalchemy.Column(
        "state",
        sqlalchemy.JSON,
        nullable=False,
    ),
    sqlalchemy.Column(
        "next_player",
        sqlalchemy.Integer,
    ),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, nullable=False),
)
