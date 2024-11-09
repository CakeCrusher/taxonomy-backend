# db/session_handler.py

import json
from neo4j import Driver
from pydantic import BaseModel
import uuid
from db.category_handler import create_category


class SessionModel(BaseModel):
    id: str


def create_session(driver: Driver) -> SessionModel:
    session_id = str(uuid.uuid4())
    # make session_id url safe
    session_id = session_id.replace("-", "")
    with driver.session() as db_session:
        db_session.execute_write(_create_session_tx, session_id)

    # Create a root category with template inputs
    root_category = create_category(
        driver,
        name="Root Category",
        description="This is the root category",
        session_id=session_id,
    )

    # Create HAS_ROOT relationship between the session and root category
    with driver.session() as db_session:
        db_session.execute_write(
            _create_has_root_relationship_tx, session_id, root_category.id
        )

    return SessionModel(id=session_id)


def _create_session_tx(tx, session_id: str):
    tx.run(
        """
        CREATE (s:SESSION {id: $id})
        """,
        id=session_id,
    )


def _create_has_root_relationship_tx(tx, session_id: str, category_id: str):
    tx.run(
        """
        MATCH (s:SESSION {id: $session_id}), (c:CATEGORY {id: $category_id})
        CREATE (s)-[:HAS_ROOT]->(c)
        """,
        session_id=session_id,
        category_id=category_id,
    )


def get_session_data(driver: Driver, session_id: str):
    with driver.session() as session:
        result = session.execute_read(_get_session_data_tx, session_id)
        return result


def _get_session_data_tx(tx, session_id: str):
    # Query to get categories, their parent relationships, and contained items
    query = """
    MATCH (s:SESSION {id: $session_id})-[:HAS]->(c:CATEGORY)
    OPTIONAL MATCH (c)-[:IS_CHILD_OF]->(parent:CATEGORY)
    OPTIONAL MATCH (c)-[:CONTAINS]->(i:ITEM)
    RETURN c, parent, collect(DISTINCT i) as items
    """
    records = tx.run(query, session_id=session_id).data()

    # Dictionaries to hold categories and their relationships
    categories = {}
    category_parents = {}

    for record in records:
        category_node = record["c"]
        parent_node = record.get("parent")
        item_nodes = record["items"]

        category_id = category_node["id"]
        category = {
            "id": category_id,
            "name": category_node["name"],
            "description": category_node["description"],
            "children": [],
            "items": [],
            "position": {"x": 0, "y": 0},
        }
        categories[category_id] = category

        if parent_node:
            parent_id = parent_node["id"]
            category_parents[category_id] = parent_id

        # Process items
        for item_node in item_nodes:
            if item_node:
                item_id = item_node["id"]
                properties = json.loads(item_node["properties"])
                item = {"id": item_id, **properties}
                category["items"].append(item)

    # Build the category tree
    for category_id, parent_id in category_parents.items():
        if parent_id in categories:
            parent_category = categories[parent_id]
            child_category = categories[category_id]
            parent_category["children"].append(child_category)

    # Identify root categories (categories without parents)
    root_categories = [
        category
        for category_id, category in categories.items()
        if category_id not in category_parents
    ]

    # Prepare the data for response
    def build_tree_node(category_dict):
        return {
            "value": {
                "id": category_dict["id"],
                "name": category_dict["name"],
                "description": category_dict["description"],
            },
            "children": [build_tree_node(child) for child in category_dict["children"]],
            "items": category_dict["items"],
            "position": category_dict["position"],
        }

    tree_nodes = [build_tree_node(category) for category in root_categories]

    # request all items with (s:SESSION {id: $session_id})-[:HAS]->(i:ITEM) except those that are contained in a category
    orphan_items = []
    query = """
    MATCH (s:SESSION {id: $session_id})-[:HAS]->(i:ITEM)
    WHERE NOT (:CATEGORY)-[:CONTAINS]->(i)
    RETURN i
    """
    records = tx.run(query, session_id=session_id).data()
    for record in records:
        item_node = record["i"]
        item_id = item_node["id"]
        properties = json.loads(item_node["properties"])
        item = {"id": item_id, **properties}
        orphan_items.append(item)

    return {"tree": tree_nodes, "orphan_items": orphan_items}
