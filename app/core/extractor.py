import logging

from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.models.policy import PolicyResponse, PolicyRow

logger = logging.getLogger(__name__)

# 模块级单例，避免重复初始化
_llm = ChatOpenAI(
    model=settings.deepseek_model,
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_api_base,
    timeout=120,       # 单次请求最长等待 120 秒
    max_retries=0,     # 禁用 httpx 内部重试，由外层逻辑统一管理
    max_tokens=128000,   # DeepSeek 最大输出 8192 tokens，避免 JSON 被截断
)
# DeepSeek 使用 json_mode 比 function_calling 更稳定
_chain = _llm.with_structured_output(PolicyResponse, method="json_mode")

SYSTEM_PROMPT = """\
你是一个政策文件信息提取助手。请从用户提供的政策文件文本中提取结构化信息，\
以合法的 JSON 格式输出，不要输出任何其他内容。

规则：
1. 所有字段必须有值，确实无法提取的字段填"/"，不允许留空。
2. 「支持方向列表」必须是数组：文件中有几个独立的支持方向，就输出几个元素。
3. 每个支持方向的「特定方向要求」「申报要求」等字段，只填写该方向专属的内容。
4. 「申报要求」条目化输出，格式：1. xxx 2. xxx 3. xxx
5. 「政策有效期」如无明确截止日期则填"/"。

输出 JSON 结构：
{
  "项目名称": "...",
  "政策依据": "...",
  "归口部门": "...",
  "联系人": "...",
  "申报时间": "...",
  "支持方向列表": [
    {
      "支持方向": "...",
      "特定方向要求": "...",
      "申报要求": "...",
      "优惠政策": "...",
      "申报材料": "...",
      "申报方式": "...",
      "网站链接": "...",
      "政策有效期": "..."
    }
  ]
}
"""


def extract(text: str) -> list[PolicyRow]:
    """
    调用 DeepSeek 提取政策信息，返回按支持方向拆分的行列表。
    JSON 解析失败时最多重试 3 次，仍失败则抛出异常。

    注意：当前不对超长文本做分块处理，若文本超过模型 context window
    会直接报错，调用方应将 task 置为 error 状态并记录日志。
    """
    last_exc: Exception = RuntimeError("Unknown extraction error")

    logger.info("LLM 提取开始，文本长度 %d 字符", len(text))
    for attempt in range(3):
        try:
            logger.info("LLM 调用第 %d 次", attempt + 1)
            response: PolicyResponse = _chain.invoke(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ]
            )
            if response is None:
                raise ValueError("LLM 返回 None，JSON 解析失败，请检查模型输出格式")
            logger.info("LLM 调用成功，提取到 %d 个支持方向", len(response.支持方向列表))
            return response.to_rows()
        except Exception as e:
            last_exc = e
            logger.warning("LLM 调用第 %d 次失败: %s", attempt + 1, e)
            if attempt < 2:
                continue

    raise last_exc
