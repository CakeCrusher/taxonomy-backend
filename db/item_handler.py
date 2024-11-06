# db/item_handler.py

from neo4j import Driver
from typing import Optional, List
import uuid
import json

from taxonomy_synthesis.models import Item as TSItem  # Imported TSItem


class ItemModel(TSItem):
    id_: str  # Unique across the database
    properties: str  # JSON string of the properties


# Create Item Function
def create_item(
    driver: Driver,
    session_id: str,
    item: TSItem,
    is_contained_inside: Optional[str] = None,
) -> ItemModel:
    """
    Creates a new item within the specified session.

    Args:
        driver (Driver): Neo4j driver instance.
        session_id (str): ID of the session.
        item (TSItem): Item data to be created.
        is_contained_inside (Optional[str]): CATEGORY ID for the CONTAINS relationship.

    Returns:
        ItemModel: The created item with a unique `id_`.
    """
    with driver.session() as session:
        res = session.execute_write(
            _create_item_tx, session_id, item, is_contained_inside
        )

    return res


def _create_item_tx(
    tx, session_id: str, item: TSItem, is_contained_inside: Optional[str]
) -> ItemModel:
    """
    Transaction function to create an item and establish relationships.

    Args:
        tx: Neo4j transaction object.
        session_id (str): ID of the session.
        item (TSItem): Item data to be created.
        is_contained_inside (Optional[str]): CATEGORY ID for the CONTAINS relationship.

    Returns:
        ItemModel: The created item with a unique `id_`.
    """
    # Generate a unique id_ (UUID) for the item
    id_ = str(uuid.uuid4())

    # Extract properties excluding 'id' and 'id_'
    properties = item.model_dump(exclude={"id", "id_"})
    properties_json = json.dumps(properties)

    # Create an ItemModel instance by adding id_ to the TSItem
    item_model = ItemModel(id_=id_, id=item.id, properties=properties_json)

    # Create ITEM node and establish HAS relationship with SESSION
    create_item_query = """
    MATCH (s:SESSION {id: $session_id})
    CREATE (i:ITEM {id: $id, id_: $id_, properties: $properties})
    CREATE (s)-[:HAS]->(i)
    """
    tx.run(
        create_item_query,
        session_id=session_id,
        id=item_model.id,
        id_=item_model.id_,
        properties=item_model.properties,
    )
    print(f"Item Created: {item.id}")

    # If is_contained_inside is provided, create CONTAINS relationship with CATEGORY
    if is_contained_inside:
        create_contains_query = """
        MATCH (c:CATEGORY {id: $category_id}), (i:ITEM {id_: $id_})
        CREATE (c)-[:CONTAINS]->(i)
        """
        tx.run(
            create_contains_query,
            category_id=is_contained_inside,
            id_=item_model.id_,
        )

    return item_model


# Update Item Function
def update_item(
    driver: Driver,
    session_id: str,
    item: TSItem,
    is_contained_inside: Optional[str] = None,
) -> ItemModel:
    """
    Updates an existing item within the specified session. If the item does not exist, it will be created.

    Args:
        driver (Driver): Neo4j driver instance.
        session_id (str): ID of the session.
        item (TSItem): Item data to be updated.
        is_contained_inside (Optional[str]): CATEGORY ID for the CONTAINS relationship.

    Returns:
        ItemModel: The updated or newly created item with a unique `id_`.
    """
    with driver.session() as session:
        res = session.execute_write(
            _update_item_tx, session_id, item, is_contained_inside
        )

    return res


def _update_item_tx(
    tx, session_id: str, item: TSItem, is_contained_inside: Optional[str]
) -> ItemModel:
    """
    Transaction function to update an item and manage relationships. If the item does not exist, it will be created.

    Args:
        tx: Neo4j transaction object.
        session_id (str): ID of the session.
        item (TSItem): Item data to be updated.
        is_contained_inside (Optional[str]): CATEGORY ID for the CONTAINS relationship.

    Returns:
        ItemModel: The updated or newly created item with a unique `id_`.
    """
    # Attempt to find the item by 'id' within the session
    find_item_query = """
    MATCH (s:SESSION {id: $session_id})-[:HAS]->(i:ITEM {id: $id})
    OPTIONAL MATCH (c:CATEGORY)-[:CONTAINS]->(i)
    RETURN i.id_ AS id_, i.properties AS properties, c.id AS current_category
    """
    result = tx.run(
        find_item_query,
        session_id=session_id,
        id=item.id,
    ).single()

    if result:
        # Item exists; proceed to update
        id_ = result["id_"]
        current_category = result["current_category"]

        # Serialize new properties
        new_properties = item.model_dump(exclude={"id", "id_"})
        new_properties_json = json.dumps(new_properties)

        # Update ITEM properties
        update_properties_query = """
        MATCH (s:SESSION {id: $session_id})-[:HAS]->(i:ITEM {id: $id})
        SET i.properties = $properties
        """
        tx.run(
            update_properties_query,
            session_id=session_id,
            id=item.id,
            properties=new_properties_json,
        )
        print(f"Item Updated: {item.id}")

        # Handle CONTAINS relationship
        if is_contained_inside != current_category:
            if current_category:
                # Remove existing CONTAINS relationship
                remove_contains_query = """
                MATCH (c:CATEGORY)-[r:CONTAINS]->(i:ITEM {id_: $id_})
                DELETE r
                """
                tx.run(
                    remove_contains_query,
                    id_=id_,
                )
                print(
                    f"CONTAINS relationship removed from category: {current_category}"
                )

            if is_contained_inside:
                # Create new CONTAINS relationship
                create_contains_query = """
                MATCH (c:CATEGORY {id: $category_id}), (i:ITEM {id_: $id_})
                CREATE (c)-[:CONTAINS]->(i)
                """
                tx.run(
                    create_contains_query,
                    category_id=is_contained_inside,
                    id_=id_,
                )
                print(
                    f"CONTAINS relationship created with category: {is_contained_inside}"
                )

        # Return the updated ItemModel
        updated_item = ItemModel(
            id_=id_,
            id=item.id,
            properties=new_properties_json,
        )
        return updated_item
    else:
        # Item does not exist; create it
        print(
            f"Item with id '{item.id}' not found in session '{session_id}'. Creating new item."
        )
        return _create_item_tx(tx, session_id, item, is_contained_inside)


# Delete Item Function
def delete_item(driver: Driver, session_id: str, item_ids: List[str]) -> None:
    """
    Deletes items within the specified session based on their IDs.

    Args:
        driver (Driver): Neo4j driver instance.
        session_id (str): ID of the session.
        item_ids (List[str]): List of item IDs to be deleted.

    Returns:
        None
    """
    with driver.session() as session:
        session.execute_write(_delete_item_tx, session_id, item_ids)


def _delete_item_tx(tx, session_id: str, item_ids: List[str]):
    """
    Transaction function to delete items and their relationships.

    Args:
        tx: Neo4j transaction object.
        session_id (str): ID of the session.
        item_ids (List[str]): List of item IDs to be deleted.

    Returns:
        None
    """
    delete_items_query = """
    MATCH (s:SESSION {id: $session_id})-[:HAS]->(i:ITEM)
    WHERE i.id IN $item_ids
    DETACH DELETE i
    """
    tx.run(delete_items_query, session_id=session_id, item_ids=item_ids)
    print(f"Items Deleted: {item_ids}")
