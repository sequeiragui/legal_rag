import os
import shutil
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from app.rag import index_document, query_rag, delete_document
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_portfolio():
    return FileResponse("static/index.html")

@app.get("/folio")
async def serve_folio():
    return FileResponse("static/folio.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    num_chunks = index_document(file_path)
    return {"message": f"Indexed {file.filename}", "chunks": num_chunks}

@app.get("/documents")
async def list_documents():
    files = []
    for name in os.listdir(UPLOAD_DIR):
        if name.lower().endswith(".pdf"):
            path = os.path.join(UPLOAD_DIR, name)
            files.append({"name": name, "size": os.path.getsize(path)})
    return {"documents": files}

@app.delete("/documents/{filename}")
async def remove_document(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return {"error": "File not found"}, 404
    os.remove(file_path)
    delete_document(filename)
    return {"message": f"Deleted {filename}"}

@app.post("/query")
async def query(question: str):
    answer = query_rag(question)
    return {"answer": answer}

@app.get("/health")
async def health():
    return {"status": "ok"}