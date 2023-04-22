import sqlalchemy

metadata = sqlalchemy.MetaData()

games = sqlalchemy.Table(
    "games",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, unique=True, index=True),
)

matches = sqlalchemy.Table(
    "matches",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column(
        "game_id",
        sqlalchemy.BigInteger,
        sqlalchemy.ForeignKey("games.id"),
        nullable=False,
    ),
    sqlalchemy.Column(
        "status",
        sqlalchemy.Enum("new", "in_progress", "finished", name="match_status"),
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
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime, nullable=False),
    sqlalchemy.Column("finished_at", sqlalchemy.DateTime),
)

match_players = sqlalchemy.Table(
    "match_players",
    metadata,
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
    sqlalchemy.CheckConstraint("user_id IS NOT NULL OR agent_id IS NOT NULL"),
    sqlalchemy.CheckConstraint("number > 0"),
)


match_turns = sqlalchemy.Table(
    "match_turns",
    metadata,
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
