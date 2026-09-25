// Carregadores: carga dos dados, horário de funcionamento, lotação prevista e compatibilidade
const ChargerService = {
    lista: [],

    async carregar() {
        if (CONFIG.apiChargers) {
            try {
                const dados = await Http.json(CONFIG.apiChargers, {}, 8000);
                this.lista = dados.map(e => this._normalizar(e));
                return this.lista;
            } catch (err) {
                console.warn("API de carregadores indisponível, usando a base local.", err);
            }
        }
        this.lista = mockChargers.map(e => this._normalizar(e));
        return this.lista;
    },

    // Normalização completa dos dados da API (/api/estacoes)
    _normalizar(e) {
        const conectoresLista = Array.isArray(e.conectores) ? e.conectores : [];
        const temConectores = conectoresLista.length > 0;

        // Potência máxima disponível na estação
        const potMax = temConectores
            ? Math.max(...conectoresLista.map(c => parseFloat(c.potencia_kw) || 0))
            : (parseFloat(e.potenciaKw) || 22);

        // Vagas e status em tempo real a partir dos conectores da API
        const vagasTotal = temConectores ? conectoresLista.length : (e.vagasTotal || 2);
        const vagasLivres = temConectores
            ? conectoresLista.filter(c => c.status === "DISPONIVEL").length
            : (e.vagasLivre != null ? e.vagasLivre : 1);

        const statusEstacao = vagasLivres > 0 ? "disponivel" : (e.status || "ocupado");

        // Conectores legíveis
        const nomesConectores = temConectores
            ? conectoresLista.map(c => `${c.tipo || 'Type 2'} (${parseInt(c.potencia_kw || 22, 10)} kW)`)
            : (Array.isArray(e.conectores) ? e.conectores : ["Type 2"]);

        return {
            id: String(e.id),
            nome: e.nome,
            endereco: e.endereco || "Endereço não informado",
            lat: parseFloat(e.latitude ?? e.lat),
            lng: parseFloat(e.longitude ?? e.lng),
            potenciaKw: potMax,
            tipo: potMax >= 50 ? "DC Fast" : "AC GoodWe",
            conectores: nomesConectores,
            vagasTotal: vagasTotal,
            vagasLivre: vagasLivres,
            precoKwh: parseFloat(e.preco_base_kwh ?? e.precoKwh ?? 1.90),
            status: statusEstacao,
            horario: e.horario || null,
            sessaoMediaMin: e.sessaoMediaMin || (potMax >= 50 ? 30 : 60)
        };
    },

    // Tempo médio que cada carro fica conectado
    _sessaoPadrao(e) {
        if (/^AC/i.test(e.tipo)) return 180;
        return e.potenciaKw >= 100 ? 25 : 40;
    },

    aberto(est, data) {
        if (!est.horario) return true;
        const h = data.getHours() + data.getMinutes() / 60;
        const [abre, fecha] = est.horario;
        return abre <= fecha ? (h >= abre && h < fecha) : (h >= abre || h < fecha);
    },

    // Horários de maior procura: almoço, fim do expediente e fins de semana
    _fatorLotacao(data) {
        const dia = data.getDay();
        const h = data.getHours();
        const diaUtil = dia >= 1 && dia <= 5;
        if (diaUtil && ((h >= 12 && h < 14) || (h >= 18 && h < 21))) return 1.35;
        if (!diaUtil && h >= 10 && h < 19) return 1.25;
        if (h < 6 || h >= 22) return 0.6;
        return 1;
    },

    compativel(est) {
        return BatteryCalc.modoDeCarga(est) !== null;
    },

    // Estado esperado do carregador em "quando".
    // Para horários próximos usa as vagas atuais; para mais longe, ajusta pela demanda típica do horário.
    previsao(est, quando = new Date()) {
        if (est.status === "manutencao") {
            return { estado: "manutencao", vagasLivres: 0, esperaMin: Infinity };
        }
        if (!this.aberto(est, quando)) {
            return { estado: "fechado", vagasLivres: 0, esperaMin: Infinity };
        }

        const agora = new Date();
        const minutosAte = (quando - agora) / 60000;
        let ocupacao = 1 - est.vagasLivre / est.vagasTotal;

        if (minutosAte > 20) {
            ocupacao = Math.min(1, ocupacao * (this._fatorLotacao(quando) / this._fatorLotacao(agora)));
        }

        const vagasLivres = Math.round(est.vagasTotal * (1 - ocupacao));
        // Sem vaga: espera média até algum carro sair
        const esperaMin = vagasLivres > 0 ? 0 : Math.round(est.sessaoMediaMin / est.vagasTotal);

        return {
            estado: vagasLivres > 0 ? "disponivel" : "ocupado",
            vagasLivres,
            esperaMin
        };
    }
};
