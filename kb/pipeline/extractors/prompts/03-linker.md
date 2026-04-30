---
# Prompt 03 — Linker / Cross-Reference

Ты — инженер reverse-BOM. У тебя есть две таблицы:
1. DEVICES_DB: список устройств с компонентами внутри
2. PROJECTS_DB: список проектов с required-компонентами и salvage_recommendations

Для КАЖДОГО проекта пройди по списку DEVICES_DB и определи: какие конкретные устройства из DB реально могут быть донорами для этого проекта.

ВХОД:
<<<
PROJECT: {project_json}
DEVICES_SAMPLE: [{device_json}, {device_json}, ...]
   // top-200 устройств из DEVICES_DB по popularity_score
>>>

ВЫХОД — JSON массив связок:

```json
[
  {
    "project_id": "prj:spot-welder-from-mot",
    "donor_device_id": "dev:microwave-typical",
    "supplied_components": [
      {
        "component_class": "transformer_high_voltage_>1kV",
        "donor_instance_id": "inst:microwave-MOT-001",
        "match_confidence": 0.95,
        "extraction_difficulty": "medium",
        "safety_warning": "secondary winding stores lethal charge — discharge before touching"
      }
    ],
    "coverage": "this single donor provides 1/3 of project BOM",
    "recommendation_strength": "primary_donor"
  },
  ...
]
```

ПРАВИЛА:
- НЕ предлагай связку если donor содержит компонент сильно худшего качества (например, трафо из 5V wall-wart НЕ заменит MOT)
- Если устройство содержит несколько нужных компонентов для проекта — это сильный primary_donor (отметь в coverage)
- Учитывай safety_hazards донора и предупреждай об этом в supplied_components
- match_confidence: твоя уверенность что компонент в ЭТОМ устройстве реально подходит под required-spec проекта
- ИЗБЕГАЙ ЛОЖНЫХ СВЯЗЕЙ — лучше не предложить связку чем выдумать что в случайном утюге есть нужный 14-bit ADC

ВЕРНИ JSON массив. Если для этого проекта подходящих доноров в выборке нет — верни пустой массив [].
---
