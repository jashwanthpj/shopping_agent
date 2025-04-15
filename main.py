from sentence_transformers import SentenceTransformer
from openai import OpenAI
from pinecone import Pinecone
import json
from dotenv import load_dotenv
import os

def configure():
    load_dotenv()

conversation_history = []

def build_suggestions_json(user_query, context):
    # Call configure to load environment variables
    configure()
    
    # Initialize the SentenceTransformer model
    print("🚀 ~ context:", context)
    model = SentenceTransformer('all-mpnet-base-v2')
    
    # Get API key from environment or provide a default for testing
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OpenAI API key is missing. Please set the OPENAI_API_KEY environment variable or add it to your .env file.")
        
    # Initialize the OpenAI client with the API key
    client = OpenAI(api_key=openai_api_key)
    
    prompt_for_query = f"""
            Given the previous list of user queries and the current query, combine them to generate the exact query the user is making.
            The previous queries provide context to the current query. Ensure the generated query logically integrates the context and reflects the user's intent as accurately as possible.
            Always refer to the latest product, category queried by user and without context don't decide the color for current product.
            Previous queries: {context}
            Current query: {user_query}

            if query is not related to product or category, return {user_query}

            Example:
            Previous queries: ['I want tshirts', 'for boys', 'white color', 'shoes', 'black color']
            Current query: 'blue color'
            Generated exact query: "shoes with blue color"
            ONLY return the exact query, no additional text or explanation. 
    """
    try: 
        # Create messages array with system message and conversation history
        messages = [
            {"role": "system", "content": "You are a helpful Assistant."}
        ]
        messages.append({"role": "user", "content": prompt_for_query})

        # Call OpenAI API with conversation history
        LLM_output_for_query = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        structured_query = LLM_output_for_query.choices[0].message.content

    except Exception as e:
        print(f"An error occurred while calling OpenAI for structured query: {e}")
    # ------------------------------------------------------------------------------------------

    # Embedding the user's query
    query_embedding = model.encode(structured_query).tolist()

    # Initialize Pinecone client and index
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index("shopping-chatbot")

    try:
        # Query Pinecone index for similar products
        response = index.query(
            vector=query_embedding,
            top_k=10,
            include_values=True,
            include_metadata=True
        )

        product_list = []
        product_descriptions = []  # Store product descriptions to send in one OpenAI request
 
        for match in response['matches']:
            pdt_desc = match['metadata']['description']
            uri = match['metadata']['uri']

            product_descriptions.append(pdt_desc)  # Append product descriptions to the list

            product_data = {
                "uri": uri,
                "description": pdt_desc
            }

            product_list.append(product_data)

        # Define the function schema for structured output 
        function_schema = {
            "name": "suggestions",
            "description": "Returns product suggestions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "match": {"type": "string"},
                                "match_percentage": {"type": "number"},
                                "product_url": {"type": "string"},
                                "product_description": {"type": "string"}
                            },
                            "required": ["match", "match_percentage", "product_url", "product_description"]
                        }
                    },
                    "fallback_response": {
                        "type": "string",
                        "description": "A helpful and frindly response suitable for user query to the user, If query is greeting, return a greeting response, If user asks any general fashion related query, return a response based on the context"
                    }
                },
                "required": ["query", "results"]
            }
        }

        
        try:
            system_prompt = f"""
            You are a specialized shopping assistant that accurately matches user search queries to product listings.

            Your primary goal is to return only the most relevant products that precisely match the user's search intent. You must follow these strict matching rules:

            1. EXACT CATEGORY MATCHING: Only include products that belong to the exact category the user is searching for (e.g., "shoes" should not return flip-flops or sandals).

            2. KEYWORD PRECISION: All key terms in the user's query must appear in the product description. Missing any essential keyword disqualifies the product.

            3. RELEVANCE FILTERING: Return a maximum of 4 products with at least 85% match relevance, sorted in descending order of match percentage.

            4. CLEAN OUTPUT: Respond with a valid JSON object containing:
               - The query
               - Matched results array
               - A fallback_response when no matches are found, provide a helpful fallback_response suitable for user query to user.

            Example Correct Matches:
            Query: "black formal shoes"
            ✓ "Men's Black Leather Oxford Formal Shoes"
            ✗ "Black Casual Flip-flops" (wrong category)
            ✗ "Navy Blue Formal Shoes" (wrong color)
            
            Query: "blue formal shirts"
            ✓ "Men's Blue Cotton Formal Shirt"
            ✗ "Blue Cotton T-shirt" (wrong category)
            ✗ "Navy Formal Shirt" (not exact color match)

            If no products meet the criteria, provide a helpful fallback_response suitable for user query to user.
            """
            
            # Create user message with product matching prompt
            user_message = {
                "role": "user", 
                "content": f"""
                Read this current user search query: '{structured_query}'
                Compare it against the following product records: {product_list}  
                """
            }
            
            # messages.append(user_message)
            conversation_history.append(user_message)  # Add user message to history

            # Call OpenAI API with the conversation history
            LLM_output = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", 
                     "content": system_prompt}
                ] + conversation_history,
                functions=[function_schema]
            )

            try:
                LLM_response = LLM_output.choices[0].message.function_call.arguments
            except:
                LLM_response = LLM_output.choices[0].message.content

            # Add assistant's response to conversation history
            assistant_message = {
                "role": "assistant",
                "content": LLM_response
            }
            conversation_history.append(assistant_message)
            suggestions_json = json.loads(LLM_response)
            print("🚀 ~ suggestions_json:", suggestions_json)
            return suggestions_json

        except Exception as e:
            print(f"An error occurred while calling OpenAI: {e}")
        
        print("#"*100,"\n")
        return suggestions_json

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# user_q = "Give me yellow footwear"
# print(build_suggestions_json(user_q))
