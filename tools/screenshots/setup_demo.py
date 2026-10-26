"""Write a fresh Home Assistant config for the screenshots (demo user, dashboard).

Used by tools/screenshots/run.sh:  python setup_demo.py <config dir> <repo root>
"""
import json
import os
import sys
from pathlib import Path

CONFIG = """homeassistant:
  name: Demo Home
  unit_system: metric
  time_zone: America/Denver
  currency: USD
  country: US
  latitude: 0
  longitude: 0
  elevation: 0
frontend:
config:
my:
http:
  server_port: {port}
api:
person:
logbook:
history:
stream:
system_health:
logger:
  default: warning
"""

CAMERAS = ["driveway", "front_door", "backyard", "garage", "patio", "side_gate"]

DASHBOARD = {
    "title": "Demo Home",
    "views": [
        {
            "title": "Cameras",
            "path": "cameras",
            "type": "sections",
            "max_columns": 3,
            "sections": [
                {
                    "type": "grid",
                    "cards": [{"type": "heading", "heading": "Blue Iris cameras"}]
                    + [
                        {
                            "type": "picture-entity",
                            "entity": f"camera.bi5_{camera}",
                            "camera_view": "auto",
                            "show_state": False,
                            "grid_options": {"columns": 6},
                        }
                        for camera in CAMERAS
                    ],
                },
                {
                    "type": "grid",
                    "cards": [
                        {"type": "heading", "heading": "Blue Iris server"},
                        {
                            "type": "entities",
                            "entities": [
                                "sensor.bi5_connection_health",
                                "sensor.bi5_cpu",
                                "sensor.bi5_memory",
                                "sensor.bi5_disk_d_free",
                                "sensor.bi5_uptime",
                                "sensor.bi5_active_profile",
                                "select.bi5_shield",
                                "switch.bi5_profile_hold",
                            ],
                        },
                        {
                            "type": "entities",
                            "title": "Streaming",
                            "entities": [
                                "switch.bi5_ha_streaming",
                                "select.bi5_stream_type",
                                "select.bi5_stream_method",
                            ],
                        },
                    ],
                },
                {
                    "type": "grid",
                    "cards": [
                        {"type": "heading", "heading": "Camera health"},
                        {
                            "type": "entities",
                            "entities": [f"binary_sensor.bi5_{c}_problem" for c in CAMERAS],
                        },
                        {
                            "type": "entities",
                            "title": "Side Gate",
                            "entities": [
                                "switch.bi5_side_gate_auto_reset",
                                "number.bi5_side_gate_auto_reset_attempts",
                                "sensor.bi5_side_gate_last_alert",
                                "button.bi5_side_gate_reset",
                            ],
                        },
                    ],
                },
            ],
        }
    ],
}


def main():
    config_dir = Path(sys.argv[1])
    repo = Path(sys.argv[2]).resolve()
    port = os.environ.get("HA_PORT", "8124")

    (config_dir / ".storage").mkdir(parents=True, exist_ok=True)
    (config_dir / "custom_components").mkdir(exist_ok=True)

    link = config_dir / "custom_components" / "blueiris"
    if not link.exists():
        link.symlink_to(repo / "custom_components" / "blueiris")

    (config_dir / "configuration.yaml").write_text(CONFIG.format(port=port))

    def store(key, data, version=1):
        (config_dir / ".storage" / key).write_text(
            json.dumps({"version": version, "minor_version": 1, "key": key, "data": data})
        )

    store("onboarding", {"done": ["user", "core_config", "analytics", "integration"]}, version=4)
    store("lovelace", {"config": DASHBOARD})


if __name__ == "__main__":
    main()
