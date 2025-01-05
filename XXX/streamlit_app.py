import streamlit as st
import google.generativeai as genai
from streamlit_option_menu import option_menu
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from neo4j import GraphDatabase
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.llms.base import LLM
from typing import Optional, List
import asyncio

# Neo4j connection details
NEO4J_URI = "neo4j+s://2696b0c1.databases.neo4j.io:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "USZbhA5ZkAjkNMtE-DfGkuSuvDn8beXUdt6kK7_8-kk"

# Define a custom Gemini wrapper for LangChain
class GeminiLLM(LLM):
    model_name: str = "gemini-1.5-pro-latest"
    model: any = None

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro-latest"):
        super().__init__()
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        try:
            if not self.model:
                raise ValueError("Model not initialized")
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            st.error(f"Error generating text with Gemini: {e}")
            return f"An error occurred: {e}"

    @property
    def _llm_type(self) -> str:
        return "gemini"

# Function to query Neo4j
def query_neo4j(query, parameters=None):
    with neo4j_driver.session() as session:
        result = session.run(query, parameters)
        return [record.data() for record in result]

# Updated read_pdf function to use Microsoft Document Intelligence API
def read_pdf(file, endpoint, key):
    try:
        document_analysis_client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        file_content = file.read()
        poller = document_analysis_client.begin_analyze_document("prebuilt-document", document=file_content)
        result = poller.result()

        text = "\n".join([
            "".join([line.content for line in page.lines])
            for page in result.pages
        ])

        if not text.strip():
            return "No readable text found in the document."
        return text
    except Exception as e:
        return f"Error processing the document with Microsoft Document Intelligence API: {e}"

# OpenAI Embedding
import openai

# Set your OpenAI API key
openai.api_key = "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"

async def generate_embedding(text: str):
    try:
        response = await openai.Embedding.acreate(
            model="text-embedding-ada-002",
            input=text
        )
        return response["data"][0]["embedding"]
    except Exception as e:
        st.error(f"Error generating embeddings: {e}")
        return None

def find_similar_chunks(embedding, top_n=3):
    query = """
    MATCH (c:Chunk)
    WHERE vector_distance(c.embedding, $embedding) < 0.8
    RETURN c.text AS text, vector_distance(c.embedding, $embedding) AS score
    ORDER BY score ASC
    LIMIT $top_n
    """
    parameters = {"embedding": embedding, "top_n": top_n}
    return query_neo4j(query, parameters)

# Chatbot Section
async def chatbot_section(llm):
    st.title("BoT Auditor Assistant AI Chatbot")
    st.subheader("Ask your legal questions or queries!")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for role, message in st.session_state.chat_history:
        st.chat_message(role).markdown(message)

    if user_input := st.chat_input("Type your question here..."):
        st.session_state.chat_history.append(("user", user_input))
        st.chat_message("user").markdown(user_input)

        if llm:
            try:
                # Step 1: Determine Query Type
                analysis_prompt = f"""
                You are an AI assistant for the Bank of Thailand's auditor. Analyze the user query:
                - If it is related to laws or Bank of Thailand announcements(ประกาศธนาคาร,ประกาศธนาคารแห่งประเทศไทย), respond with 'database_query'.
                - Otherwise, respond with 'general_question'.
                User Query: "{user_input}"
                """
                query_type = llm._call(analysis_prompt).strip()

                if query_type == "database_query":
                    try:
                        # Step 2: Generate embedding for the user query
                        query_embedding = await generate_embedding(user_input)
                        # Check if embedding generation was successful
                        if query_embedding is None:
                            response_text = "An error occurred during embedding generation."
                        # Step 3: Retrieve relevant chunks from the database
                        cypher_query = """
                        MATCH (c:Chunk)
                        WHERE c.embedding IS NOT NULL
                        RETURN c.id, c.text
                        ORDER BY vector_distance(c.embedding, $query_embedding) ASC
                        LIMIT 3
                        """
                        parameters = {"query_embedding": query_embedding}
                        similar_chunks = query_neo4j(cypher_query, parameters)

                        # Display the retrieved raw text and Cypher query in a sidebar
                        with st.sidebar:
                            st.subheader("Retrieved Information")
                            if similar_chunks:
                                raw_texts = "\n\n".join(chunk["c.text"] for chunk in similar_chunks)
                                st.text_area("Raw Retrieved Text", raw_texts, height=300)
                                st.code(cypher_query, language="cypher")

                        # Combine retrieved chunks for context
                        chunk_context = "\n\n".join(chunk["c.text"] for chunk in similar_chunks)

                        # Step 4: Generate response using retrieved chunks
                        answer_prompt = f"""
                        You are an AI assistant for the Bank of Thailand's auditor. Use the following retrieved information to answer the user's question:

                        Retrieved Information:
                        {chunk_context}

                        User's Question:
                        {user_input}

                        Provide a clear and accurate response based on the retrieved information.
                        """
                        response_text = llm._call(answer_prompt).strip()
                    except Exception as e:
                        response_text = f"An error occurred during vector search or response generation: {e}"
                else:
                    # Handle general questions
                    general_prompt = f"""
                    You are an AI assistant for the Bank of Thailand's auditor. Respond formally and in Thai to the following query:
                    "{user_input}"
                    """
                    response_text = llm._call(general_prompt).strip()
            except Exception as e:
                response_text = f"An error occurred while processing your query: {e}"

        st.session_state.chat_history.append(("assistant", response_text))
        st.chat_message("assistant").markdown(response_text)

# Minute Meeting Checker Section
def minute_meeting_checker_section(llm):
    st.title("Minute Meeting Checker")
    st.subheader("Upload Credentials and Minute Meetings for Analysis")

    endpoint = st.text_input("Microsoft Document Intelligence Endpoint:", placeholder="Enter your endpoint")
    key = st.text_input("Microsoft Document Intelligence Key:", placeholder="Enter your API key", type="password")

    if not endpoint or not key:
        st.warning("Please provide your Microsoft Document Intelligence credentials to proceed.")
        return

    minutes_file = st.file_uploader("Upload a minutes file", type=["txt", "pdf", "docx", "csv"], key="minutes")

    if minutes_file and llm:
        try:
            minutes_content = read_pdf(minutes_file, endpoint, key)
            st.subheader("Extracted Text")
            if minutes_content.strip():
                st.text_area("Raw Extracted Text", value=minutes_content, height=300)
            else:
                st.error("The uploaded file does not contain readable text.")
                return

            if len(minutes_content.split()) < 10:
                st.error("The content appears too short or invalid for analysis.")
                return

            summarization_prompt = PromptTemplate(
                input_variables=["minutes_content"],
                template="""
                You are an AI assistant specializing in summarizing meeting minutes for auditors at the Bank of Thailand in Thai.

                Analyze the following meeting minutes and provide:
                1. Key Decisions Made
                2. Critical Topics Discussed
                3. Action Items and Responsibilities
                4. Potential Compliance or Regulatory Implications

                Meeting Minutes:
                {minutes_content}

                Provide a structured and detailed summary.
                """
            )

            summarization_chain = LLMChain(llm=llm, prompt=summarization_prompt)
            summary = summarization_chain.run({"minutes_content": minutes_content})

            st.subheader("Meeting Minutes Analysis")
            st.markdown(summary)

        except Exception as e:
            st.error(f"An error occurred during minutes processing: {e}")

# Main App
async def main():
    st.set_page_config(page_title="BoT Auditor Assistant", page_icon="🏦")

    with st.sidebar:
        selected = option_menu(
            menu_title="Main Menu",
            options=["Chatbot", "Minute Meeting Checker"],
            icons=["chat", "file-text"],
            menu_icon="cast",
            default_index=0
        )

    gemini_api_key = st.text_input("Gemini API Key:", 
                                   placeholder="Enter your Gemini API Key", 
                                   type="password")

    llm = None
    if gemini_api_key:
        try:
            llm = GeminiLLM(api_key=gemini_api_key)
            st.success("Gemini model successfully initialized.")
        except Exception as e:
            st.error(f"Error initializing Gemini model: {e}")

    global neo4j_driver
    neo4j_driver = None
    try:
        neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        st.sidebar.success("Neo4j Connection Established")
    except Exception as e:
        st.sidebar.error(f"Neo4j Connection Error: {e}")

    if selected == "Chatbot":
        await chatbot_section(llm)
    elif selected == "Minute Meeting Checker":
        minute_meeting_checker_section(llm)

    if neo4j_driver:
        neo4j_driver.close()

if __name__ == "__main__":
    asyncio.run(main())