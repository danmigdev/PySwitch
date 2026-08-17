import sys
import unittest
from unittest.mock import patch

from .mocks_lib import *

with patch.dict(sys.modules, {
    "micropython": MockMicropython,
    "displayio": MockDisplayIO(),
    "adafruit_display_text": MockAdafruitDisplayText(),
    "adafruit_midi.control_change": MockAdafruitMIDIControlChange(),
    "adafruit_midi.system_exclusive": MockAdafruitMIDISystemExclusive(),
    "adafruit_midi.midi_message": MockAdafruitMIDIMessage(),
    "adafruit_midi.program_change": MockAdafruitMIDIProgramChange(),
    "adafruit_display_shapes.rect": MockDisplayShapes().rect(),
    "gc": MockGC()
}):
    from lib.pyswitch.clients.kemper import KemperEffectSlot
    from lib.pyswitch.clients.kemper.actions.effect_state_dynamic import (
        EFFECT_STATE_DYNAMIC,
        KemperEffectEnableDynamicCallback,
        TOKEN_LETTER_TO_SLOT,
    )
    from lib.pyswitch.controller.actions import PushButtonAction

    from .mocks_appl import MockClient


class _MockLedAction:
    """Mock PushButtonAction exposing LED writes for debounce tests."""
    def __init__(self):
        self.label = None
        self.state = False
        self._c = None
        self._b = None
        self.color_writes = []
    @property
    def switch_color(self):
        return self._c
    @switch_color.setter
    def switch_color(self, v):
        self._c = v
        self.color_writes.append(v)
    @property
    def switch_brightness(self):
        return self._b
    @switch_brightness.setter
    def switch_brightness(self, v):
        self._b = v
    def feedback_state(self, s):
        self.state = s


A   = KemperEffectSlot.EFFECT_SLOT_ID_A
B   = KemperEffectSlot.EFFECT_SLOT_ID_B
C   = KemperEffectSlot.EFFECT_SLOT_ID_C
D   = KemperEffectSlot.EFFECT_SLOT_ID_D
X   = KemperEffectSlot.EFFECT_SLOT_ID_X
MOD = KemperEffectSlot.EFFECT_SLOT_ID_MOD
DLY = KemperEffectSlot.EFFECT_SLOT_ID_DLY
REV = KemperEffectSlot.EFFECT_SLOT_ID_REV


class _MockAppl:
    """Minimal mock application for callback init."""
    config = {}

    def __init__(self):
        self.client = MockClient()

    def add_updateable(self, _):
        pass


def _init_cb(cb):
    appl = _MockAppl()
    cb.init(appl)
    return appl


##############################################################################
# Factory
##############################################################################

class TestEffectStateDynamicFactory(unittest.TestCase):

    def test_factory_returns_push_button_action(self):
        action = EFFECT_STATE_DYNAMIC(digit_position = 1)
        self.assertIsInstance(action, PushButtonAction)
        self.assertIsInstance(action.callback, KemperEffectEnableDynamicCallback)


##############################################################################
# Letter -> slot map, incl. M/L/R
##############################################################################

class TestTokenLetterToSlot(unittest.TestCase):

    def test_letters_map_to_expected_slots(self):
        self.assertEqual(TOKEN_LETTER_TO_SLOT["A"], A)
        self.assertEqual(TOKEN_LETTER_TO_SLOT["B"], B)
        self.assertEqual(TOKEN_LETTER_TO_SLOT["C"], C)
        self.assertEqual(TOKEN_LETTER_TO_SLOT["D"], D)
        self.assertEqual(TOKEN_LETTER_TO_SLOT["X"], X)
        self.assertEqual(TOKEN_LETTER_TO_SLOT["M"], MOD)
        self.assertEqual(TOKEN_LETTER_TO_SLOT["L"], DLY)
        self.assertEqual(TOKEN_LETTER_TO_SLOT["R"], REV)


##############################################################################
# Token parsing / fallback via _current_slots(), single digit position
##############################################################################

class TestSingleDigitPositionResolution(unittest.TestCase):

    def setUp(self):
        self.cb = KemperEffectEnableDynamicCallback(digit_position = 1)

    def test_valid_token_resolves_letter(self):
        self.cb._rig_name_mapping.value = "Lead ((ACXR))"
        self.assertEqual(self.cb._current_slots(), [A])

    def test_letter_is_case_insensitive(self):
        self.cb._rig_name_mapping.value = "Lead ((acxr))"
        self.assertEqual(self.cb._current_slots(), [A])

    def test_no_token_disabled_when_no_default(self):
        self.cb._rig_name_mapping.value = "Plain Rig Name"
        self.assertIsNone(self.cb._current_slots())

    def test_missing_rig_name_disabled_when_no_default(self):
        self.cb._rig_name_mapping.value = None
        self.assertIsNone(self.cb._current_slots())

    def test_unclosed_token_treated_as_no_token(self):
        self.cb._rig_name_mapping.value = "Broken ((ACXR"
        self.assertIsNone(self.cb._current_slots())

    def test_unopened_token_treated_as_no_token(self):
        self.cb._rig_name_mapping.value = "Broken ACXR))"
        self.assertIsNone(self.cb._current_slots())

    def test_unrecognized_letter_disables_button(self):
        self.cb._rig_name_mapping.value = "Weird ((-CXR))"
        self.assertIsNone(self.cb._current_slots())


class TestDefaultSlotFallback(unittest.TestCase):

    def setUp(self):
        self.cb = KemperEffectEnableDynamicCallback(digit_position = 2, default_slot_id = MOD)

    def test_no_token_falls_back_to_default(self):
        self.cb._rig_name_mapping.value = "Plain Rig Name"
        self.assertEqual(self.cb._current_slots(), [MOD])

    def test_missing_rig_name_falls_back_to_default(self):
        self.cb._rig_name_mapping.value = None
        self.assertEqual(self.cb._current_slots(), [MOD])

    def test_token_too_short_falls_back_to_default(self):
        # Token has only 1 character, but digit_position=2 needs a 2nd.
        self.cb._rig_name_mapping.value = "Short ((A))"
        self.assertEqual(self.cb._current_slots(), [MOD])

    def test_token_long_enough_overrides_default(self):
        self.cb._rig_name_mapping.value = "Lead ((AC))"
        self.assertEqual(self.cb._current_slots(), [C])

    def test_unrecognized_letter_in_long_enough_token_disables_not_falls_back(self):
        # Distinct from "too short": this token covers position 2 but with an
        # unrecognized character there, so the whole button is disabled -- it must
        # NOT fall back to default_slot_id.
        self.cb._rig_name_mapping.value = "Weird ((A-))"
        self.assertIsNone(self.cb._current_slots())


##############################################################################
# Multi-digit AND logic, incl. partial-unrecognized-disables-all
##############################################################################

class TestMultiDigitPositionResolution(unittest.TestCase):

    def setUp(self):
        self.cb = KemperEffectEnableDynamicCallback(digit_position = [1, 2, 3, 4])

    def test_all_positions_recognized(self):
        self.cb._rig_name_mapping.value = "Lead ((ACXR))"
        self.assertEqual(self.cb._current_slots(), [A, C, X, REV])

    def test_one_unrecognized_position_disables_whole_button(self):
        # Position 3 is '-': even though 1, 2 and 4 are valid, the whole button
        # is disabled (all-or-nothing), not a partial/subset AND.
        self.cb._rig_name_mapping.value = "Lead ((AC-R))"
        self.assertIsNone(self.cb._current_slots())

    def test_last_unrecognized_position_disables_whole_button(self):
        self.cb._rig_name_mapping.value = "Lead ((ACX-))"
        self.assertIsNone(self.cb._current_slots())


##############################################################################
# Custom delimiters
##############################################################################

class TestCustomDelimiters(unittest.TestCase):

    def test_custom_delimiters_are_used_instead_of_defaults(self):
        cb = KemperEffectEnableDynamicCallback(
            digit_position = 1,
            token_start = "[[",
            token_end = "]]"
        )
        cb._rig_name_mapping.value = "Lead [[ACXR]]"
        self.assertEqual(cb._current_slots(), [A])

    def test_default_delimiters_not_recognized_when_custom_set(self):
        cb = KemperEffectEnableDynamicCallback(
            digit_position = 1,
            token_start = "[[",
            token_end = "]]"
        )
        cb._rig_name_mapping.value = "Lead ((ACXR))"
        self.assertIsNone(cb._current_slots())

    def test_plain_parens_survive_with_double_paren_defaults(self):
        cb = KemperEffectEnableDynamicCallback(digit_position = 1)
        cb._rig_name_mapping.value = "Lead (Live) ((ACXR))"
        self.assertEqual(cb._current_slots(), [A])


##############################################################################
# state_changed_by_user — multi-slot AND logic toggle
##############################################################################

class TestMultiSlotToggle(unittest.TestCase):

    def test_all_on_turns_all_off(self):
        cb = KemperEffectEnableDynamicCallback(digit_position = [1, 2])
        appl = _init_cb(cb)
        cb._rig_name_mapping.value = "Lead ((MC))"

        cb._state_map(MOD).value = 1
        cb._state_map(C).value = 1
        appl.client.set_calls.clear()

        cb.state_changed_by_user()

        sent = {call["mapping"]: call["value"] for call in appl.client.set_calls}
        self.assertEqual(sent[cb._state_map(MOD)], 0)
        self.assertEqual(sent[cb._state_map(C)], 0)

    def test_not_all_on_turns_all_on(self):
        cb = KemperEffectEnableDynamicCallback(digit_position = [1, 2])
        appl = _init_cb(cb)
        cb._rig_name_mapping.value = "Lead ((MC))"

        cb._state_map(MOD).value = 1
        cb._state_map(C).value = 0
        appl.client.set_calls.clear()

        cb.state_changed_by_user()

        sent = {call["mapping"]: call["value"] for call in appl.client.set_calls}
        self.assertEqual(sent[cb._state_map(MOD)], 1)
        self.assertEqual(sent[cb._state_map(C)], 1)

    def test_disabled_rig_does_nothing(self):
        cb = KemperEffectEnableDynamicCallback(digit_position = [1, 2])
        appl = _init_cb(cb)
        cb._rig_name_mapping.value = "Plain Rig Name"   # no token, no default -> disabled
        appl.client.set_calls.clear()

        cb.state_changed_by_user()

        self.assertEqual(appl.client.set_calls, [])


##############################################################################
# Display / LED update on rig change
##############################################################################

class TestDisplayUpdateOnRigChange(unittest.TestCase):

    def _build(self, digit_position = 1, default_slot_id = None):
        cb = KemperEffectEnableDynamicCallback(digit_position = digit_position, default_slot_id = default_slot_id)
        _init_cb(cb)
        cb.action = _MockLedAction()
        return cb

    def test_rig_change_triggers_display_refresh(self):
        cb = self._build()
        cb._rig_name_mapping.value = "Lead ((A))"
        cb._type_map(A).value = 65

        cb.parameter_changed(cb._rig_name_mapping)

        self.assertEqual(cb._last_rendered_slots, [A])

    def test_disabled_rig_clears_led_and_label(self):
        cb = self._build()
        cb.action.label = type("L", (), {"text": "stale"})()
        cb._rig_name_mapping.value = "Plain Rig Name"

        cb.update_displays()

        self.assertEqual(cb.action.switch_brightness, 0)
        self.assertEqual(cb.action.label.text, "")
        self.assertIsNone(cb._last_rendered_slots)


##############################################################################
# Multi-slot must render the LED in a single write (NeoPixels auto-show, so a
# bright->dim double write flashes the LED).
##############################################################################

class TestMultiSlotSingleLedWrite(unittest.TestCase):

    def _build(self, mod_state, c_state):
        cb = KemperEffectEnableDynamicCallback(digit_position = [1, 2])
        _init_cb(cb)
        cb.action = _MockLedAction()
        cb._rig_name_mapping.value = "Lead ((MC))"
        cb._state_map(MOD).value = mod_state
        cb._state_map(C).value = c_state
        cb._type_map(MOD).value = 65   # Chorus
        cb._type_map(C).value = 65
        return cb

    def test_not_all_on_writes_led_once(self):
        cb = self._build(1, 0)
        cb.update_displays()
        self.assertEqual(len(cb.action.color_writes), 1)
        self.assertFalse(cb.action.state)

    def test_all_on_writes_led_once(self):
        cb = self._build(1, 1)
        cb.update_displays()
        self.assertEqual(len(cb.action.color_writes), 1)
        self.assertTrue(cb.action.state)

    def test_all_off_writes_led_once(self):
        cb = self._build(0, 0)
        cb.update_displays()
        self.assertEqual(len(cb.action.color_writes), 1)
        self.assertFalse(cb.action.state)

    def test_first_slot_value_is_restored(self):
        cb = self._build(1, 0)
        cb.update_displays()
        self.assertEqual(cb._state_map(MOD).value, 1)
        self.assertEqual(cb._state_map(C).value, 0)
