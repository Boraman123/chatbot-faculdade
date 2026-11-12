
import os
import re
import threading
import unicodedata
from collections import defaultdict

import requests
import ollama
from flask import Flask, request, jsonify


# ==========================================================
# CONFIGURAÇÕES DO PROJETO
# ==========================================================

app = Flask(__name__)

PHONE_NUMBER_ID = "1279935878543572"

# COLOQUE AQUI SEU TOKEN ATUAL DA META
ACCESS_TOKEN = "EAAekHdZCE5acBSYcFwoPkIeSxQqiNlGF7ZAwLNj1b8ZCIocr8X0M04gZBuDT6hpXXm1dZAOWbJ0NJkFelCZAjm1G6l8Sx92ubfOxV05IExlXMBrzOmdSXQAOMQTGeofWDzK5ZBuOo0yhUUZBRaGmBtSDzrmYyNNbo2OgENwOhHWgEoEOdNfeRQcM1jKwlGW4mMy7UwZDZD"

TOKEN_VERIFICACAO = "meu_token_faculdade"

URL_WHATSAPP = (
    f"https://graph.facebook.com/v26.0/"
    f"{PHONE_NUMBER_ID}/messages"
)

MODELO_OLLAMA = "llama3.2:latest"

ARQUIVO_CONHECIMENTO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "conhecimento.txt"
)

MENSAGEM_INICIAL = (
    "Olá! 👋\n"
    "Sou o assistente virtual da Faculdade Anhanguera. "
    "Como posso ajudar?"
)

MENSAGEM_FINAL = (
    "Até mais! 👏 Foi um prazer ajudar! 😊"
)

FALLBACK = (
    "Não encontrei essa informação na base da faculdade."
)

historico = defaultdict(list)
mensagens_processadas = set()
lock_mensagens = threading.Lock()


# ==========================================================
# CARREGAMENTO DO CONHECIMENTO
# ==========================================================

def carregar_conhecimento():

    try:
        with open(
            ARQUIVO_CONHECIMENTO,
            "r",
            encoding="utf-8"
        ) as arquivo:

            conteudo = arquivo.read().strip()

            if not conteudo:
                print("AVISO: conhecimento.txt está vazio.")

            return conteudo

    except FileNotFoundError:
        print("ERRO: conhecimento.txt não foi encontrado.")
        return ""

    except Exception as erro:
        print(f"Erro ao carregar conhecimento.txt: {erro}")
        return ""


CONHECIMENTO = carregar_conhecimento()


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================

def normalizar(texto):

    texto = str(texto).lower().strip()

    texto = unicodedata.normalize("NFD", texto)

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def contem_algum(texto, palavras):

    return any(
        palavra in texto
        for palavra in palavras
    )


def eh_pergunta_de_horario_aulas(texto):

    indicadores = [
        "horario das aulas",
        "horarios das aulas",
        "horario de aula",
        "horarios de aula",
        "que horas tem aula",
        "que horas comeca a aula",
        "quando tem aula",
        "periodo da manha",
        "periodo da noite",
        "aula de manha",
        "aula a noite",
        "aulas de manha",
        "aulas a noite",
        "horario noturno",
        "horario matutino",
        "aula noturna",
        "aula matutina"
    ]

    return contem_algum(texto, indicadores)


# ==========================================================
# RESPOSTAS RÁPIDAS
# ==========================================================

def responder_pergunta_frequente(pergunta):

    p = normalizar(pergunta)

    # ------------------------------------------------------
    # SAUDAÇÕES
    # ------------------------------------------------------

    saudacoes = [
        "oi",
        "ola",
        "bom dia",
        "boa tarde",
        "boa noite",
        "e ai",
        "tudo bem",
        "ola tudo bem",
        "oi tudo bem"
    ]

    if p in saudacoes:
        return MENSAGEM_INICIAL

    # ------------------------------------------------------
    # AGRADECIMENTOS
    # ------------------------------------------------------

    agradecimentos = [
        "obrigado",
        "obrigada",
        "muito obrigado",
        "muito obrigada",
        "valeu",
        "agradeco",
        "agradecido",
        "agradecida"
    ]

    if p in agradecimentos:
        return (
            "Por nada! 😊 Fico muito feliz em ajudar!\n\n"
            "Se surgir outra dúvida sobre a Faculdade Anhanguera, "
            "pode me chamar. Estou à disposição! 💙"
        )

    # ------------------------------------------------------
    # DESPEDIDAS
    # ------------------------------------------------------

    # Expressões curtas reconhecidas quando enviadas sozinhas.
    despedidas_exatas = [
        "tchau",
        "tchauzinho",
        "ate",
        "ate mais",
        "ate logo",
        "ate amanha",
        "ate a proxima",
        "ate proxima",
        "ate breve",
        "ate depois",
        "ate qualquer dia",
        "adeus",
        "falou",
        "flw",
        "fui",
        "sair"
    ]

    # Expressões que também podem aparecer dentro de uma frase.
    despedidas_em_frases = [
        "vou embora",
        "tenho que ir",
        "preciso ir",
        "estou indo",
        "to indo",
        "vou nessa",
        "vou indo",
        "vou sair",
        "encerrar conversa",
        "encerrar o atendimento",
        "finalizar conversa",
        "preciso sair",
        "estou de saida",
        "tenho que sair",
        "vou ter que ir"
    ]

    if (
        p in despedidas_exatas
        or any(
            re.search(rf"\b{re.escape(frase)}\b", p)
            for frase in despedidas_em_frases
        )
    ):
        return MENSAGEM_FINAL

    # ------------------------------------------------------
    # ENDEREÇO FÍSICO DA FACULDADE
    # ------------------------------------------------------

    perguntas_endereco = [
        "endereco da faculdade",
        "endereco da anhanguera",
        "qual o endereco",
        "qual endereco",
        "onde fica a faculdade",
        "onde fica a anhanguera",
        "localizacao da faculdade",
        "localizacao da unidade",
        "como chegar na faculdade",
        "como chegar na anhanguera",
        "qual o local da faculdade",
        "em que endereco fica"
    ]

    if contem_algum(p, perguntas_endereco):
        return FALLBACK

    # ------------------------------------------------------
    # CONTATOS
    # ------------------------------------------------------

    palavras_contato = [
        "telefone",
        "telefone da faculdade",
        "numero da faculdade",
        "numero de telefone",
        "contato da faculdade",
        "contatos da faculdade",
        "whatsapp da faculdade",
        "numero do whatsapp",
        "qual o whatsapp",
        "qual o telefone",
        "como entro em contato"
    ]

    if contem_algum(p, palavras_contato):
        return (
            "Claro! 😊 Aqui estão os canais de contato "
            "da Faculdade Anhanguera:\n\n"
            "📞 *Telefone:*\n"
            "3003-4030\n\n"
            "💬 *WhatsApp:*\n"
            "(11) 91348-1040\n\n"
            "🌐 *Portal do Aluno:*\n"
            "https://alunodigital.anhanguera.com/\n\n"
            "Por esses canais, você pode buscar atendimento "
            "e informações da faculdade."
        )

    # ------------------------------------------------------
    # CURSOS OFERECIDOS
    # ------------------------------------------------------

    perguntas_cursos = [
        "quais cursos",
        "quais sao os cursos",
        "cursos oferecidos",
        "cursos disponiveis",
        "lista de cursos",
        "cursos da faculdade",
        "cursos que a faculdade oferece",
        "o que posso estudar",
        "quais graduacoes"
    ]

    if contem_algum(p, perguntas_cursos):
        return (
            "Claro! 😊 A Faculdade Anhanguera oferece "
            "os seguintes cursos:\n\n"
            "🎓 *Cursos disponíveis:*\n\n"
            "1. Ciência da Computação\n"
            "2. Administração de Empresas\n"
            "3. Engenharia de Software\n"
            "4. Direito\n"
            "5. Psicologia\n"
            "6. Biologia\n"
            "7. Enfermagem\n"
            "8. Geografia\n"
            "9. Ciências Sociais\n\n"
            "Se quiser, posso apresentar a duração e os valores "
            "de qualquer um desses cursos!"
        )

    # ------------------------------------------------------
    # INFORMAÇÕES DOS CURSOS
    # ------------------------------------------------------

    cursos = {
        "ciencia da computacao": {
            "nome": "Ciência da Computação",
            "duracao": "4 anos (8 semestres)",
            "presencial": "R$ 850,00",
            "ead": "R$ 390,00"
        },
        "administracao de empresas": {
            "nome": "Administração de Empresas",
            "duracao": "4 anos (8 semestres)",
            "presencial": "R$ 650,00",
            "ead": "R$ 290,00"
        },
        "engenharia de software": {
            "nome": "Engenharia de Software",
            "duracao": "4 anos (8 semestres)",
            "presencial": "R$ 920,00"
        },
        "direito": {
            "nome": "Direito",
            "duracao": "5 anos (10 semestres)",
            "presencial": "R$ 1.100,00"
        },
        "psicologia": {
            "nome": "Psicologia",
            "duracao": "6 anos (12 semestres)",
            "presencial": "R$ 1.600,00",
            "ead": "R$ 999,90"
        },
        "biologia": {
            "nome": "Biologia",
            "duracao": "4 anos (8 semestres)",
            "presencial": "R$ 1.000,00",
            "ead": "R$ 500,00"
        },
        "enfermagem": {
            "nome": "Enfermagem",
            "duracao": "5 anos (10 semestres)",
            "presencial": "R$ 1.520,00"
        },
        "geografia": {
            "nome": "Geografia",
            "duracao": "4 anos (8 semestres)",
            "ead": "R$ 300,00"
        },
        "ciencias sociais": {
            "nome": "Ciências Sociais",
            "duracao": "4 anos (8 semestres)",
            "presencial": "R$ 600,00",
            "ead": "R$ 250,00"
        }
    }

    pergunta_ead = contem_algum(
        p,
        [
            "ead",
            "modalidade ead",
            "ensino a distancia",
            "online",
            "a distancia"
        ]
    )

    pergunta_presencial = "presencial" in p

    for chave, dados in cursos.items():

        if chave in p:

            nome = dados["nome"]
            duracao = dados["duracao"]

            # Pergunta específica sobre EAD.
            if pergunta_ead and not pergunta_presencial:

                valor = dados.get("ead")

                if not valor:
                    return FALLBACK

                return (
                    f"🎓 *{nome}*\n\n"
                    f"📚 *Duração:* {duracao}\n\n"
                    f"💻 *Modalidade EAD:* {valor}\n\n"
                    "Espero ter ajudado! 😊"
                )

            # Pergunta específica sobre presencial.
            if pergunta_presencial and not pergunta_ead:

                valor = dados.get("presencial")

                if not valor:
                    return FALLBACK

                return (
                    f"🎓 *{nome}*\n\n"
                    f"📚 *Duração:* {duracao}\n\n"
                    f"🏫 *Modalidade presencial:* {valor}\n\n"
                    "Espero ter ajudado! 😊"
                )

            # Pergunta geral sobre o curso.
            # Exibe somente informações cadastradas.
            resposta = (
                f"🎓 *{nome}*\n\n"
                f"📚 *Duração:* {duracao}\n\n"
            )

            if dados.get("presencial"):
                resposta += (
                    f"🏫 *Modalidade presencial:* "
                    f"{dados['presencial']}\n"
                )

            if dados.get("ead"):
                resposta += (
                    f"💻 *Modalidade EAD:* "
                    f"{dados['ead']}\n"
                )

            resposta += (
                "\nEspero ter ajudado! 😊 "
                "Se quiser saber sobre outro curso, "
                "é só perguntar."
            )

            return resposta

    # ------------------------------------------------------
    # HORÁRIOS DAS AULAS
    # ------------------------------------------------------

    if eh_pergunta_de_horario_aulas(p):

        pergunta_sobre_noite = contem_algum(
            p,
            [
                "noite",
                "noturno",
                "a noite",
                "noturna"
            ]
        )

        pergunta_sobre_manha = contem_algum(
            p,
            [
                "manha",
                "matutino",
                "de manha",
                "matutina"
            ]
        )

        # Pergunta somente sobre a noite.
        if pergunta_sobre_noite and not pergunta_sobre_manha:

            return (
                "🌙 *Horário das aulas - Período da noite*\n\n"
                "As aulas do período noturno acontecem "
                "de segunda a sexta-feira.\n\n"
                "🕖 *Horário:* das *19h às 21h50*.\n\n"
                "Espero ter esclarecido sua dúvida! 😊"
            )

        # Pergunta somente sobre a manhã.
        if pergunta_sobre_manha and not pergunta_sobre_noite:

            return (
                "☀️ *Horário das aulas - Período da manhã*\n\n"
                "As aulas do período da manhã acontecem "
                "de segunda a sexta-feira.\n\n"
                "🕢 *Horário:* das *07h30 às 11h10*.\n\n"
                "Espero ter esclarecido sua dúvida! 😊"
            )

        # Pergunta geral ou sobre os dois períodos.
        return (
            "📚 *Horários das aulas*\n\n"
            "A faculdade possui dois períodos de aula:\n\n"
            "☀️ *Período da manhã:*\n"
            "Das *07h30 às 11h10*.\n\n"
            "🌙 *Período da noite:*\n"
            "Das *19h às 21h50*.\n\n"
            "📅 As aulas acontecem de segunda a sexta-feira.\n\n"
            "Se precisar de mais alguma informação, "
            "estou à disposição! 😊"
        )

    # ------------------------------------------------------
    # SECRETARIA
    # ------------------------------------------------------

    palavras_secretaria = [
        "secretaria",
        "horario da secretaria",
        "horarios da secretaria",
        "atendimento da secretaria",
        "secretaria funciona",
        "secretaria abre",
        "secretaria fecha"
    ]

    if contem_algum(p, palavras_secretaria):
        return (
            "🏢 *Horário de atendimento da secretaria*\n\n"
            "A secretaria funciona nos seguintes horários:\n\n"
            "📅 *De segunda a sexta-feira:*\n"
            "Das *08h às 20h30*.\n\n"
            "📅 *Aos sábados:*\n"
            "Das *08h às 12h*.\n\n"
            "A secretaria pode orientar você sobre assuntos "
            "acadêmicos e administrativos.\n\n"
            "Espero ter ajudado! 😊"
        )

    # ------------------------------------------------------
    # BIBLIOTECA
    # ------------------------------------------------------

    if "biblioteca" in p:

        return (
            "📚 *Horário da biblioteca*\n\n"
            "A biblioteca funciona de segunda a sexta-feira, "
            "das *07h às 22h*.\n\n"
            "Bons estudos! 😊"
        )

    # ------------------------------------------------------
    # PORTAL DO ALUNO
    # ------------------------------------------------------

    palavras_portal = [
        "portal do aluno",
        "acessar o portal",
        "site do aluno",
        "portal anhanguera",
        "consultar minhas notas",
        "consultar minhas faltas",
        "ver minhas notas",
        "ver minhas faltas",
        "consultar boletos"
    ]

    if contem_algum(p, palavras_portal):

        return (
            "🌐 *Portal do Aluno*\n\n"
            "Você pode acessar o portal pelo endereço:\n\n"
            "https://alunodigital.anhanguera.com/\n\n"
            "📌 Pelo portal, é possível consultar:\n"
            "• Notas;\n"
            "• Faltas;\n"
            "• Atividades;\n"
            "• Informações financeiras;\n"
            "• Boletos;\n"
            "• Informações de matrícula.\n\n"
            "Espero ter ajudado! 😊"
        )

    # ------------------------------------------------------
    # FREQUÊNCIA
    # ------------------------------------------------------

    if contem_algum(
        p,
        [
            "frequencia minima",
            "porcentagem de frequencia",
            "quantos por cento de presenca",
            "quantas faltas posso ter",
            "limite de faltas",
            "presenca minima"
        ]
    ):

        return (
            "📌 *Frequência mínima*\n\n"
            "A faculdade exige uma frequência mínima de "
            "*75%* para aprovação.\n\n"
            "É importante acompanhar suas faltas pelo "
            "Portal do Aluno para não ultrapassar o limite.\n\n"
            "Qualquer dúvida, estou à disposição! 😊"
        )

    # ------------------------------------------------------
    # NOTAS E APROVAÇÃO
    # ------------------------------------------------------

    if contem_algum(
        p,
        [
            "nota minima",
            "media para passar",
            "nota para passar",
            "criterios de aprovacao",
            "como funciona a aprovacao",
            "quando reprova",
            "nota de aprovacao"
        ]
    ):

        return (
            "📝 *Critérios de aprovação*\n\n"
            "Confira como funcionam as notas:\n\n"
            "✅ *Nota igual ou superior a 7,0:*\n"
            "Aprovação direta.\n\n"
            "📋 *Nota entre 4,0 e 6,9:*\n"
            "O aluno realiza avaliação final.\n\n"
            "❌ *Nota abaixo de 4,0:*\n"
            "Reprovação direta.\n\n"
            "Espero ter ajudado! 😊"
        )

    # ------------------------------------------------------
    # MENSALIDADES E PAGAMENTOS
    # ------------------------------------------------------

    if contem_algum(
        p,
        [
            "mensalidade",
            "vencimento",
            "dia de pagamento",
            "quando vence",
            "desconto na mensalidade",
            "juros da mensalidade",
            "multa por atraso"
        ]
    ):

        return (
            "💰 *Informações sobre mensalidades*\n\n"
            "📅 *Vencimento:* todo dia 5.\n\n"
            "🎁 *Desconto por pontualidade:*\n"
            "10% para pagamentos realizados até o dia 1.\n\n"
            "⚠️ *Em caso de atraso:*\n"
            "• Multa de 2%;\n"
            "• Juros de 0,033% ao dia.\n\n"
            "Essas são as condições registradas na base "
            "de conhecimento."
        )

    # ------------------------------------------------------
    # TRANCAMENTO E CANCELAMENTO
    # ------------------------------------------------------

    if contem_algum(
        p,
        [
            "trancar matricula",
            "trancamento",
            "cancelar matricula",
            "cancelamento do curso",
            "desistir do curso"
        ]
    ):

        return (
            "📋 *Trancamento ou cancelamento*\n\n"
            "As solicitações devem ser realizadas diretamente "
            "com a secretaria.\n\n"
            "📅 O prazo informado na base para solicitar "
            "o trancamento é até a quarta semana.\n\n"
            "Recomendo entrar em contato com a secretaria "
            "para receber as orientações necessárias. 😊"
        )

    # ------------------------------------------------------
    # ESTÁGIO, DOCUMENTOS E TRANSFERÊNCIA
    # ------------------------------------------------------

    if contem_algum(
        p,
        [
            "estagio",
            "documentos",
            "historico escolar",
            "declaracao",
            "transferencia",
            "documentacao"
        ]
    ):

        return (
            "📄 *Informações acadêmicas*\n\n"
            "Para orientações sobre estágio, documentos, "
            "histórico escolar ou transferência, recomendo "
            "entrar em contato diretamente com a secretaria "
            "ou pelos canais oficiais da faculdade.\n\n"
            "Assim você poderá receber as informações "
            "corretas para sua solicitação. 😊"
        )

    # Nenhuma resposta rápida encontrada.
    return None


# ==========================================================
# BUSCA DE CONTEXTO NO CONHECIMENTO.TXT
# ==========================================================

def buscar_contexto(pergunta):

    if not CONHECIMENTO:
        return ""

    pergunta_normalizada = normalizar(pergunta)

    palavras_pergunta = set(
        pergunta_normalizada.split()
    )

    secoes = re.split(
        r"(?m)(?=^#{1,3}\s)",
        CONHECIMENTO
    )

    resultados = []

    for secao in secoes:

        texto = normalizar(secao)

        palavras_secao = set(texto.split())

        pontuacao = len(
            palavras_pergunta.intersection(palavras_secao)
        )

        if pontuacao > 0:
            resultados.append(
                (pontuacao, secao.strip())
            )

    resultados.sort(
        key=lambda item: item[0],
        reverse=True
    )

    melhores = [
        secao
        for pontuacao, secao in resultados[:5]
    ]

    return "\n\n".join(melhores)


# ==========================================================
# RESPOSTAS MAIS ELABORADAS COM O OLLAMA
# ==========================================================

def responder_com_ollama(pergunta, numero):

    contexto = buscar_contexto(pergunta)

    if not contexto:
        return FALLBACK

    instrucoes = f"""
Você é o assistente virtual da Faculdade Anhanguera.

Seu objetivo é ajudar os alunos com informações da faculdade.

REGRAS OBRIGATÓRIAS:

1. Utilize somente as informações presentes no contexto.
2. Nunca invente informações.
3. Não suponha valores, horários, regras ou procedimentos.
4. Se a informação solicitada não estiver no contexto,
   responda exatamente:
{FALLBACK}
5. Responda em português do Brasil.
6. Seja simpático, educado, acolhedor e natural.
7. Evite respostas secas, curtas demais ou robóticas.
8. Organize respostas maiores com títulos e tópicos.
9. Use emojis moderadamente.
10. Para negrito no WhatsApp, utilize um único asterisco
    de cada lado.
11. Não utilize dois asteriscos para negrito.
12. Não diga que é uma inteligência artificial, modelo ou Ollama.
13. Não invente informações para completar respostas.
14. Quando informar horários, apresente o intervalo completo.
15. Se a pergunta for sobre um assunto específico,
    responda somente sobre esse assunto.
16. Não confunda horário das aulas com horário da secretaria.
17. Não apresente informações de um curso como se fossem de outro.
18. Não confunda o endereço do Portal do Aluno com o endereço
    físico da faculdade.
19. Não invente endereço ou localização da unidade.
20. Apresente somente modalidades e valores que estejam
    expressamente cadastrados no contexto.

CONTEXTO DISPONÍVEL:

{contexto}
"""

    mensagens = [
        {
            "role": "system",
            "content": instrucoes
        }
    ]

    mensagens.extend(
        historico[numero][-6:]
    )

    mensagens.append({
        "role": "user",
        "content": pergunta
    })

    try:

        resultado = ollama.chat(
            model=MODELO_OLLAMA,
            messages=mensagens,
            options={
                "temperature": 0.2,
                "num_predict": 300,
                "num_ctx": 2048
            },
            keep_alive="30m"
        )

        resposta = resultado["message"]["content"].strip()

        if not resposta:
            return FALLBACK

        historico[numero].append({
            "role": "user",
            "content": pergunta
        })

        historico[numero].append({
            "role": "assistant",
            "content": resposta
        })

        historico[numero] = historico[numero][-8:]

        return resposta

    except Exception as erro:

        print(f"Erro ao consultar Ollama: {erro}")

        return (
            "Desculpe, tive um problema ao consultar "
            "as informações neste momento. 😕\n\n"
            "Pode tentar novamente daqui a pouco?"
        )


# ==========================================================
# PROCESSAMENTO DA PERGUNTA
# ==========================================================

def processar_pergunta(pergunta, numero):

    resposta_rapida = responder_pergunta_frequente(
        pergunta
    )

    if resposta_rapida is not None:

        # Ao se despedir, encerra o contexto anterior do contato.
        if resposta_rapida == MENSAGEM_FINAL:
            historico[numero].clear()

        return resposta_rapida

    return responder_com_ollama(
        pergunta,
        numero
    )


# ==========================================================
# ENVIO DE MENSAGENS PELO WHATSAPP
# ==========================================================

def enviar_mensagem(numero, mensagem):

    cabecalhos = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    dados = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {
            "body": mensagem
        }
    }

    try:

        resposta = requests.post(
            URL_WHATSAPP,
            headers=cabecalhos,
            json=dados,
            timeout=20
        )

        if resposta.status_code not in (200, 201):

            print("Erro ao enviar mensagem:")
            print(resposta.status_code)
            print(resposta.text)

        else:

            print(
                f"Mensagem enviada com sucesso para {numero}"
            )

    except requests.RequestException as erro:

        print(f"Erro de conexão com WhatsApp: {erro}")


# ==========================================================
# PROCESSAMENTO EM SEGUNDO PLANO
# ==========================================================

def processar_mensagem(numero, mensagem):

    print(
        f"Mensagem recebida de {numero}: {mensagem}"
    )

    resposta = processar_pergunta(
        mensagem,
        numero
    )

    enviar_mensagem(
        numero,
        resposta
    )


# ==========================================================
# WEBHOOK - VERIFICAÇÃO DA META
# ==========================================================

@app.route("/webhook", methods=["GET"])
def verificar_webhook():

    modo = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    desafio = request.args.get("hub.challenge")

    if (
        modo == "subscribe"
        and token == TOKEN_VERIFICACAO
    ):

        print("Webhook verificado com sucesso!")

        return desafio, 200

    return "Token inválido", 403


# ==========================================================
# WEBHOOK - RECEBIMENTO DAS MENSAGENS
# ==========================================================

@app.route("/webhook", methods=["POST"])
def receber_mensagem():

    dados = request.get_json(silent=True)

    if not dados:
        return jsonify({"status": "sem dados"}), 200

    try:

        entradas = dados.get("entry", [])

        for entrada in entradas:

            alteracoes = entrada.get("changes", [])

            for alteracao in alteracoes:

                valor = alteracao.get("value", {})

                mensagens = valor.get("messages", [])

                for mensagem in mensagens:

                    identificador = mensagem.get("id")

                    if identificador:

                        with lock_mensagens:

                            if identificador in mensagens_processadas:
                                continue

                            mensagens_processadas.add(
                                identificador
                            )

                            if len(mensagens_processadas) > 1000:
                                mensagens_processadas.clear()

                    if mensagem.get("type") != "text":
                        continue

                    numero = mensagem.get("from")

                    texto = mensagem.get(
                        "text", {}
                    ).get("body", "").strip()

                    if not numero or not texto:
                        continue

                    thread = threading.Thread(
                        target=processar_mensagem,
                        args=(numero, texto),
                        daemon=True
                    )

                    thread.start()

    except Exception as erro:

        print(f"Erro ao receber mensagem: {erro}")

    return jsonify({"status": "recebido"}), 200


# ==========================================================
# INICIALIZAÇÃO DO SERVIDOR
# ==========================================================

if __name__ == "__main__":

    print("\n====================================")
    print(" CHATBOT DA FACULDADE ANHANGUERA")
    print("====================================")

    if not CONHECIMENTO:
        print("AVISO: conhecimento.txt não foi carregado.")

    if not ACCESS_TOKEN.strip():
        print("AVISO: falta configurar o token da Meta.")

    print(f"Modelo: {MODELO_OLLAMA}")
    print("Servidor Flask: porta 5000")
    print("====================================\n")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
