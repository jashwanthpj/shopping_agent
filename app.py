import streamlit as st
import requests
from main import build_suggestions_json
from urllib.parse import urlencode, urlunparse
from datetime import datetime
import psycopg2
import json
import random

dbname = "shopping_chatbot"
user = "postgres"
password = ""
host = "localhost"

COCKROACH_DB_URL = "postgresql://gowtham:nQ5kXObwIbnmDRrGJUTcXQ@ruddy-gerbil-5910.j77.aws-ap-south-1.cockroachlabs.cloud:26257/defaultdb?sslmode=require"
NEON_DB_URL = "postgresql://shopping_chatbot_owner:pON7LcahuDS8@ep-shiny-meadow-a571h2da.us-east-2.aws.neon.tech/shopping_chatbot?sslmode=require"

def connect_db(db_type):
    try:
        if db_type == "local":
            conn = psycopg2.connect(NEON_DB_URL)
        elif db_type == "cockroach":
            if not COCKROACH_DB_URL:
                raise ValueError("CockroachDB URL is not set in the environment variables.")
            conn = psycopg2.connect(COCKROACH_DB_URL)
            # conn = psycopg2.connect(
            #         dbname="defaultdb",
            #         user="gowtham",
            #         password="nQ5kXObwIbnmDRrGJUTcXQ",
            #         host="ruddy-gerbil-5910.j77.aws-ap-south-1.cockroachlabs.cloud",
            #         port=26257,
            #         sslmode="verify-full",
            #         sslrootcert="system"
            #     )
        else:
            raise ValueError("Invalid database type specified.")
        
        return conn

    except Exception as e:
        print(f"Error connecting to {db_type} database: {e}")
        return None

def update_sessions_to_db(chat_sessions, userid):
    with connect_db("local") as conn:
        cursor = conn.cursor()

        session_data_json = json.dumps(dict(chat_sessions))

        cursor.execute(
            "UPDATE user_sessions SET chat_sessions = %s WHERE user_id = %s",
            (session_data_json, userid)
        )
        conn.commit()

def update_wishlist_to_db(wishlist_products, userid):
    with connect_db("local") as conn:
        cursor = conn.cursor()

        session_data_json = json.dumps(wishlist_products)
        cursor.execute(
            "UPDATE wishlist SET products = %s WHERE user_id = %s",
            (session_data_json, userid)
        )
        conn.commit()

def fetch_sessions_from_db(userid):
    with connect_db("local") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chat_sessions FROM user_sessions WHERE user_id = %s",
            (userid,)
        )
        current_user_sessions = cursor.fetchone()

        if current_user_sessions:
            return json.loads(current_user_sessions[0] if isinstance(current_user_sessions[0], str) else json.dumps(current_user_sessions[0]))
        return None
    
def fetch_wishlist_from_db(userid):
    with connect_db("local") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT products FROM wishlist WHERE user_id = %s",
            (userid,)
        )
        current_user_wishlist = cursor.fetchone()

        if current_user_wishlist:
            return current_user_wishlist[0]
        else:
            return {"products":[]}
    

def check_user_in_db(userid):
    with connect_db("local") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM user_sessions WHERE user_id = %s)",
            (userid,)
        )
        user_exists = cursor.fetchone()[0]

        return user_exists
    

def add_user_to_db(userid):
    with connect_db("local") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_sessions (user_id, chat_sessions) VALUES (%s, '{}')",
            (userid,)
        )
        conn.commit()

        wishlist = {"products":[]}
        cursor.execute(
            "INSERT INTO wishlist (user_id, products) VALUES (%s, %s)",
            (userid, json.dumps(wishlist))
        )
        conn.commit()


def check_login_status():
    try:
        query_params = st.query_params
        if query_params.get("logged_in") == "True":
            return True
    except Exception as e:
        print(f"Error checking login status: {e}")
    return False


def redirect_to_login():
    login_url = 'https://af98-115-114-88-222.ngrok-free.app'
    redirect_url = f'{login_url}?next=https://shopping-agent-zyg6.onrender.com'
    st.markdown(f'<meta http-equiv="refresh" content="0; url={redirect_url}" />', unsafe_allow_html=True)
    st.stop()

def chatbot():
    if not check_login_status():
        redirect_to_login()

    userid = int(st.query_params.get("user_id"))
    # st.query_params.from_dict({"logged_in":"True"})

    if not check_user_in_db(userid):
        add_user_to_db(userid)

    # conn = connect_db("cockroach")
    # cursor = conn.cursor()
    # cursor.execute("SELECT username FROM users_login WHERE id = %s",(userid,))
    # mail_id = cursor.fetchone()[0]
    # username = mail_id.split("@")[0]
    
    # Initialize session state for chats if not done already

    username = "User"
    
    if 'chat_sessions' not in st.session_state:
        st.session_state.chat_sessions = fetch_sessions_from_db(userid) or {}
        
    if 'current_chat' not in st.session_state:
        st.session_state.current_chat = None

    # Sidebar: Display all chats (including the current chat)
    st.sidebar.title("Chat Sessions")

    # Save the current chat to the sidebar if not already saved
    if st.session_state.current_chat not in st.session_state.chat_sessions:
        if st.session_state.current_chat:
            st.session_state.chat_sessions[st.session_state.current_chat] = st.session_state.messages

    if st.button('Wish List ❤️', key="wishlist_button"):
        # fetch_wishlist_from_db(userid)
        st.session_state.show_wishlist = True

    if st.button('Log out', key="logout_button"):
        logout_session()
        
    # Simulated popup for wishlist
    if st.session_state.get('show_wishlist', False):
        st.subheader(f"{username}'s Wishlist")
        wishlist_data = fetch_wishlist_from_db(userid)  # Get the data
        
        if "products" in wishlist_data and wishlist_data["products"]:
            # Display each product image
            products = wishlist_data["products"]
            num_columns = 6
            rows = len(products) // num_columns + (len(products) % num_columns > 0)

            for i in range(rows):
                cols = st.columns(num_columns)
                for j in range(num_columns):
                    idx = i * num_columns + j
                    if idx < len(products):
                        with cols[j]:
                            st.image(products[idx], use_container_width=True)
            # for product_url in wishlist_data["products"]:
            #     st.image(product_url, width=200)
        else:
            st.write("Your wishlist is empty!")

        # Close button
        if st.button("Close", key="close_wishlist"):
            st.session_state.show_wishlist = False


    for index, (chat_name, chat_content) in enumerate(st.session_state.chat_sessions.items()):
        # Find the first user message or pick a random friendly phrase
        first_user_message = next(
            (message["content"] for message in chat_content if message["role"] == "user"),
            "Let's get started! 😊"# Random friendly phrase
        )
        # Truncate long messages for better display
        display_name = first_user_message[:30] + "..." if len(first_user_message) > 30 else first_user_message
        
        # Ensure unique key for each button
        button_key = f"{chat_name}_{index}"  # Combines chat_name and index for uniqueness

        if st.sidebar.button(display_name, key=button_key):
            # Save the current chat session before switching
            if st.session_state.current_chat and "messages" in st.session_state:
                st.session_state.chat_sessions[st.session_state.current_chat] = st.session_state.messages
            # Switch to the selected chat
            st.session_state.current_chat = chat_name
            st.session_state.messages = st.session_state.chat_sessions[chat_name]


    # Button to start a new chat
    if st.sidebar.button("New Chat"):
        # Save the current chat before starting a new one
        if st.session_state.current_chat and 'messages' in st.session_state:
            st.session_state.chat_sessions[st.session_state.current_chat] = st.session_state.messages

        # Create a new chat session
        new_chat_name = f"{userid}_Chat_{len(st.session_state.chat_sessions) + 1}"
        st.session_state.current_chat = new_chat_name
        st.session_state.messages = []

    # Ensure a current chat is set
    if not st.session_state.current_chat:
        st.session_state.current_chat = f"{userid}_Chat_{len(st.session_state.chat_sessions) + 1}"
        st.session_state.messages = []

    # Initialize chat messages if it's a new session
    if not st.session_state.messages:
        # username = st.query_params.get("user", "User")
        st.session_state.messages.append({
            "role": "assistant", 
            "content": f"Hello! 👋 Welcome to Smart Shopping AI Agent. How can I assist you today?", 
            "image_urls": []
        })

    # Update the current chat in the sidebar
    current_chat = st.session_state.current_chat[20:]
    st.sidebar.write(f"Current Chat: {current_chat}")

    st.title(f"Smart Shopping AI Agent")

    # Display chat messages
    for message_idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message['role']):
            st.write(message['content'])
            if message['role'] == 'assistant' and message['image_urls']:
                cols = st.columns(4)
                # for col, img_url in zip(cols, message['image_urls']):
                for idx, (col, img_url) in enumerate(zip(cols, message['image_urls'])):
                    with col:
                        st.image(img_url, caption='Product Image')
                        if st.button("wishlist", key=f"wishlist_{message_idx}_{idx}"):
                            wishlist_products = fetch_wishlist_from_db(userid)
                            wishlist_products["products"].append(img_url)
                            update_wishlist_to_db(wishlist_products,userid)

    # User input for search prompt
    prompt = st.chat_input("Search...")

    if prompt:
        # Collect historical context from previous messages
        context = [msg['content'] for msg in st.session_state.messages if msg['role'] == 'user']
        context_text = " ".join(context)

        with st.chat_message("user"):
            st.write(prompt)

        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Generating response...."):
            LLM_response = build_suggestions_json(prompt, context_text)

        image_urls = []
        if LLM_response:
            bot_answer = "These are the products retrieved as per your query!"
            for item in LLM_response['results']:
                image_urls.append(item['product_url'])
        else:
            bot_answer = "I'm sorry, but I couldn't find any products matching your query."

        st.session_state.messages.append({"role": "assistant", "content": bot_answer, "image_urls": image_urls})

        with st.chat_message("assistant"):
            st.write(bot_answer)
            if image_urls:
                cols = st.columns(4)
                for idx, (col, img_url) in enumerate(zip(cols, image_urls)):
                        with col:
                            st.image(img_url, caption='Product Image')
                            wishlist_button_key = f"wishlist_{len(st.session_state.messages)-1}_{idx}"
                            if st.button("wishlist", key=wishlist_button_key):
                                print("button clicked!!!!!!!!!!!!!!")
                                # st.session_state[wishlist_button_key] = False
                                print("buttoon clicked \n\n\n\n\n")
                                wishlist_products = fetch_wishlist_from_db(userid)
                                wishlist_products["products"].append(img_url)
                                update_wishlist_to_db(wishlist_products,userid)


    update_sessions_to_db(st.session_state.chat_sessions, userid)

def logout_session():
    st.query_params.clear() 
    if not check_login_status():
        redirect_to_login()


if __name__ == "__main__":
    chatbot()
