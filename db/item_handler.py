# db/item_handler.py

from neo4j import Driver
from typing import Optional
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
    # Generate a unique id_ (UUID) for the item
    id_ = str(uuid.uuid4())
    # Create an ItemModel instance by adding id_ to the TSItem
    properties = item.model_dump(exclude={"id", "id_"})
    properties = json.dumps(properties)
    item_model = ItemModel(id_=id_, id=item.id, properties=properties)

    with driver.session() as session:
        session.execute_write(
            _create_item_tx, session_id, item_model, is_contained_inside
        )
    return item_model


def _create_item_tx(
    tx, session_id: str, item: ItemModel, is_contained_inside: Optional[str]
):
    # Prepare properties excluding 'id' and 'id_' since they're already used

    # Create ITEM node and establish HAS relationship with SESSION
    tx.run(
        """
        MATCH (s:SESSION {id: $session_id})
        CREATE (i:ITEM {id: $id, id_: $id_, properties: $properties})
        CREATE (s)-[:HAS]->(i)
        """,
        session_id=session_id,
        id=item.id,
        id_=item.id_,
        properties=item.properties,
    )
    print("Item Created: ", item.id)

    # If is_contained_inside is provided, create CONTAINS relationship with CATEGORY
    if is_contained_inside:
        tx.run(
            """
            MATCH (c:CATEGORY {id: $category_id}), (i:ITEM {id_: $id_})
            CREATE (c)-[:CONTAINS]->(i)
            """,
            category_id=is_contained_inside,
            id_=item.id_,
        )
