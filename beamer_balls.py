import os
import sys
import time
import threading
import numpy as np

os.environ['SDL_VIDEO_WINDOW_POS'] = '1512,-28'
os.environ['SDL_VIDEO_CENTERED'] = '0'

import pygame
import pymunk
import cv2

BEAMER_W, BEAMER_H = 1280, 800
FPS = 60
BALL_RADIUS = 12
SPAWN_INTERVAL = 0.5
GRAVITY = 600

KAMERA_INDEX = 0
ZOOM = 2.0

HSV_MIN = np.array([19, 83, 160])
HSV_MAX = np.array([73, 158, 242])
MIN_ZETTEL_FLAECHE = 300

SPAWN_POSITIONEN = [750]
spawn_index = 0

DEBUG = True

HOMOGRAPHIE = None
if os.path.exists('homographie.npy'):
    HOMOGRAPHIE = np.load('homographie.npy')
    print("✓ Homographie geladen")
else:
    print("Keine homographie.npy – einfache Skalierung wird verwendet")

def transformiere_punkte(punkte_kamera):
    if HOMOGRAPHIE is not None:
        pts = np.array(punkte_kamera, dtype=np.float32).reshape(-1, 1, 2)
        transformiert = cv2.perspectiveTransform(pts, HOMOGRAPHIE)
        return [(float(p[0][0]), float(p[0][1])) for p in transformiert]
    else:
        cam_w, cam_h = 1280, 720
        return [
            (float(px / cam_w * BEAMER_W), float(py / cam_h * BEAMER_H))
            for (px, py) in punkte_kamera
        ]

pygame.init()
screen = pygame.display.set_mode((BEAMER_W, BEAMER_H), pygame.NOFRAME)
clock = pygame.time.Clock()

space = pymunk.Space()
space.gravity = (0, GRAVITY)

PHYSIK_DT = 1.0 / 120.0
physik_akkumulator = 0.0

def segment_hinzufuegen(p1, p2, elastizitaet=0.7):
    seg = pymunk.Segment(space.static_body, p1, p2, 3)
    seg.elasticity = elastizitaet
    seg.friction = 0.3
    seg.filter = pymunk.ShapeFilter(categories=0b10, mask=0b11)
    space.add(seg)
    return seg

segment_hinzufuegen((0, 0), (0, BEAMER_H), 0.6)
segment_hinzufuegen((BEAMER_W, 0), (BEAMER_W, BEAMER_H), 0.6)

aktuelle_kollider = []
letzter_zettel_hash = None

def ecken_hash(zettel_liste):
    """Schneller Vergleich ob Zettel-Positionen sich geändert haben."""
    if not zettel_liste:
        return None
    arr = np.array(zettel_liste).flatten()
    return round(float(np.sum(arr)), 0)

def zettel_kollider_aktualisieren(zettel_ecken_liste):
    global aktuelle_kollider, letzter_zettel_hash

    neuer_hash = ecken_hash(zettel_ecken_liste)

    if neuer_hash == letzter_zettel_hash:
        return
    letzter_zettel_hash = neuer_hash

    for seg in aktuelle_kollider:
        space.remove(seg)
    aktuelle_kollider = []

    for ecken_kamera in zettel_ecken_liste:
        ecken_beamer = transformiere_punkte(ecken_kamera)
        for i in range(len(ecken_beamer)):
            p1 = ecken_beamer[i]
            p2 = ecken_beamer[(i + 1) % len(ecken_beamer)]
            seg = segment_hinzufuegen(p1, p2, 0.75)
            aktuelle_kollider.append(seg)

kamera_zettel = []
kamera_lock = threading.Lock()
debug_lock = threading.Lock()
debug_data = {'frame': None, 'maske': None}

def kamera_loop():
    cap = cv2.VideoCapture(KAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        print(f"FEHLER: Kamera {KAMERA_INDEX} nicht gefunden!")
        return

    print("Kamera gestartet...")
    kernel = np.ones((5, 5), np.uint8)

    while True:
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

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        maske = cv2.inRange(hsv, HSV_MIN, HSV_MAX)
        maske = cv2.morphologyEx(maske, cv2.MORPH_CLOSE, kernel)
        maske = cv2.morphologyEx(maske, cv2.MORPH_OPEN, kernel)

        konturen, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        neue_zettel = []
        debug_frame = frame.copy()

        for k in konturen:
            flaeche = cv2.contourArea(k)
            if flaeche > MIN_ZETTEL_FLAECHE:
                rect = cv2.minAreaRect(k)
                ecken = cv2.boxPoints(rect)
                ecken_int = ecken.astype(np.int32)
                cv2.drawContours(debug_frame, [ecken_int], 0, (0, 255, 0), 3)
                mx, my = int(rect[0][0]), int(rect[0][1])
                w_r, h_r = int(rect[1][0]), int(rect[1][1])
                cv2.putText(debug_frame, f"{int(flaeche)}px {w_r}x{h_r} {rect[2]:.0f}°",
                            (mx - 60, my - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
                neue_zettel.append([(float(px), float(py)) for (px, py) in ecken])
            else:
                cv2.drawContours(debug_frame, [k], 0, (0, 0, 255), 1)
                cv2.putText(debug_frame, f"{int(flaeche)}px",
                            (int(k[0][0][0]), int(k[0][0][1]) - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 80, 255), 1)

        cv2.putText(debug_frame,
                    f"Erkannt: {len(neue_zettel)}  |  D = Debug an/aus",
                    (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(debug_frame,
                    f"HSV min({HSV_MIN[0]},{HSV_MIN[1]},{HSV_MIN[2]}) "
                    f"max({HSV_MAX[0]},{HSV_MAX[1]},{HSV_MAX[2]})",
                    (10, debug_frame.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        maske_rgb = cv2.cvtColor(maske, cv2.COLOR_GRAY2BGR)
        cv2.putText(maske_rgb, "Maske (weiss = erkannte Farbe)",
                    (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

        with kamera_lock:
            kamera_zettel.clear()
            kamera_zettel.extend(neue_zettel)
        with debug_lock:
            debug_data['frame'] = debug_frame.copy()
            debug_data['maske'] = maske_rgb.copy()

    cap.release()

threading.Thread(target=kamera_loop, daemon=True).start()

baelle = []
letzter_spawn = time.time()
letzter_zettel_update = time.time()
letzter_debug_update = time.time()

def neuer_ball():
    global spawn_index
    masse = 1
    traegheit = pymunk.moment_for_circle(masse, 0, BALL_RADIUS)
    body = pymunk.Body(masse, traegheit)
    x = SPAWN_POSITIONEN[spawn_index % len(SPAWN_POSITIONEN)]
    spawn_index += 1
    body.position = (x, -BALL_RADIUS)
    shape = pymunk.Circle(body, BALL_RADIUS)
    shape.elasticity = 0.6
    shape.friction = 0.3
    shape.filter = pymunk.ShapeFilter(categories=0b01, mask=0b11)
    space.add(body, shape)
    return (body, shape)

print("Beamer Balls gestartet  |  ESC = Beenden  |  D = Debug")

laufend = True
while laufend:
    frame_dt = clock.tick(FPS) / 1000.0
    jetzt = time.time()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            laufend = False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                laufend = False
            if event.key == pygame.K_d:
                DEBUG = not DEBUG
                if not DEBUG:
                    cv2.destroyAllWindows()
                print(f"Debug: {'AN' if DEBUG else 'AUS'}")

    if jetzt - letzter_zettel_update > 0.5:
        with kamera_lock:
            snapshot = list(kamera_zettel)
        zettel_kollider_aktualisieren(snapshot)
        letzter_zettel_update = jetzt

    if jetzt - letzter_spawn >= SPAWN_INTERVAL:
        baelle.append(neuer_ball())
        letzter_spawn = jetzt

    for body, shape in baelle:
        if body.position.y > BEAMER_H + 50:
            space.remove(body, shape)
    baelle = [(b, s) for b, s in baelle if b.position.y <= BEAMER_H + 50]

    physik_akkumulator += frame_dt
    while physik_akkumulator >= PHYSIK_DT:
        space.step(PHYSIK_DT)
        physik_akkumulator -= PHYSIK_DT

    if DEBUG and jetzt - letzter_debug_update > 0.066:
        with debug_lock:
            df = debug_data['frame']
            dm = debug_data['maske']
        if df is not None and dm is not None:
            df_r = cv2.resize(df, (960, 540))
            dm_r = cv2.resize(dm, (960, 540))
            cv2.imshow("Debug  (D zum Schliessen)", np.hstack([df_r, dm_r]))
            cv2.waitKey(1)
        letzter_debug_update = jetzt

    screen.fill((0, 0, 0))
    for body, shape in baelle:
        pos = (int(body.position.x), int(body.position.y))
        pygame.draw.circle(screen, (255, 255, 255), pos, BALL_RADIUS)
        pygame.draw.circle(screen, (200, 230, 255), pos, BALL_RADIUS - 4)
    pygame.display.flip()

cv2.destroyAllWindows()
pygame.quit()
sys.exit()