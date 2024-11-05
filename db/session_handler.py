# db/session_handler.py

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
        driver, name="Root Category", description="This is the root category"
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
