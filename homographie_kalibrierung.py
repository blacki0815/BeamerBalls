"""
Homographie-Kalibrierung
========================
Einmalig ausführen um die exakte Transformation
zwischen Kamera und Beamer zu berechnen.

Ablauf:
1. Beamer projiziert 4 Kreise an die Wand
2. Du klickst im Kamerabild auf jeden dieser Kreise
3. Die Homographie-Matrix wird in 'homographie.npy' gespeichert
4. beamer_balls.py lädt diese Datei automatisch

Starten:
    python3 homographie_kalibrierung.py
"""

import cv2
import numpy as np
import os

KAMERA_INDEX = 0
ZOOM = 2.0
BEAMER_W, BEAMER_H = 1280, 800

BEAMER_PUNKTE = np.array([
    [100,  100],
    [1180, 100],
    [1180, 700],
    [100,  700],
], dtype=np.float32)

import pygame

os.environ['SDL_VIDEO_WINDOW_POS'] = '1512,-28'
os.environ['SDL_VIDEO_CENTERED'] = '0'
pygame.init()
beamer = pygame.display.set_mode((BEAMER_W, BEAMER_H), pygame.NOFRAME)
beamer.fill((0, 0, 0))

farben = [(255,80,80), (80,255,80), (80,80,255), (255,255,80)]
labels = ["1: oben links", "2: oben rechts", "3: unten rechts", "4: unten links"]
font = pygame.font.SysFont('Arial', 28)

for i, (px, py) in enumerate(BEAMER_PUNKTE):
    pygame.draw.circle(beamer, farben[i], (int(px), int(py)), 20)
    pygame.draw.circle(beamer, (255,255,255), (int(px), int(py)), 20, 3)
    txt = font.render(str(i+1), True, (255,255,255))
    beamer.blit(txt, (int(px)+25, int(py)-15))

pygame.display.flip()
print("Beamer zeigt 4 Kreise. Kamerafenster erscheint gleich...")

cap = cv2.VideoCapture(KAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

angeklickte_punkte = []

def maus_klick(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(angeklickte_punkte) < 4:
        angeklickte_punkte.append([x, y])
        print(f"  Punkt {len(angeklickte_punkte)} gesetzt: ({x}, {y})")

cv2.namedWindow("Kalibrierung – klick auf die Kreise", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Kalibrierung – klick auf die Kreise", 1280, 720)
cv2.setMouseCallback("Kalibrierung – klick auf die Kreise", maus_klick)

print("\n=== Anleitung ===")
print("Schau auf die Wand: der Beamer zeigt 4 nummerierte Kreise.")
print("Klicke im Kamerafenster der Reihe nach auf:")
for i, l in enumerate(labels):
    print(f"  Klick {i+1}: {l}")
print("\nNach 4 Klicks wird die Homographie gespeichert.")

while len(angeklickte_punkte) < 4:
    ret, frame = cap.read()
    if not ret:
        continue

    if ZOOM > 1.0:
        h_f, w_f = frame.shape[:2]
        cx, cy = w_f // 2, h_f // 2
        crop_w, crop_h = int(w_f / ZOOM), int(h_f / ZOOM)
        x1, y1 = cx - crop_w // 2, cy - crop_h // 2
        frame = frame[y1:y1+crop_h, x1:x1+crop_w]
        frame = cv2.resize(frame, (w_f, h_f))

    anzeige = frame.copy()

    for i, (px, py) in enumerate(angeklickte_punkte):
        cv2.circle(anzeige, (px, py), 15, farben[i][::-1], -1)
        cv2.circle(anzeige, (px, py), 15, (255,255,255), 2)
        cv2.putText(anzeige, str(i+1), (px+18, py+8),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

    naechster = len(angeklickte_punkte)
    if naechster < 4:
        hinweis = f"Klick {naechster+1}/4: {labels[naechster]}"
        cv2.putText(anzeige, hinweis, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

    cv2.imshow("Kalibrierung – klick auf die Kreise", anzeige)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            break

    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("Abgebrochen.")
        cap.release()
        cv2.destroyAllWindows()
        pygame.quit()
        exit()

kamera_punkte = np.array(angeklickte_punkte, dtype=np.float32)
H, status = cv2.findHomography(kamera_punkte, BEAMER_PUNKTE)

np.save('homographie.npy', H)
np.save('beamer_punkte.npy', BEAMER_PUNKTE)

print("\nHomographie gespeichert in 'homographie.npy'")
print("  Matrix:")
print(H)
print("\nbeamer_balls.py starten – Koordinaten sind jetzt exakt!")

print("\nKontrolle (sollte nah an den Beamer-Punkten sein):")
for i, kp in enumerate(kamera_punkte):
    tp = cv2.perspectiveTransform(kp.reshape(1,1,2), H).reshape(2)
    bp = BEAMER_PUNKTE[i]
    print(f"  Punkt {i+1}: Kamera({kp[0]:.0f},{kp[1]:.0f}) → "
          f"Berechnet({tp[0]:.0f},{tp[1]:.0f}) | "
          f"Soll({bp[0]:.0f},{bp[1]:.0f})")

cap.release()
cv2.destroyAllWindows()
pygame.quit()
