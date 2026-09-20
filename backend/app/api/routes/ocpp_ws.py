from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ocpp.routing import on
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call_result

router = APIRouter()


class WebSocketAdapter:
    def __init__(self, ws: WebSocket):
        self.ws = ws

    async def recv(self):
        return await self.ws.receive_text()

    async def send(self, message):
        await self.ws.send_text(message)


class ChargePoint(BaseChargePoint):
    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        return call_result.BootNotification(
            current_time=datetime.now(timezone.utc).isoformat(),
            interval=30,
            status="Accepted",
        )


@router.websocket("/ocpp/{cp_id}")
async def ocpp_endpoint(ws: WebSocket, cp_id: str):
    await ws.accept(subprotocol="ocpp1.6")
    cp = ChargePoint(cp_id, WebSocketAdapter(ws))
    try:
        await cp.start()
    except WebSocketDisconnect:
        pass