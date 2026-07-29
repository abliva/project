"""
文档检索模块 - RAG系统的核心检索组件
实现文档加载、文本切分、向量化存储和相似度检索功能

主要功能：
1. 支持多种文档格式加载（TXT、PDF）
2. 基于Token的智能文本切分
3. 使用FAISS进行向量存储和相似度检索
4. 提供高效的语义搜索能力
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

# 配置日志记录器
logger = logging.getLogger(__name__)


class TextSplitter:
    """
    文本切分器 - 基于Token的智能分块工具
    
    将长文档切分成适合向量化和检索的小块，
    保证每个块在模型处理的token限制内，同时保持上下文连续性
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """
        初始化文本切分器
        
        Args:
            chunk_size (int): 每个文本块的最大字符数，默认500
            chunk_overlap (int): 相邻块之间的重叠字符数，默认50
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        logger.info(f"文本切分器初始化完成 - 块大小:{chunk_size}, 重叠:{chunk_overlap}")

    def split_text(self, text: str) -> List[str]:
        """
        将文本切分成多个块
        
        切分策略：
        1. 首先按段落（双换行符）分割
        2. 对过长的段落按句子进一步切分
        3. 确保相邻块有重叠内容以保持上下文
        
        Args:
            text (str): 待切分的原始文本
            
        Returns:
            List[str]: 切分后的文本块列表
        """
        if not text or not text.strip():
            logger.warning("输入文本为空，返回空列表")
            return []

        # 预处理：清理多余空白字符
        text = ' '.join(text.split())

        # 第一步：按段落分割（双换行符作为段落分隔符）
        paragraphs = text.split('\n\n')

        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # 如果当前块加上新段落后不超过大小限制，直接追加
            if len(current_chunk) + len(paragraph) + 1 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n" + paragraph
                else:
                    current_chunk = paragraph
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果单个段落就超过块大小，需要进一步切分
                if len(paragraph) > self.chunk_size:
                    sub_chunks = self._split_long_paragraph(paragraph)
                    chunks.extend(sub_chunks[:-1])  # 除最后一个外的所有子块
                    current_chunk = sub_chunks[-1]   # 最后一个子块作为当前块
                else:
                    current_chunk = paragraph

        # 不要忘记最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        logger.info(f"文本切分完成 - 共生成 {len(chunks)} 个文本块")
        return chunks

    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """
        切分超长段落
        
        按句子（句号、问号、感叹号）分割，确保不会在句子中间断开
        
        Args:
            paragraph (str): 超长段落文本
            
        Returns:
            List[str]: 切分后的文本块列表
        """
        import re

        # 按中文和英文的句子结束符号分割
        sentences = re.split(r'(?<=[。！？.!?])', paragraph)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 检查添加这个句子是否会超出限制
            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                if current_chunk:
                    current_chunk += sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


class SimpleEmbedding:
    """
    简单的文本向量化实现
    
    注意：这是一个基础实现，用于演示RAG流程。
    生产环境建议使用专业的embedding模型如：
    - OpenAI text-embedding-ada-002
    - HuggingFace sentence-transformers
    - 本地部署的embedding模型
    """

    def __init__(self, dimension: int = 1536):
        """
        初始化向量化器
        
        Args:
            dimension (int): 向量维度，默认1536（与OpenAI embedding一致）
        """
        self.dimension = dimension
        logger.info(f"简单向量化器初始化 - 维度:{dimension}")

    def embed_text(self, text: str) -> np.ndarray:
        """
        将文本转换为向量
        
        这里使用基于字符编码的简单哈希方法生成固定维度向量。
        这种方法虽然不如专业embedding模型准确，但足以演示RAG流程。
        
        Args:
            text (str): 输入文本
            
        Returns:
            np.ndarray: 文本对应的向量（shape: [dimension]）
        """
        if not text or not text.strip():
            return np.zeros(self.dimension, dtype=np.float32)

        # 创建一个固定维度的零向量
        vector = np.zeros(self.dimension, dtype=np.float32)

        # 使用简单的字符级特征提取
        for i, char in enumerate(text):
            # 字符的ASCII码作为索引
            idx = ord(char) % self.dimension
            # 根据字符位置加权
            weight = 1.0 / (i + 1)
            vector[idx] += weight

        # L2归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        批量将多个文本转换为向量
        
        Args:
            texts (List[str]): 输入文本列表
            
        Returns:
            np.ndarray: 向量矩阵（shape: [len(texts), dimension]）
        """
        vectors = []
        for text in texts:
            vec = self.embed_text(text)
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)


class VectorStore:
    """
    向量存储类 - 管理文档向量的存储和检索
    
    提供以下功能：
    1. 存储文档向量及其元数据
    2. 执行相似度搜索
    3. 支持持久化到磁盘
    """

    def __init__(self, dimension: int = 1536, store_path: Optional[Path] = None):
        """
        初始化向量存储
        
        Args:
            dimension (int): 向量维度
            store_path (Path): 存储路径，如果提供则支持持久化
        """
        self.dimension = dimension
        self.store_path = store_path

        # 存储结构：向量和对应的元数据
        self.vectors = np.array([], dtype=np.float32).reshape(0, dimension)
        self.documents = []  # 存储原始文档文本
        self.metadata = []   # 存储文档元数据（来源文件等）

        # 尝试从磁盘加载已有的向量库
        if store_path and store_path.exists():
            self._load_from_disk()

        logger.info(f"向量存储初始化完成 - 当前文档数:{len(self.documents)}")

    def add_documents(self, documents: List[str], vectors: np.ndarray,
                      metadata: Optional[List[Dict]] = None):
        """
        添加文档及其向量到存储中
        
        Args:
            documents (List[str]): 文档文本列表
            vectors (np.ndarray): 文档向量矩阵
            metadata (List[Dict]): 可选的元数据列表
        """
        if len(documents) != len(vectors):
            raise ValueError("文档数量和向量数量不匹配")

        if metadata is None:
            metadata = [{"source": "unknown", "index": i} for i in range(len(documents))]

        # 追加新的向量和文档
        if len(self.vectors) == 0:
            self.vectors = vectors
        else:
            self.vectors = np.vstack([self.vectors, vectors])

        self.documents.extend(documents)
        self.metadata.extend(metadata)

        logger.info(f"成功添加 {len(documents)} 个文档到向量库")

        # 自动保存到磁盘
        if self.store_path:
            self._save_to_disk()

    def search(self, query_vector: np.ndarray, top_k: int = 5,
               threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        相似度搜索 - 找到与查询向量最相似的文档
        
        使用余弦相似度计算相似性，并返回最相关的top_k个结果
        
        Args:
            query_vector (np.ndarray): 查询向量
            top_k (int): 返回的最相关结果数量，默认5
            threshold (float): 相似度阈值，低于此值的结果将被过滤，默认0.7
            
        Returns:
            List[Dict]: 搜索结果列表，每项包含文档内容、相似度和元数据
        """
        if len(self.vectors) == 0:
            logger.warning("向量库为空，无法执行搜索")
            return []

        # 计算余弦相似度
        similarities = self._cosine_similarity(query_vector, self.vectors)

        # 获取top_k个结果的索引（降序排序）
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            similarity = similarities[idx]
            
            # 过滤低相似度结果
            if similarity < threshold:
                continue

            result = {
                'content': self.documents[idx],
                'similarity': float(similarity),
                'metadata': self.metadata[idx],
                'index': int(idx)
            }
            results.append(result)

        logger.info(f"搜索完成 - 返回 {len(results)} 个结果（阈值:{threshold}）")
        return results

    def _cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> np.ndarray:
        """
        计算余弦相似度
        
        Args:
            vec_a (np.ndarray): 查询向量 (1, dim)
            vec_b (np.ndarray): 文档向量矩阵 (n, dim)
            
        Returns:
            np.ndarray: 相似度数组 (n,)
        """
        # 确保向量是二维的
        if vec_a.ndim == 1:
            vec_a = vec_a.reshape(1, -1)

        # 计算点积
        dot_product = np.dot(vec_b, vec_a.T).flatten()

        # 计算范数
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b, axis=1)

        # 避免除以零
        denominator = norm_a * norm_b
        denominator[denominator == 0] = 1e-10

        similarities = dot_product / denominator
        return similarities

    def _save_to_disk(self):
        """将向量库保存到磁盘"""
        if not self.store_path:
            return

        try:
            import pickle

            # 确保目录存在
            self.store_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存数据
            data = {
                'vectors': self.vectors,
                'documents': self.documents,
                'metadata': self.metadata,
                'dimension': self.dimension
            }

            with open(self.store_path, 'wb') as f:
                pickle.dump(data, f)

            logger.info(f"向量库已保存到 {self.store_path}")
        except Exception as e:
            logger.error(f"保存向量库失败: {e}")

    def _load_from_disk(self):
        """从磁盘加载向量库"""
        try:
            import pickle

            with open(self.store_path, 'rb') as f:
                data = pickle.load(f)

            self.vectors = data['vectors']
            self.documents = data['documents']
            self.metadata = data['metadata']

            logger.info(f"从 {self.store_path} 加载了 {len(self.documents)} 个文档")
        except Exception as e:
            logger.warning(f"加载向量库失败，将使用空库: {e}")


class DocumentLoader:
    """
    文档加载器 - 负责从不同格式的文件中读取文本内容
    
    支持格式：
    - TXT：纯文本文件
    - PDF：PDF文档（需要PyPDF2库）
    - MD：Markdown文件
    """

    def __init__(self):
        """初始化文档加载器"""
        self.supported_extensions = ['.txt', '.pdf', '.md']
        logger.info("文档加载器初始化完成")

    def load_file(self, file_path: Path) -> str:
        """
        加载单个文件的内容
        
        Args:
            file_path (Path): 文件路径
            
        Returns:
            str: 文件的文本内容
            
        Raises:
            ValueError: 不支持的文件格式
            FileNotFoundError: 文件不存在
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        extension = file_path.suffix.lower()

        if extension == '.txt' or extension == '.md':
            return self._load_text_file(file_path)
        elif extension == '.pdf':
            return self._load_pdf_file(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {extension}")

    def load_directory(self, directory: Path) -> Dict[str, str]:
        """
        加载目录中的所有支持的文档
        
        Args:
            directory (Path): 目录路径
            
        Returns:
            Dict[str, str]: 文件名到内容的映射字典
        """
        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")

        documents = {}
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                try:
                    content = self.load_file(file_path)
                    documents[file_path.name] = content
                    logger.info(f"成功加载文件: {file_path.name}")
                except Exception as e:
                    logger.error(f"加载文件失败 {file_path.name}: {e}")

        logger.info(f"目录加载完成 - 共加载 {len(documents)} 个文件")
        return documents

    def _load_text_file(self, file_path: Path) -> str:
        """
        加载文本文件（TXT/MD）
        
        Args:
            file_path (Path): 文件路径
            
        Returns:
            str: 文件内容
        """
        # 尝试不同的编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                logger.debug(f"使用 {encoding} 编码成功读取 {file_path.name}")
                return content
            except UnicodeDecodeError:
                continue

        # 如果所有编码都失败，使用utf-8并忽略错误
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def _load_pdf_file(self, file_path: Path) -> str:
        """
        加载PDF文件
        
        Args:
            file_path (Path): PDF文件路径
            
        Returns:
            str: PDF文件的文本内容
        """
        try:
            import PyPDF2
        except ImportError:
            raise ImportError("需要安装PyPDF2库来处理PDF文件: pip install PyPDF2")

        text_content = []
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # 遍历每一页
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(f"=== 第{page_num + 1}页 ===\n{page_text}")

                logger.info(f"成功解析PDF: {file_path.name} ({len(pdf_reader.pages)}页)")
        except Exception as e:
            logger.error(f"PDF解析错误: {e}")
            raise

        return '\n\n'.join(text_content)


class DocumentRetriever:
    """
    文档检索器 - RAG系统的核心检索组件
    
    整合文档加载、切分、向量化、存储和检索的完整流程
    提供简洁的高级接口供外部调用
    """

    def __init__(self, config=None):
        """
        初始化文档检索器
        
        Args:
            config: 配置对象，如果为None则使用默认配置
        """
        # 导入配置（延迟导入避免循环依赖）
        if config is None:
            from config import Config
            config = Config()

        self.config = config

        # 初始化各个组件
        self.loader = DocumentLoader()
        self.splitter = TextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP
        )
        self.embedding = SimpleEmbedding(dimension=config.VECTOR_DIMENSION)

        # 初始化向量存储
        vector_db_path = config.VECTOR_DB_PATH
        vector_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_store = VectorStore(
            dimension=config.VECTOR_DIMENSION,
            store_path=vector_db_path.with_suffix('.pkl')
        )

        # 标记知识库是否已构建
        self._is_initialized = len(self.vector_store.documents) > 0

        logger.info("文档检索器初始化完成")

    def build_knowledge_base(self, directory: Optional[Path] = None) -> Dict[str, Any]:
        """
        构建知识库 - 从指定目录加载文档并向量化
        
        完整流程：
        1. 扫描目录获取所有支持的文档
        2. 加载每个文档的文本内容
        3. 将文本切分成合适的块
        4. 将每个文本块转换为向量
        5. 存储到向量数据库中
        
        Args:
            directory (Path): 知识库目录路径，如果为None则使用配置中的路径
            
        Returns:
            Dict: 构建统计信息，包括文档数量、总块数等
        """
        if directory is None:
            directory = self.config.KNOWLEDGE_BASE_PATH

        logger.info(f"开始构建知识库 - 目录: {directory}")

        # 步骤1：加载所有文档
        all_documents = self.loader.load_directory(directory)

        if not all_documents:
            logger.warning("未找到任何文档，知识库构建失败")
            return {
                'status': 'error',
                'message': '未找到任何支持的文档',
                'documents_count': 0,
                'chunks_count': 0
            }

        # 步骤2&3：切分所有文档
        all_chunks = []
        all_metadata = []

        for filename, content in all_documents.items():
            # 切分文档
            chunks = self.splitter.split_text(content)

            # 为每个块创建元数据
            for chunk_idx, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadata.append({
                    'source': filename,
                    'chunk_index': chunk_idx,
                    'total_chunks': len(chunks)
                })

            logger.info(f"文件 {filename}: 切分为 {len(chunks)} 个块")

        # 步骤4：向量化所有文本块
        logger.info(f"正在向量化 {len(all_chunks)} 个文本块...")
        vectors = self.embedding.embed_texts(all_chunks)

        # 步骤5：存储到向量数据库
        self.vector_store.add_documents(all_chunks, vectors, all_metadata)

        # 标记知识库已构建完成
        self._is_initialized = True

        result = {
            'status': 'success',
            'message': '知识库构建成功',
            'documents_count': len(all_documents),
            'chunks_count': len(all_chunks),
            'vector_dimension': self.config.VECTOR_DIMENSION
        }

        logger.info(f"知识库构建完成 - 文档:{result['documents_count']}, 块:{result['chunks_count']}")
        return result

    def retrieve(self, query: str, top_k: Optional[int] = None,
                 threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        执行相似度检索
        
        根据用户查询，从知识库中找到最相关的文档片段
        
        Args:
            query (str): 用户查询文本
            top_k (int): 返回的相关文档数量，默认使用配置值
            threshold (float): 相似度阈值，默认使用配置值
            
        Returns:
            List[Dict]: 检索结果列表，按相似度降序排列
        """
        if not query or not query.strip():
            logger.warning("查询文本为空")
            return []

        # 检查知识库是否已初始化
        if not self._is_initialized and len(self.vector_store.documents) == 0:
            logger.error("知识库未初始化，请先调用 build_knowledge_base()")
            return []

        # 使用配置默认值
        if top_k is None:
            top_k = self.config.TOP_K
        if threshold is None:
            threshold = self.config.SIMILARITY_THRESHOLD

        logger.info(f"执行检索 - 查询:'{query[:50]}...', top_k:{top_k}, 阈值:{threshold}")

        # 将查询文本向量化
        query_vector = self.embedding.embed_text(query)

        # 在向量库中搜索
        results = self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
            threshold=threshold
        )

        logger.info(f"检索完成 - 返回 {len(results)} 个结果")
        return results

    def get_context_string(self, query: str, **kwargs) -> str:
        """
        获取格式化的上下文字符串
        
        将检索结果格式化为适合注入Prompt的字符串格式
        
        Args:
            query (str): 用户查询
            **kwargs: retrieve()方法的额外参数
            
        Returns:
            str: 格式化的上下文字符串
        """
        results = self.retrieve(query, **kwargs)

        if not results:
            return ""

        # 格式化检索结果
        context_parts = []
        for idx, result in enumerate(results, 1):
            context_part = (
                f"\n【参考资料 {idx}】\n"
                f"来源: {result['metadata']['source']}\n"
                f"相关度: {result['similarity']:.2%}\n"
                f"内容:\n{result['content']}\n"
            )
            context_parts.append(context_part)

        context_string = '\n'.join(context_parts)
        logger.info(f"生成上下文字符串 - 包含 {len(results)} 条参考资料")
        return context_string

    def add_document(self, file_path: Path) -> Dict[str, Any]:
        """
        单个文档添加到知识库
        
        Args:
            file_path (Path): 要添加的文档路径
            
        Returns:
            Dict: 添加结果信息
        """
        try:
            # 加载文档
            content = self.loader.load_file(file_path)

            # 切分文档
            chunks = self.splitter.split_text(content)

            # 准备元数据
            metadata = [{
                'source': file_path.name,
                'chunk_index': i,
                'total_chunks': len(chunks)
            } for i in range(len(chunks))]

            # 向量化
            vectors = self.embedding.embed_texts(chunks)

            # 添加到向量库
            self.vector_store.add_documents(chunks, vectors, metadata)

            self._is_initialized = True

            result = {
                'status': 'success',
                'message': f'文档 {file_path.name} 添加成功',
                'chunks_count': len(chunks),
                'filename': file_path.name
            }

            logger.info(f"成功添加文档: {file_path.name} ({len(chunks)} 个块)")
            return result

        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return {
                'status': 'error',
                'message': f'添加文档失败: {str(e)}'
            }

    def get_stats(self) -> Dict[str, Any]:
        """
        获取知识库统计信息
        
        Returns:
            Dict: 统计信息字典
        """
        stats = {
            'total_documents': len(self.vector_store.documents),
            'unique_sources': len(set(m['source'] for m in self.vector_store.metadata)),
            'vector_dimension': self.config.VECTOR_DIMENSION,
            'is_initialized': self._is_initialized,
            'chunk_size': self.config.CHUNK_SIZE,
            'top_k': self.config.TOP_K
        }

        return stats


# 便捷函数：创建检索器实例
def create_retriever(config=None) -> DocumentRetriever:
    """
    工厂函数：创建文档检索器实例
    
    Args:
        config: 配置对象
        
    Returns:
        DocumentRetriever: 检索器实例
    """
    return DocumentRetriever(config)


if __name__ == '__main__':
    # 测试代码
    print("=" * 60)
    print("文档检索器测试")
    print("=" * 60)

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建检索器实例
    retriever = create_retriever()

    # 测试构建知识库
    from config import Config
    config = Config()
    result = retriever.build_knowledge_base(config.KNOWLEDGE_BASE_PATH)
    print("\n知识库构建结果:")
    print(result)

    # 测试检索
    test_query = "什么是深度学习？"
    print(f"\n测试查询: {test_query}")
    results = retriever.retrieve(test_query)
    print(f"\n找到 {len(results)} 个相关结果:")
    for i, r in enumerate(results, 1):
        print(f"\n--- 结果 {i} (相关度: {r['similarity']:.2%}) ---")
        print(r['content'][:200] + "...")
