# main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from taxonomy_synthesis.models import Category, Item, ClassifiedItem
from taxonomy_synthesis.tree.tree_node import TreeNode
from taxonomy_synthesis.tree.node_operator import NodeOperator
from taxonomy_synthesis.generator.taxonomy_generator import TaxonomyGenerator
from taxonomy_synthesis.classifiers.gpt_classifier import GPTClassifier
from fastapi.middleware.cors import CORSMiddleware

from openai import OpenAI


# Define the request model for generate_classes
class GenerateClassesRequest(BaseModel):
    items: List[Item]  # items in current node
    category: Category  # category of current node
    num_categories: int
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


app = FastAPI(title="Taxonomy Synthesis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper function to initialize OpenAI client
def get_openai_client(api_key: str):
    return OpenAI(api_key=api_key)


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
            generation_method="Generate subcategories based on the parent category.",
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
