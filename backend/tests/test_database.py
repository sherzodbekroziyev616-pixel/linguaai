from sqlalchemy import create_engine, inspect, text

from backend.app.database import Base, ensure_schema_columns


def test_schema_healing_adds_missing_existing_table_columns():
    engine = create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    'CREATE TABLE users ('
                    'id INTEGER PRIMARY KEY, '
                    'email VARCHAR(255) NOT NULL, '
                    'full_name VARCHAR(255) NOT NULL, '
                    'password_hash VARCHAR(255) NOT NULL'
                    ')'
                )
            )
        Base.metadata.create_all(bind=engine)
        ensure_schema_columns(Base, engine)

        columns = {column['name'] for column in inspect(engine).get_columns('users')}
        assert {'nickname', 'recovery_code_hash', 'updated_at', 'is_active'} <= columns
    finally:
        engine.dispose()
