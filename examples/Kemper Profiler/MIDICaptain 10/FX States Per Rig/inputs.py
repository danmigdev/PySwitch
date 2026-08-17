from pyswitch.hardware.devices.pa_midicaptain_10 import *
from pyswitch.clients.kemper import KemperEffectSlot
from pyswitch.clients.kemper.actions.effect_state_dynamic import EFFECT_STATE_DYNAMIC
from pyswitch.clients.kemper.actions.rig_select import RIG_SELECT, RIG_SELECT_DISPLAY_TARGET_RIG
from pyswitch.clients.kemper.actions.bank_up_down import BANK_UP, BANK_DOWN
from display import DISPLAY_SWITCH_3, DISPLAY_SWITCH_4

# The slot(s) each switch controls are not configured here at all: they are read live from a
# token embedded in the Kemper rig name (see the README for the rig names used in this example
# and how to set them up on the device). Reorganizing which slot a switch controls on a given
# rig only needs a rig rename on the Kemper, no redeploy of this file.

Inputs = [

    # Switch 1 — not used in this example
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_1,
        "actions": []
    },

    # Switch 2 — not used in this example
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_2,
        "actions": []
    },

    # Switch 3 — reads digit position 1 of the rig name token. No default: off on any rig
    # whose name has no token (or a token shorter than 1 character).
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_3,
        "actions": [
            EFFECT_STATE_DYNAMIC(
                digit_position = 1,
                display = DISPLAY_SWITCH_3
            )
        ]
    },

    # Switch 4 — reads digit position 2. Falls back to slot C (Compressor) on any rig with no
    # token / a too-short token, so most rigs get a sensible default without needing a token
    # at all; only rigs that need something else get tagged.
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_4,
        "actions": [
            EFFECT_STATE_DYNAMIC(
                digit_position = 2,
                default_slot_id = KemperEffectSlot.EFFECT_SLOT_ID_C,
                display = DISPLAY_SWITCH_4
            )
        ]
    },

    # Switch UP — reads digit positions 3 and 4 together (AND logic): the LED is on only when
    # both slots are engaged, and pressing turns both on or both off together.
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_UP,
        "actions": [
            EFFECT_STATE_DYNAMIC(
                digit_position = [3, 4],
                display = None
            )
        ]
    },

    # Switch A — Rig 1, hold: Bank Down (keeps the current rig slot within the new bank)
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_A,
        "actions": [
            RIG_SELECT(
                rig = 1,
                display_mode = RIG_SELECT_DISPLAY_TARGET_RIG
            )
        ],
        "actionsHold": [
            BANK_DOWN(
                display_mode = RIG_SELECT_DISPLAY_TARGET_RIG,
                text = "Bank dn"
            )
        ]
    },

    # Switch B — Rig 2
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_B,
        "actions": [
            RIG_SELECT(
                rig = 2,
                display_mode = RIG_SELECT_DISPLAY_TARGET_RIG
            )
        ]
    },

    # Switch C — Rig 3
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_C,
        "actions": [
            RIG_SELECT(
                rig = 3,
                display_mode = RIG_SELECT_DISPLAY_TARGET_RIG
            )
        ]
    },

    # Switch D — Rig 4
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_D,
        "actions": [
            RIG_SELECT(
                rig = 4,
                display_mode = RIG_SELECT_DISPLAY_TARGET_RIG
            )
        ]
    },

    # Switch DOWN — Rig 5, hold: Bank Up (keeps the current rig slot within the new bank)
    {
        "assignment": PA_MIDICAPTAIN_10_SWITCH_DOWN,
        "actions": [
            RIG_SELECT(
                rig = 5,
                display_mode = RIG_SELECT_DISPLAY_TARGET_RIG
            )
        ],
        "actionsHold": [
            BANK_UP(
                display_mode = RIG_SELECT_DISPLAY_TARGET_RIG,
                text = "Bank up"
            )
        ]
    },

]
