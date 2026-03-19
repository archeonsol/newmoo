# Program-Device Interaction Framework

This document covers how Matrix programs interact with networked devices, how the unified device interface menu works, and how to build new device types and programs.

> Program names used in examples (`CRUD.exe`, `Skeleton.key`, etc.) are illustrative — canonical names are not yet finalized. See [programs.md](programs.md).

## Accessing Devices

There are two ways to open a device's interface:

**From meatspace:**
```
operate <device>        # open device menu
operate                 # if already inside a device's Interface room
```

**From the Matrix:**
```
patch cmd.exe           # open device operation menu at your ACL level
patch sudo.exe          # open device operation menu at root (level 10) if authorized
```

Both paths launch the same EvMenu (`typeclasses/matrix/device_menu.py`). The `from_matrix` flag passed at launch controls which commands are visible and which skill is used for threshold checks.

Entry point: `start_device_menu(caller, device, from_matrix=False)`

---

## Device Interface Menu

The device menu is driven by `typeclasses/matrix/device_menu.py`. It shows:
- Device info (type, security level, Matrix ID)
- ACL authorization status for the caller
- Available commands (filtered by access mode and skill)
- File browser (if device has storage)
- ACL viewer

Menu node flow:
```
device_main_menu
  ├── node_execute_command  (prompt for args)
  │     └── node_process_command  (execute, return result)
  ├── node_execute_noargs  (execute immediately, no args)
  ├── node_browse_files
  │     ├── node_read_file_prompt
  │     └── node_read_file
  └── node_view_acl
```

Command handlers can return a `(node_name, kwargs)` tuple from `invoke_device_command()` to drive the menu to another node instead of returning to main. This is how the ACL revoke flow works.

---

## NetworkedMixin API

`typeclasses/matrix/mixins/networked.py` — all networked devices inherit this.

### Storage Operations

Devices with `db.has_storage = True` store files as a list of dicts:
```python
{"filename": str, "filetype": str, "contents": str}
```

| Method | Returns | Notes |
|--------|---------|-------|
| `add_file(filename, filetype, contents)` | `bool` | `False` if storage off or file exists |
| `get_file(filename)` | `dict \| None` | |
| `update_file(filename, contents)` | `bool` | `False` if file not found |
| `delete_file(filename)` | `bool` | `False` if file not found |
| `list_files()` | `list` | Empty list if no storage |

### Access Control List (ACL)

The ACL is a dict: `{char_pk: level}` where level is 1-10.

**ACL Levels:**
- `1`: Entry — basic access, can reach interface
- `2-3`: Low — basic authenticated commands
- `4-6`: Medium — standard modification commands
- `7-9`: High — advanced commands, full control
- `10`: Root — all commands including ACL management

For **MatrixAvatars**, `check_acl` checks both the avatar itself AND its physical operator, returning the highest level found. This allows granting Matrix-only access to an avatar without knowing the operator's physical identity.

| Method | Signature | Returns |
|--------|-----------|---------|
| `check_acl` | `(character, required_level=1)` | `int` (0 if not authorized, level if authorized) |
| `get_acl_level` | `(character)` | `int` ACL level (0 if not on list) |
| `add_to_acl` | `(character, level=5)` | `bool` |
| `remove_from_acl` | `(character)` | `bool` |
| `get_acl_names` | `()` | `list[str]` — formatted as `"Name (physical, level 5)"` |

Devices can call `register_acl_commands()` in `at_object_creation()` to add `grant` and `revoke` commands (both require level 10).

### Connection Status

| Method | Returns |
|--------|---------|
| `has_network_coverage()` | `bool` — True if device is in a room with an online router |
| `get_relay()` | `Router \| None` |

### Device Commands

Device commands are registered at creation time and invoked via the device interface menu.

#### Registering Commands

```python
self.register_device_command(
    command_name,           # str: "pan", "record", "jack_out"
    handler_method_name,    # str: name of method on this device
    help_text=None,         # str: shown in menu
    matrix_only=False,      # bool: only accessible from Matrix
    physical_only=False,    # bool: only accessible from meatspace
    auth_level=0,           # int 0-10: minimum ACL level required (0 = public)
    visibility_threshold=0  # int 0-150: minimum skill to see this command
)
```

`auth_level=0` means anyone can invoke it. `auth_level=1` requires being on the ACL. The check is enforced automatically in `invoke_device_command()`.

`visibility_threshold` hides commands from callers below the threshold skill level. Matrix access uses the `cyberdecking` skill. Physical access skill is TBD.

#### Invoking Commands

```python
invoke_device_command(command_name, caller, from_matrix=False, *args)
```

Returns `True`/`False`, or a `(node_name, kwargs)` tuple if the handler wants to navigate the menu.

#### Getting Available Commands

```python
get_available_commands(caller=None, from_matrix=False)
# Returns {command_name: help_text} filtered by access mode and skill threshold
```

---

## Creating Custom Device Types

```python
from typeclasses.matrix.objects import NetworkedObject

class SecurityCamera(NetworkedObject):
    def at_object_creation(self):
        super().at_object_creation()
        self.setup_networked_attrs()

        self.db.device_type = "camera"
        self.db.has_controls = True
        self.db.security_level = 3

        # Public command — anyone can check status
        self.register_device_command(
            "status", "handle_status",
            help_text="Show camera direction and recording state",
            auth_level=0
        )
        # Requires ACL level 5 to control
        self.register_device_command(
            "pan", "handle_pan",
            help_text="Pan camera: pan <direction>",
            auth_level=5
        )
        # Matrix-only, hidden below cyberdecking 75
        self.register_device_command(
            "disable", "handle_disable",
            help_text="Disable camera (exploit)",
            matrix_only=True, auth_level=0, visibility_threshold=75
        )

    def handle_status(self, caller, *args):
        direction = self.db.get("camera_direction", "north")
        caller.msg(f"Camera facing {direction}.")
        return True

    def handle_pan(self, caller, *args):
        if not args:
            caller.msg("Usage: pan <north|south|east|west>")
            return False
        self.db.camera_direction = args[0].lower()
        caller.msg(f"Camera panned {args[0]}.")
        return True

    def handle_disable(self, caller, *args):
        self.db.disabled = True
        caller.msg("|gCamera disabled.|n")
        return True
```

---

## Creating Custom Programs

```python
from typeclasses.matrix.programs.base import Program

class MyProgram(Program):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "myprog.exe"
        self.db.program_type = "utility"
        self.db.requires_device = True   # False if usable anywhere
        self.db.max_uses = 10            # None for unlimited
        self.db.uses_remaining = 10
        self.db.quality = 1
        self.db.desc = "My custom program."

    def execute(self, caller, device, *args):
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted.|n")
            return False

        if not device:
            caller.msg("|rNo device connected.|n")
            return False

        if not device.db.has_storage:
            caller.msg("|rDevice has no storage.|n")
            return False

        files = device.list_files()
        caller.msg(f"Found {len(files)} files.")

        self.degrade()
        return True
```

**Program vs Device Command — when to use which:**

| Use a **Program** | Use a **Device Command** |
|---|---|
| Hacking / exploiting | Legitimate device control |
| Limited-use operations | Unlimited-use operations |
| Illegal activities | Owner/authorized actions |
| Cross-device functionality | Device-specific functionality |
| Combat / ICE interaction | Configuration / customization |

---

## Skill-Gated Commands

`visibility_threshold` on a device command hides it from callers below that skill level. This creates natural progression tiers without adding special access checks:

```
threshold 0   — public, everyone sees it
threshold 25  — basic skill required
threshold 50  — intermediate
threshold 75  — advanced, most corporate systems cap here
threshold 100 — expert / military grade
threshold 125 — rare, black market programs may be needed
```

Combine with `matrix_only=True` to create commands that only skilled deckers can discover remotely while physical access remains open to lower thresholds.

Example progression for a corporate file server:
```python
# Anyone with physical access sees this
self.register_device_command("status", "handle_status", auth_level=0)

# Deckers with moderate skill see this from Matrix
self.register_device_command("list_processes", "handle_list_procs",
    matrix_only=True, visibility_threshold=50)

# Only skilled deckers can find this exploit
self.register_device_command("inject_backdoor", "handle_backdoor",
    matrix_only=True, visibility_threshold=100, auth_level=0)
```

---

## Technical Notes

### ACL Resolution for MatrixAvatars

When checking ACL for a MatrixAvatar, the framework checks both the avatar itself and its physical operator, returning the highest level. This means:
- A character added to the ACL (physical entry) retains that access when they jack in as their avatar
- An avatar can be granted Matrix-only access without revealing the operator's identity

### Command Registry Persistence

Device commands are stored as strings (method names) rather than function references. This survives server restarts and avoids pickling issues. `invoke_device_command()` uses `getattr()` at call time.

### ACL Migration

The ACL was previously a list of character dbrefs. A migration method (`_migrate_acl()`) handles old-format data in-place, defaulting migrated entries to level 5. It is called automatically by all ACL methods.
