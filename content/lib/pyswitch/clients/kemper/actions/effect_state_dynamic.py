from ....controller.actions import PushButtonAction
from ...kemper import KemperMappings, KemperEffectSlot, KEMPER_RIG_NAME_TOKEN_START, KEMPER_RIG_NAME_TOKEN_END, kemper_parse_rig_name_token
from .effect_state import KemperEffectEnableCallback


# Letters recognized inside a rig-name token, mapped to Kemper effect slot IDs. MOD/DLY/REV
# use single letters M/L/R (L instead of D, which would collide with slot D). Letters are
# matched case-insensitively. Any character not in this map (the docs suggest "-" as a
# convention) disables the button for that digit position.
TOKEN_LETTER_TO_SLOT = {
    "A": KemperEffectSlot.EFFECT_SLOT_ID_A,
    "B": KemperEffectSlot.EFFECT_SLOT_ID_B,
    "C": KemperEffectSlot.EFFECT_SLOT_ID_C,
    "D": KemperEffectSlot.EFFECT_SLOT_ID_D,
    "X": KemperEffectSlot.EFFECT_SLOT_ID_X,
    "M": KemperEffectSlot.EFFECT_SLOT_ID_MOD,
    "L": KemperEffectSlot.EFFECT_SLOT_ID_DLY,
    "R": KemperEffectSlot.EFFECT_SLOT_ID_REV,
}


# Switch an effect slot on / off, with the slot assigned dynamically from a token embedded in
# the Kemper rig name, instead of a config-side per-rig table. Rename rigs on the Kemper to
# reorganize which slot a button controls, with no PySwitch config change needed.
#
# The token is a run of letters between delimiters in the rig name, e.g. a rig named
# "Lead ((ACXR))" encodes slot A at digit position 1, C at position 2, X at position 3 and
# R at position 4. Letter -> slot mapping: A, B, C, D, X map to the slots of the same name;
# MOD -> M, DLY -> L, REV -> R (see TOKEN_LETTER_TO_SLOT).
#
# digit_position:  Which digit position(s) of the token this button reads. Either a single
#                   int or a list of ints (1-indexed into the token content). A list controls
#                   all resolved slots together with AND logic: the LED shows ON only when all
#                   of them are ON, and pressing the button turns them all on or all off together.
# default_slot_id:  Slot used when the current rig name has no token at all, or the token is
#                   too short to cover the requested digit_position(s). Pass None (the default)
#                   to disable the button in that case.
# token_start,
# token_end:        Token delimiters, default "((" / "))" (so plain "(" / ")" can still be used
#                   elsewhere in rig names).
#
# Within a present, long-enough token, any digit position that doesn't resolve to a recognized
# letter disables the button entirely for that rig (all-or-nothing, even in the multi-position
# case) -- this is different from a missing/too-short token, which falls back to default_slot_id.
#
# Examples:
#   # Button follows whatever slot digit position 1 of the token names; disabled on rigs
#   # without a token:
#   EFFECT_STATE_DYNAMIC(
#       digit_position = 1
#   )
#
#   # Button controls the slots named at positions 2 and 4 together (AND logic); falls back to
#   # slot MOD on rigs with no token or a token shorter than 4 characters:
#   EFFECT_STATE_DYNAMIC(
#       digit_position = [2, 4],
#       default_slot_id = KemperEffectSlot.EFFECT_SLOT_ID_MOD
#   )
def EFFECT_STATE_DYNAMIC(
        digit_position,
        default_slot_id = None,
        token_start = KEMPER_RIG_NAME_TOKEN_START,
        token_end = KEMPER_RIG_NAME_TOKEN_END,
        display = None,
        mode = PushButtonAction.HOLD_MOMENTARY,
        show_slot_names = False,
        id = False,
        text = None,
        color = None,
        use_leds = True,
        enable_callback = None
    ):
    return PushButtonAction({
        "callback": KemperEffectEnableDynamicCallback(
            digit_position = digit_position,
            default_slot_id = default_slot_id,
            token_start = token_start,
            token_end = token_end,
            text = text,
            color = color,
            show_slot_names = show_slot_names
        ),
        "mode": mode,
        "display": display,
        "id": id,
        "useSwitchLeds": use_leds,
        "enableCallback": enable_callback,
    })


class KemperEffectEnableDynamicCallback(KemperEffectEnableCallback):
    """
    Like KemperEffectEnableCallback but the slot is resolved per rig from a token embedded in
    the rig name, instead of a fixed slot_id.

    digit_position:  Digit position(s) read from the token (1-indexed). Single int or list of ints.
    default_slot_id: Slot used when the rig name has no token, or a too-short one. None disables
                      the button in that case.
    token_start,
    token_end:        Token delimiters. See EFFECT_STATE_DYNAMIC docstring for details.
    """

    def __init__(self, digit_position, default_slot_id = None, token_start = KEMPER_RIG_NAME_TOKEN_START, token_end = KEMPER_RIG_NAME_TOKEN_END, **kwargs):
        self._positions = digit_position if isinstance(digit_position, list) else [digit_position]
        self._max_position = max(self._positions)
        self._token_start = token_start
        self._token_end = token_end
        self._default_slot_id = default_slot_id

        # The parent class requires a valid slot_id to set up its MIDI mappings. Any slot works
        # as a stand-in here: all slots reachable via the letter map get registered below anyway.
        _parent_slot = default_slot_id if default_slot_id is not None else TOKEN_LETTER_TO_SLOT["A"]

        super().__init__(_parent_slot, **kwargs)

        # Register state/type mappings for every slot reachable via a token letter, plus
        # default_slot_id if it is not already covered by the letter map (e.g. a no-spillover slot).
        self._state_maps = {}
        self._type_maps = {}
        all_slots = set(TOKEN_LETTER_TO_SLOT.values())
        if default_slot_id is not None:
            all_slots.add(default_slot_id)

        for slot in all_slots:
            if slot == _parent_slot:
                # The parent already registered mappings for this slot; reuse them instead of
                # creating duplicate registrations for the same parameter.
                self._state_maps[slot] = self.mapping
                self._type_maps[slot] = self.mapping_fxtype
            else:
                sm = KemperMappings.EFFECT_STATE(slot)
                tm = KemperMappings.EFFECT_TYPE(slot)
                self._state_maps[slot] = sm
                self._type_maps[slot] = tm
                self.register_mapping(sm)
                self.register_mapping(tm)

        # Track the current rig name via the Kemper RIG_NAME mapping.
        self._rig_name_mapping = KemperMappings.RIG_NAME()
        self.register_mapping(self._rig_name_mapping)
        self._appl_ref = None

        # Last slot set actually rendered. Used to bust the parent display cache only when the
        # active slot set really changes (rig switch), not on every update.
        self._last_rendered_slots = None

    def init(self, appl, listener = None):
        super().init(appl, listener)
        # Store appl reference separately for use in state_changed_by_user().
        # BinaryParameterCallback stores __appl with name mangling, so we keep our own.
        self._appl_ref = appl

    def _current_slots(self):
        """
        Return the effective list of slot IDs for the current rig, resolved from the rig-name
        token. Returns None if the button is disabled for this rig. Returns [default_slot_id]
        (or None) when the rig name has no token, or a token too short for the requested
        digit_position(s).
        """
        token = kemper_parse_rig_name_token(self._rig_name_mapping.value, self._token_start, self._token_end)

        if token is None or len(token) < self._max_position:
            if self._default_slot_id is None:
                return None  # Disabled by default
            return [self._default_slot_id]

        slots = []
        for pos in self._positions:
            letter = token[pos - 1].upper()
            if letter not in TOKEN_LETTER_TO_SLOT:
                return None  # Any unrecognized position disables the whole button
            slots.append(TOKEN_LETTER_TO_SLOT[letter])
        return slots

    def _state_map(self, slot):
        """Return the state mapping for the given slot."""
        return self._state_maps[slot]

    def _type_map(self, slot):
        """Return the type mapping for the given slot."""
        return self._type_maps[slot]

    def state_changed_by_user(self):
        """Send MIDI CC to toggle the effect on the currently active slot(s)."""
        slots = self._current_slots()
        if slots is None:
            return  # Button disabled for this rig

        if len(slots) == 1 and slots[0] == self._default_slot_id:
            super().state_changed_by_user()
            return

        # Multiple slots (or a non-default single slot): AND logic -- all ON -> turn all OFF,
        # else -> turn all ON.
        all_on = all(self._state_map(s).value == 1 for s in slots)
        new_value = 0 if all_on else 1
        for s in slots:
            self._appl_ref.client.set(self._state_map(s), new_value)
        self.update()

    def update_displays(self):
        """Update LED and display label for the currently active slot(s)."""
        slots = self._current_slots()

        if slots is None:
            # Disabled for this rig: turn off LED and clear label.
            # Reset cached display state so the next real slot switch forces a redraw.
            self.reset()
            self.action.switch_brightness = 0
            if self.action.label:
                self.action.label.text = ""
            self._last_rendered_slots = None
            return

        if len(slots) == 1 and slots[0] == self._default_slot_id:
            super().update_displays()
            self._last_rendered_slots = slots
            return

        # Multiple slots (or a non-default single slot): derive color/label from the first
        # slot, AND logic for state.
        first_slot = slots[0]
        multi = len(slots) > 1
        slots_changed = (slots != self._last_rendered_slots)

        # The reset() calls below bust the parent BinaryParameterCallback value cache.
        # They are only needed when:
        #   1. Multiple slots are controlled: the AND correction may set action.state
        #      to False after the parent recorded state=True, and a change in a
        #      secondary slot (not the "first slot" used for color/label) would
        #      otherwise be suppressed by the first-slot value cache, leaving the LED
        #      stuck.
        #   2. The active slot set just changed (rig switch): the color/value caches
        #      from the previous slot must not suppress the redraw for the new slot.
        # For a single, unchanged slot neither applies, so we keep the parent cache to
        # avoid re-blanking the LED on every bidirectional update -- that re-blanking is
        # what makes the LED flicker several times during a rig change.
        need_reset = multi or slots_changed

        if need_reset:
            self.reset()

        # Temporarily redirect self.mapping and self.mapping_fxtype to the first slot so the
        # parent update_displays() reads from the right slot.
        orig_mapping = self.mapping
        orig_fxtype = self.mapping_fxtype
        self.mapping = self._state_map(first_slot)
        self.mapping_fxtype = self._type_map(first_slot)

        if multi:
            # AND logic, rendered in a SINGLE LED write. The NeoPixels auto-show on every
            # brightness assignment, so letting the parent render the first slot (possibly
            # ON) and then correcting to OFF would write the LED twice -- a visible
            # bright->dim flash on every update. Instead pre-compute the AND result and
            # force the first-slot state value so the parent's single render produces the
            # correct brightness directly.
            all_on = all(self._state_map(s).value == 1 for s in slots)
            saved_val = self.mapping.value
            self.mapping.value = 1 if all_on else 0
            super().update_displays()
            self.mapping.value = saved_val
        else:
            super().update_displays()  # Single slot: parent renders state from the slot.

        self.mapping = orig_mapping
        self.mapping_fxtype = orig_fxtype

        # Reset caches again (only when we reset above) so the next call re-evaluates from
        # scratch -- required for multi-slot AND re-checks and right after a slot switch. For
        # a stable single slot we deliberately keep the cache.
        if need_reset:
            self.reset()

        self._last_rendered_slots = slots

    def parameter_changed(self, mapping):
        """
        Called when any registered mapping receives a MIDI update. Trigger a display refresh
        on rig change, or when the active slot(s) change state.
        """
        if mapping is self._rig_name_mapping:
            # Rig changed: refresh the display to reflect the new slot(s).
            self.update_displays()
            return

        active_slots = self._current_slots()
        if active_slots is None or (len(active_slots) == 1 and active_slots[0] == self._default_slot_id):
            super().parameter_changed(mapping)
            return

        # Check if the changed mapping belongs to any active slot.
        for s in active_slots:
            if mapping is self._state_map(s) or mapping is self._type_map(s):
                self.update_displays()
                return

        super().parameter_changed(mapping)
