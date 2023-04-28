import sqlalchemy

metadata = sqlalchemy.MetaData()

game = sqlalchemy.Enum("connect4", name="game")
