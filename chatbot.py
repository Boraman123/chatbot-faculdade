from flask import Flask, request
import ollama
import requests
import re

app = Flask(__name__)

# =========================================================
# CONFIGURAÇÕES DO WHATSAPP / META
# =========================================================

PHONE_NUMBER_ID = "1279935878543572"

# COLOQUE SEU ACCESS TOKEN AQUI
ACCESS_TOKEN = "EAAekHdZCE5acBSYcFwoPkIeSxQqiNlGF7ZAwLNj1b8ZCIocr8X0M04gZBuDT6hpXXm1dZAOWbJ0NJkFelCZAjm1G6l8Sx92ubfOxV05IExlXMBrzOmdSXQAOMQTGeofWDzK5ZBuOo0yhUUZBRaGmBtSDzrmYyNNbo2OgENwOhHWgEoEOdNfeRQcM1jKwlGW4mMy7UwZDZD"

# Token usado na verificação do Webhook
TOKEN_VERIFICACAO = "meu_token_faculdade"

WHATSAPP_URL = f"https://graph.facebook.com/v26.0/{PHONE_NUMBER_ID}/messages"


# =========================================================
# CARREGAR BASE DE CONHECIMENTO
# =========================================================

with open("conhecimento.txt", "r", encoding="utf-8") as arquivo:
    conhecimento = arquivo.read()


# =========================================================
# DIVIDIR BASE DE CONHECIMENTO EM BLOCOS
# =========================================================

def dividir_conhecimento(texto):

    blocos = re.split(
        r"\n(?=[A-ZÁÉÍÓÚÃÕÇ ]+\n)",
        texto
    )

    blocos = [
        bloco.strip()
        for bloco in blocos
        if bloco.strip()
    ]

    return blocos


blocos_conhecimento = dividir_conhecimento(conhecimento)


# =========================================================
# HISTÓRICO DOS USUÁRIOS
# =========================================================

historicos = {}


# =========================================================
# EVITAR MENSAGENS DUPLICADAS
# =========================================================

mensagens_processadas = set()


# =========================================================
# PALAVRAS QUE NÃO AJUDAM NA BUSCA
# =========================================================

palavras_ignoradas = {
    "a", "o", "as", "os",
    "um", "uma", "uns", "umas",
    "de", "da", "do", "das", "dos",
    "em", "no", "na", "nos", "nas",
    "para", "por",
    "com", "sem",
    "e", "ou",
    "que",
    "é", "são",
    "qual", "quais",
    "como",
    "quando",
    "onde",
    "me", "te",
    "se",
    "eu", "você",
    "tem", "têm",
    "sobre"
}


# =========================================================
# BUSCAR INFORMAÇÃO RELEVANTE
# =========================================================

def buscar_informacao(pergunta):

    pergunta_limpa = pergunta.lower()

    pergunta_limpa = re.sub(
        r"[^\w\s]",
        "",
        pergunta_limpa
    )

    palavras = set(
        palavra
        for palavra in pergunta_limpa.split()
        if palavra not in palavras_ignoradas
    )

    resultados = []

    for bloco in blocos_conhecimento:

        bloco_limpo = bloco.lower()

        bloco_limpo = re.sub(
            r"[^\w\s]",
            "",
            bloco_limpo
        )

        palavras_bloco = set(bloco_limpo.split())

        pontuacao = len(
            palavras.intersection(palavras_bloco)
        )

        if pontuacao > 0:
            resultados.append(
                (pontuacao, bloco)
            )

    resultados.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # Pega somente os 3 blocos mais relevantes
    melhores = resultados[:3]

    if not melhores:
        return ""

    return "\n\n".join(
        bloco for _, bloco in melhores
    )


# =========================================================
# GERAR RESPOSTA
# =========================================================

def responder(pergunta, usuario_id):

    # -----------------------------------------------------
    # NORMALIZAR TEXTO
    # -----------------------------------------------------

    pergunta_minuscula = pergunta.lower().strip()

    # -----------------------------------------------------
    # COMANDO SAIR
    # -----------------------------------------------------

    if pergunta_minuscula == "sair":

        # Limpa o histórico do usuário
        if usuario_id in historicos:
            del historicos[usuario_id]

        return "Até mais! 👋"

    # -----------------------------------------------------
    # SAUDAÇÕES
    # -----------------------------------------------------

    saudacoes = [
        "oi",
        "olá",
        "ola",
        "bom dia",
        "boa tarde",
        "boa noite",
        "oii",
        "oii!",
        "olá!",
        "ola!"
    ]

    if pergunta_minuscula in saudacoes:

        resposta = (
            "Olá! 👋\n"
            "Sou o assistente virtual da faculdade. "
            "Como posso ajudar?"
        )

        return resposta

    # -----------------------------------------------------
    # BUSCAR SOMENTE A INFORMAÇÃO NECESSÁRIA
    # -----------------------------------------------------

    informacao_relevante = buscar_informacao(pergunta)

    # -----------------------------------------------------
    # SE NÃO ENCONTRAR
    # -----------------------------------------------------

    if not informacao_relevante:

        resposta = (
            "Não encontrei essa informação "
            "na base da faculdade."
        )

        return resposta

    # -----------------------------------------------------
    # HISTÓRICO
    # -----------------------------------------------------

    if usuario_id not in historicos:
        historicos[usuario_id] = []

    historicos[usuario_id].append({
        "role": "user",
        "content": pergunta
    })

    # -----------------------------------------------------
    # PROMPT
    # -----------------------------------------------------

    prompt_sistema = f"""
Você é o assistente virtual de uma faculdade.

Responda às perguntas dos alunos usando SOMENTE
as informações fornecidas na base de conhecimento abaixo.

Não invente informações.

Se a informação não estiver na base, diga claramente
que essa informação não está disponível na base da faculdade.

Responda em português do Brasil.

Seja direto, claro e natural.

Não diga que você é um modelo de linguagem.

Não mencione a base de conhecimento desnecessariamente.

BASE DE CONHECIMENTO RELEVANTE:

{informacao_relevante}
"""

    # -----------------------------------------------------
    # ENVIAR PARA OLLAMA
    # -----------------------------------------------------

    try:

        mensagens = [
            {
                "role": "system",
                "content": prompt_sistema
            }
        ]

        # Adiciona somente as últimas mensagens do histórico
        mensagens.extend(
            historicos[usuario_id][-6:]
        )

        resposta_ollama = ollama.chat(
            model="llama3.2:latest",
            messages=mensagens
        )

        resposta = resposta_ollama["message"]["content"].strip()

        # -------------------------------------------------
        # REMOVER POSSÍVEL "assistant:" DA RESPOSTA
        # -------------------------------------------------

        resposta = re.sub(
            r"^\s*assistant\s*:\s*",
            "",
            resposta,
            flags=re.IGNORECASE
        ).strip()

        # -------------------------------------------------
        # SALVAR RESPOSTA NO HISTÓRICO
        # -------------------------------------------------

        historicos[usuario_id].append({
            "role": "assistant",
            "content": resposta
        })

        return resposta

    except Exception as erro:

        print("ERRO NO OLLAMA:")
        print(erro)

        return (
            "Desculpe, ocorreu um erro ao "
            "processar sua pergunta."
        )


# =========================================================
# ENVIAR MENSAGEM PELO WHATSAPP
# =========================================================

def enviar_whatsapp(numero, mensagem):

    headers = {
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

    resposta = requests.post(
        WHATSAPP_URL,
        headers=headers,
        json=dados
    )

    print("RESPOSTA DA META:")
    print(resposta.status_code)
    print(resposta.text)


# =========================================================
# VERIFICAÇÃO DO WEBHOOK
# =========================================================

@app.route("/webhook", methods=["GET"])
def verificar_webhook():

    modo = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    desafio = request.args.get("hub.challenge")

    if modo == "subscribe" and token == TOKEN_VERIFICACAO:

        print("WEBHOOK VERIFICADO!")

        return desafio, 200

    print("ERRO NA VERIFICAÇÃO DO WEBHOOK")

    return "Token inválido", 403


# =========================================================
# RECEBER MENSAGENS
# =========================================================

@app.route("/webhook", methods=["POST"])
def receber_webhook():

    dados = request.get_json()

    print("\n===================================")
    print("MENSAGEM RECEBIDA DA META")
    print("===================================")
    print(dados)

    # -----------------------------------------------------
    # VERIFICAR SE É EVENTO DO WHATSAPP
    # -----------------------------------------------------

    if dados.get("object") != "whatsapp_business_account":

        return "IGNORADO", 200

    # -----------------------------------------------------
    # PERCORRER OS EVENTOS
    # -----------------------------------------------------

    for entrada in dados.get("entry", []):

        for alteracao in entrada.get("changes", []):

            valor = alteracao.get("value", {})

            mensagens = valor.get("messages", [])

            for mensagem in mensagens:

                # -------------------------------------------------
                # ID ÚNICO DA MENSAGEM
                # -------------------------------------------------

                mensagem_id = mensagem.get("id")

                # -------------------------------------------------
                # EVITAR PROCESSAR A MESMA MENSAGEM DUAS VEZES
                # -------------------------------------------------

                if mensagem_id:

                    if mensagem_id in mensagens_processadas:

                        print("Mensagem duplicada ignorada.")

                        continue

                    mensagens_processadas.add(mensagem_id)

                # -------------------------------------------------
                # SOMENTE MENSAGENS DE TEXTO
                # -------------------------------------------------

                if mensagem.get("type") != "text":

                    continue

                # -------------------------------------------------
                # NÚMERO DO USUÁRIO
                # -------------------------------------------------

                numero_usuario = mensagem.get("from")

                # -------------------------------------------------
                # TEXTO RECEBIDO
                # -------------------------------------------------

                texto_usuario = mensagem.get(
                    "text",
                    {}
                ).get(
                    "body",
                    ""
                )

                print("USUÁRIO:", numero_usuario)
                print("PERGUNTA:", texto_usuario)

                # -------------------------------------------------
                # GERAR RESPOSTA
                # -------------------------------------------------

                resposta = responder(
                    texto_usuario,
                    numero_usuario
                )

                print("RESPOSTA:", resposta)

                # -------------------------------------------------
                # ENVIAR RESPOSTA
                # -------------------------------------------------

                enviar_whatsapp(
                    numero_usuario,
                    resposta
                )

    return "EVENT_RECEIVED", 200


# =========================================================
# INICIAR SERVIDOR
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
