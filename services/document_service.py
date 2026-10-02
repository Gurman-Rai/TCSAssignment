import logging
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocumentService:
    def __init__(self) -> None:
        self.policies_dir = Path(__file__).resolve().parents[1] / "data" / "policies"

    def load_documents(self) -> list[Document]:
        documents: list[Document] = []

        for pdf_path in sorted(self.policies_dir.glob("*.pdf")):
            if not pdf_path.is_file():
                continue

            logging.getLogger(__name__).info("Loading %s", pdf_path.name)
            pages = PyPDFLoader(str(pdf_path)).load()
            for page in pages:
                page.metadata["source_file"] = pdf_path.name
            documents.extend(pages)

        return documents

    def split_documents(self, documents: list[Document]) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        return splitter.split_documents(documents)


if __name__ == "__main__":
    document_service = DocumentService()
    loaded_documents = document_service.load_documents()
    print(f"Total pages loaded: {len(loaded_documents)}")

    chunks = document_service.split_documents(loaded_documents)
    print(f"Total chunks created: {len(chunks)}")

    if chunks:
        first_chunk = chunks[0]
        print("First chunk metadata:")
        print(first_chunk.metadata)
        print("First chunk text:")
        print(first_chunk.page_content)
        print(f"First chunk character length: {len(first_chunk.page_content)}")
    else:
        print("No chunks created.")
