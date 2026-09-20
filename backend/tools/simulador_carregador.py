import asyncio

import websockets
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call

URL = "ws://127.0.0.1:8000/api/ocpp/CP001"


class Simulador(BaseChargePoint):
    async def enviar_boot(self):
        pedido = call.BootNotification(
            charge_point_model="Kit1",
            charge_point_vendor="GoodWe",
        )
        resposta = await self.call(pedido)
        print("Resposta da API:", resposta.status)


async def main():
    async with websockets.connect(URL, subprotocols=["ocpp1.6"]) as ws:
        sim = Simulador("CP001", ws)
        escuta = asyncio.create_task(sim.start())
        await sim.enviar_boot()
        escuta.cancel()


asyncio.run(main())