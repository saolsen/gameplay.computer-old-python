import sqlalchemy

metadata = sqlalchemy.MetaData()

widgets = sqlalchemy.Table(
    "widgets",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean),
)
