import logging
import re
import sqlite3

logger = logging.getLogger(__name__)

class Connection:
    def __init__(self, database_name = "recap", memory = False):
        """
        Connection class provides an interface for interacting with the SQLite database file. If the database file does not exist
        (e.g. on initial run), it is created using the included schema. Must be closed with the close() method after use.
        :param database_name: Database filename
        :param memory: Memory mode flag
        """
        try:
            # Connect without implicitly creating a new database
            # See https://docs.python.org/3/library/sqlite3.html#how-to-work-with-sqlite-uris)
            source = sqlite3.connect(f"file:{database_name}.db?mode=rw", uri = True)
        except sqlite3.OperationalError:
            source = sqlite3.connect(f"{database_name}.db")
            with open(f"{database_name}.sql", "r") as schema:
                source.executescript(schema.read())
        # Memory mode opens the connection in RAM so operations are nondestructive
        if memory:
            target = sqlite3.connect(":memory:")
            with target:
                source.backup(target)
            source.close()
            self.source = target
        else:
            self.source = source
        self.source.row_factory = sqlite3.Row
        # Enable foreign key constraints
        self.source.execute("pragma foreign_keys = on;")

    def execute(self, query, parameters = ()):
        """
        Helper for executing queries on the connection object. Uses the connection as a context manager for automatic transaction
        management (https://docs.python.org/3.9/library/sqlite3.html#using-the-connection-as-a-context-manager) and provides
        informative error handling.
        :param query: Query string
        :param parameters: Values to be substituted into any query placeholders
        :return: Cursor (on successful execution)
        """
        try:
            with self.source:
                return self.source.execute(query, parameters)
        except sqlite3.Error as error:
            logger.error(re.sub(r"class \'(.+)\'", r"\1", str(error.__class__)) + f" {error}")

    def insert_row(self, table, **kwargs):
        columns = f"({', '.join(kwargs.keys())})"
        placeholders = re.sub(r"(\w+)", r":\1", columns)
        cursor = self.execute(f"insert into {table} {columns} values {placeholders};", kwargs)
        if cursor:
            return self.execute(f"select * from {table} where id = ?;", (cursor.lastrowid,)).fetchone()

    def get_game(self, title):
        return self.execute("select * from games where title = ?;", (title,)).fetchone()

    def update_game(self, game, **kwargs):
        """
        Updates a game's properties. Note that "title" can only have its case changed, since it's used as the unique identifier in
        a recap post. A special syntax will need to be implemented to support actual title updating. A row object is passed instead
        of a title to spare the extra SQL query for "id" lookup, and because this function is only called where the row object is
        already immediately accessible.
        :param game: Game row object
        :param kwargs: Properties to update (title, dev, tools, web)
        :return: Cursor
        """
        self.execute(
            f"update games set {', '.join(f'{column} = ?' for column in kwargs.keys())} where id = ?;",
            list(kwargs.values()) + [game["id"]]
        )

    def close(self):
        self.source.close()
