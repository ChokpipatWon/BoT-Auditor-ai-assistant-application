import streamlit as st
from streamlit_option_menu import option_menu
from gemini_llm import GeminiLLM
from chatbot_section import chatbot_section
from minute_checker import minute_meeting_checker_section
from neo4j import GraphDatabase
from config import Config  # Import centralized configuration
import asyncio

# Neo4j connection details :streamlit run streamlit_app.py
NEO4J_URI = "neo4j+s://2696b0c1.databases.neo4j.io:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "USZbhA5ZkAjkNMtE-DfGkuSuvDn8beXUdt6kK7_8-kk"

# Global variable to manage Neo4j driver
driver = None


def get_neo4j_driver():
    """Initialize and return the Neo4j driver if not already initialized."""
    global driver
    if driver is None:
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            st.sidebar.success("Connected to Neo4j.")
        except Exception as e:
            st.sidebar.error(f"Failed to connect to Neo4j: {e}")
            driver = None
    return driver


def close_neo4j_driver():
    """Close the Neo4j driver if it has been initialized."""
    global driver
    if driver:
        try:
            driver.close()
            st.sidebar.info("Neo4j connection closed.")
        except Exception as e:
            st.sidebar.error(f"Error closing Neo4j connection: {e}")
        driver = None
    else:
        st.sidebar.info("No active Neo4j connection to close.")


def main():
    st.set_page_config(page_title="BoT Auditor Assistant", page_icon="🏦")

    # Sidebar menu
    with st.sidebar:
        selected = option_menu("Main Menu", ["Chatbot", "Minute Meeting Checker"], icons=["chat", "file-text"])

        # Input Gemini API Key
        gemini_api_key = st.text_input("Gemini API Key:", placeholder="Enter your Gemini API Key", type="password")
        if gemini_api_key:
            Config.set_gemini_key(gemini_api_key)
            st.success("Gemini API Key set successfully.")

        # Input OpenAI API Key
        openai_api_key = st.text_input("OpenAI API Key:", placeholder="Enter your OpenAI API Key", type="password")
        if openai_api_key:
            Config.set_openai_key(openai_api_key)
            st.success("OpenAI API Key set successfully.")

    # Initialize LLM if the Gemini API key is set
    llm = None
    if Config.gemini_api_key:
        try:
            llm = GeminiLLM()  # Automatically uses the key from Config
            st.success("Gemini model initialized successfully.")
        except Exception as e:
            st.error(f"Error initializing Gemini model: {e}")
    else:
        st.warning("Please provide a Gemini API Key to use the Chatbot.")

    # Initialize the Neo4j driver
    driver = get_neo4j_driver()

    # Debug: Display selected menu
    st.write(f"Selected menu: {selected}")

    # Main menu logic
    try:
        if selected == "Chatbot":
            st.header("Chatbot Section")
            if driver and llm:
                asyncio.run(chatbot_section(llm, driver))  # Pass Neo4j driver and LLM
            else:
                st.error("Both Neo4j and Gemini must be initialized to use the chatbot.")
        elif selected == "Minute Meeting Checker":
            st.header("Minute Meeting Checker Section")
            if llm and driver:
                asyncio.run(minute_meeting_checker_section(llm, driver))  # Pass Neo4j driver and LLM
            else:
                st.error("Both Gemini model and Neo4j driver must be initialized to use the Minute Meeting Checker.")
    except Exception as e:
        st.error(f"Error in {selected}: {e}")

    # Close Neo4j connection when done
    close_neo4j_driver()


if __name__ == "__main__":
    main()

