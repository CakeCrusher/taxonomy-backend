# **Backend README**

# Taxonomy Synthesis API

An AI-driven API for generating taxonomies and classifying items using OpenAI's GPT models.

## Overview

This API provides endpoints to generate subcategories and classify items into categories using AI. It leverages the `taxonomy-synthesis` package and OpenAI's GPT models to automate the creation and management of taxonomies.

## Directory Structure

```
.
├── __pycache__
│   └── main.cpython-311.pyc
├── main.py
└── requirements.txt
```

## Requirements

- Python 3.7+
- An OpenAI API key

## Quickstart

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Create a Virtual Environment

It's recommended to use a virtual environment to manage dependencies.

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

### 3. Install Dependencies

Install the required packages using `requirements.txt`.

```bash
pip install -r requirements.txt
```

**Contents of `requirements.txt`:**

```
fastapi
uvicorn
taxonomy-synthesis
openai
```

### 4. Run the Server

Start the FastAPI server using Uvicorn.

```bash
uvicorn main:app --host 0.0.0.0 --port 4000 --reload
```

This will run the server on `http://localhost:4000`.

### 5. Test the API

You can test the API endpoints using a tool like `curl` or Postman.

#### **Generate Classes Endpoint**

- **URL:** `http://localhost:4000/generate_classes`
- **Method:** `POST`
- **Request Body:**

  ```json
  {
    "items": [/* list of items */],
    "category": {
      "name": "Animals",
      "description": "All animal species"
    },
    "num_categories": 2,
    "api_key": "your-openai-api-key"
  }
  ```

- **Response:**

  ```json
  {
    "categories": [
      {
        "name": "Mammals",
        "description": "Description generated by AI"
      },
      {
        "name": "Reptiles",
        "description": "Description generated by AI"
      }
    ]
  }
  ```

#### **Classify Items Endpoint**

- **URL:** `http://localhost:4000/classify_items`
- **Method:** `POST`
- **Request Body:**

  ```json
  {
    "categories": [
      {
        "name": "Mammals",
        "description": "Warm-blooded vertebrates"
      },
      {
        "name": "Reptiles",
        "description": "Cold-blooded vertebrates"
      }
    ],
    "items": [
      {"id": "1", "name": "Elephant"},
      {"id": "2", "name": "Crocodile"}
    ],
    "api_key": "your-openai-api-key"
  }
  ```

- **Response:**

  ```json
  {
    "classified_items": [
      {
        "item": {"id": "1", "name": "Elephant"},
        "category": {"name": "Mammals", "description": "Warm-blooded vertebrates"}
      },
      {
        "item": {"id": "2", "name": "Crocodile"},
        "category": {"name": "Reptiles", "description": "Cold-blooded vertebrates"}
      }
    ]
  }
  ```

## Notes

- **API Key Security:** Ensure that your OpenAI API key is kept secure. Do not hard-code it or commit it to version control.
- **CORS Configuration:** The server allows CORS from any origin for development purposes. Adjust the `allow_origins` setting in `main.py` as needed.
- **Error Handling:** The API includes basic error handling. Enhance it as needed for production use.
- **Extensibility:** You can extend the API by adding more endpoints or integrating additional features from the `taxonomy-synthesis` package.

## Dependencies

Ensure the following packages are included in your `requirements.txt`:

- `fastapi`
- `uvicorn`
- `taxonomy-synthesis`
- `openai`

## Contact

For any questions or issues, please contact the project maintainer.

---