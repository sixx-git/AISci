"""
公开数据集发现 Skill
参考能力：Hugging Face datasets、OpenML、Croissant metadata
——根据 research_question 推荐公开数据集，如果无法联网则返回 warning。
"""
import logging
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, List, Optional

from app.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15

KNOWN_DATASETS = [
    {
        "dataset_name": "PubMed / PubMed Central",
        "source": "NCBI / NIH",
        "license": "Public Domain / various",
        "url": "https://pubmed.ncbi.nlm.nih.gov/",
        "task_type": "text_mining",
        "modalities": ["text"],
        "metadata_standard": "PubMed XML",
        "description": "生物医学文献摘要与全文数据库",
    },
    {
        "dataset_name": "GEO (Gene Expression Omnibus)",
        "source": "NCBI",
        "license": "Public Domain",
        "url": "https://www.ncbi.nlm.nih.gov/geo/",
        "task_type": "gene_expression_analysis",
        "modalities": ["tabular", "genomics"],
        "metadata_standard": "MINiML / SOFT",
        "description": "基因表达综合数据库",
    },
    {
        "dataset_name": "ChEMBL",
        "source": "EBI",
        "license": "CC BY-SA 3.0",
        "url": "https://www.ebi.ac.uk/chembl/",
        "task_type": "drug_discovery",
        "modalities": ["tabular"],
        "metadata_standard": "ChEMBL schema",
        "description": "生物活性分子与药物靶点数据库，适用于纳米载药与靶向递送研究",
    },
    {
        "dataset_name": "PubChem BioAssay",
        "source": "NCBI",
        "license": "Public Domain",
        "url": "https://pubchem.ncbi.nlm.nih.gov/",
        "task_type": "drug_discovery",
        "modalities": ["tabular"],
        "metadata_standard": "PubChem",
        "description": "化合物生物活性与理化性质数据",
    },
    {
        "dataset_name": "Protein Data Bank (PDB)",
        "source": "rcsb.org",
        "license": "CC0 1.0",
        "url": "https://www.rcsb.org/",
        "task_type": "structure_prediction",
        "modalities": ["3d_structure"],
        "metadata_standard": "mmCIF / PDB",
        "description": "蛋白质 3D 结构数据库",
    },
    {
        "dataset_name": "TCGA (The Cancer Genome Atlas)",
        "source": "NCI",
        "license": "Restricted / Data Use Agreement",
        "url": "https://www.cancer.gov/tcga",
        "task_type": "genomic_analysis",
        "modalities": ["tabular", "genomics", "image"],
        "metadata_standard": "TCGA metadata",
        "description": "癌症基因组图谱，涵盖 33 种癌症类型",
    },
    {
        "dataset_name": "MIMIC-III / MIMIC-IV",
        "source": "PhysioNet",
        "license": "PhysioNet Restricted",
        "url": "https://physionet.org/content/mimiciii/",
        "task_type": "clinical_prediction",
        "modalities": ["tabular", "time_series", "text"],
        "metadata_standard": "MIMIC schema",
        "description": "重症监护病房临床数据集",
    },
    {
        "dataset_name": "UCI Machine Learning Repository",
        "source": "archive.ics.uci.edu",
        "license": "various",
        "url": "https://archive.ics.uci.edu/",
        "task_type": "classification/regression",
        "modalities": ["tabular"],
        "metadata_standard": "UCI metadata",
        "description": "经典表格数据集，涵盖生物、物理、金融等多个领域",
    },
    {
        "dataset_name": "Hugging Face Datasets",
        "source": "huggingface.co/datasets",
        "license": "various",
        "url": "https://huggingface.co/datasets",
        "task_type": "various",
        "modalities": ["text", "image", "audio", "tabular"],
        "metadata_standard": "Croissant / HF metadata",
        "description": "Hugging Face 数据集 Hub，可搜索 nanomedicine / drug delivery 等主题",
    },
    {
        "dataset_name": "Zenodo",
        "source": "zenodo.org",
        "license": "various",
        "url": "https://zenodo.org/",
        "task_type": "research_data",
        "modalities": ["tabular", "text", "image"],
        "metadata_standard": "DataCite",
        "description": "开放科研数据仓储，含纳米医学与药物递送专题数据集",
    },
    {
        "dataset_name": "Kaggle Datasets",
        "source": "kaggle.com",
        "license": "various",
        "url": "https://www.kaggle.com/datasets",
        "task_type": "various",
        "modalities": ["tabular", "image", "text", "time_series"],
        "metadata_standard": "Kaggle metadata",
        "description": "社区驱动的大规模开放数据集平台",
    },
    {
        "dataset_name": "OpenML",
        "source": "openml.org",
        "license": "various",
        "url": "https://www.openml.org/",
        "task_type": "classification/regression",
        "modalities": ["tabular"],
        "metadata_standard": "OpenML / ARFF",
        "description": "开放机器学习数据集和实验管理平台",
    },
    {
        "dataset_name": "ImageNet",
        "source": "image-net.org",
        "license": "Non-commercial research",
        "url": "https://www.image-net.org/",
        "task_type": "image_classification",
        "modalities": ["image"],
        "metadata_standard": "custom",
        "description": "大规模图像分类数据集，包含 1400 万+ 标注图像",
    },
    {
        "dataset_name": "CIFAR-10 / CIFAR-100",
        "source": "University of Toronto",
        "license": "CC-BY",
        "url": "https://www.cs.toronto.edu/~kriz/cifar.html",
        "task_type": "image_classification",
        "modalities": ["image"],
        "metadata_standard": "custom",
        "description": "10/100 类小尺寸自然图像分类基准数据集",
    },
    {
        "dataset_name": "COCO (Common Objects in Context)",
        "source": "cocodataset.org",
        "license": "CC-BY 4.0",
        "url": "https://cocodataset.org/",
        "task_type": "object_detection",
        "modalities": ["image"],
        "metadata_standard": "COCO JSON",
        "description": "通用物体检测、分割、字幕数据集",
    },
    {
        "dataset_name": "MNIST",
        "source": "Yann LeCun",
        "license": "CC BY-SA 3.0",
        "url": "http://yann.lecun.com/exdb/mnist/",
        "task_type": "image_classification",
        "modalities": ["image"],
        "metadata_standard": "IDX",
        "description": "手写数字识别基准数据集，28x28 灰度图",
    },
    {
        "dataset_name": "SQuAD",
        "source": "Stanford",
        "license": "CC BY-SA 4.0",
        "url": "https://rajpurkar.github.io/SQuAD-explorer/",
        "task_type": "question_answering",
        "modalities": ["text"],
        "metadata_standard": "JSON",
        "description": "阅读理解 / 问答基准数据集",
    },
    {
        "dataset_name": "GLUE / SuperGLUE",
        "source": "gluebenchmark.com",
        "license": "various",
        "url": "https://gluebenchmark.com/",
        "task_type": "nlp_benchmark",
        "modalities": ["text"],
        "metadata_standard": "TSV/JSON",
        "description": "自然语言理解多任务基准",
    },
]

TASK_TYPE_KEYWORDS = {
    "drug_discovery": [
        "药物", "drug", "nanorobot", "nanomedicine", "纳米", "靶向", "targeted delivery",
        "drug delivery", "载药", "chembl", "pubchem", "化合物",
    ],
    "research_data": [
        "科研数据", "research data", "zenodo", "开放数据",
    ],
    "image_classification": [
        "图像分类", "image classification", "图片分类", "物体识别",
    ],
    "object_detection": [
        "目标检测", "object detection", "物体检测",
    ],
    "text_mining": [
        "文本挖掘", "文献挖掘", "text mining", "literature mining", "PubMed",
    ],
    "question_answering": [
        "问答", "question answering", "阅读理解", "QA",
    ],
    "nlp_benchmark": [
        "自然语言理解", "NLP", "language understanding", "文本分类",
    ],
    "classification/regression": [
        "分类", "回归", "classification", "regression", "预测", "prediction",
    ],
    "clinical_prediction": [
        "临床", "clinical", "诊疗", "MIMIC", "电子病历", "EHR",
    ],
    "gene_expression_analysis": [
        "基因表达", "gene expression", "转录组", "transcriptomics", "GEO",
    ],
    "genomic_analysis": [
        "基因组", "genomics", "突变", "mutation", "TCGA", "癌症", "cancer",
    ],
    "structure_prediction": [
        "蛋白质结构", "protein structure", "PDB", "structure prediction", "分子",
    ],
    "various": [
        "Kaggle", "OpenML", "Hugging Face", "huggingface",
    ],
}

# 查询含以下词时，排除纯计算机视觉基准数据集
_CV_ONLY_DATASETS = frozenset({
    "ImageNet", "CIFAR-10 / CIFAR-100", "COCO (Common Objects in Context)", "MNIST",
})

_BIOMED_QUERY_HINTS = (
    "纳米", "nanorobot", "nanomedicine", "药物", "drug", "靶向", "delivery",
    "生物", "bio", "medical", "clinical", "cancer", "蛋白", "protein", "基因",
)

_BIOMED_FALLBACK_NAMES = (
    "PubMed / PubMed Central", "GEO (Gene Expression Omnibus)", "ChEMBL",
    "PubChem BioAssay", "Zenodo", "Hugging Face Datasets", "UCI Machine Learning Repository",
)


def _is_biomed_query(query_terms: List[str]) -> bool:
    blob = " ".join(query_terms).lower()
    return any(h in blob for h in _BIOMED_QUERY_HINTS)


def _should_exclude_dataset(ds: Dict[str, Any], query_terms: List[str]) -> bool:
    if not _is_biomed_query(query_terms):
        return False
    name = ds.get("dataset_name", "")
    if name in _CV_ONLY_DATASETS:
        return True
    modalities = set(ds.get("modalities") or [])
    if modalities == {"image"} and ds.get("task_type") in (
        "image_classification", "object_detection",
    ):
        return True
    return False


class DatasetDiscoverySkill(BaseSkill):
    """公开数据集发现 Skill

    输入:
      - research_question: str        研究问题
      - keywords: List[str]           额外关键词
      - task_type: str                期望的任务类型
      - modality_filter: List[str]    模态过滤: tabular / image / text / time_series / genomics
      - max_results: int = 10         最大返回数

    输出 (SkillResult.data):
      - datasets: List[dict]          推荐数据集列表
      - total: int                    匹配数量
      - matched_keywords: List[str]   匹配到的关键词
      - search_source: str            数据来源: local_knowledge / hf_api
    """

    name = "DatasetDiscovery"
    description = "根据研究问题推荐公开数据集（Hugging Face / OpenML / Croissant 元数据）"
    source_reference = "Hugging Face datasets; OpenML; Croissant metadata — 数据集发现能力参考"

    async def run(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> SkillResult:
        result = SkillResult(success=True)
        result.metadata = {"source_reference": self.source_reference}

        research_question = input_data.get("research_question", "")
        keywords: List[str] = input_data.get("keywords", [])
        task_type = input_data.get("task_type", "")
        modality_filter: List[str] = input_data.get("modality_filter", [])
        max_results = input_data.get("max_results", 10)

        if not isinstance(keywords, list):
            keywords = []

        query_terms = []
        if research_question:
            query_terms.append(research_question.lower())
        query_terms.extend(k.lower() for k in keywords if isinstance(k, str) and k.strip())

        if not query_terms:
            result.add_warning("缺少搜索关键词，返回生物医学与通用科研数据平台推荐")
            entry = {
                "datasets": [ds for ds in KNOWN_DATASETS if ds["dataset_name"] in _BIOMED_FALLBACK_NAMES][:max_results],
                "total": min(len(_BIOMED_FALLBACK_NAMES), max_results),
                "matched_keywords": [],
                "search_source": "local_knowledge_biomed_default",
            }
            result.data = entry
            return result

        is_biomed = _is_biomed_query(query_terms)
        matched_keywords: set = set()
        scored_datasets: List[tuple] = []

        for ds in KNOWN_DATASETS:
            if _should_exclude_dataset(ds, query_terms):
                continue
            score = 0
            ds_text = (
                f"{ds['dataset_name']} {ds.get('description', '')} "
                f"{ds.get('task_type', '')} {ds.get('source', '')} "
                f"{' '.join(ds.get('modalities', []))}"
            ).lower()

            for term in query_terms:
                if term in ds_text:
                    score += 3
                    matched_keywords.add(term)
                else:
                    for word in term.split():
                        if len(word) >= 3 and word in ds_text:
                            score += 1
                            matched_keywords.add(word)

            if task_type:
                ds_task_lower = ds.get("task_type", "").lower()
                if ds_task_lower == task_type.lower():
                    score += 5
                elif any(t in ds_task_lower for t in task_type.lower().split("_")):
                    score += 2

            if modality_filter:
                ds_modalities = set(ds.get("modalities", []))
                filter_set = set(m.lower() for m in modality_filter)
                overlap = ds_modalities & filter_set
                score += len(overlap) * 2

            if score > 0:
                scored_datasets.append((score, ds))

        scored_datasets.sort(key=lambda x: -x[0])

        top_datasets = [ds for _, ds in scored_datasets[:max_results]]

        if not top_datasets:
            if is_biomed:
                top_datasets = [
                    ds for ds in KNOWN_DATASETS
                    if ds["dataset_name"] in _BIOMED_FALLBACK_NAMES
                ][:max_results]
                result.add_warning("未找到精确匹配的数据集，已改为推荐生物医学/开放科研数据平台")
            else:
                top_datasets = KNOWN_DATASETS[:max_results]
                result.add_warning("未找到精确匹配的数据集，返回通用推荐")

        online_results = await self._try_huggingface_search(query_terms, max_results)

        result.data = {
            "datasets": top_datasets,
            "total": len(top_datasets),
            "matched_keywords": sorted(matched_keywords),
            "search_source": "local_knowledge",
            "hf_preview": {
                "available": online_results is not None,
                "count": len(online_results) if online_results else 0,
                "items": (online_results or [])[:5],
            },
        }

        if online_results is None:
            result.add_warning("Hugging Face API 不可达，仅返回本地数据集知识库")

        return result

    async def _try_huggingface_search(
        self, query_terms: List[str], max_results: int
    ) -> Optional[List[dict]]:
        query = " ".join(query_terms[:3])
        params = urllib.parse.urlencode({
            "search": query,
            "limit": min(max_results, 20),
            "full": "false",
        })
        url = f"https://huggingface.co/api/datasets?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AISci/1.0 (mailto:dev@aiscilab.org)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            logger.warning(f"Hugging Face API 不可达: {e}")
            return None

        results = []
        for item in (data if isinstance(data, list) else data.get("datasets", []))[:max_results]:
            results.append({
                "dataset_name": item.get("id") or item.get("name", ""),
                "source": "huggingface",
                "license": item.get("license", "") or item.get("cardData", {}).get("license", ""),
                "url": f"https://huggingface.co/datasets/{item.get('id', '')}",
                "task_type": "",
                "modalities": item.get("modalities", []),
                "metadata_standard": "Croissant",
            })
        return results