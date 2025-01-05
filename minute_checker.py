import streamlit as st
from azure_utils import read_pdf
from neo4j_utils import query_neo4j
from embeddings import generate_embedding, openai

async def minute_meeting_checker_section(llm, driver):
    st.title("Minute Meeting Checker")
    st.subheader("Upload Credentials and Meeting Minutes for Analysis")

    # Input Microsoft Document Intelligence credentials
    with st.expander("Enter Microsoft Document Intelligence Credentials"):
        endpoint = st.text_input("Endpoint:", placeholder="Enter your Microsoft Document Intelligence endpoint")
        key = st.text_input("API Key:", placeholder="Enter your Microsoft Document Intelligence API key", type="password")

    if not endpoint or not key:
        st.warning("Please provide your Microsoft Document Intelligence credentials to proceed.")
        return

    # File upload for meeting minutes
    with st.expander("Upload Meeting Minutes File"):
        minutes_file = st.file_uploader(
            "Upload a minutes file (PDF, DOCX, TXT, or CSV):",
            type=["pdf", "docx", "txt", "csv"],
            key="minutes"
        )

    if not minutes_file:
        st.info("Please upload a meeting minutes file to begin analysis.")
        return

    try:
        # Step 1: Extract Text from Uploaded File
        st.subheader("Step 1: Extract Text from Uploaded File")
        minutes_content = read_pdf(minutes_file, endpoint, key)
        if minutes_content.strip():
            st.text_area("Extracted Text", value=minutes_content, height=300)
        else:
            st.error("The uploaded file does not contain readable text.")
            return

        if len(minutes_content.split()) < 10:
            st.error("The content appears too short or invalid for analysis.")
            return

        # Step 2: Analyze the Meeting Minutes
        st.subheader("Step 2: Analyze the Meeting Minutes")
        analysis_prompt = f"""
        คุณเป็นผู้ช่วย AI สำหรับสรุปรายงานการประชุมสำหรับผู้ตรวจสอบของธนาคารแห่งประเทศไทยเป็นภาษาไทย
        กรุณาจัดทำรายงานที่มีโครงสร้างชัดเจนและครบถ้วนโดยแบ่งเป็นหัวข้อหลักดังนี้:

        **วาระการประชุม:**
        - [หัวข้อย่อย]: [รายละเอียด เช่น เงื่อนไขที่กำหนด,อัตราร้อยละ, จำนวนเงิน, ระยะเวลา และกลุ่มเป้าหมายที่ชัดเจน]

        **ประเด็นสำคัญอื่นๆที่ได้มีการหารือ:**
        - [หัวข้อย่อย]: [รายละเอียด เช่น เงื่อนไขที่กำหนด,อัตราร้อยละ, จำนวนเงิน, ระยะเวลา และกลุ่มเป้าหมายที่ชัดเจน ]

        **งานที่ต้องดำเนินการและผู้รับผิดชอบ:**
        - [หัวข้อย่อย]: [รายละเอียด เช่น ขั้นตอนปฏิบัติ และชื่อบุคคล/หน่วยงานที่รับผิดชอบ]

        ข้อมูลที่ควรระบุในทุกหัวข้อ:
        1. รายละเอียดตัวเลข เช่น ร้อยละ, จำนวนเงิน, หรือข้อมูลที่เจาะจงเกี่ยวกับมาตรการ
        2. ระยะเวลา เช่น วันเริ่มต้น, วันสิ้นสุด หรือระยะเวลาการบังคับใช้
        3. กลุ่มเป้าหมายหรือเงื่อนไข เช่น ประเภทลูกค้า, ข้อจำกัด, หรือผลกระทบ
        4. ถ้ามีชื่อเต็มของตัวย่อให้เขียนแบบนี้เสมอ ชื่อเต็ม(ตัวย่อ)
        5. ถ้ามีหัวข้อแยกย่อยในหัวข้อย่อยมากกว่า1ให้ใช้เป็นข้อ 1.,2.,3. ...

        รายงานการประชุม:
        {minutes_content}
        
        ตอบในรูปแบบที่กำหนดเพื่อให้สามารถแยกและประมวลผลหัวข้อย่อยได้ง่าย โดยใช้โครงสร้าง:
        - [หัวข้อย่อย]: [รายละเอียด]
        """
        
        try:
            analysis_response = llm._call(analysis_prompt).strip()
            if not analysis_response:
                st.error("The LLM did not return any analysis. Please check the input or LLM configuration.")
                return
            st.text_area("Analyzed Content", value=analysis_response, height=300)
        except Exception as e:
            st.error(f"An error occurred during analysis: {e}")
            return

        # Step 3: Split and Process Subtopics
        st.subheader("Step 3: Split and Process Subtopics")
        sections = {"วาระการประชุม": [], "ประเด็นสำคัญอื่นๆที่ได้มีการหารือ": [], "งานที่ต้องดำเนินการและผู้รับผิดชอบ": []}

        try:
            for section in sections.keys():
                start_index = analysis_response.find(section)
                if start_index != -1:
                    next_sections = [analysis_response.find(next_section, start_index + len(section))
                                     for next_section in sections.keys() if next_section != section]
                    next_sections = [idx for idx in next_sections if idx != -1]
                    end_index = min(next_sections) if next_sections else len(analysis_response)

                    section_content = analysis_response[start_index + len(section):end_index].strip()

                    subtopics = []
                    for line in section_content.split("\n"):
                        line = line.strip()
                        if line.startswith("- "):
                            subtopic, content = line.split(":", 1) if ":" in line else (line, "")
                            subtopic = subtopic.replace("- ", "").strip()
                            subtopics.append({"subtopic": subtopic, "content": content.strip()})
                        elif subtopics and line:
                            subtopics[-1]["content"] += f" {line}"

                    sections[section] = subtopics
                else:
                    st.warning(f"Section '{section}' was not found in the analysis response.")

            # Step 4: Match Subtopics to Documents
            st.subheader("Step 4: Match Subtopics to Documents")

            # Query to retrieve document names
            document_query = """
            MATCH (d:Document)
            RETURN d.name AS documentName
            """
            document_results = query_neo4j(driver, document_query, {})

            # Normalize and trim document names
            import unicodedata
            document_names = [
                unicodedata.normalize('NFC', result['documentName'].strip())
                for result in document_results
            ]

            # Log retrieved document names for debugging###########################Log for dev
            #st.write("Retrieved Document Names:", document_names)

            # Initialize dictionary to store matched documents
            matched_documents = {}

            for section, subtopics in sections.items():
                for subtopic in subtopics:
                    subtopic_name = subtopic.get("subtopic", "Unknown Subtopic")
                    subtopic_content = subtopic.get("content", "")

                    match_prompt = f"""
                    คุณเป็นผู้ช่วย AI สำหรับตรวจสอบบันทึกการประชุม
                    หัวข้อย่อย: {subtopic_name}
                    เนื้อหา: {subtopic_content}
                    รายการชื่อเอกสารที่มีอยู่:
                    {', '.join(document_names)}

                    โปรดจับคู่หัวข้อย่อยกับชื่อเอกสารที่เหมาะสมที่สุดจากรายการด้านบนมา1เอกสาร และตอบในรูปแบบ:
                    "หัวข้อย่อย: <ชื่อหัวข้อย่อย>"
                    "เอกสารที่เกี่ยวข้อง: <ชื่อเอกสาร 1>"

                    ตัวอย่าง:
                    หัวข้อย่อย: มาตรการส่งเสริมการใช้จ่ายผ่านบัตรเครดิต
                    เอกสารที่เกี่ยวข้อง: การกำหนดหลักเกณฑ์ วิธีการ และเงื่อนไขในการประกอบธุรกิจบัตรเครดิตของธนาคารพานิชย์, การกำหนดหลักเกณฑ์ วิธีการ และเงื่อนไขในการประกอบธุรกิจบัตรเครดิตของบริษัทที่มิใช่สถาบันการเงิน
                    """
                    
                    try:
                        matched_document = llm._call(match_prompt).strip()
                    except Exception as e:
                        st.error(f"An error occurred during LLM matching: {e}")
                        matched_document = "No Match"

                    # Log the matched document for debugging###########################Log for dev
                    #st.write(f"Matched Document for '{subtopic_name}': {matched_document}")

                    matched_documents[subtopic_name] = matched_document

            # Step 5: Process Subtopics with Matched Documents
            st.subheader("Step 5: Process Subtopics with Matched Documents")
            report_data = []
            for section, subtopics in sections.items():
                if section in ["งานที่ต้องดำเนินการและผู้รับผิดชอบ", "ประเด็นสำคัญอื่นๆที่ได้มีการหารือ"]:
                    st.write(f"Skipping section: {section}")
                    continue  # Skip further processing for these sections
                with st.expander(section):
                    for subtopic in subtopics:
                        subtopic_name = subtopic.get("subtopic", "Unknown Subtopic")
                        subtopic_content = subtopic.get("content", "")
                        matched_document = matched_documents.get(subtopic_name, "No Match")
                        st.write(f"**{subtopic_name}**: {subtopic_content} \n(Matched Document: {matched_document})")

                        if subtopic_content:
                            topic_embedding = await generate_embedding(subtopic_content)
                            if isinstance(topic_embedding, str) and topic_embedding.startswith("Error"):
                                st.error(f"Error generating embedding for {subtopic_name}: {topic_embedding}")
                                continue

                            cypher_query = """
                            WITH genai.vector.encode(
                                $userInput,
                                "OpenAI",
                                { token: $apiKey }) AS userEmbedding
                            CALL db.index.vector.queryNodes('chunk_embedding_index', 10, userEmbedding)
                            YIELD node, score
                            OPTIONAL MATCH (node)-[:NEXT]->(nextChunk:Chunk)
                            OPTIONAL MATCH (previousChunk:Chunk)-[:NEXT]->(node)
                            OPTIONAL MATCH (node)-[:PART_OF]->(doc:Document)
                            WHERE trim(doc.name) = trim($matchedDocument)
                            RETURN 
                                node.text AS chunkText, 
                                nextChunk.text AS nextChunkText, 
                                previousChunk.text AS previousChunkText,
                                doc.name AS documentName, 
                                doc.related_sections AS documentRelatedSections, 
                                score
                            ORDER BY score DESC
                            """
                            parameters = {
                                "userInput": f"{subtopic_name}: {subtopic_content}",
                                "apiKey": openai.api_key,
                                "matchedDocument": matched_document.strip()
                            }
                            results = query_neo4j(driver, cypher_query, parameters)

                            comment_prompt = f"""
                            คุณเป็นผู้ช่วย AI สำหรับตรวจสอบบันทึกการประชุม
                            Subtopic: {subtopic_name}
                            Content: {subtopic_content}

                            Based on the retrieved database results:
                            {results}

                            โปรดให้ความเห็นตามแนวทางใดแนวทางหนึ่งจากต่อไปนี้:
                            1. หากไม่พบข้อขัดแย้ง ให้ระบุว่า "ไม่พบข้อขัดแย้งต่อกฎหมายและประกาศธนาคาร" และไม่ต้องให้ความเห็นเพิ่มเติม
                            2. หากข้อมูลไม่เพียงพอ ให้ระบุว่า "ข้อมูลไม่เพียงพอ" และแจ้งข้อมูลที่ควรขอเพิ่มเติมจากธนาคารเจ้าของ minute meeting และประเมินว่าข้อมูลretrieved database resultsเกี่ยวข้องกับsubtopicนี้หรือไม่
                            3. หากพบข้อขัดแย้ง ให้ระบุว่า "พบข้อขัดแย้ง" พร้อมมาตรากฎหมายที่เกี่ยวข้องและชื่อประกาศที่เกี่ยวข้อง ถ้ามีบางส่วนของหัวข้อย่อยที่มีข้อมูลไม่เพียงพอให้เขียนกำกับที่ส่วนนั้นว่าข้อมูลไม่เพียงพอ และแจ้งข้อมูลที่ควรขอเพิ่มเติมจากธนาคารเจ้าของ minute meeting
                            4. ข้อมูลจาก Retrieved database results ไม่เกี่ยวข้องกับ หัวข้อย่อย
                            """
                            llm_comment = llm._call(comment_prompt).strip()

                            report_data.append((subtopic_name, subtopic_content, results, matched_document, llm_comment))
        
        except Exception as e:
            st.error(f"An error occurred while splitting and processing subtopics: {e}")
            return

        # Step 6: Generate Compliance Report
        st.subheader("Step 6: Generate Compliance Report")
        try:
            # Initialize reports
            violations_report = "### Violations Report\n"
            retrieved_report = "### Retrieved Database Results\n"

            for subtopic_name, subtopic_content, results, matched_document, llm_comment in report_data:
                violations_report += f"\n#### {subtopic_name}\n"
                violations_report += f"Matched Document: {matched_document}\n"
                violations_report += f"Comment: {llm_comment}\n"

                if results:
                    retrieved_report += f"####**Subtopic**: {subtopic_name}\n"
                    retrieved_report += f"  **Content**: {subtopic_content}\n"
                    retrieved_report += f"  **Matched Document**: {matched_document}\n"
                    for result in results:
                        retrieved_report += f"  - **Chunk**: {result['chunkText']}\n"
                        retrieved_report += f"    **Document**: {result['documentName']}\n"
                        retrieved_report += f"    **Related Sections**: {result['documentRelatedSections']}\n"
                        retrieved_report += f"    **Score**: {result['score']}\n"

            # Display the violations reports directly in the app
            st.markdown(violations_report, unsafe_allow_html=True)
            
            # Display the retrieved results in a text box
            st.text_area("Retrieved Results", value=retrieved_report, height=300)
            

        except Exception as e:
            st.error(f"An error occurred while generating the compliance report: {e}")


    except Exception as e:
        st.error(f"An error occurred during processing: {e}")
