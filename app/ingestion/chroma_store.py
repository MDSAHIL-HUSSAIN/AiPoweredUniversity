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
        count = self.count()
        if count == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, count),
        )

    def count(self) -> int:
        return self.collection.count()


class InMemoryChromaStore:
    """Contract-compatible store that does not require a model download."""

    def __init__(self):
        self._items: dict[str, dict] = {}

    def upsert(self, ids, documents, embeddings, metadatas) -> None:
        for chunk_id, text, vector, metadata in zip(
            ids, documents, embeddings, metadatas
        ):
            self._items[chunk_id] = {
                "document": text,
                "embedding": vector,
                "metadata": metadata,
            }

    def search(self, query_embedding: list[float], n_results: int) -> dict:
        ranked = []
        for chunk_id, item in self._items.items():
            similarity = sum(
                left * right
                for left, right in zip(query_embedding, item["embedding"])
            )
            ranked.append((max(0.0, 1.0 - similarity), chunk_id, item))
        ranked.sort(key=lambda value: value[0])
        selected = ranked[:n_results]
        return {
            "ids": [[value[1] for value in selected]],
            "documents": [[value[2]["document"] for value in selected]],
            "metadatas": [[value[2]["metadata"] for value in selected]],
            "distances": [[value[0] for value in selected]],
        }

    def count(self) -> int:
        return len(self._items)
