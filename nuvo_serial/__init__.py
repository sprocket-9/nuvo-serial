from __future__ import annotations

from typing import Optional
from typeguard.importhook import install_import_hook

from nuvo_serial.grand_concerto_essentia_g import NuvoSync, NuvoAsync

install_import_hook("nuvo_serial")


def get_nuvo(port_url: str, model: str, retries: Optional[int] = None) -> NuvoSync:

    return NuvoSync(port_url, model, retries)


async def get_nuvo_async(
    port_url: str,
    model: str,
    timeout: Optional[float] = None,
    disconnect_time: Optional[float] = None,
    do_model_check: Optional[bool] = True,
    track_state: Optional[bool] = True,
    wakeup_essentia: Optional[bool] = True,
) -> NuvoAsync:

    nuvo = NuvoAsync(
        port_url=port_url,
        model=model,
        timeout=timeout,
        disconnect_time=disconnect_time,
        do_model_check=do_model_check,
        track_state=track_state,
        wakeup_essentia=wakeup_essentia
    )
    await nuvo.connect()
    return nuvo
