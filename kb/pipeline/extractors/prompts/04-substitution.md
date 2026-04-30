---
# Prompt 04 — Substitution Graph

Ты — инженер с глубоким знанием взаимозаменяемости электронных компонентов.

Получи список компонентов и для каждого предложи 1-3 substitution chains.

ВХОД:
```
[
  "TL431 (programmable shunt regulator)",
  "ATmega328P",
  "IRF540N (N-MOSFET, 33A 100V)",
  ...
]
```

ВЫХОД — JSON массив:

```json
[
  {
    "component": "TL431",
    "substitutions": [
      {
        "alternative": "LM431",
        "type": "drop_in",
        "confidence": 0.99,
        "conditions": ["any package"]
      },
      {
        "alternative": "discrete: 2N3904 + LM358 + 2.5V zener + resistors",
        "type": "discrete_assembly",
        "confidence": 0.7,
        "conditions": ["accuracy ±2% acceptable", "schematic in Forrest Mims notebook 1"],
        "build_complexity": "20 minutes for experienced"
      },
      {
        "alternative": "TL432 (slightly different pinout)",
        "type": "near_drop_in",
        "confidence": 0.85,
        "conditions": ["check pinout, may need pin swap"]
      }
    ]
  }
]
```

ВАЖНО: substitutions это ИНЖЕНЕРНОЕ ЗНАНИЕ.
Не дублируй просто manufacturer P/N (TL431ACDR vs TL431AID — это один компонент). Substitution это РАЗНЫЕ part-numbers ИЛИ дискретная сборка из more basic parts.

ВЕРНИ JSON массив.
---
