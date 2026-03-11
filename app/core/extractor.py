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

【字段提取规则】

■ 项目名称
  文件标题或政策项目的完整名称。

■ 政策依据
  引用的上位法规、文件编号或政策来源。

■ 归口部门
  负责受理或主管的政府部门/机构名称。

■ 联系人
  文件中列出的联系人姓名及联系方式（电话、邮箱等），完整保留。

■ 申报时间
  申报/报名的起止时间或截止日期。

■ 支持方向（对应「支持方向列表」数组的每个元素）
  文件中"评审范围""支持范围"等章节所列的独立方向/类别，\
  一个独立方向对应数组中的一个元素；若文件无明确分方向则整体作为一个元素。

■ 特定方向要求（每个支持方向专属）
  仅针对该方向的特殊门槛、限定条件或差异化要求，\
  与其他方向共用的通用要求不填入此字段。

■ 申报要求
  文件中"申报条件""申请条件""基本条件""具体要求""认定条件""参评条件"\
  "申报资格""评价要求""申请对象""资助对象""选树条件"\
  "一般规定""特别规定""认定标准"等章节的内容。\
  条目化输出，格式：1. xxx 2. xxx 3. xxx

■ 优惠政策
  文件中"支持内容""支持方式""支持标准""资助内容""资助额度"\
  "经费保障""奖励办法""奖项"等章节的奖励金额、扶持比例或具体支持手段。

■ 申报材料
  文件中"报送材料""证明材料""附件"等章节列出的需提交材料清单，精简列举。

■ 申报方式
  申报的具体流程说明，包括线上/线下提交步骤、联系地址等文字描述。\
  不要将 URL 填入此字段。

■ 网站链接
  文件中明确出现的官方申报/受理网站完整 URL（以 http:// 或 https:// 开头的原文链接）。\
  若文件中未出现任何 URL，填"/"。\
  不要填写申报流程说明文字，只填 URL 本身。

■ 政策有效期
  明确的截止或失效时间；无则填"/"。

【通用规则】
1. 所有字段必须有值，确实无法从文件中提取的字段填"/"，不允许留空或 null。
2. 「支持方向列表」是数组：文件中有几个独立支持方向就输出几个元素，无明确分向则输出 1 个元素。
3. 同一字段内容若同时含通用部分与方向专属部分，\
   通用部分填入「申报要求」，专属部分填入「特定方向要求」。
4. 「申报要求」必须条目化，格式：1. xxx 2. xxx 3. xxx。

【输出 JSON 结构】
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
