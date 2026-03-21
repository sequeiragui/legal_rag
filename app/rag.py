import os
import chromadb
import anthropic
from pypdf import PdfReader
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
chroma_client = chromadb.Client()
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() for page in reader.pages)

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def index_document(pdf_path: str, collection_name: str = "documents") -> int:
    collection = chroma_client.get_or_create_collection(collection_name)
    text = extract_text_from_pdf(pdf_path)
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        embedding = embedding_model.encode(chunk).tolist()
        collection.add(
            documents=[chunk],
            embeddings=[embedding],
            ids=[f"{os.path.basename(pdf_path)}_chunk_{i}"]
        )
    return len(chunks)

def delete_document(filename: str, collection_name: str = "documents"):
    collection = chroma_client.get_or_create_collection(collection_name)
    all_ids = collection.get()["ids"]
    matching = [id for id in all_ids if id.startswith(filename + "_chunk_")]
    if matching:
        collection.delete(ids=matching)

def query_rag(question: str, collection_name: str = "documents") -> str:
    collection = chroma_client.get_collection(collection_name)
    question_embedding = embedding_model.encode(question).tolist()
    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=3
    )
    context = "\n\n".join(results["documents"][0])
    answer = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system="You are a helpful assistant. Answer the question using only the context provided. If the answer isn't in the context, say so.",
        messages=[{
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}"
        }]
    )
    return answer.content[0].text