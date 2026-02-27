from pydantic import BaseModel, field_validator


class SupportItem(BaseModel):
    """对应一个「支持方向」的 8 个字段（字段 6-13）。"""

    支持方向: str = "/"
    特定方向要求: str = "/"
    申报要求: str = "/"
    优惠政策: str = "/"
    申报材料: str = "/"
    申报方式: str = "/"
    网站链接: str = "/"
    政策有效期: str = "/"


class PolicyResponse(BaseModel):
    """LLM 返回的完整结构。支持方向列表为数组，每项拆为 Excel 一行。"""

    项目名称: str = "/"
    政策依据: str = "/"
    归口部门: str = "/"
    联系人: str = "/"
    申报时间: str = "/"
    支持方向列表: list[SupportItem]

    @field_validator("支持方向列表", mode="before")
    @classmethod
    def ensure_non_empty(cls, v: list) -> list:
        if not v:
            return [SupportItem()]
        return v

    def to_rows(self) -> list["PolicyRow"]:
        """将多个支持方向展开为多行，前 5 个公共字段在每行重复。"""
        return [
            PolicyRow(
                项目名称=self.项目名称,
                政策依据=self.政策依据,
                归口部门=self.归口部门,
                联系人=self.联系人,
                申报时间=self.申报时间,
                **item.model_dump(),
            )
            for item in self.支持方向列表
        ]


class PolicyRow(BaseModel):
    """13 个字段的扁平行，对应 MySQL 一行 / Excel 一行。"""

    项目名称: str
    政策依据: str
    归口部门: str
    联系人: str
    申报时间: str
    支持方向: str
    特定方向要求: str
    申报要求: str
    优惠政策: str
    申报材料: str
    申报方式: str
    网站链接: str
    政策有效期: str
