// ARC educational door alarm: Arduino Uno, reed to D2/GND,
// small passive piezo to D8/GND. Bench testing on hardware is still required.
const byte CONTACT = 2;
const byte PIEZO = 8;
bool rawState = HIGH;
bool stableState = HIGH;
unsigned long changedAt = 0;
void setup() {
  pinMode(CONTACT, INPUT_PULLUP);
  pinMode(PIEZO, OUTPUT);
  rawState = digitalRead(CONTACT);
  stableState = rawState;
}
void loop() {
  bool next = digitalRead(CONTACT);
  if (next != rawState) { rawState = next; changedAt = millis(); }
  if (millis() - changedAt >= 40) stableState = rawState;
  if (stableState == HIGH) tone(PIEZO, 2200);
  else noTone(PIEZO);
}
