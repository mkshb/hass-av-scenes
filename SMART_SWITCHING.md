# Smart Activity Switching

When an activity starts while another one runs in the same room, AV Scenes does not stop everything and start again. It compares the device lists of both activities:

| Device is used by … | What happens |
|---------------------|--------------|
| old and new activity | stays on; the new activity's steps reconfigure it (source, volume, …) |
| old activity only | switched off |
| new activity only | switched on (after its power outlet and readiness check) |

Power outlets follow the devices:

- An outlet stays on as long as any device of the new activity hangs on it.
- An outlet that is no longer needed is switched off **in the background** once every device on it had its `delay_after_off`. The new activity does not wait for that.
- If the outlet is needed again before that (e.g. switching back), the pending switch-off is cancelled.

`on_stop` of the old activity does **not** run when switching; it is meant for leaving the room idle (opening covers, lights back on).

## Example

```yaml
devices:
  onkyo:  {entity_id: media_player.onkyo_receiver, power_switch: switch.steckdose_multimedia}
  vu:     {entity_id: media_player.vu_as2b_de,     power_switch: switch.steckdose_multimedia}
  beamer: {entity_id: media_player.epson_ehtw7400, power_switch: switch.steckdose_beamer,
           delay_after_off: 180}
activities:
  tv:    {devices: [onkyo, beamer, vu], steps: [{type: set_source, device: onkyo, source: SAT}]}
  musik: {devices: [onkyo],             steps: [{type: set_source, device: onkyo, source: NET}]}
```

Switching **TV → Musik**:

1. VU+ off, projector off
2. Onkyo stays on (no warm-up delay, since it is already on); source changes SAT → NET
3. `switch.steckdose_multimedia` stays on — the Onkyo still needs it
4. `switch.steckdose_beamer` is switched off 180 s later, in the background

Musik is `active` right after step 2.

## Stopping

A full stop is different: it waits. Devices are switched off in reverse order, each followed by its `delay_after_off`, and the outlets go last — so the projector gets its cool-down before its power is cut. See [README](README.md#stop).
