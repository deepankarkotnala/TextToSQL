import streamlit as st
import os
import mysql.connector
from mysql.connector import Error
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
import time

# Set the environment variable for the Ollama host
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"

# Function to connect to the MySQL database
def connect_to_mysql():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="tomatogoat398",
            database="user_orders_db"
        )
        if connection.is_connected():
            return connection, None
    except Error as e:
        return None, f"Error connecting to MySQL database: {e}"
    return None, "Unknown connection error"

# Function to execute SQL and return results
def execute_sql(connection, query):
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        return cursor.fetchall(), None
    except Exception as e:
        return None, f"Error executing SQL query: {e}"

# Function to create a text-to-SQL generator chain
def create_text_to_sql_chain():
    template = """
    You are an expert SQL generator.
    Given a natural language query, translate it into a syntactically correct SQL query. 
    The query should be optimized to run in less time. 

    Database Schema: {schema}
    Natural Language Query: {query}

    Important: Do not provide any explanation. ONLY return a ready-to-execute SQL statement.

    SQL Query:
    """
    prompt = ChatPromptTemplate.from_template(template)
    model = ChatOllama(model="llama3.2:3b", base_url=os.environ["OLLAMA_HOST"])
    return prompt | model

# Function to generate a natural language response
def generate_natural_language_response(llm, sql_result, query):
    template = """
    Given the SQL query result: {sql_result} and the original user query: {query}, 
    provide a concise and natural language response that DIRECTLY answers the user's query by describing the returned data. 
    The SQL query has been designed to return only the data that fully satisfies ALL the conditions specified in the query.

    If the SQL result is empty, respond that there is no data. 
    Otherwise, describe the data returned by the query, ensuring that you indicate that those entries all satisfy the conditions of the query.
    """
    prompt = ChatPromptTemplate.from_template(template)
    input_data = {"sql_result": sql_result, "query": query}
    result = prompt | llm
    return result.invoke(input_data).content

# Utility functions to clean responses
def remove_code_blocks(text):
    if "```" in text:
        parts = text.split("```")
        if len(parts) % 2 == 1:
            text = "".join(parts[::2])
    return text.strip()

def remove_think_tags(text):
    if "<think>" in text:
        text = text.split("</think>")[-1].strip()
    return text

# Streamlit app
def main():
    st.set_page_config(page_title="Text-to-SQL Query Generator", page_icon="🗄️", layout="wide")
    st.title("Text-to-SQL Query Generator")
    st.write("Generate SQL queries from natural language queries and get responses based on your database.")

    # Database schema and sample query
    schema = """
    Tables:
    - users : id (integer), name (string), age (integer), email (string)
    - orders: id (integer), user_id (integer), amount (float), date (date)
    """
    st.sidebar.subheader("Database Schema")
    st.sidebar.text(schema)

    sample_query = "Users older than 30 years having overall order value greater than $100"
    query = st.text_area("Enter your natural language query:", value=sample_query, height=100)

    if st.button("Generate SQL and Fetch Results"):
        if not query.strip():
            st.warning("Please enter a query.")
            return

        with st.spinner("Generating SQL query..."):
            log_messages = []
            s1 = time.time()
            text_to_sql_chain = create_text_to_sql_chain()
            input_data = {"schema": schema, "query": query}

            try:
                generated_sql = text_to_sql_chain.invoke(input_data).content.strip()
                generated_sql = remove_code_blocks(generated_sql)
                log_messages.append(f"Generated SQL: {generated_sql}")
                st.code(generated_sql, language="sql")
            except Exception as e:
                st.error(f"Error generating SQL query: {e}")
                return
                
            max_retries = 3
            attempt = 0
            sql_result = None

            while attempt < max_retries:
                attempt += 1
                log_messages.append(f"Attempt {attempt}: Executing SQL query...")
                with st.spinner(f"Attempt {attempt}: Executing SQL query..."):
                  connection, conn_error = connect_to_mysql()
                
                  if conn_error:
                    log_messages.append(conn_error)
                    st.error("Database connection failed. Retrying...")
                    time.sleep(1)
                    continue
                  
                  sql_result, exec_error = execute_sql(connection, generated_sql)
                  connection.close()

                  if exec_error:
                     log_messages.append(exec_error)
                     st.error("SQL execution failed. Retrying...")
                     time.sleep(1)
                  else:
                    break

            if sql_result:
                st.success("SQL query executed successfully.")
                st.write("Query Results:")
                st.table(sql_result)

                # Generate natural language response
                with st.spinner("Generating natural language response..."):
                  llm = ChatOllama(model="deepseek-r1:1.5b", base_url=os.environ["OLLAMA_HOST"])
                  natural_language_response = generate_natural_language_response(llm, str(sql_result), query)
                  natural_language_response = remove_code_blocks(natural_language_response)
                  natural_language_response = remove_think_tags(natural_language_response)
                  st.subheader("Natural Language Response")
                  st.write(natural_language_response)
            else:
                st.warning("No results returned by the SQL query after multiple attempts.")

            e1 = time.time()
            log_messages.append(f"Total time taken: {e1 - s1:.2f} seconds")
            st.write(f"Total time taken: {e1 - s1:.2f} seconds")
            
            with st.expander("View Execution Log"):
                for message in log_messages:
                    st.write(message)

if __name__ == "__main__":
    main()