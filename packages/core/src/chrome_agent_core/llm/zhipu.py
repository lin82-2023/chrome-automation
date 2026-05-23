"""智谱 GLM LLM Provider（OpenAI 兼容）"""
from __future__ import annotations

from .openai_compat import OpenAICompatLLM


class ZhipuLLM(OpenAICompatLLM):
    """智谱 AI BigModel 开放平台

    环境变量：``ZHIPU_API_KEY``
    支持模型：glm-4-plus / glm-4 / glm-4-flash / glm-4v 等。
    """

    provider_name = "zhipu"
    default_base_url = "https://open.bigmodel.cn/api/paas/v4"
    default_model = "glm-4-flash"
    env_var = "ZHIPU_API_KEY"


__all__ = ["ZhipuLLM"]
