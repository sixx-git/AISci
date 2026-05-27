"""
文献统一导入服务

统一管理 arXiv / BibTeX / Google Scholar 等多来源文献的检索和导入。
"""
import uuid
import re
import os
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.models import Document, SourceType, ImportStatus, LibraryScope, DocumentStatus
from app.services.literature_sources.arxiv_source import ArxivSource, ArxivPaper
from app.services.literature_sources.bibtex_importer import BibTexImporter, BibTexParseError, parse_bibtex
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LiteratureIngestionService:
    """文献统一导入服务"""

    def __init__(self, db: Session):
        self.db = db
        self.arxiv_source = ArxivSource()

    # ==================== arXiv 搜索 ====================

    def search_arxiv(
        self,
        query: str,
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "relevance",
    ) -> List[Dict[str, Any]]:
        """
        搜索 arXiv 文献

        Args:
            query: 搜索关键词
            max_results: 最大返回数
            start: 分页偏移
            sort_by: 排序方式

        Returns:
            List[Dict]: ArxivPaper.to_dict() 列表
        """
        papers: List[ArxivPaper] = self.arxiv_source.search(
            query=query,
            max_results=max_results,
            start=start,
            sort_by=sort_by,
        )
        return [paper.to_dict() for paper in papers]

    def search_arxiv_by_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 arXiv ID 查询单篇论文

        Returns:
            Dict or None
        """
        paper = self.arxiv_source.search_by_id(arxiv_id)
        return paper.to_dict() if paper else None

    # ==================== arXiv 导入 ====================

    def import_arxiv_papers(
        self,
        project_id: str,
        papers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        批量导入 arXiv 论文元数据到 Document 表

        Args:
            project_id: 目标项目 ID
            papers: ArxivPaper.to_dict() 列表

        Returns:
            {
                "total": int,
                "imported": int,
                "duplicates": int,
                "failed": int,
                "results": [
                    {"external_id": str, "document_id": str, "title": str, "duplicate": bool}
                ]
            }
        """
        imported = 0
        duplicates = 0
        failed = 0
        results = []

        for paper in papers:
            try:
                doc_id, is_dup = self._import_single_paper(project_id, paper)
                results.append({
                    "external_id": paper.get("external_id", ""),
                    "document_id": doc_id,
                    "title": paper.get("title", "")[:100],
                    "duplicate": is_dup,
                })
                if is_dup:
                    duplicates += 1
                else:
                    imported += 1
            except Exception as e:
                logger.error(f"导入文献失败: {paper.get('external_id', '?')} - {e}")
                results.append({
                    "external_id": paper.get("external_id", ""),
                    "document_id": None,
                    "title": paper.get("title", "")[:100],
                    "duplicate": False,
                    "error": str(e),
                })
                failed += 1

        return {
            "total": len(papers),
            "imported": imported,
            "duplicates": duplicates,
            "failed": failed,
            "results": results,
        }

    def _import_single_paper(
        self,
        project_id: str,
        paper: Dict[str, Any],
    ) -> Tuple[str, bool]:
        """
        导入单篇 arXiv 论文

        Returns:
            Tuple[str, bool]: (document_id, is_duplicate)
        """
        external_id = paper.get("external_id", "")

        # 去重：同一 project_id + external_id 不重复创建
        existing = (
            self.db.query(Document)
            .filter(
                Document.project_id == project_id,
                Document.external_id == external_id,
                Document.source_type == SourceType.ARXIV,
            )
            .first()
        )
        if existing:
            logger.debug(f"已存在，跳过: {external_id}")
            return existing.id, True

        # 解析发布时间
        published_at = None
        pub_str = paper.get("published_at")
        if pub_str:
            try:
                published_at = datetime.fromisoformat(pub_str)
            except (ValueError, TypeError):
                pass

        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            project_id=project_id,
            filename=paper.get("title", "untitled")[:255],
            file_path="",  # 未下载 PDF
            file_type="pdf",
            file_size=0,
            title=paper.get("title", ""),
            authors=paper.get("authors", ""),
            abstract=paper.get("abstract", ""),
            doi=paper.get("doi"),
            publication_date=published_at,
            journal=paper.get("journal_ref"),
            source_url=paper.get("source_url", ""),
            pdf_url=paper.get("pdf_url", ""),
            external_id=external_id,
            # 多来源字段
            source_type=SourceType.ARXIV,
            library_scope=LibraryScope.BASE,
            import_status=ImportStatus.IMPORTED,
            is_personal=False,
            metadata_json={
                "arxiv_id": external_id,
                "categories": paper.get("categories", ""),
                "comment": paper.get("comment"),
                "journal_ref": paper.get("journal_ref"),
                "source_type": "arxiv",
            },
            created_at=datetime.now(),
        )

        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        logger.info(f"导入成功: {external_id} -> {doc_id}")
        return doc_id, False

    # ==================== 项目文献查询 ====================

    def get_project_documents(
        self,
        project_id: str,
        source_type: Optional[str] = None,
        library_scope: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        查询项目已导入的文献

        Args:
            project_id: 项目 ID
            source_type: 按来源筛选（upload / arxiv / bibtex ...）
            library_scope: 按范围筛选（base / project / personal）
            page: 页码
            page_size: 每页数量

        Returns:
            {"total": int, "items": [...], "page": int, "page_size": int}
        """
        q = self.db.query(Document).filter(Document.project_id == project_id)

        if source_type:
            q = q.filter(Document.source_type == source_type)
        if library_scope:
            q = q.filter(Document.library_scope == library_scope)

        total = q.count()

        offset = (page - 1) * page_size
        items = q.order_by(Document.created_at.desc()).offset(offset).limit(page_size).all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": d.id,
                    "title": d.title,
                    "authors": d.authors,
                    "abstract": (d.abstract or "")[:500],
                    "doi": d.doi,
                    "external_id": d.external_id,
                    "source_type": d.source_type.value if d.source_type else None,
                    "source_url": d.source_url,
                    "pdf_url": d.pdf_url,
                    "library_scope": d.library_scope.value if d.library_scope else None,
                    "import_status": d.import_status.value if d.import_status else None,
                    "is_personal": d.is_personal,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in items
            ],
        }

    # ==================== BibTeX 导入 ====================

    def import_bibtex(
        self,
        project_id: str,
        bibtex_text: str,
        source_type: str = "google_scholar_import",
    ) -> Dict[str, Any]:
        """
        解析 BibTeX 并导入为项目文献

        Args:
            project_id: 目标项目 ID
            bibtex_text: BibTeX 格式文本
            source_type: 来源类型标记（默认 google_scholar_import）

        Returns:
            {
                "total": int,
                "imported": int,
                "duplicates": int,
                "failed": int,
                "parse_errors": [...],
                "results": [...]
            }

        Raises:
            BibTexParseError: BibTeX 文本无法解析时抛出
        """
        # 1. 解析 BibTeX
        entries = parse_bibtex(bibtex_text, source_type=source_type)

        # 2. 逐条导入
        imported = 0
        duplicates = 0
        failed = 0
        results = []

        for entry in entries:
            try:
                doc_id, is_dup = self._import_bibtex_entry(project_id, entry)
                results.append({
                    "cite_key": entry.get("cite_key", ""),
                    "title": entry.get("title", "")[:100],
                    "document_id": doc_id,
                    "duplicate": is_dup,
                })
                if is_dup:
                    duplicates += 1
                else:
                    imported += 1
            except Exception as e:
                logger.error(f"BibTeX 导入失败: {entry.get('cite_key', '?')} - {e}")
                results.append({
                    "cite_key": entry.get("cite_key", ""),
                    "title": entry.get("title", "")[:100],
                    "document_id": None,
                    "duplicate": False,
                    "error": str(e),
                })
                failed += 1

        return {
            "total": len(entries),
            "imported": imported,
            "duplicates": duplicates,
            "failed": failed,
            "results": results,
        }

    def _import_bibtex_entry(
        self,
        project_id: str,
        entry: Dict[str, Any],
    ) -> Tuple[str, bool]:
        """
        导入单个 BibTeX 条目

        去重策略（按优先级）：
          1. 优先 DOI
          2. 其次 URL
          3. 其次标题归一化（去除非字母数字、小写）

        Returns:
            Tuple[str, bool]: (document_id, is_duplicate)
        """
        # ========== 去重检查 ==========
        existing = self._find_bibtex_duplicate(project_id, entry)
        if existing:
            logger.debug(f"BibTeX 条目已存在，跳过: {entry.get('title', '?')[:60]}")
            return existing.id, True

        # ========== 构造 source_type 枚举 ==========
        src_type_str = entry.get("source_type", "google_scholar_import")
        try:
            src_type = SourceType(src_type_str)
        except ValueError:
            src_type = SourceType.GOOGLE_SCHOLAR_IMPORT

        # ========== 构造 Document ==========
        doc_id = str(uuid.uuid4())
        year = entry.get("year")
        published_at = None
        if year:
            try:
                published_at = datetime(year=int(year), month=1, day=1)
            except (ValueError, TypeError):
                pass

        # journal / booktitle 合并为 journal 字段
        journal = entry.get("journal") or entry.get("booktitle") or None

        doc = Document(
            id=doc_id,
            project_id=project_id,
            filename=entry.get("title", "untitled")[:255],
            file_path="",  # 不下载 PDF
            file_type="bibtex",
            file_size=0,
            title=entry.get("title", ""),
            authors=entry.get("authors", ""),
            abstract=entry.get("abstract", ""),
            doi=entry.get("doi"),
            publication_date=published_at,
            journal=journal,
            volume=entry.get("volume"),
            number=entry.get("number"),
            pages=entry.get("pages"),
            publisher=entry.get("publisher"),
            source_url=entry.get("url", ""),
            pdf_url="",
            external_id=entry.get("cite_key", ""),
            # 多来源字段
            source_type=src_type,
            library_scope=LibraryScope.PROJECT,
            import_status=ImportStatus.IMPORTED,
            is_personal=True,
            metadata_json={
                "entry_type": entry.get("entry_type"),
                "cite_key": entry.get("cite_key"),
                "booktitle": entry.get("booktitle"),
                "publisher": entry.get("publisher"),
                "source_type": src_type_str,
                "import_method": "bibtex_paste",
            },
            created_at=datetime.now(),
        )

        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        logger.info(f"BibTeX 导入成功: {entry.get('cite_key', '?')} -> {doc_id}")
        return doc_id, False

    def _find_bibtex_duplicate(
        self,
        project_id: str,
        entry: Dict[str, Any],
    ) -> Optional[Document]:
        """
        检查 BibTeX 条目是否已存在

        去重优先级: DOI > URL > 归一化标题
        """
        # 1. DOI 去重
        doi = entry.get("doi")
        if doi:
            existing = (
                self.db.query(Document)
                .filter(
                    Document.project_id == project_id,
                    Document.doi == doi,
                )
                .first()
            )
            if existing:
                return existing

        # 2. URL 去重
        url = entry.get("url")
        if url:
            existing = (
                self.db.query(Document)
                .filter(
                    Document.project_id == project_id,
                    Document.source_url == url,
                )
                .first()
            )
            if existing:
                return existing

        # 3. 标题归一化去重（去除非字母数字 + 小写）
        title = entry.get("title", "").strip()
        if title:
            normalized = re.sub(r'[^a-z0-9]', '', title.lower())
            if normalized:
                # 检查所有项目的文献，若标题归一化后匹配
                candidates = (
                    self.db.query(Document)
                    .filter(Document.project_id == project_id)
                    .filter(Document.title.isnot(None))
                    .all()
                )
                for c in candidates:
                    if c.title:
                        c_norm = re.sub(r'[^a-z0-9]', '', (c.title or "").lower().strip())
                        if c_norm and c_norm == normalized:
                            return c

        return None

    # ==================== arXiv PDF 下载 ====================

    def download_arxiv_pdf(
        self,
        project_id: str,
        document_id: str,
    ) -> Dict[str, Any]:
        """
        下载 arXiv 论文 PDF

        从 Document.pdf_url 下载 PDF 文件，保存到本地存储，
        更新 Document.file_path 和 import_status。

        Args:
            project_id: 项目 ID
            document_id: 文献 Document ID

        Returns:
            {
                "document_id": str,
                "pdf_url": str,
                "file_path": str,
                "file_size": int,
                "status": "pdf_downloaded",
            }

        Raises:
            ValueError: 文档不存在 / 不是 arXiv 来源 / 无 PDF URL
            RuntimeError: 下载失败
        """
        # 1. 查找文档
        doc = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.project_id == project_id)
            .first()
        )
        if not doc:
            raise ValueError(f"文献不存在: {document_id}")

        # 2. 检查 PDF URL
        pdf_url = doc.pdf_url or ""
        if not pdf_url:
            raise ValueError(f"该文献无 PDF 下载链接（pdf_url 为空）")
        if not pdf_url.startswith(("http://", "https://")):
            raise ValueError(f"无效的 PDF URL: {pdf_url}")

        # 3. 准备本地存储路径
        settings = get_settings()
        upload_dir = settings.UPLOAD_DIR
        storage_dir = os.path.join(upload_dir, project_id, "external", "arxiv")
        os.makedirs(storage_dir, exist_ok=True)

        pdf_path = os.path.join(storage_dir, f"{document_id}.pdf")

        # 4. 下载 PDF
        logger.info(f"开始下载 arXiv PDF: {pdf_url} -> {pdf_path}")
        try:
            headers = {
                "User-Agent": "AI-Scientist/1.0 (mailto:research@example.com)",
            }
            resp = requests.get(pdf_url, headers=headers, timeout=60, stream=True)
            resp.raise_for_status()

            # 检查 Content-Type（arXiv 可能返回 HTML 错误页而非 PDF）
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type and b"<html" in resp.content[:200].lower():
                raise RuntimeError("arXiv 返回了 HTML 页面而非 PDF，可能是频率限制，请稍后重试")

            with open(pdf_path, "wb") as f:
                file_size = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        file_size += len(chunk)

        except requests.Timeout:
            raise RuntimeError(f"下载 PDF 超时（60s）: {pdf_url}")
        except requests.RequestException as e:
            raise RuntimeError(f"下载 PDF 失败: {e}")

        # 5. 更新 Document
        doc.file_path = pdf_path
        doc.file_size = file_size
        doc.file_type = "pdf"
        doc.mime_type = "application/pdf"
        doc.import_status = ImportStatus.PDF_DOWNLOADED
        doc.updated_at = datetime.now()

        self.db.commit()
        self.db.refresh(doc)

        logger.info(f"arXiv PDF 下载完成: {document_id} ({file_size} bytes) -> {pdf_path}")

        return {
            "document_id": document_id,
            "pdf_url": pdf_url,
            "file_path": pdf_path,
            "file_size": file_size,
            "status": doc.import_status.value,
        }

    # ==================== PDF 解析 + 向量索引 ====================

    def parse_and_index_document(
        self,
        project_id: str,
        document_id: str,
        auto_index: bool = True,
    ) -> Dict[str, Any]:
        """
        解析文献 PDF 并构建向量索引

        流程：
          1. 查找 Document，验证 PDF 已下载
          2. 调用 DocumentParser 解析 PDF，生成 Chunk
          3. 更新 import_status = parsed
          4. 若 auto_index=True，调用 VectorStore.build_index() 增量添加索引
          5. 更新 import_status = indexed

        Args:
            project_id: 项目 ID
            document_id: 文献 Document ID
            auto_index: 是否自动构建向量索引

        Returns:
            {
                "document_id": str,
                "title": str,
                "chunk_count": int,
                "status": "indexed" | "parsed",
                "index_added": int | None,
            }

        Raises:
            ValueError: 文档不存在 / PDF 未下载
            RuntimeError: 解析或索引失败
        """
        # 1. 查找文档
        doc = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.project_id == project_id)
            .first()
        )
        if not doc:
            raise ValueError(f"文献不存在: {document_id}")

        # 2. 验证 PDF 是否已下载
        if not doc.file_path or not os.path.exists(doc.file_path):
            raise ValueError(f"PDF 文件未下载或不存在，请先调用 download-pdf 下载")
        if not doc.file_path.lower().endswith(".pdf"):
            raise ValueError(f"文件不是 PDF 格式: {doc.file_path}")

        # 3. 解析 PDF，生成 Chunk
        logger.info(f"开始解析 PDF: {doc.file_path}")
        doc.import_status = ImportStatus.PARSED  # 默认先标 parsed（解析完成后可能改成 indexed）
        doc.status = DocumentStatus.PROCESSING
        self.db.flush()

        try:
            from app.services.document_parser import DocumentParser

            parser = DocumentParser(self.db)
            doc, chunks = parser.parse_file(
                file_path=doc.file_path,
                project_id=project_id,
                original_filename=doc.filename or f"{document_id}.pdf",
                document=doc,  # 复用已有 Document，不创建新的
            )

            # 更新 import_status
            doc.import_status = ImportStatus.PARSED
            doc.status = DocumentStatus.PROCESSED
            doc.chunk_count = len(chunks)
            self.db.commit()
            self.db.refresh(doc)

            logger.info(f"PDF 解析完成: {document_id} -> {len(chunks)} chunks")

        except Exception as e:
            doc.import_status = ImportStatus.FAILED
            doc.status = DocumentStatus.FAILED
            doc.error_message = f"解析失败: {str(e)}"
            self.db.commit()
            raise RuntimeError(f"PDF 解析失败: {e}") from e

        # 4. 构建向量索引
        index_added = None
        if auto_index and chunks:
            logger.info(f"开始构建向量索引: project={project_id}")
            try:
                from app.services.vector_store import build_vector_index

                # build_vector_index 索引项目下所有已 processed 的 chunk
                # （包括刚解析的 + 之前已有的）
                index_added = build_vector_index(project_id, db=self.db)

                # 更新 import_status
                doc.import_status = ImportStatus.INDEXED
                self.db.commit()

                logger.info(f"向量索引完成: project={project_id}, added={index_added}")

            except Exception as e:
                logger.error(f"向量索引失败（文献已解析）: {e}")
                # 索引失败不影响解析结果，保留 parsed 状态
                doc.error_message = (doc.error_message or "") + f"; 索引失败: {str(e)}"
                self.db.commit()
                raise RuntimeError(f"PDF 解析成功但索引失败: {e}") from e

        result = {
            "document_id": document_id,
            "title": doc.title or doc.filename,
            "chunk_count": doc.chunk_count or 0,
            "status": doc.import_status.value,
            "index_added": index_added,
        }
        return result