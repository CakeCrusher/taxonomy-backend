# main.py

from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import List, Optional

from taxonomy_synthesis.models import Category, Item, ClassifiedItem
from taxonomy_synthesis.tree.tree_node import TreeNode
from taxonomy_synthesis.tree.node_operator import NodeOperator
from taxonomy_synthesis.generator.taxonomy_generator import TaxonomyGenerator
from taxonomy_synthesis.classifiers.gpt_classifier import GPTClassifier
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from openai import OpenAI
from dotenv import load_dotenv

import os

from db.item_handler import ItemModel, create_item, delete_item, update_item
from db.session_handler import SessionModel, create_session

load_dotenv()


# Define the request model for generate_classes
class GenerateClassesRequest(BaseModel):
    items: List[Item]  # items in current node
    category: Category  # category of current node
    num_categories: int
    generation_method: str
    api_key: str = Field(..., description="OpenAI API Key")


# Define the response model for generate_classes
class GenerateClassesResponse(BaseModel):
    categories: List[Category]


# Define the request model for classify_items
class ClassifyItemsRequest(BaseModel):
    categories: List[Category]  # subcategories of current node
    items: List[Item]  # items in current node
    api_key: str = Field(..., description="OpenAI API Key")


# Define the response model for classify_items
class ClassifyItemsResponse(BaseModel):
    classified_items: List[ClassifiedItem]


@asynccontextmanager
async def lifespan(app: FastAPI):
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not username or not password:
        raise Exception("Missing Neo4j credentials")
    app.state.neo4j_driver = GraphDatabase.driver(uri, auth=(username, password))
    yield
    app.state.neo4j_driver.close()


app = FastAPI(title="Taxonomy Synthesis API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db(request: Request):
    return request.app.state.neo4j_driver


# Helper function to initialize OpenAI client
def get_openai_client(api_key: str):
    return OpenAI(api_key=api_key)


@app.post("/initialize_session", response_model=SessionModel)
def initialize_session(request: Request):
    try:
        driver = get_db(request)
        session_model = create_session(driver)
        return session_model
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Define the request model for create_items
class CreateItemsRequest(BaseModel):
    session_id: str
    items: List[Item]  # List of TSItem objects with arbitrary fields
    is_contained_inside: Optional[str] = None  # Optional CATEGORY ID


# Define the response model for create_items
class CreateItemsResponse(BaseModel):
    items: List[ItemModel]  # List of created ItemModel objects


@app.post("/create_items", response_model=CreateItemsResponse)
def create_items_endpoint(request: Request, create_req: CreateItemsRequest):
    """
    Endpoint to create multiple items within a session.

    - **session_id**: ID of the session.
    - **items**: List of items to be created. Each item must have an `id` and can have arbitrary additional fields.
    - **is_contained_inside**: Optional CATEGORY ID to establish a CONTAINS relationship.

    Returns the list of created items with their unique `_id`s.
    """
    try:
        driver = get_db(request)
        created_items: List[ItemModel] = []

        for ts_item in create_req.items:
            # Create the item and receive the ItemModel with _id
            item_model = create_item(
                driver=driver,
                session_id=create_req.session_id,
                item=ts_item,
                is_contained_inside=create_req.is_contained_inside,
            )
            created_items.append(item_model)

        return CreateItemsResponse(items=created_items)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Define the request model for update_items
class UpdateItemsRequest(BaseModel):
    session_id: str
    items: List[Item]  # List of TSItem objects with arbitrary fields
    is_contained_inside: Optional[str] = None  # Optional CATEGORY ID


# Define the response model for update_items
class UpdateItemsResponse(BaseModel):
    items: List[ItemModel]  # List of updated ItemModel objects


@app.post("/update_items", response_model=UpdateItemsResponse)
def update_items_endpoint(request: Request, update_req: UpdateItemsRequest):
    """
    Endpoint to update multiple items within a session.

    - **session_id**: ID of the session.
    - **items**: List of items to be updated. Each item must have an `id` and can have arbitrary additional fields.
    - **is_contained_inside**: Optional CATEGORY ID to update the CONTAINS relationship.

    Returns the list of updated or newly created items with their unique `id_`.
    """
    try:
        driver = get_db(request)
        updated_items = []

        for ts_item in update_req.items:
            # Update the item and receive the updated or created ItemModel with id_
            updated_item = update_item(
                driver=driver,
                session_id=update_req.session_id,
                item=ts_item,
                is_contained_inside=update_req.is_contained_inside,
            )
            updated_items.append(updated_item)

        return UpdateItemsResponse(items=updated_items)

    except ValueError as ve:
        # This is raised if an item to update was not found and couldn't be created
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        # General exception catch-all
        raise HTTPException(status_code=500, detail=str(e))


# Define the request model for delete_items
class DeleteItemsRequest(BaseModel):
    session_id: str
    items: List[Item]  # List of item IDs to be deleted


# Define the response model for delete_items
class DeleteItemsResponse(BaseModel):
    detail: str


@app.post("/delete_items", response_model=DeleteItemsResponse)
def delete_items_endpoint(request: Request, delete_req: DeleteItemsRequest):
    """
    Endpoint to delete multiple items within a session.

    - **session_id**: ID of the session.
    - **items**: List of item IDs to be deleted.

    Returns a confirmation message upon successful deletion.
    """
    try:
        driver = get_db(request)
        item_ids = [item.id for item in delete_req.items]
        delete_item(driver=driver, session_id=delete_req.session_id, item_ids=item_ids)
        return DeleteItemsResponse(detail="Items deleted successfully.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Helper function to create a TreeNode from a Category
def create_tree_node(
    category: Category,
    children: Optional[List[Category]] = None,
    items: Optional[List[Item]] = None,
):
    node = TreeNode(value=category)
    node.items = items or []
    if children:
        for child_category in children:
            child_node = TreeNode(value=child_category)
            node.add_child(child_node)
    return node


@app.post("/generate_classes", response_model=GenerateClassesResponse)
def generate_classes(request: GenerateClassesRequest):
    try:
        # Initialize OpenAI client
        client = get_openai_client(request.api_key)

        classifier = GPTClassifier(client=client)

        # Initialize the Taxonomy Generator
        generator = TaxonomyGenerator(
            client=client,
            max_categories=request.num_categories,
            generation_method=request.generation_method,
        )

        # Initialize the operator without a classifier (not needed here)
        operator = NodeOperator(generator=generator, classifier=classifier)

        root_node = create_tree_node(request.category, items=request.items)

        # Generate subcategories
        new_categories = operator.generate_subcategories(root_node)

        return GenerateClassesResponse(categories=new_categories)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classify_items", response_model=ClassifyItemsResponse)
def classify_items(request: ClassifyItemsRequest):
    try:
        # Initialize OpenAI client
        client = get_openai_client(request.api_key)

        # Initialize the GPT classifier
        classifier = GPTClassifier(client=client)

        # Initialize the Taxonomy Generator
        generator = TaxonomyGenerator(
            client=client,
            max_categories=2,
            generation_method="Generate subcategories based on the parent category.",
        )

        # Initialize the operator without a generator (not needed here)
        operator = NodeOperator(generator=generator, classifier=classifier)

        root_node = create_tree_node(
            Category(name="Root", description="asd"),
            children=request.categories,
            items=request.items,
        )

        # Classify items
        classified_items = operator.classify_items(root_node, root_node.get_all_items())

        return ClassifyItemsResponse(classified_items=classified_items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
