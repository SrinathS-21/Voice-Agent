"""
Knowledge Ingestion Service - Simplified
Uses paragraph chunking + semantic search. No LLM extraction, no filters.

Pipeline:
1. Parse document (LlamaParse) → Extract text
2. Chunk content → Paragraph-based splitting
3. Store in RAG → OpenAI embeddings + Convex vector DB
4. Semantic search handles retrieval
"""

import os
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from app.core.logging import get_logger
from app.core.convex_client import get_convex_client
from app.services.document_parser_service import get_document_parser
from app.services.chunking_service import get_chunking_service, ChunkingStrategy

logger = get_logger(__name__)


class KnowledgeIngestionService:
    """
    Simplified ingestion service for any document type.
    
    Uses pure semantic search - no filters, no LLM extraction.
    Categories and metadata embedded in text help semantic matching.
    """
    
    def __init__(self, organization_id: str):
        """
        Initialize ingestion service for an organization
        
        Args:
            organization_id: The organization identifier (namespace for RAG)
        """
        self.organization_id = organization_id
        self.convex_client = get_convex_client()
        self.document_parser = get_document_parser()
        self.chunking_service = get_chunking_service()
        
        logger.info(f"KnowledgeIngestionService initialized for org: {organization_id}")
    
    async def ingest_file(
        self,
        file_path: str,
        source_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a file into the knowledge base using simple paragraph chunking.
        
        Args:
            file_path: Path to the file
            source_type: Type label (for tracking only, not filtering)
            metadata: Optional custom metadata
            
        Returns:
            Ingestion result with document_id and chunk count
        """
        document_id = str(uuid.uuid4())
        filename = os.path.basename(file_path)
        
        logger.info(f"Starting ingestion: {filename} (doc_id: {document_id})")
        
        try:
            # Step 1: Create document record for tracking
            await self._create_document_record(
                document_id=document_id,
                filename=filename,
                file_path=file_path,
                source_type=source_type,
                status="processing"
            )
            
            # Step 2: Parse document (LlamaParse extracts text from PDFs, etc.)
            logger.info(f"Parsing document: {filename}")
            parsed = await self.document_parser.parse_file(file_path)
            
            if not parsed.get("content"):
                raise ValueError("Document parsing returned empty content")
            
            # Step 3: Simple paragraph chunking (works for any content type)
            logger.info("Chunking content with paragraph strategy...")
            content_text = parsed["content"]
            cleaned_text = self.chunking_service.clean_text(content_text)
            
            chunk_metadata = {
                "filename": filename,
                "source_type": source_type,
                "file_type": parsed.get("file_type", ""),
                **(metadata or {})
            }
            
            chunks = self.chunking_service.chunk_text(
                cleaned_text,
                metadata=chunk_metadata,
                strategy=ChunkingStrategy.PARAGRAPH
            )
            
            if not chunks:
                raise ValueError("Chunking returned no chunks")

            # Step 4: Ingest into RAG with batching for rate limits
            logger.info(f"Ingesting {len(chunks)} chunks into RAG...")
            
            rag_ids = []
            batch_size = 10
            delay_between_batches = 1.5  # seconds
            
            for i, chunk in enumerate(chunks):
                chunk_key = f"{document_id}_chunk_{i}"
                
                try:
                    chunk_text = chunk.get("chunkText") or chunk.get("text", "")
                    
                    # Simple RAG args - no filters, just text + namespace
                    rag_args = {
                        "namespace": self.organization_id,
                        "key": chunk_key,
                        "text": chunk_text,
                        "title": f"{filename} (part {i+1})",
                    }
                        
                    result = await self.convex_client.action("rag:ingest", rag_args)
                    rag_ids.append(result.get("entryId"))
                    
                    # Rate limit protection
                    if (i + 1) % batch_size == 0 and i < len(chunks) - 1:
                        logger.info(f"  Ingested {i + 1}/{len(chunks)} chunks, pausing...")
                        await asyncio.sleep(delay_between_batches)
                        
                except Exception as e:
                    logger.warning(f"Failed to ingest chunk {i}: {e}")

            # Step 5: Update document record
            await self._update_document_status(
                document_id=document_id,
                status="completed",
                chunk_count=len(rag_ids),
                rag_entry_ids=rag_ids
            )
            
            result_data = {
                "success": True,
                "document_id": document_id,
                "rag_entry_ids": rag_ids,
                "chunks_created": len(rag_ids),
                "filename": filename,
                "source_type": source_type
            }
            
            logger.info(f"Ingestion complete: {document_id} ({len(rag_ids)} chunks)")
            return result_data
            
        except Exception as e:
            logger.error(f"Ingestion failed for {filename}: {e}")
            
            await self._update_document_status(
                document_id=document_id,
                status="failed",
                error_message=str(e)
            )
            
            return {
                "success": False,
                "document_id": document_id,
                "filename": filename,
                "error": str(e)
            }
    
    async def ingest_text(
        self,
        text: str,
        title: str = "text_content",
        source_type: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest raw text directly (no file parsing needed).
        
        Args:
            text: The text content to ingest
            title: Title/name for the content
            source_type: Type label for tracking
            metadata: Optional custom metadata
            
        Returns:
            Ingestion result
        """
        document_id = str(uuid.uuid4())
        
        logger.info(f"Ingesting text: {title} (doc_id: {document_id})")
        
        try:
            # Create document record
            await self._create_document_record(
                document_id=document_id,
                filename=title,
                file_path="",
                source_type=source_type,
                status="processing"
            )
            
            # Chunk the text
            cleaned_text = self.chunking_service.clean_text(text)
            chunk_metadata = {
                "title": title,
                "source_type": source_type,
                **(metadata or {})
            }
            
            chunks = self.chunking_service.chunk_text(
                cleaned_text,
                metadata=chunk_metadata,
                strategy=ChunkingStrategy.PARAGRAPH
            )
            
            if not chunks:
                raise ValueError("Chunking returned no chunks")
            
            # Ingest with batching
            rag_ids = []
            batch_size = 10
            delay_between_batches = 1.5
            
            for i, chunk in enumerate(chunks):
                chunk_key = f"{document_id}_chunk_{i}"
                
                try:
                    chunk_text = chunk.get("chunkText") or chunk.get("text", "")
                    
                    rag_args = {
                        "namespace": self.organization_id,
                        "key": chunk_key,
                        "text": chunk_text,
                        "title": f"{title} (part {i+1})",
                    }
                    
                    result = await self.convex_client.action("rag:ingest", rag_args)
                    rag_ids.append(result.get("entryId"))
                    
                    if (i + 1) % batch_size == 0 and i < len(chunks) - 1:
                        logger.info(f"  Ingested {i + 1}/{len(chunks)} chunks, pausing...")
                        await asyncio.sleep(delay_between_batches)
                        
                except Exception as e:
                    logger.warning(f"Failed to ingest chunk {i}: {e}")
            
            await self._update_document_status(
                document_id=document_id,
                status="completed",
                chunk_count=len(rag_ids),
                rag_entry_ids=rag_ids
            )
            
            return {
                "success": True,
                "document_id": document_id,
                "rag_entry_ids": rag_ids,
                "chunks_created": len(rag_ids),
                "title": title
            }
            
        except Exception as e:
            logger.error(f"Text ingestion failed: {e}")
            return {
                "success": False,
                "document_id": document_id,
                "error": str(e)
            }
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete a document and all its chunks from RAG.
        
        Args:
            document_id: The document to delete
            
        Returns:
            Deletion result
        """
        try:
            # Get document to find RAG entry IDs
            doc = await self.convex_client.query(
                "documents:getByDocumentId", 
                {"documentId": document_id}
            )
            
            if not doc:
                return {
                    "success": False,
                    "document_id": document_id,
                    "error": "Document not found"
                }

            chunks_deleted = 0
            
            # Delete RAG entries
            rag_entry_ids = doc.get("ragEntryIds", [])
            for entry_id in rag_entry_ids:
                try:
                    await self.convex_client.action(
                        "rag:deleteDocument", 
                        {"entryId": entry_id}
                    )
                    chunks_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete RAG entry {entry_id}: {e}")

            # Delete document record
            await self.convex_client.mutation(
                "documents:deleteByDocumentId", 
                {"documentId": document_id}
            )
            
            logger.info(f"Deleted document {document_id}: {chunks_deleted} chunks")
            return {
                "success": True,
                "document_id": document_id,
                "chunks_deleted": chunks_deleted
            }
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return {
                "success": False,
                "document_id": document_id,
                "error": str(e)
            }
    
    async def _create_document_record(
        self,
        document_id: str,
        filename: str,
        file_path: str,
        source_type: str,
        status: str
    ):
        """Create a document tracking record in Convex"""
        try:
            file_size = 0
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
            
            file_type = os.path.splitext(filename)[1].lower() if filename else ""
            
            await self.convex_client.mutation(
                "documents:create",
                {
                    "organizationId": self.organization_id,
                    "documentId": document_id,
                    "fileName": filename,
                    "fileType": file_type,
                    "fileSize": file_size,
                    "sourceType": source_type,
                    "status": status,
                    "chunkCount": 0
                }
            )
        except Exception as e:
            logger.warning(f"Could not create document record: {e}")
    
    async def _update_document_status(
        self,
        document_id: str,
        status: str,
        chunk_count: int = 0,
        rag_entry_ids: List[str] = None,
        error_message: str = None
    ):
        """Update document status in Convex"""
        try:
            args = {
                "documentId": document_id,
                "status": status,
                "chunkCount": chunk_count
            }
            if rag_entry_ids:
                args["ragEntryIds"] = rag_entry_ids
            if error_message:
                args["errorMessage"] = error_message
                
            await self.convex_client.mutation("documents:updateStatus", args)
        except Exception as e:
            logger.warning(f"Could not update document status: {e}")


def get_ingestion_service(organization_id: str) -> KnowledgeIngestionService:
    """
    Factory function to create an ingestion service instance.
    
    Args:
        organization_id: The organization identifier
        
    Returns:
        KnowledgeIngestionService instance
    """
    return KnowledgeIngestionService(organization_id)
