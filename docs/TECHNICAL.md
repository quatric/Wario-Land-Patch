# Technical Architecture & Implementation Details

This document explains how the Classic Controller and GameCube controller patches operate in *Wario Land: Shake It!* / *The Shake Dimension*, where they hook into the game's executable, and how a unified operational definition compiles into static DOL patches, Gecko codes, and Riivolution XML files.

---

## 1. Unified Operation Pipeline

Every patch is modeled as a sequence of atomic operations against the game's `main.dol`:

| Operation | Static DOL (`main.dol`) | Gecko Code (`codes/`) | Riivolution (`riivolution/`) |
| --- | --- | --- | --- |
| **Patch** | Overwrite bytes in-place | `04` / `06` code | `<memory value="..." offset="..." />` |
| **Hook** | Branch to injected trampoline section (`0x80001820`), execute displaced instruction, branch back | `C2` code | `<memory>` (branch + trampoline bytes) |

- **Idempotent and Verified**: `tools/prebuilt/<feature>_<region>.json` encodes the expected pristine retail bytes for every site. `tools/patcher.py` verifies these bytes before writing, preventing corruption of already-modified or foreign DOL files.
- **Self-Contained Trampolines**: All hook trampolines carry their required logic or resolve external SDK symbols through absolute addresses.
- **Section Injection**: For static DOL patching, an additional text section is allocated at `0x80001820` (the Wii's boot-time scratch area, which is unused after kernel boot). The section size is padded to a 32-byte boundary to satisfy strict Wii DOL loader alignment.

---

## 2. Low-Memory Layout

```
0x80001820 - 0x80002000 : Classic Controller Hook Trampolines (CC_BASE .. CC_END)
0x80002000 - 0x80002A00 : GameCube Controller Bridge Trampolines (GC_BASE .. GC_END)
0x80003000              : CAVE_LIMIT (End of safe scratch RAM)
...
0x800041c0 - 0x800041d0 : GC Bridge State Struct (STATE: in Section 0 zero-padding)
```

The GameCube bridge maintains a 16-byte state struct at `0x800041c0` (verified zero-padding in Section 0 text across all 4 game builds):
```c
struct GcState {
    u32 initialized;
    u32 counter;
    u32 last_buttons;
    u32 connected;
};
```

---

## 3. Classic Controller Hook Engine

Vague Rant & crediar's Classic Controller patch hooks into the game's high-level controller input processing pipeline:

1. **Motion / Shake / Tilt Hook**:
   Intercepts accelerometer processing. Reads Classic Controller right stick inputs and translates them into tilt angles for aiming throws, driving the submarine, and navigating minecarts.
2. **Pointer Hook**:
   Translates analog stick inputs into pointer coordinates for map screens and UI selection menus.
3. **Stick -> D-Pad Converter**:
   Converts analog left stick deflection into directional D-Pad inputs for character movement and ducking.
4. **Button Remapper**:
   Translates Classic Controller button masks into the game's internal action flags. In **B/A Mode**, A jumps and B attacks; in **Y/B Mode**, B jumps and Y attacks. Both modes assign dedicated shake actions to the top face button (Y in B/A Mode, X in Y/B Mode).

---

## 4. GameCube Controller Bridge

Rather than writing a separate driver from scratch, the GameCube controller support acts as an **SI-to-Classic-Controller synthesis bridge**. It hooks three strategic points in the Revolution SDK:

### A. SI Auto-Polling & Hotplug Recovery (`HOOK_POLL` @ `KPADiRead`)
- Reads the hardware Serial Interface (SI) result registers at `SIC0INBUFH` (`0xCD006404`).
- Handles SI communication errors: If the `NOREP` (no response) latch is set, it checks whether SI auto-polling needs to be re-armed, restores the shadow registers, and triggers a clean rescan.
- Supports runtime hotplugging of the controller in port 1.

### B. Classic Controller Report Synthesizer (`HOOK_SAMPLE` @ `KPADiRead + 0x274`)
- Located just before `KPADiRead`'s sample count check (`lbz r0, 0x10f(r28)`).
- When channel 0 is read and a GameCube controller is detected in port 1:
  - Synthesizes a valid `WPAD_EXP_CLASSIC` data packet directly into the `KPADUnifiedWpad` sample structure.
  - Maps GameCube Control Stick -> Classic Controller Left Stick (`cl.lstick_x`, `cl.lstick_y`).
  - Maps GameCube C-Stick -> Classic Controller Right Stick (`cl.rstick_x`, `cl.rstick_y`).
  - Maps GameCube digital buttons (A, B, X, Y, L, R, Z, Start, D-Pad) to matching Classic Controller button masks according to the active mode (`ba` or `yb`).
  - Sets sample format to `WPAD_FMT_EXP` (format 3) and sample count to 1, ensuring the game processes the synthesized sample immediately.

### C. WPADProbe Expansion Spoofing (`HOOK_PROBE` @ `WPADProbe`)
- Intercepts `WPADProbe(chan, &type)`.
- If channel 0 is probed and a GameCube controller is active, it writes `WPAD_DEV_CLASSIC` (type 2) into `*type` and returns `WPAD_ERR_NONE` (0).
- This allows playing with a GameCube controller even when **no Wii Remote is connected or synced to the console**!

---

## 5. Regional Address Table

The SDK and game hook sites across the four supported revisions:

| Symbol / Hook Site | USA (`RWLE01`) | Europe (`RWLP01`) | Japan Rev 1 (`RWLJ01`) | Korea (`RWLK01`) |
| :--- | :---: | :---: | :---: | :---: |
| **Read Function (HOOK_POLL)** | `0x8040B5F8` | `0x8040BB68` | `0x8040EC6C` | `0x8040B624` |
| **Sample Check (HOOK_SAMPLE)** | `0x8040B6FC` | `0x8040BC6C` | `0x8040ED70` | `0x8040B73C` |
| **WPADProbe (HOOK_PROBE)** | `0x803B0EF0` | `0x803B1460` | `0x803B4564` | `0x803AE9F0` |
| **SIGetType** | `0x803A57B8` | `0x803A5D28` | `0x803A8E2C` | `0x803A53FC` |
| **SiTypes** | `0x804DE888` | `0x804DFB68` | `0x804E2D88` | `0x804E12E8` |
| **SiBusy** | `0x8061FACC` | `0x80620E4C` | `0x8061A2EC` | `0x8060B8C4` |
| **SiShadow** | `0x804DE874` | `0x804DFB54` | `0x804E2D74` | `0x804E12D4` |
| **WpadTbl** | `0x804E0634` | `0x804E1914` | `0x804E4B34` | `0x804E278C` |
| **OSDisableInterrupts** | `0x8041B328` | `0x8041B898` | `0x8041E99C` | `0x804189F4` |
| **OSRestoreInterrupts** | `0x8041B350` | `0x8041B8C0` | `0x8041E9C4` | `0x80418A1C` |
| **CC Hook 1 (Motion)** | `0x80409AB4` | `0x8040A024` | `0x8040D128` | `0x80409A9C` |
| **CC Hook 2 (Pointer)** | `0x8040ABDC` | `0x8040B14C` | `0x8040E250` | `0x8040AC08` |
| **CC Hook 3 (Stick->Dpad)** | `0x8040B50C` | `0x8040BA7C` | `0x8040EB80` | `0x8040B538` |
| **CC Hook 4 (Buttons)** | `0x8040BBFC` | `0x8040C16C` | `0x8040F270` | `0x8040BC3C` |
