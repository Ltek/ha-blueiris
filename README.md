# Blue Iris (Ltek)

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Ltek&repository=ha-blueiris&category=integration)

Home Assistant integration for Blue Iris Video Security Software, polling the Blue Iris JSON API and listening to its MQTT events.

Ltek fork of [elad-bar/ha-blueiris](https://github.com/elad-bar/ha-blueiris). It keeps the same `blueiris` domain, so it replaces an existing install in place with the same entities. Fork changes are also offered upstream as PRs.

Current version: **1.0.25** · [Changelog](CHANGELOG.md)

## Features

- **Camera** per Blue Iris camera, group and system camera (All, Cycle), with live attributes (FPS, online, no signal count, error, ...)
- **Streams**: H264 (HLS), H264 TS or MJPEG, optionally through the Home Assistant stream component
- **Binary sensors** per camera from MQTT: Motion, Audio, Connectivity, DIO, External, plus a server-level Alerts sensor
- **Sensors** for the server: Connection Health and Uptime
- **Switches** for Blue Iris profiles and schedules (admin user required)
- **Services**: Trigger Camera, Move to Preset, Reset Camera, Current Camera Snapshot
- **Diagnostics** download for bug reports
- SSL with self-signed certificates

## New in this fork

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

**Page 1 - which components to create.** Each section has a drop-down with three choices; the labels show how many items the section has and how many are currently selected, e.g. `Choose… (3 of 15 selected)`:

| Choice    | Effect                                                                                  |
| --------- | --------------------------------------------------------------------------------------- |
| All (n)   | Creates the component for every item, including cameras added to Blue Iris later        |
| None (0)  | Turns the section off; no entities are created for it                                    |
| Choose…   | Opens a checkbox list for that section on page 2                                         |

| Section              | Items                                    | Shown when                     |
| -------------------- | ---------------------------------------- | ------------------------------ |
| Camera components    | All cameras, groups and system cameras   | Always                         |
| Motion sensors       | Non-system cameras                       | MQTT integration is set up     |
| Connectivity sensors | Non-system cameras                       | MQTT integration is set up     |
| Audio sensors        | Non-system cameras that support audio    | MQTT integration is set up     |
| DIO sensors          | Non-system cameras                       | MQTT integration is set up     |
| External sensors     | Non-system cameras                       | MQTT integration is set up     |
| Profile switches     | Blue Iris profiles                       | User has admin rights          |
| Schedule switches    | Blue Iris schedules                      | User has admin rights          |

A section that is not shown keeps its saved setting.

Two collapsed groups below hold the other settings:

| Group               | Fields                                                                                                                       |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Connection          | Host, Port, SSL, Username, Password, Clear credentials (workaround to clear the username and password; not stored as option) |
| Streams and logging | Stream type (H264 / H264 TS / MJPEG), Stream support (requires restart), Log level, Generate configuration files            |

**Page 2 - choose items.** Only appears when at least one section is set to `Choose…`. Each of those sections is a group with a checkbox per item, pre-filled with the current selection.

**Integration's title**
Title will be extracted from BlueIris server's configuration, it will be set upon adding the server, and after every Option's change

Note that in case there are 2 integrations with the same integration's title, components will be overwritten by both integrations.

**Log Level's drop-down**
New feature to set the log level for the component without need to set log_level in `customization:` and restart or call manually `logger.set_level` and loose it after restart.

Upon startup or integration's option update, based on the value chosen, the component will make a service call to `logger.set_level` for that component with the desired value,

In case `Default` option is chosen the service call will not happen. Therefore after changing from any other option to `Default` a restart is required.

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
