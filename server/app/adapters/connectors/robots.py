"""robots.txt parsing and matching, following RFC 9309.

Written here because the standard library parser ignores the ``*`` and ``$``
wildcards that real robots.txt files use, so it would fetch pages a site has
asked crawlers to leave alone.

How a file is read:

* rules are grouped by ``User-agent``; the groups naming this crawler apply,
  and only when none does do the ``*`` groups;
* of the rules that match a path, the longest pattern wins and ``Allow`` wins a
  tie;
* ``*`` matches any run of characters and a trailing ``$`` anchors the end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class _Rule:
    allow: bool
    pattern: str
    regex: re.Pattern[str]


@dataclass
class _Group:
    agents: list[str] = field(default_factory=lambda: [])
    rules: list[_Rule] = field(default_factory=lambda: [])
    crawl_delay: float | None = None


def _compile(pattern: str) -> re.Pattern[str]:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = ".*".join(re.escape(part) for part in body.split("*"))
    return re.compile(regex + ("$" if anchored else ""))


class RobotsRules:
    """The rules that apply to one crawler, from one robots.txt."""

    def __init__(self, rules: list[_Rule] | None = None, crawl_delay: float | None = None) -> None:
        self._rules = rules or []
        self.crawl_delay = crawl_delay

    @classmethod
    def allow_all(cls) -> RobotsRules:
        return cls()

    @classmethod
    def disallow_all(cls) -> RobotsRules:
        return cls([_Rule(False, "/", _compile("/"))])

    @classmethod
    def parse(cls, text: str, *, agent: str) -> RobotsRules:
        """Parse a robots.txt for the crawler called ``agent`` (its product token)."""
        token = agent.lower()
        groups: list[_Group] = []
        current: _Group | None = None
        collecting_agents = False

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            name, _, value = line.partition(":")
            name = name.strip().lower()
            value = value.strip()
            if name == "user-agent":
                if current is None or not collecting_agents:
                    current = _Group()
                    groups.append(current)
                current.agents.append(value.lower())
                collecting_agents = True
                continue
            collecting_agents = False
            if current is None:
                continue
            if name in ("allow", "disallow"):
                if not value:
                    # An empty Disallow allows everything; an empty Allow says nothing.
                    continue
                current.rules.append(_Rule(name == "allow", value, _compile(value)))
            elif name == "crawl-delay":
                try:
                    current.crawl_delay = max(0.0, float(value))
                except ValueError:
                    pass

        specific = [group for group in groups if any(a != "*" and a in token for a in group.agents)]
        chosen = specific or [group for group in groups if "*" in group.agents]
        rules = [rule for group in chosen for rule in group.rules]
        delays = [group.crawl_delay for group in chosen if group.crawl_delay is not None]
        return cls(rules, delays[0] if delays else None)

    def allows(self, path_and_query: str) -> bool:
        """Whether the crawler may fetch ``path_and_query`` (a path, with its query if any)."""
        best: _Rule | None = None
        for rule in self._rules:
            if not rule.regex.match(path_and_query):
                continue
            if best is None or len(rule.pattern) > len(best.pattern) or (
                len(rule.pattern) == len(best.pattern) and rule.allow and not best.allow
            ):
                best = rule
        return best is None or best.allow
