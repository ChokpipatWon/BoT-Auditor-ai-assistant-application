import streamlit as st
import re
from embeddings import generate_embedding, openai
from neo4j_utils import query_neo4j

async def chatbot_section(llm, driver):
    # Validate the Neo4j driver before proceeding
    if not driver or not hasattr(driver, 'session'):
        st.error("Neo4j driver is not properly initialized.")
        return

    st.title("BoT Auditor Assistant AI Chatbot")
    st.subheader("Ask your legal questions or queries!")

    # Initialize chat history if not already present
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display chat history
    for role, message in st.session_state.chat_history:
        st.chat_message(role).markdown(message)

    # Handle user input
    if user_input := st.chat_input("Type your question here..."):
        st.session_state.chat_history.append(("user", user_input))
        st.chat_message("user").markdown(user_input)

        # Process user input with LLM
        if llm:
            try:
                # Step 1: Determine Query Type using LLM
                analysis_prompt = f"""
                You are an AI assistant for the Bank of Thailand's auditor. Analyze the user query:
                - If it explicitly references a specific section (e.g., "มาตรา 98"), respond with 'exact_section_query'.
                - If it is related to laws or sections (กฏหมาย, มาตรา), respond with 'law_query'.
                - If it is related to Bank of Thailand announcements (ประกาศธนาคาร, ประกาศธนาคารแห่งประเทศไทย), respond with 'announcement_query'.
                - Otherwise, respond with 'general_question'.
                User Query: "{user_input}"
                """
                query_type = llm._call(analysis_prompt).strip()

                # Handle exact section queries for multiple มาตรา
                if query_type == "exact_section_query" and "มาตรา" in user_input:
                    # Extract all section numbers using regex
                    section_numbers = re.findall(r"มาตรา\s*(\d+)", user_input)

                    if section_numbers:
                        retrieved_texts = []
                        for section_number in section_numbers:
                            cypher_query = f"""
                            MATCH (s:Section {{section: '{section_number}'}})
                            RETURN s.text AS sectionText, s.id AS sectionId
                            """
                            results = query_neo4j(driver, cypher_query, {})
                            if results:
                                retrieved_texts.append(
                                    "\n\n".join(
                                        f"Section: {r['sectionText']} (ID: {r['sectionId']})" for r in results
                                    )
                                )
                            else:
                                retrieved_texts.append(f"No exact match found for Section {section_number}.")

                        retrieved_text = "\n\n".join(retrieved_texts)
                        response_text = f"Retrieved Information for Sections:\n{retrieved_text}"
                    else:
                        response_text = "No valid sections found in your query."

                # Handle embedding-based queries (law_query and announcement_query)
                else:
                    query_embedding = await generate_embedding(user_input)
                    if query_embedding is None:
                        st.error("An error occurred during embedding generation.")
                        return

                    if query_type == "announcement_query":
                        cypher_query = """
                        WITH genai.vector.encode(
                            $userInput,
                            "OpenAI",
                            { token: $apiKey }) AS userEmbedding
                        CALL db.index.vector.queryNodes('chunk_embedding_index', 10, userEmbedding)
                        YIELD node, score
                        OPTIONAL MATCH (node)-[:NEXT]->(nextChunk:Chunk)
                        OPTIONAL MATCH (node)-[:PART_OF]->(doc:Document)
                        RETURN 
                            node.text AS chunkText, 
                            nextChunk.text AS nextChunkText, 
                            doc.name AS documentName, 
                            doc.related_sections AS documentRelatedSections, 
                            score
                        ORDER BY score DESC
                        """
                    elif query_type == "law_query":
                        cypher_query = """
                        WITH genai.vector.encode(
                            $userInput,
                            "OpenAI",
                            { token: $apiKey }) AS userEmbedding
                        CALL db.index.vector.queryNodes('section_embedding_index', 5, userEmbedding)
                        YIELD node, score
                        OPTIONAL MATCH (node)-[:UNDER]->(Law:Law)
                        RETURN 
                            node.text AS sectionText, 
                            Law.law_name AS LawName, 
                            score
                        ORDER BY score DESC
                        """
                    else:
                        general_prompt = f"""
                        You are an AI assistant for the Bank of Thailand's auditor. Respond formally and in Thai to the following query:
                        "{user_input}"
                        """
                        response_text = llm._call(general_prompt).strip()
                        st.session_state.chat_history.append(("assistant", response_text))
                        st.chat_message("assistant").markdown(response_text)
                        return

                    # Query Neo4j for embedding-based results
                    parameters = {
                        "userInput": user_input,
                        "apiKey": openai.api_key  # Fetch the API key dynamically
                    }
                    results = query_neo4j(driver, cypher_query, parameters)

                    if results:
                        with st.sidebar:
                            st.subheader("Retrieved Information")
                            if query_type == "announcement_query":
                                retrieved_texts = "\n\n".join(
                                    f"Chunk: {r['chunkText']}, Next Chunk: {r['nextChunkText']}, Document: {r['documentName']}, Sections: {r['documentRelatedSections']}"
                                    for r in results
                                )
                            elif query_type == "law_query":
                                retrieved_texts = "\n\n".join(
                                    f"Section: {r['sectionText']}, Law: {r['LawName']}, Score: {r['score']}"
                                    for r in results
                                )
                            st.text_area("Raw Retrieved Text", retrieved_texts, height=300)

                        chunk_context = "\n\n".join(
                            r.get("chunkText", r.get("sectionText", ""))
                            for r in results
                        )

                        answer_prompt = f"""
                        You are an AI assistant for the Bank of Thailand's auditor. Use the following retrieved information to answer the user's question:

                        Retrieved Information:
                        {chunk_context}

                        User's Question:
                        {user_input}

                        Provide a clear and accurate response based on the retrieved information in Thai.
                        """
                        response_text = llm._call(answer_prompt).strip()
                    else:
                        response_text = "No relevant information was found in the database."

            except Exception as e:
                response_text = f"An error occurred while processing your query: {e}"

        else:
            response_text = "The Gemini LLM is not initialized. Please provide a valid API key."

        # Add the assistant's response to the chat history
        st.session_state.chat_history.append(("assistant", response_text))
        st.chat_message("assistant").markdown(response_text)






