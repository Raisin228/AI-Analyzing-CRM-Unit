"""Фабрика по производству мокированых объектов отзывов. Атрошенко Б. С."""

import uuid
import random
from datetime import datetime, timedelta, timezone

from faker import Faker

from .models import OrgUnit, Product, Review

fake = Faker("ru_RU")
random.seed(42)

PRODUCTS = [
    Product(id=uuid.uuid4(), name="Смартфон Galaxy S24", category="Электроника"),
    Product(id=uuid.uuid4(), name="Ноутбук ThinkPad X1", category="Электроника"),
    Product(id=uuid.uuid4(), name="Кроссовки Nike Air", category="Обувь"),
    Product(id=uuid.uuid4(), name="Рюкзак туристический", category="Спорт"),
    Product(id=uuid.uuid4(), name="Кофемашина Delonghi", category="Бытовая техника"),
]

ORG_UNITS = [
    OrgUnit(id=uuid.uuid4(), name="Отдел продаж", responsible_email="sales@company.ru"),
    OrgUnit(id=uuid.uuid4(), name="Служба поддержки", responsible_email="support@company.ru"),
    OrgUnit(id=uuid.uuid4(), name="Отдел логистики", responsible_email="logistics@company.ru"),
]

_NEGATIVE_DELIVERY = [
    "Доставка заняла две недели, курьер позвонил за 5 минут до прибытия. Ужасный сервис.",
    "Привезли не то, что заказывал. Курьер грубил и отказывался принимать жалобы.",
    "Посылка пришла помятой, внутри всё разбито. Доставка полный провал.",
    "Ждал заказ 10 дней вместо обещанных 2. Никаких уведомлений не было.",
    "Курьер не позвонил, оставил посылку у двери соседей. Недопустимо.",
    "Службой доставки недоволен — опоздание на 3 дня без объяснений.",
]

_NEGATIVE_QUALITY = [
    "Товар пришёл бракованный, сразу сломался при первом использовании.",
    "Качество ужасное, не соответствует фото на сайте. Похоже на подделку.",
    "Через неделю использования начали расходиться швы. Очень разочарован.",
    "Экран покрылся трещинами от малейшего удара. Хрупкий товар.",
    "Не работает половина заявленных функций. Обманули при покупке.",
]

_NEGATIVE_SUPPORT = [
    "Служба поддержки не берёт трубку уже три дня. Возврат невозможен.",
    "Чат поддержки отвечает через сутки и не решает проблему.",
    "Оператор был груб и отправил меня читать FAQ вместо помощи.",
    "Обещали перезвонить — не перезвонили. Проблема до сих пор не решена.",
    "Заявку на возврат рассматривают месяц без какого-либо ответа.",
]

_NEGATIVE_APP = [
    "Приложение постоянно вылетает при оплате. Деньги списались, заказ не оформился.",
    "После обновления приложение перестало открываться. Починить не могут.",
    "Нельзя применить промокод — кнопка не работает уже неделю.",
    "Интерфейс жуткий, невозможно найти нужный раздел.",
    "Геолокация неверно определяет адрес, заказы уходят не туда.",
]

_POSITIVE = [
    "Отличный товар, полностью соответствует описанию! Доставили быстро.",
    "Очень доволен покупкой. Курьер вежливый, всё в целости и сохранности.",
    "Качество превзошло ожидания. Обязательно буду заказывать ещё.",
    "Служба поддержки помогла мгновенно. Проблему решили за 10 минут.",
    "Удобное приложение, заказ оформил за 2 минуты. Рекомендую всем.",
    "Товар пришёл раньше срока, упакован отлично. Спасибо!",
    "Прекрасное качество по разумной цене. Полностью доволен.",
    "Доставка работает на отлично — звонили заранее, подождали у двери.",
    "Рад, что выбрал этот магазин. Всё чётко и без задержек.",
]

# Собрали все негативные отзывы в кучу
_ALL_NEGATIVE = _NEGATIVE_DELIVERY + _NEGATIVE_QUALITY + _NEGATIVE_SUPPORT + _NEGATIVE_APP


class GeneratorFakeUserReviews:
    """Создатель фейковых отзывов."""

    @staticmethod
    def generate_reviews(count: int = 100) -> list[Review]:
        """
        Создание синтетических отзывов.

        :param count: кол-во отзывов.
        :return: список из отзывов.
        """

        now = datetime.now(timezone.utc)
        items: list[Review] = []

        n_neg = int(count * 0.40)  # Полностью негативных
        n_pos = int(count * 0.30)  # Полностью позитивных
        n_mis_hi = int(count * 0.20)  # Высокий рейтинг и не соответствующий текст
        n_mis_lo = count - n_neg - n_pos - n_mis_hi  # Низкий рейтинг + хороший текст

        # Всплеск жалоб за 2 дня
        for _ in range(n_neg):
            in_spike = random.random() < 0.40
            created = GeneratorFakeUserReviews._rand_time(now, 0, 2) if in_spike else (
                GeneratorFakeUserReviews._rand_time(now, 2, 14)
            )
            items.append(Review(
                id=uuid.uuid4(), customer_name=fake.name(),
                text=random.choice(_ALL_NEGATIVE),
                rating=random.randint(1, 2), created_at=created,
                product_id=random.choice(PRODUCTS).id,
            ))

        # Полностью позитивные
        items.extend(GeneratorFakeUserReviews.high_rating(n_pos, _POSITIVE))

        # Высокий рейтинг и не соответствующий текст
        items.extend(GeneratorFakeUserReviews.high_rating(n_mis_hi, _ALL_NEGATIVE))

        # Низкий рейтинг + хороший текст
        for _ in range(n_mis_lo):
            items.append(Review(
                id=uuid.uuid4(), customer_name=fake.name(),
                text=random.choice(_POSITIVE),
                rating=random.randint(1, 2),
                created_at=GeneratorFakeUserReviews._rand_time(now, 2, 14),
                product_id=random.choice(PRODUCTS).id,
            ))

        items.sort(key=lambda itm: itm.created_at)

        return items

    @staticmethod
    def high_rating(quantity: int, comment: list[str]) -> list[Review]:
        """
        Генерация отзывов с высоким рейтингом.

        :param quantity: кол-во штук.
        :param comment: отзыв на товар.

        :return: список с отзывами.
        """

        result = []
        for _ in range(quantity):
            result.append(Review(
                id=uuid.uuid4(), customer_name=fake.name(),
                text=random.choice(comment),
                rating=random.randint(4, 5),
                created_at=GeneratorFakeUserReviews._rand_time(datetime.now(timezone.utc), 2, 14),
                product_id=random.choice(PRODUCTS).id,
            ))
        return result

    @staticmethod
    def _rand_time(now: datetime, days_min: int, days_max: int) -> datetime:
        """Генерация случайного времени."""

        lo = days_min * 86400
        hi = days_max * 86400
        return now - timedelta(seconds=random.randint(lo, hi))
