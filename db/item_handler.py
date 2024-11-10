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
    Transaction function to update an item and manage relationships.

    Args:
        tx: Neo4j transaction object.
        session_id (str): ID of the session.
        item (TSItem): Item data to be updated.
        is_contained_inside (Optional[str]): CATEGORY ID for the CONTAINS relationship.

    Returns:
        ItemModel: The updated item with a unique `id_`.
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

    # raise error
    if not result:
        raise ValueError(
            f"Item with id '{item.id}' not found in session '{session_id}'."
        )

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
            print(f"CONTAINS relationship removed from category: {current_category}")

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
            print(f"CONTAINS relationship created with category: {is_contained_inside}")

    # Return the updated ItemModel
    updated_item = ItemModel(
        id_=id_,
        id=item.id,
        properties=new_properties_json,
    )
    return updated_item


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


def _delete_item_tx(tx, session_id: str, item_ids: List[str]) -> None:
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


def update_category_items(
    driver: Driver,
    session_id: str,
    category_id: str,
    items: List[TSItem],
) -> List[ItemModel]:
    """
    Updates the items inside a category according to the following rules:
    - If an item in the input list does not exist in the database, it is created and added to the category.
    - If an item exists in the category but is not in the input list, it is deleted from the database.
    - Items that exist both in the category and in the input list are updated.

    Args:
        driver (Driver): Neo4j driver instance.
        session_id (str): ID of the session.
        category_id (str): ID of the category.
        items (List[TSItem]): List of items to update in the category.

    Returns:
        List[ItemModel]: List of updated or created items.
    """
    with driver.session() as session:
        updated_items = session.execute_write(
            _update_category_items_tx, session_id, category_id, items
        )
    return updated_items


def _update_category_items_tx(
    tx, session_id: str, category_id: str, items: List[TSItem]
) -> List[ItemModel]:
    """
    Transaction function to update items inside a category.

    Args:
        tx: Neo4j transaction object.
        session_id (str): ID of the session.
        category_id (str): ID of the category.
        items (List[TSItem]): List of items to update in the category.

    Returns:
        List[ItemModel]: List of updated or created items.
    """
    input_item_ids = set(item.id for item in items)

    # Get existing items in the category
    existing_items_query = """
    MATCH (s:SESSION {id: $session_id})-[:HAS]->(i:ITEM)<-[:CONTAINS]-(c:CATEGORY {id: $category_id})
    RETURN i.id AS id
    """
    existing_items_result = tx.run(
        existing_items_query, session_id=session_id, category_id=category_id
    )
    existing_item_ids = set(record["id"] for record in existing_items_result)

    # Determine items to create, update, and delete
    items_to_create = [item for item in items if item.id not in existing_item_ids]
    items_to_update = [item for item in items if item.id in existing_item_ids]
    items_to_delete_ids = list(existing_item_ids - input_item_ids)

    # Delete surplus items from the session
    if items_to_delete_ids:
        _delete_item_tx(tx, session_id, items_to_delete_ids)

    # Update existing items
    updated_items = []
    for item in items_to_update:
        try:
            updated_item = _update_item_tx(tx, session_id, item, category_id)
            updated_items.append(updated_item)
        except ValueError as ve:
            # Item does not exist; raise an error
            raise ve

    # Create new items and associate them with the category
    for item in items_to_create:
        created_item = _create_item_tx(tx, session_id, item, category_id)
        updated_items.append(created_item)

    return updated_items
