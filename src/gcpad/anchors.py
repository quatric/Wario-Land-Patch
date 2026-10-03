"""Find the Wario Land addresses the GameCube-pad patch needs in any revision."""
import struct

READ_FUNCS = {
    'RWLE01': 0x8040B5F8,
    'RWLP01': 0x8040BB68,
    'RWLJ01': 0x8040EC6C,
    'RWLK01': 0x8040B624,
}

SAMPLE_SITES = {
    'RWLE01': 0x8040B6FC,
    'RWLP01': 0x8040BC6C,
    'RWLJ01': 0x8040ED70,
    'RWLK01': 0x8040B73C,
}

WPADPROBE_FUNCS = {
    'RWLE01': 0x803B0EF0,
    'RWLP01': 0x803B1460,
    'RWLJ01': 0x803B4564,
    'RWLK01': 0x803AE9F0,
}

SIGETTYPE_FUNCS = {
    'RWLE01': 0x803A57B8,
    'RWLP01': 0x803A5D28,
    'RWLJ01': 0x803A8E2C,
    'RWLK01': 0x803A53FC,
}

SITYPES_ADDRS = {
    'RWLE01': 0x804DE888,
    'RWLP01': 0x804DFB68,
    'RWLJ01': 0x804E2D88,
    'RWLK01': 0x804E12E8,
}

SIBUSY_ADDRS = {
    'RWLE01': 0x8061FACC,
    'RWLP01': 0x80620E4C,
    'RWLJ01': 0x8061A2EC,
    'RWLK01': 0x8060B8C4,
}

WPADTBL_ADDRS = {
    'RWLE01': 0x804E0634,
    'RWLP01': 0x804E1914,
    'RWLJ01': 0x804E4B34,
    'RWLK01': 0x804E278C,
}

OSDISABLE_FUNCS = {
    'RWLE01': 0x8041B328,
    'RWLP01': 0x8041B898,
    'RWLJ01': 0x8041E99C,
    'RWLK01': 0x804189F4,
}

OSRESTORE_FUNCS = {
    'RWLE01': 0x8041B350,
    'RWLP01': 0x8041B8C0,
    'RWLJ01': 0x8041E9C4,
    'RWLK01': 0x80418A1C,
}

STATE_ADDR = 0x800041C0


def resolve(region, dol):
    # Verify displaced instructions
    w_read = struct.unpack('>I', dol.read(READ_FUNCS[region], 4))[0]
    assert w_read == 0x9421FF40, f'{region}: unexpected Read prologue: 0x{w_read:08X}'

    w_sample = struct.unpack('>I', dol.read(SAMPLE_SITES[region], 4))[0]
    assert w_sample == 0x881F010F, f'{region}: unexpected sample check: 0x{w_sample:08X}'

    w_probe = struct.unpack('>I', dol.read(WPADPROBE_FUNCS[region], 4))[0]
    assert w_probe == 0x9421FFF0, f'{region}: unexpected WPADProbe prologue: 0x{w_probe:08X}'

    return {
        'Read': READ_FUNCS[region],
        'sample_site': SAMPLE_SITES[region],
        'WPADProbe': WPADPROBE_FUNCS[region],
        'SIGetType': SIGETTYPE_FUNCS[region],
        'SiTypes': SITYPES_ADDRS[region],
        'SiBusy': SIBUSY_ADDRS[region],
        'SiShadow': SITYPES_ADDRS[region] - 0x14,
        'WpadTbl': WPADTBL_ADDRS[region],
        'OSDisableInterrupts': OSDISABLE_FUNCS[region],
        'OSRestoreInterrupts': OSRESTORE_FUNCS[region],
        'STATE': STATE_ADDR,
    }
