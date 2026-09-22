from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ocpp.routing import on
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call, call_result

from app.db.session import SessionLocal
from app.models.conector import Conector
from app.models.recarga import Recarga

router = APIRouter()

# Guarda as conexoes abertas: {cp_id: instancia do ChargePoint}
CONEXOES: dict[str, "ChargePoint"] = {}

# Guarda o meter_start de cada transacao em andamento: {cp_id: {"recarga_id": int, "meter_start": int}}
TRANSACOES: dict[str, dict] = {}


class WebSocketAdapter:
    def __init__(self, ws: WebSocket):
        self.ws = ws

    async def recv(self):
        return await self.ws.receive_text()

    async def send(self, message):
        await self.ws.send_text(message)


def _obter_valor_medidor(meter_value: list, measurand_alvo: str) -> Decimal | None:
    """Procura, dentro do MeterValues do OCPP, o valor de um measurand especifico
    (ex.: 'Energy.Active.Import.Register' ou 'Power.Active.Import')."""
    for entrada in meter_value or []:
        amostras = entrada.get("sampledValue") or entrada.get("sampled_value") or []
        for amostra in amostras:
            measurand = amostra.get("measurand") or "Energy.Active.Import.Register"
            if measurand == measurand_alvo:
                try:
                    return Decimal(str(amostra.get("value")))
                except Exception:
                    return None
    return None


class ChargePoint(BaseChargePoint):
    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        return call_result.BootNotification(
            current_time=datetime.now(timezone.utc).isoformat(),
            interval=30,
            status="Accepted",
        )

    @on("Heartbeat")
    async def on_heartbeat(self, **kwargs):
        return call_result.Heartbeat(
            current_time=datetime.now(timezone.utc).isoformat(),
        )

    @on("Authorize")
    async def on_authorize(self, id_tag, **kwargs):
        return call_result.Authorize(id_tag_info={"status": "Accepted"})

    @on("StatusNotification")
    async def on_status_notification(self, connector_id, error_code, status, **kwargs):
        db = SessionLocal()
        try:
            conector = db.query(Conector).filter(Conector.codigo == self.id).first()
            if conector:
                conector.status = self._mapear_status(status)
                db.commit()
        finally:
            db.close()
        return call_result.StatusNotification()

    @staticmethod
    def _mapear_status(status_ocpp: str) -> str:
        mapa = {
            "Available": "DISPONIVEL",
            "Preparing": "DISPONIVEL",
            "Charging": "CARREGANDO",
            "Finishing": "CARREGANDO",
            "Faulted": "MANUTENCAO",
            "Unavailable": "MANUTENCAO",
        }
        return mapa.get(status_ocpp, "DISPONIVEL")

    @on("StartTransaction")
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        db = SessionLocal()
        try:
            try:
                recarga_id = int(id_tag)
            except (TypeError, ValueError):
                return call_result.StartTransaction(
                    transaction_id=0,
                    id_tag_info={"status": "Invalid"},
                )

            recarga = db.get(Recarga, recarga_id)
            if not recarga:
                return call_result.StartTransaction(
                    transaction_id=0,
                    id_tag_info={"status": "Invalid"},
                )

            recarga.status = "CARREGANDO"
            recarga.iniciada_em = datetime.now(timezone.utc)

            conector = db.get(Conector, recarga.conector_id)
            if conector:
                conector.status = "CARREGANDO"

            db.commit()

            TRANSACOES[self.id] = {"recarga_id": recarga_id, "meter_start": meter_start}

            return call_result.StartTransaction(
                transaction_id=recarga_id,
                id_tag_info={"status": "Accepted"},
            )
        finally:
            db.close()

    @on("MeterValues")
    async def on_meter_values(self, connector_id, meter_value, transaction_id=None, **kwargs):
        info = TRANSACOES.get(self.id)
        recarga_id = transaction_id or (info["recarga_id"] if info else None)
        if recarga_id is None:
            return call_result.MeterValues()

        energia_wh = _obter_valor_medidor(meter_value, "Energy.Active.Import.Register")
        potencia_w = _obter_valor_medidor(meter_value, "Power.Active.Import")

        db = SessionLocal()
        try:
            recarga = db.get(Recarga, recarga_id)
            if recarga:
                if energia_wh is not None:
                    recarga.energia_entregue_kwh = energia_wh / Decimal(1000)
                if potencia_w is not None:
                    recarga.potencia_atual_kw = potencia_w / Decimal(1000)
                db.commit()
        finally:
            db.close()

        return call_result.MeterValues()

    @on("StopTransaction")
    async def on_stop_transaction(self, transaction_id, meter_stop, timestamp, **kwargs):
        recarga_id = transaction_id
        info = TRANSACOES.pop(self.id, None)
        meter_start = info["meter_start"] if info else 0

        db = SessionLocal()
        try:
            recarga = db.get(Recarga, recarga_id)
            if recarga:
                energia_kwh = (Decimal(meter_stop) - Decimal(meter_start)) / Decimal(1000)
                if energia_kwh < 0:
                    energia_kwh = recarga.energia_entregue_kwh or Decimal("0")

                recarga.status = "CONCLUIDA"
                recarga.finalizada_em = datetime.now(timezone.utc)
                recarga.energia_entregue_kwh = energia_kwh
                recarga.valor_final = round(energia_kwh * recarga.preco_kwh + recarga.taxa_servico, 2)
                recarga.potencia_atual_kw = Decimal("0.0")
                recarga.tempo_restante_minutos = 0

                conector = db.get(Conector, recarga.conector_id)
                if conector:
                    conector.status = "DISPONIVEL"

                db.commit()
        finally:
            db.close()

        return call_result.StopTransaction(id_tag_info={"status": "Accepted"})


async def enviar_remote_start(cp_id: str, recarga_id: int) -> bool:
    """Manda a API pedir pro carregador iniciar a recarga. Retorna True se o
    carregador aceitou o pedido."""
    cp = CONEXOES.get(cp_id)
    if cp is None:
        return False
    resposta = await cp.call(call.RemoteStartTransaction(id_tag=str(recarga_id)))
    return resposta.status == "Accepted"


async def enviar_remote_stop(cp_id: str, recarga_id: int) -> bool:
    """Manda a API pedir pro carregador parar a recarga."""
    cp = CONEXOES.get(cp_id)
    if cp is None:
        return False
    resposta = await cp.call(call.RemoteStopTransaction(transaction_id=recarga_id))
    return resposta.status == "Accepted"


@router.websocket("/ocpp/{cp_id}")
async def ocpp_endpoint(ws: WebSocket, cp_id: str):
    await ws.accept(subprotocol="ocpp1.6")
    cp = ChargePoint(cp_id, WebSocketAdapter(ws))
    CONEXOES[cp_id] = cp
    try:
        await cp.start()
    except WebSocketDisconnect:
        pass
    finally:
        CONEXOES.pop(cp_id, None)
        TRANSACOES.pop(cp_id, None)