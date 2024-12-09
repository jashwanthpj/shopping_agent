from pinecone import Pinecone
import psycopg2
from sentence_transformers import SentenceTransformer

# model = SentenceTransformer('all-MiniLM-L6-v2')
model = SentenceTransformer('all-mpnet-base-v2')

database = "shopping_chatbot"
user = "postgres"
password = ""
host = "localhost"

def connect_db(dbname):
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host
        )
        return conn
    except Exception as e:
        print(f"Error connecting to Database {dbname}: ", e)


conn = connect_db(database)
cursor = conn.cursor()

cursor.execute("""
    SELECT id, pdt_desc, uri FROM apparels
""")
embeddings = cursor.fetchall()

# print(embeddings[1])

vectors = []

i=0
for vector in embeddings:
    id, description, uri = vector

    vectors.append({
        "id" : str(id),
        "values" : model.encode(description).tolist(),
        "metadata" : {
            "description" : description,
            "uri" : uri
        }
    })
    i += 1
    print("done : " , i)

print("completed with the vector conversions")


pc = Pinecone(api_key="pcsk_6zDjF8_CGveaQt9SV6zkJZKCqwnRQ67PxRqD8z9gWrqYvpcounvgpWWmp6NkZmKDBbLoHJ")
index = pc.Index("shopping-chatbot")

def chunk_list(data, chunk_size):
    """Split data into chunks of a specified size."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

chunk_size = 100  # Adjust this size based on the vector length and the payload size
for batch in chunk_list(vectors, chunk_size):
    # Send each batch to Pinecone
    index.upsert(vectors=batch)


# index.upsert(vectors=vectors)
print("upsert completed")