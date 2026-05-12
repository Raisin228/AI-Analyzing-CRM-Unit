"""Возможные состояния для LLM Graph. Атрошенко Б. С."""

from pydantic import BaseModel, Field


class CategoryItem(BaseModel):
    """Категория к которой отнесли к отзыв."""

    name: str = Field(description="Найминг категории")
    is_issue: bool = Field(description="Выписан ли тикет на эту категорию")


class ReviewState(BaseModel):
    """Состояние обаботанности отзыва."""

    external_id: str = Field(
        description="Внешний Id отзыва, используемый внутри CRMки", default="ab2f83d4-bb41-42c1-9049-f388a75e8b03"
    )
    text: str = Field(description="Текстовка самого отзыва")
    rating: int = Field(description="Кол-во звёзд")
    customer_name: str = Field("ФИО покупателя")
    product_id: str = Field(description="Idшник товара в CRM")
    created_at: str = Field(description="Дата создания отзыва")
    # [{"name": "courier", "is_issue": True}, ...]
    categories: list[CategoryItem] = Field(description="Список с подкатегориями, к которым отнесли этот отзыв")
    sentiment: str = Field(description="Настроение, к которой отнесли этот отзыв")
    confidence: float = Field(description="Уверенность в решении")
    mismatch: bool = Field(description="Есть ли несоответствие в текстовке и рейтинге")
    review_db_id: int | None = Field(description="Id в БД")
