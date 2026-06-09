import pytest
from sqlalchemy import text


class TestDatabaseConnection:
    @pytest.mark.asyncio
    async def test_executes_simple_query(self, db_session):
        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1
