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
    global conversation_history

    print("USER QUERY:\n", user_query,"\n\n")
    print("CONTEXT:\n", context,"\n\n")

    # Initialize the SentenceTransformer model
    model = SentenceTransformer('all-mpnet-base-v2')
    

    client = OpenAI()
    OpenAI.api_key = os.getenv('api_key')
    # ------------------------------------------------------------------------------------------
    prompt_for_query = f"""
            Given the previous list of user queries and the current query, combine them to generate the exact query the user is making.
            The previous queries provide context to the current query. Ensure the generated query logically integrates the context and reflects the user's intent as accurately as possible.
            Always refer to the latest product, category queried by user and without context don't decide the color for current product.
            Previous queries: {context}
            Current query: {user_query}

            Example:
            Previous queries: ['I want tshirts', 'for boys', 'white color', 'shoes', 'black color']
            Current query: 'blue color'
            Generated exact query: "shoes with blue color"
            ONLY return the exact query, no additional text or explanation. 
    """
    try: 
            # Call OpenAI API with the entire prompt at once
            LLM_output_for_query = client.chat.completions.create(
                model="gpt-4o-mini",
                # model="GPT-3.5-turbo",
                messages=
                [
                    {"role": "system", "content": "You are a helpful Assistant."},
                    {
                        "role": "user",
                        "content": prompt_for_query
                    }
                ]
            )
            structured_query = LLM_output_for_query.choices[0].message.content
            print("THIS IS LLM OUTPUT(RAW): \n", structured_query)

    except Exception as e:
            print(f"An error occurred while calling OpenAI for structured query: {e}")
    # ------------------------------------------------------------------------------------------

    # Embedding the user's query
    query_embedding = model.encode(structured_query).tolist()

    # Initialize Pinecone client and index
    pc = Pinecone(api_key="pcsk_6zDjF8_CGveaQt9SV6zkJZKCqwnRQ67PxRqD8z9gWrqYvpcounvgpWWmp6NkZmKDBbLoHJ")
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

        print("RESPONSES FROM CONEPINE COSINE SIMILARITY:\n", "\n")

        for match in response['matches']:
            pdt_desc = match['metadata']['description']
            uri = match['metadata']['uri']

            product_descriptions.append(pdt_desc)  # Append product descriptions to the list

            product_data = {
                "uri": uri,
                "description": pdt_desc
            }
            print(product_data,"\n")

            product_list.append(product_data)
        
        prompt = f"""
            You are an assistant that matches user queries with product records.

            Read this current user search query: '{structured_query}'
            Compare it against the following product records: {product_list}

            ### Instructions ###
            1. Match each product record to the user query based on the following rules:  
            - **Exact Category Match**: Only include products explicitly matching the user query's category (e.g., "caps"). Products in unrelated or different categories (e.g., "t-shirts") must be excluded, even if they contain semantically related keywords.  
            - **Mandatory Keyword Matching**: Ensure the product description contains all key terms directly relevant to the query. If the query specifies "red caps," products must explicitly mention both "red" and "caps." Omit products that are missing any keyword or that conflict with the query's details.  
            - **Exclude Unrelated Products**: Products that do not align with the user’s intent, wrong subcategory, or wrong gender should not be included.  

            2. **Sorting and Filtering**:
            - Strictly include only the max 4 products with the highest match percentage, sorted in descending order of relevance.  
            - Exclude all products with a match percentage of less than 85%.  
            - If no products meet the criteria (e.g., query category or mandatory keywords are unmatched), return an empty json in the results.  
            """

        # print("PROMPT GIVEN TO OPENAI:\n", prompt,"\n\n")

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
                    }
                }
            }
        }

        
        try:
            # Call OpenAI API with the entire prompt at once
            LLM_output = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=
                # conversation_history,
                [
                    {"role": "system", "content": "You are a shopping assistant."},
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                functions=[function_schema]
            )

            # print("THIS IS LLM OUTPUT(RAW): \n", LLM_output)

            try:
                LLM_response = LLM_output.choices[0].message.function_call.arguments
            except:
                LLM_response = LLM_output.choices[0].message.content

            # print("THIS IS LLM RESPONSE FROM GIVEN PROMPT:\n", LLM_response,"\n\n")

            suggestions_json = json.loads(LLM_response)

            conversation_history.append({
                "role" : "assistant",
                "content" : json.dumps(suggestions_json, indent=2)
            })

            
        # except OpenAI.error.OpenAIError as e:
        except Exception as e:
            print(f"An error occurred while calling OpenAI: {e}")
        
        print("#"*100,"\n")
        return suggestions_json

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# user_q = "Give me yellow footwear"
# print(build_suggestions_json(user_q))