from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from services.embedding_service import EmbeddingService


class VectorStoreService:
    def __init__(self) -> None:
        self.persist_directory = Path(__file__).resolve().parents[1] / "data" / "chroma_db"
        self.collection_name = "apple_policies"
        self.embedding_service = EmbeddingService()
        self._vector_store: Chroma | None = None

    def _open_vector_store(self, create_if_missing: bool = False) -> Chroma:
        return Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedding_service.embedding_model,
            persist_directory=str(self.persist_directory),
            create_collection_if_not_exists=create_if_missing,
        )

    def search(self, query: str, k: int = 3) -> list[Document]:
        """Retrieve matching chunks from the existing index without rebuilding it."""
        if not query.strip():
            raise ValueError("The search query must not be empty.")
        if k < 1:
            raise ValueError("k must be at least 1.")

        if self._vector_store is None:
            if not self.persist_directory.is_dir():
                raise FileNotFoundError(
                    f"No persisted vector database found at {self.persist_directory}."
                )
            self._vector_store = self._open_vector_store()
        return self._vector_store.similarity_search(query, k=k)

    def create_vector_store(self, documents: list[Document]) -> Chroma:
        """Rebuild the policy collection from chunks, preserving their metadata."""
        if not documents:
            raise ValueError("No documents to index; the existing collection was left intact.")

        vector_store = self._open_vector_store(create_if_missing=True)
        # This explicit build replaces only this collection to avoid duplicate chunks.
        vector_store.reset_collection()
        vector_store.add_documents(documents)
        self._vector_store = vector_store
        # Chroma writes automatically when a persist_directory is configured.
        return vector_store


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    vector_store_service = VectorStoreService()
    queries = [
        "What is Apple's return policy?",
        "What accommodations does Apple provide to customers with disabilities?",
        "What does Apple say about human rights?",
    ]
    for query in queries:
        print(f"\n{'=' * 50}\nQUERY: {query}\n{'=' * 50}")
        for rank, document in enumerate(vector_store_service.search(query, k=3), start=1):
            page = document.metadata.get("page")
            display_page = page + 1 if isinstance(page, int) else page
            print(f"\nRESULT {rank}")
            print(f"Source: {document.metadata.get('source_file')}")
            print(f"Page: {display_page}")
            print(f"\nText:\n{document.page_content}")
            print(f"\n{'-' * 50}")
