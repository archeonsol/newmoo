# Programs

> **Design intent — not yet implemented.** This document describes the planned program ecosystem. The execution framework exists (`patch <program>`) but most individual programs do not yet exist in code.

---

## Acquisition

**Deckers** craft programs in advance and deploy them on a potion-like system (limited uses, crafted ahead of time).

**Psionics** conjure programs at-will (balance via power level, casting time, or whatever makes sense).

---

## Program Types

### CRUD
Create, Read, Update, Delete — basic file manipulation on device storage.

### Encrypt / Decrypt
Secure and unsecure data files.

### Beacon / Recall
Conjure a beacon at a location; recall to it later.

### Trace
Locate a specific device in the Matrix (which relay, physical location).

### Probe
Examine properties of a device or room in the Matrix.

### Scan
Get a list of objects in a location (current room, adjacent room).

### Crack (Combat)
Attack programs, manifested as weapons for deckers. Psionics can conjure these naturally.

---

## File Types

| Extension | Purpose |
|-----------|---------|
| `.lnk` | Device connection reference |
| `.dat` | Generic data file |
| `.exe` | Executable program |
| `.enc` | Encryption key |

### Notable `.exe` Programs

| Program | Function |
|---------|----------|
| `exfil.exe` | Extract a file from device storage → physical data chip |
| `wedge.exe` | Add yourself (or another) to a device's ACL |
| `dewedge.exe` | Remove from ACL |
| `cmd.exe` | Open device operation menu at ACL level 1-9 (level based on program quality / crafter skill) |
| `sudo.exe` | Open device operation menu at ACL level 10 |

> **Note:** `cmd.exe` / `sudo.exe` are partially implemented — the `operate` command opens the same device menu from meatspace, and `patch cmd.exe` should work the same from the Matrix. ACL level override based on crafter skill is future work.
