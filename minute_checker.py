import streamlit as st
from azure_utils import read_pdf
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

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