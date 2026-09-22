import asyncio
from datetime import datetime, timezone

import websockets
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call

CP_ID = "GW22K-HCA-20"
URL = f"ws://127.0.0.1:8000/api/ocpp/{CP_ID}"
RECARGA_ID_TESTE = 9


class Simulador(BaseChargePoint):
    async def enviar_boot(self):
        resposta = await self.call(call.BootNotification(
            charge_point_model="Kit1",
            charge_point_vendor="GoodWe",
        ))
        print("BootNotification ->", resposta.status)

    async def enviar_start(self):
        resposta = await self.call(call.StartTransaction(
            connector_id=1,
            id_tag=str(RECARGA_ID_TESTE),
            meter_start=0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        print("StartTransaction ->", resposta.transaction_id, resposta.id_tag_info)

    async def enviar_meter_values(self):
        await self.call(call.MeterValues(
            connector_id=1,
            transaction_id=RECARGA_ID_TESTE,
            meter_value=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sampledValue": [
                    {"value": "3500", "measurand": "Energy.Active.Import.Register"},
                    {"value": "7000", "measurand": "Power.Active.Import"},
                ],
            }],
        ))
        print("MeterValues -> ok")

    async def enviar_stop(self):
        resposta = await self.call(call.StopTransaction(
            transaction_id=RECARGA_ID_TESTE,
            meter_stop=7000,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        print("StopTransaction ->", resposta.id_tag_info)


async def main():
    async with websockets.connect(URL, subprotocols=["ocpp1.6"]) as ws:
        sim = Simulador(CP_ID, ws)
        escuta = asyncio.create_task(sim.start())

        await sim.enviar_boot()
        await asyncio.sleep(0.5)
        await sim.enviar_start()
        await asyncio.sleep(0.5)
        await sim.enviar_meter_values()
        await asyncio.sleep(0.5)
        await sim.enviar_stop()

        escuta.cancel()


asyncio.run(main())