# Matrix Device Clusters

Every networked device creates an ephemeral 2-room cluster when accessed from the Matrix. Clusters are created on demand and cleaned up automatically when empty.

## Structure

```
[Router Node]
    ↓  (route via <router>, then navigate to device)
[Checkpoint]   ← Entry point; future ICE spawns here
    ↓  exit: "Interface" / "in"
[Interface]    ← Device interaction happens here
    ↓  exit: "Checkpoint" / "c"
[Checkpoint]
    ↓  route back
[Previous router / session origin]
```

## The Two Rooms

### Checkpoint

The entry room. Future home of ICE security — unauthorized avatars will eventually encounter daemon mobs here. Currently: always passable (the exit to Interface is unlocked). Items cannot be dropped here.

```python
checkpoint.db.parent_object = device  # Physical device reference
checkpoint.db.is_checkpoint = True
checkpoint.db.ephemeral = True
checkpoint.db.node_type = "device_checkpoint"
```

### Interface

The functional room. Programs work here, `operate` opens the device menu, and device storage/commands are accessible. Items cannot be dropped here.

```python
interface.db.parent_object = device  # Physical device reference
interface.db.is_interface = True
interface.db.ephemeral = True
interface.db.node_type = "device_interface"
```

Interface description is set from `device.db.interface_desc` at cluster creation time. If not set, a generic description is generated from the device type.

## Navigation

**Getting there:** Use `route via <router>` to open the router navigation menu, then select the device. You are moved to its checkpoint.

**Within the cluster:**
- `interface` or `in` — move from checkpoint to interface
- `checkpoint` or `c` — move from interface back to checkpoint
- `route back` — leave the cluster and return one step up the proxy chain

**Using the device:** `operate` (from inside the Interface room) opens the device interface menu.

## Lifecycle

**Creation** (`device.get_or_create_cluster()`):
1. Check if `device.db.checkpoint_node` and `device.db.interface_node` exist and are valid
2. If both exist and valid, return the existing cluster
3. If either is missing or stale, delete any partial cluster and create fresh
4. Create checkpoint and interface rooms, link them with `MatrixExit` objects
5. Store room PKs on device: `checkpoint_node`, `interface_node`

**Persistence:** Cluster exists as long as at least one avatar is in either room. Multiple avatars can share a cluster simultaneously.

**Cleanup:** A periodic script deletes clusters where both rooms are empty, then clears the device's `checkpoint_node` and `interface_node` references. The next access creates a fresh cluster from current device state.

**What persists across cluster recreations:** Device storage (files), ACL, `interface_desc`, all other device attributes — everything is stored on the device object, not the rooms.

## Device Attributes

```python
device.db.checkpoint_node = pk      # int or None
device.db.interface_node = pk       # int or None
device.db.device_type = "camera"    # string
device.db.security_level = 3        # 0-10
device.db.has_storage = True
device.db.has_controls = True
device.db.acl = {char_pk: level}    # dict, level 1-10
device.db.storage = [               # list of dicts
    {"filename": "data.txt", "filetype": "text", "contents": "..."},
]
device.db.interface_desc = "..."    # optional custom room desc
```

## Item Handling

Items cannot be dropped in ephemeral nodes. Programs and data chips must be carried in avatar inventory. To move data between inventory and a device, use programs: `exfil.exe` extracts a device file to a portable data chip; `infil.exe` uploads a chip to device storage.

## Future: ICE

The checkpoint is the structural hook for ICE enforcement. When implemented:
- Avatars not on the device ACL will trigger daemon spawns in the checkpoint
- The Interface exit will be locked until ICE is defeated or ACL clears
- The `# TODO: Add lock based on ICE/ACL status` comment in `get_or_create_cluster()` marks where this goes
