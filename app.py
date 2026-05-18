import os
from flask import Flask, render_template_string, jsonify, request
from dotenv import load_dotenv
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode

load_dotenv()

app = Flask(__name__)

# Configure Plaid Client
configuration = plaid.Configuration(
    host=plaid.Environment.Development if os.getenv('PLAID_ENV') == 'development' else plaid.Environment.Sandbox,
    api_key={
        'clientId': os.getenv('PLAID_CLIENT_ID'),
        'secret': os.getenv('PLAID_SECRET'),
    }
)
api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Pi Finance Linker</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 100px; background-color: #f4f6f9; }
        button { padding: 15px 30px; font-size: 18px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
        button:hover { background-color: #0056b3; }
    </style>
</head>
<body>
    <h2>🔗 Link your UK Bank/Credit Accounts</h2>
    <p>Click the button below to link Monzo, Amex, or Nationwide.</p>
    <button id="link-button">Connect an Account</button>

    <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
    <script>
        async function startLink() {
            const response = await fetch('/api/create_link_token', { method: 'POST' });
            const data = await response.json();
            
            const handler = Plaid.create({
                token: data.link_token,
                onSuccess: async (public_token, metadata) => {
                    await fetch('/api/exchange_public_token', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ public_token: public_token, bank_name: metadata.institution.name })
                    });
                    alert(metadata.institution.name + " linked successfully! You can link another or close this tab.");
                },
            });
            handler.open();
        }
        document.getElementById('link-button').onclick = startLink;
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/create_link_token', methods=['POST'])
def create_link_token():
    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id='pi_user_1'),
        client_name="Pi Finance Tracker",
        products=[Products('transactions')],
        country_codes=[CountryCode('GB')],
        language='en'
    )
    response = client.link_token_create(request)
    return jsonify(response.to_dict())

@app.route('/api/exchange_public_token', methods=['POST'])
def exchange_public_token():
    data = request.get_json()
    exchange_request = ItemPublicTokenExchangeRequest(public_token=data['public_token'])
    exchange_response = client.item_public_token_exchange(exchange_request)
    
    access_token = exchange_response['access_token']
    bank_name = data['bank_name'].lower().replace(" ", "_")
    
    # Saves the permanent access token locally to a text file
    with open(f"token_{bank_name}.txt", "w") as f:
        f.write(access_token)
        
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)