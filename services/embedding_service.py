from langchain_ollama import OllamaEmbeddings


class EmbeddingService:
    def __init__(self) -> None:
        self.embedding_model = OllamaEmbeddings(model="nomic-embed-text")

    def embed_query(self, text: str) -> list[float]:
        return self.embedding_model.embed_query(text)


if __name__ == "__main__":
    embedding_service = EmbeddingService()
    embedding = embedding_service.embed_query(
        "Apple customers may return eligible products according to the company's return policy."
    )

    print("Embedding generated successfully.")
    print(f"Embedding dimensions: {len(embedding)}")
    print(f"First 10 numbers: {embedding[:10]}")