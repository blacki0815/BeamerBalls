"""
Kalibrierungs-Tool für Notizzettel-Farberkennung
=================================================
Dieses Skript hilft dir, die richtigen HSV-Werte für deine
neongelben Notizzettel zu finden.

Installation:
    pip3 install opencv-python numpy

Starten:
    python3 kalibrierung.py

Bedienung:
    - 6 Schieberegler erscheinen (H_min, H_max, S_min, S_max, V_min, V_max)
    - Klebe einen Notizzettel an die Wand, beleuchte wie später beim Projekt
    - Schieberegler so einstellen, dass der Zettel weiß leuchtet, alles andere schwarz ist
    - Die aktuellen Werte werden live im Terminal angezeigt
    - Q zum Beenden und Werte notieren
"""

import cv2
import numpy as np

KAMERA_INDEX = 0

ZOOM = 2.0

cap = cv2.VideoCapture(KAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print(f"FEHLER: Kamera {KAMERA_INDEX} nicht gefunden!")
    exit()

print("Schieberegler anpassen bis Notizzettel weiß = erkannt")

cv2.namedWindow("Kalibrierung", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Kalibrierung", 800, 600)

cv2.createTrackbar("H min", "Kalibrierung", 20, 179, lambda x: None)
cv2.createTrackbar("H max", "Kalibrierung", 35, 179, lambda x: None)
cv2.createTrackbar("S min", "Kalibrierung", 150, 255, lambda x: None)
cv2.createTrackbar("S max", "Kalibrierung", 255, 255, lambda x: None)
cv2.createTrackbar("V min", "Kalibrierung", 150, 255, lambda x: None)
cv2.createTrackbar("V max", "Kalibrierung", 255, 255, lambda x: None)

letzter_print = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Kein Bild von Kamera")
        break

    h_min = cv2.getTrackbarPos("H min", "Kalibrierung")
    h_max = cv2.getTrackbarPos("H max", "Kalibrierung")
    s_min = cv2.getTrackbarPos("S min", "Kalibrierung")
    s_max = cv2.getTrackbarPos("S max", "Kalibrierung")
    v_min = cv2.getTrackbarPos("V min", "Kalibrierung")
    v_max = cv2.getTrackbarPos("V max", "Kalibrierung")

    if ZOOM > 1.0:
        h_f, w_f = frame.shape[:2]
        cx, cy = w_f // 2, h_f // 2
        crop_w, crop_h = int(w_f / ZOOM), int(h_f / ZOOM)
        x1, y1 = cx - crop_w // 2, cy - crop_h // 2
        frame = frame[y1:y1+crop_h, x1:x1+crop_w]
        frame = cv2.resize(frame, (w_f, h_f))

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    untere_grenze = np.array([h_min, s_min, v_min])
    obere_grenze  = np.array([h_max, s_max, v_max])
    maske = cv2.inRange(hsv, untere_grenze, obere_grenze)

    konturen, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ergebnis = frame.copy()
    for k in konturen:
        flaeche = cv2.contourArea(k)
        if flaeche > 300:
            x, y, w, h = cv2.boundingRect(k)
            cv2.rectangle(ergebnis, (x, y), (x+w, y+h), (0, 255, 0), 3)
            cv2.putText(ergebnis, f"{int(flaeche)}px", (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    maske_rgb = cv2.cvtColor(maske, cv2.COLOR_GRAY2BGR)
    anzeige = np.hstack([
        cv2.resize(ergebnis,    (640, 360)),
        cv2.resize(maske_rgb,   (640, 360))
    ])
    cv2.putText(anzeige, "Original + erkannte Zettel", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
    cv2.putText(anzeige, "Maske (weiss = erkannt)", (650, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

    cv2.imshow("Kalibrierung", anzeige)

    import time
    jetzt = time.time()
    if jetzt - letzter_print > 2:
        print(f"HSV: ({h_min},{s_min},{v_min}) → ({h_max},{s_max},{v_max})  |  Zettel erkannt: {len([k for k in konturen if cv2.contourArea(k) > 300])}")
        letzter_print = jetzt

    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("\n=== Finale HSV-Werte (in beamer_balls.py eintragen) ===")
        print(f"HSV_GELB_MIN = ({h_min}, {s_min}, {v_min})")
        print(f"HSV_GELB_MAX = ({h_max}, {s_max}, {v_max})")
        break

cap.release()
cv2.destroyAllWindows()