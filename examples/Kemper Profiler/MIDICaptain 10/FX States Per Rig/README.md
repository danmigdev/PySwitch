## Example Description

This demonstrates `EFFECT_STATE_DYNAMIC`: a switch controls a different Kemper effect slot
depending on which rig is active, without any per-rig table in `inputs.py`. Instead, the slot
assignment is read live from a token embedded in the **Kemper rig name** itself, e.g. a rig
named `Clean ((X-LR))` tells switch 3 to control slot X, tells switch 4 to stay off, and tells
switch UP to control slots DLY+REV together. Reorganizing which slot a switch controls on a
given rig only needs a rig rename on the Kemper — no redeploy of this file.

Each switch reads one or more fixed digit position(s) of the token (1-indexed, letters ->
slots: `A,B,C,D,X` map directly, `MOD` -> `M`, `DLY` -> `L`, `REV` -> `R`; any other character,
by convention `-`, disables the switch for that rig). This example uses a 4-character token:

| Position | Used by            |
|----------|---------------------|
| 1        | Switch 3            |
| 2        | Switch 4            |
| 3 + 4    | Switch UP (AND logic) |

To reproduce the behavior below, rename the rigs in bank 1 on the Kemper like this (the
`((...))` part is stripped automatically from the on-screen rig name label):

| Rig | Suggested name       | Switch 3 | Switch 4 | Switch UP |
|-----|-----------------------|----------|----------|-----------|
| 1   | `Acoustic ((-M--))`   | off      | MOD      | off       |
| 2   | `Clean ((X-LR))`      | X        | off      | DLY+REV   |
| 3   | `Crunch ((X-LR))`     | X        | off      | DLY+REV   |
| 4   | `Heavy ((-XLR))`      | off      | X        | DLY+REV   |
| 5   | `Lead ((X---))`       | X        | off      | off       |

Switch 4 also sets `default_slot_id = KemperEffectSlot.EFFECT_SLOT_ID_C`: any rig with no
token at all (or a token shorter than 2 characters) falls back to slot C (Compressor) instead
of turning off, so most rigs elsewhere on the device get a sensible default without needing to
be tagged. Explicit `-` in a present, long-enough token (as in rigs 2, 3 and 5 above) still
disables the switch — it does not fall back to the default.

Switches A-E also demonstrate `BANK_UP`/`BANK_DOWN` on long press, which keep the currently
selected rig slot when moving to the next/previous bank instead of resetting it.

| Switch     | Short Press | Long Press |
|------------|-------------|------------|
| Switch 1   | (not used)  |            |
| Switch 2   | (not used)  |            |
| Switch 3   | FX per rig token, digit position 1 |  |
| Switch 4   | FX per rig token, digit position 2 (default: Compressor) |  |
| Switch up  | FX per rig token, digit positions 3+4 together (AND logic) |  |
| Switch A   | Select rig 1 of curr. bank | Bank down (keeps rig slot) |
| Switch B   | Select rig 2 of curr. bank |  |
| Switch C   | Select rig 3 of curr. bank |  |
| Switch D   | Select rig 4 of curr. bank |  |
| Switch dn  | Select rig 5 of curr. bank | Bank up (keeps rig slot) |
