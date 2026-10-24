"""
Support for Blue Iris.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.blueiris/
"""
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as DOMAIN_BINARY_SENSOR,
    BinarySensorDeviceClass,
)
from homeassistant.components.button import DOMAIN as DOMAIN_BUTTON
from homeassistant.components.camera import DOMAIN as DOMAIN_CAMERA
from homeassistant.components.number import DOMAIN as DOMAIN_NUMBER
from homeassistant.components.select import DOMAIN as DOMAIN_SELECT
from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

CONF_LOG_LEVEL = "log_level"
CONF_ALLOWED_CAMERA = "allowed_camera"
CONF_ALLOWED_PROFILE = "allowed_profile"
CONF_ALLOWED_SCHEDULE = "allowed_schedule"
CONF_ALLOWED_MOTION_SENSOR = "allowed_motion_sensor"
CONF_ALLOWED_AUDIO_SENSOR = "allowed_audio_sensor"
CONF_ALLOWED_CONNECTIVITY_SENSOR = "allowed_connectivity_sensor"
CONF_ALLOWED_DIO_SENSOR = "allowed_dio_sensor"
CONF_ALLOWED_EXTERNAL_SENSOR = "allowed_external_sensor"
CONF_ALLOWED_PROBLEM_SENSOR = "allowed_problem_sensor"

CONF_SUPPORT_STREAM = "support_stream"

BI_ATTR_NAME = "optionDisplay"
BI_ATTR_ID = "optionValue"
BI_ATTR_AUDIO = "audio"
BI_ATTR_IS_ONLINE = "isOnline"
BI_ATTR_GROUP = "group"
BI_ATTR_TYPE = "type"

BI_NON_GENERIC_ATTRIBUTES = [
    BI_ATTR_NAME,
    BI_ATTR_ID,
    BI_ATTR_AUDIO,
    BI_ATTR_IS_ONLINE,
    BI_ATTR_GROUP,
    BI_ATTR_TYPE,
]

CAMERA_HAS_AUDIO = "has_audio"
CAMERA_IS_ONLINE = "is_online"
CAMERA_IS_SYSTEM = "is_system"
CAMERA_IS_GROUP = "is_group"
CAMERA_GROUP_CAMERAS = "group_cameras"
CAMERA_DATA = "data"
CAMERA_TYPE = "type"
CAMERA_IS_PHYSICAL = "is_physical"


CONF_ARR = [CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT, CONF_SSL]

DROP_DOWNS_CONF = [
    CONF_ALLOWED_CAMERA,
    CONF_ALLOWED_PROFILE,
    CONF_ALLOWED_SCHEDULE,
    CONF_ALLOWED_MOTION_SENSOR,
    CONF_ALLOWED_AUDIO_SENSOR,
    CONF_ALLOWED_CONNECTIVITY_SENSOR,
    CONF_ALLOWED_DIO_SENSOR,
    CONF_ALLOWED_EXTERNAL_SENSOR,
    CONF_ALLOWED_PROBLEM_SENSOR,
]

ENTRY_PRIMARY_KEY = CONF_NAME

CONFIG_FLOW_DATA = "config_flow_data"
CONFIG_FLOW_OPTIONS = "config_flow_options"
CONFIG_FLOW_INIT = "config_flow_init"

VERSION = "2.0.0"

DOMAIN = "blueiris"
PASSWORD_MANAGER_BLUEIRIS = f"pm_{DOMAIN}"
DATA_BLUEIRIS = f"data_{DOMAIN}"
DATA_BLUEIRIS_API = f"{DATA_BLUEIRIS}_API"
DATA_BLUEIRIS_HA = f"{DATA_BLUEIRIS}_HA"
DATA_BLUEIRIS_HA_ENTITIES = f"{DATA_BLUEIRIS}_HA_Entities"
DEFAULT_NAME = "BlueIris"
DEFAULT_PORT = "80"
DEFAULT_VERSION = "0.0.0.0"

NOT_AVAILABLE = "N/A"

DOMAIN_KEY_FILE = f"{DOMAIN}.key"
JSON_DATA_FILE = f"custom_components/{DOMAIN}/data/[NAME].json"

DOMAIN_LOGGER = "logger"
SERVICE_SET_LEVEL = "set_level"
SERVICE_TRIGGER_CAMERA = "trigger_camera"
SERVICE_MOVE_TO_PRESET = "move_to_preset"
SERVICE_RESET_CAMERA = "reset_camera"
SERVICE_SNAPSHOT_TO_DATABASE = "snapshot_to_database"
SERVICE_CURRENT_CAMERA_SNAPSHOT = "current_camera_snapshot"
SERVICE_SNAPSHOT_FILENAME = "filename"
SNAPSHOT_MEDIA_FOLDER = DOMAIN


ATTR_ADMIN_PROFILE = "Profile"
ATTR_ADMIN_SCHEDULE = "Schedule"
ATTR_SYSTEM_CAMERA_ALL_NAME = "All"
ATTR_SYSTEM_CAMERA_ALL_ID = "Index"
ATTR_SYSTEM_CAMERA_CYCLE_NAME = "Cycle"
ATTR_SYSTEM_CAMERA_CYCLE_ID = "@Index"

AUDIO_EVENT_LENGTH = 2
RECONNECT_DELAY = 15

BLUEIRIS_AUTH_ERROR = "Authorization required"

SYSTEM_CAMERA_CONFIG = {
    ATTR_SYSTEM_CAMERA_ALL_NAME: ATTR_SYSTEM_CAMERA_ALL_ID,
    ATTR_SYSTEM_CAMERA_CYCLE_NAME: ATTR_SYSTEM_CAMERA_CYCLE_ID,
}

SYSTEM_CAMERA_ID = [ATTR_SYSTEM_CAMERA_ALL_ID, ATTR_SYSTEM_CAMERA_CYCLE_ID]

AUTHENTICATION_BASIC = "basic"

NOTIFICATION_ID = f"{DOMAIN}_notification"
NOTIFICATION_TITLE = f"{DEFAULT_NAME} Setup"

DEFAULT_ICON = "mdi:alarm-light"
SCHEDULE_ICON = "mdi:calendar-clock"
ATTR_FRIENDLY_NAME = "friendly_name"

PROTOCOLS = {True: "https", False: "http"}

SCAN_INTERVAL = timedelta(seconds=30)

DEFAULT_FORCE_UPDATE = False

SENSOR_CONNECTIVITY_NAME = "Connectivity"
SENSOR_MOTION_NAME = "Motion"
SENSOR_EXTERNAL_NAME = "External"
SENSOR_DIO_NAME = "DIO"
SENSOR_AUDIO_NAME = "Audio"
SENSOR_MAIN_NAME = "Main"

SENSOR_CONNECTION_HEALTH_NAME = "Connection Health"
SENSOR_UPTIME_NAME = "Uptime"
SENSOR_PROBLEM_NAME = "Problem"
BUTTON_RESET_NAME = "Reset"

PROBLEM_NO_SIGNAL = "no_signal"
PROBLEM_OFFLINE = "offline"
PROBLEM_STALLED = "stalled"
PROBLEM_MIN_FPS = 1
# Cameras reconnect for a while after Blue Iris starts; don't report
# problems before this many seconds of uptime
PROBLEM_STARTUP_GRACE = 300

CONNECTION_STATE_CONNECTING = "connecting"
CONNECTION_STATE_CONNECTED = "connected"
CONNECTION_STATE_AUTH_FAILED = "auth_failed"
CONNECTION_STATE_UNREACHABLE = "server_unreachable"
CONNECTION_STATE_ERROR = "error"

CONNECTION_STATES = [
    CONNECTION_STATE_CONNECTING,
    CONNECTION_STATE_CONNECTED,
    CONNECTION_STATE_AUTH_FAILED,
    CONNECTION_STATE_UNREACHABLE,
    CONNECTION_STATE_ERROR,
]

CONNECTION_HEALTH_ICON = "mdi:heart-pulse"
UPTIME_ICON = "mdi:timer-outline"
PROBLEM_ICON = "mdi:cctv-off"
RESET_ICON = "mdi:restart"

ENTITY_SENSOR_DEVICE_CLASS = "device_class"
ENTITY_SENSOR_UNIT = "native_unit_of_measurement"
ENTITY_SENSOR_SUGGESTED_UNIT = "suggested_unit_of_measurement"
ENTITY_SENSOR_OPTIONS = "options"
ENTITY_SENSOR_CATEGORY = "entity_category"
ENTITY_SENSOR_STATE_CLASS = "state_class"
ENTITY_AVAILABLE = "available"
ENTITY_BUTTON_DEVICE_CLASS = "button_device_class"
ENTITY_CONFIG_CATEGORY = "config_category"
ENTITY_NUMBER_MIN = "native_min_value"
ENTITY_NUMBER_MAX = "native_max_value"
ENTITY_NUMBER_STEP = "native_step"
ENTITY_NUMBER_UNIT = "native_unit_of_measurement"

# Auto reset
AUTO_RESET_NAME = "Auto Reset"
AUTO_RESET_NOTIFICATIONS_NAME = "Auto Reset Notifications"
AUTO_RESET_ICON = "mdi:restart-alert"
AUTO_RESET_NOTIFICATIONS_ICON = "mdi:message-alert"

AUTO_RESET_SERVER_SWITCH = "AutoResetServerSwitch"
AUTO_RESET_CAMERA_SWITCH = "AutoResetCameraSwitch"
AUTO_RESET_NUMBER = "AutoResetNumber"
PROBLEM_DETECTION_SWITCH = "ProblemDetectionSwitch"
PROBLEM_DETECTION_NAME = "Problem Detection"
PROBLEM_DETECTION_ICON = "mdi:cctv"
ATTR_PROBLEM_DETECTION = "problem_detection"
AUTO_RESET_SETTING = "auto_reset_setting"

AUTO_RESET_KEY_ENABLED = "enabled"
AUTO_RESET_KEY_NOTIFICATIONS = "notifications"
AUTO_RESET_KEY_CAMERAS = "cameras"
# Camera ids with Problem Detection turned off (kept apart from the auto
# reset values, so "Set all cameras back to these defaults" leaves it alone)
KEY_PROBLEM_DETECTION_OFF = "problem_detection_off"
AUTO_RESET_KEY_DELAY = "delay"
AUTO_RESET_KEY_ATTEMPTS = "attempts"
AUTO_RESET_KEY_INTERVAL = "interval"
# After the last reset failed: reboot the camera itself once
AUTO_RESET_KEY_REBOOT = "reboot"
AUTO_RESET_BOOL_KEYS = (AUTO_RESET_KEY_ENABLED, AUTO_RESET_KEY_REBOOT)

# Built-in defaults; the options flow can change them
AUTO_RESET_CAMERA_DEFAULTS = {
    AUTO_RESET_KEY_ENABLED: True,
    AUTO_RESET_KEY_DELAY: 30,  # seconds the problem must last first
    AUTO_RESET_KEY_ATTEMPTS: 3,
    AUTO_RESET_KEY_INTERVAL: 90,  # seconds between resets
    AUTO_RESET_KEY_REBOOT: False,
}

# Options keys holding the defaults
CONF_AUTO_RESET_DEFAULTS = {
    AUTO_RESET_KEY_ENABLED: "auto_reset_default_enabled",
    AUTO_RESET_KEY_DELAY: "auto_reset_default_delay",
    AUTO_RESET_KEY_ATTEMPTS: "auto_reset_default_attempts",
    AUTO_RESET_KEY_INTERVAL: "auto_reset_default_interval",
    AUTO_RESET_KEY_REBOOT: "auto_reset_default_reboot",
}
# Action, not stored: clear every camera's own values
CONF_AUTO_RESET_APPLY_DEFAULTS = "auto_reset_apply_defaults"
# Stored with the auto reset settings (same as the server switch), not in options
CONF_AUTO_RESET_NOTIFICATIONS = "auto_reset_notifications"
OPTION_SECTION_AUTO_RESET = "auto_reset"

# key: (min, max, step)
AUTO_RESET_LIMITS = {
    AUTO_RESET_KEY_DELAY: (30, 3600, 10),
    AUTO_RESET_KEY_ATTEMPTS: (1, 10, 1),
    AUTO_RESET_KEY_INTERVAL: (30, 900, 10),
}

# key, entity name suffix, unit, icon
AUTO_RESET_NUMBERS = [
    (AUTO_RESET_KEY_DELAY, "Delay", "s", "mdi:timer-sand"),
    (AUTO_RESET_KEY_ATTEMPTS, "Attempts", None, "mdi:counter"),
    (AUTO_RESET_KEY_INTERVAL, "Interval", "s", "mdi:timer-refresh-outline"),
]

AUTO_RESET_STATE_OFF = "off"
AUTO_RESET_STATE_PAUSED = "paused"
AUTO_RESET_STATE_IDLE = "idle"
AUTO_RESET_STATE_WAITING = "waiting"
AUTO_RESET_STATE_RESETTING = "resetting"
AUTO_RESET_STATE_GAVE_UP = "gave_up"
AUTO_RESET_STATE_REBOOTING = "rebooting"

ATTR_AUTO_RESET_STATE = "auto_reset_state"
ATTR_AUTO_RESET_ATTEMPTS = "auto_reset_attempts"
ATTR_AUTO_RESET_LAST = "auto_reset_last"
ATTR_AUTO_RESET_REBOOTED = "auto_reset_rebooted"

AUTO_RESET_EVENT = f"{DOMAIN}_auto_reset"
AUTO_RESET_EVENT_RESET = "reset"
AUTO_RESET_EVENT_RECOVERED = "recovered"
AUTO_RESET_EVENT_GAVE_UP = "gave_up"
AUTO_RESET_EVENT_REBOOT = "reboot"
AUTO_RESET_REBOOT_NAME = "Reboot"
AUTO_RESET_REBOOT_ICON = "mdi:power-cycle"

# In a camera's Notes (General tab in Blue Iris): turns Problem Detection off
NOTES_TAG_NO_DETECTION = "#ha:no-detection"

NEGATIVE_SENSOR_STATE = [SENSOR_CONNECTIVITY_NAME]
CAMERA_SENSORS = {
    SENSOR_MOTION_NAME: BinarySensorDeviceClass.MOTION,
    SENSOR_CONNECTIVITY_NAME: BinarySensorDeviceClass.CONNECTIVITY,
    SENSOR_EXTERNAL_NAME: BinarySensorDeviceClass.PRESENCE,
    SENSOR_DIO_NAME: BinarySensorDeviceClass.PLUG,
    SENSOR_AUDIO_NAME: BinarySensorDeviceClass.SOUND,
}

MQTT_MESSAGE_TRIGGER = "trigger"
MQTT_MESSAGE_TYPE = "type"
MQTT_MESSAGE_VALUE_UNKNOWN = "unknown"

MQTT_ALL_TOPIC = "BlueIris/+/Status"
DEFAULT_QOS = 0

CONFIG_OPTIONS = "options"
CONFIG_CONDITIONS = "conditions"
CONFIG_ITEMS = "items"

BI_CAMERA_ATTR_FPS = "FPS"
BI_CAMERA_ATTR_AUDIO_SUPPORT = "Audio Support"
BI_CAMERA_ATTR_WIDTH = "Width"
BI_CAMERA_ATTR_HEIGHT = "Height"
BI_CAMERA_ATTR_IS_ONLINE = "Is Online"
BI_CAMERA_ATTR_IS_RECORDING = "Is Recording"
BI_CAMERA_ATTR_ISSUE = "Issue"
BI_CAMERA_ATTR_ALERTS_HASH = "Alerts #"
BI_CAMERA_ATTR_TRIGGERS_HASH = "Triggers #"
BI_CAMERA_ATTR_CLIPS_HASH = "Clips #"
BI_CAMERA_ATTR_NO_SIGNAL_HASH = "No Signal #"
BI_CAMERA_ATTR_ERROR = "Error"
BI_CAMERA_ATTR_GROUP_CAMERAS = "Group Cameras"

BI_CAMERA_TYPE_GENERIC = -3
BI_CAMERA_TYPE_SYSTEM = -2
BI_CAMERA_TYPE_GROUP = -1
BI_CAMERA_TYPE_SCREEN_CAPTURE = 0
BI_CAMERA_TYPE_USB_FIREWIRE_ANALOG = 2
BI_CAMERA_TYPE_NETWORK_IP = 4
BI_CAMERA_TYPE_BROADCAST = 5

BI_CAMERA_TYPE_GENERIC_LABEL = "Camera"
BI_CAMERA_TYPE_SYSTEM_LABEL = "System Camera"
BI_CAMERA_TYPE_GROUP_LABEL = "Camera Group"
BI_CAMERA_TYPE_SCREEN_CAPTURE_LABEL = "Screen Capture Camera"
BI_CAMERA_TYPE_USB_FIREWIRE_ANALOG_LABEL = "USB, Firewire, or Analog Camera"
BI_CAMERA_TYPE_NETWORK_IP_LABEL = "Network IP Camera"
BI_CAMERA_TYPE_BROADCAST_LABEL = "Broadcast Camera"

CAMERA_TYPE_MAPPING: dict[int, str] = {
    BI_CAMERA_TYPE_GENERIC: BI_CAMERA_TYPE_GENERIC_LABEL,
    BI_CAMERA_TYPE_SYSTEM: BI_CAMERA_TYPE_SYSTEM_LABEL,
    BI_CAMERA_TYPE_GROUP: BI_CAMERA_TYPE_GROUP_LABEL,
    BI_CAMERA_TYPE_NETWORK_IP: BI_CAMERA_TYPE_NETWORK_IP_LABEL,
    BI_CAMERA_TYPE_BROADCAST: BI_CAMERA_TYPE_BROADCAST_LABEL,
    BI_CAMERA_TYPE_SCREEN_CAPTURE: BI_CAMERA_TYPE_SCREEN_CAPTURE_LABEL,
    BI_CAMERA_TYPE_USB_FIREWIRE_ANALOG: BI_CAMERA_TYPE_USB_FIREWIRE_ANALOG_LABEL,
}

ATTR_BLUE_IRIS_CAMERA = {
    "optionDisplay": CONF_NAME,
    "optionValue": CONF_ID,
    "FPS": BI_CAMERA_ATTR_FPS,
    "audio": BI_CAMERA_ATTR_AUDIO_SUPPORT,
    "width": BI_CAMERA_ATTR_WIDTH,
    "height": BI_CAMERA_ATTR_HEIGHT,
    "isOnline": BI_CAMERA_ATTR_IS_ONLINE,
    "isRecording": BI_CAMERA_ATTR_IS_RECORDING,
    "isYellow": BI_CAMERA_ATTR_ISSUE,
    "nAlerts": BI_CAMERA_ATTR_ALERTS_HASH,
    "nTriggers": BI_CAMERA_ATTR_TRIGGERS_HASH,
    "nClips": BI_CAMERA_ATTR_CLIPS_HASH,
    "nNoSignal": BI_CAMERA_ATTR_NO_SIGNAL_HASH,
    "error": BI_CAMERA_ATTR_ERROR,
    "ip": "IP",
    "group": BI_CAMERA_ATTR_GROUP_CAMERAS,
}
ATTR_BLUE_IRIS_STATUS = [
    "system name",
    "version",
    "license",
    "support",
    "user",
    "latitude",
    "longitude",
]

BI_DISCOVERY = f"{DOMAIN}_discovery"
BI_DISCOVERY_BINARY_SENSOR = f"{BI_DISCOVERY}_{DOMAIN_BINARY_SENSOR}"
BI_DISCOVERY_CAMERA = f"{BI_DISCOVERY}_{DOMAIN_CAMERA}"
BI_DISCOVERY_SWITCH = f"{BI_DISCOVERY}_{DOMAIN_SWITCH}"

BI_UPDATE_SIGNAL_CAMERA = f"{DOMAIN}_{DOMAIN_CAMERA}_UPDATE_SIGNAL"
BI_UPDATE_SIGNAL_BINARY_SENSOR = f"{DOMAIN}_{DOMAIN_BINARY_SENSOR}_UPDATE_SIGNAL"
BI_UPDATE_SIGNAL_SWITCH = f"{DOMAIN}_{DOMAIN_SWITCH}_UPDATE_SIGNAL"
BI_UPDATE_SIGNAL_SENSOR = f"{DOMAIN}_{DOMAIN_SENSOR}_UPDATE_SIGNAL"
BI_UPDATE_SIGNAL_BUTTON = f"{DOMAIN}_{DOMAIN_BUTTON}_UPDATE_SIGNAL"
BI_UPDATE_SIGNAL_NUMBER = f"{DOMAIN}_{DOMAIN_NUMBER}_UPDATE_SIGNAL"
BI_UPDATE_SIGNAL_SELECT = f"{DOMAIN}_{DOMAIN_SELECT}_UPDATE_SIGNAL"

CONFIG_FIELDS = {
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_PORT): str,
    vol.Optional(CONF_SSL, default=False): bool,
    vol.Optional(CONF_USERNAME): str,
    vol.Optional(CONF_PASSWORD): str,
}

SUPPORTED_DOMAINS = [
    DOMAIN_SWITCH,
    DOMAIN_BINARY_SENSOR,
    DOMAIN_CAMERA,
    DOMAIN_SENSOR,
    DOMAIN_BUTTON,
    DOMAIN_NUMBER,
    DOMAIN_SELECT,
]
SIGNALS = {
    DOMAIN_BINARY_SENSOR: BI_UPDATE_SIGNAL_BINARY_SENSOR,
    DOMAIN_CAMERA: BI_UPDATE_SIGNAL_CAMERA,
    DOMAIN_SWITCH: BI_UPDATE_SIGNAL_SWITCH,
    DOMAIN_SENSOR: BI_UPDATE_SIGNAL_SENSOR,
    DOMAIN_BUTTON: BI_UPDATE_SIGNAL_BUTTON,
    DOMAIN_NUMBER: BI_UPDATE_SIGNAL_NUMBER,
    DOMAIN_SELECT: BI_UPDATE_SIGNAL_SELECT,
}

ENTITY_ID = "id"
ENTITY_NAME = "name"
ENTITY_STATE = "state"
ENTITY_ATTRIBUTES = "attributes"
ENTITY_ICON = "icon"
ENTITY_UNIQUE_ID = "unique-id"
ENTITY_EVENT = "event-type"
ENTITY_TOPIC = "topic"
ENTITY_BINARY_SENSOR_DEVICE_CLASS = "binary-sensor-device-class"
ENTITY_DEVICE_NAME = "device-name"
ENTITY_CAMERA_DETAILS = "camera-details"
ENTITY_BINARY_SENSOR_TYPE = "binary-sensor-type"
ENTITY_DISABLED = "disabled"


ENTITY_STATUS = "entity-status"
ENTITY_STATUS_EMPTY = None
ENTITY_STATUS_READY = f"{ENTITY_STATUS}-ready"
ENTITY_STATUS_CREATED = f"{ENTITY_STATUS}-created"
ENTITY_STATUS_MODIFIED = f"{ENTITY_STATUS}-modified"
ENTITY_STATUS_IGNORE = f"{ENTITY_STATUS}-ignore"
ENTITY_STATUS_CANCELLED = f"{ENTITY_STATUS}-cancelled"

CONF_CLEAR_CREDENTIALS = "clear-credentials"
CONF_GENERATE_CONFIG_FILES = "generate-config-files"
CONF_ACTIONS = "actions"

OPTION_MODE_ALL = "all"
OPTION_MODE_NONE = "none"
OPTION_MODE_CUSTOM = "custom"
OPTION_ITEMS = "items"
OPTION_SECTION_CONNECTION = "connection"
OPTION_SECTION_GENERAL = "general"
OPTION_SECTION_CAMERAS = "cameras"
OPTION_SECTION_MQTT_SENSORS = "mqtt_sensors"
OPTION_SECTION_SWITCHES = "profiles_schedules"
OPTION_SECTION_SERVER = "server"
OPTION_SECTION_CAMERA_CONTROLS = "camera_controls"

# Server controls: key -> options key (all on by default)
SERVER_CONTROL_SHIELD = "shield"
SERVER_CONTROL_PROFILE_HOLD = "profile_hold"
SERVER_CONTROL_RESTART_WEB = "restart_web_server"
SERVER_CONTROL_RESTART_AI = "restart_ai"
CONF_SERVER_CONTROLS = {
    SERVER_CONTROL_SHIELD: "server_control_shield",
    SERVER_CONTROL_PROFILE_HOLD: "server_control_profile_hold",
    SERVER_CONTROL_RESTART_WEB: "server_control_restart_web_server",
    SERVER_CONTROL_RESTART_AI: "server_control_restart_ai",
}
SERVER_CONTROL = "ServerControl"
SERVER_CONTROL_KEY = "server_control"

# status 'signal'
SHIELD_OPTIONS = {"Disarmed": 0, "Armed": 1, "Arming": 2}
# status 'lock' as documented in the status reply: 0 run, 1 hold, 2 temp
PROFILE_LOCK_RUN = 0
PROFILE_LOCK_HOLD = 1
PROFILE_LOCK_TEMP = 2
PROFILE_LOCK_NAMES = {0: "run", 1: "hold", 2: "temporary"}

# Blue Iris log -> blueiris_log event and Last Message sensor
OPTION_SECTION_LOG = "blue_iris_log"
CONF_LOG_EVENTS = "log_events"
CONF_LOG_MIN_LEVEL = "log_min_level"
LOG_MIN_LEVELS = {"warning": 1, "error": 2}
DEFAULT_LOG_MIN_LEVEL = "warning"
BI_LOG_LEVELS = {0: "info", 1: "warning", 2: "error", 10: "user"}
BI_LOG_EVENT = f"{DOMAIN}_log"

# Camera controls (admin user): key -> options key
CAMERA_CONTROL_ENABLE = "enable"
CAMERA_CONTROL_PAUSE = "pause"
CAMERA_CONTROL_MANREC = "manrec"
CAMERA_CONTROL_SNAPSHOT = "snapshot"
CAMERA_CONTROL_MOTION = "motion"
CAMERA_CONTROL_REBOOT = "reboot"
CONF_CAMERA_CONTROLS = {
    CAMERA_CONTROL_ENABLE: "allowed_camera_enable",
    CAMERA_CONTROL_PAUSE: "allowed_camera_pause",
    CAMERA_CONTROL_MANREC: "allowed_camera_manrec",
    CAMERA_CONTROL_SNAPSHOT: "allowed_camera_snapshot",
    CAMERA_CONTROL_MOTION: "allowed_camera_motion",
    CAMERA_CONTROL_REBOOT: "allowed_camera_reboot",
}
# None by default (opt-in); All is then stored explicitly as null
CAMERA_CONTROLS_DEFAULT_OFF = {CAMERA_CONTROL_MOTION, CAMERA_CONTROL_REBOOT}

# Camera sensors (from camlist, no admin needed): key -> options key
OPTION_SECTION_CAMERA_SENSORS = "camera_sensors"
CAMERA_SENSOR_BITRATE = "bitrate"
CAMERA_SENSOR_LAST_ALERT = "last_alert"
CAMERA_SENSOR_RECORDING = "recording"
CAMERA_SENSOR_TRIGGERED = "triggered"
CAMERA_SENSOR_ALERTING = "alerting"
CONF_CAMERA_SENSORS = {
    CAMERA_SENSOR_BITRATE: "allowed_camera_bitrate",
    CAMERA_SENSOR_LAST_ALERT: "allowed_camera_last_alert",
    CAMERA_SENSOR_RECORDING: "allowed_camera_recording",
    CAMERA_SENSOR_TRIGGERED: "allowed_camera_triggered",
    CAMERA_SENSOR_ALERTING: "allowed_camera_alerting",
}
CAMERA_SENSORS_DEFAULT_OFF = {
    CAMERA_SENSOR_RECORDING,
    CAMERA_SENSOR_TRIGGERED,
    CAMERA_SENSOR_ALERTING,
}
# binary sensor: camlist field, name suffix, icon
CAMERA_STATE_SENSORS = {
    CAMERA_SENSOR_RECORDING: ("isRecording", "Recording", "mdi:record-rec"),
    CAMERA_SENSOR_TRIGGERED: ("isTriggered", "Triggered", "mdi:motion-sensor"),
    CAMERA_SENSOR_ALERTING: ("isAlerting", "Alerting", "mdi:bell-ring-outline"),
}
CAMERA_SENSOR = "CameraSensor"

DEFAULT_OFF_OPTION_KEYS = {
    *(CONF_CAMERA_CONTROLS[k] for k in CAMERA_CONTROLS_DEFAULT_OFF),
    *(CONF_CAMERA_SENSORS[k] for k in CAMERA_SENSORS_DEFAULT_OFF),
}

CAMERA_CONTROL = "CameraControl"
CAMERA_CONTROL_KEY = "camera_control"

# key: (entity name suffix, domain, icon, config category)
CAMERA_CONTROL_ENTITIES = {
    CAMERA_CONTROL_ENABLE: ("Enabled", "switch", "mdi:cctv", True),
    CAMERA_CONTROL_PAUSE: ("Pause", "select", "mdi:pause-circle-outline", False),
    CAMERA_CONTROL_MANREC: ("Manual Recording", "switch", "mdi:record-rec", False),
    CAMERA_CONTROL_SNAPSHOT: (
        "Snapshot to Database",
        "button",
        "mdi:camera-plus-outline",
        False,
    ),
    CAMERA_CONTROL_MOTION: ("Motion Detection", "switch", "mdi:motion-sensor", True),
    CAMERA_CONTROL_REBOOT: ("Reboot", "button", "mdi:restart", True),
}
MOTION_REFRESH_INTERVAL = timedelta(minutes=5)

# Pause choices -> Blue Iris pause value (values other than 0 / -1 ADD time)
PAUSE_OFF = "Off"
PAUSE_INDEFINITELY = "Indefinitely"
PAUSE_OPTIONS = {
    PAUSE_OFF: 0,
    "30 seconds": 1,
    "5 minutes": 2,
    "15 minutes": 10,
    "30 minutes": 3,
    "1 hour": 4,
    "2 hours": 5,
    "3 hours": 6,
    "5 hours": 7,
    "10 hours": 8,
    "24 hours": 9,
    PAUSE_INDEFINITELY: -1,
}

# Page 1 section of each All / None / Choose category; collapsed or not
CATEGORY_SECTIONS = {
    CONF_ALLOWED_CAMERA: OPTION_SECTION_CAMERAS,
    CONF_ALLOWED_PROBLEM_SENSOR: OPTION_SECTION_CAMERAS,
    CONF_ALLOWED_MOTION_SENSOR: OPTION_SECTION_MQTT_SENSORS,
    CONF_ALLOWED_CONNECTIVITY_SENSOR: OPTION_SECTION_MQTT_SENSORS,
    CONF_ALLOWED_AUDIO_SENSOR: OPTION_SECTION_MQTT_SENSORS,
    CONF_ALLOWED_DIO_SENSOR: OPTION_SECTION_MQTT_SENSORS,
    CONF_ALLOWED_EXTERNAL_SENSOR: OPTION_SECTION_MQTT_SENSORS,
    CONF_ALLOWED_PROFILE: OPTION_SECTION_SWITCHES,
    CONF_ALLOWED_SCHEDULE: OPTION_SECTION_SWITCHES,
    **{key: OPTION_SECTION_CAMERA_CONTROLS for key in CONF_CAMERA_CONTROLS.values()},
    **{key: OPTION_SECTION_CAMERA_SENSORS for key in CONF_CAMERA_SENSORS.values()},
}
SECTION_COLLAPSED = {
    OPTION_SECTION_CAMERAS: False,
    OPTION_SECTION_CAMERA_CONTROLS: True,
    OPTION_SECTION_CAMERA_SENSORS: True,
    OPTION_SECTION_MQTT_SENSORS: True,
    OPTION_SECTION_SWITCHES: True,
}

# Server status sensors: key -> options key (all on by default)
SERVER_SENSOR_CPU = "cpu"
SERVER_SENSOR_MEMORY = "memory"
SERVER_SENSOR_DISKS = "disks"
SERVER_SENSOR_WARNINGS = "warnings"
SERVER_SENSOR_CONNECTIONS = "connections"
CONF_SERVER_SENSORS = {
    SERVER_SENSOR_CPU: "server_sensor_cpu",
    SERVER_SENSOR_MEMORY: "server_sensor_memory",
    SERVER_SENSOR_DISKS: "server_sensor_disks",
    SERVER_SENSOR_WARNINGS: "server_sensor_warnings",
    SERVER_SENSOR_CONNECTIONS: "server_sensor_connections",
}

DOMAIN_LOAD = "load"
DOMAIN_UNLOAD = "unload"

CONF_CONTENT_TYPE = "content_type"
CONF_LIMIT_REFETCH_TO_URL_CHANGE = "limit_refetch_to_url_change"
CONF_STILL_IMAGE_URL = "still_image_url"
CONF_STREAM_SOURCE = "stream_source"
CONF_FRAMERATE = "framerate"

LOG_LEVEL_DEFAULT = "Default"
LOG_LEVEL_DEBUG = "Debug"
LOG_LEVEL_INFO = "Info"
LOG_LEVEL_WARNING = "Warning"
LOG_LEVEL_ERROR = "Error"

LOG_LEVEL_SELECT_OPTIONS = [
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    LOG_LEVEL_ERROR,
]
LOG_LEVEL_NAME = "Log Level"
LOG_LEVEL_ICON = "mdi:text-box-search-outline"
INTEGRATION_LOGGER = f"custom_components.{DOMAIN}"

LOG_LEVELS = [
    LOG_LEVEL_DEFAULT,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    LOG_LEVEL_ERROR,
]

CONF_STREAM_TYPE = "stream-type"
STREAM_TYPE_H264 = "H264"
STREAM_TYPE_H264_TS = "H264 TS"
STREAM_TYPE_MJPG = "MJPEG"

DEFAULT_STREAM_TYPE = STREAM_TYPE_H264

STREAM_VIDEO = {
    STREAM_TYPE_H264: {"file_name": "temp.m3u8", "stream_name": "h264"},
    STREAM_TYPE_H264_TS: {"file_name": "temp.ts", "stream_name": "h264"},
    STREAM_TYPE_MJPG: {"stream_name": "mjpg"},
}

STREAM_CONTENT_TYPE = {
    STREAM_TYPE_H264: "video/H264",
    STREAM_TYPE_H264_TS: "video/MP2T",
    STREAM_TYPE_MJPG: "image/jpg",
}

COMPONENTS_TEMPLATE = {
    "input_select": {
        "camera": {"name": "", "initial": "", "icon": "mdi:camera", "options": []},
        "cast_devices": {"name": "", "icon": "mdi:cast", "options": []},
    },
    "script": {
        "cast": {
            "alias": "",
            "sequence": [
                {
                    "service": "media_player.play_media",
                    "data_template": {
                        "media_content_type": "",
                        "entity_id": "",
                        "media_content_id": "",
                    },
                }
            ],
        }
    },
}

LOVELACE_TEMPLATE = {"cards": []}

DEVICE_INFO_KEYS = [
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_STREAM,
    CONF_STILL_IMAGE_URL,
    CONF_CONTENT_TYPE,
    CONF_VERIFY_SSL,
    CONF_USERNAME,
    CONF_PASSWORD,
]
