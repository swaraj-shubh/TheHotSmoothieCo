import pytest


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (
            "postgresql://u:p%40ss@ep-x-pooler.ap-south-1.aws.neon.tech/hsc?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p%40ss@ep-x-pooler.ap-south-1.aws.neon.tech/hsc?ssl=require",
        ),
        (
            "postgres://u:p@db.supabase.co:6543/postgres",
            "postgresql+asyncpg://u:p@db.supabase.co:6543/postgres",
        ),
        ("postgresql+asyncpg://u:p@localhost/hsc", "postgresql+asyncpg://u:p@localhost/hsc"),
    ],
)
def test_database_url_normalised_for_asyncpg(given, expected):
    from app.core.config import Settings

    assert Settings(database_url=given).database_url == expected
