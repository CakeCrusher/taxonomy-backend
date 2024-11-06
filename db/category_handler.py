# db/category_handler.py

from neo4j import Driver
from typing import Optional
from taxonomy_synthesis.models import Category as TSCategory
import uuid


class CategoryModel(TSCategory):
    id: str


def create_category(
    driver: Driver,
    name: str,
    description: str,
    session_id: str,
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
            session_id,
            is_child_of,
            is_parent_of,
        )
    return CategoryModel(id=category_id, name=name, description=description)


def _create_category_tx(
    tx,
    category_id: str,
    name: str,
    description: str,
    session_id: str,
    is_child_of: Optional[str],
    is_parent_of: Optional[str],
):
    # Create the CATEGORY node
    tx.run(
        """
        MATCH (s:SESSION {id: $session_id})
        CREATE (c:CATEGORY {id: $id, name: $name, description: $description})
        CREATE (s)-[:HAS]->(c)
        """,
        id=category_id,
        name=name,
        description=description,
        session_id=session_id,
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


def delete_category(driver: Driver, session_id: str, category_id: str) -> None:
    with driver.session() as session:
        session.write_transaction(_delete_category_tx, session_id, category_id)


def _delete_category_tx(tx, session_id: str, category_id: str):
    # Ensure the category is associated with the session
    tx.run(
        """
        MATCH (s:SESSION {id: $session_id})-[:HAS]->(c:CATEGORY {id: $category_id})
        DETACH DELETE c
        """,
        session_id=session_id,
        category_id=category_id,
    )
