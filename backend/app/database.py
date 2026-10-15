from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def ensure_schema_columns(base, target_engine=engine) -> None:
    inspector = inspect(target_engine)
    existing_tables = set(inspector.get_table_names())
    with target_engine.begin() as connection:
        for table in base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_columns = {column['name'] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns or column.primary_key:
                    continue
                column_type = column.type.compile(dialect=target_engine.dialect)
                connection.execute(
                    text(
                        f'ALTER TABLE {target_engine.dialect.identifier_preparer.quote(table.name)} '
                        f'ADD COLUMN {target_engine.dialect.identifier_preparer.quote(column.name)} {column_type}'
                    )
                )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
