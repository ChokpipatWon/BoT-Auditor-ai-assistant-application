from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

def read_pdf(file, endpoint, key):
    try:
        client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        file_content = file.read()
        poller = client.begin_analyze_document("prebuilt-document", document=file_content)
        result = poller.result()

        return "\n".join([
            "".join([line.content for line in page.lines])
            for page in result.pages
        ]).strip() or "No readable text found."
    except Exception as e:
        return f"Error: {e}"
