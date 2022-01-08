# MIT License
#
# Copyright (c) 2021 TrigonDev
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Sequence, Type

import asyncpg
from asyncpg.cursor import CursorFactory

from apgorm.exceptions import NoMigrationsToCreate
from apgorm.lazy_list import LazyList
from apgorm.migrations import describe
from apgorm.migrations.applied_migration import AppliedMigration
from apgorm.migrations.apply_migration import apply_migration
from apgorm.migrations.create_migration import create_next_migration
from apgorm.migrations.migration import Migration

from .connection import Connection, Pool
from .indexes import Index
from .model import Model


class Database:
    """Base database class. You must subclass this, as
    all tables and indexes are stored as classvars.

    Example:
    ```
    class MyDatabase(Database):
        users = User
        games = Game
        players = Players

        indexes = [SomeIndex, SomeOtherIndex]
    ```
    """

    _migrations = AppliedMigration
    """Internal table to track applied migrations."""

    indexes: Sequence[Index] | None = None
    """A list of indexes for the database."""

    def __init__(self, migrations_folder: Path):
        """Initialize the database.

        Args:
            migrations_folder (pathlib.Path): The folder in which migrations
            are/will be stored.
        """

        self._migrations_folder = migrations_folder
        self._all_models: list[Type[Model]] = []

        for attr_name in dir(self):
            try:
                attr = getattr(self, attr_name)
            except AttributeError:
                continue

            if not isinstance(attr, type):
                continue
            if not issubclass(attr, Model):
                continue

            attr._database = self
            attr._tablename = attr_name
            self._all_models.append(attr)

            all_fields, all_constraints = attr._special_attrs()

            for name, field in all_fields.items():
                field.model = attr
                field.name = name

            for name, constraint in all_constraints.items():
                constraint.name = name

        self.pool: Pool | None = None

    # migration functions
    def describe(self) -> describe.Describe:
        """Return the description of the database.

        Returns:
            describe.Describe: The description.
        """

        return describe.Describe(
            tables=[m._describe() for m in self._all_models],
            indexes=[i._describe() for i in self.indexes or []],
        )

    def load_all_migrations(self) -> list[Migration]:
        """Load all migrations and return them.

        Returns:
            list[Migration]: The migrations.
        """

        return Migration.load_all_migrations(self._migrations_folder)

    def load_last_migration(self) -> Migration | None:
        """Loads and returns the most recent migration, if any.

        Returns:
            Migration | None: The migration.
        """

        return Migration.load_last_migration(self._migrations_folder)

    def must_create_migrations(self) -> bool:
        """Whether or not you need to call Database.create_migrations()

        Returns:
            bool
        """

        sql = create_next_migration(self.describe(), self._migrations_folder)
        if sql is None:
            return False
        return True

    def create_migrations(self, indent: int | None = None) -> Migration:
        """Create migrations.

        Raises:
            NoMigrationsToCreate: Migrations do not creating.

        Returns:
            Migration: The created migration.
        """

        if not self.must_create_migrations():
            raise NoMigrationsToCreate
        d = self.describe()
        sql = create_next_migration(d, self._migrations_folder)
        assert sql is not None
        return Migration.create_migration(d, sql, self._migrations_folder)

    async def load_unapplied_migrations(self) -> list[Migration]:
        """Returns a list of migrations that have not been applied on the
        current database.

        Returns:
            list[Migration]: The unapplied migrations.
        """

        try:
            applied = [
                m.id_.v
                for m in await self._migrations.fetch_query().fetchmany()
            ]
        except asyncpg.UndefinedTableError:
            applied = []
        return [
            m
            for m in self.load_all_migrations()
            if m.migration_id not in applied
        ]

    async def must_apply_migrations(self) -> bool:
        """Whether or not there are migrations that need to be applied.

        Returns:
            bool
        """

        return len(await self.load_unapplied_migrations()) > 0

    async def apply_migrations(self) -> None:
        """Applies all migrations that need to be applied."""

        for m in await self.load_unapplied_migrations():
            await apply_migration(m, self)

    # database functions
    async def connect(self, **connect_kwargs) -> None:
        """Connect to a database. Any kwargs that can be passed to
        asyncpg.create_pool() can be used here.
        """

        self.pool = Pool(await asyncpg.create_pool(**connect_kwargs))

    async def cleanup(self, timeout: float = 30) -> None:
        """Close the connection.

        Args:
            timeout (float): The maximum time pool.close() has. Defaults to 30.

        Raises:
            TimeoutError: The operation timed out.
        """

        if self.pool is not None:
            await asyncio.wait_for(self.pool.close(), timeout=timeout)

    async def execute(self, query: str, params: list[Any]) -> None:
        """Execute SQL within a transaction."""

        assert self.pool is not None
        async with self.pool.acquire() as con:
            async with con.transaction():
                await con.execute(query, params)

    async def fetchrow(
        self, query: str, params: list[Any]
    ) -> dict[str, Any] | None:
        """Fetch the first matching row.

        Returns:
            dict | None: The row, if any.
        """

        assert self.pool is not None
        async with self.pool.acquire() as con:
            async with con.transaction():
                return await con.fetchrow(query, params)

    async def fetchmany(
        self, query: str, params: list[Any]
    ) -> LazyList[asyncpg.Record, dict[str, Any]]:
        """Fetch all matching rows.

        Returns:
            LazyList[asyncpg.Record, dict]: All matching rows.
        """

        assert self.pool is not None
        async with self.pool.acquire() as con:
            async with con.transaction():
                return await con.fetchmany(query, params)

    async def fetchval(self, query: str, params: list[Any]) -> Any:
        """Fetch a single value."""

        assert self.pool is not None
        async with self.pool.acquire() as con:
            async with con.transaction():
                return await con.fetchval(query, params)

    @asynccontextmanager
    async def cursor(
        self, query: str, params: list[Any], con: Connection | None = None
    ) -> AsyncGenerator[CursorFactory, None]:
        """Yields a CursorFactory, but inside a transaction.

        Usage:
        ```
        async with db.cursor(query, args) as cursor:
            async for res in cursor:
                print(res)
        ```
        """

        if con:
            yield con.cursor(query, params)

        else:
            assert self.pool is not None
            async with self.pool.acquire() as con:
                async with con.transaction():
                    yield con.cursor(query, params)
