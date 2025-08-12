import os, glob
from ..config import settings
import chromadb

def get_chroma():
    os.makedirs(settings.chroma_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=settings.chroma_dir)
    return client

def ensure_collection():
    client = get_chroma()
    coll = client.get_or_create_collection("knowledge_base")
    return coll

def ingest_directory(dirpath: str | None = None):
    dirpath = dirpath or settings.kb_dir
    coll = ensure_collection()
    # Simple ingest: each file becomes a doc; you can split further if needed
    for fp in glob.glob(os.path.join(dirpath, "*.md")):
        with open(fp, "r") as f:
            text = f.read()
        doc_id = os.path.basename(fp)
        # upsert replaces if existing
        coll.upsert(documents=[text], ids=[doc_id], metadatas=[{"source": doc_id}])

def search(query: str, n: int = 4):
    coll = ensure_collection()
    res = coll.query(query_texts=[query], n_results=n)
    docs = []
    for doc, meta in zip(res.get("documents", [[]])[0], res.get("metadatas", [[]])[0]):
        docs.append({"text": doc, "meta": meta})
    return docs
