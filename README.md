# Blue Iris (Ltek)

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Ltek&repository=ha-blueiris&category=integration)

Home Assistant integration for Blue Iris Video Security Software, polling the Blue Iris JSON API and listening to its MQTT events.

Ltek fork of [elad-bar/ha-blueiris](https://github.com/elad-bar/ha-blueiris). It keeps the same `blueiris` domain, so it replaces an existing install in place with the same entities. Fork changes are also offered upstream as PRs.

Current build: **v2026.10.24.35** · full history in [CHANGELOG.md](CHANGELOG.md)

## Features

- **Camera** per Blue Iris camera, group and system camera (All, Cycle), with live attributes (FPS, online, no signal count, error, ...)
- **Streams**: H264 (HLS), H264 TS or MJPEG, optionally through the Home Assistant stream component
- **Problem binary sensor** per camera: on when Blue Iris reports no signal, offline or a stalled stream
- **Reset button** per camera
- **Camera sensors** per camera: Bitrate (main and sub stream), Last Alert; optional Recording, Triggered, Alerting
- **Camera controls** per camera: Enabled, Pause, Manual Recording, Snapshot to Database; optional Motion Detection and Reboot
- **Auto reset** per camera: resets cameras whose Problem sensor stays on, with per-camera delay / attempts / interval you can change live
- **Binary sensors** per camera from MQTT: Motion, Audio, Connectivity, DIO, External, plus a server-level Alerts sensor
- **Sensors** for the server: Connection Health, Uptime, CPU, Memory, free space per drive, Warnings, Connections
- **Switches** for Blue Iris profiles and schedules (admin user required)
- **Server controls**: Shield (Armed / Disarmed / Arming), Profile Hold, Restart Web Server, Restart AI
- **Blue Iris log**: new warnings and errors as `blueiris_log` events and a Last Message sensor
- **Services**: Trigger Camera, Move to Preset, Reset Camera, Snapshot to Database, Current Camera Snapshot
- **Log Level** select on the server device to see and change the log level live
- **Diagnostics** download for bug reports
- SSL with self-signed certificates

## New in this fork

- Problem binary sensor per camera (no signal / offline / stalled), computed from Blue Iris' own camera status on every poll and unavailable while the server is down or just started, so it never acts on stale data
- Reset button per camera
- Auto reset: per-camera switch plus Delay, Attempts and Interval numbers, changed live without a reload and kept across restarts; persistent notification per camera and a `blueiris_auto_reset` event
- `blueiris.reset_camera` service: resets (reconnects) a frozen or "No signal" camera, the same as Blue Iris' Reset command. Raises an error with Blue Iris' reason when it fails
- `blueiris.current_camera_snapshot` service: saves the current still to `media/blueiris/` and returns a `/media/local` URL for notifications
- Connection Health sensor: `connected`, `server_unreachable`, `auth_failed` or `error`, so automations can ignore stale camera data while the server is down
- Uptime sensor: Blue Iris software uptime, e.g. to hold off automations right after a Blue Iris restart
- `H264 TS` stream type (`temp.ts`), which can work better for group and cycle cameras
- Diagnostics download with host, credentials, session and location redacted
- Easier options: All / None / Choose… per section with item counts, checkbox lists instead of drop-downs, and new cameras included automatically under All

## How to

#### Requirements

- BlueIris Server available with a user
- To control profiles and schedules, and to use Reset Camera, the user must have 'admin' level permissions
- MQTT Integration is optional - it will allow listening to BlueIris events
- Read the [BlueIris manual](docs/blueiris-server.md) for this component

#### Installations via HACS

Click the button at the top, or in HACS → ⋮ → Custom repositories add `https://github.com/Ltek/ha-blueiris` as an **Integration**, then download "Blue Iris (Ltek)" and restart Home Assistant.

Replacing an existing elad-bar install: remove that repository inside HACS first (do not delete the integration under Settings → Devices & Services), then add this one. The config entry and entities carry over.

#### Integration settings

###### Basic configuration (Configuration -> Integrations -> Add BlueIris)

| Fields name | Type      | Required | Default   | Description                                   |
| ----------- | --------- | -------- | --------- | --------------------------------------------- |
| Host        | Texbox    | +        | None      | Hostname or IP address of the BlueIris server |
| Port        | Textbox   | +        | 0         | HTTP Port to access BlueIris server           |
| SSL         | Check-box | +        | Unchecked | Is SSL supported?                             |
| Username    | Textbox   | -        |           | Username of admin user for BlueIris server    |
| Password    | Textbox   | -        |           | Password of admin user for BlueIris server    |

###### Integration options (Settings -> Devices & Services -> BlueIris -> Configure)

The options are two pages.

**Setup.** After the server details, setup shows a *Blue Iris features* page with the Server sensors and the Auto reset defaults. Everything per camera is set in Configure afterwards.

**Page 1 - which components to create.** The choices are grouped into sections: *Cameras* (camera and Problem sensors, open), *MQTT sensors* and *Profiles and schedules* (collapsed, shown only when they apply). Each choice has a drop-down with three choices; the labels show how many items the section has and how many are currently selected, e.g. `Choose… (3 of 15 selected)`:

| Choice    | Effect                                                                                  |
| --------- | --------------------------------------------------------------------------------------- |
| All (n)   | Creates the component for every item, including cameras added to Blue Iris later        |
| None (0)  | Turns the section off; no entities are created for it                                    |
| Choose…   | Opens a checkbox list for that section on page 2                                         |

| Section              | Items                                    | Shown when                     |
| -------------------- | ---------------------------------------- | ------------------------------ |
| Camera controls      | One choice per control (see Camera controls); cameras, not groups | User has admin rights |
| Camera sensors       | One choice per sensor (see Camera sensors); cameras, not groups | Always |
| Camera components    | All cameras, groups and system cameras   | Always                         |
| Problem sensors      | Cameras (not groups or system cameras)   | Always                         |
| Motion sensors       | Non-system cameras                       | MQTT integration is set up     |
| Connectivity sensors | Non-system cameras                       | MQTT integration is set up     |
| Audio sensors        | Non-system cameras that support audio    | MQTT integration is set up     |
| DIO sensors          | Non-system cameras                       | MQTT integration is set up     |
| External sensors     | Non-system cameras                       | MQTT integration is set up     |
| Profile switches     | Blue Iris profiles                       | User has admin rights          |
| Schedule switches    | Blue Iris schedules                      | User has admin rights          |

A section that is not shown keeps its saved setting.

Collapsed groups below hold the other settings:

| Group               | Fields                                                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Server              | Sensors: CPU, Memory, Free space per drive, Warnings, Connections. Controls: Shield, Profile Hold, Restart Web Server, Restart AI. Each on / off, all on by default |
| Blue Iris log       | Report Blue Iris log messages (on), Report: Warnings and errors / Errors only                                              |
| Auto reset defaults | Persistent notifications, On by default, Delay, Attempts, Interval, Set all cameras back to these defaults (admin user only) |
| Connection          | Host, Port, SSL, Username, Password, Clear credentials (workaround to clear the username and password; not stored as option) |
| Streams and logging | Stream type (H264 / H264 TS / MJPEG), Stream support (requires restart), Log level - Default on Startup, Generate configuration files |

**Page 2 - choose items.** Only appears when at least one section is set to `Choose…`. Each of those sections is a group with a checkbox per item, pre-filled with the current selection.

**Integration's title**
Title will be extracted from BlueIris server's configuration, it will be set upon adding the server, and after every Option's change

Note that in case there are 2 integrations with the same integration's title, components will be overwritten by both integrations.

**Log level**

- *Log level - Default on Startup* (options, Streams and logging) is applied every time Home Assistant starts or the integration reloads. `Default` keeps Home Assistant's own logging setup (normally Warning, or whatever `logger:` in `configuration.yaml` says)
- The server's **Log Level** entity (`select.<server>_log_level`, Configuration section of the server device) shows the level actually in effect, including changes made with HA's *Enable debug logging* or `logger.set_level`, and changes it immediately without a reload. It is not saved: the next restart goes back to the Default on Startup level, so a forgotten Debug setting doesn't keep filling the log
- Neither needs the `logger:` integration

###### Auto-generating configurations files:

Will create YAML with all the configurations in the config directory under blueiris.advanced_configurations.yaml:

- Input select (drop-downs)
- Script to cast based on the selection
- UI of all the components created by BlueIris based on the description above

[Example of configuration output](docs/configs/casting/configuration.yaml)

###### Configuration validations

After submitting the form either for a new integration instance or updating options, the component will try to login to the BlueIris server to verify the new settings.

The following errors can appear:

- BlueIris integration ({host}) already configured
- Invalid administrator credentials - credentials are invalid or user is not an admin
- Invalid server details - Cannot reach the server

###### Diagnostics

Settings -> Devices & Services -> BlueIris -> ⋮ -> Download diagnostics produces a JSON file for bug reports: login state, server version and status, the stream-related fields of every camera (online, no signal, FPS, error) and the entity list. Host, username, password, session ID, license, location and stream / image URLs are redacted.

###### Encryption key got corrupted

If a persistent notification popped up with the following message:

```
Encryption key got corrupted, please remove the integration and re-add it
```

It means that the encryption key was modified from outside the code and the integration will need to be removed and re-added.

## Components

###### Binary Sensor - Alerts

Represents whether there is an active alert or not

| Attributes         |
| ------------------ |
| Active alerts #    |
| System name        |
| Version            |
| License            |
| Support expiration |
| Logged in User     |
| Latitude           |
| Longitude          |

###### Binary Sensor - Connectivity - Non-system-camera

Represents whether the camera is online or not (based on MQTT message)

###### Binary Sensor - Audio - Non-system-camera and camera supports audio

Represents whether the camera is triggered for noise or not (based on MQTT message)

###### Binary Sensor - Motion - Non-system-camera

Represents whether the camera is triggered for motion or not (based on MQTT message)

###### Binary Sensor - DIO - Non-system-camera

Represents whether the camera is triggered for digital I/O event or not (based on MQTT message)

###### Binary Sensor - External - Non-system-camera

Represents whether the camera is triggered for external / ONVIF event or not (based on MQTT message)

###### Binary Sensor - Problem - Per camera (not groups or system cameras)

On when the camera needs attention, computed from Blue Iris' camera list on every poll (not MQTT):

| Reason      | Condition                                       |
| ----------- | ----------------------------------------------- |
| `no_signal` | Blue Iris reports No Signal                     |
| `offline`   | Camera is not online                            |
| `stalled`   | Online but below 1 FPS                          |

Disabled and paused cameras never count as a problem. The sensor is **unavailable** while the server is not `connected` (see Connection Health) and for the first 5 minutes after Blue Iris starts, so it never reports stale or settling data. It also adds the camera to the server's Alerts sensor while on.

| Attributes      |
| --------------- |
| camera_id       |
| problem_detection |
| reason          |
| since           |
| fps             |
| is_online       |
| no_signal       |
| no_signal_count |
| error           |

A camera that keeps sending the same frame at a normal frame rate cannot be detected.

**Problem Detection switch** (`switch.<camera>_problem_detection`, Configuration section of the camera's device, on by default). Turn it off for cameras on battery or solar power, or that only stream when motion is detected: they look "down" most of the time by design, and reconnect attempts can wake them and drain the battery. While it is off, the camera's Problem sensor stays `off` with `problem_detection: false`, it is left out of the Alerts sensor, and auto reset never touches it. Takes effect at once, is kept across restarts and is not changed by *Set all cameras back to these defaults*. Also turn off that camera's Watchdog in Blue Iris.

###### Button - Reset - Per camera (admin user)

Resets (reconnects) the camera, the same as the Reset Camera service. Created for cameras that have a camera entity.

###### Auto reset (admin user)

Resets a camera automatically when its Problem sensor stays on.

**Defaults** are set in the options (Configure -> *Auto reset defaults*) and used by every camera you haven't changed on its own:

| Default                | Built-in | Range       |
| ---------------------- | -------- | ----------- |
| Auto reset on          | On       | On / Off    |
| Delay before the first reset | 30 s | 30 - 3600 s |
| Attempts               | 3        | 1 - 10      |
| Interval between resets | 90 s    | 30 - 900 s  |

*Set all cameras back to these defaults* in the same section clears every camera's own values (it runs once and is not saved).

**Per camera**, the entities on its device (Configuration section) override the defaults for that camera only, value by value. Changes apply from the next poll (within 30 s) without a reload, and are kept across restarts. A camera keeps following the defaults for any value you haven't changed on it.

Problems are seen on the 30 s poll, so the first reset comes 30 - 60 s after a camera fails with the 30 s delay.

| Entity                                | Default | Range         | Meaning                                    |
| ------------------------------------- | ------- | ------------- | ------------------------------------------ |
| `switch.<camera>_auto_reset`          | default | -             | Auto reset this camera                     |
| `number.<camera>_auto_reset_delay`    | default | 30 - 3600 s   | How long the problem must last first       |
| `number.<camera>_auto_reset_attempts` | default | 1 - 10        | Resets before giving up                    |
| `number.<camera>_auto_reset_interval` | default | 30 - 900 s    | Wait after each reset before the next one  |

On the server device:

| Entity                               | Meaning                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `switch.<server>_auto_reset`         | Master switch; off pauses auto reset for every camera               |
| `switch.<server>_auto_reset_notifications` | Persistent notifications on / off                            |

How it works, on every successful poll:

1. Problem for at least *Delay* -> reset; then up to *Attempts* resets, *Interval* apart
2. Problem clears -> **recovered**
3. Still on *Interval* after the last attempt -> **gave up**; no more resets until the problem clears and comes back

It pauses while Connection Health is not `connected` and for the first 5 minutes of Blue Iris uptime, so an outage or a Blue Iris restart never triggers resets. Progress is on the Problem sensor (`auto_reset_state`: off, paused, idle, waiting, resetting, gave_up; `auto_reset_attempts`; `auto_reset_last`). After a Home Assistant restart the count starts over.

Each camera gets one persistent notification (camera, problem, since, then the outcome), updated in place. Turn them off with *Persistent notifications* in Configure -> Auto reset defaults, or the server's Auto Reset Notifications switch (both are the same setting).

Every step also fires the event `blueiris_auto_reset` with `type` (`reset`, `recovered`, `gave_up`), `camera_id`, `camera_name`, `entity_id` (the camera entity), `reason`, `since`, `attempt`, `max_attempts` and `error`. For a phone alert with a snapshot when a camera gives up:

```yaml
triggers:
  - trigger: event
    event_type: blueiris_auto_reset
    event_data:
      type: gave_up
actions:
  - action: blueiris.current_camera_snapshot
    target:
      entity_id: "{{ trigger.event.data.entity_id }}"
    response_variable: snap
    continue_on_error: true
  - action: notify.mobile_app_phone
    data:
      title: "Blue Iris: {{ trigger.event.data.camera_name }} still down"
      message: "{{ trigger.event.data.reason }} after {{ trigger.event.data.attempt }} resets"
```

Blue Iris has its own per-camera Watchdog (camera properties) for signal loss. If it is on, give it a shorter timeout than the auto reset delay, or turn one of them off for that camera.

###### Camera sensors

Per camera (not groups or system cameras), from Blue Iris' camera list on every poll. Choose which cameras get each sensor in Configure -> Camera sensors.

| Entity                                     | Default | Value                                                                     |
| ------------------------------------------ | ------- | ------------------------------------------------------------------------- |
| `sensor.<camera>_bitrate`                  | All     | Main stream, kbit/s (Blue Iris sends bytes/s); attributes fps, width, height (diagnostic) |
| `sensor.<camera>_substream_bitrate`        | All     | Same for the sub stream; only for cameras that have one (diagnostic)      |
| `sensor.<camera>_last_alert`               | All     | Time of the most recent alert; attributes new_alerts, alerts, triggers, clips, record |
| `binary_sensor.<camera>_recording`         | None    | Recording                                                                 |
| `binary_sensor.<camera>_triggered`         | None    | Triggered                                                                 |
| `binary_sensor.<camera>_alerting`          | None    | Sending an alert                                                          |

Recording, Triggered and Alerting come from the 30 s poll, so short events can be missed; the MQTT Motion sensors are better for motion.

###### Camera controls (admin user)

Per camera (not groups or system cameras), on its device page. Choose which cameras get each control in Configure -> Camera controls.

| Entity                                   | Default | What it does                                                              |
| ---------------------------------------- | ------- | ------------------------------------------------------------------------- |
| `switch.<camera>_enabled`                | All     | Enables / disables the camera in Blue Iris (Configuration)                |
| `select.<camera>_pause`                  | All     | Off, 30 s ... 24 h, Indefinitely; attributes `remaining` (s) and `until`. Shows unknown while a timed pause set elsewhere runs |
| `switch.<camera>_manual_recording`       | All     | Starts / stops manual recording                                           |
| `button.<camera>_snapshot_to_database`   | All     | Saves a snapshot into Blue Iris' clips database (its timeline / UI3), not a file in Home Assistant |
| `switch.<camera>_motion_detection`       | None    | Motion detection for the camera's active profile; read every 5 minutes (Configuration) |
| `button.<camera>_reboot`                 | None    | Reboots the camera itself; only for cameras that support it through Blue Iris (Configuration) |

Changes are sent to Blue Iris at once and read back straight away. Errors from Blue Iris show as an error on the action, with Blue Iris' reason.

###### Camera

State: Idle

| Attributes                                      |
| ----------------------------------------------- |
| FPS                                             |
| Audio support                                   |
| Width                                           |
| Height                                          |
| Is Online                                       |
| Is Recording                                    |
| Issue (Camera is yellow)                        |
| Alerts #                                        |
| Triggers #                                      |
| Clips #                                         |
| No Signal #                                     |
| Error                                           |
| Group Cameras (list of camera names if a group) |
| IP                                              |

The camera's device page has a **Visit** link to `http://<camera IP>` (the camera's own web interface), when Blue Iris reports an IP.

###### Sensor - Connection Health

Health of the connection to the Blue Iris server, refreshed on every poll. Useful to keep automations from acting on stale camera data while the server is down.

| State                | Meaning                                                   |
| -------------------- | --------------------------------------------------------- |
| `connecting`         | No poll has completed yet                                 |
| `connected`          | Last poll succeeded                                       |
| `server_unreachable` | Blue Iris did not respond                                 |
| `auth_failed`        | Blue Iris responded but the login was rejected            |
| `error`              | Logged in, but Blue Iris returned a failure for a request |

| Attributes           |
| -------------------- |
| last_update_success  |
| last_success_time    |
| consecutive_failures |
| is_logged_in         |
| bi_version           |
| profile              |
| schedule             |

###### Sensors - Server status

From Blue Iris' status on every poll, each can be turned off in Configure -> Server sensors:

| Sensor                      | Value                                                                  |
| --------------------------- | ---------------------------------------------------------------------- |
| `sensor.<server>_cpu`       | CPU use (%)                                                            |
| `sensor.<server>_memory`    | System memory in use (%); attributes Blue Iris RAM and installed RAM   |
| `sensor.<server>_disk_<drive>_free` | Free space per drive (GiB); attributes allocated, used, total, free %, and the raw values Blue Iris sent |
| `sensor.<server>_warnings`  | Warnings on Blue Iris' Messages page                                   |
| `sensor.<server>_connections` | Active web server connections (diagnostic)                           |

###### Server controls (admin user)

| Entity                          | What it does                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| `select.<server>_shield`        | Blue Iris' shield: Armed (green), Disarmed (red), Arming (yellow)                    |
| `switch.<server>_profile_hold`  | On holds the current profile; off lets the schedule run. Attribute `lock`: run, hold or temporary |
| `button.<server>_restart_web_server` | Restarts Blue Iris' web server (Configuration). The integration logs in again on the next poll |
| `button.<server>_restart_ai`    | Restarts Blue Iris' AI (Configuration)                                               |

Each can be turned off in Configure -> Server.

###### Blue Iris log (admin user)

New Blue Iris log messages are read on every poll. Each warning or error (or errors only, see Configure -> Blue Iris log) fires the event `blueiris_log` with `level`, `object` (camera or part of Blue Iris), `message`, `time` and `count`, and updates `sensor.<server>_last_message` (diagnostic). Messages from before Home Assistant started are not reported. For example, to be told about Blue Iris errors:

```yaml
triggers:
  - trigger: event
    event_type: blueiris_log
    event_data:
      level: error
actions:
  - action: notify.mobile_app_phone
    data:
      title: "Blue Iris: {{ trigger.event.data.object }}"
      message: "{{ trigger.event.data.message }}"
```

###### Sensor - Uptime

Blue Iris software uptime (duration, shown in hours by default), diagnostic entity

###### Switch - Profile (Per profile)

Allows setting the active profile, only one of the profile switches can be turned on at a time.

If you turn off one of the switches it will behave as follows:

- Profile #1 is turned off, it will turn on Profile #0
- Any of the other profiles are turned off, it will turn on Profile #1

###### Services

Trigger Camera: Provides the ability to manually trigger a camera or camera group

Move to Preset: Provides the ability to move a camera to a specified preset

Reset Camera: Resets (reconnects) a single camera, the same as Blue Iris' Reset command. The stream drops for a few seconds. Requires the integration's Blue Iris user to be an admin; camera groups are rejected

Snapshot to Database: Saves a snapshot into Blue Iris' own clips database, same as the camera's Snapshot to Database button. Not for groups

Current Camera Snapshot: Saves the camera's current still image to `media/blueiris/` (file name optional, default `<camera id>_current.jpg`) and returns `saved_path` and `local_snapshot_url` (`/media/local/blueiris/...`) as the service response, e.g. for a notification image:

```yaml
- action: blueiris.current_camera_snapshot
  target:
    entity_id: camera.bi5_driveway
  response_variable: snap
- action: notify.mobile_app_phone
  data:
    message: Driveway camera
    data:
      image: "{{ snap['camera.bi5_driveway'].local_snapshot_url }}"
```

## Lovelace UI Configuration

[Example of UI layout](docs/configs/casting/configuration.yaml)

## Casting

Currently the Stream Component is a bit too ragged to use to cast Blue Iris video streams, which don't need proxying.

#### Lovelace UI for casting

```YAML
# Example ui-lovelace.yaml view entry
  - type: entities
    title: Cast Camera to Screen
    show_header_toggle: false
    entities:
      - entity: input_select.camera_dropdown
      - entity: input_select.cast_to_screen_dropdown
      - entity: script.execute_cast_dropdown
```

[Example of configuration output](docs/configs/casting/ui-lovelace.yaml)

## Contributors

<a href="https://github.com/darkgrue">@darkgrue</a>
