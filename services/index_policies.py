"""Build local policy persistence: python -m services.index_policies."""

import argparse
import logging

from services.document_service import DocumentService
from services.vector_store_service import VectorStoreService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild", action="store_true",
        help="Replace the apple_policies collection in an existing persistence directory.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    service = VectorStoreService()
    if service.persist_directory.exists() and not args.rebuild:
        parser.error("Persistence already exists; use --rebuild only to explicitly replace the policy collection.")
    documents = DocumentService()
    pages = documents.load_documents()
    chunks = documents.split_documents(pages)
    if not chunks:
        parser.error("No policy chunks found; check data/policies/*.pdf. Nothing was indexed.")
    service.create_vector_store(chunks)
    print(f"Indexed {len(chunks)} policy chunks from {len(pages)} pages.")
    print(f"Collection: {service.collection_name}")
    print(f"Persistence: {service.persist_directory}")


if __name__ == "__main__":
    main()
