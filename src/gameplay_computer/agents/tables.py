import sqlalchemy

from gameplay_computer.common.tables import game, metadata

agents = sqlalchemy.Table(
    "agents",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.BigInteger, primary_key=True),
    sqlalchemy.Column("game", game, nullable=False, index=True),
    sqlalchemy.Column("user_id", sqlalchemy.String, nullable=False, index=True),
    sqlalchemy.Column("agentname", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.UniqueConstraint("game", "user_id", "agentname"),
)

agent_deployment = sqlalchemy.Table(
    "agent_deployment",
    metadata,
    sqlalchemy.Column(
        "agent_id",
        sqlalchemy.BigInteger,
        sqlalchemy.ForeignKey("agents.id"),
        primary_key=True,
    ),
    sqlalchemy.Column("url", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("healthy", sqlalchemy.Boolean, nullable=False),
    sqlalchemy.Column("active", sqlalchemy.Boolean, nullable=False),
)

agent_history = sqlalchemy.Table(
    "agent_history",
    metadata,
    sqlalchemy.Column(
        "agent_id",
        sqlalchemy.BigInteger,
        sqlalchemy.ForeignKey("agents.id"),
        primary_key=True,
    ),
    sqlalchemy.Column("wins", sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column("losses", sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column("draws", sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column("errors", sqlalchemy.Integer, nullable=False),
)
