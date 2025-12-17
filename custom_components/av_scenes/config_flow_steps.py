"""Step-based configuration methods for config_flow.py - to be appended."""

# This file contains the additional step methods that need to be added to config_flow.py
# Copy these methods and append them to the AVScenesOptionsFlow class

    async def async_step_add_step(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a step - select step type."""
        errors = {}

        if user_input is not None:
            try:
                step_type = user_input.get(CONF_STEP_TYPE)
                self.current_step_data = {
                    CONF_STEP_ID: str(uuid.uuid4()),
                    CONF_STEP_TYPE: step_type,
                    CONF_STEP_DELAY_AFTER: 0,
                    CONF_STEP_PARAMETERS: {},
                }

                # If step type is DELAY, we don't need entity selection
                if step_type == STEP_TYPE_DELAY:
                    return await self.async_step_add_step_delay_config()
                else:
                    return await self.async_step_add_step_entity()
            except Exception as ex:
                _LOGGER.exception("Error in add_step: %s", ex)
                errors["base"] = "unknown"

        # Build step type options with descriptions
        step_types = {
            STEP_TYPE_POWER_ON: "Turn on device",
            STEP_TYPE_SET_SOURCE: "Set input source (media player)",
            STEP_TYPE_SET_VOLUME: "Set volume (media player)",
            STEP_TYPE_SET_BRIGHTNESS: "Set brightness/color (light)",
            STEP_TYPE_SET_COLOR_TEMP: "Set color temperature (light)",
            STEP_TYPE_SET_POSITION: "Set position (cover)",
            STEP_TYPE_SET_TILT: "Set tilt (cover)",
            STEP_TYPE_DELAY: "Wait/Delay",
        }

        return self.async_show_form(
            step_id="add_step",
            data_schema=vol.Schema({
                vol.Required(CONF_STEP_TYPE): vol.In(step_types),
            }),
            errors=errors,
            description_placeholders={
                "info": "Select the type of step to add. Steps are executed in order.",
            },
        )

    async def async_step_add_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select entity for the step."""
        errors = {}

        if user_input is not None:
            try:
                entity_id = user_input.get(CONF_ENTITY_ID)

                # Validate entity exists
                state = self.hass.states.get(entity_id)
                if state is None:
                    errors[CONF_ENTITY_ID] = "entity_not_found"
                else:
                    self.current_step_data[CONF_ENTITY_ID] = entity_id
                    return await self.async_step_add_step_config()
            except Exception as ex:
                _LOGGER.exception("Error in add_step_entity: %s", ex)
                errors["base"] = "unknown"

        # Get step type to filter entities
        step_type = self.current_step_data.get(CONF_STEP_TYPE)

        # Determine which domains to show based on step type
        if step_type in [STEP_TYPE_SET_SOURCE, STEP_TYPE_SET_VOLUME]:
            supported_domains = ["media_player"]
        elif step_type in [STEP_TYPE_SET_BRIGHTNESS, STEP_TYPE_SET_COLOR_TEMP]:
            supported_domains = ["light"]
        elif step_type in [STEP_TYPE_SET_POSITION, STEP_TYPE_SET_TILT]:
            supported_domains = ["cover"]
        else:  # POWER_ON and others
            supported_domains = ["media_player", "light", "switch", "cover"]

        entities = []
        for domain in supported_domains:
            for entity_id in self.hass.states.async_entity_ids(domain):
                state = self.hass.states.get(entity_id)
                if state:
                    friendly_name = state.attributes.get("friendly_name", entity_id)
                    display_name = f"[{domain}] {friendly_name}"
                    entities.append((entity_id, display_name))

        # Sort by display name
        entities.sort(key=lambda x: x[1])

        # Create entity selector options
        entity_options = {entity_id: name for entity_id, name in entities}

        if not entity_options:
            entity_options = {"": "No entities found"}

        return self.async_show_form(
            step_id="add_step_entity",
            data_schema=vol.Schema({
                vol.Required(CONF_ENTITY_ID): vol.In(entity_options),
            }),
            errors=errors,
            description_placeholders={
                "step_type": step_type,
            },
        )

    async def async_step_add_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure step parameters."""
        errors = {}

        step_type = self.current_step_data.get(CONF_STEP_TYPE)
        entity_id = self.current_step_data.get(CONF_ENTITY_ID)

        if user_input is not None:
            try:
                # Get delay_after
                delay_after = user_input.get(CONF_STEP_DELAY_AFTER, 0)
                self.current_step_data[CONF_STEP_DELAY_AFTER] = delay_after

                # Get step-specific parameters
                parameters = {}

                if step_type == STEP_TYPE_SET_SOURCE:
                    source = user_input.get(CONF_INPUT_SOURCE)
                    if source and source != "none":
                        parameters[CONF_INPUT_SOURCE] = source

                elif step_type == STEP_TYPE_SET_VOLUME:
                    volume_level = user_input.get(CONF_VOLUME_LEVEL, 50)
                    parameters[CONF_VOLUME_LEVEL] = volume_level / 100.0

                elif step_type == STEP_TYPE_SET_BRIGHTNESS:
                    brightness = user_input.get(CONF_BRIGHTNESS)
                    if brightness is not None:
                        parameters[CONF_BRIGHTNESS] = int(brightness * 255 / 100)

                    color_temp = user_input.get(CONF_COLOR_TEMP)
                    if color_temp is not None:
                        parameters[CONF_COLOR_TEMP] = color_temp

                    transition = user_input.get(CONF_TRANSITION)
                    if transition is not None:
                        parameters[CONF_TRANSITION] = transition

                elif step_type == STEP_TYPE_SET_COLOR_TEMP:
                    color_temp = user_input.get(CONF_COLOR_TEMP)
                    if color_temp is not None:
                        parameters[CONF_COLOR_TEMP] = color_temp

                elif step_type == STEP_TYPE_SET_POSITION:
                    position = user_input.get(CONF_POSITION)
                    if position is not None:
                        parameters[CONF_POSITION] = position

                elif step_type == STEP_TYPE_SET_TILT:
                    tilt = user_input.get(CONF_TILT_POSITION)
                    if tilt is not None:
                        parameters[CONF_TILT_POSITION] = tilt

                self.current_step_data[CONF_STEP_PARAMETERS] = parameters

                # Add step to activity
                if CONF_STEPS not in self.current_activity_data:
                    self.current_activity_data[CONF_STEPS] = []

                self.current_activity_data[CONF_STEPS].append(self.current_step_data)
                _LOGGER.info("Added step %s", self.current_step_data[CONF_STEP_ID])

                return await self.async_step_step_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_step_config: %s", ex)
                errors["base"] = "unknown"

        # Get entity state for source list etc.
        state = self.hass.states.get(entity_id)
        friendly_name = state.attributes.get("friendly_name", entity_id) if state else entity_id

        # Build dynamic schema based on step type
        schema_dict = {}

        # Common field for delay
        schema_dict[vol.Optional(CONF_STEP_DELAY_AFTER, default=0)] = vol.All(
            int, vol.Range(min=0, max=60)
        )

        # Step-specific fields
        if step_type == STEP_TYPE_POWER_ON:
            # No additional parameters for power on
            pass

        elif step_type == STEP_TYPE_SET_SOURCE:
            source_list = state.attributes.get("source_list", []) if state else []

            if source_list:
                source_options = {"none": "-- Select source --"}
                for source in source_list:
                    source_options[source] = source
            else:
                source_options = {"none": "-- Device has no sources --"}

            schema_dict[vol.Required(CONF_INPUT_SOURCE, default="none")] = vol.In(source_options)

        elif step_type == STEP_TYPE_SET_VOLUME:
            schema_dict[vol.Required(CONF_VOLUME_LEVEL, default=50)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        elif step_type == STEP_TYPE_SET_BRIGHTNESS:
            schema_dict[vol.Optional(CONF_BRIGHTNESS, default=100)] = vol.All(
                int, vol.Range(min=0, max=100)
            )
            schema_dict[vol.Optional(CONF_COLOR_TEMP)] = vol.All(
                int, vol.Range(min=153, max=500)
            )
            schema_dict[vol.Optional(CONF_TRANSITION, default=0)] = vol.All(
                int, vol.Range(min=0, max=60)
            )

        elif step_type == STEP_TYPE_SET_COLOR_TEMP:
            schema_dict[vol.Required(CONF_COLOR_TEMP, default=250)] = vol.All(
                int, vol.Range(min=153, max=500)
            )

        elif step_type == STEP_TYPE_SET_POSITION:
            schema_dict[vol.Required(CONF_POSITION, default=100)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        elif step_type == STEP_TYPE_SET_TILT:
            schema_dict[vol.Required(CONF_TILT_POSITION, default=50)] = vol.All(
                int, vol.Range(min=0, max=100)
            )

        return self.async_show_form(
            step_id="add_step_config",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "device": friendly_name,
                "step_type": step_type,
                "info": "Configure the parameters for this step. The delay is applied AFTER this step completes.",
            },
        )

    async def async_step_add_step_delay_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure delay step."""
        errors = {}

        if user_input is not None:
            try:
                delay = user_input.get(CONF_STEP_DELAY_AFTER, 1)
                self.current_step_data[CONF_STEP_DELAY_AFTER] = delay
                self.current_step_data[CONF_ENTITY_ID] = ""  # No entity for delay

                # Add step to activity
                if CONF_STEPS not in self.current_activity_data:
                    self.current_activity_data[CONF_STEPS] = []

                self.current_activity_data[CONF_STEPS].append(self.current_step_data)
                _LOGGER.info("Added delay step of %d seconds", delay)

                return await self.async_step_step_menu()
            except Exception as ex:
                _LOGGER.exception("Error in add_step_delay_config: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="add_step_delay_config",
            data_schema=vol.Schema({
                vol.Required(CONF_STEP_DELAY_AFTER, default=1): vol.All(
                    int, vol.Range(min=1, max=60)
                ),
            }),
            errors=errors,
            description_placeholders={
                "info": "How long should the system wait (in seconds)?",
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

            # If done, return to step menu
            if direction == "done":
                # Save if editing existing activity
                if (self.current_room in self.rooms and
                    self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                    self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                    self._save_config()
                return await self.async_step_step_menu()

            if step_id and direction:
                # Find step index
                current_index = None
                for idx, step in enumerate(steps):
                    if step.get(CONF_STEP_ID) == step_id:
                        current_index = idx
                        break

                if current_index is not None:
                    # Calculate new index
                    if direction == "up" and current_index > 0:
                        new_index = current_index - 1
                    elif direction == "down" and current_index < len(steps) - 1:
                        new_index = current_index + 1
                    else:
                        # Can't move further
                        return await self.async_step_reorder_step()

                    # Swap positions
                    steps[current_index], steps[new_index] = steps[new_index], steps[current_index]

                    # Save if editing existing activity
                    if (self.current_room in self.rooms and
                        self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                        self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                        self._save_config()

                    _LOGGER.info("Moved step %s", direction)

            # Stay in reorder mode to allow multiple moves
            return await self.async_step_reorder_step()

        if not steps or len(steps) < 2:
            return await self.async_step_step_menu()

        # Build step selection with current order numbers
        step_options = {}
        for idx, step in enumerate(steps, 1):
            step_id = step.get(CONF_STEP_ID)
            step_type = step.get(CONF_STEP_TYPE, "unknown")
            entity_id = step.get(CONF_ENTITY_ID, "")
            parameters = step.get(CONF_STEP_PARAMETERS, {})

            # Get friendly name
            state = self.hass.states.get(entity_id) if entity_id else None
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else "Delay"

            # Build short description
            if step_type == STEP_TYPE_POWER_ON:
                desc = f"Turn on {friendly_name}"
            elif step_type == STEP_TYPE_SET_SOURCE:
                source = parameters.get(CONF_INPUT_SOURCE, "")
                desc = f"{friendly_name} → {source}"
            elif step_type == STEP_TYPE_DELAY:
                delay = step.get(CONF_STEP_DELAY_AFTER, 0)
                desc = f"Wait {delay}s"
            else:
                desc = f"{step_type} {friendly_name}"

            step_options[step_id] = f"{idx}. {desc}"

        return self.async_show_form(
            step_id="reorder_step",
            data_schema=vol.Schema({
                vol.Required("step_id"): vol.In(step_options),
                vol.Required("direction"): vol.In({
                    "up": "Move up",
                    "down": "Move down",
                    "done": "Done reordering",
                }),
            }),
            description_placeholders={
                "info": "Select a step and choose whether to move it up or down. Steps are executed from top to bottom.",
            },
        )

    async def async_step_select_step_to_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a step to delete."""
        if user_input is not None:
            step_id = user_input.get("step_id")

            steps = self.current_activity_data.get(CONF_STEPS, [])
            # Find and remove step
            self.current_activity_data[CONF_STEPS] = [s for s in steps if s.get(CONF_STEP_ID) != step_id]
            _LOGGER.info("Deleted step %s", step_id)

            # Save if editing existing activity
            if (self.current_room in self.rooms and
                self.current_activity in self.rooms[self.current_room].get(CONF_ACTIVITIES, {})):
                self.rooms[self.current_room][CONF_ACTIVITIES][self.current_activity] = self.current_activity_data
                self._save_config()

            return await self.async_step_step_menu()

        steps = self.current_activity_data.get(CONF_STEPS, [])

        if not steps:
            return await self.async_step_step_menu()

        # Build step selection
        step_options = {}
        for idx, step in enumerate(steps, 1):
            step_id = step.get(CONF_STEP_ID)
            step_type = step.get(CONF_STEP_TYPE, "unknown")
            entity_id = step.get(CONF_ENTITY_ID, "")

            state = self.hass.states.get(entity_id) if entity_id else None
            friendly_name = state.attributes.get("friendly_name", entity_id) if state else "Delay"

            desc = f"{idx}. {step_type} - {friendly_name}"
            step_options[step_id] = desc

        return self.async_show_form(
            step_id="select_step_to_delete",
            data_schema=vol.Schema({
                vol.Required("step_id"): vol.In(step_options),
            }),
            description_placeholders={
                "warning": "This action cannot be undone!",
            },
        )

    async def async_step_select_step_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a step to edit."""
        # For now, redirect to delete - full edit can be added later
        # Editing individual steps is complex, so we'll keep it simple
        return await self.async_step_step_menu()
