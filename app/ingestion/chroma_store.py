import chromadb


class ChromaStore:

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "university_documents",
    ):
        client = chromadb.PersistentClient(path=persist_directory)

        self.collection = client.get_or_create_collection(
            name=collection_name
        )

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        n_results: int,
    ) -> dict:
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

    def count(self) -> int:
        return self.collection.count()