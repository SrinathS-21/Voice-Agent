"""
Knowledge Base API Endpoints
Handles document upload, knowledge search, and management
"""

import os
import tempfile
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, status
from typing import Optional, List
from pydantic import BaseModel

from app.core.convex_client import get_convex_client
from app.services.knowledge_ingestion_service import get_ingestion_service
from app.services.knowledge_base_service import get_knowledge_base_service
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge-base"])


# ============================================
# SCHEMAS
# ============================================

class UploadResponse(BaseModel):
    success: bool
    document_id: str
    filename: str
    chunks_created: int = 0
    error: Optional[str] = None


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    source_type: str
    status: str
    chunk_count: int
    uploaded_at: int


class SearchResult(BaseModel):
    chunk_text: str
    score: float
    source_type: str
    metadata: dict


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int


# ============================================
# FILE UPLOAD ENDPOINTS
# ============================================

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    organization_id: str = Form(...),
    source_type: str = Form(default="general"),
):
    """
    Upload and ingest a document into the knowledge base
    
    - **file**: The document to upload (PDF, DOCX, CSV, TXT, images)
    - **organization_id**: The organization this document belongs to
    - **source_type**: Type of content - "menu", "faq", "policy", "catalog", etc.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check file size (max 20MB)
    MAX_SIZE = 20 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_SIZE // (1024*1024)}MB")
    
    # Save to temp file
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        # Ingest document
        ingestion_service = get_ingestion_service(organization_id)
        result = await ingestion_service.ingest_file(
            file_path=temp_path,
            source_type=source_type
        )
        
        return UploadResponse(
            success=result.get("success", False),
            document_id=result.get("document_id", ""),
            filename=result.get("filename", file.filename),
            chunks_created=result.get("chunks_created", 0),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup temp files
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================
# DOCUMENT MANAGEMENT ENDPOINTS
# ============================================

@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    organization_id: str = Query(...),
    status: Optional[str] = Query(None, description="Filter by status: completed, processing, failed")
):
    """
    List all documents for an organization
    """
    client = get_convex_client()
    
    try:
        args = {"organizationId": organization_id}
        if status:
            args["status"] = status
        
        docs = await client.query("documents:listByOrganization", args)
        
        return [
            DocumentResponse(
                document_id=doc.get("documentId", ""),
                filename=doc.get("fileName", ""),
                file_type=doc.get("fileType", ""),
                source_type=doc.get("sourceType", "general"),
                status=doc.get("status", "unknown"),
                chunk_count=doc.get("chunkCount", 0),
                uploaded_at=doc.get("uploadedAt", 0)
            )
            for doc in (docs or [])
        ]
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get details of a specific document
    """
    client = get_convex_client()
    
    try:
        doc = await client.query("documents:getByDocumentId", {"documentId": document_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return DocumentResponse(
            document_id=doc.get("documentId", ""),
            filename=doc.get("fileName", ""),
            file_type=doc.get("fileType", ""),
            source_type=doc.get("sourceType", "general"),
            status=doc.get("status", "unknown"),
            chunk_count=doc.get("chunkCount", 0),
            uploaded_at=doc.get("uploadedAt", 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, organization_id: str = Query(...)):
    """
    Delete a document and all its chunks
    """
    try:
        ingestion_service = get_ingestion_service(organization_id)
        result = await ingestion_service.delete_document(document_id)
        
        if result.get("success"):
            return {"message": "Document deleted", "chunks_deleted": result.get("chunks_deleted", 0)}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Delete failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# SEARCH ENDPOINTS
# ============================================

@router.get("/search", response_model=SearchResponse)
async def search_knowledge(
    organization_id: str = Query(...),
    query: str = Query(..., min_length=1),
    source_type: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20)
):
    """
    Search the knowledge base using semantic search
    
    - **query**: The search query (e.g., "vegetarian options", "return policy")
    - **source_type**: Optional filter by source type
    - **limit**: Maximum number of results (1-20)
    """
    try:
        kb_service = get_knowledge_base_service(organization_id)
        results = await kb_service.search_knowledge(
            query=query,
            source_type=source_type,
            limit=limit
        )
        
        return SearchResponse(
            query=query,
            results=[
                SearchResult(
                    chunk_text=r.get("chunkText", ""),
                    score=r.get("_score", 0.0),
                    source_type=r.get("sourceType", "general"),
                    metadata=r.get("metadata", {}) if isinstance(r.get("metadata"), dict) else {}
                )
                for r in results
            ],
            total_results=len(results)
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/menu", response_model=SearchResponse)
async def search_menu(
    organization_id: str = Query(...),
    query: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20)
):
    """
    Search menu items using semantic search
    
    - **query**: The search query (e.g., "spicy chicken", "vegetarian")
    - **category**: Optional category filter
    - **limit**: Maximum number of results
    """
    try:
        kb_service = get_knowledge_base_service(organization_id)
        results = await kb_service.search_menu(
            query=query,
            category=category,
            limit=limit
        )
        
        return SearchResponse(
            query=query,
            results=[
                SearchResult(
                    chunk_text=f"{r.get('name', '')} - ${r.get('price', 0):.2f}: {r.get('description', '')}",
                    score=r.get("_score", 0.0),
                    source_type="menu",
                    metadata={
                        "name": r.get("name"),
                        "price": r.get("price"),
                        "category": r.get("category")
                    }
                )
                for r in results
            ],
            total_results=len(results)
        )
        
    except Exception as e:
        logger.error(f"Menu search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# STATS ENDPOINT
# ============================================

@router.get("/stats")
async def get_knowledge_stats(organization_id: str = Query(...)):
    """
    Get statistics about the knowledge base
    """
    try:
        kb_service = get_knowledge_base_service(organization_id)
        stats = await kb_service.get_knowledge_stats()
        
        client = get_convex_client()
        doc_count = await client.query("documents:getCount", {"organizationId": organization_id})
        
        return {
            "organization_id": organization_id,
            "total_documents": doc_count or 0,
            "total_chunks": stats.get("totalChunks", 0),
            "embedding_dimensions": stats.get("embeddingDimensions", 768)
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
