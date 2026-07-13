"""Steps management mixin for AV Scenes config flow."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_STEPS,
    CONF_STEP_ID,
    CONF_STEP_TYPE,
    CONF_STEP_DELAY_AFTER,
    CONF_STEP_PARAMETERS,
    CONF_ENTITY_ID,
    CONF_ACTIVITIES,
    CONF_ACTION,
    STEP_TYPE_POWER_OFF,
    STEP_TYPE_CALL_ACTION,
    STEP_TYPE_DELAY,
    STEP_TYPES,
)

# Step types offered in the "add step" menu. POWER_OFF is intentionally
# excluded — shutdown is handled automatically when an activity stops.
_ADDABLE_STEP_TYPES = [t for t in STEP_TYPES if t != STEP_TYPE_POWER_OFF]
from .config_flow_helpers import (
    build_step_schema,
    describe_step,
    parse_step_params,
    step_choice_label,
    step_entity_domains,
    translatable_select,
)

_LOGGER = logging.getLogger(__name__)


class StepsFlowMixin:
    """Mixin for step management flow steps."""

    async def async_step_step_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage steps for an activity."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add_step":
                return await self.async_step_add_step()
            if action == "edit_step":
                return await self.async_step_select_step_to_edit()
            if action == "delete_step":
                return await self.async_step_select_step_to_delete()
            if action == "reorder_step":
                return await self.async_step_reorder_step()
            if action == "finish_activity":
                return await self._finish_activity()

        steps = self.current_activity_data.get(CONF_STEPS, [])
        step_list_str = self._render_step_list(steps, empty="No steps added yet")

        options = ["add_step"]
        if steps:
            options += ["edit_step", "delete_step"]
            if len(steps) >= 2:
                options.append("reorder_step")
        options.append("finish_activity")

        return self.async_show_form(
            step_id="step_menu",
            data_schema=vol.Schema({
                vol.Required("action"): translatable_select(options, "step_action"),
            }),
            description_placeholders={"steps": step_list_str},
        )

    async def _finish_activity(self) -> FlowResult:
        """Persist the current activity into its room and return to the menu."""
        if self.current_room not in self.rooms:
            _LOGGER.error("Room %s not found", self.current_room)
            return await self.async_step_room_menu()

        room_data = self.rooms[self.current_room]
        room_data.setdefault(CONF_ACTIVITIES, {})
        room_data[CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
        _LOGGER.debug(
            "Saved activity %s to room %s with %d steps",
            self.current_activity, self.current_room,
            len(self.current_activity_data.get(CONF_STEPS, [])),
        )
        self._save_config()
        return await self.async_step_activity_menu()

    def _render_step_list(self, steps: list[dict[str, Any]], *, empty: str) -> str:
        """Render an ordered, human-readable list of steps for the form body."""
        lines = [
            f"{idx}. {describe_step(self.hass, step)}"
            for idx, step in enumerate(steps, 1)
        ]
        return "\n".join(lines) if lines else empty

    async def async_step_add_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a step - select step type."""
        if user_input is not None:
            step_type = user_input.get(CONF_STEP_TYPE)
            self.current_step_data = {
                CONF_STEP_ID: str(uuid.uuid4()),
                CONF_STEP_TYPE: step_type,
                CONF_STEP_DELAY_AFTER: 0,
                CONF_STEP_PARAMETERS: {},
            }
            if step_type == STEP_TYPE_DELAY:
                return await self.async_step_add_step_delay_config()
            if step_type == STEP_TYPE_CALL_ACTION:
                return await self.async_step_add_step_action_config()
            return await self.async_step_add_step_entity()

        return self.async_show_form(
            step_id="add_step",
            data_schema=vol.Schema({
                vol.Required(CONF_STEP_TYPE): translatable_select(_ADDABLE_STEP_TYPES, "step_type"),
            }),
        )

    async def async_step_add_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select entity for the step."""
        errors: dict[str, str] = {}
        step_type = self.current_step_data.get(CONF_STEP_TYPE)

        if user_input is not None:
            entity_id = user_input.get(CONF_ENTITY_ID)
            if self.hass.states.get(entity_id) is None:
                errors[CONF_ENTITY_ID] = "entity_not_found"
            else:
                self.current_step_data[CONF_ENTITY_ID] = entity_id
                return await self.async_step_add_step_config()

        return self.async_show_form(
            step_id="add_step_entity",
            data_schema=vol.Schema({
                vol.Required(CONF_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(domain=step_entity_domains(step_type))
                ),
            }),
            errors=errors,
            description_placeholders={"step_type": step_type},
        )

    async def async_step_add_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure step parameters for a device-targeting step."""
        errors: dict[str, str] = {}
        step_type = self.current_step_data.get(CONF_STEP_TYPE)
        entity_id = self.current_step_data.get(CONF_ENTITY_ID)

        if user_input is not None:
            self.current_step_data[CONF_STEP_DELAY_AFTER] = int(
                user_input.get(CONF_STEP_DELAY_AFTER, 0)
            )
            parameters, errors = parse_step_params(step_type, user_input)
            if not errors:
                self.current_step_data[CONF_STEP_PARAMETERS] = parameters
                self._append_step(self.current_step_data)
                return await self.async_step_step_menu()

        return self.async_show_form(
            step_id="add_step_config",
            data_schema=build_step_schema(self.hass, step_type, entity_id=entity_id),
            errors=errors,
            description_placeholders={
                "device": self._friendly_name(entity_id),
                "step_type": step_type,
                "info": (
                    "Configure the parameters for this step. "
                    "The delay is applied AFTER this step completes."
                ),
            },
        )

    async def async_step_add_step_delay_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure a pure delay step."""
        if user_input is not None:
            self.current_step_data[CONF_STEP_DELAY_AFTER] = int(
                user_input.get(CONF_STEP_DELAY_AFTER, 1)
            )
            self.current_step_data[CONF_ENTITY_ID] = ""  # No entity for delay
            self._append_step(self.current_step_data)
            return await self.async_step_step_menu()

        return self.async_show_form(
            step_id="add_step_delay_config",
            data_schema=build_step_schema(self.hass, STEP_TYPE_DELAY),
            description_placeholders={
                "info": "How long should the system wait (in seconds)?",
            },
        )

    async def async_step_add_step_action_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure an action-call step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            parameters, errors = parse_step_params(STEP_TYPE_CALL_ACTION, user_input)
            if not errors:
                self.current_step_data[CONF_ENTITY_ID] = ""  # No entity for action call
                self.current_step_data[CONF_STEP_DELAY_AFTER] = int(
                    user_input.get(CONF_STEP_DELAY_AFTER, 0)
                )
                self.current_step_data[CONF_STEP_PARAMETERS] = parameters
                self._append_step(self.current_step_data)
                return await self.async_step_step_menu()

        return self.async_show_form(
            step_id="add_step_action_config",
            data_schema=build_step_schema(self.hass, STEP_TYPE_CALL_ACTION),
            errors=errors,
            description_placeholders={
                "info": (
                    "Call any Home Assistant action. Format: domain.service "
                    "(e.g. light.turn_on). Service data must be valid JSON."
                ),
            },
        )

    async def async_step_reorder_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reorder steps in the activity."""
        steps = self.current_activity_data.get(CONF_STEPS, [])

        if user_input is not None:
            step_id = user_input.get("step_id")
            direction = user_input.get("direction")

            if direction == "done":
                self._save_if_persisted()
                return await self.async_step_step_menu()

            if step_id and direction:
                self._move_step(steps, step_id, direction)
            return await self.async_step_reorder_step()

        if len(steps) < 2:
            return await self.async_step_step_menu()

        return self.async_show_form(
            step_id="reorder_step",
            data_schema=vol.Schema({
                vol.Required("step_id"): self._step_choice_selector(steps),
                vol.Required("direction"): translatable_select(
                    ["up", "down", "done"], "reorder_direction"
                ),
            }),
            description_placeholders={
                "info": (
                    "Select a step and move it up or down. "
                    "Steps run from top to bottom."
                ),
            },
        )

    def _move_step(self, steps: list[dict[str, Any]], step_id: str, direction: str) -> None:
        """Swap a step with its neighbour in the given direction, then persist."""
        index = next(
            (i for i, s in enumerate(steps) if s.get(CONF_STEP_ID) == step_id), None
        )
        if index is None:
            return
        if direction == "up" and index > 0:
            target = index - 1
        elif direction == "down" and index < len(steps) - 1:
            target = index + 1
        else:
            return
        steps[index], steps[target] = steps[target], steps[index]
        self._save_if_persisted()
        _LOGGER.debug("Moved step %s", direction)

    async def async_step_select_step_to_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a step to delete."""
        steps = self.current_activity_data.get(CONF_STEPS, [])

        if user_input is not None:
            step_id = user_input.get("step_id")
            self.current_activity_data[CONF_STEPS] = [
                s for s in steps if s.get(CONF_STEP_ID) != step_id
            ]
            _LOGGER.debug("Deleted step %s", step_id)
            self._save_if_persisted()
            return await self.async_step_step_menu()

        if not steps:
            return await self.async_step_step_menu()

        return self.async_show_form(
            step_id="select_step_to_delete",
            data_schema=vol.Schema({
                vol.Required("step_id"): self._step_choice_selector(steps),
            }),
            description_placeholders={"warning": "This action cannot be undone!"},
        )

    async def async_step_select_step_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a step to edit."""
        steps = self.current_activity_data.get(CONF_STEPS, [])

        if user_input is not None:
            self.selected_step_id = user_input.get("step_id")
            return await self.async_step_edit_step()

        if not steps:
            return await self.async_step_step_menu()

        return self.async_show_form(
            step_id="select_step_to_edit",
            data_schema=vol.Schema({
                vol.Required("step_id"): self._step_choice_selector(steps),
            }),
            description_placeholders={"info": "Choose a step to edit"},
        )

    async def async_step_edit_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit an existing step's configuration."""
        errors: dict[str, str] = {}
        current_step = self._find_step(self.selected_step_id)
        if current_step is None:
            _LOGGER.error("Step %s not found", self.selected_step_id)
            return await self.async_step_step_menu()

        step_type = current_step.get(CONF_STEP_TYPE)
        entity_id = current_step.get(CONF_ENTITY_ID, "")

        if user_input is not None:
            parameters, errors = parse_step_params(step_type, user_input)
            if not errors:
                if step_type not in (STEP_TYPE_DELAY, STEP_TYPE_CALL_ACTION):
                    new_entity_id = user_input.get(CONF_ENTITY_ID)
                    if new_entity_id:
                        current_step[CONF_ENTITY_ID] = new_entity_id
                current_step[CONF_STEP_DELAY_AFTER] = int(
                    user_input.get(CONF_STEP_DELAY_AFTER, 0)
                )
                current_step[CONF_STEP_PARAMETERS] = parameters
                _LOGGER.debug("Updated step %s", self.selected_step_id)
                self._save_if_persisted()
                self.selected_step_id = None
                return await self.async_step_step_menu()

        device = (
            f"Action: {current_step.get(CONF_STEP_PARAMETERS, {}).get(CONF_ACTION, '')}"
            if step_type == STEP_TYPE_CALL_ACTION
            else self._friendly_name(entity_id, fallback="Delay")
        )

        return self.async_show_form(
            step_id="edit_step",
            data_schema=build_step_schema(
                self.hass,
                step_type,
                params=current_step.get(CONF_STEP_PARAMETERS, {}),
                delay=current_step.get(CONF_STEP_DELAY_AFTER, 0),
                include_entity=True,
                entity_id=entity_id,
            ),
            errors=errors,
            description_placeholders={
                "device": device,
                "step_type": step_type,
                "info": "Edit the parameters for this step.",
            },
        )

    # ------------------------------------------------------------------
    # Small shared helpers
    # ------------------------------------------------------------------

    def _append_step(self, step: dict[str, Any]) -> None:
        """Append a fully-built step to the current activity."""
        self.current_activity_data.setdefault(CONF_STEPS, []).append(step)
        _LOGGER.debug(
            "Added step (type: %s). Total steps: %d",
            step.get(CONF_STEP_TYPE),
            len(self.current_activity_data[CONF_STEPS]),
        )

    def _find_step(self, step_id: str | None) -> dict[str, Any] | None:
        """Return the step with the given id, or None."""
        for step in self.current_activity_data.get(CONF_STEPS, []):
            if step.get(CONF_STEP_ID) == step_id:
                return step
        return None

    def _friendly_name(self, entity_id: str, fallback: str = "") -> str:
        """Resolve an entity's friendly name for display."""
        if not entity_id:
            return fallback or entity_id
        state = self.hass.states.get(entity_id)
        return state.attributes.get("friendly_name", entity_id) if state else entity_id

    def _step_choice_selector(self, steps: list[dict[str, Any]]) -> SelectSelector:
        """Build a dropdown of numbered step labels keyed by step id."""
        options = [
            SelectOptionDict(
                value=step.get(CONF_STEP_ID),
                label=step_choice_label(self.hass, idx, step),
            )
            for idx, step in enumerate(steps, 1)
        ]
        return SelectSelector(
            SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
        )
