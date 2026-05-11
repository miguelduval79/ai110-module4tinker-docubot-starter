"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index
- Retrieving relevant snippets
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini
"""

import os
import glob
import string


class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        self.documents = self.load_documents()
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")

        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()

                filename = os.path.basename(path)
                docs.append((filename, text))

        return docs

    # -----------------------------------------------------------
    # Text Cleaning Helper
    # -----------------------------------------------------------

    def tokenize(self, text):
        """
        Convert text into lowercase words with punctuation removed.
        """
        text = text.lower()

        for mark in string.punctuation:
            text = text.replace(mark, " ")

        stop_words = {
            "what", "where", "which", "how", "do", "does", "is", "are",
            "the", "a", "an", "to", "of", "in", "on", "for", "and",
            "or", "this", "that", "with", "from"
        }

        words = text.split()

        return [
            word
            for word in words
            if word not in stop_words
        ]

    def split_into_snippets(self, text):
        """
        Split a document into smaller paragraph-sized snippets.
        """
        raw_sections = text.split("\n\n")
        snippets = []

        for section in raw_sections:
            cleaned = section.strip()

            if cleaned:
                snippets.append(cleaned)

        return snippets

    # -----------------------------------------------------------
    # Index Construction
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        Build a tiny inverted index mapping words to document filenames.
        """
        index = {}

        for filename, text in documents:
            words = self.tokenize(text)

            for word in words:
                if word not in index:
                    index[word] = set()

                index[word].add(filename)

        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        Return a relevance score based on matching query words.
        """
        query_words = self.tokenize(query)
        document_words = self.tokenize(text)

        score = 0

        for word in query_words:
            score += document_words.count(word)

        return score

    def retrieve(self, query, top_k=3):
        """
        Return the top_k most relevant snippets for a query.
        """
        scored_results = []

        for filename, text in self.documents:
            snippets = self.split_into_snippets(text)

            for snippet in snippets:
                score = self.score_document(query, snippet)

                if score > 0:
                    scored_results.append((score, filename, snippet))

        scored_results.sort(reverse=True, key=lambda item: item[0])

        if not scored_results:
            return []

        best_score = scored_results[0][0]

        # Guardrail: refuse weak matches
        if best_score < 3:
            return []

        results = []

        for score, filename, snippet in scored_results[:top_k]:
            results.append((filename, snippet))

        return results

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Return raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []

        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Use retrieval to select snippets, then ask the LLM to answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        """
        return "\n\n".join(text for _, text in self.documents)