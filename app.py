import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- VARIABLES DE ENTORNO (Corregidas) ---
# El código busca la "etiqueta" de la caja, no el contenido.
API_KEY = os.getenv("WXO_API_KEY")
SERVICE_URL = os.getenv("WXO_SERVICE_URL")
AGENT_ID = os.getenv("WXO_AGENT_ID")

# --- BLOQUE DE DIAGNÓSTICO (Esto saldrá en los logs) ---
print("=========================================")
print(" 🕵️‍♂️ INICIANDO DIAGNÓSTICO DE VARIABLES")
print(f" 1. API KEY detectada:   {'✅ SI' if API_KEY else '❌ NO (Revisa WXO_API_KEY)'}")
print(f" 2. SERVICE URL detectada: {'✅ SI' if SERVICE_URL else '❌ NO (Revisa WXO_SERVICE_URL)'}")
print(f" 3. AGENT ID detectada:  {'✅ SI' if AGENT_ID else '❌ NO (Revisa WXO_AGENT_ID)'}")
print("=========================================")

# ... (El resto de tu código sigue igual: def get_iam_token etc.)

def get_iam_token():
    try:
        response = requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": API_KEY}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        print(f"Error IAM: {response.text}")
    except Exception as e:
        print(f"Excepción IAM: {e}")
    return None

@app.route('/', methods=['POST'])
def webhook():
    # 1. Validar que sea un mensaje de Google Chat
    event = request.get_json()
    if not event or event.get('type') != 'MESSAGE':
        return jsonify({}) # Responder vacío si no es mensaje (ej: ping)

    user_message = event['message']['text']
    sender_email = event['message']['sender']['email']
    print(f"📩 Mensaje de {sender_email}: {user_message}")

    # 2. Autenticar con IBM
    token = get_iam_token()
    if not token:
        return jsonify({"text": "Error: No pude conectar con IBM IAM."})

    # 3. Enviar a Watsonx Orchestrate (/runs)
    try:
        base_url = SERVICE_URL.strip().rstrip('/')
        run_res = requests.post(
            f"{base_url}/v1/orchestrate/runs?multiple_content=true",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"agent_id": AGENT_ID, "message": {"role": "user", "content": user_message}}
        )

        if run_res.status_code not in [200, 201, 202]:
            return jsonify({"text": f"Error WxO ({run_res.status_code}): El agente no está disponible."})

        thread_id = run_res.json().get('thread_id')

        # 4. Esperar Respuesta (Polling)
        # Google Chat espera respuesta en ~30s. Hacemos polling rápido.
        for _ in range(14): # Aprox 28 segundos
            msg_res = requests.get(
                f"{base_url}/v1/orchestrate/threads/{thread_id}/messages",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
            )
            
            if msg_res.status_code == 200:
                response_data = msg_res.json()
                # Manejo robusto de lista vs dict (lo que validamos antes)
                msgs = response_data if isinstance(response_data, list) else response_data.get('data', [])
                
                if msgs:
                    last_msg = msgs[-1]
                    if last_msg.get('role') == 'assistant':
                        content = last_msg.get('content', [])
                        if content:
                            text_response = content[0].get('text', "")
                            # RESPUESTA FINAL A GOOGLE CHAT
                            return jsonify({"text": text_response})
            
            time.sleep(2)
        
        return jsonify({"text": "El agente está pensando más de lo normal. Por favor espera..."})

    except Exception as e:
        print(f"Error critico: {e}")
        return jsonify({"text": "Ocurrió un error interno en el middleware."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
