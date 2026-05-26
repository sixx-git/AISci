"""
文献解析模块 - 用于解析 PDF 文档并提取内容
"""
import os
import re
import uuid
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
from enum import Enum
from datetime import datetime

from sqlalchemy.orm import Session

# Models
from app.models import (
    Document,
    Chunk,
    DocumentType,
    DocumentStatus,
    ChunkStatus
)

# Configuration
from app.core.config import get_settings

settings = get_settings()


class ParserBackend(Enum):
    """PDF 解析后端枚举"""
    PYPDF = "pypdf"
    PYMUPDF = "pymupdf"


@dataclass
class ParsedDocument:
    """解析后的文档数据结构"""
    title: str = ""
    authors: str = ""
    abstract: str = ""
    content: str = ""
    references: str = ""
    pages: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TextChunk:
    """文本切片数据结构"""
    content: str
    start_page: int
    end_page: int
    start_offset: int = 0
    end_offset: int = 0
    chunk_type: str = "text"


class DocumentParser:
    """文档解析器"""
    
    def __init__(
        self,
        db: Session,
        backend: ParserBackend = ParserBackend.PYMUPDF,
        min_chunk_size: int = 800,
        max_chunk_size: int = 1200,
        overlap: int = 100
    ):
        self.db = db
        self.backend = backend
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.fitz = None
        self.PdfReader = None
        
        # 检查后端可用性
        self._check_backend()
    
    def _check_backend(self):
        """检查解析后端是否可用"""
        if self.backend == ParserBackend.PYMUPDF:
            try:
                import fitz
                self.fitz = fitz
            except ImportError:
                print("Warning: pymupdf not available, falling back to pypdf")
                self.backend = ParserBackend.PYPDF
        
        if self.backend == ParserBackend.PYPDF:
            try:
                from pypdf import PdfReader
                self.PdfReader = PdfReader
            except ImportError:
                try:
                    # 尝试使用已有的 PyPDF2
                    from PyPDF2 import PdfReader
                    self.PdfReader = PdfReader
                except ImportError:
                    print("Warning: Neither pymupdf nor pypdf available. Only text files supported.")
                    self.backend = None
    
    def parse_file(
        self,
        file_path: str,
        project_id: Optional[str] = None,
        original_filename: Optional[str] = None
    ) -> Tuple[Document, List[Chunk]]:
        """
        解析文件并保存到数据库
        
        Args:
            file_path: 文件路径
            project_id: 关联的项目 ID
            original_filename: 原始文件名
            
        Returns:
            Tuple[Document, List[Chunk]]: 创建的文档和切片
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = Path(file_path).suffix.lower()
        
        # 创建文档记录
        document = self._create_document_record(
            file_path=file_path,
            project_id=project_id,
            original_filename=original_filename or Path(file_path).name,
            file_ext=file_ext
        )
        
        try:
            # 解析文件
            if file_ext == '.pdf':
                parsed_data = self._parse_pdf(file_path)
            else:
                # 简单文本处理
                parsed_data = self._parse_simple_text(file_path)
            
            # 更新文档信息
            self._update_document_record(document, parsed_data)
            
            # 切片并保存
            chunks = self._split_and_save_chunks(
                document=document,
                parsed_data=parsed_data
            )
            
            # 更新文档状态
            document.status = DocumentStatus.PROCESSED
            self.db.commit()
            
            return document, chunks
            
        except Exception as e:
            # 处理失败
            document.status = DocumentStatus.FAILED
            document.error_message = str(e)
            self.db.commit()
            raise
    
    def _create_document_record(
        self,
        file_path: str,
        project_id: Optional[str],
        original_filename: str,
        file_ext: str
    ) -> Document:
        """创建初始文档记录"""
        file_size = os.path.getsize(file_path)
        
        document = Document(
            id=str(uuid.uuid4()),
            project_id=project_id,
            filename=original_filename,
            file_path=file_path,
            file_type=file_ext.lstrip('.'),
            file_size=file_size,
            doc_type=DocumentType.RESEARCH_PAPER,
            status=DocumentStatus.PROCESSING,
            created_at=datetime.now()
        )
        
        self.db.add(document)
        self.db.flush()
        
        return document
    
    def _update_document_record(
        self,
        document: Document,
        parsed_data: ParsedDocument
    ):
        """更新文档记录"""
        document.title = parsed_data.title
        document.authors = parsed_data.authors
        document.abstract = parsed_data.abstract
        document.raw_text = parsed_data.content
        document.extra_metadata = parsed_data.metadata
        document.updated_at = datetime.now()
    
    def _parse_pdf(self, file_path: str) -> ParsedDocument:
        """解析 PDF 文件"""
        if self.backend is None:
            raise RuntimeError("No PDF parsing backend available. Please install pymupdf or pypdf.")
        
        if self.backend == ParserBackend.PYMUPDF:
            return self._parse_pdf_pymupdf(file_path)
        else:
            return self._parse_pdf_pypdf(file_path)
    
    def _parse_pdf_pymupdf(self, file_path: str) -> ParsedDocument:
        """使用 pymupdf 解析 PDF"""
        doc = self.fitz.open(file_path)
        parsed = ParsedDocument(pages=len(doc))
        
        full_text = []
        page_texts = []
        
        for page_num, page in enumerate(doc, 1):
            text = page.get_text()
            page_texts.append(text)
            full_text.append(text)
            
            # 提取元数据（前几页）
            if page_num <= 3:
                self._extract_metadata_from_page(text, parsed, page_num)
        
        parsed.content = "\n".join(full_text)
        
        # 提取参考文献（最后几页）
        if len(page_texts) > 0:
            refs_start = max(0, len(page_texts) - 5)
            ref_text = "\n".join(page_texts[refs_start:])
            parsed.references = self._extract_references(ref_text)
        
        # 获取 PDF 元数据
        metadata = doc.metadata
        if metadata:
            parsed.metadata['pdf_metadata'] = {
                'title': metadata.get('title', ''),
                'author': metadata.get('author', ''),
                'subject': metadata.get('subject', ''),
                'keywords': metadata.get('keywords', ''),
                'creator': metadata.get('creator', '')
            }
        
        doc.close()
        return parsed
    
    def _parse_pdf_pypdf(self, file_path: str) -> ParsedDocument:
        """使用 pypdf 解析 PDF"""
        with open(file_path, 'rb') as f:
            reader = self.PdfReader(f)
            parsed = ParsedDocument(pages=len(reader.pages))
            
            full_text = []
            page_texts = []
            
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text()
                    if text:
                        page_texts.append(text)
                        full_text.append(text)
                        
                        # 提取元数据（前几页）
                        if page_num <= 3:
                            self._extract_metadata_from_page(text, parsed, page_num)
                except Exception as e:
                    print(f"Warning: Error extracting page {page_num}: {e}")
                    continue
            
            parsed.content = "\n".join(full_text)
            
            # 提取参考文献
            if len(page_texts) > 0:
                refs_start = max(0, len(page_texts) - 5)
                ref_text = "\n".join(page_texts[refs_start:])
                parsed.references = self._extract_references(ref_text)
            
            # 元数据
            if reader.metadata:
                parsed.metadata['pdf_metadata'] = {
                    'title': reader.metadata.get('/Title', ''),
                    'author': reader.metadata.get('/Author', ''),
                    'subject': reader.metadata.get('/Subject', ''),
                    'keywords': reader.metadata.get('/Keywords', ''),
                    'creator': reader.metadata.get('/Creator', '')
                }
        
        return parsed
    
    def _extract_metadata_from_page(self, text: str, parsed: ParsedDocument, page_num: int):
        """从页面文本中提取元数据"""
        lines = text.strip().split('\n')
        lines = [l.strip() for l in lines if l.strip()]
        
        if page_num == 1:
            # 第一页，尝试提取标题
            if not parsed.title and lines:
                # 标题通常在前几行
                for i in range(min(3, len(lines))):
                    if len(lines[i]) > 3 and not any(keyword in lines[i].lower() 
                        for keyword in ['abstract', 'introduction', '摘要', '引言']):
                        parsed.title = lines[i]
                        break
            
            # 尝试提取摘要
            if not parsed.abstract:
                abstract_match = re.search(
                    r'(?:abstract|摘要)(?:\s*[:：])?\s*([\s\S]*?)(?=\n\s*(?:keywords|introduction|引言|关键词|$))',
                    text,
                    re.IGNORECASE
                )
                if abstract_match:
                    parsed.abstract = abstract_match.group(1).strip()
        
        # 尝试提取作者
        if not parsed.authors:
            author_match = re.search(
                r'(?:authors?|作者)(?:\s*[:：])?\s*([\s\S]*?)(?=\n\s*(?:abstract|introduction|$))',
                text,
                re.IGNORECASE
            )
            if author_match:
                parsed.authors = author_match.group(1).strip()
    
    def _extract_references(self, text: str) -> str:
        """提取参考文献"""
        # 查找参考文献部分
        ref_patterns = [
            r'(?:references|bibliography|参考文献)(?:\s*[:：])?\s*([\s\S]*)$',
            r'^[\d\[\]]+\s*[\w\W]*$'
        ]
        
        for pattern in ref_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip() if len(match.groups()) > 0 else text
        
        return ""
    
    def _parse_simple_text(self, file_path: str) -> ParsedDocument:
        """解析简单文本文件"""
        parsed = ParsedDocument()
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            parsed.content = content
            parsed.title = Path(file_path).stem
        
        return parsed
    
    def _split_and_save_chunks(
        self,
        document: Document,
        parsed_data: ParsedDocument
    ) -> List[Chunk]:
        """切片并保存"""
        text_chunks = self._split_text_by_chinese_characters(
            parsed_data.content,
            self.min_chunk_size,
            self.max_chunk_size,
            self.overlap
        )
        
        chunks = []
        
        for idx, chunk in enumerate(text_chunks):
            db_chunk = Chunk(
                id=str(uuid.uuid4()),
                project_id=document.project_id,
                document_id=document.id,
                chunk_index=idx,
                content=chunk.content,
                content_preview=chunk.content[:200] if len(chunk.content) > 200 else chunk.content,
                start_page=chunk.start_page,
                end_page=chunk.end_page,
                page_number=chunk.start_page,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                chunk_type=chunk.chunk_type,
                status=ChunkStatus.PENDING,
                created_at=datetime.now()
            )
            self.db.add(db_chunk)
            chunks.append(db_chunk)
        
        self.db.flush()
        return chunks
    
    def _split_text_by_chinese_characters(
        self,
        text: str,
        min_size: int,
        max_size: int,
        overlap: int
    ) -> List[TextChunk]:
        """
        按中文字符数切片
        
        Args:
            text: 原始文本
            min_size: 最小切片大小
            max_size: 最大切片大小
            overlap: 重叠大小
            
        Returns:
            切片列表
        """
        if not text.strip():
            return []
        
        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_length = 0
        start_offset = 0
        page_num = 1
        
        for line in lines:
            # 估计页码（简单方法：按换页符或固定长度）
            if '\x0c' in line:
                page_num += 1
                line = line.replace('\x0c', '')
            
            # 计算这一行的中文字符数
            line_chars = self._count_chinese_chars(line)
            
            if current_length + line_chars > max_size and current_length > 0:
                # 当前切片已满，创建切片
                chunk_content = '\n'.join(current_chunk)
                chunks.append(TextChunk(
                    content=chunk_content,
                    start_page=page_num,
                    end_page=page_num,
                    start_offset=start_offset,
                    end_offset=start_offset + len(chunk_content)
                ))
                
                # 保留重叠部分
                if overlap > 0:
                    # 计算重叠文本
                    overlap_text = chunk_content[-min(overlap, len(chunk_content)):]
                    # 查找合适的分割点
                    if overlap_text:
                        current_chunk = [overlap_text]
                        current_length = self._count_chinese_chars(overlap_text)
                        start_offset = start_offset + len(chunk_content) - len(overlap_text)
                    else:
                        current_chunk = []
                        current_length = 0
                        start_offset = start_offset + len(chunk_content)
                else:
                    current_chunk = []
                    current_length = 0
                    start_offset = start_offset + len(chunk_content)
            
            # 添加当前行
            current_chunk.append(line)
            current_length += line_chars
        
        # 处理剩余部分
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(TextChunk(
                content=chunk_content,
                start_page=page_num,
                end_page=page_num,
                start_offset=start_offset,
                end_offset=start_offset + len(chunk_content)
            ))
        
        return chunks
    
    def _count_chinese_chars(self, text: str) -> int:
        """计算中文字符数"""
        count = 0
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                count += 1
            else:
                # 英文字符按比例计算
                count += 0.5
        return int(count)


# ==================== 便捷函数 ====================

def parse_and_save_document(
    db: Session,
    file_path: str,
    project_id: Optional[str] = None,
    original_filename: Optional[str] = None,
    backend: ParserBackend = ParserBackend.PYMUPDF
) -> Tuple[Document, List[Chunk]]:
    """
    解析并保存文档的便捷函数
    
    Args:
        db: 数据库会话
        file_path: 文件路径
        project_id: 项目 ID
        original_filename: 原始文件名
        backend: 解析后端
        
    Returns:
        Tuple[Document, List[Chunk]]
    """
    parser = DocumentParser(db=db, backend=backend)
    return parser.parse_file(
        file_path=file_path,
        project_id=project_id,
        original_filename=original_filename
    )
