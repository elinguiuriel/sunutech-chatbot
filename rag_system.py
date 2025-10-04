# rag_system.py

from pathlib import Path
from typing import List, Tuple

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.document_loaders.pdf import PyPDFDirectoryLoader

from dotenv import load_dotenv

load_dotenv()

class DirectoryRAG:
    def __init__(self, folder_path: str, k: int = 4):
        self.folder_path = Path(folder_path)
        self.k = k
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.vstore = None
        self._build_index()

    def _load_documents(self):
        if not self.folder_path.exists() or not self.folder_path.is_dir():
            raise FileNotFoundError(f"Dossier non trouvé : {self.folder_path}")

        try:
            pdf_loader = PyPDFDirectoryLoader(str(self.folder_path))
            docs_pdf = pdf_loader.load()
        except Exception as e:
            print(f"[Warning] erreur chargement PDF : {e}")
            docs_pdf = []

        try:
            txt_loader = DirectoryLoader(
                str(self.folder_path), glob="**/*.txt", loader_cls=TextLoader)
            docs_txt = txt_loader.load()
        except Exception as e:
            print(f"[Warning] erreur chargement TXT : {e}")
            docs_txt = []

        docs = docs_pdf + docs_txt
        if not docs:
            raise ValueError(f"Aucun document dans {self.folder_path}")
        return docs

    def _build_index(self):
        docs = self._load_documents()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=100)
        texts: List[str] = []
        metadatas: List[dict] = []
        for doc in docs:
            content = doc.page_content
            try:
                chunks = splitter.split_text(content)
            except Exception as e:
                print(f"[Warning] split error pour doc {doc.metadata} : {e}")
                chunks = [content]
            for chunk in chunks:
                texts.append(chunk)
                meta = dict(doc.metadata) if hasattr(doc, "metadata") else {}
                meta.setdefault("source", meta.get("source", ""))
                metadatas.append(meta)
        try:
            self.vstore = FAISS.from_texts(
                texts, self.embeddings, metadatas=metadatas)
        except Exception as e:
            raise RuntimeError(f"Erreur création index FAISS : {e}")

    def retrieve(self, query: str) -> List[Tuple[str, str]]:
        if self.vstore is None:
            raise RuntimeError("Index non initialisé.")
        try:
            docs = self.vstore.similarity_search(query, k=self.k)
        except Exception as e:
            print(f"[Warning] erreur similarity_search : {e}")
            return []
        return [(d.metadata.get("source", ""), d.page_content) for d in docs]

    def make_context(self, query: str) -> str:
        hits = self.retrieve(query)
        return "\n\n".join([f"[{src}]\n{txt}" for src, txt in hits])
