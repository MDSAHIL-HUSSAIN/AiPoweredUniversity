from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def embed_query(self, query: str) -> list[float]:
        vector = self.model.encode(
            query,
            normalize_embeddings=True,
        )
        return vector.tolist()

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
        )

        return vectors.tolist()