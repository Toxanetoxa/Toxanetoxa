"""Render share-of-code and share-of-repository SVG cards for the profile."""

from html import escape


_CARD_WIDTH = 352
_INSET = 19
_ROW_HEIGHT = 35
_BAR_WIDTH = _CARD_WIDTH - 2 * _INSET
_COPY = {
    "en": {
        "languages": "Languages",
        "primary_languages": "Primary languages",
        "technologies": "Technologies",
        "empty": "No data found",
        "other": "Other",
        "undetected": "Undetected",
    },
    "ru": {
        "languages": "Языки",
        "primary_languages": "Основные языки",
        "technologies": "Технологии",
        "empty": "Данные не найдены",
        "other": "Другие",
        "undetected": "Не определён",
    },
}


def render_languages(rows, repo_count, locale):
    """Render detected code-byte percentages."""
    if locale == "ru":
        last_digit = repo_count % 10
        if 11 <= repo_count % 100 <= 14:
            repos = "репозиториев"
        elif last_digit == 1:
            repos = "репозиторий"
        elif 2 <= last_digit <= 4:
            repos = "репозитория"
        else:
            repos = "репозиториев"
        scope = f"Доля байтов кода · {repo_count} {repos}"
    else:
        repos = "repo" if repo_count == 1 else "repos"
        scope = f"Share of code bytes · {repo_count} {repos}"
    return _render_card("languages", rows, scope, locale)


def render_technologies(rows, repo_count, locale):
    """Render technology detection rates over scanned repositories."""
    if locale == "ru":
        scope = f"Доля репозиториев · проверено {repo_count}"
    else:
        scope = f"Share of repositories · {repo_count} scanned"
    return _render_card("technologies", rows, scope, locale)


def render_primary_languages(rows, repo_count, locale):
    """Render the percentage of repositories per primary language."""
    if locale == "ru":
        scope = f"Один голос на репозиторий · всего {repo_count}"
    else:
        repos = "repo" if repo_count == 1 else "repos"
        scope = f"One vote per repository · {repo_count} {repos}"
    return _render_card("primary_languages", rows, scope, locale)


def _format_share(share, locale):
    rounded = f"{share:.1f}".removesuffix(".0")
    if 0 < share < 0.05:
        rounded = "<0.1"
    if locale == "ru":
        rounded = rounded.replace(".", ",")
    return f"{rounded}%"


def _render_card(kind, rows, scope, locale):
    copy = _COPY[locale]
    title = copy[kind]
    special_labels = {"Other": copy["other"], "Undetected": copy["undetected"]}
    labels = [(special_labels.get(name, name), share) for name, share in rows]
    height = 99 + max(1, len(labels)) * _ROW_HEIGHT
    description = scope + ". " + ", ".join(
        f"{name} {_format_share(share, locale)}" for name, share in labels
    )
    markup = [
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" xml:lang="{locale}" '
        f'aria-labelledby="card-title card-description" width="{_CARD_WIDTH}" height="{height}" '
        f'viewBox="0 0 {_CARD_WIDTH} {height}">',
        f'  <title id="card-title">{title}</title>',
        f'  <desc id="card-description">{escape(description)}</desc>',
        f'  <rect x="0.5" y="0.5" width="{_CARD_WIDTH - 1}" height="{height - 1}" '
        'rx="14" fill="#211A30" stroke="#9E78CD"/>',
        '  <g font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
        f'    <text x="{_INSET}" y="34" font-size="23" font-weight="700" fill="#FAF6FF">{title}</text>',
    ]
    if not labels:
        markup.append(
            f'    <text x="{_INSET}" y="70" font-size="15" fill="#D6C9E3">{copy["empty"]}</text>'
        )
    for index, (name, share) in enumerate(labels):
        y = 65 + index * _ROW_HEIGHT
        bar_y = y + 7
        bar_width = _BAR_WIDTH * share / 100
        markup.extend([
            f'    <text x="{_INSET}" y="{y}" font-size="15" font-weight="550" fill="#F6F0FC">'
            f'{escape(name)}</text>',
            f'    <text x="{_CARD_WIDTH - _INSET}" y="{y}" text-anchor="end" font-size="15" '
            f'font-weight="650" fill="#E0B9FC">{escape(_format_share(share, locale))}</text>',
            f'    <rect x="{_INSET}" y="{bar_y}" width="{_BAR_WIDTH}" height="5" rx="2.5" fill="#443653"/>',
            f'    <rect x="{_INSET}" y="{bar_y}" width="{bar_width:.3f}" height="5" '
            f'rx="{min(2.5, bar_width / 2):.3f}" fill="#CE9EEE"/>',
        ])
    markup.extend([
        f'    <path d="M{_INSET} {height - 43}H{_CARD_WIDTH - _INSET}" stroke="#59486A"/>',
        f'    <text x="{_INSET}" y="{height - 20}" font-size="13" fill="#D6C9E3">{escape(scope)}</text>',
        '  </g>',
        '</svg>',
    ])
    return "\n".join(markup) + "\n"
