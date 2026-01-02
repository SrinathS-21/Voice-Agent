"""
Text Chunking Service
Domain-aware chunking strategies for optimal knowledge retrieval.
Supports multiple content types with specialized chunking logic.
"""

import re
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from app.core.logging import get_logger

logger = get_logger(__name__)


class ChunkingStrategy(str, Enum):
    """Available chunking strategies"""
    PARAGRAPH = "paragraph"      # Standard paragraph-based
    ITEM = "item"              # One item per chunk (products, menu items)
    FAQ = "faq"                # One Q&A pair per chunk
    SECTION = "section"        # Section-based (headers)
    SENTENCE = "sentence"      # Sentence-level (for dense content)
    FIXED = "fixed"            # Fixed character size


class ChunkingService:
    """
    Service for chunking text into semantic segments.
    Supports domain-aware chunking strategies for better retrieval.
    """
    
    def __init__(
        self,
        chunk_size: int = 400,
        chunk_overlap: int = 150,
        min_chunk_size: int = 50
    ):
        """
        Initialize chunking service
        
        Args:
            chunk_size: Target size for each chunk (in characters)
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum size for a chunk (discard smaller chunks)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        
        logger.info(
            f"ChunkingService initialized: chunk_size={chunk_size}, "
            f"overlap={chunk_overlap}, min_size={min_chunk_size}"
        )
    
    def chunk_text(
        self,
        text: str,
        metadata: Dict[str, Any] = None,
        strategy: ChunkingStrategy = ChunkingStrategy.PARAGRAPH
    ) -> List[Dict[str, Any]]:
        """
        Chunk text into semantic segments using specified strategy.
        
        Args:
            text: The text to chunk
            metadata: Optional metadata to attach to each chunk
            strategy: Chunking strategy to use
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or not text.strip():
            return []
        
        # Clean the text
        text = self.clean_text(text)
        
        # Select strategy
        if strategy == ChunkingStrategy.FAQ:
            return self._chunk_faq(text, metadata)
        elif strategy == ChunkingStrategy.ITEM:
            return self._chunk_items(text, metadata)
        elif strategy == ChunkingStrategy.SECTION:
            return self.chunk_by_sections(text)
        elif strategy == ChunkingStrategy.SENTENCE:
            return self._chunk_sentences(text, metadata)
        else:
            # Default paragraph-based chunking
            return self._chunk_paragraphs(text, metadata)
    
    def _chunk_paragraphs(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Standard paragraph-based chunking"""
        paragraphs = self._split_by_paragraphs(text)
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(self._create_chunk(current_chunk, chunk_index, metadata))
                    chunk_index += 1
                    
                    overlap_text = self._get_overlap(current_chunk)
                    current_chunk = overlap_text + para
                else:
                    current_chunk += "\n\n" + para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(self._create_chunk(current_chunk, chunk_index, metadata))
        
        logger.info(f"Paragraph chunking: {len(chunks)} chunks")
        return chunks
    
    def _chunk_faq(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Chunk FAQ content - one Q&A pair per chunk.
        Preserves question-answer relationships for better retrieval.
        """
        chunks = []
        chunk_index = 0
        
        # Pattern 1: Q: ... A: ... format
        qa_pattern = re.findall(
            r'(?:Q:|Question:?)\s*(.+?)\n+(?:A:|Answer:?)\s*(.+?)(?=\n\n|\n(?:Q:|Question:)|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        
        if qa_pattern:
            for question, answer in qa_pattern:
                q = question.strip()
                a = answer.strip()
                if q and a:
                    chunk_text = f"Question: {q}\nAnswer: {a}"
                    chunk_meta = {**(metadata or {}), "type": "faq", "question": q}
                    chunks.append(self._create_chunk(chunk_text, chunk_index, chunk_meta))
                    chunk_index += 1
        else:
            # Pattern 2: Lines ending with ? followed by answer
            lines = text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.endswith('?'):
                    question = line
                    # Collect answer (next non-empty lines until next question)
                    answer_parts = []
                    i += 1
                    while i < len(lines) and not lines[i].strip().endswith('?'):
                        if lines[i].strip():
                            answer_parts.append(lines[i].strip())
                        i += 1
                    
                    if answer_parts:
                        answer = ' '.join(answer_parts)
                        chunk_text = f"Question: {question}\nAnswer: {answer}"
                        chunk_meta = {**(metadata or {}), "type": "faq"}
                        chunks.append(self._create_chunk(chunk_text, chunk_index, chunk_meta))
                        chunk_index += 1
                else:
                    i += 1
        
        # Fallback to paragraph chunking if no Q&A found
        if not chunks:
            logger.warning("No FAQ patterns found, falling back to paragraph chunking")
            return self._chunk_paragraphs(text, metadata)
        
        logger.info(f"FAQ chunking: {len(chunks)} Q&A pairs")
        return chunks
    
    def _chunk_items(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Chunk item listings - attempts to identify individual items.
        Good for menus, product lists, service catalogs.
        """
        chunks = []
        chunk_index = 0
        current_category = ""
        
        lines = text.split('\n')
        current_item = []
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                # Empty line might separate items
                if current_item:
                    item_text = '\n'.join(current_item)
                    if len(item_text) >= self.min_chunk_size:
                        chunk_meta = {**(metadata or {}), "type": "item", "category": current_category}
                        chunks.append(self._create_chunk(item_text, chunk_index, chunk_meta))
                        chunk_index += 1
                    current_item = []
                continue
            
            # Check if line is a category header
            if self._is_category_header(line_stripped):
                # Save current item if any
                if current_item:
                    item_text = '\n'.join(current_item)
                    if len(item_text) >= self.min_chunk_size:
                        chunk_meta = {**(metadata or {}), "type": "item", "category": current_category}
                        chunks.append(self._create_chunk(item_text, chunk_index, chunk_meta))
                        chunk_index += 1
                    current_item = []
                
                current_category = line_stripped.rstrip(':').title()
                continue
            
            # Check if line starts a new item (has price or bullet)
            if self._is_item_start(line_stripped) and current_item:
                item_text = '\n'.join(current_item)
                if len(item_text) >= self.min_chunk_size:
                    chunk_meta = {**(metadata or {}), "type": "item", "category": current_category}
                    chunks.append(self._create_chunk(item_text, chunk_index, chunk_meta))
                    chunk_index += 1
                current_item = [line_stripped]
            else:
                current_item.append(line_stripped)
        
        # Don't forget last item
        if current_item:
            item_text = '\n'.join(current_item)
            if len(item_text) >= self.min_chunk_size:
                chunk_meta = {**(metadata or {}), "type": "item", "category": current_category}
                chunks.append(self._create_chunk(item_text, chunk_index, chunk_meta))
        
        # Fallback if no items identified
        if not chunks:
            logger.warning("No item patterns found, falling back to paragraph chunking")
            return self._chunk_paragraphs(text, metadata)
        
        logger.info(f"Item chunking: {len(chunks)} items")
        return chunks
    
    def _chunk_sentences(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Sentence-level chunking for dense content"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                chunks.append(self._create_chunk(current_chunk.strip(), chunk_index, metadata))
                chunk_index += 1
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(self._create_chunk(current_chunk.strip(), chunk_index, metadata))
        
        logger.info(f"Sentence chunking: {len(chunks)} chunks")
        return chunks
    
    def _is_category_header(self, line: str) -> bool:
        """Check if a line is likely a category header"""
        # All caps
        if line.isupper() and len(line) < 50:
            return True
        # Ends with colon
        if line.endswith(':') and len(line) < 50:
            return True
        # Common category patterns
        category_patterns = [
            r'^#+\s+',  # Markdown headers
            r'^\d+\.\s+[A-Z]',  # Numbered sections
        ]
        for pattern in category_patterns:
            if re.match(pattern, line):
                return True
        return False
    
    def _is_item_start(self, line: str) -> bool:
        """Check if a line likely starts a new item"""
        # Has price
        if re.search(r'\$\d+\.?\d*', line):
            return True
        # Starts with bullet
        if re.match(r'^[-•*]\s+', line):
            return True
        # Starts with number followed by period
        if re.match(r'^\d+\.\s+', line):
            return True
        return False
    
    def chunk_structured_data(
        self,
        items: List[Dict[str, Any]],
        item_template: str = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk structured data (e.g., menu items, products)
        Each item becomes its own chunk
        
        Args:
            items: List of structured data items
            item_template: Optional template for formatting items
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        
        for idx, item in enumerate(items):
            # Format item as text
            if item_template:
                chunk_text = item_template.format(**item)
            else:
                # Format: Name (Category) \n Description \n Price
                cat_str = f" ({item.get('category')})" if item.get('category') else ""
                chunk_text = f"{item['name']}{cat_str}\n{item.get('description', '')}\nPrice: ${item.get('price', 0)}"
            
            chunk = {
                "chunkText": chunk_text,
                "chunkIndex": idx,
                "metadata": {
                    "type": "structured_item",
                    "item_data": item
                }
            }
            chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} chunks from structured data")
        return chunks
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text while preserving paragraph structure.
        Also removes markdown formatting for cleaner voice output."""
        
        # Remove markdown table syntax - convert pipes to spaces
        text = re.sub(r'\|+', ' ', text)
        
        # Remove markdown headers (# ## ### etc) but keep the text
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        
        # Remove bold/italic markers (** * __ _)
        text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
        text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
        
        # Remove bullet point markers at start of lines
        text = re.sub(r'^[\-•]\s*', '', text, flags=re.MULTILINE)
        
        # Clean up table formatting artifacts (multiple dashes)
        text = re.sub(r'-{3,}', '', text)
        
        # Only collapse horizontal whitespace (spaces, tabs), preserve newlines
        text = re.sub(r'[ \t]+', ' ', text)
        # Normalize multiple newlines to max 2 (paragraph break)  
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Strip whitespace from each line but preserve empty lines for paragraph breaks
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)
        # Strip leading/trailing whitespace
        return text.strip()
    
    def _split_by_paragraphs(self, text: str) -> List[str]:
        """Split text by paragraph boundaries"""
        # Split by double newlines or section markers
        paragraphs = re.split(r'\n\n+', text)
        
        # Filter out empty paragraphs
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        return paragraphs
    
    def _get_overlap(self, text: str) -> str:
        """Get overlap text from the end of current chunk"""
        if len(text) <= self.chunk_overlap:
            return text
        
        # Try to break at sentence boundary
        overlap_text = text[-self.chunk_overlap:]
        
        # Find last sentence boundary in overlap
        sentence_end = max(
            overlap_text.rfind('. '),
            overlap_text.rfind('! '),
            overlap_text.rfind('? ')
        )
        
        if sentence_end > 0:
            overlap_text = overlap_text[sentence_end + 2:]
        
        return overlap_text
    
    def _create_chunk(
        self,
        text: str,
        index: int,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a chunk dictionary"""
        chunk = {
            "chunkText": text.strip(),
            "chunkIndex": index,
            "metadata": metadata or {}
        }
        return chunk
    
    def _format_item(self, item: Dict[str, Any]) -> str:
        """Format a structured item as text"""
        # Simple key-value formatting
        parts = []
        for key, value in item.items():
            if value is not None and str(value).strip():
                parts.append(f"{key}: {value}")
        return " | ".join(parts)
    
    def chunk_by_sections(
        self,
        text: str,
        section_markers: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk text by section headers
        
        Args:
            text: The text to chunk
            section_markers: List of regex patterns for section headers
            
        Returns:
            List of chunks, one per section
        """
        if section_markers is None:
            # Default section markers (markdown headers, numbered sections)
            section_markers = [
                r'^#{1,6}\s+.+$',  # Markdown headers
                r'^\d+\.\s+.+$',    # Numbered sections
                r'^[A-Z][A-Z\s]+$'  # ALL CAPS headers
            ]
        
        # Combine patterns
        pattern = '|'.join(f'({marker})' for marker in section_markers)
        
        # Split by sections
        sections = re.split(pattern, text, flags=re.MULTILINE)
        
        chunks = []
        chunk_index = 0
        
        for section in sections:
            if section and section.strip() and len(section.strip()) >= self.min_chunk_size:
                chunks.append(self._create_chunk(section.strip(), chunk_index))
                chunk_index += 1
        
        logger.info(f"Chunked text into {len(chunks)} sections")
        return chunks


def get_chunking_service(
    chunk_size: int = 400,
    chunk_overlap: int = 150
) -> ChunkingService:
    """
    Create a chunking service instance
    
    Args:
        chunk_size: Target size for each chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        ChunkingService instance
    """
    return ChunkingService(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
