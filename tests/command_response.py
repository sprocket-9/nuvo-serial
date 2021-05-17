import re
from nuvo_serial.const import MODEL_GC, MODEL_ESSENTIA_G, RESPONSE_STRING_OK
from tests.const import ZONE, ZONE_OFF, ZONE_NUVONET_SOURCE, SOURCE, SOURCE_NUVONET

command_patterns: dict = {MODEL_GC: {}}

grand_concerto_patterns = command_patterns[MODEL_GC]

responses: dict = {MODEL_GC: {}}

grand_concerto_responses = responses[MODEL_GC]

"""
Version
"""
grand_concerto_patterns["version"] = re.compile(r"VER")
grand_concerto_responses["version"] = r'#VER"NV-I8G FWv0.91 HWv0"$'
# r"#VER\"(?P<product_number>.+)?\s+(?P<fw_version>.+)?\s+(?P<hw_version>.+)?\""

"""
Zone Status
"""
grand_concerto_patterns["zone_status"] = re.compile(r"Z(?P<zone>\d+)STATUS\?$")
grand_concerto_patterns["zone_power_off"] = re.compile(r"Z(?P<zone>\d+)OFF$$")
grand_concerto_patterns["zone_source_change"] = re.compile(
    r"Z(?P<zone>\d+)SRC(?P<source>\d+)$"
)
grand_concerto_patterns["zone_source_next"] = re.compile(r"Z(?P<zone>\d+)SRC\+$")
grand_concerto_patterns["zone_mute_on"] = re.compile(r"Z(?P<zone>\d+)MUTEON$")
grand_concerto_patterns["zone_mute_off"] = re.compile(r"Z(?P<zone>\d+)MUTEOFF$")
grand_concerto_patterns["zone_volume_set"] = re.compile(
    r"Z(?P<zone>\d+)VOL(?P<volume>\d+)$"
)
grand_concerto_patterns["zone_dnd_on"] = re.compile(r"Z(?P<zone>\d+)DNDON$")
grand_concerto_patterns["zone_dnd_off"] = re.compile(r"Z(?P<zone>\d+)DNDOFF$")

zone_status_response_baseline = "#Z1,ON,SRC4,VOL60,DND0,LOCK0"
grand_concerto_responses["zone_status"] = zone_status_response_baseline
grand_concerto_responses["zone_power_off"] = "#Z1,OFF"
grand_concerto_responses["zone_source_change"] = "#Z1,ON,SRC5,VOL60,DND0,LOCK0"
grand_concerto_responses["zone_source_next"] = "#Z1,ON,SRC5,VOL60,DND0,LOCK0"
grand_concerto_responses["zone_mute_on"] = "#Z1,ON,SRC4,VOLMUTE,DND0,LOCK0"
grand_concerto_responses["zone_mute_off"] = zone_status_response_baseline
grand_concerto_responses["zone_volume_set"] = "#Z1,ON,SRC4,VOL59,DND0,LOCK0"
grand_concerto_responses["zone_dnd_on"] = "#Z1,ON,SRC4,VOL60,DND1,LOCK0"
grand_concerto_responses["zone_dnd_off"] = zone_status_response_baseline


"""
Zone EQ
"""

grand_concerto_patterns["zone_eq_status"] = re.compile(r"ZCFG(?P<zone>\d+)EQ\?$")
grand_concerto_patterns["zone_bass_set"] = re.compile(
    r"ZCFG(?P<zone>\d+)BASS(?P<bass>-?\d+)"
)
grand_concerto_patterns["zone_treble_set"] = re.compile(
    r"ZCFG(?P<zone>\d+)TREB(?P<treble>-?\d+)"
)
grand_concerto_patterns["zone_balance_set_L"] = re.compile(
    r"ZCFG(?P<zone>\d+)BAL(?P<balance_position>L)(?P<balance>\d+)$"
)
grand_concerto_patterns["zone_balance_set_R"] = re.compile(
    r"ZCFG(?P<zone>\d+)BAL(?P<balance_position>R)(?P<balance>\d+)$"
)
grand_concerto_patterns["zone_balance_set_C"] = re.compile(
    r"ZCFG(?P<zone>\d+)BAL(?P<balance_position>C)(?P<balance>\d+)$"
)
grand_concerto_patterns["zone_loudcmp_set"] = re.compile(
    r"ZCFG(?P<zone>\d+)LOUDCMP(?P<loudcmp>\d+)$"
)

"""
The L/R swaps here are intentional to mimic the GC reversed speaker balance bug
"""
zone_eq_response_baseline = "#ZCFG1,BASS18,TREB-4,BALL9,LOUDCMP1"
grand_concerto_responses["zone_eq_status"] = zone_eq_response_baseline
grand_concerto_responses["zone_bass_set"] = "#ZCFG1,BASS-12,TREB-4,BALL9,LOUDCMP1"
grand_concerto_responses["zone_treble_set"] = "#ZCFG1,BASS18,TREB8,BALL9,LOUDCMP1"
grand_concerto_responses["zone_balance_set_L"] = "#ZCFG1,BASS18,TREB-4,BALR10,LOUDCMP1"
grand_concerto_responses["zone_balance_set_R"] = "#ZCFG1,BASS18,TREB-4,BALL2,LOUDCMP1"
grand_concerto_responses["zone_balance_set_C"] = "#ZCFG1,BASS18,TREB-4,BALC,LOUDCMP1"
grand_concerto_responses["zone_loudcmp_set"] = "#ZCFG1,BASS18,TREB-4,BALL9,LOUDCMP0"

"""
Zone Configuration
"""
grand_concerto_patterns["zone_configuration"] = re.compile(
    r"ZCFG(?P<zone>\d+)STATUS\?$"
)
grand_concerto_patterns["zone_configuration_set_source_mask"] = re.compile(
    r"ZCFG(?P<zone>\d+)SOURCES(?P<sources>\d+)$"
)
grand_concerto_patterns["zone_configuration_set_dnd_mask"] = re.compile(
    r"ZCFG(?P<zone>\d+)DND(?P<dnd>\d)$"
)
grand_concerto_patterns["zone_configuration_set_name"] = re.compile(
    r"ZCFG(?P<zone>\d+)NAME\"(?P<name>.+)\"$"
)
grand_concerto_patterns["zone_configuration_slave_to"] = re.compile(
    r"ZCFG(?P<slave_zone>\d+)SLAVETO(?P<master_zone>\d+)$"
)

zone_configuration_response_baseline = '#ZCFG1,ENABLE1,NAME"Kitchen",SLAVETO0,GROUP0,SOURCES17,XSRC0,IR0,DND7,LOCKED0,SLAVEEQ0'
grand_concerto_responses["zone_configuration"] = zone_configuration_response_baseline
grand_concerto_responses[
    "zone_configuration_set_source_mask"
] = '#ZCFG1,ENABLE1,NAME"Kitchen",SLAVETO0,GROUP0,SOURCES32,XSRC0,IR0,DND7,LOCKED0,SLAVEEQ0'
grand_concerto_responses[
    "zone_configuration_set_dnd_mask"
] = '#ZCFG1,ENABLE1,NAME"Kitchen",SLAVETO0,GROUP0,SOURCES17,XSRC0,IR0,DND1,LOCKED0,SLAVEEQ0'
grand_concerto_responses[
    "zone_configuration_set_name"
] = '#ZCFG1,ENABLE1,NAME"Office",SLAVETO0,GROUP0,SOURCES17,XSRC0,IR0,DND7,LOCKED0,SLAVEEQ0'
grand_concerto_responses[
    "zone_configuration_slave_to"
] = '#ZCFG1,ENABLE1,NAME"Kitchen",SLAVETO16,GROUP0,SOURCES17,XSRC0,IR0,DND7,LOCKED0,SLAVEEQ0'

"""
Source Configuration
"""
grand_concerto_patterns["source_configuration_status"] = re.compile(
    r"SCFG(?P<source>\d+)STATUS\?"
)
grand_concerto_patterns["source_configuration_set_long_name"] = re.compile(
    r"SCFG(?P<source>\d+)NAME\"(?P<name>.+)\"$"
)
grand_concerto_patterns["source_configuration_set_enable"] = re.compile(
    r"SCFG(?P<source>\d+)ENABLE(?P<enable>0|1)$"
)
grand_concerto_patterns["source_configuration_set_gain"] = re.compile(
    r"SCFG(?P<source>\d+)GAIN(?P<gain>\d+)$"
)
grand_concerto_patterns["source_configuration_set_nuvonet"] = re.compile(
    r"SCFG(?P<source>\d+)NUVONET(?P<nuvonet>1)$"
)
grand_concerto_patterns["source_configuration_set_short_name"] = re.compile(
    r"SCFG(?P<source>\d+)SHORTNAME\"(?P<name>.+)\"$"
)

source_configuration_response_baseline = (
    '#SCFG4,ENABLE1,NAME"Network Streamer",GAIN4,NUVONET0,SHORTNAME"NST"'
)
grand_concerto_responses[
    "source_configuration_status"
] = source_configuration_response_baseline
grand_concerto_responses[
    "source_configuration_set_long_name"
] = '#SCFG4,ENABLE1,NAME"Music Server",GAIN4,NUVONET0,SHORTNAME"NST"'
grand_concerto_responses["source_configuration_set_enable"] = "#SCFG4,ENABLE0"
grand_concerto_responses[
    "source_configuration_set_gain"
] = '#SCFG4,ENABLE1,NAME"Network Streamer",GAIN8,NUVONET0,SHORTNAME"NST"'
grand_concerto_responses[
    "source_configuration_set_nuvonet"
] = '#SCFG4,ENABLE1,NAME"Network Streamer",GAIN4,NUVONET1,SHORTNAME"NST"'
grand_concerto_responses[
    "source_configuration_set_short_name"
] = '#SCFG4,ENABLE1,NAME"Network Streamer",GAIN4,NUVONET0,SHORTNAME"ABC"'

"""
Zone Volume Configuration
"""
grand_concerto_patterns["zone_volume_configuration"] = re.compile(
    r"ZCFG(?P<zone>\d+)VOL\?$"
)
grand_concerto_patterns["zone_volume_max"] = re.compile(
    r"ZCFG(?P<zone>\d+)MAXVOL(?P<max>\d+)$"
)
grand_concerto_patterns["zone_volume_ini"] = re.compile(
    r"ZCFG(?P<zone>\d+)INIVOL(?P<ini>\d+)$"
)
grand_concerto_patterns["zone_volume_page"] = re.compile(
    r"ZCFG(?P<zone>\d+)PAGEVOL(?P<page>\d+)$"
)
grand_concerto_patterns["zone_volume_party"] = re.compile(
    r"ZCFG(?P<zone>\d+)PARTYVOL(?P<party>\d+)$"
)
grand_concerto_patterns["zone_volume_reset"] = re.compile(
    r"ZCFG(?P<zone>\d+)VOLRST(?P<reset>1)$"
)

zone_volume_configuration_response_baseline = (
    "#ZCFG1,MAXVOL0,INIVOL20,PAGEVOL40,PARTYVOL50,VOLRST0"
)
grand_concerto_responses[
    "zone_volume_configuration"
] = zone_volume_configuration_response_baseline
grand_concerto_responses[
    "zone_volume_max"
] = "#ZCFG1,MAXVOL22,INIVOL20,PAGEVOL40,PARTYVOL50,VOLRST0"
grand_concerto_responses[
    "zone_volume_ini"
] = "#ZCFG1,MAXVOL0,INIVOL33,PAGEVOL40,PARTYVOL50,VOLRST0"
grand_concerto_responses[
    "zone_volume_page"
] = "#ZCFG1,MAXVOL0,INIVOL20,PAGEVOL44,PARTYVOL50,VOLRST0"
grand_concerto_responses[
    "zone_volume_party"
] = "#ZCFG1,MAXVOL0,INIVOL20,PAGEVOL40,PARTYVOL55,VOLRST0"
grand_concerto_responses[
    "zone_volume_reset"
] = "#ZCFG1,MAXVOL0,INIVOL20,PAGEVOL40,PARTYVOL50,VOLRST1"

"""
Zone Button
"""
grand_concerto_patterns["zone_button_next_zone_off"] = re.compile(
    r"Z{}NEXT$".format(ZONE_OFF)
)
grand_concerto_patterns["zone_button_prev_zone_off"] = re.compile(
    r"Z{}PREV$".format(ZONE_OFF)
)
grand_concerto_patterns["zone_button_play_pause_zone_off"] = re.compile(
    r"Z{}PLAYPAUSE$".format(ZONE_OFF)
)

grand_concerto_patterns["zone_button_next_zone_nuvonet_source"] = re.compile(
    r"Z{}NEXT$".format(ZONE_NUVONET_SOURCE)
)
grand_concerto_patterns["zone_button_prev_zone_nuvonet_source"] = re.compile(
    r"Z{}PREV$".format(ZONE_NUVONET_SOURCE)
)
grand_concerto_patterns["zone_button_play_pause_zone_nuvonet_source"] = re.compile(
    r"Z{}PLAYPAUSE$".format(ZONE_NUVONET_SOURCE)
)

grand_concerto_patterns["zone_button_next"] = re.compile(r"Z(?P<zone>\d+)NEXT$")
grand_concerto_patterns["zone_button_prev"] = re.compile(r"Z(?P<zone>\d+)PREV$")
grand_concerto_patterns["zone_button_play_pause"] = re.compile(
    r"Z(?P<zone>\d+)PLAYPAUSE$"
)


grand_concerto_responses["zone_button_next_zone_off"] = "#Z{},OFF".format(ZONE_OFF)
grand_concerto_responses["zone_button_prev_zone_off"] = "#Z{},OFF".format(ZONE_OFF)
grand_concerto_responses["zone_button_play_pause_zone_off"] = "#Z{},OFF".format(
    ZONE_OFF
)

grand_concerto_responses["zone_button_next_zone_nuvonet_source"] = RESPONSE_STRING_OK
grand_concerto_responses["zone_button_prev_zone_nuvonet_source"] = RESPONSE_STRING_OK
grand_concerto_responses[
    "zone_button_play_pause_zone_nuvonet_source"
] = RESPONSE_STRING_OK

grand_concerto_responses["zone_button_next"] = "#Z{}S{}NEXT".format(ZONE, SOURCE)
grand_concerto_responses["zone_button_prev"] = "#Z{}S{}PREV".format(ZONE, SOURCE)
grand_concerto_responses["zone_button_play_pause"] = "#Z{}S{}PLAYPAUSE".format(
    ZONE, SOURCE
)

#
command_patterns[MODEL_ESSENTIA_G] = command_patterns[MODEL_GC]
responses[MODEL_ESSENTIA_G] = responses[MODEL_GC]
