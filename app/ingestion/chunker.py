from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_id: str
    text: str
    section: str | None
    page: int


class Chunker:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_pages(
        self,
        doc_id: str,
        pages,
    ) -> list[Chunk]:

        chunks = []

        for page_data in pages:
            text = page_data.text.strip()

            if not text:
                continue

            page_chunks = self._split_text(text)

            for index, chunk_text in enumerate(page_chunks):
                chunk_id = (
                    f"{doc_id}_p{page_data.page}_c{index}"
                )

                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        text=chunk_text,
                        section=None,
                        page=page_data.page,
                    )
                )

        return chunks

    def _split_text(self, text: str) -> list[str]:
        chunks = []

        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(
                start + self.chunk_size,
                text_length,
            )

            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            start = end - self.chunk_overlap

        return chunks