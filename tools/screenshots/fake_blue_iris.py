"""A made-up Blue Iris server for README screenshots (no real cameras or data).

Serves the JSON API (/json: login, camlist, status, log, camconfig, ...),
still images (/image/<camera>) drawn with Pillow, and /admin. Used by
tools/screenshots/run.sh; start it alone with:
    python tools/screenshots/fake_blue_iris.py 8181
"""
import hashlib
import json
import io
import random
import sys
import time

from aiohttp import web
from PIL import Image, ImageDraw, ImageFont

USER, PASSWORD = "demo", "demo"
SESSION = "5e55i0n0000demo"

# id, name, (sky, ground) colours, scene, extra camlist fields
CAMERAS = [
    ("driveway", "Driveway", ((150, 185, 215), (110, 110, 105)), "car", {}),
    ("frontdoor", "Front Door", ((165, 195, 220), (125, 120, 112)), "door", {"audio": True}),
    ("backyard", "Backyard", ((140, 180, 210), (85, 125, 70)), "fence", {}),
    ("garage", "Garage", ((60, 62, 68), (95, 92, 88)), "garage", {}),
    ("patio", "Patio", ((150, 190, 215), (150, 135, 115)), "table", {}),
    (
        "sidegate",
        "Side Gate",
        ((30, 30, 30), (30, 30, 30)),
        "nosignal",
        {"isOnline": False, "isNoSignal": True, "FPS": 0, "BPS": 0, "FPS2": 0, "BPS2": 0,
         "error": "Failed to connect", "nNoSignal": 12},
    ),
]


def _camera(index, cam_id, name, extra):
    data = {
        "optionDisplay": name,
        "optionValue": cam_id,
        "ip": f"192.168.1.{101 + index}",
        "notes": "",
        "type": 4,
        "admin": True,
        "audio": False,
        "ptz": False,
        "isEnabled": True,
        "isOnline": True,
        "isNoSignal": False,
        "isPaused": False,
        "isRecording": True,
        "isTriggered": False,
        "isAlerting": False,
        "isManRec": False,
        "isYellow": False,
        "pause": 0,
        "profile": 1,
        "FPS": 15.0 + index,
        "BPS": 180000 + index * 21000,
        "FPS2": 15.0,
        "BPS2": 14000 + index * 900,
        "width": 2560,
        "height": 1440,
        "width2": 640,
        "height2": 360,
        "newalerts": 3 + index,
        "nAlerts": 40 + index * 7,
        "nTriggers": 90 + index * 11,
        "nClips": 1200 + index * 97,
        "nNoSignal": index,
        "alertutc": int(time.time()) - 600 * (index + 1),
        "lastalert": 241000000 + index,
        "error": "",
    }
    data.update(extra)
    return data


CAMLIST = [_camera(i, c[0], c[1], c[4]) for i, c in enumerate(CAMERAS)]
CAMLIST.append({
    "optionDisplay": "+Outside",
    "optionValue": "outside",
    "group": ["driveway", "frontdoor", "backyard", "patio"],
    "isEnabled": True,
})
STATUS = {
    "profile": 1,
    "schedule": "Default",
    "lock": 0,
    "signal": 1,
    "uptime": "6:04:12:33",
    "cpu": 11,
    "memload": "38%",
    "mem": "1.1G",
    "memphys": "32G",
    "cxns": 4,
    "warnings": 1,
    "discs": [
        {"disc": "C:", "allocated": "100G", "used": "41G", "free": "158G", "total": "237G"},
        {"disc": "D:", "allocated": "3.5T", "used": "3.1T", "free": "1.4T", "total": "3.6T"},
    ],
}
LOGIN_DATA = {
    "system name": "BI5",
    "version": "5.9.9.1",
    "admin": True,
    "support": "2027-03-01",
    "profiles": ["Inactive", "Home", "Away", "Night"],
    "schedules": ["Default", "Vacation"],
    "streams": ["Default", "Low", "High"],
}
MOTION = {}


def _font(size):
    for path in (
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "DejaVuSansMono.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_frame(cam_id):
    """A simple made-up camera picture with a timestamp overlay."""
    cam = next((c for c in CAMERAS if c[0] == cam_id), None)
    if cam is None:
        return None

    _cid, name, (sky, ground), scene, _extra = cam
    w, h = 1280, 720
    img = Image.new("RGB", (w, h), sky)
    d = ImageDraw.Draw(img)
    horizon = int(h * 0.48)

    for y in range(horizon):
        f = y / horizon
        d.line([(0, y), (w, y)], fill=tuple(int(c * (0.85 + 0.25 * f)) for c in sky))
    for y in range(horizon, h):
        f = (y - horizon) / (h - horizon)
        d.line([(0, y), (w, y)], fill=tuple(int(c * (0.8 + 0.3 * f)) for c in ground))

    rnd = random.Random(cam_id)

    if scene == "nosignal":
        img = Image.new("RGB", (w, h), (20, 20, 20))
        d = ImageDraw.Draw(img)
        for _ in range(9000):
            x, y = rnd.randrange(w), rnd.randrange(h)
            v = rnd.randrange(30, 90)
            d.point((x, y), fill=(v, v, v))
        d.text((w // 2 - 170, h // 2 - 30), "NO SIGNAL", fill=(220, 220, 220), font=_font(64))
    elif scene == "car":
        d.polygon([(w * .3, h), (w * .48, horizon), (w * .58, horizon), (w * .9, h)], fill=(70, 70, 72))
        d.rounded_rectangle([520, 470, 860, 600], 30, fill=(160, 30, 35))
        d.rounded_rectangle([580, 410, 800, 490], 25, fill=(140, 25, 30))
        d.rectangle([600, 425, 780, 470], fill=(170, 200, 220))
        for x in (575, 805):
            d.ellipse([x - 38, 565, x + 38, 641], fill=(25, 25, 25))
        d.rectangle([60, horizon - 210, 380, horizon + 40], fill=(205, 185, 150))
        d.polygon([(40, horizon - 210), (220, horizon - 330), (400, horizon - 210)], fill=(120, 70, 55))
    elif scene == "door":
        d.rectangle([380, 90, 900, h], fill=(215, 205, 185))
        d.rectangle([540, 200, 740, h], fill=(110, 60, 40))
        d.ellipse([705, 470, 725, 490], fill=(220, 190, 90))
        d.rectangle([470, 640, 810, h], fill=(90, 85, 70))
        d.rectangle([780, 230, 860, 330], fill=(250, 240, 200))
    elif scene == "fence":
        for x in range(0, w, 70):
            d.rectangle([x, horizon - 120, x + 55, horizon + 30], fill=(150, 110, 75))
        d.ellipse([850, 120, 1150, 420], fill=(60, 110, 55))
        d.rectangle([985, 380, 1015, horizon + 60], fill=(95, 70, 45))
        d.rectangle([200, 520, 520, 560], fill=(200, 200, 205))
    elif scene == "garage":
        d.rectangle([0, 0, w, horizon], fill=(78, 78, 82))
        d.rectangle([140, 160, 520, horizon + 10], fill=(120, 120, 125))
        for y in range(180, horizon, 40):
            d.line([(140, y), (520, y)], fill=(95, 95, 100), width=3)
        d.rounded_rectangle([640, 420, 1060, 610], 40, fill=(30, 60, 120))
        d.rectangle([700, 360, 980, 440], fill=(40, 70, 130))
        d.rectangle([760, 190, 1180, 330], fill=(140, 120, 90))
    elif scene == "table":
        d.ellipse([470, 450, 830, 560], fill=(60, 60, 60))
        d.rectangle([640, 505, 660, 650], fill=(50, 50, 50))
        for x in (380, 900):
            d.rectangle([x - 50, 470, x + 50, 600], fill=(110, 80, 55))
        d.polygon([(560, 200), (650, 120), (740, 200)], fill=(220, 120, 60))
        d.rectangle([645, 200, 655, 450], fill=(60, 60, 60))

    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    d.text((22, 18), stamp, fill=(255, 255, 255), font=_font(30), stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((22, h - 52), name, fill=(255, 255, 255), font=_font(30), stroke_width=2, stroke_fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue()


async def json_api(request):
    body = json.loads(await request.text() or "{}")
    cmd = body.get("cmd")

    def ok(data=None, **extra):
        result = {"result": "success", **extra}
        if data is not None:
            result["data"] = data
        return web.json_response(result)

    if cmd == "login":
        if "response" not in body:
            return web.json_response({"result": "fail", "session": SESSION})
        token = hashlib.md5(f"{USER}:{SESSION}:{PASSWORD}".encode()).hexdigest()
        if body["response"] != token:
            return web.json_response({"result": "fail", "data": {"reason": "Invalid login"}})
        return ok(LOGIN_DATA, session=SESSION)

    if body.get("session") != SESSION:
        return web.json_response({"result": "fail", "data": {"reason": "Invalid session"}})

    if cmd == "camlist":
        now = int(time.time())
        for i, cam in enumerate(CAMLIST):
            if "alertutc" in cam:
                cam["alertutc"] = now - 600 * (i + 1)
        return ok(CAMLIST)
    if cmd == "status":
        for key in ("signal", "schedule"):
            if key in body:
                STATUS[key] = body[key]
        return ok(STATUS)
    if cmd == "camconfig":
        camera = body.get("camera")
        for key in ("motion",):
            if key in body:
                MOTION[camera] = bool(body[key])
        return ok({"motion": MOTION.get(camera, True)})
    if cmd == "log":
        now = int(time.time())
        return ok([{"date": now - 120, "obj": "Side Gate", "msg": "Signal: network retry", "level": 1}])
    if cmd in ("snapshot", "trigger", "ptz"):
        return ok({})
    return web.json_response({"result": "fail", "data": {"reason": f"unknown cmd {cmd}"}})


async def image(request):
    jpeg = draw_frame(request.match_info["camera"])
    if jpeg is None:
        raise web.HTTPNotFound()
    return web.Response(body=jpeg, content_type="image/jpeg")


async def admin(_request):
    return web.Response(text="ok")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8181
    app = web.Application()
    app.router.add_post("/json", json_api)
    app.router.add_get("/image/{camera}", image)
    app.router.add_get("/admin", admin)
    web.run_app(app, host="127.0.0.1", port=port, print=None)


if __name__ == "__main__":
    main()
