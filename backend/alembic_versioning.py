from __future__ import annotations

from alembic.ddl.impl import DefaultImpl
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table


CLIPFORGE_ALEMBIC_VERSION_TABLE_LENGTH = 128
_PATCH_APPLIED = False


def patch_alembic_version_table_impl() -> None:
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    def clipforge_version_table_impl(
        self,
        *,
        version_table: str,
        version_table_schema: str | None,
        version_table_pk: bool,
        **kw,
    ) -> Table:
        version_table_obj = Table(
            version_table,
            MetaData(),
            Column(
                "version_num",
                String(CLIPFORGE_ALEMBIC_VERSION_TABLE_LENGTH),
                nullable=False,
            ),
            schema=version_table_schema,
        )
        if version_table_pk:
            version_table_obj.append_constraint(
                PrimaryKeyConstraint(
                    "version_num",
                    name=f"{version_table}_pkc",
                )
            )

        return version_table_obj

    DefaultImpl.version_table_impl = clipforge_version_table_impl
    _PATCH_APPLIED = True
