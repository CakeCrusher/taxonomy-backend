# db/category_handler.py

from neo4j import Driver
from pydantic import BaseModel
from typing import Optional
from taxonomy_synthesis.models import Category as TSCategory
import uuid


class CategoryModel(TSCategory):
    id: str


def create_category(
    driver: Driver,
    name: str,
    description: str,
    is_child_of: Optional[str] = None,
    is_parent_of: Optional[str] = None,
) -> CategoryModel:
    category_id = str(uuid.uuid4())
    with driver.session() as session:
        session.execute_write(
            _create_category_tx,
            category_id,
            name,
            description,
            is_child_of,
            is_parent_of,
        )
    return CategoryModel(id=category_id, name=name, description=description)


def _create_category_tx(
    tx,
    category_id: str,
    name: str,
    description: str,
    is_child_of: Optional[str],
    is_parent_of: Optional[str],
):
    # Create the CATEGORY node
    tx.run(
        """
        CREATE (c:CATEGORY {id: $id, name: $name, description: $description})
        """,
        id=category_id,
        name=name,
        description=description,
    )

    # Create IS_CHILD_OF and IS_PARENT_TO relationships if provided
    if is_child_of:
        tx.run(
            """
            MATCH (parent:CATEGORY {id: $parent_id}), (child:CATEGORY {id: $child_id})
            CREATE (child)-[:IS_CHILD_OF]->(parent)
            CREATE (parent)-[:IS_PARENT_TO]->(child)
            """,
            parent_id=is_child_of,
            child_id=category_id,
        )

    if is_parent_of:
        tx.run(
            """
            MATCH (parent:CATEGORY {id: $parent_id}), (child:CATEGORY {id: $child_id})
            CREATE (parent)-[:IS_PARENT_TO]->(child)
            CREATE (child)-[:IS_CHILD_OF]->(parent)
            """,
            parent_id=category_id,
            child_id=is_parent_of,
        )
