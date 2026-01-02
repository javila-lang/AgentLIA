import os
import requests
from flask import Flask, request, jsonify
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

app = Flask(__name__)

@app.route('/', methods=['POST'])
def webhook():
    # --- BLOQUE DE DIAGNÓSTICO EN TIEMPO REAL ---
    debug_status = []
    try:
        # 1. Validar Variables de Entorno
        api_key = os.getenv("WXO_API_KEY")
        service_url = os.getenv("WXO_SERVICE_URL")
        agent_id = os.getenv("WXO_AGENT_ID")
        
        debug_status.append(f"API_KEY: {'✅' if api_key else '❌ FALTA'}")
        debug_status.append(f"URL: {'✅' if service_url else '❌ FALTA'}")
        debug_status.append(f"AGENT_ID: {'✅' if agent_id else '❌ FALTA'}")

        # Si faltan variables, avisar al chat
        if not (api_key and service_url and agent_id):
            return jsonify({"text": f"⚠️ ERROR DE CONFIGURACIÓN:\n" + "\n".join(debug_status)})

        # 2. Procesar Mensaje de Google Chat
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"text": "Bot activo, pero no recibí mensaje de texto."})
        
        user_message = data['message']['text']

        # 3. Intentar conectar con Watsonx Orchestrate
        authenticator = IAMAuthenticator(api_key)
        token = authenticator.token_manager.get_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "sessionId": "session-debug-001",
            "message": {"text": user_message}
        }
        
        # Enviar a Watsonx
        response = requests.post(f"{service_url}/agents/{agent_id}/sessions", json=payload, headers=headers)
        
        # 4. Manejar respuesta de Watsonx
        if response.status_code == 200:
            wxo_data = response.json()
            # Intentar extraer el texto de la respuesta
            try:
                bot_text = wxo_data['messages'][0]['text']
            except:
                bot_text = f"Respuesta recibida (JSON crudo): {str(wxo_data)}"
                
            return jsonify({"text": bot_text})
        else:
            return jsonify({"text": f"🛑 ERROR WATSONX ({response.status_code}):\n{response.text}"})

    except Exception as e:
        # 5. SI ALGO FALLA, ENVIAR EL ERROR AL CHAT
        return jsonify({"text": f"🔥 ERROR CRÍTICO DEL SISTEMA:\n{str(e)}\n\nEstado Variables:\n" + "\n".join(debug_status)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
