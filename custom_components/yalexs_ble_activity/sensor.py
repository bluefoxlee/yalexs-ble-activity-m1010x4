"""Support for Yale Access Bluetooth Activity sensors."""

from __future__ import annotations

from collections.abc import Mapping
import datetime as dt
import logging
from typing import Any

from homeassistant.components import recorder
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_DOMAIN,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.yalexs_ble.entity import YALEXSBLEEntity
from homeassistant.components.yalexs_ble.models import YaleXSBLEData
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import entity_registry as er, event as evt
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import (
    ExtraStoredData,
    RestoredExtraData,
    RestoreEntity,
)
from homeassistant.util import dt as dt_util
from yalexs_ble import ConnectionInfo, DoorActivity, LockActivity, LockInfo, RawActivity

from .const import (
    ATTR_ACTIVITY_TYPE,
    ATTR_LAST_PIN_ACTIVITY_TYPE,
    ATTR_LAST_PIN_ID,
    ATTR_LAST_PIN_NAME,
    ATTR_LAST_PIN_RAW_FRAME,
    ATTR_LAST_PIN_TIMESTAMP,
    ATTR_PIN_ID,
    ATTR_PIN_NAME,
    ATTR_RAW_FRAME,
    ATTR_REMOTE_TYPE,
    ATTR_SLOT,
    ATTR_SOURCE,
    ATTR_TIMESTAMP,
    CONF_LOCK_ENTITIES,
    CONF_PIN_NAMES,
    OPERATION_SENSOR_WRITE_DELAY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(  # noqa: RUF029
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yale Access Bluetooth Activity sensors."""

    entity_registry = er.async_get(hass)
    pin_names = entry.data.get(CONF_PIN_NAMES, {})

    async_add_entities(
        YaleXSBLEOperationSensor(data, pin_names, lock_entity_id)
        for lock_entity_id in entry.data[CONF_LOCK_ENTITIES]
        if (
            (lock_entry := entity_registry.async_get(lock_entity_id))
            and (core_entry_id := lock_entry.config_entry_id)
            and (core_entry := hass.config_entries.async_get_known_entry(core_entry_id))
            and (data := core_entry.runtime_data)
        )
    )


class YaleXSBLEOperationSensor(YALEXSBLEEntity, SensorEntity, RestoreEntity):
    """Representation of an Yale Access Bluetooth lock operation sensor."""

    _attr_translation_key = "operation"
    _attr_icon = "mdi:lock-clock"
    _pending_activity_update: DoorActivity | LockActivity | RawActivity | None = None
    _cancel_pending_activity_update: CALLBACK_TYPE | None = None

    def __init__(
        self,
        data: YaleXSBLEData,
        pin_names: Mapping[str, str] | None = None,
        lock_entity_id: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data)
        self._attr_unique_id = f"{data.lock.address}operation"
        self._pin_names = dict(pin_names or {})
        self._lock_entity_id = lock_entity_id
        self._last_pin_attributes: dict[str, Any] = {}
        self._last_logged_activity_key: tuple[str, float] | None = None

    @callback
    def _async_activity_update(
        self,
        activity: DoorActivity | LockActivity | RawActivity,
        lock_info: LockInfo,  # noqa: ARG002
        connection_info: ConnectionInfo,  # noqa: ARG002
    ) -> None:
        """Handle activity update."""

        value, attributes = self._activity_values(activity)

        _LOGGER.debug("creating event for activity update")

        self.hass.bus.async_fire(
            "yalexs_ble_activity",
            {
                "entity_id": self.entity_id,
                "state": value,
                "attributes": attributes,
            },
        )

        self._record_logbook_activity(activity, attributes)
        # Raw 0x07 is represented by the human-readable logbook entry below.
        # Keep the event and attributes, but do not add a second raw history row.
        if not (
            isinstance(activity, RawActivity) and activity.activity_type == 0x07
        ):
            self._record_activity(activity, value, attributes)
        self._pending_activity_update = activity

        if self._cancel_pending_activity_update:
            self._cancel_pending_activity_update()

        self._cancel_pending_activity_update = evt.async_call_later(
            self.hass,
            OPERATION_SENSOR_WRITE_DELAY,
            self._flush_pending_update,
        )

    def _record_activity(
        self,
        activity: DoorActivity | LockActivity | RawActivity,
        native_value: str | None,
        attributes: dict[str, Any],
    ) -> None:
        state_changed_data: EventStateChangedData = {
            "entity_id": self.entity_id,
            "old_state": None,
            "new_state": State(
                self.entity_id,
                native_value or STATE_UNAVAILABLE,
                attributes,
                last_changed=activity.timestamp,
                last_reported=activity.timestamp,
                last_updated=activity.timestamp,
                last_updated_timestamp=dt_util.as_timestamp(activity.timestamp),
            ),
        }

        _LOGGER.debug("writing historic activity update: %s", state_changed_data)

        instance = recorder.get_instance(self.hass)
        instance.queue_task(Event(str(EVENT_STATE_CHANGED), state_changed_data))

    def _record_logbook_activity(
        self,
        activity: DoorActivity | LockActivity | RawActivity,
        attributes: dict[str, Any],
    ) -> None:
        """Add a human-readable PIN activity entry to Home Assistant Activity."""
        if (
            not isinstance(activity, RawActivity)
            or activity.activity_type != 0x07
            or activity.pin_id is None
            or self._lock_entity_id is None
            or self.entity_id is None
        ):
            return

        activity_key = (
            activity.raw_frame,
            dt_util.as_timestamp(activity.timestamp),
        )
        if activity_key == self._last_logged_activity_key:
            return
        self._last_logged_activity_key = activity_key

        lock_name = self._lock_name()
        pin_name = attributes.get(ATTR_PIN_NAME, "未知 PIN")

        self.hass.bus.async_fire(
            EVENT_LOGBOOK_ENTRY,
            {
                LOGBOOK_ENTRY_NAME: pin_name,
                LOGBOOK_ENTRY_MESSAGE: f"{pin_name}以通行碼開鎖",
                LOGBOOK_ENTRY_DOMAIN: LOCK_DOMAIN,
                "entity_id": self.entity_id,
            },
            time_fired=activity_key[1],
        )

    def _lock_name(self) -> str:
        """Return the configured lock name for a human-readable activity entry."""
        if self._lock_entity_id and (state := self.hass.states.get(self._lock_entity_id)):
            return state.name

        if self._lock_entity_id:
            return self._lock_entity_id.split(".", 1)[-1].replace("_", " ").title()
        return "門鎖"

    @callback
    def _flush_pending_update(self, now: dt.datetime) -> None:  # noqa: ARG002
        activity = self._pending_activity_update
        assert activity is not None

        _LOGGER.debug("flushing pending activity update")

        value, attributes = self._activity_values(activity)
        # Preserve the last meaningful door/lock state for raw PIN frames. The
        # raw frame is still available in attributes and in the activity event,
        # while the friendly logbook entry avoids a duplicate activity row.
        if not (
            isinstance(activity, RawActivity) and activity.activity_type == 0x07
        ):
            self._attr_native_value = value
        self._attr_extra_state_attributes = attributes
        self._pending_activity_update = None

        self.async_write_ha_state()

    @staticmethod
    def _extract_values(
        activity: DoorActivity | LockActivity | RawActivity,
    ) -> tuple[str | None, dict[str, Any]]:
        value: str | None = None
        attributes: dict[str, Any] = {}

        if isinstance(activity, DoorActivity):
            value = f"door_{activity.status.name.lower()}"
            attributes[ATTR_TIMESTAMP] = activity.timestamp
        elif isinstance(activity, LockActivity):
            value = f"lock_{activity.status.name.lower()}"
            attributes[ATTR_TIMESTAMP] = activity.timestamp
            attributes[ATTR_SOURCE] = activity.source.name.lower()
            if activity.remote_type is not None:
                attributes[ATTR_REMOTE_TYPE] = activity.remote_type.name.lower()
            if activity.slot is not None:
                attributes[ATTR_SLOT] = activity.slot
        elif isinstance(activity, RawActivity):
            value = f"activity_0x{activity.activity_type:02x}"
            attributes[ATTR_TIMESTAMP] = activity.timestamp
            attributes[ATTR_ACTIVITY_TYPE] = f"0x{activity.activity_type:02X}"
            attributes[ATTR_RAW_FRAME] = activity.raw_frame
            if activity.pin_id is not None:
                # This is a provisional internal credential identifier, not
                # the confirmed Yale slot number.
                attributes[ATTR_SOURCE] = "pin"
                attributes[ATTR_PIN_ID] = f"0x{activity.pin_id:02X}"

        return (value, attributes)

    def _activity_values(
        self,
        activity: DoorActivity | LockActivity | RawActivity,
    ) -> tuple[str | None, dict[str, Any]]:
        """Extract values and retain the latest raw PIN record.

        Returns:
            The sensor value and attributes for the activity.
        """
        value, attributes = self._extract_values(activity)

        if isinstance(activity, RawActivity) and activity.pin_id is not None:
            self._last_pin_attributes = {
                ATTR_LAST_PIN_ACTIVITY_TYPE: attributes[ATTR_ACTIVITY_TYPE],
                ATTR_LAST_PIN_ID: attributes[ATTR_PIN_ID],
                ATTR_LAST_PIN_RAW_FRAME: attributes[ATTR_RAW_FRAME],
                ATTR_LAST_PIN_TIMESTAMP: activity.timestamp,
            }
            if pin_name := self._pin_names.get(attributes[ATTR_PIN_ID]):
                attributes[ATTR_PIN_NAME] = pin_name
                self._last_pin_attributes[ATTR_LAST_PIN_NAME] = pin_name

        attributes.update(self._last_pin_attributes)
        return value, attributes

    async def async_added_to_hass(self) -> None:
        """Register callbacks, perform initial updates & restore state."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self._device.register_activity_callback(
                self._async_activity_update, request_update=True
            )
        )

        if (
            (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in {STATE_UNKNOWN, STATE_UNAVAILABLE}
            and (extra_data := await self.async_get_last_extra_data()) is not None
        ):
            extra_data_dict = extra_data.as_dict()
            self._attr_native_value = extra_data_dict["value"]
            restored_attributes = dict(extra_data_dict["attributes"] or {})
            if last_pin_id := restored_attributes.get(ATTR_LAST_PIN_ID):
                if pin_name := self._pin_names.get(last_pin_id):
                    restored_attributes[ATTR_LAST_PIN_NAME] = pin_name
                else:
                    restored_attributes.pop(ATTR_LAST_PIN_NAME, None)
            if pin_id := restored_attributes.get(ATTR_PIN_ID):
                if pin_name := self._pin_names.get(pin_id):
                    restored_attributes[ATTR_PIN_NAME] = pin_name
                else:
                    restored_attributes.pop(ATTR_PIN_NAME, None)
            self._attr_extra_state_attributes = restored_attributes
            self._last_pin_attributes = {
                key: restored_attributes[key]
                for key in (
                    ATTR_LAST_PIN_ACTIVITY_TYPE,
                    ATTR_LAST_PIN_ID,
                    ATTR_LAST_PIN_NAME,
                    ATTR_LAST_PIN_RAW_FRAME,
                    ATTR_LAST_PIN_TIMESTAMP,
                )
                if key in restored_attributes
            }

    @property
    def extra_restore_state_data(self) -> ExtraStoredData | None:
        return RestoredExtraData(
            {
                "value": self._attr_native_value,
                "attributes": self._attr_extra_state_attributes,
            }
        )
