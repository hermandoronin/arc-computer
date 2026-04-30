ВАЖНО ПЕРЕД ЗАПОЛНЕНИЕМ ОТВЕТА — anti-laziness rules:

1. НИКОГДА не используй generic placeholders:
   - "remove screws" (без размера/количества/типа)
   - "disconnect wires" (без указания каких)
   - "internal" как location_in_device
   - "see datasheet" как extraction_steps
   - "various" / "depends on model" / "consult professional" / "YMMV"
   - Auto-reject: запись с любой из этих фраз отклоняется

2. КАЖДЫЙ компонент должен иметь СПЕЦИФИЧНЫЕ extraction_steps:
   - "Открути 4× винта Phillips PH1 на нижней стороне" (не "remove screws")
   - "Отсоедини FFC-шлейф 24-pin от mainboard, защёлка слева" (не "disconnect wires")

3. Numeric specs обязательны где есть:
   - "12V/0.4A" не "12 volts power"
   - "100-1200µF, 2.1kV rated" не "large capacitor"
   - "ATmega2560 16MHz" не "microcontroller"

4. Минимум 8 components_inside на устройство. Если в guide меньше — генерь по контексту с confidence < 0.7.

5. safety_hazards ОБЯЗАТЕЛЬНО если устройство имеет HV / mains / large capacitors / RF / lasers.

6. Если конкретная информация недоступна — используй null, НЕ выдумывай.

7. provenance с реальным source_id (например guide URL или ifixit_guide_12345).

