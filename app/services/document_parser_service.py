"""
Document Parser Service
Handles document parsing and text extraction using LlamaParse
"""

import os
from typing import List, Dict, Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

# Check if LlamaParse is available
try:
    from llama_cloud_services import LlamaParse
    LLAMAPARSE_AVAILABLE = True
except ImportError:
    LLAMAPARSE_AVAILABLE = False
    logger.warning("llama-cloud-services not installed. Document parsing will be limited.")


class DocumentParserService:
    """Service for parsing documents using LlamaParse"""
    
    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        '.pdf', '.docx', '.doc', '.txt', '.rtf',
        '.csv', '.xlsx', '.xls',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
        '.html', '.htm'
    }
    
    def __init__(self, tier: str = "cost_effective"):
        """
        Initialize document parser
        
        Args:
            tier: Parsing tier - "cost_effective", "agentic", or "agentic_plus"
        """
        self.tier = tier
        self.parser = None
        
        if LLAMAPARSE_AVAILABLE:
            api_key = os.getenv("LLAMA_CLOUD_API_KEY")
            if api_key:
                self.parser = LlamaParse(
                    api_key=api_key,
                    result_type="markdown",  # Get markdown for easy chunking
                    num_workers=4,
                    verbose=False
                )
                logger.info(f"DocumentParserService initialized with LlamaParse (tier: {tier})")
            else:
                logger.warning("LLAMA_CLOUD_API_KEY not set. LlamaParse disabled.")
        else:
            logger.warning("LlamaParse not available. Using fallback text extraction.")
    
    def is_supported(self, filename: str) -> bool:
        """Check if file type is supported"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.SUPPORTED_EXTENSIONS
    
    async def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a single file and extract text content
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            Dictionary with parsed content and metadata
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        
        if not self.is_supported(filename):
            raise ValueError(f"Unsupported file type: {ext}")
        
        result = {
            "filename": filename,
            "file_type": ext,
            "file_size": os.path.getsize(file_path),
            "content": "",
            "pages": 0,
            "metadata": {}
        }
        
        try:
            if self.parser:
                # Use LlamaParse for extraction
                documents = await self.parser.aload_data(file_path)
                
                # Combine all document content
                content_parts = []
                for doc in documents:
                    content_parts.append(doc.text)
                    # Collect metadata from first doc
                    if not result["metadata"] and hasattr(doc, 'metadata'):
                        result["metadata"] = doc.metadata or {}
                
                result["content"] = "\n\n".join(content_parts)
                result["pages"] = len(documents)
                
                logger.info(f"Parsed {filename} with LlamaParse: {result['pages']} pages")
            else:
                # Fallback: basic text extraction
                result["content"] = await self._fallback_parse(file_path, ext)
                result["pages"] = 1
                
                logger.info(f"Parsed {filename} with fallback: {len(result['content'])} chars")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse {filename}: {str(e)}")
            raise Exception(f"Document parsing failed: {str(e)}")
    
    async def parse_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Parse multiple files
        
        Args:
            file_paths: List of file paths to parse
            
        Returns:
            List of parsed results
        """
        results = []
        for file_path in file_paths:
            try:
                result = await self.parse_file(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to parse {file_path}: {e}")
                results.append({
                    "filename": os.path.basename(file_path),
                    "error": str(e)
                })
        return results
    
    async def _fallback_parse(self, file_path: str, ext: str) -> str:
        """
        Fallback text extraction without LlamaParse
        
        Args:
            file_path: Path to file
            ext: File extension
            
        Returns:
            Extracted text content
        """
        # Simple text file reading
        if ext == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        
        # CSV parsing
        if ext == '.csv':
            import csv
            rows = []
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    rows.append(' | '.join(row))
            return '\n'.join(rows)
        
        # For other formats without LlamaParse, return error message
        return f"[Unable to parse {ext} files without LlamaParse. Please install llama-cloud-services.]"
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions"""
        return list(self.SUPPORTED_EXTENSIONS)


# Singleton instance
_parser_instance: Optional[DocumentParserService] = None


def get_document_parser(tier: str = "cost_effective") -> DocumentParserService:
    """
    Get or create document parser instance
    
    Args:
        tier: Parsing tier to use
        
    Returns:
        DocumentParserService instance
    """
    global _parser_instance
    
    if _parser_instance is None:
        _parser_instance = DocumentParserService(tier=tier)
    
    return _parser_instance
