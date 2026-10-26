# Setup and configuration

Requirements, installation, options and the server device settings of [Blue Iris (Ltek)](README.md). The entities themselves are described in the README's *Components* section.


## Requirements

- BlueIris Server available with a user
- To control profiles and schedules, and to use Reset Camera, the user must have 'admin' level permissions
- MQTT Integration is optional - it will allow listening to BlueIris events
- Read the [BlueIris manual](docs/blueiris-server.md) for this component

## Installations via HACS

Click the button at the top, or in HACS → ⋮ → Custom repositories add `https://github.com/Ltek/ha-blueiris` as an **Integration**, then download "Blue Iris (Ltek)" and restart Home Assistant.

Replacing an existing elad-bar install: remove that repository inside HACS first (do not delete the integration under Settings → Devices & Services), then add this one. The config entry and entities carry over.

## Integration settings

### Basic configuration (Configuration -> Integrations -> Add BlueIris)

| Fields name | Type      | Required | Default   | Description                                   |
| ----------- | --------- | -------- | --------- | --------------------------------------------- |
| Host        | Texbox    | +        | None      | Hostname or IP address of the BlueIris server |
| Port        | Textbox   | +        | 0         | HTTP Port to access BlueIris server           |
| SSL         | Check-box | +        | Unchecked | Is SSL supported?                             |
| Username    | Textbox   | -        |           | Username of admin user for BlueIris server    |
| Password    | Textbox   | -        |           | Password of admin user for BlueIris server    |

### Integration options (Settings -> Devices & Services -> BlueIris -> Configure)

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
| Connection          | Host, Port, SSL, Username, Password, Clear credentials (workaround to clear the username and password; not stored as option) |
| Logging             | Log level - Default on Startup, Generate configuration files                                                                 |

Stream type, HA Streaming, Stream Method, Blue Iris log reporting and the auto reset defaults are on the server device instead (see [Server device settings](#server-device-settings)). On the first start of v2026.10.26.45 they take the values they had in the options.

**Page 2 - choose items.** Only appears when at least one section is set to `Choose…`. Each of those sections is a group with a checkbox per item, pre-filled with the current selection.

**Integration's title**
Title will be extracted from BlueIris server's configuration, it will be set upon adding the server, and after every Option's change

Note that in case there are 2 integrations with the same integration's title, components will be overwritten by both integrations.

### Server device settings

Settings that change how the integration behaves are entities on the server device, in its Configuration section. Each shows its current value, changes at once without a reload, and is kept across restarts.

| Entity | What it sets |
| ------ | ------------ |
| `select.<server>_stream_type` | Stream type (see below) |
| `switch.<server>_ha_streaming` | HA's own stream or the MJPEG view |
| `select.<server>_stream_method` | How session URLs are kept up to date |
| `switch.<server>_stream_monitoring` | Stream monitoring on / off |
| `select.<server>_blue_iris_log_reporting` | Off / Warnings and errors / Errors only (admin) |
| `switch.<server>_default_auto_reset`, `..._default_auto_reset_reboot` | Auto reset defaults: on, reboot after the last reset (admin) |
| `number.<server>_default_auto_reset_delay` / `_attempts` / `_interval` | Auto reset defaults (admin) |
| `button.<server>_reset_cameras_to_auto_reset_defaults` | Clears every camera's own auto reset values (admin) |
| `select.<server>_log_level`, `switch.<server>_auto_reset`, `..._auto_reset_notifications`, Restart and Reload buttons | As before |

Read-only values in the Diagnostic section: Host, Port, SSL, Username (never the password), Admin (whether that user has admin rights in Blue Iris), Integration Version (the build installed), Blue Iris Version, Blue Iris Support, Active Profile, Active Schedule and Cameras (with groups and system cameras as attributes). The server device's **Visit** link opens Blue Iris' web interface.

**Stream type RTSP** (server device -> Stream Type)

| Stream type      | URL Home Assistant opens                                  |
| ---------------- | --------------------------------------------------------- |
| H264 (default)   | `http://<server>/h264/<camera>/temp.m3u8?session=...` - Blue Iris' HLS playlist |
| H264 TS          | `http://<server>/h264/<camera>/temp.ts?session=...` - MPEG transport stream |
| RTSP             | `rtsp://<user>:<password>@<server>/<camera>` - RTSP on Blue Iris' web server port |
| RTSP sub stream  | Same with `?decode=-1`: the camera's sub stream, much lighter for dashboards with many cameras |

RTSP reads the camera's H264 without Blue Iris' HLS step, which is what Home Assistant's stream handles best; try it if the log shows `Error opening stream (Server returned 5XX ...)` for `temp.m3u8`. It uses the integration's username and password (escaped; Home Assistant hides them in its stream logs, and the camera's `stream_source` attribute shows `****`), has no session, and so is the same for every Stream Method. It is plain `rtsp://` even when the integration uses SSL. Only used with HA Streaming on. A new stream type is used by cameras after Reload Integration or a restart.

**HA Streaming** (`switch.<server>_ha_streaming`, Configuration section of the server device; only when HA's `stream` integration is loaded, as with `default_config`)

| Switch | What camera live views get                                                                                 |
| ------ | ---------------------------------------------------------------------------------------------------------- |
| Off    | An MJPEG view that Home Assistant builds by fetching the camera's still image from Blue Iris over and over (once per frame at the camera's FPS) |
| On     | Home Assistant's stream: one H264 connection per camera to Blue Iris, played as HLS (or WebRTC when a WebRTC provider such as go2rtc is set up) |

Switches at once for every camera, no restart: cameras change their supported features, and running HA streams are stopped when it is turned off. Open dashboards may need a refresh to pick it up. Kept across restarts. With many cameras on one dashboard, *On* puts far less load on Blue Iris than the MJPEG view. Stream Method and Stream Monitoring only apply while it is on.

**Stream Method** (`select.<server>_stream_method`, Configuration section of the server device)

Switches how camera entities build their stream and still-image URLs, without a restart. Running streams are restarted with the new URL straight away; the choice is kept across restarts.

| Method                  | Behaviour                                                                                          |
| ----------------------- | -------------------------------------------------------------------------------------------------- |
| Fixed URL (default)     | The URL made when the camera entity was created, with that session. The original elad-bar behaviour: running streams are never touched, except once when you switch to Fixed URL from another method |
| Follow session          | The URL always uses the current Blue Iris session; when the integration logs in again, every running stream is restarted with the new URL (the method used by kramttocs/ha-blueiris) |
| Follow session + audio  | As Follow session, and adds `audio=1` for cameras that have audio                                  |
| Login in URL            | No session: the integration's username and password go in the URL (`http://user:password@host/...`, sent as HTTP Basic auth). Never goes stale, so streams are never restarted. Still images use Basic auth too. Without a username and password it works like Follow session |

The attribute `stream_restarts` counts streams restarted with a new URL since start. Follow session restarts every running stream on each new login, so a server that drops sessions often will make streams restart often. Try one method for a while, then the other.

With *Login in URL* the password is part of the stream URL Home Assistant opens. Home Assistant hides it in its stream logs, but anything else that shows the stream source (for example a custom card, or a log at debug level from another integration) could show it. Blue Iris must accept HTTP Basic auth for streams; if the live view stays black with this method, it doesn't, and you should switch back.

**Stream monitoring** (`switch.<server>_stream_monitoring`, Configuration section of the server device, **off by default**, kept across restarts)

While it is off, none of the monitoring runs: no checks, no events, no extra camera attributes, and no Stream Health sensor. While it is on, every open stream (someone watching, or preloaded) is checked every 2 s for new video. Each change fires the event `blueiris_stream` and writes an info line to the Home Assistant log:

| `type`      | When                                                                                         |
| ----------- | -------------------------------------------------------------------------------------------- |
| `restart`   | The integration gave the stream a new URL; `reason` is `method_change` or `session_change`   |
| `connected` | Video is flowing; `seconds` since the stream was opened, restarted or dropped                |
| `dropped`   | No new video for 20 s while it was connected                                                 |
| `failed`    | Still no video 60 s after opening, a restart or a drop                                       |

Each event also has `camera_id`, `camera_name`, `entity_id`, `method` (the Stream Method at the time) and `reason` (`opened`, `method_change`, `session_change`, `stalled`).

Camera entities get `stream_status` (idle, connecting, connected, down, failed), `stream_last_connect_seconds`, `stream_restarts`, `stream_drops` and `stream_failures`.

`sensor.<server>_stream_health` (diagnostic, only while monitoring is on) is the number of open streams without video, with one attribute per Stream Method: restarts, connected, dropped, failed and average_connect_seconds. Counts start over when Home Assistant restarts.

It can see whether video reaches Home Assistant and how fast it comes back; it can't see delay or buffering in the browser's player. It only sees streams Home Assistant opens itself (HLS live view); still-image cards and players that bypass Home Assistant's stream (for example WebRTC through go2rtc) are not seen. The log lines are at info level: set the server's Log Level to Info to see them.

**Reload Integration** (`button.<server>_reload_integration`, Configuration section of the server device) reloads the integration, the same as Devices & Services -> Blue Iris -> Reload: it logs in again and recreates the entities and streams. Entities, settings and statistics of the stream monitor in memory start over.

**Log level**

- *Log level - Default on Startup* (options, Streams and logging) is applied every time Home Assistant starts or the integration reloads. `Default` keeps Home Assistant's own logging setup (normally Warning, or whatever `logger:` in `configuration.yaml` says)
- The server's **Log Level** entity (`select.<server>_log_level`, Configuration section of the server device) shows the level actually in effect, including changes made with HA's *Enable debug logging* or `logger.set_level`, and changes it immediately without a reload. It is not saved: the next restart goes back to the Default on Startup level, so a forgotten Debug setting doesn't keep filling the log
- Neither needs the `logger:` integration

### Auto-generating configurations files:

Will create YAML with all the configurations in the config directory under blueiris.advanced_configurations.yaml:

- Input select (drop-downs)
- Script to cast based on the selection
- UI of all the components created by BlueIris based on the description above

[Example of configuration output](docs/configs/casting/configuration.yaml)

### Configuration validations

After submitting the form either for a new integration instance or updating options, the component will try to login to the BlueIris server to verify the new settings.

The following errors can appear:

- BlueIris integration ({host}) already configured
- Invalid administrator credentials - credentials are invalid or user is not an admin
- Invalid server details - Cannot reach the server

### Diagnostics

Settings -> Devices & Services -> BlueIris -> ⋮ -> Download diagnostics produces a JSON file for bug reports: login state, server version and status, the stream-related fields of every camera (online, no signal, FPS, error) and the entity list. Host, username, password, session ID, license, location and stream / image URLs are redacted.

### Encryption key got corrupted

If a persistent notification popped up with the following message:

```
Encryption key got corrupted, please remove the integration and re-add it
```

It means that the encryption key was modified from outside the code and the integration will need to be removed and re-added.
