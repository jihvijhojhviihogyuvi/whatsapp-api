# WhatsApp MCP API

Standalone WhatsApp sender that pairs through WhatsApp Web multi-device auth, stores the auth state locally, and then sends messages through a local REST/MCP API.

It exposes both:

- MCP-over-HTTP endpoint: `POST http://127.0.0.1:8790/mcp`
- REST API endpoints for scripts and local tools

This uses `whatsapp-web.js`, an unofficial WhatsApp Web client. Use it only for accounts and recipients you control or have permission to message. Automated WhatsApp use may violate WhatsApp terms.

## Get Started

First, clone the repository:

```bash
git clone https://github.com/jihvijhojhviihogyuvi/whatsapp-api.git
```

Then, navigate into the project directory:

```powershell
cd whatsapp-api\whatsapp-mcp-api
```

## Install

```powershell
npm install
```

If your `npm` shell shim is broken, use the full Windows command:

```powershell
"C:\Program Files\nodejs\npm" install
```

## Run

```powershell
npm start
```

Default server:

```text
http://127.0.0.1:8790
```

## Pair

Start the server, then request a pairing code:

```powershell
curl.exe -X POST http://127.0.0.1:8790/api/pairing-code `
  -H "content-type: application/json" `
  -d "{\"phone_number\":\"15551234567\"}"
```

On your phone, open WhatsApp:

```text
Settings -> Linked devices -> Link a device -> Link with phone number instead
```

Enter the returned code. The auth state is saved in `.wwebjs_auth/session-default/`.

## Preserve Auth

Do not delete this folder:

```text
./.wwebjs_auth/session-default
```

That Chrome profile contains the linked-device auth. It is excluded from git because it is sensitive. Back up the whole `.wwebjs_auth` folder if you want to preserve the login across machine moves or workspace cleanup.

## Send

```powershell
curl.exe -X POST http://127.0.0.1:8790/api/send `
  -H "content-type: application/json" `
  -d "{\"phone_number\":\"15551234567\",\"message\":\"hello from the local API\"}"
```

## List Chats

```powershell
curl.exe "http://127.0.0.1:8790/api/chats?limit=20"
```

## Read Last Messages

```powershell
curl.exe "http://127.0.0.1:8790/api/messages?phone_number=15551234567&limit=10"
```

Or with JSON:

```powershell
curl.exe -X POST http://127.0.0.1:8790/api/messages `
  -H "content-type: application/json" `
  -d "{\"phone_number\":\"15551234567\",\"limit\":10}"
```

## MCP Tools

- `whatsapp_status`: connection and auth status
- `whatsapp_start_auth`: start WhatsApp Web authentication
- `whatsapp_pairing_code`: get a phone-number pairing code
- `whatsapp_send_message`: send a text message
- `whatsapp_list_chats`: list recent chats
- `whatsapp_read_messages`: read recent messages from a phone-number chat
- `whatsapp_logout`: logout and clear the current WhatsApp connection

## Environment

```powershell
$env:WHATSAPP_MCP_HOST = "127.0.0.1"
$env:WHATSAPP_MCP_PORT = "8790"
$env:WHATSAPP_AUTH_DIR = "C:\path\to\auth"
$env:WHATSAPP_CHROME_EXECUTABLE = "C:\Program Files\Google\Chrome\Application\chrome.exe"
```
