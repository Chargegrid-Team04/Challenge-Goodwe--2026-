// Configurações gerais do app: serviços externos, regras de bateria e limites de rota
const CONFIG = {
    // Localização inicial chumbada próxima aos postos (Aclimação / FIAP / Paulista)
    origemPadrao: { lat: -23.5700, lng: -46.6350, nome: "Minha Localização (Aclimação - SP)" },

    // URL do backend (FastAPI) que devolve a lista de carregadores reais
    apiChargers: "/api/estacoes",

    servicos: {
        osrm: "https://router.project-osrm.org",
        nominatim: "https://nominatim.openstreetmap.org",
        overpass: "https://overpass-api.de/api/interpreter"
    },

    bateria: {
        reservaSoc: 10,          // % mínimo aceitável na chegada
        margemPlanejamento: 5,   // folga extra ao calcular quanto recarregar
        tetoRecargaRapida: 90,   // % máximo planejado em carregador DC
        tetoRecargaLenta: 100    // % máximo planejado em carregador AC
    },

    rota: {
        limiteMaxKmh: 120,       // teto de velocidade de automóvel em rodovias de pista dupla (SP)
        corredorKm: 20,          // distância máxima do carregador até a rota para ser candidato
        maxCandidatos: 3,        // quantos carregadores têm a rota real calculada
        timeoutMs: 20000
    },

    mapa: { zoomInicial: 14 },

    destinosRapidos: [
        { nome: "Campinas", lat: -22.9056, lng: -47.0608 },
        { nome: "Santos", lat: -23.9608, lng: -46.3336 },
        { nome: "São José dos Campos", lat: -23.1896, lng: -45.8841 },
        { nome: "Sorocaba", lat: -23.5015, lng: -47.4526 },
        { nome: "Jundiaí", lat: -23.1864, lng: -46.8842 }
    ]
};
