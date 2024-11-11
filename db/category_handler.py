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
        session.execute_write(_delete_category_tx, session_id, category_id)


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


def update_category(
    driver: Driver,
    session_id: str,
    category_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_child_of: Optional[str] = None,
    is_parent_of: Optional[str] = None,
) -> CategoryModel:
    """
    Updates an existing category within a session.

    Args:
        driver (Driver): Neo4j driver instance.
        session_id (str): ID of the session.
        category_id (str): ID of the category to update.
        name (Optional[str]): New name for the category.
        description (Optional[str]): New description for the category.
        is_child_of (Optional[str]): ID of the new parent category.
        is_parent_of (Optional[str]): ID of the new child category.

    Returns:
        CategoryModel: The updated category.
    """
    with driver.session() as session:
        updated_category = session.execute_write(
            _update_category_tx,
            session_id,
            category_id,
            name,
            description,
            is_child_of,
            is_parent_of,
        )
    return updated_category


def _update_category_tx(
    tx,
    session_id: str,
    category_id: str,
    name: Optional[str],
    description: Optional[str],
    is_child_of: Optional[str],
    is_parent_of: Optional[str],
) -> CategoryModel:
    """
    Transaction function to update a category's properties and relationships.

    Args:
        tx: Neo4j transaction object.
        session_id (str): ID of the session.
        category_id (str): ID of the category to update.
        name (Optional[str]): New name for the category.
        description (Optional[str]): New description for the category.
        is_child_of (Optional[str]): ID of the new parent category.
        is_parent_of (Optional[str]): ID of the new child category.

    Returns:
        CategoryModel: The updated category.

    Raises:
        ValueError: If the category does not exist within the session.
    """
    # Check if the category exists within the session
    check_query = """
    MATCH (s:SESSION {id: $session_id})-[:HAS]->(c:CATEGORY {id: $category_id})
    RETURN c
    """
    result = tx.run(
        check_query,
        session_id=session_id,
        category_id=category_id,
    ).single()

    if not result:
        raise ValueError(
            f"Category with id '{category_id}' not found in session '{session_id}'."
        )

    # Update the category's properties if provided
    if name or description:
        update_fields = {}
        if name:
            update_fields["name"] = name
        if description:
            update_fields["description"] = description

        # Dynamically build the SET clause based on provided fields
        set_clauses = ", ".join([f"c.{key} = ${key}" for key in update_fields.keys()])
        update_query = f"""
        MATCH (s:SESSION {{id: $session_id}})-[:HAS]->(c:CATEGORY {{id: $category_id}})
        SET {set_clauses}
        """

        tx.run(
            update_query,
            session_id=session_id,
            category_id=category_id,
            **update_fields,
        )
        print(f"Category Updated: {category_id}")

    # # Update IS_CHILD_OF relationship if provided
    # if is_child_of:
    #     # Remove existing IS_CHILD_OF and IS_PARENT_TO relationships
    #     remove_child_rel_query = """
    #     MATCH (c:CATEGORY {id: $category_id})-[r:IS_CHILD_OF]->()
    #     DELETE r
    #     """
    #     remove_parent_rel_query = """
    #     MATCH ()-[r:IS_PARENT_TO]->(c:CATEGORY {id: $category_id})
    #     DELETE r
    #     """
    #     tx.run(
    #         remove_child_rel_query,
    #         category_id=category_id,
    #     )
    #     tx.run(
    #         remove_parent_rel_query,
    #         category_id=category_id,
    #     )
    #     # Create new IS_CHILD_OF and IS_PARENT_TO relationships
    #     add_child_rel_query = """
    #     MATCH (parent:CATEGORY {id: $parent_id}), (child:CATEGORY {id: $child_id})
    #     CREATE (child)-[:IS_CHILD_OF]->(parent)
    #     CREATE (parent)-[:IS_PARENT_TO]->(child)
    #     """
    #     tx.run(
    #         add_child_rel_query,
    #         parent_id=is_child_of,
    #         child_id=category_id,
    #     )
    #     print(
    #         f"IS_CHILD_OF relationship updated: {category_id} is now child of {is_child_of}"
    #     )
    # else:
    #     # if is_child_of is not provided remove exising IS_CHILD_OF and IS_PARENT_TO relationships
    #     remove_child_rel_query = """
    #     MATCH (c:CATEGORY {id: $category_id})-[r:IS_CHILD_OF]->()
    #     DELETE r
    #     """
    #     remove_parent_rel_query = """
    #     MATCH ()-[r:IS_PARENT_TO]->(c:CATEGORY {id: $category_id})
    #     DELETE r
    #     """
    #     tx.run(
    #         remove_child_rel_query,
    #         category_id=category_id,
    #     )
    #     tx.run(
    #         remove_parent_rel_query,
    #         category_id=category_id,
    #     )
    #     print(
    #         f"IS_CHILD_OF relationship removed: {category_id} is no longer child of any category"
    #     )

    # # Update IS_PARENT_OF relationship if provided
    # if is_parent_of:
    #     # Remove existing IS_PARENT_TO and IS_CHILD_OF relationships
    #     remove_parent_rel_query = """
    #     MATCH (c:CATEGORY {id: $category_id})-[r:IS_PARENT_TO]->()
    #     DELETE r
    #     """
    #     remove_child_rel_query = """
    #     MATCH ()-[r:IS_CHILD_OF]->(c:CATEGORY {id: $category_id})
    #     DELETE r
    #     """
    #     tx.run(
    #         remove_parent_rel_query,
    #         category_id=category_id,
    #     )
    #     tx.run(
    #         remove_child_rel_query,
    #         category_id=category_id,
    #     )
    #     # Create new IS_PARENT_TO and IS_CHILD_OF relationships
    #     add_parent_rel_query = """
    #     MATCH (parent:CATEGORY {id: $parent_id}), (child:CATEGORY {id: $child_id})
    #     CREATE (parent)-[:IS_PARENT_TO]->(child)
    #     CREATE (child)-[:IS_CHILD_OF]->(parent)
    #     """
    #     tx.run(
    #         add_parent_rel_query,
    #         parent_id=category_id,
    #         child_id=is_parent_of,
    #     )
    #     print(
    #         f"IS_PARENT_TO relationship updated: {category_id} is now parent of {is_parent_of}"
    #     )
    # else:
    #     # if is_parent_of is not provided remove exising IS_PARENT_TO and IS_CHILD_OF relationships
    #     remove_parent_rel_query = """
    #     MATCH (c:CATEGORY {id: $category_id})-[r:IS_PARENT_TO]->()
    #     DELETE r
    #     """
    #     remove_child_rel_query = """
    #     MATCH ()-[r:IS_CHILD_OF]->(c:CATEGORY {id: $category_id})
    #     DELETE r
    #     """
    #     tx.run(
    #         remove_parent_rel_query,
    #         category_id=category_id,
    #     )
    #     tx.run(
    #         remove_child_rel_query,
    #         category_id=category_id,
    #     )
    #     print(
    #         f"IS_PARENT_TO relationship removed: {category_id} is no longer parent of any category"
    #     )

    # Fetch the updated category to return
    get_category_query = """
    MATCH (s:SESSION {id: $session_id})-[:HAS]->(c:CATEGORY {id: $category_id})
    RETURN c.id AS id, c.name AS name, c.description AS description
    """
    updated_result = tx.run(
        get_category_query,
        session_id=session_id,
        category_id=category_id,
    ).single()

    if updated_result:
        return CategoryModel(
            id=updated_result["id"],
            name=updated_result["name"],
            description=updated_result["description"],
        )
    else:
        raise ValueError(
            f"Failed to update category with id '{category_id}' in session '{session_id}'."
        )
