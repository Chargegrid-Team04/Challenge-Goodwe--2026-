// Lógica de autonomia, consumo e tempo de recarga do veículo elétrico
const BatteryCalc = {
    // Perfis de exemplo. Ajuste capacidade/consumo conforme os veículos que o app for atender.
    PERFIS: {
        compacto: {
            nome: "Compacto urbano",
            capacidadeKwh: 40,
            consumoKwhKm: 0.14,
            dcMaxKw: 70,
            acMaxKw: 7,
            conectores: ["CCS2", "Tipo 2"]
        },
        sedan: {
            nome: "Sedã / SUV médio",
            capacidadeKwh: 60,
            consumoKwhKm: 0.18,
            dcMaxKw: 100,
            acMaxKw: 11,
            conectores: ["CCS2", "Tipo 2"]
        },
        suv: {
            nome: "SUV grande",
            capacidadeKwh: 80,
            consumoKwhKm: 0.22,
            dcMaxKw: 150,
            acMaxKw: 11,
            conectores: ["CCS2", "Tipo 2"]
        },
        chademo: {
            nome: "Hatch com CHAdeMO",
            capacidadeKwh: 40,
            consumoKwhKm: 0.16,
            dcMaxKw: 50,
            acMaxKw: 6.6,
            conectores: ["CHAdeMO", "Tipo 2"]
        }
    },

    AR_CONDICIONADO_FATOR: 1.07,

    perfilId: "sedan",
    perfil: null,
    arCondicionado: true,

    definirPerfil(id) {
        this.perfilId = this.PERFIS[id] ? id : "sedan";
        this.perfil = this.PERFIS[this.perfilId];
    },

    // O consumo por km muda com a velocidade: cidade é eficiente (frenagem regenerativa),
    // rodovia rápida gasta bem mais. Curva aproximada, calibrar com dados reais do veículo.
    fatorVelocidade(kmh) {
        if (kmh < 25) return 1.05;
        if (kmh <= 60) return 0.92;
        if (kmh <= 80) return 1.0;
        if (kmh <= 100) return 1.15;
        return 1.32;
    },

    _fatorClima() {
        return this.arCondicionado ? this.AR_CONDICIONADO_FATOR : 1;
    },

    // segmentos: [{ d: km, v: km/h }] vindos da rota
    consumoKwh(segmentos) {
        const base = this.perfil.consumoKwhKm * this._fatorClima();
        return segmentos.reduce((soma, s) => soma + s.d * base * this.fatorVelocidade(s.v), 0);
    },

    // Versão simples, só com distância e velocidade média
    calcularConsumo(distanciaKm, velocidadeMediaKmh = 70) {
        const kwhGasto = distanciaKm * this.perfil.consumoKwhKm * this._fatorClima() * this.fatorVelocidade(velocidadeMediaKmh);
        return { kwhGasto, socPercentGasto: this.kwhParaSoc(kwhGasto) };
    },

    kwhParaSoc(kwh) {
        return (kwh / this.perfil.capacidadeKwh) * 100;
    },

    validarAutonomia(kwhGasto, socAtual) {
        const socPercentGasto = this.kwhParaSoc(kwhGasto);
        const socRestante = socAtual - socPercentGasto;
        return {
            kwhGasto,
            socPercentGasto,
            socRestante,
            suportaViagem: socRestante >= CONFIG.bateria.reservaSoc
        };
    },

    // Distância que ainda dá para rodar sem passar da reserva
    autonomiaKm(socAtual, kwhPorKm) {
        const socUtil = Math.max(0, socAtual - CONFIG.bateria.reservaSoc);
        return ((socUtil / 100) * this.perfil.capacidadeKwh) / kwhPorKm;
    },

    // Define como o veículo carregaria neste ponto: corrente (DC/AC) e potência que ele aceita.
    // Retorna null se os plugs forem incompatíveis.
    modoDeCarga(est) {
        const p = this.perfil;
        const estAC = /^AC/i.test(est.tipo);
        const plugDC = est.conectores.some(c => c !== "Tipo 2" && p.conectores.includes(c));

        if (plugDC && !estAC) {
            return { corrente: "DC", potenciaKw: Math.min(est.potenciaKw, p.dcMaxKw) };
        }
        if (est.conectores.includes("Tipo 2") && p.conectores.includes("Tipo 2")) {
            const potenciaEst = estAC ? est.potenciaKw : 22;
            return { corrente: "AC", potenciaKw: Math.min(potenciaEst, p.acMaxKw) };
        }
        return null;
    },

    // Tempo (min) para ir de socIni a socFim. Em DC a potência cai bastante depois de 80%.
    tempoRecargaMin(socIni, socFim, potenciaKw, corrente = "DC") {
        if (socFim <= socIni) return 0;
        const cap = this.perfil.capacidadeKwh;
        const potencia = potenciaKw * 0.92; // perdas de conversão e gestão térmica
        const ate80 = Math.max(0, Math.min(socFim, 80) - socIni);
        const acima80 = Math.max(0, socFim - Math.max(socIni, 80));
        const fatorAcima = corrente === "DC" ? 0.35 : 0.8;

        const horas = (ate80 / 100 * cap) / potencia +
            (acima80 / 100 * cap) / (potencia * fatorAcima);
        return Math.ceil(horas * 60);
    }
};

BatteryCalc.definirPerfil("sedan");
