"""
Script to ingest a single file (PDF, DOCX, Image, etc.) into the knowledge base.
Uses the existing KnowledgeIngestionService and DocumentParserService.

Usage:
    python scripts/ingest_file.py --file "path/to/file.pdf" --org "org_id" --type "menu"
"""

import asyncio
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure app modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import setup_logging, get_logger
from app.services.knowledge_ingestion_service import get_ingestion_service

load_dotenv(override=True)
setup_logging()
logger = get_logger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Ingest a file into the knowledge base")
    parser.add_argument("--file", "-f", required=True, help="Path to the file to ingest")
    parser.add_argument("--org", "-o", required=True, help="Organization ID")
    parser.add_argument("--type", "-t", default="general", help="Source type (menu, policy, etc.)")
    parser.add_argument("--metadata", "-m", help="JSON string of additional metadata")
    
    args = parser.parse_args()
    
    file_path = Path(args.file)
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
        
    logger.info(f"Initializing ingestion for: {file_path}")
    logger.info(f"Organization: {args.org}")
    logger.info(f"Source Type: {args.type}")
    
    # Initialize service
    try:
        service = get_ingestion_service(args.org)
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        sys.exit(1)
        
    # Parse generic metadata if provided
    metadata = {}
    if args.metadata:
        import json
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON metadata provided, ignoring.")

    # Execute ingestion
    try:
        result = await service.ingest_file(
            file_path=str(file_path),
            source_type=args.type,
            metadata=metadata
        )
        
        if result.get("success"):
            logger.info("=" * 50)
            logger.info("INGESTION SUCCESSFUL")
            logger.info(f"Document ID: {result.get('document_id')}")
            logger.info(f"Chunks Created: {result.get('chunks_created')}")
            logger.info("=" * 50)
        else:
            logger.error("=" * 50)
            logger.error("INGESTION FAILED")
            logger.error(f"Error: {result.get('error')}")
            logger.error("=" * 50)
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unhandled exception during ingestion: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
