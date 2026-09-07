"""Constants for the Yale Access Bluetooth Activity integration."""

from typing import Final

DOMAIN: Final = "yalexs_ble_activity"
YALEXSBLE_PATCH_URL = (
    "git+https://github.com/wbyoung/yalexs-ble@yalexs-ble-{version}-patches"
)

ATTR_REMOTE_TYPE: Final = "remote_type"
ATTR_SLOT: Final = "slot"
ATTR_SOURCE: Final = "source"
ATTR_TIMESTAMP: Final = "timestamp"
ATTR_ACTIVITY_TYPE: Final = "activity_type"
ATTR_PIN_ID: Final = "pin_id"
ATTR_RAW_FRAME: Final = "raw_frame"
ATTR_LAST_PIN_ACTIVITY_TYPE: Final = "last_pin_activity_type"
ATTR_LAST_PIN_ID: Final = "last_pin_id"
ATTR_LAST_PIN_RAW_FRAME: Final = "last_pin_raw_frame"
ATTR_LAST_PIN_TIMESTAMP: Final = "last_pin_timestamp"

CONF_LOCK_ENTITIES: Final = "lock_entities"

OPERATION_SENSOR_WRITE_DELAY: Final = 2

TRACE: Final = 5
