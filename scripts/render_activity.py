"""Render the activity calendar that GitHub shows to signed-out visitors."""

from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen


COLORS = ("#1b2b3c", "#23574f", "#268172", "#33af99", "#73e5cb")


class ContributionCalendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}
        self.counts = {}
        self.tooltip_day = None
        self.tooltip_text = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "td" and "ContributionCalendar-day" in attrs.get("class", "").split():
            day = date.fromisoformat(attrs["data-date"])
            self.days[day] = (attrs["id"], int(attrs["data-level"]))
        if tag == "tool-tip" and attrs.get("for", "").startswith("contribution-day-component-"):
            self.tooltip_day = attrs["for"]
            self.tooltip_text = []

    def handle_data(self, data):
        if self.tooltip_day:
            self.tooltip_text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tooltip_day:
            match = re.match(r"(No|[\d,]+) contributions? on ", "".join(self.tooltip_text).strip())
            if match:
                value = match.group(1)
                self.counts[self.tooltip_day] = 0 if value == "No" else int(value.replace(",", ""))
            self.tooltip_day = None

    def read_days(self):
        days = sorted(self.days)
        if not 365 <= len(days) <= 372 or (days[-1] - days[0]).days + 1 != len(days):
            raise ValueError("GitHub did not return a complete yearly contribution calendar")

        result = []
        for day in days:
            key, level = self.days[day]
            count = self.counts[key]
            if level not in range(len(COLORS)) or bool(count) != bool(level):
                raise ValueError(f"Unrecognized contribution level for {day}")
            result.append((day, level, count))
        return result


def render(days):
    first, last = days[0][0], days[-1][0]
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)
    total = sum(count for _, _, count in days)
    active = sum(count > 0 for _, _, count in days)
    shape = []

    for day, level, _ in days:
        week, weekday = divmod((day - grid_start).days, 7)
        x = 32 + week * 15
        y = 170 + weekday * 15
        shape.append(f'  <rect x="{x}" y="{y}" width="12" height="12" rx="2.5" fill="{COLORS[level]}"/>')

    squares = "\n".join(shape)
    total_label = f"{total:,}".replace(",", " ")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 856 326" width="856" height="326" role="img" aria-labelledby="title desc">
  <title id="title">Активность на GitHub за год</title>
  <desc id="desc">{total_label} вкладов за год, {active} активных дней. С {first:%d.%m.%Y} по {last:%d.%m.%Y}. Каждый квадрат показывает день.</desc>
  <rect x="0.5" y="0.5" width="855" height="325" rx="15" fill="#0f1928" stroke="#2a4051"/>
  <g font-family="system-ui, sans-serif">
    <text x="32" y="50" fill="#edf6f8" font-size="30" font-weight="650">Активность за год</text>
    <text x="32" y="108" fill="#73e5cb" font-size="43" font-weight="700">{total_label}</text>
    <text x="32" y="139" fill="#b8ccd5" font-size="25">Вклады</text>
    <text x="312" y="108" fill="#73e5cb" font-size="43" font-weight="700">{active}</text>
    <text x="312" y="139" fill="#b8ccd5" font-size="25">Активные дни</text>
    <text x="32" y="304" fill="#b8ccd5" font-size="23">{first:%d.%m.%Y} – {last:%d.%m.%Y}</text>
    <text x="683" y="304" fill="#b8ccd5" font-size="23">GitHub</text>
  </g>
{squares}
</svg>
'''


def main():
    username, output = sys.argv[1:]
    if not re.fullmatch(r"[a-zA-Z0-9-]+", username):
        raise ValueError("Invalid GitHub username")
    request = Request(
        f"https://github.com/users/{username}/contributions",
        headers={"User-Agent": "GitHub-profile-activity", "Accept-Language": "en-US"},
    )
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")
    parser = ContributionCalendar()
    parser.feed(html)
    parser.close()
    svg = render(parser.read_days())
    Path(output).write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
