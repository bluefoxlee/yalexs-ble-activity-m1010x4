# Yale Access Bluetooth Activity for Home Assistant

[![HACS](https://img.shields.io/badge/custom-grey?logo=homeassistantcommunitystore&logoColor=white)][hacs-repo]
[![HACS installs](https://img.shields.io/github/downloads/bluefoxlee/yalexs-ble-activity-m1010x4/latest/total?label=installs&color=blue)][hacs-repo]
[![Version](https://img.shields.io/github/v/release/bluefoxlee/yalexs-ble-activity-m1010x4)][releases]
![Downloads](https://img.shields.io/github/downloads/bluefoxlee/yalexs-ble-activity-m1010x4/total)
![Build](https://img.shields.io/github/actions/workflow/status/bluefoxlee/yalexs-ble-activity-m1010x4/pytest.yml)

Activity history sensor for Yale Access Bluetooth.

Disclaimers:

- Enabling this integration for a lock will consume activity from the lock. This means that the activity **will not be available** to the Yale mobile app.
- This installs the [custom patched version](https://github.com/bluefoxlee/yalexs-ble-m1010x4/tree/yalexs-ble-4.0.1-patches) of [`yalexs-ble`](https://github.com/Yale-Libs/yalexs-ble) maintained for this fork.
- This fork is based on the original project by [wbyoung](https://github.com/wbyoung).
- The provisional `0x07` PIN layout is verified for the M1010X4 keypad/module variant. Other Yale/August models may use a different activity type or frame layout; verify their frames before relying on the mapping.
- This is an independent fork and is not affiliated with Yale, Yale Home, August, or Home Assistant.
- This is an implementation of work done to [integrate activity into Home Assistant Core](https://github.com/home-assistant/core/pull/151436#issuecomment-3243330215).
- The ideas were rejected from HA Core because there is not yet a standard architecture for [recording historic state changes](https://github.com/home-assistant/architecture/discussions/580).

## Installation

### HACS

Installation through [HACS][hacs] is the preferred installation method.

1. Go to the HACS dashboard.
1. Click the ellipsis menu (three dots) in the top right &rarr; choose _Custom repositories_.
1. Enter the URL of this GitHub repository,
   `https://github.com/bluefoxlee/yalexs-ble-activity-m1010x4`, in the _Repository_ field.
1. Select _Integration_ as the category.
1. Click _Add_.
1. Search for "Yale Access Bluetooth Activity" &rarr; select it &rarr; press _DOWNLOAD_.
1. Press _DOWNLOAD_.
1. Select the version (it will auto select the latest) &rarr; press _DOWNLOAD_.
1. Restart Home Assistant then continue to [the setup section](#setup).

### Manual Download

1. Go to the [release page][releases] and download the `yalexs_ble_activity.zip` attached
   to the latest release.
1. Unpack the zip file and move `custom_components/yalexs_ble_activity` to the following
   directory of your Home Assistant configuration: `/config/custom_components/`.
1. Restart Home Assistant then continue to [the setup section](#setup).

## Setup

Open your Home Assistant instance and start setting up by following these steps:

1. Navigate to "Settings" &rarr; "Devices & Services"
1. Click "+ Add Integration"
1. Search for and select &rarr; "Yale Access Bluetooth Activity"

Or you can use the My Home Assistant Button below.

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)][config-flow-start]

Follow the instructions to configure the integration.

The integration options include an optional local PIN identifier mapping. Enter
one entry per line using the form `0xNN=Name`, for example:

```text
0x1A=Person A
0x22=Person B
0xEE=Master PIN user
```

These are the identifier bytes reported by the lock, not the PIN values. The
mapping is stored in the Home Assistant config entry and is not part of the
source code. Unknown identifiers remain available as their original `pin_id`.

## Entities

One _sensor_ entity is created for each selected lock:

### `sensor.<lock_name>_operation`

The last operation of the door or lock. One of:

- `door_unknown`
- `door_closed`
- `door_ajar`
- `door_opened`
- `lock_unknown`
- `lock_unlocking`
- `lock_unlocked`
- `lock_locking`
- `lock_locked`

The sensor value will only change to the most recent value obtained and will skip over activity to avoid rapid state changes. To create automations that trigger on any activity, use the [`yalexs_ble_activity` event](#yalexs_ble_activity)

#### Attributes

- `timestamp`: The time of the activity.
- `source`: The source of a lock operation. Possible values: `remote`, `manual`, `auto_lock`, `pin` or `unknown`. Not present for door related activity.
- `remote_type`: The type of remote operation performed. Not present for door related activity.
- `slot`: This is a unique integer representing the code used. Only present for unlock activity with `source=pin`.
- `pin_id`: The raw hexadecimal credential identifier exposed by the patched activity parser.
- `pin_name`: The optional local name configured for the current raw PIN activity.
- `last_pin_id`, `last_pin_name`, `last_pin_raw_frame`, `last_pin_timestamp`: The latest raw PIN details retained after later door/lock activity is received.

## Events

### `yalexs_ble_activity`

An event emitted immediately when new activity is received.

This will be triggered for all activity that is received from the lock regardless of how old it is. Even for the most recent activity, however, the state of the [`sensor.<lock_name>_operation`](#sensorlock_name_operation) sensor entity will not yet be updated at the time this event is fired. (State updates are deferred for a short period to ensure all activity has been read from the lock.)

#### Event Data

- `entity_id`: The entity ID of the [`sensor.<lock_name>_operation`](#sensorlock_name_operation) with the activity.
- `state`: The state of the activity which mirrors that of [`sensor.<lock_name>_operation`](#sensorlock_name_operation).
- `attributes`: The attributes for the activity which mirrors that of the [`sensor.<lock_name>_operation`](#sensorlock_name_operation) attributes.

For a received `0x07` PIN activity, the integration also writes a human-readable
entry directly to Home Assistant's Activity panel and associates it with the
operation sensor. The configured PIN identifier is included in the message and
follows the form:

```text
Front Door — Person A以通行碼開鎖
```

The raw `activity_0x07` frame remains available in the sensor event and
attributes, but is not written as a second historical Activity row.

The lock domain supplies the lock icon. The raw identifier remains available on
the operation sensor for looking up or updating the local mapping. Existing
`yalexs_ble_activity` events remain available for notifications and other
automations.

[config-flow-start]: https://my.home-assistant.io/redirect/config_flow_start/?domain=yalexs_ble_activity
[hacs]: https://hacs.xyz/
[hacs-repo]: https://github.com/hacs/integration
[hacs-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-open]: https://my.home-assistant.io/redirect/hacs_repository/?owner=bluefoxlee&repository=yalexs-ble-activity-m1010x4&category=integration
[releases]: https://github.com/bluefoxlee/yalexs-ble-activity-m1010x4/releases
