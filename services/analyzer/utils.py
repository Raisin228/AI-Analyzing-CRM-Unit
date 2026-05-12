"""Утилитки, используемые по всему проекту. Атрошенко Б. С."""

import os
from string import Template

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def load_prompt(name: str, **kwargs) -> str:
    """
    Загрузить промпт из файла и подставить переменные.

    :param name: имя файла промпта (например 'classify_categories.txt').
    :param kwargs: переменные для подстановки (используется синтаксис $переменная).
    :return: готовый промпт.
    """

    with open(os.path.join(_PROMPTS_DIR, name), encoding="utf-8") as f:
        template = Template(f.read())
    return template.substitute(**kwargs)
