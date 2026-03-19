# Matrix Concepts

The Matrix is the city's cyberspace network — a traversable virtual space that mirrors and connects physical infrastructure. Characters can "jack in" via a DiveRig, spawning an avatar that navigates virtual geography while their body remains in meatspace.

Sections marked **[planned]** describe intended design that is not yet implemented in code.

---

## Network Architecture

### The Frame
The central AGI that runs the city's core infrastructure. A mysterious, possibly sentient intelligence housed in a heavily fortified server farm. The guilds have historically worked to keep The Frame in check.

### CORTEX
The main street of the Matrix. A public marketplace and social hub where data and programs are bought and sold. Acts as the central routing point between major spine networks. ("Originally stood for something technical, but everyone just calls it the Cortex now.")

### Spines
The hardwired backbone of the network. Major infrastructure branches throughout the city, composed of relay nodes. Each spine has territorial associations:
- **Spine A**: Frame territory, connects through Firewall A-B to Spine B
- **Spine B**: Guild territory, hosts public services
- **Spine C**: Upper class district
- **Spine W**: Working class/service district

Firewalls between spines create security boundaries and political control points.

### Routers
Virtual relay objects that sit in Matrix relay nodes and provide network connectivity to meatspace areas. A meatspace room linked to a router has "network coverage." Devices in that room are discoverable and accessible via the Matrix. Routers can be taken online or offline.

### Nodes
Virtual rooms in the Matrix. There are two broad categories:

- **Persistent nodes**: Spine rooms, public spaces, and any manually built Matrix geography. These exist permanently.
- **Ephemeral device nodes**: Created on-demand when an avatar routes to a networked device. Automatically cleaned up when empty. See [device_clusters.md](device_clusters.md).

---

## Identity & Matrix IDs

Every object with a Matrix presence has a **Matrix ID** — a unique 6-character alphanumeric code in the format `^XXXXXX`. This is how objects are referenced IC across the network. IDs are permanent and never recycled.

### Aliases
Characters can set a human-readable **alias** linked to their Matrix ID. An alias is used as a callsign: it appears as your avatar's name, your sender ID on network messages, and (eventually) your social media handle. Aliases follow `@username` conventions. One alias per character; changes have a cooldown.

### Jailbroken Handsets **[planned]**
Long-term, handsets will be able to act as their own independent Matrix identities. Slotting a jailbroken handset into a DiveRig allows diving as a *different* avatar with a *different* alias — effectively a fake identity. Handsets can be stolen, making this a risk/reward mechanic. This means the character↔avatar relationship is not always 1:1.

### Account Types **[planned]**
- **Citizen**: One per person, tied to city ID
- **Corporate/work**: Issued by employers, monitored
- **Clandestine**: Burner accounts, spoofed IDs, relay exploits

### Profile vs Record **[planned]**
- **Profile**: Public-facing info (editable by user)
- **Record**: Official backend data — identity, linked accounts, logs, infractions. Requires authority access or hacking to view.

---

## Diving & Jacking Out

Characters jack in from a **DiveRig** (a reclined chair/console). The rig must be in a room with network coverage (linked to an online router). Jacking in creates a MatrixAvatar at the router's location and puppets the controlling account over to it.

### Proxy Tunnel
At any given time, a diving avatar has up to three routers to track:

1. **Session origin** — the router the DiveRig is connected to. This is where your connection anchors to meatspace.
2. **Proxy tunnel** *(optional)* — an intermediate router you've designated as a waypoint. Set by visiting a router and opening a proxy tunnel in its menu. This becomes your "recall" point: `route back` from anywhere will return you here first.
3. **Device router** — the router a remote device is connected to, if you are currently inside that device's ephemeral cluster.

`route back` always returns you one step up the chain. To get all the way back to session origin, you must close the proxy tunnel first. If your proxy is in an inconvenient place, you have to physically navigate back to it to close it — there is no shortcut.

The proxy tunnel "sticks" on the avatar, so it persists even if you use different DiveRigs across sessions. Session origin may change, but the proxy does not.

### Jackout Severity
- **Normal**: Clean disconnect, no penalty.
- **Emergency**: Uncontrolled disconnect, minor penalties.
- **Forced**: Violent disconnect, physical damage to the character's body.
- **Fatal**: Avatar death propagates to the physical body.

### Disconnection **[planned]**
If a device loses connection while a character is diving:
- **Graceful** (signal degrading): Warning messages, time to safely jack out.
- **Sudden** (instant loss): Short grace period, then forced jack-out with minor penalties.
- **Violent** (device destroyed): Forced jack-out, major damage, possible unconsciousness.

---

## Devices

### Networked Devices
Any physical object implementing `NetworkedMixin` has a Matrix presence. Devices in a room with network coverage are discoverable via the router serving that room, and can be accessed by avatars navigating to them.

Accessing a device creates an ephemeral 2-room cluster (Checkpoint + Interface). See [device_clusters.md](device_clusters.md).

### DiveRig
The hardware required to jack in. A DiveRig is a seat (characters must be sitting to dive) that also acts as a networked device, with an associated router providing the session origin.

### Handsets **[planned — partial implementation]**
Personal communicators, functionally a cyberpunk smartphone. Tied to a character's Frame ID/alias. Used for texting, network messaging, and (eventually) browsing public services. The handset system is partially implemented; full integration with the Matrix identity and social systems is future work.

### Other Device Types **[planned]**
- **Tablets**: Mid-tier portable devices
- **Consoles**: Stationary workstations, can be hardwired for faster/more reliable access
- **Cameras, terminals, locks**: Specific-purpose networked objects with device-type-specific commands

---

## Programs **[planned — framework implemented, programs mostly not]**

Programs are portable executable objects avatars carry. They are run via `patch <program>` (or `patch <program> <args>`). The execution framework exists; most individual programs are not yet implemented.

Planned program types:
- **CRUD**: Basic file manipulation on device storage
- **exfil.exe / infil.exe**: Extract files to portable data chips / upload chips to device storage
- **Skeleton.key**: ACL manipulation (illegal)
- **cmd.exe / sudo.exe**: Pull up device operation menu at various ACL levels
- **ICEpick.exe**: Combat program for fighting ICE
- **Trace / Probe / Scan**: Network investigation tools
- **Recall**: Return to beacon location
- **Daemons**: Background processes (monitoring, auto-defense, ICE)

See [programs.md](programs.md) for full design intent.

---

## Security & ICE **[planned]**

The checkpoint room in every device cluster is the structural hook for future security enforcement. When implemented:
- Avatars not on a device's ACL will trigger ICE spawn in the checkpoint room
- ICE are daemon creatures that must be defeated (or bypassed via skill/programs) to reach the interface
- The exit from checkpoint to interface will be locked until ACL clears or ICE is defeated

### Decker Trace **[planned]**
Skilled deckers will be able to trace an avatar's connection chain through proxy routers:
- Low-skill result: sees only the exit point
- High-skill result: identifies session origin
- Expert: can force-close a proxy tunnel remotely

This is the adversarial counterpart to the proxy tunnel system.

---

## Public Services (Subframe B) **[planned]**

Historically controlled by the guilds, these services will live in Subframe B:

- **The Feed**: Short public posts, topics/hashtags, auto-archived
- **The Archives**: Permanent record of Feed posts, curated content library
- **Pages**: Static content hosting with FrameML markup
- **Chat/DMs**: Direct messaging between Frame IDs

---

## Design Philosophy

- **No perfect crimes**: Every action leaves traces.
- **Physical/virtual interplay**: Moving a device in meatspace affects Matrix navigation. Device node location follows the device.
- **Tools create depth**: Investigation programs (Trace, Probe) are not default commands — you need the right tools.
- **Security through obscurity works (somewhat)**: Devices aren't automatically visible; someone needs to scan or know the Matrix ID.
- **Persistence where it counts**: Public nodes and spine infrastructure are permanent. Device clusters are ephemeral.
