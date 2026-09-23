import asyncio
import json
import urllib.request
from datetime import datetime, timezone

import websockets
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call

CP_ID = "GW22K-HCA-20"
URL_WS = f"ws://127.0.0.1:8000/api/ocpp/{CP_ID}"
URL_API_RECARGAS = "http://127.0.0.1:8000/api/recargas"


def criar_recarga() -> int:
    """Cria uma recarga nova via API e devolve o id dela."""
    corpo = json.dumps({
        "usuario_id": 1,
        "veiculo_id": 1,
        "estacao_id": 1,
        "conector_id": 3,
        "modo": "RAPIDO",
        "quantidade_kwh": 10,
    }).encode("utf-8")

    requisicao = urllib.request.Request(
        URL_API_RECARGAS,
        data=corpo,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(requisicao) as resposta:
        dados = json.loads(resposta.read())
        return dados["id"]


class Simulador(BaseChargePoint):
    async def enviar_boot(self):
        resposta = await self.call(call.BootNotification(
            charge_point_model="Kit1",
            charge_point_vendor="GoodWe",
        ))
        print("BootNotification ->", resposta.status)

    async def enviar_start(self, recarga_id: int):
        resposta = await self.call(call.StartTransaction(
            connector_id=1,
            id_tag=str(recarga_id),
            meter_start=0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        print("StartTransaction ->", resposta.transaction_id, resposta.id_tag_info)

    async def enviar_meter_values(self, recarga_id: int):
        await self.call(call.MeterValues(
            connector_id=1,
            transaction_id=recarga_id,
            meter_value=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sampledValue": [
                    {"value": "3500", "measurand": "Energy.Active.Import.Register"},
                    {"value": "7000", "measurand": "Power.Active.Import"},
                ],
            }],
        ))
        print("MeterValues -> ok")

    async def enviar_stop(self, recarga_id: int):
        resposta = await self.call(call.StopTransaction(
            transaction_id=recarga_id,
            meter_stop=7000,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        print("StopTransaction ->", resposta.id_tag_info)


async def main():
    recarga_id = criar_recarga()
    print(f"Recarga criada -> id {recarga_id}")

    async with websockets.connect(URL_WS, subprotocols=["ocpp1.6"]) as ws:
        sim = Simulador(CP_ID, ws)
        escuta = asyncio.create_task(sim.start())

        await sim.enviar_boot()
        await asyncio.sleep(0.5)
        await sim.enviar_start(recarga_id)
        await asyncio.sleep(0.5)
        await sim.enviar_meter_values(recarga_id)
        await asyncio.sleep(0.5)
        await sim.enviar_stop(recarga_id)

        escuta.cancel()

    print(f"\nConfira em: http://127.0.0.1:8000/docs -> GET /api/recargas/{recarga_id}")


asyncio.run(main())